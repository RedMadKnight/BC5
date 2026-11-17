
// ---- experiment 0429 candidate R: KYTY_BC5_0429_RR=1, the console's "a lower number wins" for the guest's sleepers -
// On the console a woken job worker takes its CPU at once from any lower-priority thread there (TODO(verify): the
// console's kernel; the title's own priorities and masks, exp 0429's trace). Here a woken worker waited behind threads
// of lower guest priority (h429Z1: 18 % of the job-semaphore wakes took 0.1-2 ms) while the owner's help took the job.
// On: a guest thread whose priority is below 700 (TODO(verify): the console's default thread priority) gets SCHED_RR
// from RealtimeKit1 (rtkit, the system bus; no system setting changed: on the box his RLIMIT_RTPRIO is 0, rtkit grants
// RR 1-20 with RLIMIT_RTTIME up to 200 ms, read 2026-11-17) at its first sleep on a guest semaphore, with an RR priority
// in the guest's order (a lower guest number, a higher RR priority). For any title; no title rows.
// Bounds (the box runs with RT throttling off, sched_rt_runtime_us = period):
//   1. RLIMIT_RTTIME on the process: soft 20 ms of RR time without blocking -> SIGXCPU, whose handler drops the running
//      RR thread back to SCHED_OTHER for good (a spinner); hard 200 ms -> the kernel ends the emulator (never the box);
//   2. a watchdog thread every 5 ms: an RR thread that ran 100 ms with no new time slice is dropped for good;
//   3. at most (online CPUs - 2) guest threads hold RR at once, so host threads always have two CPUs.
// A dropped thread is never promoted again (rtkit also limits its calls to 25 per 20 s per user, TODO(verify)).
// Off: nothing here runs. Normal build: every promotion, drop and refusal is logged (the first 200).
#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
#include <dlfcn.h>
#include <fcntl.h>
#include <sys/resource.h>
namespace bc5_0429r {
static bool On() {
	static const bool v = [] {
		const bool on = bc5::env_rule::on(std::getenv("KYTY_BC5_0429_RR"));
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0429: R (RR for the guest's sleepers) %s\n", on ? "ON" : "off");
#endif
		return on;
	}();
	return v;
}
constexpr int     kMaxSlots   = 64;
constexpr int64_t kSoftUs     = 20000;
constexpr int64_t kHardUs     = 200000;
constexpr int     kRrMax      = 20; // rtkit's MaxRealtimePriority on the box (2026-11-17)
static std::atomic<int> g_tid[kMaxSlots];      // RR threads (0: free)
static std::atomic<int> g_slot_prio[kMaxSlots]; // their guest priorities
static std::atomic<int>  g_xcpu_tid {0};       // the last thread SIGXCPU dropped (logged by the watchdog)
static std::atomic<bool> g_rtkit_full {false};   // rtkit refused once: ask again only to replace an evicted thread
static std::atomic<int> g_held {0};            // how many hold RR now
static std::atomic<int> g_calls {0};           // rtkit calls made
#ifndef BC5_LEAN
static std::atomic<int> g_logged {0};
#endif
static std::atomic<int> g_spinner_tid[kMaxSlots]; // dropped for good
static int              g_cap = 0;

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
static bool Drop(int tid) {
	for (auto& s: g_tid) {
		int t = tid;
		if (s.compare_exchange_strong(t, 0)) {
			struct { int prio; } p {0};
			RawSyscall3(SYS_sched_setscheduler, tid, SCHED_OTHER | 0x40000000 /* SCHED_RESET_ON_FORK */, reinterpret_cast<long>(&p));
			g_held.fetch_sub(1, std::memory_order_relaxed);
			MarkSpinner(tid);
			return true;
		}
	}
	return false;
}
static void ResetSoft() {
	rlimit r {static_cast<rlim_t>(kSoftUs), static_cast<rlim_t>(kHardUs)};
	RawSyscall4(SYS_prlimit64, 0, RLIMIT_RTTIME, reinterpret_cast<long>(&r), 0);
}
static void OnXcpu(int) { // bound 1: the kernel sends SIGXCPU to the RR thread that passed the soft limit
	const int self = static_cast<int>(RawSyscall3(SYS_gettid, 0, 0, 0));
	if (Drop(self)) {
		g_xcpu_tid.store(self, std::memory_order_relaxed);
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
	for (;;) {
		std::this_thread::sleep_for(std::chrono::milliseconds(5));
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
				Drop(tid); // the thread is gone
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
				if (Drop(tid)) {
					Log("dropped by the watchdog (100 ms in one slice)", tid, "", 0, 0, 0);
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
		Drop(tid); // not a spinner, but the rule says out; it stays out (rtkit's budget)
		Log("dropped (priority 700 or above)", tid, thread->name.c_str(), prio, 0, 0);
		return;
	}
	if (held || !sleeper || prio >= 700 || IsSpinner(tid)) {
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
		if (victim == 0 || !Drop(victim)) {
			Log("not promoted (the cap, no holder of a lower priority)", tid, thread->name.c_str(), prio, 0, 0);
			return;
		}
		Log("evicted for a higher priority", victim, "", vprio, 0, 0);
		evicted = true;
		if (g_held.fetch_add(1) >= g_cap) {
			g_held.fetch_sub(1);
			return;
		}
	}
	if (g_calls.load() >= 24 || (g_rtkit_full.load() && !evicted)) {
		g_held.fetch_sub(1);
		Log("not promoted (rtkit's budget)", tid, thread->name.c_str(), prio, 0, 0);
		return;
	}
	const int  rr = RrOf(prio);
	const long rc = RtkitMakeRealtime(static_cast<uint64_t>(tid), static_cast<uint32_t>(rr));
	if (rc != 0) {
		g_held.fetch_sub(1);
		g_rtkit_full.store(true);
		Log("rtkit refused", tid, thread->name.c_str(), prio, rr, rc);
		return;
	}
	for (int i = 0; i < kMaxSlots; i++) {
		int z = 0;
		if (g_tid[i].compare_exchange_strong(z, tid)) {
			g_slot_prio[i].store(prio, std::memory_order_relaxed);
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

// The first sleep of a guest thread on a guest semaphore (kernel/semaphore.cpp, after the resume): mark it a sleeper.
extern "C" void bc5_0429_r_on_sleep() {
	if (!bc5_0429r::On()) {
		return;
	}
	Pthread self = g_pthread_self;
	if (self == nullptr || self->bc5_rr_sleeper) {
		return;
	}
	self->bc5_rr_sleeper = true;
	bc5_0429r::Apply(self, true);
}
#endif
// ---- end of experiment 0429 candidate R --------------------------------------------------------------------------
