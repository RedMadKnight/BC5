
// ---- experiment 0429 candidate F: KYTY_BC5_0429_FAST_MUTEX=1, the guest mutex as a lock word in user space ------------
// The title's job workers take a per-entry guest mutex to scan their job list (its wrapper spins a bounded number of
// rounds of 16 `pause` and a trylock, then locks; exp 0429's reading of the title's worker loop), while the owner's help
// scans without it. Here every guest trylock, lock and unlock first took the host std::mutex inside the guest mutex, so
// a spinning trylock could sleep in the kernel behind the holder's unlock, and a waiter was woken through a condition
// variable. A FreeBSD-derived kernel (TODO(verify): the console's libkernel) keeps a mutex as a word in user space:
// trylock and an uncontended lock or unlock are one atomic operation, and the kernel is entered only to sleep on a
// contended word or to wake its sleeper. On (read once per process, so every mutex uses one scheme): the word is 0 free,
// 1 locked, 2 locked with sleepers (the futex mutex of U. Drepper, "Futexes Are Tricky", 2011, mutex 2); owner and count
// are written only by the holder; a timed lock and the guest-signal poll keep their meaning. Off: as before. Normal
// build: KYTY_BC5_0429_WAITS=1 also prints, every 20,000 contended locks, how many slept and their mean and max sleep.
#ifdef __linux__
#include <linux/futex.h>
static bool Bc5FastMutex() {
	static const bool v = [] {
		const bool on = bc5::env_rule::on(std::getenv("KYTY_BC5_0429_FAST_MUTEX"));
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0429: fast guest mutex %s\n", on ? "ON" : "off");
#endif
		return on;
	}();
	return v;
}

#ifndef BC5_LEAN
static std::atomic<uint64_t> g_bc5_fm_contended {0}, g_bc5_fm_slept {0}, g_bc5_fm_sleep_ns {0}, g_bc5_fm_max_ns {0};
static void Bc5FastMutexStat(bool slept, uint64_t ns) {
	static const bool on = bc5::env_rule::on(std::getenv("KYTY_BC5_0429_WAITS"));
	if (!on) {
		return;
	}
	const uint64_t n = g_bc5_fm_contended.fetch_add(1, std::memory_order_relaxed) + 1;
	if (slept) {
		g_bc5_fm_slept.fetch_add(1, std::memory_order_relaxed);
		g_bc5_fm_sleep_ns.fetch_add(ns, std::memory_order_relaxed);
		uint64_t m = g_bc5_fm_max_ns.load(std::memory_order_relaxed);
		while (ns > m && !g_bc5_fm_max_ns.compare_exchange_weak(m, ns, std::memory_order_relaxed)) {}
	}
	if (n % 20000 == 0) {
		const uint64_t s = g_bc5_fm_slept.load();
		std::fprintf(stderr, "[bc5] exp 0429 fast mutex: %llu contended locks, %llu slept, mean sleep %.1f us, max %.1f us\n",
		             static_cast<unsigned long long>(n), static_cast<unsigned long long>(s),
		             s != 0 ? static_cast<double>(g_bc5_fm_sleep_ns.load()) / static_cast<double>(s) / 1000.0 : 0.0,
		             static_cast<double>(g_bc5_fm_max_ns.load()) / 1000.0);
	}
}
#endif

static std::atomic<uint32_t>& Bc5FmWord(PthreadMutexPrivate* mutex) {
	return mutex->bc5_word;
}

static int Bc5FastMutexTrylock(PthreadMutexPrivate* mutex, Pthread self) {
	if (std::atomic_ref<Pthread>(mutex->owner).load(std::memory_order_relaxed) == self) {
		if (mutex->type == 2) {
			if (mutex->count == UINT32_MAX) {
				return EAGAIN;
			}
			mutex->count++;
			return OK;
		}
		return EBUSY;
	}
	uint32_t expected = 0;
	if (!Bc5FmWord(mutex).compare_exchange_strong(expected, 1, std::memory_order_acquire, std::memory_order_relaxed)) {
		return EBUSY;
	}
	std::atomic_ref<Pthread>(mutex->owner).store(self, std::memory_order_relaxed);
	mutex->count = 1;
	return OK;
}

static int Bc5FastMutexLock(PthreadMutexPrivate* mutex, Pthread self, KernelUseconds* timeout_us) {
	if (std::atomic_ref<Pthread>(mutex->owner).load(std::memory_order_relaxed) == self) {
		if (mutex->type == 2) {
			if (mutex->count == UINT32_MAX) {
				return EAGAIN;
			}
			mutex->count++;
			return OK;
		}
		if (timeout_us != nullptr) {
			if (*timeout_us > 0) {
				std::this_thread::sleep_for(std::chrono::microseconds(*timeout_us));
			}
			return ETIMEDOUT;
		}
		return EDEADLK;
	}
	auto&    w        = Bc5FmWord(mutex);
	uint32_t expected = 0;
	if (!w.compare_exchange_strong(expected, 1, std::memory_order_acquire, std::memory_order_relaxed)) {
		bool     slept = false;
		uint64_t t0    = 0;
		bool     got   = false;
		for (int i = 0; i < 64 && !got; i++) { // a short spin while the holder is likely running
			_mm_pause();
			expected = 0;
			got      = w.load(std::memory_order_relaxed) == 0 &&
			      w.compare_exchange_weak(expected, 1, std::memory_order_acquire, std::memory_order_relaxed);
		}
		if (!got) {
			if (timeout_us != nullptr && *timeout_us == 0) {
				return ETIMEDOUT;
			}
			const auto deadline = timeout_us != nullptr
			                          ? std::chrono::steady_clock::now() + std::chrono::microseconds(*timeout_us)
			                          : std::chrono::steady_clock::time_point::max();
			t0 = static_cast<uint64_t>(std::chrono::steady_clock::now().time_since_epoch().count());
			while (w.exchange(2, std::memory_order_acquire) != 0) {
				uint32_t slice = SIGNAL_APC_POLL_MICROS;
				if (timeout_us != nullptr) {
					const auto now = std::chrono::steady_clock::now();
					if (now >= deadline) {
						return ETIMEDOUT; // the word may stay 2: the next unlock then wakes nobody or one sleeper, both correct
					}
					slice = static_cast<uint32_t>(std::min<int64_t>(
					    SIGNAL_APC_POLL_MICROS, std::chrono::duration_cast<std::chrono::microseconds>(deadline - now).count() + 1));
				}
				timespec ts {};
				ts.tv_sec  = static_cast<time_t>(slice / 1000000u);
				ts.tv_nsec = static_cast<long>((slice % 1000000u) * 1000u);
				syscall(SYS_futex, reinterpret_cast<uint32_t*>(&w), FUTEX_WAIT_PRIVATE, 2u, &ts, nullptr, 0u);
				slept = true;
				KernelDispatchPendingSignalForCurrentThread();
			}
		}
#ifndef BC5_LEAN
		Bc5FastMutexStat(slept, slept ? static_cast<uint64_t>(std::chrono::steady_clock::now().time_since_epoch().count()) - t0 : 0);
#else
		(void)slept;
		(void)t0;
#endif
	}
	std::atomic_ref<Pthread>(mutex->owner).store(self, std::memory_order_relaxed);
	mutex->count = 1;
	return OK;
}

static int Bc5FastMutexUnlock(PthreadMutexPrivate* mutex, Pthread self, uint32_t* recurse) {
	if (std::atomic_ref<Pthread>(mutex->owner).load(std::memory_order_relaxed) != self) {
		return EPERM;
	}
	if (recurse != nullptr) {
		*recurse     = mutex->count;
		mutex->count = 1;
	}
	if (mutex->type == 2 && mutex->count > 1) {
		mutex->count--;
		return OK;
	}
	std::atomic_ref<Pthread>(mutex->owner).store(nullptr, std::memory_order_relaxed);
	mutex->count = 0;
	if (Bc5FmWord(mutex).exchange(0, std::memory_order_release) == 2) {
		syscall(SYS_futex, reinterpret_cast<uint32_t*>(&Bc5FmWord(mutex)), FUTEX_WAKE_PRIVATE, 1, nullptr, nullptr, 0u);
	}
	return OK;
}
#endif // __linux__
// ---- end of experiment 0429 candidate F ----------------------------------------------------------------------------
