#!/usr/bin/perl
# BC5 experiment 0358, trap v4 + the fix candidate: applied AFTER patch0358.pl and patch0358v3.pl to the same PRIVATE
# copies (the shared tree is only read). Units: kernel/semaphore.cpp (new in v4), kernel/pthread.cpp,
# loader/runtimeLinker.cpp, libs/bc5LleAgc.cpp.
#   kernel/semaphore.cpp:
#     - a ring of the last 512 semaphore events (steady-clock us, kind, semaphore name, thread host id, count, and for
#       a satisfied wait the latency from the signal that made it ready to the waiter's return), filled by Signal and
#       Wait; a per-thread "inside a wait on <name> since <us>" table; both read by the crash print.
#     - the fix candidate, BC5_0358_FIX=1 (F451: Signal marks the ready waiters and then broadcasts to every waiter of
#       the semaphore, so five idle Hi workers all wake, contend for the mutex, four sleep again): under the switch
#       each waiter waits on its own condition variable (one per thread, thread_local) and Signal/Cancel/Delete wake
#       only the waiters they mark ready - what the console's kernel does when it hands the count to one thread.
#   kernel/pthread.cpp: bc5_pthread_each() also passes the OS thread id (for /proc).
#   loader/runtimeLinker.cpp: after v3's job lines, the ring (newest 96) and every guest thread's /proc state
#     (state letter, CPU seconds, context switches) with its semaphore wait state.
#   libs/bc5LleAgc.cpp: the sampler adds the five Hi workers' CPU seconds.
# usage: patch0358v4.pl <private src root>
use strict;
use warnings;
my ($root) = @ARGV;
die "usage: patch0358v4.pl <src root>\n" unless defined $root;
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

# /proc/self/task/<tid>/stat and /status reader, a copy in the two units that use it.
my $procread =
	"// BC5 (experiment 0358, trap v4): a thread's /proc state: state letter, CPU seconds (user+system, user), the\n" .
	"// voluntary and involuntary context switches. Reads two small files; false when the thread is gone.\n" .
	"struct Bc5ProcState {\n" .
	"\tchar     state = '?';\n" .
	"\tdouble   cpu_s = 0, user_s = 0;\n" .
	"\tuint64_t vol = 0, invol = 0;\n" .
	"};\n" .
	"static bool bc5_proc_state(uint64_t os_tid, Bc5ProcState* out) {\n" .
	"\tchar path[64];\n" .
	"\tchar buf[1024];\n" .
	"\tstd::snprintf(path, sizeof(path), \"/proc/self/task/%\" PRIu64 \"/stat\", os_tid);\n" .
	"\tint fd = open(path, O_RDONLY | O_CLOEXEC);\n" .
	"\tif (fd < 0) return false;\n" .
	"\tssize_t n = read(fd, buf, sizeof(buf) - 1);\n" .
	"\tclose(fd);\n" .
	"\tif (n <= 0) return false;\n" .
	"\tbuf[n] = 0;\n" .
	"\tconst char* p = std::strrchr(buf, ')');\n" .
	"\tif (p == nullptr || p[1] != ' ') return false;\n" .
	"\tout->state = p[2];\n" .
	"\t// fields after the state: ppid(0) pgrp session tty tpgid flags minflt cminflt majflt cmajflt utime(10) stime(11); exp 0360 found the index slip (f[11]/f[12] printed kernel time only)\n" .
	"\tunsigned long long f[13] {};\n" .
	"\tconst char* q = p + 3;\n" .
	"\tfor (int k = 0; k < 13; k++) {\n" .
	"\t\twhile (*q == ' ') q++;\n" .
	"\t\tchar* e = nullptr;\n" .
	"\t\tf[k] = std::strtoull(q, &e, 10);\n" .
	"\t\tif (e == q) break;\n" .
	"\t\tq = e;\n" .
	"\t}\n" .
	"\tconst double hz = static_cast<double>(sysconf(_SC_CLK_TCK));\n" .
	"\tout->user_s = static_cast<double>(f[10]) / hz;\n" .
	"\tout->cpu_s  = static_cast<double>(f[10] + f[11]) / hz;\n" .
	"\tstd::snprintf(path, sizeof(path), \"/proc/self/task/%\" PRIu64 \"/status\", os_tid);\n" .
	"\tfd = open(path, O_RDONLY | O_CLOEXEC);\n" .
	"\tif (fd >= 0) {\n" .
	"\t\tchar sbuf[4096];\n" .
	"\t\tn = read(fd, sbuf, sizeof(sbuf) - 1);\n" .
	"\t\tclose(fd);\n" .
	"\t\tif (n > 0) {\n" .
	"\t\t\tsbuf[n] = 0;\n" .
	"\t\t\tif (const char* v = std::strstr(sbuf, \"voluntary_ctxt_switches:\")) out->vol = std::strtoull(v + 24, nullptr, 10);\n" .
	"\t\t\tif (const char* v = std::strstr(sbuf, \"nonvoluntary_ctxt_switches:\")) out->invol = std::strtoull(v + 27, nullptr, 10);\n" .
	"\t\t}\n" .
	"\t}\n" .
	"\treturn true;\n" .
	"}\n";

# ---- kernel/semaphore.cpp
my $sem = "$root/src/kernel/semaphore.cpp";
patch($sem,
	"#include <algorithm>\n#include <atomic>\n",
	"#include <algorithm>\n#include <atomic>\n#include <chrono>  // BC5 (experiment 0358, trap v4)\n#include <cinttypes>\n#include <cstdio>\n#include <cstring>\n",

	"constexpr uint32_t SIGNAL_APC_POLL_MICROS = 10000;\n\nclass KernelSemaPrivate {\n",
	"constexpr uint32_t SIGNAL_APC_POLL_MICROS = 10000;\n\n" .
	"// BC5 (experiment 0358, trap v4): the semaphore event ring, the per-thread wait table, the fix switch.\n" .
	"struct Bc5SemaEvent {\n" .
	"\tuint64_t t_us   = 0;\n" .
	"\tuint64_t lat_us = 0;\n" .
	"\tint      tid    = 0;\n" .
	"\tint      count  = 0;\n" .
	"\tuint8_t  kind   = 0; // 1 signal, 2 wait-begin, 3 wait-ok, 4 wait-timeout, 5 wait-immediate, 6 wait-other\n" .
	"\tchar     name[24] {};\n" .
	"};\n" .
	"static Bc5SemaEvent           g_bc5_sema_ring[512];\n" .
	"static std::atomic<uint32_t>  g_bc5_sema_ring_n {0};\n" .
	"struct Bc5WaitState {\n" .
	"\tstd::atomic<const char*> name {nullptr};\n" .
	"\tstd::atomic<uint64_t>    since_us {0};\n" .
	"};\n" .
	"static Bc5WaitState g_bc5_wait_state[4096];\n" .
	"static uint64_t     bc5_now_us() {\n" .
	"\tstatic const auto t0 = std::chrono::steady_clock::now();\n" .
	"\treturn static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now() - t0).count());\n" .
	"}\n" .
	"static void bc5_sema_event(uint8_t kind, const std::string& name, int count, uint64_t lat_us) {\n" .
	"\tconst uint32_t i = g_bc5_sema_ring_n.fetch_add(1, std::memory_order_relaxed) & 511u;\n" .
	"\tauto&          e = g_bc5_sema_ring[i];\n" .
	"\te.t_us           = bc5_now_us();\n" .
	"\te.lat_us         = lat_us;\n" .
	"\te.tid            = Common::Thread::GetThreadIdUnique();\n" .
	"\te.count          = count;\n" .
	"\te.kind           = kind;\n" .
	"\tstd::snprintf(e.name, sizeof(e.name), \"%s\", name.c_str());\n" .
	"}\n" .
	"static bool bc5_fix_on() {\n" .
	"\tstatic const bool on = [] {\n" .
	"\t\tconst char* e = std::getenv(\"BC5_0358_FIX\");\n" .
	"\t\treturn e != nullptr && std::strcmp(e, \"0\") != 0;\n" .
	"\t}();\n" .
	"\treturn on;\n" .
	"}\n" .
	"extern \"C\" void bc5_sema_ring_dump(void (*fn)(const char* line, void* ctx), void* ctx) {\n" .
	"\tconst uint32_t     n    = g_bc5_sema_ring_n.load();\n" .
	"\tconst uint32_t     take = n < 512u ? n : 512u;\n" .
	"\tconst uint64_t     now  = bc5_now_us();\n" .
	"\tstatic const char* kinds[] = {\"?\", \"signal\", \"wait-begin\", \"wait-ok\", \"wait-timeout\", \"wait-immediate\", \"wait-other\"};\n" .
	"\tchar               line[256];\n" .
	"\tstd::snprintf(line, sizeof(line), \"semaphore ring: %u events in all, fix %s, now %\" PRIu64 \" us; the newest first\", n, bc5_fix_on() ? \"on\" : \"off\", now);\n" .
	"\tfn(line, ctx);\n" .
	"\tfor (uint32_t k = 0; k < take && k < 96u; k++) {\n" .
	"\t\tconst auto& e = g_bc5_sema_ring[(n - 1u - k) & 511u];\n" .
	"\t\tstd::snprintf(line, sizeof(line), \"  -%9.3f ms %-14s host id %3d %-23s count %d lat %\" PRIu64 \" us\", static_cast<double>(now - e.t_us) / 1e3,\n" .
	"\t\t              kinds[e.kind < 7 ? e.kind : 0], e.tid, e.name, e.count, e.lat_us);\n" .
	"\t\tfn(line, ctx);\n" .
	"\t}\n" .
	"}\n" .
	"extern \"C\" const char* bc5_sema_wait_state(int uid, uint64_t* since_us) {\n" .
	"\tif (uid < 0 || uid >= 4096) return nullptr;\n" .
	"\t*since_us = g_bc5_wait_state[uid].since_us.load();\n" .
	"\treturn g_bc5_wait_state[uid].name.load();\n" .
	"}\n" .
	"extern \"C\" uint64_t bc5_sema_now_us() {\n" .
	"\treturn bc5_now_us();\n" .
	"}\n\n" .
	"class KernelSemaPrivate {\n",

	"\t\tbool   ready      = false;\n\t};\n",
	"\t\tbool   ready      = false;\n" .
	"\t\tuint64_t        t_ready_us = 0;       // BC5 (experiment 0358, trap v4): when Signal/Cancel marked it ready\n" .
	"\t\tCommon::CondVar* cv        = nullptr; // BC5 (experiment 0358, the fix): the waiter's own condition variable\n" .
	"\t};\n",

	# the destructor's and Cancel's wake-ups reach a waiter on its own condition variable too
	"\t\t\twaiter->result = Result::Deleted;\n\t\t\twaiter->ready  = true;\n",
	"\t\t\twaiter->result = Result::Deleted;\n\t\t\twaiter->ready  = true;\n\t\t\twaiter->t_ready_us = bc5_now_us();\n\t\t\tif (waiter->cv != nullptr) waiter->cv->Signal(); // BC5 (experiment 0358, the fix)\n",

	"\t\t\twaiter->result = Result::Canceled;\n\t\t\twaiter->ready  = true;\n",
	"\t\t\twaiter->result = Result::Canceled;\n\t\t\twaiter->ready  = true;\n\t\t\twaiter->t_ready_us = bc5_now_us();\n\t\t\tif (waiter->cv != nullptr) waiter->cv->Signal(); // BC5 (experiment 0358, the fix)\n",

	# Signal: the event, and under the fix no broadcast (WakeWaiters woke the ready ones)
	"\tm_count += signal_count;\n\n\tWakeWaiters();\n\n\tm_cond_var.SignalAll();\n\n\treturn Result::Ok;\n",
	"\tm_count += signal_count;\n\n\tWakeWaiters();\n\n" .
	"\tbc5_sema_event(1, m_name, signal_count, 0); // BC5 (experiment 0358, trap v4)\n" .
	"\tif (!bc5_fix_on()) m_cond_var.SignalAll(); // BC5 (experiment 0358, the fix): the ready waiters were woken one by one\n\n" .
	"\treturn Result::Ok;\n",

	# WakeWaiters: the ready time and the targeted wake
	"\t\tif (!waiter->ready && waiter->need_count <= m_count) {\n\t\t\tm_count -= waiter->need_count;\n\t\t\twaiter->result = Result::Ok;\n\t\t\twaiter->ready  = true;\n\t\t}\n",
	"\t\tif (!waiter->ready && waiter->need_count <= m_count) {\n\t\t\tm_count -= waiter->need_count;\n\t\t\twaiter->result = Result::Ok;\n\t\t\twaiter->ready  = true;\n" .
	"\t\t\twaiter->t_ready_us = bc5_now_us();                // BC5 (experiment 0358, trap v4)\n" .
	"\t\t\tif (waiter->cv != nullptr) waiter->cv->Signal(); // BC5 (experiment 0358, the fix): wake this one only\n" .
	"\t\t}\n",

	# Wait: the immediate path's event
	"\tif (m_count >= need_count) {\n\t\tm_count -= need_count;\n\t\tif (ptr_micros != nullptr) {\n\t\t\t*ptr_micros = micros;\n\t\t}\n\t\treturn Result::Ok;\n\t}\n",
	"\tif (m_count >= need_count) {\n\t\tm_count -= need_count;\n\t\tif (ptr_micros != nullptr) {\n\t\t\t*ptr_micros = micros;\n\t\t}\n" .
	"\t\tbc5_sema_event(5, m_name, need_count, 0); // BC5 (experiment 0358, trap v4)\n" .
	"\t\treturn Result::Ok;\n\t}\n",

	# Wait: the waiter's own condition variable, the begin event and the wait table
	"\tWaitingThread waiter {};\n\twaiter.id         = id;\n",
	"\tWaitingThread waiter {};\n" .
	"\tstatic thread_local Common::CondVar t_bc5_cv; // BC5 (experiment 0358, the fix): a thread waits on one semaphore at a time\n" .
	"\tif (bc5_fix_on()) waiter.cv = &t_bc5_cv;\n" .
	"\tbc5_sema_event(2, m_name, need_count, 0); // BC5 (experiment 0358, trap v4)\n" .
	"\tif (id >= 0 && id < 4096) {\n" .
	"\t\tg_bc5_wait_state[id].name.store(m_name.c_str());\n" .
	"\t\tg_bc5_wait_state[id].since_us.store(bc5_now_us());\n" .
	"\t}\n" .
	"\twaiter.id         = id;\n",

	"\t\t\tRemoveWaiter(&waiter);\n\t\t\t*ptr_micros = 0;\n\t\t\treturn Result::TimedOut;\n",
	"\t\t\tRemoveWaiter(&waiter);\n\t\t\t*ptr_micros = 0;\n" .
	"\t\t\tbc5_sema_event(4, m_name, need_count, 0); // BC5 (experiment 0358, trap v4)\n" .
	"\t\t\tif (id >= 0 && id < 4096) g_bc5_wait_state[id].name.store(nullptr);\n" .
	"\t\t\treturn Result::TimedOut;\n",

	"\t\tif (infinitely) {\n\t\t\tm_cond_var.WaitFor(&m_mutex, SIGNAL_APC_POLL_MICROS);\n\t\t} else {\n\t\t\tm_cond_var.WaitFor(&m_mutex, micros - elapsed);\n\t\t}\n",
	"\t\tCommon::CondVar& cv = waiter.cv != nullptr ? *waiter.cv : m_cond_var; // BC5 (experiment 0358, the fix)\n" .
	"\t\tif (infinitely) {\n\t\t\tcv.WaitFor(&m_mutex, SIGNAL_APC_POLL_MICROS);\n\t\t} else {\n\t\t\tcv.WaitFor(&m_mutex, micros - elapsed);\n\t\t}\n",

	"\tRemoveWaiter(&waiter);\n\n\tif (ptr_micros != nullptr) {\n\t\t*ptr_micros = (elapsed >= micros ? 0 : micros - elapsed);\n",
	"\tRemoveWaiter(&waiter);\n" .
	"\t{ // BC5 (experiment 0358, trap v4): the wait's end, with the latency since the signal that made it ready\n" .
	"\t\tconst uint64_t now = bc5_now_us();\n" .
	"\t\tbc5_sema_event(waiter.result == Result::Ok ? 3 : 6, m_name, need_count, waiter.t_ready_us != 0 && now > waiter.t_ready_us ? now - waiter.t_ready_us : 0);\n" .
	"\t\tif (id >= 0 && id < 4096) g_bc5_wait_state[id].name.store(nullptr);\n" .
	"\t}\n\n" .
	"\tif (ptr_micros != nullptr) {\n\t\t*ptr_micros = (elapsed >= micros ? 0 : micros - elapsed);\n",
);

# ---- kernel/pthread.cpp: the OS thread id through bc5_pthread_each (v1's text)
my $pt = "$root/src/kernel/pthread.cpp";
patch($pt,
	"extern \"C\" void bc5_pthread_each(void (*fn)(int unique_id, int guest_id, const char* name, void* ctx), void* ctx) {\n" .
	"\tif (g_pthread_context == nullptr || g_pthread_context->GetPthreadPool() == nullptr) return;\n" .
	"\tstruct Ctx {\n" .
	"\t\tvoid (*fn)(int, int, const char*, void*);\n",
	"extern \"C\" void bc5_pthread_each(void (*fn)(int unique_id, int guest_id, const char* name, uint64_t os_tid, void* ctx), void* ctx) {\n" .
	"\tif (g_pthread_context == nullptr || g_pthread_context->GetPthreadPool() == nullptr) return;\n" .
	"\tstruct Ctx {\n" .
	"\t\tvoid (*fn)(int, int, const char*, uint64_t, void*);\n",

	"\t\t    cc->fn(t->unique_id, t->guest.thread_id, t->name.c_str(), cc->ctx);\n",
	"\t\t    cc->fn(t->unique_id, t->guest.thread_id, t->name.c_str(), t->host_thread_id, cc->ctx);\n",
);

# ---- loader/runtimeLinker.cpp
my $rtl = "$root/src/loader/runtimeLinker.cpp";
patch($rtl,
	"#include <sys/uio.h> // BC5 (experiment 0358, trap v3)\n#include <unistd.h>\n",
	"#include <sys/uio.h> // BC5 (experiment 0358, trap v3)\n#include <unistd.h>\n#include <fcntl.h> // BC5 (experiment 0358, trap v4)\n",

	"extern \"C\" void bc5_pthread_each(void (*fn)(int unique_id, int guest_id, const char* name, void* ctx), void* ctx); // ditto\n",
	"extern \"C\" void bc5_pthread_each(void (*fn)(int unique_id, int guest_id, const char* name, uint64_t os_tid, void* ctx), void* ctx); // ditto (v4: + the OS thread id)\n" .
	"extern \"C\" void        bc5_sema_ring_dump(void (*fn)(const char* line, void* ctx), void* ctx); // kernel/semaphore.cpp, BC5 (experiment 0358, trap v4)\n" .
	"extern \"C\" const char* bc5_sema_wait_state(int uid, uint64_t* since_us);                     // ditto\n" .
	"extern \"C\" uint64_t    bc5_sema_now_us();                                                   // ditto\n",

	# the reader block of v3 gains the /proc reader
	"// The title's job system (F448/F449): three worker entries, their pending jobs, the owner thread's globals.\n",
	$procread . "// The title's job system (F448/F449): three worker entries, their pending jobs, the owner thread's globals.\n",

	"\t\t\t\tstruct Name { int uid; int gid; char name[32]; };\n",
	"\t\t\t\tstruct Name { int uid; int gid; char name[32]; uint64_t os_tid; };\n",

	"\t\t\t\t    [](int uid, int gid, const char* name, void*) {\n" .
	"\t\t\t\t\t    if (nnames < 512) {\n" .
	"\t\t\t\t\t\t    names[nnames].uid = uid;\n" .
	"\t\t\t\t\t\t    names[nnames].gid = gid;\n",
	"\t\t\t\t    [](int uid, int gid, const char* name, uint64_t os_tid, void*) {\n" .
	"\t\t\t\t\t    if (nnames < 512) {\n" .
	"\t\t\t\t\t\t    names[nnames].uid    = uid;\n" .
	"\t\t\t\t\t\t    names[nnames].gid    = gid;\n" .
	"\t\t\t\t\t\t    names[nnames].os_tid = os_tid;\n",

	# after v3's job-system block: the threads' /proc states and the semaphore ring
	"\t\t\t\t\t\tBc5CrashLog(\"thread trap: entry %d%s: live %d/%d gen %u pending %d (owner-class %d, runnable %d, null %d, bad %d) array %016\" PRIx64 \" list %016\" PRIx64 \"\\n\", k,\n" .
	"\t\t\t\t\t\t            e.ok ? \"\" : \" (unreadable)\", e.live, e.cap, e.gen, e.pending, e.owner_cls, e.runnable, e.nulls, e.bad, e.array, e.list);\n" .
	"\t\t\t\t\t}\n" .
	"\t\t\t\t}\n",
	"\t\t\t\t\t\tBc5CrashLog(\"thread trap: entry %d%s: live %d/%d gen %u pending %d (owner-class %d, runnable %d, null %d, bad %d) array %016\" PRIx64 \" list %016\" PRIx64 \"\\n\", k,\n" .
	"\t\t\t\t\t\t            e.ok ? \"\" : \" (unreadable)\", e.live, e.cap, e.gen, e.pending, e.owner_cls, e.runnable, e.nulls, e.bad, e.array, e.list);\n" .
	"\t\t\t\t\t}\n" .
	"\t\t\t\t}\n" .
	"\t\t\t\t// trap v4: every guest thread's /proc state and its semaphore wait, then the semaphore ring\n" .
	"\t\t\t\t{\n" .
	"\t\t\t\t\tconst uint64_t now_us = bc5_sema_now_us();\n" .
	"\t\t\t\t\tfor (int k = 0; k < nnames; k++) {\n" .
	"\t\t\t\t\t\tBc5ProcState ps;\n" .
	"\t\t\t\t\t\tconst bool   ok    = bc5_proc_state(names[k].os_tid, &ps);\n" .
	"\t\t\t\t\t\tuint64_t     since = 0;\n" .
	"\t\t\t\t\t\tconst char*  w     = bc5_sema_wait_state(names[k].uid, &since);\n" .
	"\t\t\t\t\t\tBc5CrashLog(\"thread trap: proc \\\"%s\\\" host id %d os %\" PRIu64 \": state %c cpu %.3f s (user %.3f) switches %\" PRIu64 \" voluntary %\" PRIu64 \" involuntary%s%s%s (for %.3f ms)\\n\",\n" .
	"\t\t\t\t\t\t            names[k].name, names[k].uid, names[k].os_tid, ok ? ps.state : '?', ps.cpu_s, ps.user_s, ps.vol, ps.invol,\n" .
	"\t\t\t\t\t\t            w != nullptr ? \", in a wait on \\\"\" : \"\", w != nullptr ? w : \"\", w != nullptr ? \"\\\"\" : \"\",\n" .
	"\t\t\t\t\t\t            w != nullptr && now_us > since ? static_cast<double>(now_us - since) / 1e3 : 0.0);\n" .
	"\t\t\t\t\t}\n" .
	"\t\t\t\t\tbc5_sema_ring_dump([](const char* line, void*) { Bc5CrashLog(\"thread trap: %s\\n\", line); }, nullptr);\n" .
	"\t\t\t\t}\n",
);

# ---- libs/bc5LleAgc.cpp: the Hi workers' CPU in the sampler
my $agc = "$root/src/libs/bc5LleAgc.cpp";
patch($agc,
	"#include <sys/mman.h>\n#include <sys/uio.h> // BC5 (experiment 0358, trap v3)\n",
	"#include <sys/mman.h>\n#include <sys/uio.h> // BC5 (experiment 0358, trap v3)\n" .
	"extern \"C\" void bc5_pthread_each(void (*fn)(int unique_id, int guest_id, const char* name, uint64_t os_tid, void* ctx), void* ctx); // kernel/pthread.cpp, BC5 (experiment 0358, trap v4)\n",

	"// The title's job system (F448/F449): three worker entries, their pending jobs, the owner thread's globals.\n",
	$procread . "// The title's job system (F448/F449): three worker entries, their pending jobs, the owner thread's globals.\n",

	"\tif (ns > cost_max) cost_max = ns;\n" .
	"\tjournal(\"pool sample: t %.3f s, live %d/%d %d/%d %d/%d, pending %d %d %d, owner-class %d %d %d, runnable %d %d %d, bad %d %d %d; owner id %u override arena %016\" PRIx64 \"; cost %\" PRIu64 \" ns (max %\" PRIu64 \")\\n\",\n" .
	"\t        now, s.e[0].live, s.e[0].cap, s.e[1].live, s.e[1].cap, s.e[2].live, s.e[2].cap, s.e[0].pending, s.e[1].pending, s.e[2].pending,\n" .
	"\t        s.e[0].owner_cls, s.e[1].owner_cls, s.e[2].owner_cls, s.e[0].runnable, s.e[1].runnable, s.e[2].runnable, s.e[0].bad + s.e[0].nulls,\n" .
	"\t        s.e[1].bad + s.e[1].nulls, s.e[2].bad + s.e[2].nulls, s.owner_id, s.over, ns, cost_max);\n",
	"\t// trap v4: the five Hi workers' CPU seconds (their OS thread ids looked up once)\n" .
	"\tstatic uint64_t hi_tid[5] {};\n" .
	"\tstatic int      hi_n = 0;\n" .
	"\tif (hi_n == 0) {\n" .
	"\t\tbc5_pthread_each(\n" .
	"\t\t    [](int, int, const char* name, uint64_t os_tid, void*) {\n" .
	"\t\t\t    if (name != nullptr && std::strncmp(name, \"Job Hi\", 6) == 0 && hi_n < 5) hi_tid[hi_n++] = os_tid;\n" .
	"\t\t    },\n" .
	"\t\t    nullptr);\n" .
	"\t}\n" .
	"\tdouble hi_cpu[5] {};\n" .
	"\tchar   hi_state[6] = \"-----\";\n" .
	"\tfor (int k = 0; k < hi_n; k++) {\n" .
	"\t\tBc5ProcState ps;\n" .
	"\t\tif (bc5_proc_state(hi_tid[k], &ps)) {\n" .
	"\t\t\thi_cpu[k]   = ps.cpu_s;\n" .
	"\t\t\thi_state[k] = ps.state;\n" .
	"\t\t}\n" .
	"\t}\n" .
	"\tconst auto ns2 = static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now() - c0).count());\n" .
	"\tif (ns2 > cost_max) cost_max = ns2;\n" .
	"\tjournal(\"pool sample: t %.3f s, live %d/%d %d/%d %d/%d, pending %d %d %d, owner-class %d %d %d, runnable %d %d %d, bad %d %d %d; owner id %u override arena %016\" PRIx64 \"; hi cpu %.2f %.2f %.2f %.2f %.2f s states %s; cost %\" PRIu64 \" ns (max %\" PRIu64 \")\\n\",\n" .
	"\t        now, s.e[0].live, s.e[0].cap, s.e[1].live, s.e[1].cap, s.e[2].live, s.e[2].cap, s.e[0].pending, s.e[1].pending, s.e[2].pending,\n" .
	"\t        s.e[0].owner_cls, s.e[1].owner_cls, s.e[2].owner_cls, s.e[0].runnable, s.e[1].runnable, s.e[2].runnable, s.e[0].bad + s.e[0].nulls,\n" .
	"\t        s.e[1].bad + s.e[1].nulls, s.e[2].bad + s.e[2].nulls, s.owner_id, s.over, hi_cpu[0], hi_cpu[1], hi_cpu[2], hi_cpu[3], hi_cpu[4], hi_state, ns2, cost_max);\n",
);
print "patch0358v4.pl: $marks edits\n";
