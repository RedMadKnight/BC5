#!/usr/bin/perl
# BC5 experiment 0358: the thread trap in a PRIVATE copy of two host units (the shared tree is only read).
#   kernel/pthread.cpp: bc5_pthread_self_line() names the current guest thread (pthread name, guest id, host unique
#                       id); bc5_pthread_each() walks the pool's threads for the crash print.
#   loader/runtimeLinker.cpp: after a guest access violation's stack trace, print the faulting thread, the main
#                       program's TLS layout and image values at tcb-0x110..-0x100, and every guest thread's slots at
#                       tcb-0x108 / tcb-0x104 (the title's worker generation and index) and tcb-0x98, with its name.
# usage: patch0358.pl <private src root>   (holds src/kernel/pthread.cpp and src/loader/runtimeLinker.cpp)
use strict;
use warnings;
my ($root) = @ARGV;
die "usage: patch0358.pl <src root>\n" unless defined $root;
my $marks = 0;
sub patch {
	my ($file, @pairs) = @_;
	open(my $h, "<", $file) or die "$file: $!\n";
	my $s = do { local $/; <$h> };
	close $h;
	my $crlf = ($s =~ /\r\n/) ? 1 : 0; # kernel/pthread.cpp is CRLF in the tree (exp 0318's note); the anchors are written LF
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

my $pt = "$root/src/kernel/pthread.cpp";
patch($pt,
	"\tvoid FreeDetachedThreads();\n\n",
	"\tvoid FreeDetachedThreads();\n\n" .
	"\t// BC5 (experiment 0358): the crash print walks the threads; no lock (a crash path).\n" .
	"\tvoid Bc5Each(void (*fn)(Pthread, void*), void* ctx) {\n" .
	"\t\tfor (auto& t: m_threads) {\n" .
	"\t\t\tif (t != nullptr && !t->free) fn(t, ctx);\n" .
	"\t\t}\n" .
	"\t}\n\n",

	"static Common::Mutex g_guest_stack_mutex;\n",
	"static Common::Mutex g_guest_stack_mutex;\n\n" .
	"// BC5 (experiment 0358): the faulting thread as the title knows it, for runtimeLinker.cpp's crash print.\n" .
	"extern \"C\" void bc5_pthread_self_line(char* buf, size_t n) {\n" .
	"\tif (g_pthread_self == nullptr) {\n" .
	"\t\tstd::snprintf(buf, n, \"not a guest pthread (host unique id %d)\", Common::Thread::GetThreadIdUnique());\n" .
	"\t\treturn;\n" .
	"\t}\n" .
	"\tstd::snprintf(buf, n, \"pthread \\\"%s\\\" guest id %d, host unique id %d, os thread %\" PRIu64, g_pthread_self->name.c_str(),\n" .
	"\t              g_pthread_self->guest.thread_id, g_pthread_self->unique_id, g_pthread_self->host_thread_id);\n" .
	"}\n" .
	"// Every live guest thread: (host unique id, guest id, name) through fn.\n" .
	"extern \"C\" void bc5_pthread_each(void (*fn)(int unique_id, int guest_id, const char* name, void* ctx), void* ctx) {\n" .
	"\tif (g_pthread_context == nullptr || g_pthread_context->GetPthreadPool() == nullptr) return;\n" .
	"\tstruct Ctx {\n" .
	"\t\tvoid (*fn)(int, int, const char*, void*);\n" .
	"\t\tvoid* ctx;\n" .
	"\t} c {fn, ctx};\n" .
	"\tg_pthread_context->GetPthreadPool()->Bc5Each(\n" .
	"\t    [](Pthread t, void* p) {\n" .
	"\t\t    auto* cc = static_cast<Ctx*>(p);\n" .
	"\t\t    cc->fn(t->unique_id, t->guest.thread_id, t->name.c_str(), cc->ctx);\n" .
	"\t    },\n" .
	"\t    &c);\n" .
	"}\n",
);

my $rtl = "$root/src/loader/runtimeLinker.cpp";
patch($rtl,
	"\t\tauto dump_guest_qwords = [](const char* name, uint64_t addr) {\n",
	"\t\t// BC5 (experiment 0358): the thread trap. Which guest thread faulted, and the title's per-thread\n" .
	"\t\t// worker slots (tcb-0x108 generation, tcb-0x104 index, tcb-0x98 a pointer) of every guest thread's\n" .
	"\t\t// thread-local block, with the TLS image's initial values: a null frame arena at eboot.bin+0x3d7eca0 is\n" .
	"\t\t// a worker index of -1 on the faulting thread (F444).\n" .
	"\t\t{\n" .
	"\t\t\tchar who[256] {};\n" .
	"\t\t\tbc5_pthread_self_line(who, sizeof(who));\n" .
	"\t\t\tBc5CrashLog(\"thread trap: faulting %s\\n\", who);\n" .
	"\t\t\tauto* prog = g_tls_main_program;\n" .
	"\t\t\tif (prog != nullptr) {\n" .
	"\t\t\t\tconst uint64_t tcb_off = prog->tls.tcb_offset != 0 ? prog->tls.tcb_offset : prog->tls.image_size;\n" .
	"\t\t\t\tBc5CrashLog(\"thread trap: tls image_size 0x%\" PRIx64 \" init_size 0x%\" PRIx64 \" tcb_offset 0x%\" PRIx64 \" blocks %zu\\n\", prog->tls.image_size,\n" .
	"\t\t\t\t            prog->tls.init_size, tcb_off, prog->tls.tlss.size());\n" .
	"\t\t\t\tconst uint8_t* img = !prog->tls.init_image.empty() ? prog->tls.init_image.data() : reinterpret_cast<const uint8_t*>(prog->tls.image_vaddr);\n" .
	"\t\t\t\tconst uint64_t img_n = !prog->tls.init_image.empty() ? prog->tls.init_image.size() : prog->tls.init_size;\n" .
	"\t\t\t\tif (img != nullptr && tcb_off >= 0x110) {\n" .
	"\t\t\t\t\tBc5CrashLog(\"thread trap: image at tcb-0x110..-0x100:\");\n" .
	"\t\t\t\t\tfor (uint64_t o = tcb_off - 0x110; o < tcb_off - 0x100; o += 4) {\n" .
	"\t\t\t\t\t\tif (o + 4 <= img_n) Bc5CrashLog(\" %08\" PRIx32, *reinterpret_cast<const uint32_t*>(img + o));\n" .
	"\t\t\t\t\t\telse Bc5CrashLog(\" (bss)\");\n" .
	"\t\t\t\t\t}\n" .
	"\t\t\t\t\tBc5CrashLog(\"\\n\");\n" .
	"\t\t\t\t}\n" .
	"\t\t\t\tstruct Name { int uid; int gid; char name[32]; };\n" .
	"\t\t\t\tstatic Name names[512];\n" .
	"\t\t\t\tstatic int  nnames = 0;\n" .
	"\t\t\t\tnnames = 0;\n" .
	"\t\t\t\tbc5_pthread_each(\n" .
	"\t\t\t\t    [](int uid, int gid, const char* name, void*) {\n" .
	"\t\t\t\t\t    if (nnames < 512) {\n" .
	"\t\t\t\t\t\t    names[nnames].uid = uid;\n" .
	"\t\t\t\t\t\t    names[nnames].gid = gid;\n" .
	"\t\t\t\t\t\t    std::snprintf(names[nnames].name, sizeof(names[nnames].name), \"%s\", name != nullptr ? name : \"\");\n" .
	"\t\t\t\t\t\t    nnames++;\n" .
	"\t\t\t\t\t    }\n" .
	"\t\t\t\t    },\n" .
	"\t\t\t\t    nullptr);\n" .
	"\t\t\t\tfor (const auto& [tid, block]: prog->tls.tlss) {\n" .
	"\t\t\t\t\tif (block.ptr == nullptr || tcb_off < 0x110) continue;\n" .
	"\t\t\t\t\tconst uint8_t* tcb = block.ptr + tcb_off;\n" .
	"\t\t\t\t\tconst char*    nm  = \"?\";\n" .
	"\t\t\t\t\tint            gid = -1;\n" .
	"\t\t\t\t\tfor (int k = 0; k < nnames; k++) {\n" .
	"\t\t\t\t\t\tif (names[k].uid == tid) { nm = names[k].name; gid = names[k].gid; break; }\n" .
	"\t\t\t\t\t}\n" .
	"\t\t\t\t\tBc5CrashLog(\"thread trap: host id %d guest id %d \\\"%s\\\": gen %d index %d ptr-0x98 %016\" PRIx64 \"%s\\n\", tid, gid, nm,\n" .
	"\t\t\t\t\t            *reinterpret_cast<const int32_t*>(tcb - 0x108), *reinterpret_cast<const int32_t*>(tcb - 0x104),\n" .
	"\t\t\t\t\t            *reinterpret_cast<const uint64_t*>(tcb - 0x98), tid == Common::Thread::GetThreadIdUnique() ? \" <- faulting\" : \"\");\n" .
	"\t\t\t\t}\n" .
	"\t\t\t}\n" .
	"\t\t}\n" .
	"\t\tauto dump_guest_qwords = [](const char* name, uint64_t addr) {\n",

	"static Program*              g_tls_main_program        = nullptr;\n",
	"static Program*              g_tls_main_program        = nullptr;\n" .
	"extern \"C\" void bc5_pthread_self_line(char* buf, size_t n);                                           // kernel/pthread.cpp, BC5 (experiment 0358)\n" .
	"extern \"C\" void bc5_pthread_each(void (*fn)(int unique_id, int guest_id, const char* name, void* ctx), void* ctx); // ditto\n",
);
print "patch0358.pl: $marks edits\n";
