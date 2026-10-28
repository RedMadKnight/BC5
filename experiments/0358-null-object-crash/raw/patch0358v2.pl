#!/usr/bin/perl
# BC5 experiment 0358, trap v2: applied AFTER patch0358.pl to the same PRIVATE copies (the shared tree is only read).
#   loader/runtimeLinker.cpp: (1) a journal line per guest thread-local block creation (host id, the guest thread as the
#                       title knows it, run time); (2) after the per-thread slots of the v1 trap, the title's pool state
#                       read safely (process_vm_readv): the override's arena pointer at image+0xb064018, the special
#                       index at image+0xb064020, the pool object from image+0x8e51418 with +0x20/+0x88/+0x8c/+0x94/+0x98
#                       (the spin at eboot.bin+0x3ccb180 waits while +0x94 >= +0x98), and the three worker tables'
#                       +0x290 (capacity) / +0x294 (count) at image+0xb0639c0, +0xb0636d0, +0xb063cb0 (F448).
#   libs/bc5LleAgc.cpp:  (3) bc5_pool_sample(): once a second, from the game thread's flip (frame_profile_flip, before its
#                       profile switch), the same pool fields journaled with the sample's own cost in ns.
# usage: patch0358v2.pl <private src root>
use strict;
use warnings;
my ($root) = @ARGV;
die "usage: patch0358v2.pl <src root>\n" unless defined $root;
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

# The guest reads shared by (2) and (3): a copy in each unit (static, no new header).
my $reader =
	"// BC5 (experiment 0358, trap v2): a guest read that cannot fault (process_vm_readv on the own process returns\n" .
	"// EFAULT for an unmapped page instead of a SIGSEGV inside a crash print or the flip path).\n" .
	"static bool bc5_guest_read(uint64_t addr, void* out, size_t n) {\n" .
	"\tstruct iovec l {out, n};\n" .
	"\tstruct iovec r {reinterpret_cast<void*>(addr), n};\n" .
	"\treturn process_vm_readv(getpid(), &l, 1, &r, 1, 0) == static_cast<ssize_t>(n);\n" .
	"}\n" .
	"// The title's frame-block pool (F448): the fields the spin at eboot.bin+0x3ccb180 and its callers use.\n" .
	"struct Bc5PoolState {\n" .
	"\tuint64_t pool = 0, f20 = 0, f88 = 0, over = 0;\n" .
	"\tint32_t  f8c = 0, f94 = 0, f98 = 0, special = 0;\n" .
	"\tint32_t  cap[3] {}, cnt[3] {};\n" .
	"\tbool     pool_ok = false;\n" .
	"};\n" .
	"static Bc5PoolState bc5_pool_state(uint64_t base) {\n" .
	"\tBc5PoolState s;\n" .
	"\tbc5_guest_read(base + 0xb064018, &s.over, 8);\n" .
	"\tbc5_guest_read(base + 0xb064020, &s.special, 4);\n" .
	"\tif (bc5_guest_read(base + 0x8e51418, &s.pool, 8) && s.pool != 0) {\n" .
	"\t\ts.pool_ok = bc5_guest_read(s.pool + 0x20, &s.f20, 8) && bc5_guest_read(s.pool + 0x88, &s.f88, 8) &&\n" .
	"\t\t            bc5_guest_read(s.pool + 0x8c, &s.f8c, 4) && bc5_guest_read(s.pool + 0x94, &s.f94, 4) &&\n" .
	"\t\t            bc5_guest_read(s.pool + 0x98, &s.f98, 4);\n" .
	"\t}\n" .
	"\tconst uint64_t tables[3] {0xb0639c0, 0xb0636d0, 0xb063cb0};\n" .
	"\tfor (int k = 0; k < 3; k++) {\n" .
	"\t\tbc5_guest_read(base + tables[k] + 0x290, &s.cap[k], 4);\n" .
	"\t\tbc5_guest_read(base + tables[k] + 0x294, &s.cnt[k], 4);\n" .
	"\t}\n" .
	"\treturn s;\n" .
	"}\n";
my $fmt = "pool %016\" PRIx64 \"%s count %d capacity %d flags %08\" PRIx32 \" +0x20 %016\" PRIx64 \" +0x88 %016\" PRIx64 \"; override arena %016\" PRIx64 \" special %d; tables count/capacity %d/%d %d/%d %d/%d";
my $args = "s.pool, s.pool_ok ? \"\" : \" (unreadable)\", s.f94, s.f98, static_cast<uint32_t>(s.f8c), s.f20, s.f88, s.over, s.special, s.cnt[0], s.cap[0], s.cnt[1], s.cap[1], s.cnt[2], s.cap[2]";

my $rtl = "$root/src/loader/runtimeLinker.cpp";
patch($rtl,
	# includes and the reader, before the crash log helper (v1's externs sit near g_tls_main_program; the reader needs <sys/uio.h>)
	"#include <execinfo.h>\n",
	"#include <execinfo.h>\n#include <sys/uio.h> // BC5 (experiment 0358, trap v2)\n#include <unistd.h>\n",

	"static void Bc5CrashLog(const char* format, ...) {\n",
	$reader . "\nstatic void Bc5CrashLog(const char* format, ...) {\n",

	# (1) the block journal: after the image copy of a new block
	"\t\tif (!program->tls.init_image.empty()) {\n\t\t\tstd::memcpy(tls.ptr, program->tls.init_image.data(), program->tls.init_image.size());\n",
	"\t\t// BC5 (experiment 0358, trap v2): every guest thread-local block's birth, dated and named (F447: the title's\n" .
	"\t\t// main thread kept the image's -1 worker slots; this says when its block was made and on which host thread).\n" .
	"\t\t{\n" .
	"\t\t\tstatic const auto t0 = std::chrono::steady_clock::now();\n" .
	"\t\t\tchar who[256] {};\n" .
	"\t\t\tbc5_pthread_self_line(who, sizeof(who));\n" .
	"\t\t\tstd::fprintf(stderr, \"tls block: t %.3f s, host id %d, program %s, %s\\n\",\n" .
	"\t\t\t             std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count(), Common::Thread::GetThreadIdUnique(),\n" .
	"\t\t\t             program == g_tls_main_program ? \"main\" : \"other\", who);\n" .
	"\t\t}\n" .
	"\t\tif (!program->tls.init_image.empty()) {\n\t\t\tstd::memcpy(tls.ptr, program->tls.init_image.data(), program->tls.init_image.size());\n",

	# (2) the pool state after v1's per-thread block lines
	"\t\t\t\t\t            *reinterpret_cast<const uint64_t*>(tcb - 0x98), tid == Common::Thread::GetThreadIdUnique() ? \" <- faulting\" : \"\");\n\t\t\t\t}\n",
	"\t\t\t\t\t            *reinterpret_cast<const uint64_t*>(tcb - 0x98), tid == Common::Thread::GetThreadIdUnique() ? \" <- faulting\" : \"\");\n\t\t\t\t}\n" .
	"\t\t\t\t// trap v2: the pool (F448) at the fault\n" .
	"\t\t\t\t{\n" .
	"\t\t\t\t\tconst Bc5PoolState s = bc5_pool_state(prog->base_vaddr);\n" .
	"\t\t\t\t\tBc5CrashLog(\"thread trap: base %016\" PRIx64 \" " . $fmt . "\\n\", prog->base_vaddr, " . $args . ");\n" .
	"\t\t\t\t}\n",
);

my $agc = "$root/src/libs/bc5LleAgc.cpp";
patch($agc,
	"#include <sys/mman.h>\n",
	"#include <sys/mman.h>\n#include <sys/uio.h> // BC5 (experiment 0358, trap v2)\n",

	"static void frame_profile_flip(double drain_ms) {\n",
	$reader .
	"// Once a second from the game thread's flip: the pool's count against its capacity (F448: the crash is the\n" .
	"// pool-full reclaim on the main thread; does the count climb over the fight, or jump at the crash frame?). The\n" .
	"// cost outside a sampled frame is one timing_now() and a compare; a sample is nine small reads through the\n" .
	"// kernel, timed and printed.\n" .
	"static void bc5_pool_sample() {\n" .
	"\tstatic double   t_last   = 0;\n" .
	"\tstatic uint64_t cost_max = 0;\n" .
	"\tconst double    now      = timing_now();\n" .
	"\tif (now - t_last < 1.0) return;\n" .
	"\tt_last = now;\n" .
	"\tconst auto         c0 = std::chrono::steady_clock::now();\n" .
	"\tconst Bc5PoolState s  = bc5_pool_state(0x900000000ull);\n" .
	"\tconst auto         ns = static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now() - c0).count());\n" .
	"\tif (ns > cost_max) cost_max = ns;\n" .
	"\tjournal(\"pool sample: t %.3f s, " . $fmt . "; cost %\" PRIu64 \" ns (max %\" PRIu64 \")\\n\", now, " . $args . ", ns, cost_max);\n" .
	"}\n\n" .
	"static void frame_profile_flip(double drain_ms) {\n" .
	"\tbc5_pool_sample(); // BC5 (experiment 0358, trap v2): before the profile switch, every flip\n",
);
print "patch0358v2.pl: $marks edits\n";
