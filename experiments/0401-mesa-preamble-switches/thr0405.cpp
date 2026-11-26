// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e5, exp 0405's thread synchronisation and semaphore ports (mkthr0405.py,
// thr0405-notes.md): the CPU test of src/kernel/pthread.cpp (KYTY_BC5_THREAD_SYNC_FIXES: kk06, kk03, signalto, x87,
// kk07) and src/kernel/semaphore.cpp (KYTY_BC5_SEMA_FIXES: attr, signal), with real host threads and real guest threads
// (PthreadCreate, so RunThread's start path runs). Run on the box, in the build container, from a fresh directory:
//   KYTY_BC5_THREAD_SYNC_FIXES=1 KYTY_BC5_SEMA_FIXES=1 thr0405 on
//   KYTY_BC5_THREAD_SYNC_FIXES=0 KYTY_BC5_SEMA_FIXES=0 thr0405 off      (both unset: off too)
// The program reads both switches itself, as the units do (a comma list turns on only the parts it names; the mode is
// then "part"); the argument, when given, must name the mode the switches give. One line per case, then exactly
// "thr0405: on N of N; end" or "thr0405: off N of N; end"; exit 0 only then (1: a case failed, 2: setup or argument,
// 3: the watchdog, which ends a hang after 120 s with a FAIL line naming the case). Nothing is written to disk.
// The units print "[bc5] exp 0405: thread sync on (items: ...)|off" (at the Pthread init) and "[bc5] exp 0405: sema
// on (items: ...)|off" (at the first semaphore call) on stderr.
// Cases (thr0405-notes.md has the reasons):
//   1 kk06 wake-ups, objects kept until both threads are done: 8 pairs x 1000 rounds, signal / broadcast / signalto,
//     before and after the mutex unlock, untimed and timed waits, mutex types 1 and 4: every wake arrives (on and off)
//   2 kk06 destroy at once: the same, but the waiter destroys the mutex and the condition variable and frees (after
//     poisoning) the memory that holds their handles as soon as its wait returns: 8 x 1500 rounds, no crash, no error.
//     Only with kk06 on; off it is not run (today's notify after the unlock touches freed memory then: crash-prone)
//   3 kk03 statically initialised rwlock and condition variable: on, Destroy OK without creating, the timed locks
//     create it on first use; off, those calls stop the emulator (EXIT): not run; both: Tryrdlock creates one (exp 0336)
//   4 signalto answers: null thread EINVAL; a waiting thread is woken alone (OK); a handle that is no thread, the
//     caller, a live guest thread, a finished guest thread, a joined guest thread: on ESRCH, EPERM, EPERM, ESRCH, ESRCH;
//     off OK for all five (today's)
//   5 x87: the creator loads 0x027f and creates a guest thread: on, the thread starts with 0x037f; off, with 0x027f
//     (inherited, today's); both: the creator keeps 0x027f, the thread's MXCSR is the creator's
//   6 kk07: Getprio, Setprio, Cancel of a joined guest thread: on ESRCH; off not run (they use the reaped host thread);
//     both: Getprio of a live guest thread is OK, 700
//   7 sema attr: 0, 1, 2 OK; 3, 0x103, 0x104, 0x200, 0x1000, 0xffffffff EINVAL; 0x100-0x102: on OK and working, off EINVAL
//   8 sema signal: on, 0, -1 and INT_MAX give EINVAL and leave the count; off, 0 and -1 are OK and -1 lowers the count
//     (today's; INT_MAX's wrapped arithmetic is recorded, not checked); both: the room check at the maximum
//   9 sema poll (already EINVAL for 0, -1 and above the maximum) and a blocked wait woken by a signal, on and off
// Build (box0401's build0401.py, series e5): this file compiled with src/kernel/pthread.cpp's compile command
// (--gate thr0405.cpp <out> --like src/kernel/pthread.cpp) and linked with every emulator object but main.cpp.o, the
// private pthread.cpp.o and semaphore.cpp.o (mkthr0405.py's outputs) in place of the shared ones.
// Runtime state it sets up (as pth0401.cpp, plus the RuntimeLinker singleton): the Threads subsystem's main thread, the
// Pthread subsystem and the RuntimeLinker singleton are made on a helper thread that then ends (their constructors
// check for the main thread; PRINT_NAME stays off on every other thread; a guest thread's end asks the RuntimeLinker
// to drop its TLS, and a static object's creation asks it for the owning program: none). Logging off. Every host
// thread that calls the pthread code first gets its own PthreadPrivate (PthreadInitSelfForMainThread). Guest threads
// get their stacks from this test (PthreadAttrSetstack), so the Memory subsystem is not needed, and are created on a
// host thread of their own that then ends: PthreadCreate turns PRINT_NAME on for its caller, and PRINT_NAME needs the
// log subsystem. Guest signals are never raised.

#include "common/logging/log.h"
#include "common/singleton.h"
#include "common/threads.h"
#include "kernel/pthread.h"
#include "kernel/semaphore.h"
#include "libs/errno.h"
#include "loader/runtimeLinker.h"

#include <atomic>
#include <chrono>
#include <climits>
#include <condition_variable>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include <unistd.h>

namespace {

namespace LK = Libs::LibKernel;
namespace SM = Libs::LibKernel::Semaphore;
using Clock  = std::chrono::steady_clock;

constexpr int kWatchdogSeconds = 120;

constexpr uint32_t kKk06     = 1u;
constexpr uint32_t kKk03     = 2u;
constexpr uint32_t kSignalto = 4u;
constexpr uint32_t kX87      = 8u;
constexpr uint32_t kKk07     = 16u;
constexpr uint32_t kThrAll   = 31u;
constexpr uint32_t kAttr     = 1u;
constexpr uint32_t kSignal   = 2u;
constexpr uint32_t kSemaAll  = 3u;

uint32_t                 g_thr  = 0; // the parts of KYTY_BC5_THREAD_SYNC_FIXES that are on, read as the unit reads them
uint32_t                 g_sema = 0; // the parts of KYTY_BC5_SEMA_FIXES
std::atomic<int>         g_cases {0};
std::atomic<int>         g_passed {0};
std::atomic<const char*> g_case {"start"};
std::atomic<bool>        g_finished {false};

bool ThrOn(uint32_t part) {
	return (g_thr & part) != 0;
}

bool SemaOn(uint32_t part) {
	return (g_sema & part) != 0;
}

// The units' reading of a switch: unset, empty or "0" is off; a comma list of known names turns on only those; any
// other value turns all on.
uint32_t ParseParts(const char* e, const char* const* names, const uint32_t* bits, int count, uint32_t all) {
	if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
		return 0;
	}
	uint32_t    parts = 0;
	const char* p     = e;
	for (;;) {
		const char*  comma = std::strchr(p, ',');
		const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
		for (int k = 0; k < count; k++) {
			if (std::strlen(names[k]) == n && std::strncmp(p, names[k], n) == 0) {
				parts |= bits[k];
			}
		}
		if (comma == nullptr) {
			break;
		}
		p = comma + 1;
	}
	return parts != 0 ? parts : all;
}

long long UsSince(Clock::time_point t0) {
	return std::chrono::duration_cast<std::chrono::microseconds>(Clock::now() - t0).count();
}

const char* ErrName(int r) {
	switch (r) {
		case OK: return "OK";
		case LK::KERNEL_ERROR_EBUSY: return "EBUSY";
		case LK::KERNEL_ERROR_ETIMEDOUT: return "ETIMEDOUT";
		case LK::KERNEL_ERROR_EPERM: return "EPERM";
		case LK::KERNEL_ERROR_ESRCH: return "ESRCH";
		case LK::KERNEL_ERROR_EDEADLK: return "EDEADLK";
		case LK::KERNEL_ERROR_EINVAL: return "EINVAL";
		case LK::KERNEL_ERROR_EACCES: return "EACCES";
		case -1: return "not run";
		case -3: return "test: waiter waited too long for the signaller";
		case -4: return "test: signaller found no round";
		case -5: return "test: waiter not waiting";
		default: return "other";
	}
}

std::string Fmt(const char* format, ...) __attribute__((format(printf, 1, 2)));
std::string Fmt(const char* format, ...) {
	char    buf[1536];
	va_list args;
	va_start(args, format);
	std::vsnprintf(buf, sizeof(buf), format, args);
	va_end(args);
	return buf;
}

void Report(const char* name, bool ok, const std::string& info) {
	g_cases++;
	if (ok) {
		g_passed++;
	}
	std::printf("thr0405: case %d %s: %s (%s)\n", g_cases.load(), name, ok ? "ok" : "FAIL", info.c_str());
	std::fflush(stdout);
}

[[noreturn]] void SetupFail(const char* what) {
	std::printf("thr0405: FAIL setup: %s\n", what);
	std::fflush(stdout);
	_exit(2);
}

void Watchdog() {
	const auto start = Clock::now();
	while (!g_finished.load()) {
		std::this_thread::sleep_for(std::chrono::milliseconds(50));
		if (Clock::now() - start > std::chrono::seconds(kWatchdogSeconds)) {
			std::printf("thr0405: FAIL watchdog: case \"%s\" still running after %d s (a hang); %d of %d cases passed before it\n",
			            g_case.load(), kWatchdogSeconds, g_passed.load(), g_cases.load());
			std::fflush(stdout);
			_exit(3);
		}
	}
}

// A host thread that is a guest thread for the pthread code (g_pthread_self set, as for the emulator's main thread).
template <class F>
std::thread Spawn(F f) {
	return std::thread([f]() mutable {
		LK::PthreadInitSelfForMainThread();
		f();
	});
}

// A host-side one-shot flag (std primitives, not the code under test), with a bounded wait.
struct Flag {
	std::mutex              m;
	std::condition_variable cv;
	bool                    set = false;
	void                    Set() {
		{
			std::lock_guard<std::mutex> lock(m);
			set = true;
		}
		cv.notify_all();
	}
	bool Wait(int ms) {
		std::unique_lock<std::mutex> lock(m);
		return cv.wait_for(lock, std::chrono::milliseconds(ms), [this] { return set; });
	}
};

void NoteMax(std::atomic<long long>& peak, long long v) {
	long long seen = peak.load();
	while (v > seen && !peak.compare_exchange_weak(seen, v)) {
	}
}

bool WaitUntil(const std::atomic<int>& v, int want, int ms) {
	const auto t0 = Clock::now();
	while (v.load() != want) {
		if (Clock::now() - t0 > std::chrono::milliseconds(ms)) {
			return false;
		}
		std::this_thread::sleep_for(std::chrono::microseconds(200));
	}
	return true;
}

LK::PthreadMutex NewMutex(const char* name, int type, int protocol) {
	LK::PthreadMutexattr attr = nullptr;
	if (LK::PthreadMutexattrInit(&attr) != OK || LK::PthreadMutexattrSettype(&attr, type) != OK ||
	    LK::PthreadMutexattrSetprotocol(&attr, protocol) != OK) {
		SetupFail(name);
	}
	LK::PthreadMutex m = nullptr;
	if (LK::PthreadMutexInit(&m, &attr, name) != OK || m == nullptr) {
		SetupFail(name);
	}
	LK::PthreadMutexattrDestroy(&attr);
	return m;
}

LK::PthreadCond NewCond(const char* name) {
	LK::PthreadCond c = nullptr;
	if (LK::PthreadCondInit(&c, nullptr, name) != OK || c == nullptr) {
		SetupFail(name);
	}
	return c;
}

// ---- guest threads ---------------------------------------------------------------------------------------------------
constexpr size_t kGuestStack = 0x40000;

struct GuestThread {
	LK::Pthread handle = nullptr;
	void*       stack  = nullptr;
};

// Creates a guest thread through PthreadCreate, on a host thread of its own (PthreadCreate turns PRINT_NAME on for its
// caller). The guest stack is this test's memory. fpu_cw, when not 0: the x87 control word the creating thread loads
// first; *creator_cw / *creator_mxcsr get the creating thread's words after the create.
bool CreateGuest(GuestThread* g, LK::pthread_entry_func_t entry, void* arg, const char* name, uint16_t fpu_cw = 0,
                 uint16_t* creator_cw = nullptr, uint32_t* creator_mxcsr = nullptr) {
	g->stack = std::malloc(kGuestStack); // RunThread aligns the stack top itself
	if (g->stack == nullptr) {
		return false;
	}
	int         r = -1;
	std::thread creator([g, entry, arg, name, fpu_cw, creator_cw, creator_mxcsr, &r] {
		if (fpu_cw != 0) {
			const uint16_t cw = fpu_cw;
			asm volatile("fldcw %0" : : "m"(cw));
		}
		LK::PthreadAttr attr = nullptr;
		if (LK::PthreadAttrInit(&attr) != OK || LK::PthreadAttrSetstack(&attr, g->stack, kGuestStack) != OK) {
			r = -2;
			return;
		}
		r = LK::PthreadCreate(&g->handle, &attr, entry, arg, name);
		uint16_t cw = 0;
		uint32_t mx = 0;
		asm volatile("fnstcw %0" : "=m"(cw));
		asm volatile("stmxcsr %0" : "=m"(mx));
		if (creator_cw != nullptr) {
			*creator_cw = cw;
		}
		if (creator_mxcsr != nullptr) {
			*creator_mxcsr = mx;
		}
		LK::PthreadAttrDestroy(&attr);
	});
	creator.join();
	return r == OK && g->handle != nullptr;
}

int JoinGuest(GuestThread* g) {
	const int r = LK::PthreadJoin(g->handle, nullptr);
	if (r == OK) {
		std::free(g->stack);
		g->stack = nullptr;
	}
	return r;
}

// A guest thread that says it runs, waits for its release (10 s at most), says it ends, and returns.
struct GuestBlock {
	std::atomic<int> state {0};
	Flag             release;
};

KYTY_SYSV_ABI void* GuestBlockEntry(void* arg) {
	auto* b  = static_cast<GuestBlock*>(arg);
	b->state = 1;
	b->release.Wait(10000);
	b->state = 2;
	return nullptr;
}

// A guest thread that reads its x87 control word and MXCSR first thing.
struct FpuSeen {
	std::atomic<int> done {0};
	uint16_t         cw    = 0;
	uint32_t         mxcsr = 0;
};

KYTY_SYSV_ABI void* GuestFpuEntry(void* arg) {
	auto*    f  = static_cast<FpuSeen*>(arg);
	uint16_t cw = 0;
	uint32_t mx = 0;
	asm volatile("fnstcw %0" : "=m"(cw));
	asm volatile("stmxcsr %0" : "=m"(mx));
	f->cw    = cw;
	f->mxcsr = mx;
	f->done  = 1;
	return nullptr;
}

// ---- 1, 2: kk06 ------------------------------------------------------------------------------------------------------
struct Shared {
	LK::PthreadMutex m       = nullptr;
	LK::PthreadCond  c       = nullptr;
	LK::Pthread      waiter  = nullptr;
	bool             waiting = false; // under m
	bool             flag    = false; // under m
};

struct PairStats {
	std::atomic<int>       rounds {0};
	std::atomic<int>       errors {0};
	std::atomic<int>       first {0};
	std::atomic<long long> max_us {0};
	void                   Note(int got) {
		if (got != OK) {
			errors++;
			int none = 0;
			first.compare_exchange_strong(none, got);
		}
	}
};

struct Pair {
	std::atomic<Shared*> slot {nullptr};
	std::atomic<int>     x_done {-1};
};

// Each pair: a waiter W makes a mutex and a condition variable per round, locks, marks itself waiting and waits for the
// flag; the signaller X takes the round, locks (W is inside its wait then: it released the mutex only there), sets the
// flag and wakes W by signal, broadcast or signalto, under the mutex or after its unlock. waiter_destroys: W destroys
// both objects and frees (after poisoning) the memory holding their handles as soon as its wait returned, the POSIX
// pattern; otherwise only after X's calls returned.
void RunPairs(int pairs, int rounds, bool waiter_destroys, PairStats* st) {
	std::vector<Pair>        pv(static_cast<size_t>(pairs));
	std::vector<std::thread> threads;
	for (int i = 0; i < pairs; i++) {
		Pair* pr = &pv[static_cast<size_t>(i)];
		threads.push_back(Spawn([st, pr, i, rounds, waiter_destroys] {
			for (int r = 0; r < rounds; r++) {
				auto* s = new Shared;
				s->m    = NewMutex("thr0405-kk06", (r + i) % 3 == 2 ? 4 : 1, 0);
				s->c    = NewCond("thr0405-kk06");
				const bool timed = ((r / 6) % 2) == 1;
				const auto t0    = Clock::now();
				st->Note(LK::PthreadMutexLock(&s->m));
				s->waiting = true;
				s->waiter  = LK::PthreadSelf();
				pr->slot.store(s);
				while (!s->flag) {
					const int g = timed ? LK::PthreadCondTimedwait(&s->c, &s->m, 10000000) : LK::PthreadCondWait(&s->c, &s->m);
					if (g != OK) {
						st->Note(g);
						break;
					}
				}
				NoteMax(st->max_us, UsSince(t0));
				st->Note(LK::PthreadMutexUnlock(&s->m));
				if (!waiter_destroys) {
					const auto w0 = Clock::now();
					while (pr->x_done.load() < r) {
						if (Clock::now() - w0 > std::chrono::seconds(10)) {
							st->Note(-3);
							break;
						}
						std::this_thread::yield();
					}
				}
				st->Note(LK::PthreadCondDestroy(&s->c));
				st->Note(LK::PthreadMutexDestroy(&s->m));
				std::memset(static_cast<void*>(s), 0xA5, sizeof(Shared)); // a stale read of a handle now faults
				delete s;
				st->rounds++;
			}
		}));
		threads.push_back(Spawn([st, pr, i, rounds] {
			for (int r = 0; r < rounds; r++) {
				Shared*    s  = nullptr;
				const auto t0 = Clock::now();
				while ((s = pr->slot.exchange(nullptr)) == nullptr) {
					if (Clock::now() - t0 > std::chrono::seconds(10)) {
						st->Note(-4);
						return;
					}
					std::this_thread::yield();
				}
				const int v = (r + i) % 6;
				st->Note(LK::PthreadMutexLock(&s->m));
				if (!s->waiting) {
					st->Note(-5);
				}
				s->flag             = true;
				const LK::Pthread w = s->waiter;
				if (v >= 3) { // under the mutex: W can return only after this thread's unlock
					st->Note(v == 3 ? LK::PthreadCondSignal(&s->c)
					                : (v == 4 ? LK::PthreadCondBroadcast(&s->c) : LK::PthreadCondSignalto(&s->c, w)));
					st->Note(LK::PthreadMutexUnlock(&s->m));
				} else { // after the unlock: W is still registered and waits for this wake
					st->Note(LK::PthreadMutexUnlock(&s->m));
					st->Note(v == 0 ? LK::PthreadCondSignal(&s->c)
					                : (v == 1 ? LK::PthreadCondBroadcast(&s->c) : LK::PthreadCondSignalto(&s->c, w)));
				}
				pr->x_done.store(r); // with waiter_destroys, s may be gone now: not touched again
			}
		}));
	}
	for (auto& t: threads) {
		t.join();
	}
}

void CaseKk06Wakeups() {
	g_case = "kk06 wake-ups, objects kept";
	constexpr int kPairs = 8, kRounds = 1000;
	PairStats     st;
	const auto    t0 = Clock::now();
	RunPairs(kPairs, kRounds, false, &st);
	const bool ok = st.rounds.load() == kPairs * kRounds && st.errors.load() == 0 && st.max_us.load() < 10000000;
	Report("kk06 wake-ups, objects kept until both threads are done", ok,
	       Fmt("kk06 %s; %d of %d rounds (signal, broadcast, signalto; under the mutex and after its unlock; untimed and "
	           "timed waits; mutex types 1 and 4) in %lld ms, errors %d (first %s), longest round %lld us",
	           ThrOn(kKk06) ? "on" : "off", st.rounds.load(), kPairs * kRounds, UsSince(t0) / 1000, st.errors.load(),
	           ErrName(st.first.load()), st.max_us.load()));
}

void CaseKk06Destroy() {
	g_case = "kk06 destroy at once";
	if (!ThrOn(kKk06)) {
		Report("kk06 waiter destroys and frees at once", true,
		       "not run, kk06 off: today's signal and broadcast read the condition variable's handle and a mutex unlock "
		       "notifies after releasing the internal lock; a woken waiter that destroys and frees first makes that a "
		       "use-after-free (a crash once the handle reads NULL or poison): crash-prone, skipped");
		return;
	}
	constexpr int kPairs = 8, kRounds = 1500;
	PairStats     st;
	const auto    t0 = Clock::now();
	RunPairs(kPairs, kRounds, true, &st);
	const bool ok = st.rounds.load() == kPairs * kRounds && st.errors.load() == 0 && st.max_us.load() < 10000000;
	Report("kk06 waiter destroys and frees at once", ok,
	       Fmt("kk06 on; %d of %d rounds, each mutex and condition variable destroyed and its memory poisoned and freed as "
	           "soon as the wait returned, in %lld ms; errors %d (first %s), longest round %lld us; no crash",
	           st.rounds.load(), kPairs * kRounds, UsSince(t0) / 1000, st.errors.load(), ErrName(st.first.load()),
	           st.max_us.load()));
}

// ---- 3: kk03 ---------------------------------------------------------------------------------------------------------
void CaseKk03() {
	g_case = "kk03 statically initialised objects";
	// Both: Tryrdlock creates a static lock (exp 0336), the lock works and is destroyed.
	LK::PthreadRwlock t   = nullptr;
	const int         tr  = LK::PthreadRwlockTryrdlock(&t);
	const bool        tc  = t != nullptr;
	const int         tu  = tr == OK ? LK::PthreadRwlockUnlock(&t) : -1;
	const int         td  = tc ? LK::PthreadRwlockDestroy(&t) : -1;
	const bool        both = tr == OK && tc && tu == OK && td == OK && t == nullptr;
	if (!ThrOn(kKk03)) {
		Report("kk03 statically initialised rwlock and condition variable", both,
		       Fmt("kk03 off; Tryrdlock on a static lock %s, created %s, unlock %s, destroy %s; not run: Destroy, "
		           "Timedrdlock and Timedwrlock of a static rwlock and Destroy of a static condition variable stop the "
		           "emulator today (EXIT_NOT_IMPLEMENTED)",
		           ErrName(tr), tc ? "yes" : "no", ErrName(tu), ErrName(td)));
		return;
	}
	LK::PthreadRwlock s1 = nullptr;
	const int         d1 = LK::PthreadRwlockDestroy(&s1); // OK, nothing made

	LK::PthreadRwlock s2 = nullptr;
	const int         r2 = LK::PthreadRwlockTimedrdlock(&s2, 1000);
	const bool        c2 = s2 != nullptr;
	int               w2 = -1;
	std::thread       o2 = Spawn([&] { w2 = LK::PthreadRwlockTimedwrlock(&s2, 20000); }); // read-held: times out
	o2.join();
	const int  u2  = LK::PthreadRwlockUnlock(&s2);
	const int  d2  = LK::PthreadRwlockDestroy(&s2);
	const bool n2  = s2 == nullptr;
	const int  d2b = LK::PthreadRwlockDestroy(&s2); // destroyed (handle NULL, as a static one): OK with kk03

	LK::PthreadRwlock s3 = nullptr;
	const int         r3 = LK::PthreadRwlockTimedwrlock(&s3, 1000);
	const bool        c3 = s3 != nullptr;
	int               w3 = -1;
	std::thread       o3 = Spawn([&] { w3 = LK::PthreadRwlockTimedrdlock(&s3, 20000); }); // write-held: times out
	o3.join();
	const int u3 = LK::PthreadRwlockUnlock(&s3);
	const int d3 = LK::PthreadRwlockDestroy(&s3);

	LK::PthreadCond c1 = nullptr;
	const int       e1 = LK::PthreadCondDestroy(&c1);

	const bool ok = both && d1 == OK && s1 == nullptr && r2 == OK && c2 && w2 == LK::KERNEL_ERROR_ETIMEDOUT && u2 == OK &&
	                d2 == OK && n2 && d2b == OK && r3 == OK && c3 && w3 == LK::KERNEL_ERROR_ETIMEDOUT && u3 == OK &&
	                d3 == OK && e1 == OK && c1 == nullptr;
	Report("kk03 statically initialised rwlock and condition variable", ok,
	       Fmt("kk03 on; Tryrdlock on a static lock %s; Destroy of a static rwlock %s, still unmade %s; Timedrdlock on a "
	           "static lock %s (made %s), a writer from another thread %s, unlock %s, destroy %s, again %s; Timedwrlock on "
	           "a static lock %s (made %s), a reader %s, unlock %s, destroy %s; Destroy of a static condition variable %s",
	           ErrName(tr), ErrName(d1), s1 == nullptr ? "yes" : "no", ErrName(r2), c2 ? "yes" : "no", ErrName(w2),
	           ErrName(u2), ErrName(d2), ErrName(d2b), ErrName(r3), c3 ? "yes" : "no", ErrName(w3), ErrName(u3), ErrName(d3),
	           ErrName(e1)));
}

// ---- 4: signalto -----------------------------------------------------------------------------------------------------
void CaseSignalto() {
	g_case = "signalto answers";
	const bool       on = ThrOn(kSignalto);
	LK::PthreadMutex m  = NewMutex("thr0405-c4", 1, 0);
	LK::PthreadCond  c  = NewCond("thr0405-c4");

	const int r_null = LK::PthreadCondSignalto(&c, nullptr);

	// Two waiters; signalto wakes the one it names, alone.
	struct Waiter {
		std::atomic<LK::Pthread> self {nullptr};
		std::atomic<int>         woke {0};
		int                      result = -1;
		bool                     go     = false; // under m
	};
	Waiter      w1, w2;
	int         registered = 0; // under m
	auto        body       = [&m, &c, &registered](Waiter* w) {
		if (LK::PthreadMutexLock(&m) != OK) {
			return;
		}
		w->self = LK::PthreadSelf();
		registered++;
		while (!w->go) {
			w->result = LK::PthreadCondTimedwait(&c, &m, 5000000);
			if (w->result != OK) {
				break;
			}
		}
		w->woke = 1;
		LK::PthreadMutexUnlock(&m);
	};
	std::thread t1 = Spawn([&] { body(&w1); });
	std::thread t2 = Spawn([&] { body(&w2); });
	bool        both_waiting = false;
	for (int k = 0; k < 5000 && !both_waiting; k++) {
		LK::PthreadMutexLock(&m);
		both_waiting = registered == 2; // each counted itself under m and released m only inside its wait
		LK::PthreadMutexUnlock(&m);
		if (!both_waiting) {
			std::this_thread::sleep_for(std::chrono::milliseconds(1));
		}
	}
	LK::PthreadMutexLock(&m);
	w1.go            = true;
	const int r_wait = LK::PthreadCondSignalto(&c, w1.self.load());
	LK::PthreadMutexUnlock(&m);
	const bool       w1_woke = WaitUntil(w1.woke, 1, 2000);
	std::this_thread::sleep_for(std::chrono::milliseconds(100));
	const bool w2_still = w2.woke.load() == 0;
	LK::PthreadMutexLock(&m);
	w2.go = true;
	LK::PthreadCondSignal(&c);
	LK::PthreadMutexUnlock(&m);
	t1.join();
	t2.join();

	// Targets that are not waiting (no thread waits on c now).
	const int r_fake = LK::PthreadCondSignalto(&c, reinterpret_cast<LK::Pthread>(static_cast<uintptr_t>(0x12345)));
	const int r_self = LK::PthreadCondSignalto(&c, LK::PthreadSelf());

	GuestBlock  a;
	GuestThread ga;
	const bool  a_made = CreateGuest(&ga, GuestBlockEntry, &a, "thr0405-live");
	const bool  a_runs = a_made && WaitUntil(a.state, 1, 5000);
	const int   r_live = a_runs ? LK::PthreadCondSignalto(&c, ga.handle) : -1;

	GuestBlock  b;
	GuestThread gb;
	b.release.Set(); // B returns at once
	const bool b_made = CreateGuest(&gb, GuestBlockEntry, &b, "thr0405-done");
	const bool b_done = b_made && WaitUntil(b.state, 2, 5000);
	int        r_fin  = -1;
	if (b_done) { // its end (CleanupThread) marks it finished a moment after its entry returned
		const auto t0 = Clock::now();
		do {
			r_fin = LK::PthreadCondSignalto(&c, gb.handle);
			if (!on || r_fin == LK::KERNEL_ERROR_ESRCH) {
				break;
			}
			std::this_thread::sleep_for(std::chrono::milliseconds(1));
		} while (Clock::now() - t0 < std::chrono::seconds(2));
	}
	const int j_b      = b_made ? JoinGuest(&gb) : -1;
	const int r_joined = j_b == OK ? LK::PthreadCondSignalto(&c, gb.handle) : -1; // before any other create reuses it
	a.release.Set();
	const int j_a = a_made ? JoinGuest(&ga) : -1;

	const int  want_srch = on ? LK::KERNEL_ERROR_ESRCH : OK;
	const int  want_perm = on ? LK::KERNEL_ERROR_EPERM : OK;
	const bool ok = r_null == LK::KERNEL_ERROR_EINVAL && r_wait == OK && w1_woke && w2_still && w1.result == OK &&
	                w2.result == OK && r_fake == want_srch && r_self == want_perm && a_runs && r_live == want_perm &&
	                b_done && r_fin == want_srch && j_b == OK && r_joined == want_srch && j_a == OK;
	Report("signalto answers", ok,
	       Fmt("signalto %s, want %s; null thread %s; a waiting thread %s, woken %s, the other waiter left waiting %s; a "
	           "handle that is no thread %s; the caller %s; a live guest thread %s; a finished guest thread %s; a joined "
	           "guest thread %s (joins %s %s)",
	           on ? "on" : "off", on ? "EINVAL, OK, ESRCH, EPERM, EPERM, ESRCH, ESRCH" : "EINVAL, OK, then OK for all (today)",
	           ErrName(r_null), ErrName(r_wait), w1_woke ? "yes" : "no", w2_still ? "yes" : "no", ErrName(r_fake),
	           ErrName(r_self), ErrName(r_live), ErrName(r_fin), ErrName(r_joined), ErrName(j_b), ErrName(j_a)));
	LK::PthreadCondDestroy(&c);
	LK::PthreadMutexDestroy(&m);
}

// ---- 5: x87 ----------------------------------------------------------------------------------------------------------
void CaseX87() {
	g_case = "x87 control word of a new guest thread";
	const bool  on = ThrOn(kX87);
	FpuSeen     f;
	GuestThread g;
	uint16_t    creator_cw    = 0;
	uint32_t    creator_mxcsr = 0;
	const bool  made          = CreateGuest(&g, GuestFpuEntry, &f, "thr0405-fpu", 0x027f, &creator_cw, &creator_mxcsr);
	const bool  ran           = made && WaitUntil(f.done, 1, 5000);
	const int   j             = made ? JoinGuest(&g) : -1;
	uint16_t    main_cw       = 0;
	asm volatile("fnstcw %0" : "=m"(main_cw));
	const uint16_t want = on ? 0x037f : 0x027f;
	const bool     ok   = made && ran && j == OK && f.cw == want && creator_cw == 0x027f && f.mxcsr == creator_mxcsr;
	Report("x87 control word of a new guest thread", ok,
	       Fmt("x87 %s; the creator loaded 0x027f and kept 0x%04x; the new guest thread started with 0x%04x (want 0x%04x%s), "
	           "MXCSR 0x%04x (the creator's 0x%04x); this thread's word 0x%04x; join %s",
	           on ? "on" : "off", static_cast<unsigned>(creator_cw), static_cast<unsigned>(f.cw), static_cast<unsigned>(want),
	           on ? ", FreeBSD's start state" : ", inherited from the creator, today's", static_cast<unsigned>(f.mxcsr),
	           static_cast<unsigned>(creator_mxcsr), static_cast<unsigned>(main_cw), ErrName(j)));
}

// ---- 6: kk07 ---------------------------------------------------------------------------------------------------------
void CaseKk07() {
	g_case = "kk07 joined thread";
	const bool  on = ThrOn(kKk07);
	GuestBlock  b;
	GuestThread gb;
	b.release.Set();
	const bool made = CreateGuest(&gb, GuestBlockEntry, &b, "thr0405-joined");
	const int  j    = made ? JoinGuest(&gb) : -1;
	int        gp = -1, sp = -1, cn = -1, prio_j = -1;
	if (on && j == OK) {
		gp = LK::PthreadGetprio(gb.handle, &prio_j);
		sp = LK::PthreadSetprio(gb.handle, 700);
		cn = LK::PthreadCancel(gb.handle);
	}
	GuestBlock  a;
	GuestThread ga;
	const bool  a_made = CreateGuest(&ga, GuestBlockEntry, &a, "thr0405-prio");
	const bool  a_runs = a_made && WaitUntil(a.state, 1, 5000);
	int         prio   = -1;
	const int   lg     = a_runs ? LK::PthreadGetprio(ga.handle, &prio) : -1;
	a.release.Set();
	const int ja = a_made ? JoinGuest(&ga) : -1;

	const bool live_ok = a_runs && lg == OK && prio == 700 && ja == OK;
	const bool ok      = made && j == OK && live_ok &&
	                (!on || (gp == LK::KERNEL_ERROR_ESRCH && sp == LK::KERNEL_ERROR_ESRCH && cn == LK::KERNEL_ERROR_ESRCH));
	Report("kk07 a joined thread", ok,
	       on ? Fmt("kk07 on; joined thread: Getprio %s, Setprio %s, Cancel %s (want ESRCH); a live guest thread: Getprio "
	                "%s, %d",
	                ErrName(gp), ErrName(sp), ErrName(cn), ErrName(lg), prio)
	          : Fmt("kk07 off; not run on the joined thread: today Getprio, Setprio and Cancel use its reaped host thread "
	                "(pthread_getschedparam, pthread_cancel; Setprio may renice a reused host thread id); a live guest "
	                "thread: Getprio %s, %d",
	                ErrName(lg), prio));
}

// ---- 7-9: semaphores -------------------------------------------------------------------------------------------------
void CaseSemaAttr() {
	g_case = "sema attributes";
	const bool on = SemaOn(kAttr);
	bool       ok = true;
	std::string info = Fmt("attr %s;", on ? "on" : "off");
	for (uint32_t attr: {0u, 1u, 2u}) {
		SM::KernelSema s = nullptr;
		const int      r = SM::KernelCreateSema(&s, "thr0405-attr", attr, 0, 1, nullptr);
		const int      d = (r == OK && s != nullptr) ? SM::KernelDeleteSema(s) : -1;
		ok               = ok && r == OK && d == OK;
		info += Fmt(" 0x%x %s", attr, ErrName(r));
	}
	for (uint32_t attr: {3u, 0x103u, 0x104u, 0x200u, 0x1000u, 0xffffffffu}) {
		SM::KernelSema s = nullptr;
		const int      r = SM::KernelCreateSema(&s, "thr0405-attr", attr, 0, 1, nullptr);
		ok               = ok && r == LK::KERNEL_ERROR_EINVAL && s == nullptr;
		info += Fmt(" 0x%x %s", attr, ErrName(r));
	}
	for (uint32_t attr: {0x100u, 0x101u, 0x102u}) {
		SM::KernelSema s = nullptr;
		const int      r = SM::KernelCreateSema(&s, "thr0405-attr", attr, 1, 2, nullptr);
		if (on) {
			const int p1 = r == OK ? SM::KernelPollSema(s, 1) : -1;
			const int p2 = r == OK ? SM::KernelPollSema(s, 1) : -1;
			const int g1 = r == OK ? SM::KernelSignalSema(s, 2) : -1;
			const int p3 = r == OK ? SM::KernelPollSema(s, 2) : -1;
			const int d  = r == OK ? SM::KernelDeleteSema(s) : -1;
			ok = ok && r == OK && p1 == OK && p2 == LK::KERNEL_ERROR_EBUSY && g1 == OK && p3 == OK && d == OK;
			info += Fmt(" 0x%x %s (poll %s %s, signal 2 %s, poll 2 %s, delete %s)", attr, ErrName(r), ErrName(p1), ErrName(p2),
			            ErrName(g1), ErrName(p3), ErrName(d));
		} else {
			ok = ok && r == LK::KERNEL_ERROR_EINVAL && s == nullptr;
			info += Fmt(" 0x%x %s (today's)", attr, ErrName(r));
		}
	}
	Report("sema attributes", ok, info);
}

void CaseSemaSignal() {
	g_case = "sema signal counts";
	const bool     on = SemaOn(kSignal);
	SM::KernelSema s  = nullptr;
	if (SM::KernelCreateSema(&s, "thr0405-signal", 1, 1, 5, nullptr) != OK || s == nullptr) {
		SetupFail("sema create");
	}
	bool        ok = false;
	std::string info;
	if (on) {
		const int z  = SM::KernelSignalSema(s, 0);
		const int n  = SM::KernelSignalSema(s, -1);
		const int mx = SM::KernelSignalSema(s, INT_MAX); // count 1: 1 + INT_MAX would wrap
		const int p1 = SM::KernelPollSema(s, 1);          // the count is still 1
		const int p2 = SM::KernelPollSema(s, 1);
		const int f  = SM::KernelSignalSema(s, 5);
		const int o  = SM::KernelSignalSema(s, 1); // full
		const int p5 = SM::KernelPollSema(s, 5);
		ok = z == LK::KERNEL_ERROR_EINVAL && n == LK::KERNEL_ERROR_EINVAL && mx == LK::KERNEL_ERROR_EINVAL && p1 == OK &&
		     p2 == LK::KERNEL_ERROR_EBUSY && f == OK && o == LK::KERNEL_ERROR_EINVAL && p5 == OK;
		info = Fmt("signal on; count 1: signal 0 %s, -1 %s, INT_MAX %s; then poll 1 %s, poll 1 %s; signal 5 %s, 1 more %s, "
		           "poll 5 %s",
		           ErrName(z), ErrName(n), ErrName(mx), ErrName(p1), ErrName(p2), ErrName(f), ErrName(o), ErrName(p5));
	} else {
		const int z  = SM::KernelSignalSema(s, 0);  // OK, count stays 1
		const int n  = SM::KernelSignalSema(s, -1); // OK, count 0
		const int p1 = SM::KernelPollSema(s, 1);    // EBUSY: the negative signal lowered the count
		const int f  = SM::KernelSignalSema(s, 5);
		const int o  = SM::KernelSignalSema(s, 1);
		const int p5 = SM::KernelPollSema(s, 5);
		const int g1 = SM::KernelSignalSema(s, 1);       // count 1
		const int mx = SM::KernelSignalSema(s, INT_MAX); // 1 + INT_MAX: today's arithmetic wraps; recorded only
		const int px = SM::KernelPollSema(s, 1);
		ok = z == OK && n == OK && p1 == LK::KERNEL_ERROR_EBUSY && f == OK && o == LK::KERNEL_ERROR_EINVAL && p5 == OK &&
		     g1 == OK;
		info = Fmt("signal off, today's; count 1: signal 0 %s, -1 %s, then poll 1 %s (the count was lowered); signal 5 %s, "
		           "1 more %s, poll 5 %s; recorded, not checked: at count 1 signal INT_MAX %s, then poll 1 %s",
		           ErrName(z), ErrName(n), ErrName(p1), ErrName(f), ErrName(o), ErrName(p5), ErrName(mx), ErrName(px));
	}
	const int d = SM::KernelDeleteSema(s);
	Report("sema signal counts", ok && d == OK, info);
}

void CaseSemaPollWait() {
	g_case = "sema poll and wait";
	SM::KernelSema s = nullptr;
	if (SM::KernelCreateSema(&s, "thr0405-poll", 1, 2, 3, nullptr) != OK || s == nullptr) {
		SetupFail("sema create");
	}
	const int z  = SM::KernelPollSema(s, 0);
	const int n  = SM::KernelPollSema(s, -1);
	const int a  = SM::KernelPollSema(s, 4);
	const int p2 = SM::KernelPollSema(s, 2);
	const int p1 = SM::KernelPollSema(s, 1);

	int              w  = -1;
	std::atomic<int> in {0};
	long long        us = -1;
	std::thread      t  = Spawn([&] {
		in            = 1;
		const auto t0 = Clock::now();
		w             = SM::KernelWaitSema(s, 2, nullptr);
		us            = UsSince(t0);
	});
	WaitUntil(in, 1, 5000);
	std::this_thread::sleep_for(std::chrono::milliseconds(30)); // it waits (count 0)
	const auto t0 = Clock::now();
	const int  g  = SM::KernelSignalSema(s, 2);
	t.join();
	const long long back = UsSince(t0);
	const int       pe   = SM::KernelPollSema(s, 1);
	const int       d    = SM::KernelDeleteSema(s);
	const bool ok = z == LK::KERNEL_ERROR_EINVAL && n == LK::KERNEL_ERROR_EINVAL && a == LK::KERNEL_ERROR_EINVAL && p2 == OK &&
	                p1 == LK::KERNEL_ERROR_EBUSY && g == OK && w == OK && back < 1000000 && pe == LK::KERNEL_ERROR_EBUSY && d == OK;
	Report("sema poll and a woken wait", ok,
	       Fmt("max 3, count 2: poll 0 %s, -1 %s, 4 %s (EINVAL already today), poll 2 %s, poll 1 %s; a wait for 2 woken by "
	           "signal 2 (%s): %s after %lld us, back in %lld us; then poll 1 %s",
	           ErrName(z), ErrName(n), ErrName(a), ErrName(p2), ErrName(p1), ErrName(g), ErrName(w), us, back, ErrName(pe)));
}

} // namespace

int main(int argc, char** argv) {
	static const char* const thr_names[] = {"kk06", "kk03", "signalto", "x87", "kk07"};
	static const uint32_t    thr_bits[]  = {kKk06, kKk03, kSignalto, kX87, kKk07};
	static const char* const sema_names[] = {"attr", "signal"};
	static const uint32_t    sema_bits[]  = {kAttr, kSignal};
	const char*              e_thr        = std::getenv("KYTY_BC5_THREAD_SYNC_FIXES");
	const char*              e_sema       = std::getenv("KYTY_BC5_SEMA_FIXES");
	g_thr  = ParseParts(e_thr, thr_names, thr_bits, 5, kThrAll);
	g_sema = ParseParts(e_sema, sema_names, sema_bits, 2, kSemaAll);
	const char* mode = (g_thr == kThrAll && g_sema == kSemaAll) ? "on" : ((g_thr == 0 && g_sema == 0) ? "off" : "part");
	std::printf("thr0405: KYTY_BC5_THREAD_SYNC_FIXES=%s (parts 0x%x), KYTY_BC5_SEMA_FIXES=%s (parts 0x%x), so %s\n",
	            e_thr != nullptr ? e_thr : "(unset)", static_cast<unsigned>(g_thr), e_sema != nullptr ? e_sema : "(unset)",
	            static_cast<unsigned>(g_sema), mode);
	std::fflush(stdout);
	if (argc > 2 || (argc == 2 && std::strcmp(argv[1], mode) != 0)) {
		std::printf("thr0405: FAIL setup: the argument (%s) does not name the mode the switches give (%s)\n",
		            argc >= 2 ? argv[1] : "", mode);
		std::fflush(stdout);
		return 2;
	}
	Log::Bc5SetLogging(false); // the units' LOGF stays off stdout
	std::thread(Watchdog).detach();

	// The subsystems and the singleton the code needs, on a helper thread that is the "main thread" for their constructors.
	std::thread init([] {
		Common::ThreadsSubsystem::Instance()->Init(nullptr);
		LK::PthreadSubsystem::Instance()->Init(nullptr);
		(void)Common::Singleton<Loader::RuntimeLinker>::Instance();
	});
	init.join();
	LK::PthreadInitSelfForMainThread(); // this thread drives the cases

	const auto start = Clock::now();
	CaseKk06Wakeups();
	CaseKk06Destroy();
	CaseKk03();
	CaseSignalto();
	CaseX87();
	CaseKk07();
	CaseSemaAttr();
	CaseSemaSignal();
	CaseSemaPollWait();

	g_finished = true;
	const int n = g_cases.load();
	const int p = g_passed.load();
	if (p != n) {
		std::printf("thr0405: %s %d of %d passed in %lld ms; FAIL\n", mode, p, n, UsSince(start) / 1000);
		std::fflush(stdout);
		_exit(1);
	}
	std::printf("thr0405: %s %d of %d; end\n", mode, p, n);
	std::fflush(stdout);
	_exit(0);
}
