
// ---- experiment 0429 candidate R: KYTY_BC5_0429_RR=1, the console's "a lower number wins" for the guest's sleepers -
// On the console a woken job worker takes its CPU at once from any lower-priority thread there (TODO(verify): the
// console's kernel; the title's own priorities and masks, exp 0429's trace). Here a woken worker waited behind threads
// of lower guest priority (h429Z1: 18 % of the job-semaphore wakes took 0.1-2 ms) while the owner's help took the job.
// On: a guest thread (never the runtime's main thread, which runs the owner's help) whose priority is below 700 (TODO(verify): the console's default thread priority) gets SCHED_RR
// from RealtimeKit1 (rtkit, the system bus; no system setting changed: on the box his RLIMIT_RTPRIO is 0, rtkit grants
// RR 1-20 with RLIMIT_RTTIME up to 200 ms, read 2026-11-17) at its first sleep on a guest semaphore, with an RR priority
// in the guest's order (a lower guest number, a higher RR priority). For any title; no title rows.
// Bounds (the box runs with RT throttling off, sched_rt_runtime_us = period):
//   1. RLIMIT_RTTIME on the process: soft 20 ms of RR time without blocking -> SIGXCPU, whose handler drops the running
//      RR thread back to SCHED_OTHER for good (a spinner); hard 200 ms -> the kernel ends the emulator (never the box);
//   2. a watchdog thread every 5 ms: an RR thread that ran 100 ms with no new time slice is dropped for good;
//   3. at most (online CPUs - 2) guest threads hold RR at once, so host threads always have two CPUs.
// A thread dropped by bound 1 or 2 is never promoted again. A thread evicted for a higher priority (the cap) is not a
// spinner: it is promoted again at a later sleep once a place is free (build 12; h429K5: AK::AudioMgr, 450, evicted
// Job Hi 2, 500, for good, and the places the watchdog freed went unused). rtkit's calls: at most 15 per 20 s window
// (rtkit limits its actions per burst, TODO(verify) the box's ActionsPerBurst / ActionsPerBurstSec); a refusal stops
// new promotions until the window turns, except to replace an evicted thread.
// Off: nothing here runs. Normal build: every promotion, drop and refusal is logged (the first 200). Both builds
// (build 11): one count line a minute.
#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
#include <dlfcn.h>
#include <fcntl.h>
#include <sys/resource.h>
namespace bc5_0429r {
// KYTY_BC5_0429_RR: 0 or unset off; 1 any guest sleeper below 700; 2 (build 11) only a sleeper on a pool semaphore,
// one that two or more distinct threads have slept on (a worker pool: the job system's, not a lone audio thread's)
static int Mode() {
	static const int v = [] {
		const char* e = std::getenv("KYTY_BC5_0429_RR");
		int         m = 0;
		if (e != nullptr && e[0] == '2' && e[1] == 0) {
			m = 2;
		} else if (bc5::env_rule::on(e)) {
			m = 1;
		}
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0429: R (RR for the guest's sleepers) %s\n", m == 2 ? "ON, pool sleepers only" : m == 1 ? "ON" : "off");
#endif
		return m;
	}();
	return v;
}
static bool On() { return Mode() != 0; }
constexpr int     kMaxSlots   = 64;
constexpr int64_t kSoftUs     = 20000;
constexpr int64_t kHardUs     = 200000;
constexpr int     kRrMax      = 20; // rtkit's MaxRealtimePriority on the box (2026-11-17)
static std::atomic<int> g_tid[kMaxSlots];      // RR threads (0: free)
static std::atomic<int> g_slot_prio[kMaxSlots]; // their guest priorities
static std::atomic<int>  g_xcpu_tid {0};       // the last thread SIGXCPU dropped (logged by the watchdog)
constexpr int64_t        kWindowMs  = 20000; // build 12: the rtkit budget per window
constexpr int            kWindowMax = 15;
static std::atomic<int64_t> g_win_start {0};   // ms, steady clock
static std::atomic<int>     g_win_calls {0};
static std::atomic<int64_t> g_full_until {0};  // rtkit refused: no new promotion before this (ms), only replacements
static std::atomic<int>     g_evicted_tid[kMaxSlots]; // evicted, waiting to come back (not spinners)
static std::atomic<int>     g_evicted_n {0};
static std::atomic<int> g_held {0};            // how many hold RR now
static std::atomic<int> g_calls {0};           // rtkit calls made
#ifndef BC5_LEAN
static std::atomic<int> g_logged {0};
#endif
static std::atomic<int> g_spinner_tid[kMaxSlots]; // dropped for good
// build 11: counters in both builds (lean too: one stderr line a minute from the watchdog thread, for this experiment
// only; it goes from lean before any swap), and the last 16 losses as kind and guest priority
enum Ev { kPromoted, kRefused, kCapDenied, kBudgetDenied, kEvicted, kDropXcpu, kDropWatchdog, kDropPrio, kDropGone, kEvN };
static const char       kEvName[kEvN] = {'P', 'R', 'C', 'B', 'E', 'X', 'W', 'H', 'G'};
static std::atomic<int> g_ev[kEvN];
static std::atomic<int> g_last[16];
static std::atomic<int> g_last_n {0};
static void Count(Ev e, int prio) { // async-signal-safe
	g_ev[e].fetch_add(1, std::memory_order_relaxed);
	if (e == kPromoted || e == kCapDenied) {
		return; // the ring keeps the losses: drops, evictions, refusals, budget denials
	}
	g_last[g_last_n.fetch_add(1, std::memory_order_relaxed) & 15].store(e * 10000 + (prio < 0 ? 9999 : prio), std::memory_order_relaxed);
}
static int              g_cap = 0;
static int64_t NowMs() {
	return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
static bool BudgetOk(bool replacing) { // one rtkit call may be made now
	const int64_t now = NowMs();
	int64_t       w   = g_win_start.load();
	if (now - w >= kWindowMs && g_win_start.compare_exchange_strong(w, now)) {
		g_win_calls.store(0);
	}
	if (now < g_full_until.load() && !replacing) {
		return false;
	}
	return g_win_calls.fetch_add(1) < kWindowMax || (g_win_calls.fetch_sub(1), false);
}
static bool IsEvicted(int tid) {
	for (auto& s: g_evicted_tid) {
		if (s.load(std::memory_order_relaxed) == tid) {
			return true;
		}
	}
	return false;
}
static void MarkEvicted(int tid) {
	for (auto& s: g_evicted_tid) {
		int z = 0;
		if (s.load(std::memory_order_relaxed) == tid) {
			return;
		}
		if (s.compare_exchange_strong(z, tid)) {
			g_evicted_n.fetch_add(1);
			return;
		}
	}
}
static void Unevict(int tid) {
	for (auto& s: g_evicted_tid) {
		int t = tid;
		if (s.compare_exchange_strong(t, 0)) {
			g_evicted_n.fetch_sub(1);
			return;
		}
	}
}

static long RawSyscall3(long n, long a, long b, long c) { // no errno: the handler may run on any thread
	long ret;
	asm volatile("syscall" : "=a"(ret) : "a"(n), "D"(a), "S"(b), "d"(c) : "rcx", "r11", "memory");
	return ret;
}
static long RawSyscall4(long n, long a, long b, long c, long d) {
	long ret;
	register long r10 asm("r10") = d;
	asm volatile("syscall" : "=a"(ret) : "a"(n), "D"(a), "S"(b), "d"(c), "r"(r10) : "rcx", "r11", "memory");
	return ret;
}
static void Log(const char* what, int tid, const char* name, int prio, int rr, long rc) {
#ifndef BC5_LEAN
	if (g_logged.fetch_add(1, std::memory_order_relaxed) < 200) {
		std::fprintf(stderr, "[bc5] exp 0429 R: %s tid %d '%s' prio %d rr %d rc %ld (held %d, calls %d)\n", what, tid, name, prio, rr, rc,
		             g_held.load(), g_calls.load());
	}
#else
	(void)what; (void)tid; (void)name; (void)prio; (void)rr; (void)rc;
#endif
}
static bool IsSpinner(int tid) {
	for (auto& s: g_spinner_tid) {
		if (s.load(std::memory_order_relaxed) == tid) {
			return true;
		}
	}
	return false;
}
static void MarkSpinner(int tid) {
	for (auto& s: g_spinner_tid) {
		int z = 0;
		if (s.load(std::memory_order_relaxed) == tid || s.compare_exchange_strong(z, tid)) {
			return;
		}
	}
}
// Drops tid back to SCHED_OTHER (an unprivileged thread may always lower its policy; rtkit sets RESET_ON_FORK, kept).
// Async-signal-safe: raw syscalls and atomics only.
static int Drop(int tid, bool spinner = true) { // the dropped thread's guest priority, or -1 when it held no slot
	for (int i = 0; i < kMaxSlots; i++) {
		auto& s = g_tid[i];
		int   t = tid;
		if (s.compare_exchange_strong(t, 0)) {
			const int gp = g_slot_prio[i].load(std::memory_order_relaxed);
			struct { int prio; } p {0};
			RawSyscall3(SYS_sched_setscheduler, tid, SCHED_OTHER | 0x40000000 /* SCHED_RESET_ON_FORK */, reinterpret_cast<long>(&p));
			g_held.fetch_sub(1, std::memory_order_relaxed);
			if (spinner) {
				MarkSpinner(tid);
			}
			return gp;
		}
	}
	return -1;
}
static void ResetSoft() {
	rlimit r {static_cast<rlim_t>(kSoftUs), static_cast<rlim_t>(kHardUs)};
	RawSyscall4(SYS_prlimit64, 0, RLIMIT_RTTIME, reinterpret_cast<long>(&r), 0);
}
static void OnXcpu(int) { // bound 1: the kernel sends SIGXCPU to the RR thread that passed the soft limit
	const int self = static_cast<int>(RawSyscall3(SYS_gettid, 0, 0, 0));
	if (const int gp = Drop(self); gp >= 0) {
		g_xcpu_tid.store(self, std::memory_order_relaxed);
		Count(kDropXcpu, gp);
	}
	ResetSoft(); // the kernel raised the soft limit by a second; put it back below the hard one
}
static void Watchdog() { // bound 2
	pthread_setname_np(pthread_self(), "bc5-rr-watch");
	struct Seen {
		int      tid;
		uint64_t run, slices, since_ns;
	};
	Seen seen[kMaxSlots] {};
	for (int tick = 1;; tick++) {
		std::this_thread::sleep_for(std::chrono::milliseconds(5));
		if (tick % 12000 == 0) { // about a minute
			char      last[16 * 6 + 1];
			int       o = 0;
			const int n = g_last_n.load();
			for (int k = (n > 16 ? n - 16 : 0); k < n; k++) {
				const int v = g_last[k & 15].load();
				o += std::snprintf(last + o, sizeof(last) - o, "%c%d ", kEvName[v / 10000], v % 10000);
			}
			last[o] = 0;
			std::fprintf(stderr, "[bc5] exp 0429 R count: held %d calls %d P %d R %d C %d B %d E %d X %d W %d H %d G %d | last %s\n", g_held.load(),
			             g_calls.load(), g_ev[kPromoted].load(), g_ev[kRefused].load(), g_ev[kCapDenied].load(), g_ev[kBudgetDenied].load(),
			             g_ev[kEvicted].load(), g_ev[kDropXcpu].load(), g_ev[kDropWatchdog].load(), g_ev[kDropPrio].load(), g_ev[kDropGone].load(), last);
		}
		if (const int x = g_xcpu_tid.exchange(0); x != 0) {
			Log("dropped by SIGXCPU (20 ms without blocking)", x, "", 0, 0, 0);
		}
		const auto now = static_cast<uint64_t>(std::chrono::steady_clock::now().time_since_epoch().count());
		for (int i = 0; i < kMaxSlots; i++) {
			const int tid = g_tid[i].load(std::memory_order_relaxed);
			if (tid == 0) {
				seen[i].tid = 0;
				continue;
			}
			char path[64], buf[128];
			std::snprintf(path, sizeof(path), "/proc/self/task/%d/schedstat", tid);
			const int fd = open(path, O_RDONLY | O_CLOEXEC);
			if (fd < 0) {
				if (const int gp = Drop(tid); gp >= 0) { // the thread is gone
					Count(kDropGone, gp);
				}
				continue;
			}
			const ssize_t r = read(fd, buf, sizeof(buf) - 1);
			close(fd);
			buf[r > 0 ? r : 0] = 0;
			unsigned long long run = 0, wait = 0, slices = 0;
			std::sscanf(buf, "%llu %llu %llu", &run, &wait, &slices);
			if (seen[i].tid != tid || seen[i].slices != slices) {
				seen[i] = {tid, run, slices, now};
			} else if (run - seen[i].run >= 95000000ull && now - seen[i].since_ns >= 100000000ull) {
				if (const int gp = Drop(tid); gp >= 0) {
					Count(kDropWatchdog, gp);
					Log("dropped by the watchdog (100 ms in one slice)", tid, "", gp, 0, 0);
				}
			}
		}
	}
}
static void Init() {
	static std::once_flag once;
	std::call_once(once, [] {
		const long n = sysconf(_SC_NPROCESSORS_ONLN);
		g_cap        = static_cast<int>(std::clamp<long>(n - 2, 1, kMaxSlots));
		ResetSoft(); // rtkit requires RLIMIT_RTTIME with a hard limit within its RTTimeUSecMax
		struct sigaction sa {};
		sa.sa_handler = OnXcpu;
		sigemptyset(&sa.sa_mask);
		sa.sa_flags = SA_RESTART;
		sigaction(SIGXCPU, &sa, nullptr);
		std::thread(Watchdog).detach();
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0429 R: cap %d RR threads, RLIMIT_RTTIME soft %lld hard %lld us, watchdog on\n", g_cap,
		             static_cast<long long>(kSoftUs), static_cast<long long>(kHardUs));
#endif
	});
}
// rtkit's MakeThreadRealtimeWithPID through libdbus, loaded at run time (no build dependency; the host has it).
static long RtkitMakeRealtime(uint64_t tid, uint32_t prio) {
	struct Api {
		void* (*bus_get)(int, void*);
		void* (*new_call)(const char*, const char*, const char*, const char*);
		int (*append)(void*, int, ...);
		void* (*send_block)(void*, void*, int, void*);
		void (*unref)(void*);
		void (*err_init)(void*);
		int (*err_set)(const void*);
		void (*err_free)(void*);
		int (*threads_init)();
		void (*no_exit)(void*, unsigned);
		void* (*open_private)(const char*, void*);
		int (*bus_register)(void*, void*);
		bool ok = false;
	};
	static Api api = [] {
		Api a {};
		void* h = dlopen("libdbus-1.so.3", RTLD_NOW | RTLD_LOCAL);
		if (h == nullptr) {
			return a;
		}
		a.bus_get      = reinterpret_cast<void* (*)(int, void*)>(dlsym(h, "dbus_bus_get_private"));
		a.new_call     = reinterpret_cast<void* (*)(const char*, const char*, const char*, const char*)>(dlsym(h, "dbus_message_new_method_call"));
		a.append       = reinterpret_cast<int (*)(void*, int, ...)>(dlsym(h, "dbus_message_append_args"));
		a.send_block   = reinterpret_cast<void* (*)(void*, void*, int, void*)>(dlsym(h, "dbus_connection_send_with_reply_and_block"));
		a.unref        = reinterpret_cast<void (*)(void*)>(dlsym(h, "dbus_message_unref"));
		a.err_init     = reinterpret_cast<void (*)(void*)>(dlsym(h, "dbus_error_init"));
		a.err_set      = reinterpret_cast<int (*)(const void*)>(dlsym(h, "dbus_error_is_set"));
		a.err_free     = reinterpret_cast<void (*)(void*)>(dlsym(h, "dbus_error_free"));
		a.threads_init = reinterpret_cast<int (*)()>(dlsym(h, "dbus_threads_init_default"));
		a.no_exit      = reinterpret_cast<void (*)(void*, unsigned)>(dlsym(h, "dbus_connection_set_exit_on_disconnect"));
		a.open_private = reinterpret_cast<void* (*)(const char*, void*)>(dlsym(h, "dbus_connection_open_private"));
		a.bus_register = reinterpret_cast<int (*)(void*, void*)>(dlsym(h, "dbus_bus_register"));
		a.ok = a.bus_get && a.new_call && a.append && a.send_block && a.unref && a.err_init && a.err_set && a.err_free && a.threads_init && a.no_exit && a.open_private && a.bus_register;
		if (a.ok) {
			a.threads_init();
		}
		return a;
	}();
	if (!api.ok) {
		return -1000;
	}
	static std::mutex m;
	std::lock_guard   lk(m);
	alignas(16) char  err[64] {}; // DBusError: two pointers, a bit field, a pointer
	api.err_init(err);
	static void* conn = [&] { // a private connection of our own, kept; a lost bus must not end the emulator
		void* c = api.bus_get(1 /* DBUS_BUS_SYSTEM */, err);
		// inside the distrobox (the normal build) the host's system bus is at /run/host/run/dbus (read 2026-11-17); the
		// container shares the host's PID namespace, so rtkit takes our pid and tid as they are
		const char* paths[] = {std::getenv("DBUS_SYSTEM_BUS_ADDRESS"), "unix:path=/run/host/run/dbus/system_bus_socket"};
		for (const char* a: paths) {
			if (c != nullptr || a == nullptr || a[0] == 0) {
				continue;
			}
			api.err_free(err);
			api.err_init(err);
			c = api.open_private(a, err);
			if (c != nullptr && api.bus_register(c, err) == 0) {
				c = nullptr; // TODO: the connection is leaked on a failed hello; once per process
			}
		}
		if (c != nullptr) {
			api.no_exit(c, 0);
		}
		return c;
	}();
	if (conn == nullptr) {
		api.err_free(err);
		return -1001;
	}
	void* msg = api.new_call("org.freedesktop.RealtimeKit1", "/org/freedesktop/RealtimeKit1", "org.freedesktop.RealtimeKit1",
	                         "MakeThreadRealtimeWithPID");
	if (msg == nullptr) {
		return -1002;
	}
	uint64_t pid = static_cast<uint64_t>(getpid());
	api.append(msg, 't', &pid, 't', &tid, 'u', &prio, 0);
	g_calls.fetch_add(1, std::memory_order_relaxed);
	void* reply = api.send_block(conn, msg, 1000, err);
	api.unref(msg);
	long rc = 0;
	if (reply == nullptr || api.err_set(err)) {
		rc = -1003;
	}
	if (reply != nullptr) {
		api.unref(reply);
	}
	api.err_free(err);
	return rc;
}
static int RrOf(int guest_priority) {
	return std::clamp(1 + (700 - guest_priority) * (kRrMax - 1) / 700, 1, kRrMax);
}
// Called from Bc5ApplyGuestPriority (start, setprio) and at a thread's first sleep. Promotes only a sleeper below 700
// that is not a spinner, within the cap and rtkit's call budget; drops a thread whose priority went to 700 or above.
static void Apply(Pthread thread, bool sleeper) {
	if (!On() || thread == nullptr || thread->attr == nullptr || thread->host_thread_id == 0) {
		return;
	}
	Init();
	const int tid  = static_cast<int>(thread->host_thread_id);
	const int prio = thread->attr->guest_priority;
	bool      held = false;
	for (auto& s: g_tid) {
		held = held || s.load(std::memory_order_relaxed) == tid;
	}
	if (held && prio >= 700) {
		Count(kDropPrio, Drop(tid)); // not a spinner, but the rule says out; it stays out (rtkit's budget)
		Log("dropped (priority 700 or above)", tid, thread->name.c_str(), prio, 0, 0);
		return;
	}
	if (held || !sleeper || prio >= 700 || IsSpinner(tid)) {
		return;
	}
	if (thread->bc5_rr_main) { // the title's main thread runs the owner's help: the race R is meant to win, never promoted
		static std::atomic<int> once {0};
		if (once.fetch_add(1) == 0) {
			Log("not promoted (the runtime's main thread)", tid, thread->name.c_str(), prio, 0, 0);
		}
		return;
	}
	// a place under the cap, reserved atomically; when the cap is full, the holder with the numerically highest guest
	// priority above ours is dropped for good to make room (the console's order: a lower number wins)
	bool evicted = false;
	if (g_held.fetch_add(1) >= g_cap) {
		g_held.fetch_sub(1);
		int victim = 0, vprio = prio;
		for (int i = 0; i < kMaxSlots; i++) {
			const int t = g_tid[i].load(std::memory_order_relaxed);
			const int p = g_slot_prio[i].load(std::memory_order_relaxed);
			if (t != 0 && p > vprio) {
				victim = t;
				vprio  = p;
			}
		}
		if (victim == 0 || Drop(victim, false) < 0) {
			Count(kCapDenied, prio);
			Log("not promoted (the cap, no holder of a lower priority)", tid, thread->name.c_str(), prio, 0, 0);
			return;
		}
		Count(kEvicted, vprio);
		MarkEvicted(victim); // build 12: it comes back at a later sleep when a place is free
		Log("evicted for a higher priority", victim, "", vprio, 0, 0);
		evicted = true;
		if (g_held.fetch_add(1) >= g_cap) {
			g_held.fetch_sub(1);
			return;
		}
	}
	if (!BudgetOk(evicted)) {
		g_held.fetch_sub(1);
		Count(kBudgetDenied, prio);
		Log("not promoted (rtkit's budget)", tid, thread->name.c_str(), prio, 0, 0);
		return;
	}
	const int  rr = RrOf(prio);
	const long rc = RtkitMakeRealtime(static_cast<uint64_t>(tid), static_cast<uint32_t>(rr));
	if (rc != 0) {
		g_held.fetch_sub(1);
		g_full_until.store(g_win_start.load() + kWindowMs);
		Count(kRefused, prio);
		Log("rtkit refused", tid, thread->name.c_str(), prio, rr, rc);
		return;
	}
	for (int i = 0; i < kMaxSlots; i++) {
		int z = 0;
		if (g_tid[i].compare_exchange_strong(z, tid)) {
			g_slot_prio[i].store(prio, std::memory_order_relaxed);
			Count(kPromoted, prio);
			Unevict(tid);
			Log("promoted", tid, thread->name.c_str(), prio, rr, rc);
			return;
		}
	}
	g_held.fetch_sub(1);
	struct { int prio; } p0 {0};
	RawSyscall3(SYS_sched_setscheduler, tid, SCHED_OTHER | 0x40000000, reinterpret_cast<long>(&p0)); // no slot: give it back
}
} // namespace bc5_0429r

static void Bc5RrApply(Pthread thread, const char* /*why*/) {
	bc5_0429r::Apply(thread, thread != nullptr && thread->bc5_rr_sleeper);
}

// A guest thread's sleep on a guest semaphore (kernel/semaphore.cpp, after the resume): mark it a sleeper. Mode 2: only
// when the semaphore is a pool, slept on by two or more distinct threads (a table of semaphores by address, open
// addressing; with the table full no one more is promoted). A thread that slept on it first is marked at its next sleep.
namespace bc5_0429r {
constexpr int kPools = 512;
struct PoolSlot {
	std::atomic<uintptr_t> sem {0};
	std::atomic<int>       first {0};
	std::atomic<bool>      pool {false};
};
static PoolSlot g_pools[kPools];
static bool     IsPool(const void* sem, int tid) {
	const auto a = reinterpret_cast<uintptr_t>(sem);
	int        i = static_cast<int>(((a >> 4) * 2654435761ull) % kPools);
	for (int k = 0; k < kPools; k++, i = (i + 1) % kPools) {
		uintptr_t cur = g_pools[i].sem.load(std::memory_order_acquire);
		if (cur == 0) {
			uintptr_t z = 0;
			cur         = g_pools[i].sem.compare_exchange_strong(z, a) ? a : z;
		}
		if (cur != a) {
			continue; // another semaphore's slot
		}
		auto& s = g_pools[i];
		if (s.pool.load(std::memory_order_relaxed)) {
			return true;
		}
		int f = 0;
		if (s.first.compare_exchange_strong(f, tid) || f == tid) {
			return false; // the only sleeper so far
		}
		s.pool.store(true, std::memory_order_relaxed);
		return true;
	}
	return false;
}
} // namespace bc5_0429r
extern "C" void bc5_0429_r_on_sleep(const void* sem) {
	if (!bc5_0429r::On()) {
		return;
	}
	Pthread self = g_pthread_self;
	if (self == nullptr) {
		return;
	}
	if (self->bc5_rr_sleeper) { // build 12: an evicted sleeper comes back when a place is free
		if (bc5_0429r::g_evicted_n.load(std::memory_order_relaxed) > 0 && bc5_0429r::g_held.load(std::memory_order_relaxed) < bc5_0429r::g_cap &&
		    bc5_0429r::IsEvicted(static_cast<int>(self->host_thread_id))) {
			bc5_0429r::Apply(self, true);
		}
		return;
	}
	if (bc5_0429r::Mode() == 2 && !bc5_0429r::IsPool(sem, static_cast<int>(self->host_thread_id))) {
		return;
	}
	self->bc5_rr_sleeper = true;
	bc5_0429r::Apply(self, true);
}
#endif
// ---- end of experiment 0429 candidate R --------------------------------------------------------------------------
