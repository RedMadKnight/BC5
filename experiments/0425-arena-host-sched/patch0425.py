#!/usr/bin/env python3
# BC5 experiment 0425: applies the PlayGo switches, the three scheduling candidates and the catcher to private copies of four
# KytyPlus units.
#   python3 -I patch0425.py <tree>      (tree: a copy of the shared host tree, f266548 + patch 0001 4945ef1b)
# Every anchor must occur exactly once; the units' line endings are kept (semaphore.cpp and pthread.cpp are CRLF).
# Switches (all unset = off = the shared build's behaviour; unset, empty or "0" is off):
#   KYTY_BC5_0425_WAKE_SLICE_US=<100..3000>  C1: an EEVDF slice request (sched_setattr sched_runtime) on guest threads
#                                            below the background band (guest priority < 733)
#   KYTY_BC5_0425_HANDOFF_US=<1..2000>       C2: after a guest signal that readied a waiter, the signaller yields its
#                                            CPU until every waiter readied so far has resumed, at most this long
#   KYTY_BC5_0425_DIRECT_WAKE=1              C3: a signal hands the count to the waiter and wakes only that waiter, on
#                                            its own futex, after the semaphore's lock is released
#   KYTY_BC5_0425_CATCH=1                    catcher (normal build only): owner help calls taken while a "Job Hi"
#                                            waiter was readied but had not yet run; with JobArenaFix off it installs
#                                            the hook as a pass-through (the title's call unchanged)
import hashlib
import sys

PINS = {
    'src/kernel/semaphore.cpp': '0deadcb85b3419a9bd75535a8dc39878a3b7fd81120217db3043c65dcf5f0bdd',
    'src/kernel/pthread.cpp': '6791812a5cda16563b9e7bf63da167e52e562f1b4a4057ec74230841d92a8fad',
    'src/loader/gamePatch.cpp': 'a3651a0aa6260535b2118053e6f6c1a2c517ee04fc25b1d7902609c2e09cec70',
    'src/libs/libPlayGo.cpp': 'b0e55eecccb48f8ccd36bfcf1e5f8b6d6ee209985598420ae20302c97488d990',
}

# ------------------------------------------------------------------------------------------------- semaphore.cpp
SEMA = []

SEMA.append((r'''#include "bc5/load_stat.hpp" // experiment 0415 (ls415)
''', r'''#include "bc5/load_stat.hpp" // experiment 0415 (ls415)
#include <chrono> // experiment 0425
#include <memory> // experiment 0425
#ifdef __linux__
#include <linux/futex.h> // experiment 0425 C3
#include <pthread.h>     // experiment 0425 catcher: pthread_getname_np
#include <sched.h>       // experiment 0425 C2: sched_yield
#include <sys/syscall.h>
#include <unistd.h>
#include <ctime>
#endif

// ---- experiment 0425: the second title's job-arena race at its source (docs/HANDOFF.md F444-F458, F790-F806) -------
// C2 KYTY_BC5_0425_HANDOFF_US=<1..2000>: after a guest signal that readied a waiter, the signaller yields its CPU
//    (sched_yield) until every waiter this semaphore has readied so far has resumed, at most that long. Unlike exp
//    0388's PUSH_UNTIL_PAIRED (H), it yields instead of spinning, so a woken waiter queued on the signaller's own CPU
//    runs at once, and it applies to every guest semaphore, not by name or by the title's tables.
// C3 KYTY_BC5_0425_DIRECT_WAKE=1: a signal hands the count to the waiters it serves (as before) and wakes exactly those
//    waiters, each on its own futex word, after the semaphore's lock is released; the woken waiter no longer wakes into
//    a lock its waker still holds, and no broadcast reaches the other waiters. Read once per semaphore at creation.
// Catcher KYTY_BC5_0425_CATCH=1 (normal build only): the count of "Job Hi" waiters readied by a signal (result Ok)
//    and not yet resumed, read by the owner-help hook in loader/gamePatch.cpp (bc5_0425_hi_pending).
// Unset, empty or "0" is off for each word; a value that is not a positive number is off as well.
namespace bc5_0425 {
static int ReadUs(const char* name, long lo, long hi) {
	const char* e = std::getenv(name);
	if (!bc5::env_rule::on(e)) {
		return 0;
	}
	char*      end = nullptr;
	const long v   = std::strtol(e, &end, 10);
	if (end == e || v <= 0) {
		return 0;
	}
	return static_cast<int>(std::clamp(v, lo, hi));
}
static int HandoffUs() {
	static const int v = [] {
		const int us = ReadUs("KYTY_BC5_0425_HANDOFF_US", 1, 2000);
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0425: C2 handoff %s (%d us)\n", us > 0 ? "ON" : "off", us);
#endif
		return us;
	}();
	return v;
}
static bool DirectWake() {
	static const bool v = [] {
#ifdef __linux__
		const bool on = bc5::env_rule::on(std::getenv("KYTY_BC5_0425_DIRECT_WAKE"));
#else
		const bool on = false; // the futex path is Linux only
#endif
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0425: C3 direct wake %s\n", on ? "ON" : "off");
#endif
		return on;
	}();
	return v;
}
#ifndef BC5_LEAN
static std::atomic<int>      g_hi_pending {0};
static std::atomic<uint64_t> g_hi_marked {0};
static bool                  CatchOn() {
    static const bool v = bc5::env_rule::on(std::getenv("KYTY_BC5_0425_CATCH"));
    return v;
}
// A waiter of the title's high job class: its host thread carries the guest name (pthread.cpp, KytyPS5 199d0a9).
static bool ThisThreadIsHi() {
	thread_local int v = -1;
	if (v < 0) {
		char n[16] = {};
#ifdef __linux__
		pthread_getname_np(pthread_self(), n, sizeof(n));
#endif
		v = std::strncmp(n, "Job Hi", 6) == 0 ? 1 : 0;
	}
	return v == 1;
}
#endif
#ifdef __linux__
static void FutexWait(std::atomic<uint32_t>* word, uint32_t micros) {
	timespec ts {};
	ts.tv_sec  = static_cast<time_t>(micros / 1000000u);
	ts.tv_nsec = static_cast<long>((micros % 1000000u) * 1000u);
	syscall(SYS_futex, reinterpret_cast<uint32_t*>(word), FUTEX_WAIT_PRIVATE, 0u, &ts, nullptr, 0u);
}
static void FutexWake(std::atomic<uint32_t>* word) {
	syscall(SYS_futex, reinterpret_cast<uint32_t*>(word), FUTEX_WAKE_PRIVATE, 1, nullptr, nullptr, 0u);
}
#endif
#ifndef BC5_LEAN
static std::atomic<uint64_t> g_handoffs {0};
static std::atomic<uint64_t> g_handoffs_met {0};
static std::atomic<uint64_t> g_handoff_us {0};
#endif
// C2: yield until `resumed` reaches `target`, at most `us`. The counter is shared with the semaphore, so a semaphore
// deleted meanwhile is not touched.
static void Handoff(const std::shared_ptr<std::atomic<uint64_t>>& resumed, uint64_t target, int us) {
	const auto t0  = std::chrono::steady_clock::now();
	const auto end = t0 + std::chrono::microseconds(us);
	bool       met = true;
	while (resumed->load(std::memory_order_acquire) < target) {
		if (std::chrono::steady_clock::now() >= end) {
			met = false;
			break;
		}
#ifdef __linux__
		sched_yield();
#endif
	}
#ifndef BC5_LEAN
	const auto waited = std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now() - t0).count();
	const uint64_t n  = g_handoffs.fetch_add(1, std::memory_order_relaxed) + 1;
	const uint64_t m  = met ? g_handoffs_met.fetch_add(1, std::memory_order_relaxed) + 1 : g_handoffs_met.load(std::memory_order_relaxed);
	const uint64_t s  = g_handoff_us.fetch_add(static_cast<uint64_t>(waited), std::memory_order_relaxed) + static_cast<uint64_t>(waited);
	if (n == 1 || n % 2000 == 0) {
		std::fprintf(stderr, "[bc5] exp 0425 handoff: %llu handoffs, %llu ended by the resume, %llu at the bound, mean %.1f us\n",
		             static_cast<unsigned long long>(n), static_cast<unsigned long long>(m), static_cast<unsigned long long>(n - m),
		             static_cast<double>(s) / static_cast<double>(n));
	}
#else
	(void)met;
#endif
}
} // namespace bc5_0425

#ifndef BC5_LEAN
// Experiment 0425's catcher, read by loader/gamePatch.cpp's owner-help hook: "Job Hi" waiters readied, not yet resumed.
extern "C" int bc5_0425_hi_pending() {
	return bc5_0425::g_hi_pending.load(std::memory_order_acquire);
}
extern "C" unsigned long long bc5_0425_hi_marked() {
	return bc5_0425::g_hi_marked.load(std::memory_order_relaxed);
}
#endif
// ---- end of experiment 0425's helpers ------------------------------------------------------------------------------
'''))

SEMA.append((r'''	KernelSemaPrivate(const std::string& name, bool fifo, int init_count, int max_count)
	    : m_name(name), m_fifo_order(fifo), m_count(init_count), m_init_count(init_count),
	      m_max_count(max_count) {};
''', r'''	KernelSemaPrivate(const std::string& name, bool fifo, int init_count, int max_count)
	    : m_name(name), m_fifo_order(fifo), m_count(init_count), m_init_count(init_count),
	      m_max_count(max_count), m_bc5_direct(bc5_0425::DirectWake()) {};
'''))

SEMA.append((r'''	struct WaitingThread {
		int    id         = 0;
		int    priority   = 700;
		int    need_count = 0;
		Result result     = Result::TimedOut;
		bool   ready      = false;
	};

	void AddWaiter(WaitingThread* waiter);
	void RemoveWaiter(WaitingThread* waiter);
	void WakeWaiters();
''', r'''	struct WaitingThread {
		int    id         = 0;
		int    priority   = 700;
		int    need_count = 0;
		Result result     = Result::TimedOut;
		bool   ready      = false;
		bool   bc5_hi      = false; // exp 0425 catcher: a "Job Hi" thread
		bool   bc5_pending = false; // exp 0425 catcher: counted in g_hi_pending
		std::atomic<uint32_t> bc5_word {0};   // exp 0425 C3: 1 once readied (the futex word)
		std::atomic<uint32_t> bc5_waking {0}; // exp 0425 C3: 1 while a waker has still to wake this waiter
	};

	void AddWaiter(WaitingThread* waiter);
	void RemoveWaiter(WaitingThread* waiter);
	void WakeWaiters();
	void Bc5Ready(WaitingThread* waiter, Result result); // exp 0425: every "ready" goes through here
	static void Bc5WakeList(std::vector<WaitingThread*>* list); // exp 0425 C3: after the lock is released
	void Bc5Resumed(WaitingThread* waiter); // exp 0425: the waiter runs again (under the lock)
'''))

SEMA.append((r'''	int                         m_init_count;
	int                         m_max_count;
};
''', r'''	int                         m_init_count;
	int                         m_max_count;
	bool                        m_bc5_direct;            // exp 0425 C3, fixed at creation
	std::vector<WaitingThread*> m_bc5_wake;              // exp 0425 C3: readied, to be woken after the lock
	uint64_t                    m_bc5_readied = 0;       // exp 0425 C2: waiters readied so far (under the lock)
	std::shared_ptr<std::atomic<uint64_t>> m_bc5_resumed = std::make_shared<std::atomic<uint64_t>>(0); // exp 0425 C2
};
'''))

SEMA.append((r'''KernelSemaPrivate::~KernelSemaPrivate() {
	Common::LockGuard lock(m_mutex);

	while (m_status != Status::Set) {
		m_mutex.Unlock();
		Common::Thread::SleepMicro(10);
		m_mutex.Lock();
	}

	m_status = Status::Deleted;

	for (auto* waiter: m_waiting_threads) {
		if (!waiter->ready) {
			waiter->result = Result::Deleted;
			waiter->ready  = true;
		}
	}

	m_cond_var.SignalAll();
''', r'''// Experiment 0425: one place that makes a waiter ready (the result, the catcher's count, C2's count, C3's list).
void KernelSemaPrivate::Bc5Ready(WaitingThread* waiter, Result result) {
	waiter->result = result;
	waiter->ready  = true;
	m_bc5_readied++;
#ifndef BC5_LEAN
	if (result == Result::Ok && waiter->bc5_hi) {
		waiter->bc5_pending = true;
		bc5_0425::g_hi_pending.fetch_add(1, std::memory_order_acq_rel);
		bc5_0425::g_hi_marked.fetch_add(1, std::memory_order_relaxed);
	}
#endif
	if (m_bc5_direct) {
		waiter->bc5_word.store(1, std::memory_order_release);
		waiter->bc5_waking.store(1, std::memory_order_release);
		m_bc5_wake.push_back(waiter);
	}
}

// Experiment 0425 C3: wake each listed waiter on its own word; a waiter does not leave Wait while bc5_waking is 1.
void KernelSemaPrivate::Bc5WakeList(std::vector<WaitingThread*>* list) {
	for (auto* waiter: *list) {
#ifdef __linux__
		bc5_0425::FutexWake(&waiter->bc5_word);
#endif
		waiter->bc5_waking.store(0, std::memory_order_release); // the waiter may be gone after this store
	}
	list->clear();
}

// Experiment 0425: a readied waiter runs again (under the lock): the catcher's and C2's counts.
void KernelSemaPrivate::Bc5Resumed(WaitingThread* waiter) {
	m_bc5_resumed->fetch_add(1, std::memory_order_acq_rel);
#ifndef BC5_LEAN
	if (waiter->bc5_pending) {
		waiter->bc5_pending = false;
		bc5_0425::g_hi_pending.fetch_sub(1, std::memory_order_acq_rel);
	}
#else
	(void)waiter;
#endif
}

KernelSemaPrivate::~KernelSemaPrivate() {
	Common::LockGuard lock(m_mutex);

	while (m_status != Status::Set) {
		m_mutex.Unlock();
		Common::Thread::SleepMicro(10);
		m_mutex.Lock();
	}

	m_status = Status::Deleted;

	for (auto* waiter: m_waiting_threads) {
		if (!waiter->ready) {
			Bc5Ready(waiter, Result::Deleted); // exp 0425
		}
	}

	m_cond_var.SignalAll();
	Bc5WakeList(&m_bc5_wake); // exp 0425 C3: under the lock here; the waiters take it after the loop below drops it
'''))

SEMA.append((r'''KernelSemaPrivate::Result KernelSemaPrivate::Cancel(int set_count, int* num_waiting_threads) {
	Common::LockGuard lock(m_mutex);

	if (set_count > m_max_count) {
		return Result::InvalCount;
	}

	if (m_status == Status::Deleted) {
		return Result::Deleted;
	}

	if (num_waiting_threads != nullptr) {
		*num_waiting_threads = static_cast<int>(
		    std::count_if(m_waiting_threads.begin(), m_waiting_threads.end(),
		                  [](const WaitingThread* waiter) { return !waiter->ready; }));
	}

	m_count = (set_count < 0 ? m_init_count : set_count);

	for (auto* waiter: m_waiting_threads) {
		if (!waiter->ready) {
			waiter->result = Result::Canceled;
			waiter->ready  = true;
		}
	}

	m_cond_var.SignalAll();

	return Result::Ok;
}
''', r'''KernelSemaPrivate::Result KernelSemaPrivate::Cancel(int set_count, int* num_waiting_threads) {
	std::vector<WaitingThread*> wake; // exp 0425 C3
	{
		Common::LockGuard lock(m_mutex);

		if (set_count > m_max_count) {
			return Result::InvalCount;
		}

		if (m_status == Status::Deleted) {
			return Result::Deleted;
		}

		if (num_waiting_threads != nullptr) {
			*num_waiting_threads = static_cast<int>(
			    std::count_if(m_waiting_threads.begin(), m_waiting_threads.end(),
			                  [](const WaitingThread* waiter) { return !waiter->ready; }));
		}

		m_count = (set_count < 0 ? m_init_count : set_count);

		for (auto* waiter: m_waiting_threads) {
			if (!waiter->ready) {
				Bc5Ready(waiter, Result::Canceled); // exp 0425
			}
		}

		if (!m_bc5_direct) {
			m_cond_var.SignalAll();
		}
		wake.swap(m_bc5_wake);
	}
	Bc5WakeList(&wake); // exp 0425 C3: empty unless direct

	return Result::Ok;
}
'''))

SEMA.append((r'''KernelSemaPrivate::Result KernelSemaPrivate::Signal(int signal_count) {
	Common::LockGuard lock(m_mutex);

	if (m_status == Status::Deleted) {
		return Result::Deleted;
	}

	// Experiment 0405 "signal" (KYTY_BC5_SEMA_FIXES): a room check that cannot overflow (AnyPS5 Semaphore.cpp:64).
	if (Bc5SemaFix(BC5_SEMA_FIX_SIGNAL) && (signal_count <= 0 || m_count > m_max_count - signal_count)) {
		return Result::InvalCount;
	}
	if (m_count + signal_count > m_max_count) {
		return Result::InvalCount;
	}

	m_count += signal_count;
	bc5::load_stat::count(bc5::load_stat::kSemaSignal, m_waiting_threads.size()); // experiment 0415 (ls415): items = waiters present at the signal

	WakeWaiters();

	m_cond_var.SignalAll();

	return Result::Ok;
}
''', r'''KernelSemaPrivate::Result KernelSemaPrivate::Signal(int signal_count) {
	std::vector<WaitingThread*>            wake;       // exp 0425 C3
	uint64_t                               target = 0; // exp 0425 C2
	std::shared_ptr<std::atomic<uint64_t>> resumed;    // exp 0425 C2
	{
		Common::LockGuard lock(m_mutex);

		if (m_status == Status::Deleted) {
			return Result::Deleted;
		}

		// Experiment 0405 "signal" (KYTY_BC5_SEMA_FIXES): a room check that cannot overflow (AnyPS5 Semaphore.cpp:64).
		if (Bc5SemaFix(BC5_SEMA_FIX_SIGNAL) && (signal_count <= 0 || m_count > m_max_count - signal_count)) {
			return Result::InvalCount;
		}
		if (m_count + signal_count > m_max_count) {
			return Result::InvalCount;
		}

		m_count += signal_count;
		bc5::load_stat::count(bc5::load_stat::kSemaSignal, m_waiting_threads.size()); // experiment 0415 (ls415): items = waiters present at the signal

		const uint64_t readied_before = m_bc5_readied;
		WakeWaiters();

		if (!m_bc5_direct) {
			m_cond_var.SignalAll();
		}
		wake.swap(m_bc5_wake);
		if (m_bc5_readied != readied_before && bc5_0425::HandoffUs() > 0) {
			target  = m_bc5_readied;
			resumed = m_bc5_resumed;
		}
	}
	Bc5WakeList(&wake); // exp 0425 C3: empty unless direct
	if (target != 0) {
		bc5_0425::Handoff(resumed, target, bc5_0425::HandoffUs()); // exp 0425 C2
	}

	return Result::Ok;
}
'''))

SEMA.append((r'''void KernelSemaPrivate::WakeWaiters() {
	for (auto* waiter: m_waiting_threads) {
		if (!waiter->ready && waiter->need_count <= m_count) {
			m_count -= waiter->need_count;
			waiter->result = Result::Ok;
			waiter->ready  = true;
		}
	}
}
''', r'''void KernelSemaPrivate::WakeWaiters() {
	for (auto* waiter: m_waiting_threads) {
		if (!waiter->ready && waiter->need_count <= m_count) {
			m_count -= waiter->need_count;
			Bc5Ready(waiter, Result::Ok); // exp 0425
		}
	}
}
'''))

SEMA.append((r'''	WaitingThread waiter {};
	waiter.id         = id;
	waiter.priority   = (m_fifo_order ? 0 : Libs::LibKernel::PthreadGetCurrentPriorityForKernel());
	waiter.need_count = need_count;
	AddWaiter(&waiter);

	while (!waiter.ready) {
		if ((elapsed >= micros && !infinitely)) {
			RemoveWaiter(&waiter);
			*ptr_micros = 0;
			return Result::TimedOut;
		}

		if (infinitely) {
			m_cond_var.WaitFor(&m_mutex, SIGNAL_APC_POLL_MICROS);
		} else {
			m_cond_var.WaitFor(&m_mutex, micros - elapsed);
		}

		m_mutex.Unlock();
		LibKernel::KernelDispatchPendingSignalForCurrentThread();
		m_mutex.Lock();

		elapsed = static_cast<uint32_t>(t.GetTimeS() * 1000000.0);
	}

	RemoveWaiter(&waiter);

	if (ptr_micros != nullptr) {
		*ptr_micros = (elapsed >= micros ? 0 : micros - elapsed);
	}

	return waiter.result;
}
''', r'''	WaitingThread waiter {};
	waiter.id         = id;
	waiter.priority   = (m_fifo_order ? 0 : Libs::LibKernel::PthreadGetCurrentPriorityForKernel());
	waiter.need_count = need_count;
#ifndef BC5_LEAN
	waiter.bc5_hi = bc5_0425::CatchOn() && bc5_0425::ThisThreadIsHi(); // exp 0425 catcher
#endif
	AddWaiter(&waiter);

	while (!waiter.ready) {
		if ((elapsed >= micros && !infinitely)) {
			RemoveWaiter(&waiter);
			*ptr_micros = 0;
			return Result::TimedOut;
		}

#ifdef __linux__
		if (m_bc5_direct) {
			// Experiment 0425 C3: sleep on this waiter's own word, without the semaphore's lock; a waker that set the
			// word before this point makes the futex return at once.
			const uint32_t slice = infinitely ? SIGNAL_APC_POLL_MICROS : micros - elapsed;
			m_mutex.Unlock();
			bc5_0425::FutexWait(&waiter.bc5_word, slice);
			LibKernel::KernelDispatchPendingSignalForCurrentThread();
			m_mutex.Lock();
			elapsed = static_cast<uint32_t>(t.GetTimeS() * 1000000.0);
			continue;
		}
#endif
		if (infinitely) {
			m_cond_var.WaitFor(&m_mutex, SIGNAL_APC_POLL_MICROS);
		} else {
			m_cond_var.WaitFor(&m_mutex, micros - elapsed);
		}

		m_mutex.Unlock();
		LibKernel::KernelDispatchPendingSignalForCurrentThread();
		m_mutex.Lock();

		elapsed = static_cast<uint32_t>(t.GetTimeS() * 1000000.0);
	}

	RemoveWaiter(&waiter);
	Bc5Resumed(&waiter); // exp 0425

	if (ptr_micros != nullptr) {
		*ptr_micros = (elapsed >= micros ? 0 : micros - elapsed);
	}

	// Experiment 0425 C3: the waker may still have to wake this waiter's word; it stores 0 after the wake, and it never
	// holds this semaphore's lock then (or, in the destructor, has already stored 0 before the lock reached us).
	while (waiter.bc5_waking.load(std::memory_order_acquire) != 0) {
#ifdef __linux__
		sched_yield();
#endif
	}

	return waiter.result;
}
'''))

# --------------------------------------------------------------------------------------------------- pthread.cpp
PTH = []
PTH.append((r'''static void Bc5ApplyGuestPriority(Pthread thread, const char* why) {
	if (thread == nullptr || thread->attr == nullptr || thread->host_thread_id == 0) {
		return;
	}
	const int nice = Bc5GuestNice(thread->attr->guest_priority);
	if (nice != 0 || why[0] == 's') { // a Setprio may also return a thread to 0
		SDL_LinuxSetThreadPriority(static_cast<Sint64>(thread->host_thread_id), nice);
	}
}
''', r'''// ---- experiment 0425 C1: KYTY_BC5_0425_WAKE_SLICE_US=<100..3000> -----------------------------------------------------
// The console schedules a title's threads by fixed priority, so a woken game thread on a free core runs at once
// (TODO(verify): no console measurement; the PS5 kernel is FreeBSD-derived). On this host the woken job workers
// arrived 0.7-1.4 ms after the owner's signal (F453, F454), at nice 0 beside the host's own threads. EEVDF lets a
// task request a shorter slice (sched_setattr, SCHED_OTHER with sched_runtime; Linux 6.12, clamped to 0.1-100 ms by
// the kernel, TODO(verify) on the box's 7.3 kernel: the read-back line below is the exposure), and a woken task with a
// shorter slice may preempt the running one (PREEMPT_SHORT). Applied at thread start and on Setprio to guest threads
// below the background band (guest priority < 733); the thread's policy and nice are kept as read.
struct Bc5SchedAttr {
	uint32_t size;
	uint32_t sched_policy;
	uint64_t sched_flags;
	int32_t  sched_nice;
	uint32_t sched_priority;
	uint64_t sched_runtime;
	uint64_t sched_deadline;
	uint64_t sched_period;
};
static_assert(sizeof(Bc5SchedAttr) == 48, "SCHED_ATTR_SIZE_VER0");

static int Bc5WakeSliceUs() {
	static const int v = [] {
		const char* e = std::getenv("KYTY_BC5_0425_WAKE_SLICE_US");
		int         us = 0;
		if (bc5::env_rule::on(e)) {
			char*      end = nullptr;
			const long x   = std::strtol(e, &end, 10);
			if (end != e && x > 0) {
				us = static_cast<int>(std::clamp(x, 100L, 3000L));
			}
		}
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0425: C1 wake slice %s (%d us)\n", us > 0 ? "ON" : "off", us);
#endif
		return us;
	}();
	return v;
}

static void Bc5ApplyWakeSlice(Pthread thread, const char* why) {
	const int us = Bc5WakeSliceUs();
	if (us == 0 || thread == nullptr || thread->attr == nullptr || thread->host_thread_id == 0 ||
	    thread->attr->guest_priority >= 733) {
		return;
	}
	const auto   tid = static_cast<pid_t>(thread->host_thread_id);
	Bc5SchedAttr cur {};
	const long   rc0 = syscall(SYS_sched_getattr, tid, &cur, static_cast<unsigned>(sizeof(cur)), 0u);
	long         rc1 = -1;
	int          err = 0;
	Bc5SchedAttr after {};
	if (rc0 == 0 && (cur.sched_policy == SCHED_OTHER || cur.sched_policy == SCHED_BATCH)) {
		Bc5SchedAttr a {};
		a.size          = sizeof(a);
		a.sched_policy  = cur.sched_policy;
		a.sched_nice    = cur.sched_nice;
		a.sched_runtime = static_cast<uint64_t>(us) * 1000u;
		rc1             = syscall(SYS_sched_setattr, tid, &a, 0u);
		err             = rc1 == 0 ? 0 : errno;
		syscall(SYS_sched_getattr, tid, &after, static_cast<unsigned>(sizeof(after)), 0u);
	}
#ifndef BC5_LEAN
	static std::atomic<int> logged {0};
	if (logged.fetch_add(1, std::memory_order_relaxed) < 256) {
		std::fprintf(stderr,
		             "[bc5] exp 0425 slice: %s tid %d '%s' prio %d policy %u nice %d: set rc %ld errno %d, read back runtime %llu ns nice %d\n",
		             why, static_cast<int>(tid), thread->name.c_str(), thread->attr->guest_priority, cur.sched_policy, cur.sched_nice, rc1,
		             err, static_cast<unsigned long long>(after.sched_runtime), after.sched_nice);
	}
#else
	(void)why;
	(void)err;
#endif
}
// ---- end of experiment 0425 C1 ------------------------------------------------------------------------------------

static void Bc5ApplyGuestPriority(Pthread thread, const char* why) {
	if (thread == nullptr || thread->attr == nullptr || thread->host_thread_id == 0) {
		return;
	}
	const int nice = Bc5GuestNice(thread->attr->guest_priority);
	if (nice != 0 || why[0] == 's') { // a Setprio may also return a thread to 0
		SDL_LinuxSetThreadPriority(static_cast<Sint64>(thread->host_thread_id), nice);
	}
	Bc5ApplyWakeSlice(thread, why); // experiment 0425 C1 (after the nice, which it keeps)
}
'''))

# ------------------------------------------------------------------------------------------------- gamePatch.cpp
GP = []
GP.append((r'''static uint64_t              g_bc5_jaf_base = 0;
static std::atomic<uint64_t> g_bc5_jaf_calls {0};
static std::atomic<uint64_t> g_bc5_jaf_wrapped {0};
using bc5_guest_block_fn = void (KYTY_SYSV_ABI*)(void* job, void* block, uint64_t size, uint32_t n1);
''', r'''static uint64_t              g_bc5_jaf_base = 0;
static std::atomic<uint64_t> g_bc5_jaf_calls {0};
static std::atomic<uint64_t> g_bc5_jaf_wrapped {0};
using bc5_guest_block_fn = void (KYTY_SYSV_ABI*)(void* job, void* block, uint64_t size, uint32_t n1);
#ifndef BC5_LEAN
// ---- experiment 0425's catcher (normal build only), KYTY_BC5_0425_CATCH=1 ------------------------------------------
// At each owner help call through the hook (thread index -1): is a "Job Hi" waiter readied by a signal and not yet
// running again (kernel/semaphore.cpp)? Counted for all owner calls and for those whose block function is F449's
// crash job function +0x4661e50 (TODO(verify): that the job's +0x80 holds it; a crashing run with 0 such calls says
// it does not). Limits (R11): the pending count is global, not paired with this job's push or with a semaphore; a
// Hi waiter pending says a woken worker had not yet run, not that it would have taken this job.
// With JobArenaFix off the hook is installed as a pass-through: it calls the title's function unchanged.
extern "C" int                bc5_0425_hi_pending();
extern "C" unsigned long long bc5_0425_hi_marked();
static bool                   g_bc5_0425_catch       = false;
static bool                   g_bc5_jaf_passthrough  = false;
static std::atomic<uint64_t>  g_bc5_0425_owner {0};
static std::atomic<uint64_t>  g_bc5_0425_owner_hi {0};
static std::atomic<uint64_t>  g_bc5_0425_target {0};
static std::atomic<uint64_t>  g_bc5_0425_target_hi {0};
static void Bc5CatchOwnerCall(uint64_t base, bc5_guest_block_fn fn, int32_t index) {
	if (index != -1) {
		return;
	}
	const bool     target  = reinterpret_cast<uint64_t>(fn) == base + 0x4661e50;
	const int      pending = bc5_0425_hi_pending();
	const uint64_t n       = g_bc5_0425_owner.fetch_add(1, std::memory_order_relaxed) + 1;
	const uint64_t nh      = pending > 0 ? g_bc5_0425_owner_hi.fetch_add(1, std::memory_order_relaxed) + 1 : g_bc5_0425_owner_hi.load(std::memory_order_relaxed);
	uint64_t       t       = g_bc5_0425_target.load(std::memory_order_relaxed);
	uint64_t       th      = g_bc5_0425_target_hi.load(std::memory_order_relaxed);
	if (target) {
		t = g_bc5_0425_target.fetch_add(1, std::memory_order_relaxed) + 1;
		if (pending > 0) {
			th = g_bc5_0425_target_hi.fetch_add(1, std::memory_order_relaxed) + 1;
		}
	}
	if (target && (t <= 200 || t % 100 == 0)) {
		std::fprintf(stderr,
		             "[bc5] exp 0425 catch: owner takes crash-type job #%llu, Hi readied-not-running %d (owner calls %llu, with Hi pending %llu; crash-type with Hi pending %llu; Hi readied %llu)\n",
		             static_cast<unsigned long long>(t), pending, static_cast<unsigned long long>(n), static_cast<unsigned long long>(nh),
		             static_cast<unsigned long long>(th), bc5_0425_hi_marked());
	}
	if (n == 1) {
		char tn[16] = {};
#ifdef __linux__
		pthread_getname_np(pthread_self(), tn, sizeof(tn));
#endif
		std::fprintf(stderr, "[bc5] exp 0425 catch: the owner's first help call is on '%s'\n", tn);
	}
	if (n == 1 || n % 2000 == 0) {
		std::fprintf(stderr,
		             "[bc5] exp 0425 catch sum: owner calls %llu, with Hi pending %llu; crash-type %llu, with Hi pending %llu; Hi readied %llu\n",
		             static_cast<unsigned long long>(n), static_cast<unsigned long long>(nh), static_cast<unsigned long long>(t),
		             static_cast<unsigned long long>(th), bc5_0425_hi_marked());
	}
}
// ---- end of experiment 0425's catcher -----------------------------------------------------------------------------
#else
static constexpr bool g_bc5_jaf_passthrough = false;
#endif
'''))

GP.append((r'''	const int32_t  old_index = *index;
	const uint64_t old_slot  = *slot;
	const bool     wrap      = wrap_needed(old_index);
''', r'''	const int32_t  old_index = *index;
	const uint64_t old_slot  = *slot;
	const bool     wrap      = !g_bc5_jaf_passthrough && wrap_needed(old_index); // exp 0425: no window in pass-through
#ifndef BC5_LEAN
	if (g_bc5_0425_catch) {
		Bc5CatchOwnerCall(base, fn, old_index); // exp 0425 catcher
	}
#endif
'''))

GP.append((r'''	std::fprintf(stderr, "game fix (temporary, exp 0359): job-arena fix %s for %s (%s)\n", on ? "ON" : "OFF", title.c_str(), src);
	if (!on) return false;
''', r'''	std::fprintf(stderr, "game fix (temporary, exp 0359): job-arena fix %s for %s (%s)\n", on ? "ON" : "OFF", title.c_str(), src);
#ifndef BC5_LEAN
	// Experiment 0425's catcher: with the fix off, the same hook is installed as a pass-through (no window).
	g_bc5_0425_catch = bc5::env_rule::on(std::getenv("KYTY_BC5_0425_CATCH"));
	std::fprintf(stderr, "[bc5] exp 0425: catcher %s\n", g_bc5_0425_catch ? "ON" : "off");
	g_bc5_jaf_passthrough = !on && g_bc5_0425_catch;
	if (!on && !g_bc5_jaf_passthrough) return false;
#else
	if (!on) return false;
#endif
'''))

GP.append((r'''	std::fprintf(stderr, "game fix: job-arena fix APPLIED: site +0x%" PRIx64 " -> slot +0x%" PRIx64 " -> host hook %p (temporary; input.cfg JobArenaFix.%s=off turns it off)\n",
	             kSiteOffset, kSlotOffset, reinterpret_cast<void*>(hook), kTitleId);
	return true;
}
''', r'''	if (g_bc5_jaf_passthrough) {
		std::fprintf(stderr, "game fix: job-arena hook PASS-THROUGH for exp 0425's catcher: site +0x%" PRIx64 " -> slot +0x%" PRIx64 " -> host hook %p; the fix is OFF, the title's call is unchanged\n",
		             kSiteOffset, kSlotOffset, reinterpret_cast<void*>(hook));
		return false;
	}
	std::fprintf(stderr, "game fix: job-arena fix APPLIED: site +0x%" PRIx64 " -> slot +0x%" PRIx64 " -> host hook %p (temporary; input.cfg JobArenaFix.%s=off turns it off)\n",
	             kSiteOffset, kSlotOffset, reinterpret_cast<void*>(hook), kTitleId);
	return true;
}
'''))

GP.append((r'''#include "bc5/job_arena_fix.hpp" // BC5 (experiment 0359)
''', r'''#include "bc5/job_arena_fix.hpp" // BC5 (experiment 0359)
#include "bc5/env_rule.hpp"      // BC5 (experiment 0425): the switch rule
#include <cstdlib>               // experiment 0425: std::getenv
#ifdef __linux__
#include <pthread.h> // experiment 0425 catcher: the owner's thread name
#endif
'''))

# ------------------------------------------------------------------------------------------------- libPlayGo.cpp
# The PlayGo lead (exp 0425's regression hunt): the first crash at the site came 23 min after exp 0298's PlayGo answers
# were integrated (e62a97c6, 2026-10-25 10:03 -> 10:27:41). Switches on those answers, and a call counter.
PG = []
PG.append((r'''#include <algorithm>
#include <atomic>
#include <cstdarg>
#include <cstdio>
''', r'''#include <algorithm>
#include <atomic>
#include <cstdarg>
#include <cstdio>
#include <chrono>  // experiment 0425
#include <cstdlib> // experiment 0425
#include <cstring> // experiment 0425
#include <thread>  // experiment 0425
#include "bc5/env_rule.hpp" // experiment 0425
#ifdef __linux__
#include <pthread.h> // experiment 0425 catcher: the calling thread's name
#endif
'''))
PG.append((r'''static uint32_t g_chunks_num = 0;
''', r'''static uint32_t g_chunks_num = 0;

// ---- experiment 0425: the PlayGo answers as switches (all unset = exp 0298's answers) --------------------------------
// What the PS5 answers for a fully installed title is not public: TODO(verify) on a console for each of these. The open
// emulators all answer as exp 0298 does: "local fast" for every installed chunk (AnyPS5 27c88a8
// core/libs/prx/libScePlayGo/Export.cpp:180, shadPS4 60c42b9 src/core/libraries/playgo/playgo.cpp:162), Prefetch OK at
// once (Export.cpp:230, playgo.cpp:290-315), ETA 0; all synchronously on the calling thread. On the console libScePlayGo
// is a user library over the system's PlayGo service, so a call may well take IPC time (TODO(verify)).
//   KYTY_BC5_0425_PLAYGO_LOCUS=slow       P1: GetLocus answers "local slow" (2) for every valid chunk
//   KYTY_BC5_0425_PLAYGO_PREFETCH_MS=<n>  P2: Prefetch blocks the caller n ms (1..5000) before its OK
//   KYTY_BC5_0425_PLAYGO_CALL_US=<n>      P3: every PlayGo call blocks the caller n us (1..20000) before it answers
//   KYTY_BC5_0425_CATCH=1                 catcher (normal build only): every call up to 3000 lines in all, then each
//                                         kind's every 1000th, with the calling thread's name (its place among the log's
//                                         fps counter lines dates it)
namespace bc5_0425pg {
static long ReadNum(const char* name, long lo, long hi) {
	const char* e = std::getenv(name);
	if (!bc5::env_rule::on(e)) {
		return 0;
	}
	char*      end = nullptr;
	const long v   = std::strtol(e, &end, 10);
	return (end == e || v <= 0) ? 0 : std::clamp(v, lo, hi);
}
static bool LocusSlow() {
	static const bool v = [] {
		const char* e  = std::getenv("KYTY_BC5_0425_PLAYGO_LOCUS");
		const bool  on = e != nullptr && std::strcmp(e, "slow") == 0;
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0425: P1 locus %s\n", on ? "SLOW ON" : "off (local fast)");
#endif
		return on;
	}();
	return v;
}
static long PrefetchMs() {
	static const long v = [] {
		const long ms = ReadNum("KYTY_BC5_0425_PLAYGO_PREFETCH_MS", 1, 5000);
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0425: P2 prefetch delay %s (%ld ms)\n", ms > 0 ? "ON" : "off", ms);
#endif
		return ms;
	}();
	return v;
}
static long CallUs() {
	static const long v = [] {
		const long us = ReadNum("KYTY_BC5_0425_PLAYGO_CALL_US", 1, 20000);
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0425: P3 call cost %s (%ld us)\n", us > 0 ? "ON" : "off", us);
#endif
		return us;
	}();
	return v;
}
#ifndef BC5_LEAN
static bool CatchOn() {
	static const bool v = bc5::env_rule::on(std::getenv("KYTY_BC5_0425_CATCH"));
	return v;
}
static void Count(const char* fn, std::atomic<uint64_t>& n) {
	const uint64_t k = n.fetch_add(1, std::memory_order_relaxed) + 1;
	static std::atomic<int> lines {0}; // every call while under 3000 lines in all, then each kind's every 1000th
	if (k == 1 || k % 1000 == 0 || lines.fetch_add(1, std::memory_order_relaxed) < 3000) {
		char name[16] = {};
#ifdef __linux__
		pthread_getname_np(pthread_self(), name, sizeof(name));
#endif
		std::fprintf(stderr, "[bc5] exp 0425 playgo: %s call #%llu on '%s'\n", fn, static_cast<unsigned long long>(k), name);
	}
}
#endif
// At every PlayGo entry: the catcher's count, then P3's cost.
#ifndef BC5_LEAN
#define BC5_0425_PG_ENTER(fn)                                    \
	do {                                                         \
		static std::atomic<uint64_t> bc5_0425_n {0};               \
		if (bc5_0425pg::CatchOn()) bc5_0425pg::Count(fn, bc5_0425_n); \
		bc5_0425pg::Cost();                                       \
	} while (0)
#else
#define BC5_0425_PG_ENTER(fn) bc5_0425pg::Cost()
#endif
static void Cost() {
	const long us = CallUs();
	if (us > 0) {
		std::this_thread::sleep_for(std::chrono::microseconds(us));
	}
}
} // namespace bc5_0425pg
// ---- end of experiment 0425's PlayGo block -------------------------------------------------------------------------
'''))
PG.append((r'''	BC5_PG("%s\n", __func__);
''', r'''	BC5_PG("%s\n", __func__);
	BC5_0425_PG_ENTER(__func__); // experiment 0425
''', 18))
PG.append((r'''			out_loci[i] = PLAYGO_LOCUS_LOCAL_FAST;
			BC5_PG("GetLocus chunk %u: local fast\n", static_cast<unsigned>(chunk_ids[i]));''',
           r'''			out_loci[i] = bc5_0425pg::LocusSlow() ? PLAYGO_LOCUS_LOCAL_SLOW : PLAYGO_LOCUS_LOCAL_FAST; // experiment 0425 P1
			BC5_PG("GetLocus chunk %u: %s\n", static_cast<unsigned>(chunk_ids[i]), out_loci[i] == PLAYGO_LOCUS_LOCAL_SLOW ? "local slow" : "local fast");'''))
PG.append((r'''	for (uint32_t i = 0; i < number_of_entries; i++) {
		if (!is_valid_chunk(chunk_ids[i])) {
			return PLAYGO_ERROR_BAD_CHUNK_ID;
		}
	}

	return OK;
}

int KYTY_SYSV_ABI PlayGoGetEta(''', r'''	for (uint32_t i = 0; i < number_of_entries; i++) {
		if (!is_valid_chunk(chunk_ids[i])) {
			return PLAYGO_ERROR_BAD_CHUNK_ID;
		}
	}
	if (const long ms = bc5_0425pg::PrefetchMs(); ms > 0) { // experiment 0425 P2
		std::this_thread::sleep_for(std::chrono::milliseconds(ms));
	}

	return OK;
}

int KYTY_SYSV_ABI PlayGoGetEta('''))

UNITS = [('src/kernel/semaphore.cpp', SEMA), ('src/kernel/pthread.cpp', PTH), ('src/loader/gamePatch.cpp', GP),
         ('src/libs/libPlayGo.cpp', PG)]


def main():
    if len(sys.argv) != 2:
        sys.exit('usage: patch0425.py <tree>')
    tree = sys.argv[1]
    for rel, edits in UNITS:
        path = tree + '/' + rel
        raw = open(path, 'rb').read()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != PINS[rel]:
            sys.exit('0425 PATCH STOP: %s is %s, not the pin %s' % (rel, digest, PINS[rel]))
        crlf = b'\r\n' in raw
        text = raw.decode('utf-8').replace('\r\n', '\n')
        for i, edit in enumerate(edits):
            old, new = edit[0], edit[1]
            want = edit[2] if len(edit) > 2 else 1
            n = text.count(old)
            if n != want:
                sys.exit('0425 PATCH STOP: %s edit %d anchor found %d times, want %d' % (rel, i + 1, n, want))
            text = text.replace(old, new)
        out = text.replace('\n', '\r\n') if crlf else text
        open(path, 'wb').write(out.encode('utf-8'))
        print('patched %s: %d edits, %s, sha256 %s' % (rel, len(edits), 'CRLF' if crlf else 'LF',
                                                       hashlib.sha256(out.encode('utf-8')).hexdigest()))
    print('patch0425: done')


if __name__ == '__main__':
    main()
