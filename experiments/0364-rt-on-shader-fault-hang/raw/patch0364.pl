#!/usr/bin/perl
# BC5 experiment 0364: in a PRIVATE copy of src/libs/bc5LleAgc.cpp (the shared tree is only read):
#   (1) the trap: at a fence timeout with a fault address, the title's mapped range covering it (name, bounds, type,
#       whether its name is lazy) or "no guest memory", journaled before the learned region is added;
#   (2) the fix candidate, BC5_DIRECT_USER_DATA_HINTS=1|<hex window>: after the render-target hints, every dispatch's
#       COMPUTE_USER_DATA_0..15 dwords are read as offsets under the title's window (exp 0346's learned window from
#       BC5_DIRECT_HOST_INDIRECT=learn:<hex>, or the switch's own hex), and the direct mapper is asked for the same
#       window around each (bc5/user_data_hint.hpp: below 32 MiB, 32 MiB from the page, once per 64 MiB region);
#       when it asked for chunks, a forced direct sync imports them before this job is submitted, which is what the
#       learned-region path does one hang too late.
# usage: patch0364.pl <private src root>
use strict;
use warnings;
my ($root) = @ARGV;
die "usage: patch0364.pl <src root>\n" unless defined $root;
my $marks = 0;
sub patch {
	my ($file, @pairs) = @_;
	open(my $h, "<", $file) or die "$file: $!\n";
	my $s = do { local $/; <$h> };
	close $h;
	my $crlf = ($s =~ /\r\n/) ? 1 : 0;
	while (@pairs) {
		my $old = shift @pairs;
		my $new = shift @pairs;
		if ($crlf) {
			$old =~ s/\n/\r\n/g;
			$new =~ s/\n/\r\n/g;
		}
		my $n = () = $s =~ /\Q$old\E/g;
		die "$file: anchor found $n times, expected once:\n$old\n" unless $n == 1;
		$s =~ s/\Q$old\E/$new/;
		$marks++;
	}
	open(my $w, ">", $file) or die "$file: $!\n";
	print $w $s;
	close $w;
}

my $agc = "$root/src/libs/bc5LleAgc.cpp";
patch($agc,
	"#include \"bc5/direct.hpp\"\n",
	"#include \"bc5/direct.hpp\"\n#include \"bc5/user_data_hint.hpp\" // BC5 (experiment 0364)\n",

	# (2) the user-data hints, defined right before hint_targets
	"static void hint_targets(const uint32_t* ib, uint32_t num_dwords) {\n",
	"// BC5 (experiment 0364): compute user-data hints (bc5/user_data_hint.hpp). BC5_DIRECT_USER_DATA_HINTS=1 uses the\n" .
	"// title's window from BC5_DIRECT_HOST_INDIRECT=learn:<hex>; =<hex> names the window itself. Returns the bytes asked.\n" .
	"static uint64_t g_ud_hint_calls = 0, g_ud_hint_dispatches = 0, g_ud_hint_candidates = 0, g_ud_hint_windows = 0, g_ud_hint_bytes = 0, g_ud_hint_missing = 0;\n" .
	"// What a window holds before the mapper is asked: the views of direct memory overlapping [lo, hi), how many bytes of\n" .
	"// them have no BO yet (the chunks the hint will make the sync import), and the first lazy view's name.\n" .
	"static uint64_t direct_unimported(uint64_t lo, uint64_t hi, unsigned* views_n, char* lazy_name, size_t lazy_n) {\n" .
	"\tuint64_t missing = 0;\n" .
	"\t*views_n = 0;\n" .
	"\tlazy_name[0] = 0;\n" .
	"\tif (!g_dmabuf || !g_dev) return 0;\n" .
	"\tfor (auto& S: g_d) {\n" .
	"\t\tif (dstate_fd(S) < 0) continue;\n" .
	"\t\tconst auto  views_p = t_pinned_views[S.kind == 0 ? 0 : 1] ? t_pinned_views[S.kind == 0 ? 0 : 1] : direct_views(S);\n" .
	"\t\tconst auto& views   = views_p->v;\n" .
	"\t\tfor (const auto& v: views) {\n" .
	"\t\t\tconst uint64_t a = lo > v.va ? lo : v.va;\n" .
	"\t\t\tconst uint64_t b = hi < v.va + v.size ? hi : v.va + v.size;\n" .
	"\t\t\tif (a >= b) continue;\n" .
	"\t\t\t(*views_n)++;\n" .
	"\t\t\tif (v.lazy && lazy_name[0] == 0) std::snprintf(lazy_name, lazy_n, \"%s\", v.name.c_str());\n" .
	"\t\t\tfor (uint64_t c = (v.off + (a - v.va)) & ~(kDChunk - 1); c < v.off + (b - v.va); c += kDChunk) {\n" .
	"\t\t\t\tauto it = std::upper_bound(S.bos.begin(), S.bos.end(), c, [](uint64_t o, const DBo& x) { return o < x.off; });\n" .
	"\t\t\t\tconst bool imported = it != S.bos.begin() && (--it)->off <= c && c < it->off + it->size;\n" .
	"\t\t\t\tif (!imported) missing += kDChunk;\n" .
	"\t\t\t}\n" .
	"\t\t}\n" .
	"\t}\n" .
	"\treturn missing;\n" .
	"}\n" .
	"static std::vector<std::pair<uint64_t, uint64_t>> g_ud_last_windows; // the windows this IB's hints asked for (for the check after the sync)\n" .
	"static uint64_t hint_user_data(const uint32_t* ib, uint32_t num_dwords) {\n" .
	"\tusing namespace bc5::user_data_hint;\n" .
	"\tg_ud_last_windows.clear();\n" .
	"\tstatic const uint64_t window = []() -> uint64_t {\n" .
	"\t\tconst char* e = std::getenv(\"BC5_DIRECT_USER_DATA_HINTS\");\n" .
	"\t\tif (e == nullptr || *e == 0 || std::strcmp(e, \"0\") == 0) return 0ull;\n" .
	"\t\tif (std::strcmp(e, \"1\") != 0) return static_cast<uint64_t>(std::strtoull(e, nullptr, 16));\n" .
	"\t\tconst char* h = std::getenv(\"BC5_DIRECT_HOST_INDIRECT\");\n" .
	"\t\tif (h != nullptr && std::strncmp(h, \"learn:\", 6) == 0) return static_cast<uint64_t>(std::strtoull(h + 6, nullptr, 16));\n" .
	"\t\tif (h != nullptr && std::strcmp(h, \"learn\") != 0 && std::strcmp(h, \"1\") != 0) return static_cast<uint64_t>(std::strtoull(h, nullptr, 16));\n" .
	"\t\treturn 0ull;\n" .
	"\t}();\n" .
	"\tstatic const uint64_t below = (std::getenv(\"BC5_DIRECT_HINT_BELOW_MIB\") ? std::strtoull(std::getenv(\"BC5_DIRECT_HINT_BELOW_MIB\"), nullptr, 10) : 32ull) << 20u;\n" .
	"\tstatic const uint64_t size  = (std::getenv(\"BC5_DIRECT_HINT_MIB\") ? std::strtoull(std::getenv(\"BC5_DIRECT_HINT_MIB\"), nullptr, 10) : 32ull) << 20u;\n" .
	"\tstatic std::vector<uint64_t> keys; // regions already asked for (cleared with g_hinted on a reopen is not needed: asking twice is a no-op)\n" .
	"\tstatic bool                  announced = false;\n" .
	"\tif (window == 0 || !g_dev || !g_dmabuf) return 0;\n" .
	"\tif (!announced) {\n" .
	"\t\tannounced = true;\n" .
	"\t\tjournal(\"hint user data: on, window 0x%\" PRIx64 \", below %.0f MiB, size %.0f MiB (experiment 0364)\\n\", window, static_cast<double>(below) / 1048576.0, static_cast<double>(size) / 1048576.0);\n" .
	"\t}\n" .
	"\tg_ud_hint_calls++;\n" .
	"\tuint32_t ud[kUserDataCount] = {};\n" .
	"\tbool     set[kUserDataCount] = {};\n" .
	"\tuint64_t asked_total = 0;\n" .
	"\tuint32_t i = 0;\n" .
	"\twhile (i < num_dwords) {\n" .
	"\t\tconst uint32_t h    = ib[i];\n" .
	"\t\tconst uint32_t type = h >> 30u;\n" .
	"\t\tuint32_t       len  = 1;\n" .
	"\t\tif (type == 3 || type == 0) {\n" .
	"\t\t\tconst uint32_t count = (h >> 16u) & 0x3fffu;\n" .
	"\t\t\tlen = count == 0x3fffu ? 1 : count + 2;\n" .
	"\t\t}\n" .
	"\t\tif (i + len > num_dwords) break;\n" .
	"\t\tconst uint32_t  op = (h >> 8u) & 0xffu;\n" .
	"\t\tconst uint32_t* p  = ib + i;\n" .
	"\t\tif (type == 3 && op == 0x76 && len >= 3) { // SET_SH_REG\n" .
	"\t\t\tfor (uint32_t k = 2; k < len; k++) {\n" .
	"\t\t\t\tconst uint32_t off = ((p[1] & 0xffffu) + k - 2) & 0xffffu;\n" .
	"\t\t\t\tif (is_user_data(off)) {\n" .
	"\t\t\t\t\tud[off - kUserData0]  = p[k];\n" .
	"\t\t\t\t\tset[off - kUserData0] = true;\n" .
	"\t\t\t\t}\n" .
	"\t\t\t}\n" .
	"\t\t} else if (type == 3 && (op == 0x15 || op == 0x16)) { // DISPATCH_DIRECT, DISPATCH_INDIRECT\n" .
	"\t\t\tg_ud_hint_dispatches++;\n" .
	"\t\t\tfor (uint32_t r = 0; r < kUserDataCount; r++) {\n" .
	"\t\t\t\tuint64_t addr = 0;\n" .
	"\t\t\t\tif (!set[r] || !candidate(window, ud[r], &addr)) continue;\n" .
	"\t\t\t\tg_ud_hint_candidates++;\n" .
	"\t\t\t\tconst uint64_t key = region_key(addr);\n" .
	"\t\t\t\tif (std::find(keys.begin(), keys.end(), key) != keys.end()) continue;\n" .
	"\t\t\t\tkeys.push_back(key);\n" .
	"\t\t\t\tunsigned       views_n = 0;\n" .
	"\t\t\t\tchar           lazy[64];\n" .
	"\t\t\t\tconst uint64_t missing = direct_unimported(window_lo(addr, below), window_hi(addr, size), &views_n, lazy, sizeof(lazy));\n" .
	"\t\t\t\tconst uint64_t asked   = direct_force(window_lo(addr, below), window_hi(addr, size));\n" .
	"\t\t\t\tif (missing != 0) g_ud_last_windows.emplace_back(window_lo(addr, below), window_hi(addr, size));\n" .
	"\t\t\t\tg_ud_hint_windows++;\n" .
	"\t\t\t\tg_ud_hint_bytes += asked;\n" .
	"\t\t\t\tg_ud_hint_missing += missing;\n" .
	"\t\t\t\tasked_total += missing; // a forced sync only when something is not imported yet\n" .
	"\t\t\t\tjournal(\"hint user data %u 0x%\" PRIx64 \" (dispatch at %u): window 0x%\" PRIx64 \"+0x%\" PRIx64 \", %u views%s%s, %.1f MiB marked, %.1f MiB not yet imported%s\\n\", r, addr, i,\n" .
	"\t\t\t\t        window_lo(addr, below), window_hi(addr, size) - window_lo(addr, below), views_n, lazy[0] != 0 ? \", lazy: \" : \"\", lazy, static_cast<double>(asked) / 1048576.0,\n" .
	"\t\t\t\t        static_cast<double>(missing) / 1048576.0, views_n == 0 ? \" (no view there)\" : missing != 0 ? \" <- the hint matters here\" : \"\");\n" .
	"\t\t\t}\n" .
	"\t\t}\n" .
	"\t\ti += len;\n" .
	"\t}\n" .
	"\tif (g_ud_hint_calls % 512 == 0) {\n" .
	"\t\tjournal(\"hint user data: %\" PRIu64 \" IBs, %\" PRIu64 \" dispatches, %\" PRIu64 \" candidates, %\" PRIu64 \" regions asked, %.1f MiB marked, %.1f MiB imported for them in all\\n\", g_ud_hint_calls,\n" .
	"\t\t        g_ud_hint_dispatches, g_ud_hint_candidates, g_ud_hint_windows, static_cast<double>(g_ud_hint_bytes) / 1048576.0, static_cast<double>(g_ud_hint_missing) / 1048576.0);\n" .
	"\t}\n" .
	"\treturn asked_total;\n" .
	"}\n\n" .
	"static void hint_targets(const uint32_t* ib, uint32_t num_dwords) {\n",

	# the call: after the render-target hints; a forced sync when chunks were asked, so this job sees them
	"\thint_targets(ib, num_dwords);\n\tconst uint64_t t2 = SoftCp::now_ns();\n",
	"\thint_targets(ib, num_dwords);\n" .
	"\tif (const uint64_t missing = hint_user_data(ib, num_dwords); missing != 0) { // BC5 (experiment 0364): the asked chunks imported before this job\n" .
	"\t\tconst uint64_t ts = SoftCp::now_ns();\n" .
	"\t\tdirect_sync(true);\n" .
	"\t\tuint64_t still = 0;\n" .
	"\t\tfor (const auto& [lo, hi]: g_ud_last_windows) {\n" .
	"\t\t\tunsigned vn = 0;\n" .
	"\t\t\tchar     ln[64];\n" .
	"\t\t\tstill += direct_unimported(lo, hi, &vn, ln, sizeof(ln));\n" .
	"\t\t}\n" .
	"\t\tjournal(\"hint user data: forced sync %.1f ms: %.1f MiB were not imported, %.1f MiB still are not%s\\n\", static_cast<double>(SoftCp::now_ns() - ts) / 1e6,\n" .
	"\t\t        static_cast<double>(missing) / 1048576.0, static_cast<double>(still) / 1048576.0, still != 0 ? \" <- the sync did not import them\" : \"\");\n" .
	"\t}\n" .
	"\tconst uint64_t t2 = SoftCp::now_ns();\n",

	# (1) the trap at the fault
	"\t\tif (r.fault_addr != 0 && (r.fault_addr >> 40u) != 0 && aliases_on()) alias_learn(r.fault_addr); // experiment 0056\n" .
	"\t\telse if (r.fault_addr != 0) learned_add(r.fault_addr);\n",
	"\t\tif (r.fault_addr != 0) { // BC5 (experiment 0364): the title's range at the fault, before the region is learned\n" .
	"\t\t\tstruct Hit { uint64_t fault; bool found; uint64_t start, size; int type; char name[64]; };\n" .
	"\t\t\tHit hit {r.fault_addr, false, 0, 0, -1, {}};\n" .
	"\t\t\tLibs::LibKernel::Memory::Bc5ForEachMappedRange(\n" .
	"\t\t\t    [](uint64_t start, uint64_t size, int type, int, const char* name, void* ctx) {\n" .
	"\t\t\t\t    auto* hh = static_cast<Hit*>(ctx);\n" .
	"\t\t\t\t    if (hh->found || hh->fault < start || hh->fault >= start + size) return;\n" .
	"\t\t\t\t    hh->found = true;\n" .
	"\t\t\t\t    hh->start = start;\n" .
	"\t\t\t\t    hh->size  = size;\n" .
	"\t\t\t\t    hh->type  = type;\n" .
	"\t\t\t\t    std::snprintf(hh->name, sizeof(hh->name), \"%s\", name != nullptr ? name : \"\");\n" .
	"\t\t\t    },\n" .
	"\t\t\t    &hit);\n" .
	"\t\t\tif (hit.found) {\n" .
	"\t\t\t\tjournal(\"fault view: 0x%\" PRIx64 \" is in the title's range 0x%\" PRIx64 \"+0x%\" PRIx64 \" \\\"%s\\\" type %d%s, covered for the GPU: %s\\n\", r.fault_addr, hit.start, hit.size, hit.name,\n" .
	"\t\t\t\t        hit.type, direct_lazy_name(hit.name) ? \" (a lazy name)\" : \"\", g_dev && covered_sorted(*g_dev->sorted_mappings(), r.fault_addr & ~0xfffull, 4) ? \"yes\" : \"no\");\n" .
	"\t\t\t} else {\n" .
	"\t\t\t\tjournal(\"fault view: 0x%\" PRIx64 \" is in no range of the title (no guest memory)\\n\", r.fault_addr);\n" .
	"\t\t\t}\n" .
	"\t\t}\n" .
	"\t\tif (r.fault_addr != 0 && (r.fault_addr >> 40u) != 0 && aliases_on()) alias_learn(r.fault_addr); // experiment 0056\n" .
	"\t\telse if (r.fault_addr != 0) learned_add(r.fault_addr);\n",
);
print "patch0364.pl: $marks edits\n";
