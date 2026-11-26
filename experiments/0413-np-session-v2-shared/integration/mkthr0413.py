"""Exp 0413 (PRIVATE diagnostic, never for a shared build): at the fault, with BC5_0413_CRASH_WALK=1, dump every thread of
the process. All of it runs AFTER the fault, so the start's timing is untouched:
  - /proc/self/task/<tid>/comm, stat (state, start time) and syscall (number, first argument, e.g. the futex address),
    read before the thread is disturbed;
  - then a signal (SIGRTMAX-3) to each thread, whose handler records RIP, RSP, RBP and the first 12 stack values that lie
    in guest code (0x900000000-0xa00000000): the guest return addresses above whatever host call the thread sits in.
Input: mkwalk0413d.py's output (md5 08f8fd63). usage: mkthr0413.py <in> <out>"""
import hashlib
import sys

s = open(sys.argv[1], "rb").read()
assert hashlib.md5(s).hexdigest().startswith("08f8fd63"), hashlib.md5(s).hexdigest()
A = b"static bool KytyExceptionHandler(const Common::HostException::ExceptionInfo& exception_info) {\n"
assert s.count(A) == 1
HELP = rb"""// ---- exp 0413 private diagnostic: the thread dump at a fault ----
struct Thr0413 {
	int      tid;
	uint64_t rip, rsp, rbp;
	uint64_t guest[12];
	int      nguest;
	volatile int done;
};
static Thr0413          g_thr0413[256];
static std::atomic<int> g_thr0413_n {0};
static void Thr0413Handler(int /*sig*/, siginfo_t* /*si*/, void* ctx) {
	const int me = static_cast<int>(syscall(SYS_gettid));
	const int n  = g_thr0413_n.load();
	for (int i = 0; i < n; i++) {
		Thr0413& t = g_thr0413[i];
		if (t.tid != me) continue;
		const auto* uc = static_cast<const ucontext_t*>(ctx);
		t.rip          = static_cast<uint64_t>(uc->uc_mcontext.gregs[REG_RIP]);
		t.rsp          = static_cast<uint64_t>(uc->uc_mcontext.gregs[REG_RSP]);
		t.rbp          = static_cast<uint64_t>(uc->uc_mcontext.gregs[REG_RBP]);
		t.nguest       = 0;
		for (uint64_t a = t.rsp & ~7ull; a < (t.rsp & ~7ull) + 0x8000 && t.nguest < 12; a += 8) {
			if ((a & 0xfff) == 0 || a == (t.rsp & ~7ull)) {
				if (!IsDumpableRange(a, 8)) break;
			}
			const uint64_t v = *reinterpret_cast<const uint64_t*>(a);
			if (v >= 0x900000000ull && v < 0xa00000000ull) t.guest[t.nguest++] = v;
		}
		t.done = 1;
		return;
	}
}
static void Thr0413ReadFile(const char* path, char* out, size_t cap) {
	out[0]  = 0;
	FILE* f = std::fopen(path, "rb");
	if (f == nullptr) return;
	const size_t got = std::fread(out, 1, cap - 1, f);
	std::fclose(f);
	out[got] = 0;
	for (size_t i = 0; i < got; i++) {
		if (out[i] == '\n') out[i] = ' ';
	}
}
static void Thr0413Dump() {
	const int me = static_cast<int>(syscall(SYS_gettid));
	DIR*      d  = opendir("/proc/self/task");
	if (d == nullptr) return;
	int n = 0;
	char comm[256][32];
	char sysc[256][160];
	char stat[256][64];
	while (dirent* e = readdir(d)) {
		const int tid = std::atoi(e->d_name);
		if (tid <= 0 || n >= 256) continue;
		g_thr0413[n]     = Thr0413 {};
		g_thr0413[n].tid = tid;
		char path[96];
		std::snprintf(path, sizeof(path), "/proc/self/task/%d/comm", tid);
		Thr0413ReadFile(path, comm[n], sizeof(comm[n]));
		std::snprintf(path, sizeof(path), "/proc/self/task/%d/syscall", tid);
		Thr0413ReadFile(path, sysc[n], sizeof(sysc[n]));
		char full[512];
		std::snprintf(path, sizeof(path), "/proc/self/task/%d/stat", tid);
		Thr0413ReadFile(path, full, sizeof(full));
		// state is the field after the closing ')' of comm; the start time is field 22
		const char* rp    = std::strrchr(full, ')');
		char        state = rp != nullptr && rp[1] == ' ' ? rp[2] : '?';
		unsigned long long start = 0;
		if (rp != nullptr) {
			int         field = 2;
			const char* p     = rp + 1;
			while (*p != 0 && field < 22) {
				if (*p == ' ') field++;
				p++;
			}
			start = std::strtoull(p, nullptr, 10);
		}
		std::snprintf(stat[n], sizeof(stat[n]), "state %c start %llu", state, start);
		n++;
	}
	closedir(d);
	g_thr0413_n = n;
	struct sigaction sa {};
	sa.sa_sigaction = Thr0413Handler;
	sa.sa_flags     = SA_SIGINFO | SA_RESTART;
	sigemptyset(&sa.sa_mask);
	const int sig = SIGRTMAX - 3;
	sigaction(sig, &sa, nullptr);
	for (int i = 0; i < n; i++) {
		if (g_thr0413[i].tid != me) syscall(SYS_tgkill, getpid(), g_thr0413[i].tid, sig);
	}
	for (int w = 0; w < 100; w++) {
		bool all = true;
		for (int i = 0; i < n; i++) {
			if (g_thr0413[i].tid != me && g_thr0413[i].done == 0) all = false;
		}
		if (all) break;
		usleep(5000);
	}
	Bc5CrashLog("0413 threads: %d, the faulting thread is %d\n", n, me);
	for (int i = 0; i < n; i++) {
		const Thr0413& t = g_thr0413[i];
		Bc5CrashLog("0413 thread %d%s [%s] %s; syscall: %s\n", t.tid, t.tid == me ? " (FAULT)" : "", comm[i], stat[i], sysc[i]);
		if (t.tid == me) continue;
		Bc5CrashLog("0413 thread %d rip 0x%016" PRIx64 " rsp 0x%016" PRIx64 " rbp 0x%016" PRIx64 " (%s); guest code values on its stack:", t.tid, t.rip, t.rsp,
		            t.rbp, t.done != 0 ? "signalled" : "NO ANSWER");
		for (int k = 0; k < t.nguest; k++) Bc5CrashLog(" 0x%" PRIx64, t.guest[k]);
		Bc5CrashLog("\n");
	}
}

"""
s = s.replace(A, HELP + A)
INC = b'#include "loader/runtimeLinker.h"' + bytes([10])
assert s.count(INC) == 1
MORE = [b"<atomic>", b"<csignal>", b"<cstdio>", b"<cstdlib>", b"<cstring>", b"<dirent.h>", b"<sys/syscall.h>", b"<ucontext.h>"]
s = s.replace(INC, INC + b"".join(b"#include " + m + bytes([10]) for m in MORE))
B = b"\t\t\tif (IsDumpableRange(info->exception_address - 0x60, 0x80)) {\n"
assert s.count(B) == 1
s = s.replace(B, b"\t\t\tThr0413Dump();\n" + B)
open(sys.argv[2], "wb").write(s)
print(hashlib.md5(s).hexdigest())
