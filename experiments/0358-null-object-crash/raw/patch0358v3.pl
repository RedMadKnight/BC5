#!/usr/bin/perl
# BC5 experiment 0358, trap v3: applied AFTER patch0358.pl to the same PRIVATE copies (the shared tree is only read);
# replaces patch0358v2.pl (whose pool reading was wrong: image+0x8e51418 is not a pointer).
# What the code says (F449): a handle = (entry k = bits 0-1, index = bits 2-30, generation = bits 32-63) into the
# three worker entries at image+0xb0636d0 + k*0x2f0 (+0x288 objects array, 0xc0 each; +0x290 capacity; +0x294 live;
# +0x2a0 pending-handle list; +0x2ac pending count; +0x2e0 generation). A job object: +0x20 active, +0x80 the block
# function, +0x88 class bits, +0x8c flags, +0x90 started, +0x94 done, +0x98 total. The thread whose id (tcb-0x90) equals
# image+0x9b75c3c is the owner; when it waits (eboot.bin+0x3cca900 -> +0x3ccb180) it runs pending jobs itself
# (+0x3cca600) whose class intersects the owner mask image+0xb064038 (= 2 << N, N = image+0xb064010 workers,
# N = image+0xb064020 the special index); the override window (+0x3ccadc9..+0x3ccae5b) runs a block inline with the
# stack arena image+0xb064018 and the index N.
#   loader/runtimeLinker.cpp: (1) a journal line per guest thread-local block creation (as v2); (2) after the v1
#                       per-thread lines (now with the thread's job id and the owner mark): the job system's globals
#                       and every entry's pending jobs, decoded, the crash job's function (+0x4661e50) marked.
#   libs/bc5LleAgc.cpp:  (3) bc5_pool_sample(): once a second from the game thread's flip, per entry live/capacity,
#                       pending, owner-class pending, runnable pending, with the sample's cost in ns.
# usage: patch0358v3.pl <private src root>
use strict;
use warnings;
my ($root) = @ARGV;
die "usage: patch0358v3.pl <src root>\n" unless defined $root;
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
	"// BC5 (experiment 0358, trap v3): a guest read that cannot fault (process_vm_readv on the own process returns\n" .
	"// EFAULT for an unmapped page instead of a SIGSEGV inside a crash print or the flip path).\n" .
	"static bool bc5_guest_read(uint64_t addr, void* out, size_t n) {\n" .
	"\tstruct iovec l {out, n};\n" .
	"\tstruct iovec r {reinterpret_cast<void*>(addr), n};\n" .
	"\treturn process_vm_readv(getpid(), &l, 1, &r, 1, 0) == static_cast<ssize_t>(n);\n" .
	"}\n" .
	"// The title's job system (F448/F449): three worker entries, their pending jobs, the owner thread's globals.\n" .
	"struct Bc5Job {\n" .
	"\tint      k = 0, i = 0;\n" .
	"\tuint64_t handle = 0, obj = 0, fn = 0;\n" .
	"\tbool     valid = false;\n" .
	"\tint32_t  active = 0, started = 0, done = 0, total = 0;\n" .
	"\tuint32_t cls = 0, flags = 0;\n" .
	"};\n" .
	"struct Bc5JobSys {\n" .
	"\tuint32_t n_workers = 0, special = 0, owner_mask = 0, special_mask = 0, n1 = 0, n2 = 0, owner_id = 0, ids = 0;\n" .
	"\tuint64_t over = 0;\n" .
	"\tstruct Entry {\n" .
	"\t\tbool     ok = false;\n" .
	"\t\tint32_t  cap = 0, live = 0, pending = 0, owner_cls = 0, runnable = 0, bad = 0, nulls = 0;\n" .
	"\t\tuint32_t gen = 0;\n" .
	"\t\tuint64_t array = 0, list = 0;\n" .
	"\t} e[3];\n" .
	"};\n" .
	"static Bc5JobSys bc5_jobsys(uint64_t base, void (*cb)(const Bc5Job&, void*), void* ctx) {\n" .
	"\tBc5JobSys s;\n" .
	"\tbc5_guest_read(base + 0xb064010, &s.n_workers, 4);\n" .
	"\tbc5_guest_read(base + 0xb064020, &s.special, 4);\n" .
	"\tbc5_guest_read(base + 0xb064038, &s.owner_mask, 4);\n" .
	"\tbc5_guest_read(base + 0xb064034, &s.special_mask, 4);\n" .
	"\tbc5_guest_read(base + 0xb064028, &s.n1, 4);\n" .
	"\tbc5_guest_read(base + 0xb064024, &s.n2, 4);\n" .
	"\tbc5_guest_read(base + 0x9b75c3c, &s.owner_id, 4);\n" .
	"\tbc5_guest_read(base + 0x9b75c38, &s.ids, 4);\n" .
	"\tbc5_guest_read(base + 0xb064018, &s.over, 8);\n" .
	"\tstatic uint8_t  ent[3][0x2f0];\n" .
	"\tstatic uint64_t list[512];\n" .
	"\tstatic uint8_t  obj[0xc0];\n" .
	"\tfor (int k = 0; k < 3; k++) {\n" .
	"\t\tauto& e = s.e[k];\n" .
	"\t\te.ok    = bc5_guest_read(base + 0xb0636d0 + static_cast<uint64_t>(k) * 0x2f0, ent[k], sizeof(ent[k]));\n" .
	"\t\tif (!e.ok) continue;\n" .
	"\t\tstd::memcpy(&e.array, ent[k] + 0x288, 8);\n" .
	"\t\tstd::memcpy(&e.cap, ent[k] + 0x290, 4);\n" .
	"\t\tstd::memcpy(&e.live, ent[k] + 0x294, 4);\n" .
	"\t\tstd::memcpy(&e.list, ent[k] + 0x2a0, 8);\n" .
	"\t\tstd::memcpy(&e.pending, ent[k] + 0x2ac, 4);\n" .
	"\t\tstd::memcpy(&e.gen, ent[k] + 0x2e0, 4);\n" .
	"\t}\n" .
	"\tfor (int k = 0; k < 3; k++) {\n" .
	"\t\tauto&     e = s.e[k];\n" .
	"\t\tconst int n = e.ok && e.pending > 0 ? (e.pending < 512 ? e.pending : 512) : 0;\n" .
	"\t\tif (n == 0 || !bc5_guest_read(e.list, list, static_cast<size_t>(n) * 8)) continue;\n" .
	"\t\tfor (int i = 0; i < n; i++) {\n" .
	"\t\t\tBc5Job j;\n" .
	"\t\t\tj.k      = k;\n" .
	"\t\t\tj.i      = i;\n" .
	"\t\t\tj.handle = list[i];\n" .
	"\t\t\tif (j.handle == 0) {\n" .
	"\t\t\t\te.nulls++;\n" .
	"\t\t\t\tcontinue;\n" .
	"\t\t\t}\n" .
	"\t\t\tconst int      kk  = static_cast<int>(j.handle & 3u);\n" .
	"\t\t\tconst uint32_t idx = static_cast<uint32_t>(j.handle >> 2u) & 0x1fffffffu;\n" .
	"\t\t\tconst uint32_t gen = static_cast<uint32_t>(j.handle >> 32u);\n" .
	"\t\t\tif (kk < 3 && s.e[kk].ok && gen == s.e[kk].gen && static_cast<int32_t>(idx) < s.e[kk].live) {\n" .
	"\t\t\t\tj.obj   = s.e[kk].array + static_cast<uint64_t>(idx) * 0xc0;\n" .
	"\t\t\t\tj.valid = bc5_guest_read(j.obj, obj, sizeof(obj));\n" .
	"\t\t\t}\n" .
	"\t\t\tif (j.valid) {\n" .
	"\t\t\t\tstd::memcpy(&j.active, obj + 0x20, 4);\n" .
	"\t\t\t\tstd::memcpy(&j.fn, obj + 0x80, 8);\n" .
	"\t\t\t\tstd::memcpy(&j.cls, obj + 0x88, 4);\n" .
	"\t\t\t\tstd::memcpy(&j.flags, obj + 0x8c, 4);\n" .
	"\t\t\t\tstd::memcpy(&j.started, obj + 0x90, 4);\n" .
	"\t\t\t\tstd::memcpy(&j.done, obj + 0x94, 4);\n" .
	"\t\t\t\tstd::memcpy(&j.total, obj + 0x98, 4);\n" .
	"\t\t\t\tif ((j.cls & s.owner_mask) != 0) e.owner_cls++;\n" .
	"\t\t\t\tif (j.started < j.total) e.runnable++;\n" .
	"\t\t\t} else {\n" .
	"\t\t\t\te.bad++;\n" .
	"\t\t\t}\n" .
	"\t\t\tif (cb != nullptr) cb(j, ctx);\n" .
	"\t\t}\n" .
	"\t}\n" .
	"\treturn s;\n" .
	"}\n";

my $rtl = "$root/src/loader/runtimeLinker.cpp";
patch($rtl,
	"#include <execinfo.h>\n",
	"#include <execinfo.h>\n#include <sys/uio.h> // BC5 (experiment 0358, trap v3)\n#include <unistd.h>\n",

	# the reader before the crash-log helper's comment block (not between its format attribute and the function)
	"// BC5 (experiment 0318): the crash diagnostics of KytyExceptionHandler go to stderr through RawLog,\n",
	$reader . "\n// BC5 (experiment 0318): the crash diagnostics of KytyExceptionHandler go to stderr through RawLog,\n",

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

	# (2a) the per-thread line gains the thread's job id (tcb-0x90) and the owner mark
	"\t\t\t\tfor (const auto& [tid, block]: prog->tls.tlss) {\n",
	"\t\t\t\tuint32_t owner_id = 0; // trap v3: the owner thread's id at image+0x9b75c3c\n" .
	"\t\t\t\tbc5_guest_read(prog->base_vaddr + 0x9b75c3c, &owner_id, 4);\n" .
	"\t\t\t\tfor (const auto& [tid, block]: prog->tls.tlss) {\n",

	"\t\t\t\t\tBc5CrashLog(\"thread trap: host id %d guest id %d \\\"%s\\\": gen %d index %d ptr-0x98 %016\" PRIx64 \"%s\\n\", tid, gid, nm,\n" .
	"\t\t\t\t\t            *reinterpret_cast<const int32_t*>(tcb - 0x108), *reinterpret_cast<const int32_t*>(tcb - 0x104),\n" .
	"\t\t\t\t\t            *reinterpret_cast<const uint64_t*>(tcb - 0x98), tid == Common::Thread::GetThreadIdUnique() ? \" <- faulting\" : \"\");\n",
	"\t\t\t\t\tconst uint32_t jobid = *reinterpret_cast<const uint32_t*>(tcb - 0x90);\n" .
	"\t\t\t\t\tBc5CrashLog(\"thread trap: host id %d guest id %d \\\"%s\\\": gen %d index %d jobid %u%s ptr-0x98 %016\" PRIx64 \"%s\\n\", tid, gid, nm,\n" .
	"\t\t\t\t\t            *reinterpret_cast<const int32_t*>(tcb - 0x108), *reinterpret_cast<const int32_t*>(tcb - 0x104), jobid,\n" .
	"\t\t\t\t\t            jobid == owner_id ? \" (owner)\" : \"\", *reinterpret_cast<const uint64_t*>(tcb - 0x98),\n" .
	"\t\t\t\t\t            tid == Common::Thread::GetThreadIdUnique() ? \" <- faulting\" : \"\");\n",

	# (2b) the job system after the per-thread lines
	"\t\t\t\t\t            tid == Common::Thread::GetThreadIdUnique() ? \" <- faulting\" : \"\");\n\t\t\t\t}\n",
	"\t\t\t\t\t            tid == Common::Thread::GetThreadIdUnique() ? \" <- faulting\" : \"\");\n\t\t\t\t}\n" .
	"\t\t\t\t// trap v3: the job system at the fault (F448/F449)\n" .
	"\t\t\t\t{\n" .
	"\t\t\t\t\tstruct Ctx { uint64_t base; uint32_t owner_mask; };\n" .
	"\t\t\t\t\tCtx c {prog->base_vaddr, 0};\n" .
	"\t\t\t\t\tbc5_guest_read(c.base + 0xb064038, &c.owner_mask, 4);\n" .
	"\t\t\t\t\tconst Bc5JobSys s = bc5_jobsys(c.base,\n" .
	"\t\t\t\t\t    [](const Bc5Job& j, void* p) {\n" .
	"\t\t\t\t\t\t    const auto* cc = static_cast<const Ctx*>(p);\n" .
	"\t\t\t\t\t\t    if (j.i >= 64) return;\n" .
	"\t\t\t\t\t\t    if (!j.valid) {\n" .
	"\t\t\t\t\t\t\t    Bc5CrashLog(\"thread trap:   entry %d job %d: handle %016\" PRIx64 \" (not decodable)\\n\", j.k, j.i, j.handle);\n" .
	"\t\t\t\t\t\t\t    return;\n" .
	"\t\t\t\t\t\t    }\n" .
	"\t\t\t\t\t\t    Bc5CrashLog(\"thread trap:   entry %d job %d: handle %016\" PRIx64 \" obj %016\" PRIx64 \": active %d started %d done %d total %d class %08\" PRIx32 \"%s flags %08\" PRIx32 \" fn +0x%\" PRIx64 \"%s\\n\",\n" .
	"\t\t\t\t\t\t                j.k, j.i, j.handle, j.obj, j.active, j.started, j.done, j.total, j.cls, (j.cls & cc->owner_mask) != 0 ? \" (owner-class)\" : \"\", j.flags,\n" .
	"\t\t\t\t\t\t                j.fn >= cc->base ? j.fn - cc->base : j.fn, j.fn == cc->base + 0x4661e50 ? \" <- the crash job's function\" : \"\");\n" .
	"\t\t\t\t\t    },\n" .
	"\t\t\t\t\t    &c);\n" .
	"\t\t\t\t\tBc5CrashLog(\"thread trap: jobsys workers %u special %u owner-mask %08\" PRIx32 \" special-mask %08\" PRIx32 \" n1 %u n2 %u owner id %u (ids issued %u) override arena %016\" PRIx64 \"\\n\",\n" .
	"\t\t\t\t\t            s.n_workers, s.special, s.owner_mask, s.special_mask, s.n1, s.n2, s.owner_id, s.ids, s.over);\n" .
	"\t\t\t\t\tfor (int k = 0; k < 3; k++) {\n" .
	"\t\t\t\t\t\tconst auto& e = s.e[k];\n" .
	"\t\t\t\t\t\tBc5CrashLog(\"thread trap: entry %d%s: live %d/%d gen %u pending %d (owner-class %d, runnable %d, null %d, bad %d) array %016\" PRIx64 \" list %016\" PRIx64 \"\\n\", k,\n" .
	"\t\t\t\t\t\t            e.ok ? \"\" : \" (unreadable)\", e.live, e.cap, e.gen, e.pending, e.owner_cls, e.runnable, e.nulls, e.bad, e.array, e.list);\n" .
	"\t\t\t\t\t}\n" .
	"\t\t\t\t}\n",
);

my $agc = "$root/src/libs/bc5LleAgc.cpp";
patch($agc,
	"#include <sys/mman.h>\n",
	"#include <sys/mman.h>\n#include <sys/uio.h> // BC5 (experiment 0358, trap v3)\n",

	"static void frame_profile_flip(double drain_ms) {\n",
	$reader .
	"// Once a second from the game thread's flip: the job system's entries (F449: the owner thread runs pending\n" .
	"// owner-class jobs itself while it waits; does that backlog grow over the fight, or appear at the crash frame?).\n" .
	"// The cost outside a sampled frame is one timing_now() and a compare; a sample is 12 reads through the kernel\n" .
	"// plus one per pending job, timed and printed.\n" .
	"static void bc5_pool_sample() {\n" .
	"\tstatic double   t_last   = 0;\n" .
	"\tstatic uint64_t cost_max = 0;\n" .
	"\tconst double    now      = timing_now();\n" .
	"\tif (now - t_last < 1.0) return;\n" .
	"\tt_last = now;\n" .
	"\tconst auto       c0 = std::chrono::steady_clock::now();\n" .
	"\tconst Bc5JobSys  s  = bc5_jobsys(0x900000000ull, nullptr, nullptr);\n" .
	"\tconst auto       ns = static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now() - c0).count());\n" .
	"\tif (ns > cost_max) cost_max = ns;\n" .
	"\tjournal(\"pool sample: t %.3f s, live %d/%d %d/%d %d/%d, pending %d %d %d, owner-class %d %d %d, runnable %d %d %d, bad %d %d %d; owner id %u override arena %016\" PRIx64 \"; cost %\" PRIu64 \" ns (max %\" PRIu64 \")\\n\",\n" .
	"\t        now, s.e[0].live, s.e[0].cap, s.e[1].live, s.e[1].cap, s.e[2].live, s.e[2].cap, s.e[0].pending, s.e[1].pending, s.e[2].pending,\n" .
	"\t        s.e[0].owner_cls, s.e[1].owner_cls, s.e[2].owner_cls, s.e[0].runnable, s.e[1].runnable, s.e[2].runnable, s.e[0].bad + s.e[0].nulls,\n" .
	"\t        s.e[1].bad + s.e[1].nulls, s.e[2].bad + s.e[2].nulls, s.owner_id, s.over, ns, cost_max);\n" .
	"}\n\n" .
	"static void frame_profile_flip(double drain_ms) {\n" .
	"\tbc5_pool_sample(); // BC5 (experiment 0358, trap v3): before the profile switch, every flip\n",
);
print "patch0358v3.pl: $marks edits\n";
