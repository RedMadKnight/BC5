// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e4, KYTY_BC5_PTHREAD_FIXES (mkpth0401.py): the CPU stress test of the host's rwlocks and
// condition variables (src/kernel/pthread.cpp), with real threads. Run twice on the box, in the build container:
//   KYTY_BC5_PTHREAD_FIXES=1 pth0401        (on)
//   KYTY_BC5_PTHREAD_FIXES=0 pth0401        (off; unset is off too)
// The program reads the switch itself and expects, with it off, exactly today's behaviour. It prints one line per case,
// then exactly "pth0401: on N of N; end" or "pth0401: off N of N; end", and exits 0 only then. A watchdog ends a hang
// after 50 s with a FAIL line (exit 3). The unit prints "[bc5] exp 0401: pthread fixes on|off (...)" on stderr once.
// Cases (pth0401-notes.md has the reasons):
//   1 same-lock recursion past a queued writer (today's rule, on and off alike)
//   2 a reader that holds other read locks past a queued writer: the ported rule (AnyPS5 45a8b80a5, libthr
//     rdlock_count): on, it reads; off, EBUSY / ETIMEDOUT as today. Also the count: two, an EPERM unlock, one, none.
//   3 two readers, each behind the other lock's queued writer: on, both read; off, both time out (the cross-lock cycle
//     that is a permanent deadlock with untimed locks today; recorded, not a failure with the switch off)
//   4 rwlock contention stress, 8 threads (rd, wr, timed, try, nested C -> B): exclusion and no lost wake-up
//     (the races of AnyPS5 4ed0f9f91, 372f0f6c6, 83b1015c4 in their _umtx_op; checked here on our design)
//   5 condition variable ring, 4 threads taking turns, mutex types 1, 2 (locked twice), 4, untimed and timed waits
//     (the relock path of AnyPS5 16375634e)
//   6 producers and consumers: signal under the mutex, consumers in 2 ms timed waits (wake and time-out paths)
//   7 a wait that fails (mutex not held) or uses a priority-protected mutex leaves no waiter behind (AnyPS5 4ed0f9f91's
//     dangling condvar waiter): one later signal wakes the one real waiter
//   8 broadcast wakes all 8 waiters (4 untimed, 4 timed)
//   9 timed waits time out, relative and absolute, and return with the mutex held
//  10 timed-out writers leave no waiting mark (8 writers x 60 time-outs, probes alongside); readers, also one holding
//     another read lock, still time out behind a write owner
// Build (box0401's build0401.py, series e4): this file compiled with src/kernel/pthread.cpp's compile command
// (--gate pth0401.cpp <out> --like src/kernel/pthread.cpp) and linked with every emulator object but main.cpp.o, the
// private pthread.cpp.o (mkpth0401.py's output, src/kernel/pthread.cpp=<it>) in place of the shared one.
// Runtime state it sets up: the Threads subsystem's main thread and the Pthread subsystem (PThreadContext, the static
// objects, the default attributes), both on a helper thread that then ends, so PRINT_NAME stays off on every thread
// that calls the pthread code; logging off (Log::Bc5SetLogging(false)); every thread that calls the pthread code
// first gets its own PthreadPrivate through PthreadInitSelfForMainThread. Guest signals are never raised.

#include "common/logging/log.h"
#include "common/threads.h"
#include "kernel/pthread.h"
#include "libs/errno.h"

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <initializer_list>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include <unistd.h>

namespace {

namespace LK = Libs::LibKernel;
using Clock  = std::chrono::steady_clock;

constexpr int kWatchdogSeconds = 50;

bool                     g_on = false;
std::atomic<int>         g_cases {0};
std::atomic<int>         g_passed {0};
std::atomic<const char*> g_case {"start"};
std::atomic<bool>        g_finished {false};

long long UsSince(Clock::time_point t0) {
	return std::chrono::duration_cast<std::chrono::microseconds>(Clock::now() - t0).count();
}

const char* ErrName(int r) {
	switch (r) {
		case OK: return "OK";
		case LK::KERNEL_ERROR_EBUSY: return "EBUSY";
		case LK::KERNEL_ERROR_ETIMEDOUT: return "ETIMEDOUT";
		case LK::KERNEL_ERROR_EPERM: return "EPERM";
		case LK::KERNEL_ERROR_EDEADLK: return "EDEADLK";
		case LK::KERNEL_ERROR_EINVAL: return "EINVAL";
		case -1: return "not run";
		default: return "other";
	}
}

std::string Fmt(const char* format, ...) __attribute__((format(printf, 1, 2)));
std::string Fmt(const char* format, ...) {
	char    buf[1024];
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
	std::printf("pth0401: case %d %s: %s (%s)\n", g_cases.load(), name, ok ? "ok" : "FAIL", info.c_str());
	std::fflush(stdout);
}

[[noreturn]] void SetupFail(const char* what) {
	std::printf("pth0401: FAIL setup: %s\n", what);
	std::fflush(stdout);
	_exit(2);
}

void Watchdog() {
	const auto start = Clock::now();
	while (!g_finished.load()) {
		std::this_thread::sleep_for(std::chrono::milliseconds(50));
		if (Clock::now() - start > std::chrono::seconds(kWatchdogSeconds)) {
			std::printf("pth0401: FAIL watchdog: case \"%s\" still running after %d s (a hang); %s, %d of %d cases passed before it\n",
			            g_case.load(), kWatchdogSeconds, g_on ? "on" : "off", g_passed.load(), g_cases.load());
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
	void Set() {
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

void Spin(int n) {
	for (int k = 0; k < n; k++) {
		std::atomic_signal_fence(std::memory_order_seq_cst);
	}
}

void NoteMax(std::atomic<long long>& peak, long long v) {
	long long seen = peak.load();
	while (v > seen && !peak.compare_exchange_weak(seen, v)) {
	}
}

LK::PthreadRwlock NewRwlock(const char* name) {
	LK::PthreadRwlock l = nullptr;
	if (LK::PthreadRwlockInit(&l, nullptr, name) != OK || l == nullptr) {
		SetupFail(name);
	}
	return l;
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

// Waits until a writer is queued on l behind its readers: then a thread that holds no read lock is refused (EBUSY), with
// the switch on or off. Runs on a fresh guest thread, so it holds no read lock itself.
bool WaitWriterQueued(LK::PthreadRwlock* l) {
	bool        queued = false;
	std::thread probe = Spawn([&] {
		for (int k = 0; k < 3000; k++) {
			const int r = LK::PthreadRwlockTryrdlock(l);
			if (r == LK::KERNEL_ERROR_EBUSY) {
				queued = true;
				return;
			}
			if (r == OK) {
				LK::PthreadRwlockUnlock(l);
			}
			std::this_thread::sleep_for(std::chrono::milliseconds(1));
		}
	});
	probe.join();
	return queued;
}

// ---- 1 -------------------------------------------------------------------------------------------------------------
void CaseSameLockRecursion() {
	g_case = "same-lock recursion past a queued writer";
	LK::PthreadRwlock b = NewRwlock("pth0401-c1");
	Flag              holds, go, again_done, release;
	int               r_first = -1, r_again = -1, r_un1 = -1, r_un2 = -1, w_lock = -1, w_un = -1, t_try = -1, t_un = OK;
	Clock::time_point freed {}, got {};

	std::thread reader = Spawn([&] {
		r_first = LK::PthreadRwlockRdlock(&b);
		holds.Set();
		go.Wait(10000);
		r_again = LK::PthreadRwlockTimedrdlock(&b, 1000000);
		again_done.Set();
		release.Wait(10000);
		r_un1 = LK::PthreadRwlockUnlock(&b);
		freed = Clock::now();
		r_un2 = LK::PthreadRwlockUnlock(&b);
	});
	holds.Wait(10000);
	std::thread writer = Spawn([&] {
		w_lock = LK::PthreadRwlockTimedwrlock(&b, 5000000);
		got    = Clock::now();
		if (w_lock == OK) {
			w_un = LK::PthreadRwlockUnlock(&b);
		}
	});
	const bool queued = WaitWriterQueued(&b);
	go.Set();
	again_done.Wait(10000);
	std::thread other = Spawn([&] {
		t_try = LK::PthreadRwlockTryrdlock(&b);
		if (t_try == OK) {
			t_un = LK::PthreadRwlockUnlock(&b);
		}
	});
	other.join();
	release.Set();
	reader.join();
	writer.join();

	const bool ok = r_first == OK && queued && r_again == OK && t_try == LK::KERNEL_ERROR_EBUSY && t_un == OK &&
	                r_un1 == OK && r_un2 == OK && w_lock == OK && w_un == OK;
	const long long latency = std::chrono::duration_cast<std::chrono::microseconds>(got - freed).count();
	Report("same-lock recursion past a queued writer", ok,
	       Fmt("rdlock %s, writer queued %s, the reader's second timed rdlock %s, a thread holding nothing tries %s, "
	           "unlocks %s %s, writer %s %lld us after the last read unlock",
	           ErrName(r_first), queued ? "yes" : "no", ErrName(r_again), ErrName(t_try), ErrName(r_un1), ErrName(r_un2), ErrName(w_lock),
	           latency));
}

// ---- 2 -------------------------------------------------------------------------------------------------------------
void CaseCrossLockReader() {
	g_case = "a reader holding other read locks past a queued writer";
	LK::PthreadRwlock a = NewRwlock("pth0401-c2a"), b = NewRwlock("pth0401-c2b"), c = NewRwlock("pth0401-c2c");
	Flag              holds, release;
	int               r_lock = -1, r_un = -1, w_lock = -1, w_un = -1;

	std::thread reader = Spawn([&] {
		r_lock = LK::PthreadRwlockRdlock(&b);
		holds.Set();
		release.Wait(10000);
		r_un = LK::PthreadRwlockUnlock(&b);
	});
	holds.Wait(10000);
	std::thread writer = Spawn([&] {
		w_lock = LK::PthreadRwlockTimedwrlock(&b, 5000000);
		if (w_lock == OK) {
			w_un = LK::PthreadRwlockUnlock(&b);
		}
	});
	const bool queued = WaitWriterQueued(&b);

	int         a1 = -1, a2 = -1, eperm = -1, r1 = -1, u1 = OK, r2 = -1, u2 = OK, ua1 = -1, r3 = -1, u3 = OK, ua2 = -1;
	int         r4 = -1, u4 = OK;
	long long   r2_us = -1;
	std::thread t = Spawn([&] {
		a1    = LK::PthreadRwlockRdlock(&a); // two read locks held, both on A
		a2    = LK::PthreadRwlockRdlock(&a);
		eperm = LK::PthreadRwlockUnlock(&c); // not held: EPERM, the count stays at two
		r1    = LK::PthreadRwlockTryrdlock(&b);
		if (r1 == OK) {
			u1 = LK::PthreadRwlockUnlock(&b);
		}
		const auto t0 = Clock::now();
		r2            = LK::PthreadRwlockTimedrdlock(&b, 50000);
		r2_us         = UsSince(t0);
		if (r2 == OK) {
			u2 = LK::PthreadRwlockUnlock(&b);
		}
		ua1 = LK::PthreadRwlockUnlock(&a); // one read lock left
		r3  = LK::PthreadRwlockTryrdlock(&b);
		if (r3 == OK) {
			u3 = LK::PthreadRwlockUnlock(&b);
		}
		ua2 = LK::PthreadRwlockUnlock(&a); // none left: today's writer preference again, on or off
		r4  = LK::PthreadRwlockTryrdlock(&b);
		if (r4 == OK) {
			u4 = LK::PthreadRwlockUnlock(&b);
		}
	});
	t.join();
	release.Set();
	reader.join();
	writer.join();
	int         r5 = -1, u5 = OK;
	std::thread t2 = Spawn([&] {
		r5 = LK::PthreadRwlockTryrdlock(&b); // no writer left: anyone reads
		if (r5 == OK) {
			u5 = LK::PthreadRwlockUnlock(&b);
		}
	});
	t2.join();

	const int  want_try   = g_on ? OK : LK::KERNEL_ERROR_EBUSY;
	const int  want_timed = g_on ? OK : LK::KERNEL_ERROR_ETIMEDOUT;
	const bool ok = r_lock == OK && queued && a1 == OK && a2 == OK && eperm == LK::KERNEL_ERROR_EPERM && r1 == want_try &&
	                u1 == OK && r2 == want_timed && u2 == OK && ua1 == OK && r3 == want_try && u3 == OK && ua2 == OK &&
	                r4 == LK::KERNEL_ERROR_EBUSY && u4 == OK && r_un == OK && w_lock == OK && w_un == OK && r5 == OK &&
	                u5 == OK;
	Report("a reader holding other read locks past a queued writer", ok,
	       Fmt("%s; writer queued %s; holding 2 read locks (after an EPERM unlock: %s): try %s, timed 50 ms %s in %lld us; "
	           "holding 1: try %s; holding none: try %s; writer %s, then anyone reads %s",
	           g_on ? "on, the console's rule: want OK, OK, OK, EBUSY" : "off, today's rule: want EBUSY, ETIMEDOUT, EBUSY, EBUSY",
	           queued ? "yes" : "no", ErrName(eperm), ErrName(r1), ErrName(r2), r2_us, ErrName(r3), ErrName(r4), ErrName(w_lock), ErrName(r5)));
}

// ---- 3 -------------------------------------------------------------------------------------------------------------
void CaseCrossLockCycle() {
	g_case = "two readers, each behind the other lock's queued writer";
	LK::PthreadRwlock a = NewRwlock("pth0401-c3a"), b = NewRwlock("pth0401-c3b");
	Flag              t1_holds, t2_holds, go, t1_tried, t2_tried, both;
	int               t1_a = -1, t2_b = -1, t1_b = -1, t2_a = -1, t1_ub = OK, t1_ua = -1, t2_ua = OK, t2_ub = -1;
	int               wa = -1, wa_un = -1, wb = -1, wb_un = -1;
	long long         t1_us = -1, t2_us = -1;

	std::thread t1 = Spawn([&] {
		t1_a = LK::PthreadRwlockRdlock(&a);
		t1_holds.Set();
		go.Wait(10000);
		const auto t0 = Clock::now();
		t1_b          = LK::PthreadRwlockTimedrdlock(&b, 300000);
		t1_us         = UsSince(t0);
		t1_tried.Set();
		both.Wait(10000); // neither releases before both tried: the outcome does not depend on timing
		if (t1_b == OK) {
			t1_ub = LK::PthreadRwlockUnlock(&b);
		}
		t1_ua = LK::PthreadRwlockUnlock(&a);
	});
	std::thread t2 = Spawn([&] {
		t2_b = LK::PthreadRwlockRdlock(&b);
		t2_holds.Set();
		go.Wait(10000);
		const auto t0 = Clock::now();
		t2_a          = LK::PthreadRwlockTimedrdlock(&a, 300000);
		t2_us         = UsSince(t0);
		t2_tried.Set();
		both.Wait(10000);
		if (t2_a == OK) {
			t2_ua = LK::PthreadRwlockUnlock(&a);
		}
		t2_ub = LK::PthreadRwlockUnlock(&b);
	});
	t1_holds.Wait(10000);
	t2_holds.Wait(10000);
	std::thread w_a = Spawn([&] {
		wa = LK::PthreadRwlockTimedwrlock(&a, 5000000);
		if (wa == OK) {
			wa_un = LK::PthreadRwlockUnlock(&a);
		}
	});
	std::thread w_b = Spawn([&] {
		wb = LK::PthreadRwlockTimedwrlock(&b, 5000000);
		if (wb == OK) {
			wb_un = LK::PthreadRwlockUnlock(&b);
		}
	});
	const bool qa = WaitWriterQueued(&a);
	const bool qb = WaitWriterQueued(&b);
	go.Set();
	t1_tried.Wait(10000);
	t2_tried.Wait(10000);
	both.Set();
	t1.join();
	t2.join();
	w_a.join();
	w_b.join();

	const int  want = g_on ? OK : LK::KERNEL_ERROR_ETIMEDOUT;
	const bool ok   = t1_a == OK && t2_b == OK && qa && qb && t1_b == want && t2_a == want && t1_ub == OK && t2_ua == OK &&
	                t1_ua == OK && t2_ub == OK && wa == OK && wa_un == OK && wb == OK && wb_un == OK;
	const bool cycle = t1_b == LK::KERNEL_ERROR_ETIMEDOUT && t2_a == LK::KERNEL_ERROR_ETIMEDOUT;
	Report("two readers, each behind the other lock's queued writer", ok,
	       Fmt("%s; writers queued %s %s; reader 1 on B %s in %lld us, reader 2 on A %s in %lld us; cross-lock cycle seen %d "
	           "time(s)%s; writers %s %s",
	           g_on ? "on: want both to read" : "off: want both to time out, as today", qa ? "yes" : "no", qb ? "yes" : "no",
	           ErrName(t1_b), t1_us, ErrName(t2_a), t2_us, cycle ? 1 : 0,
	           cycle ? " (untimed, today's locks would wait for ever: 2 readers and 2 writers stuck)" : "", ErrName(wa),
	           ErrName(wb)));
}

// ---- 4 -------------------------------------------------------------------------------------------------------------
void CaseRwlockStress() {
	g_case = "rwlock contention stress";
	LK::PthreadRwlock b = NewRwlock("pth0401-c4b"), c = NewRwlock("pth0401-c4c");
	constexpr int     kThreads  = 8;
	constexpr int     kRounds   = 2000;
	constexpr LK::KernelUseconds kFailsafe = 2000000;

	std::atomic<int>       b_readers {0}, b_writers {0}, c_readers {0}, c_writers {0};
	std::atomic<int>       overlaps {0}, errors {0}, failsafes {0}, busy {0}, b_writes {0}, c_writes {0}, first_error {0};
	std::atomic<long long> max_wait_us {0};
	long long              b_plain = 0, c_plain = 0; // changed only under the write lock

	auto note = [&](int got, int want) {
		if (got != want) {
			errors++;
			int none = 0;
			first_error.compare_exchange_strong(none, got);
		}
	};
	auto read_b = [&] {
		b_readers++;
		if (b_writers.load() != 0 || b_plain < 0) {
			overlaps++;
		}
		b_readers--;
	};
	auto read_c = [&] {
		c_readers++;
		if (c_writers.load() != 0 || c_plain < 0) {
			overlaps++;
		}
		c_readers--;
	};
	auto write_b = [&](int i) {
		if (b_writers.fetch_add(1) != 0 || b_readers.load() != 0) {
			overlaps++;
		}
		const long long v = b_plain;
		Spin(16 + i * 4);
		b_plain = v + 1;
		b_writes++;
		b_writers--;
	};
	auto write_c = [&](int i) {
		if (c_writers.fetch_add(1) != 0 || c_readers.load() != 0) {
			overlaps++;
		}
		const long long v = c_plain;
		Spin(16 + i * 4);
		c_plain = v + 1;
		c_writes++;
		c_writers--;
	};

	auto worker = [&](int i) {
		for (int r = 0; r < kRounds; r++) {
			const int  kind = (r * 7 + i) % 8; // each round, the eight threads do the eight kinds
			const auto t0   = Clock::now();
			switch (kind) {
				case 0: {
					const int g = LK::PthreadRwlockWrlock(&b);
					NoteMax(max_wait_us, UsSince(t0));
					note(g, OK);
					if (g == OK) {
						write_b(i);
						note(LK::PthreadRwlockUnlock(&b), OK);
					}
					break;
				}
				case 1: {
					const int g = LK::PthreadRwlockTimedwrlock(&b, kFailsafe);
					NoteMax(max_wait_us, UsSince(t0));
					if (g == LK::KERNEL_ERROR_ETIMEDOUT) {
						failsafes++;
					} else {
						note(g, OK);
					}
					if (g == OK) {
						write_b(i);
						note(LK::PthreadRwlockUnlock(&b), OK);
					}
					break;
				}
				case 2: {
					const int g = LK::PthreadRwlockWrlock(&c);
					NoteMax(max_wait_us, UsSince(t0));
					note(g, OK);
					if (g == OK) {
						write_c(i);
						note(LK::PthreadRwlockUnlock(&c), OK);
					}
					break;
				}
				case 3: { // nested: C, then B (with the switch on, B is taken past B's queued writers)
					const int g1 = LK::PthreadRwlockRdlock(&c);
					note(g1, OK);
					if (g1 == OK) {
						const int g2 = LK::PthreadRwlockRdlock(&b);
						NoteMax(max_wait_us, UsSince(t0));
						note(g2, OK);
						if (g2 == OK) {
							read_b();
							read_c();
							note(LK::PthreadRwlockUnlock(&b), OK);
						}
						note(LK::PthreadRwlockUnlock(&c), OK);
					}
					break;
				}
				case 4: {
					const int g = LK::PthreadRwlockTimedrdlock(&b, kFailsafe);
					NoteMax(max_wait_us, UsSince(t0));
					if (g == LK::KERNEL_ERROR_ETIMEDOUT) {
						failsafes++;
					} else {
						note(g, OK);
					}
					if (g == OK) {
						read_b();
						note(LK::PthreadRwlockUnlock(&b), OK);
					}
					break;
				}
				case 5: {
					const bool write = (r & 1) == 0;
					const int  g     = write ? LK::PthreadRwlockTrywrlock(&b) : LK::PthreadRwlockTryrdlock(&b);
					if (g == LK::KERNEL_ERROR_EBUSY) {
						busy++;
					} else {
						note(g, OK);
					}
					if (g == OK) {
						if (write) {
							write_b(i);
						} else {
							read_b();
						}
						note(LK::PthreadRwlockUnlock(&b), OK);
					}
					break;
				}
				case 6: {
					const int g = LK::PthreadRwlockRdlock(&b);
					NoteMax(max_wait_us, UsSince(t0));
					note(g, OK);
					if (g == OK) {
						read_b();
						note(LK::PthreadRwlockUnlock(&b), OK);
					}
					break;
				}
				default: { // 7: nested and timed: C, then B
					const int g1 = LK::PthreadRwlockTimedrdlock(&c, kFailsafe);
					if (g1 == LK::KERNEL_ERROR_ETIMEDOUT) {
						failsafes++;
					} else {
						note(g1, OK);
					}
					if (g1 == OK) {
						const int g2 = LK::PthreadRwlockTimedrdlock(&b, kFailsafe);
						NoteMax(max_wait_us, UsSince(t0));
						if (g2 == LK::KERNEL_ERROR_ETIMEDOUT) {
							failsafes++;
						} else {
							note(g2, OK);
						}
						if (g2 == OK) {
							read_b();
							read_c();
							note(LK::PthreadRwlockUnlock(&b), OK);
						}
						note(LK::PthreadRwlockUnlock(&c), OK);
					}
					break;
				}
			}
			if ((r & 31) == 0) {
				std::this_thread::yield();
			}
		}
	};

	const auto               start = Clock::now();
	std::vector<std::thread> threads;
	for (int i = 0; i < kThreads; i++) {
		threads.push_back(Spawn([&, i] { worker(i); }));
	}
	for (auto& th: threads) {
		th.join();
	}
	const long long elapsed_ms = UsSince(start) / 1000;
	int             fb = -1, fbu = -1, fc = -1, fcu = -1;
	std::thread     check = Spawn([&] {
		fb = LK::PthreadRwlockTrywrlock(&b);
		if (fb == OK) {
			fbu = LK::PthreadRwlockUnlock(&b);
		}
		fc = LK::PthreadRwlockTrywrlock(&c);
		if (fc == OK) {
			fcu = LK::PthreadRwlockUnlock(&c);
		}
	});
	check.join();

	const bool ok = overlaps.load() == 0 && errors.load() == 0 && failsafes.load() == 0 && b_plain == b_writes.load() &&
	                c_plain == c_writes.load() && fb == OK && fbu == OK && fc == OK && fcu == OK;
	Report("rwlock contention stress", ok,
	       Fmt("%d threads x %d rounds in %lld ms; B writes %d (counter %lld), C writes %d (counter %lld), try refused %d; "
	           "overlaps %d, errors %d (first %s), failsafe time-outs %d; longest lock wait %lld us; free after: %s %s",
	           kThreads, kRounds, elapsed_ms, b_writes.load(), b_plain, c_writes.load(), c_plain, busy.load(),
	           overlaps.load(), errors.load(), ErrName(first_error.load()), failsafes.load(), max_wait_us.load(), ErrName(fb),
	           ErrName(fc)));
}

// ---- 5 -------------------------------------------------------------------------------------------------------------
struct RingResult {
	int  turn       = 0;
	int  total      = 0;
	int  errors     = 0;
	int  first      = 0;
	bool overlapped = false;
};

RingResult Ring(int type, bool timed) {
	constexpr int    kRingThreads = 4;
	constexpr int    kTurns       = 200;
	LK::PthreadMutex m            = NewMutex("pth0401-ring", type, 0);
	LK::PthreadCond  cv           = NewCond("pth0401-ring");
	int              turn = 0, total = 0; // under m
	std::atomic<int> inside {0}, next_id {0}, errors {0}, first {0};
	std::atomic<bool> overlapped {false}, abort_all {false};

	auto fail = [&](int g) {
		errors++;
		int none = 0;
		first.compare_exchange_strong(none, g);
		abort_all = true;
	};
	auto body = [&] {
		const int id = next_id.fetch_add(1);
		for (int round = 0; round < kTurns && !abort_all.load(); round++) {
			int g = LK::PthreadMutexLock(&m);
			if (g != OK) {
				fail(g);
				return;
			}
			if (type == 2) { // recursive: held twice across the wait, as AnyPS5's ring does
				g = LK::PthreadMutexLock(&m);
				if (g != OK) {
					fail(g);
				}
			}
			bool stop = false;
			while (turn % kRingThreads != id) {
				if (abort_all.load()) {
					stop = true;
					break;
				}
				g = timed ? LK::PthreadCondTimedwait(&cv, &m, 10000000) : LK::PthreadCondWait(&cv, &m);
				if (g != OK) { // a timed wait of 10 s that times out is a lost wake-up here
					fail(g);
					stop = true;
					break;
				}
			}
			if (!stop) {
				if (inside.fetch_add(1) != 0) {
					overlapped = true;
				}
				++turn;
				++total;
				inside.fetch_sub(1);
			}
			g = LK::PthreadCondBroadcast(&cv);
			if (g != OK) {
				fail(g);
			}
			if (type == 2) {
				LK::PthreadMutexUnlock(&m);
			}
			g = LK::PthreadMutexUnlock(&m);
			if (g != OK) {
				fail(g);
			}
			if (stop) {
				return;
			}
		}
	};
	std::vector<std::thread> threads;
	for (int k = 0; k < kRingThreads; k++) {
		threads.push_back(Spawn([&] { body(); }));
	}
	for (auto& th: threads) {
		th.join();
	}
	RingResult res;
	res.turn       = turn;
	res.total      = total;
	res.errors     = errors.load();
	res.first      = first.load();
	res.overlapped = overlapped.load();
	return res;
}

void CaseCondRing() {
	g_case = "condition variable ring";
	constexpr int kWant = 4 * 200;
	bool          ok    = true;
	std::string   info;
	const auto    start = Clock::now();
	for (int type: {1, 2, 4}) {
		for (bool timed: {false, true}) {
			const RingResult r = Ring(type, timed);
			const bool good = r.turn == kWant && r.total == kWant && r.errors == 0 && !r.overlapped;
			ok              = ok && good;
			info += Fmt("%stype %d %s: %d turns%s%s", info.empty() ? "" : "; ", type, timed ? "timed" : "untimed", r.total,
			            r.overlapped ? ", OVERLAP" : "", r.errors != 0 ? (std::string(", error ") + ErrName(r.first)).c_str() : "");
		}
	}
	info += Fmt("; %lld ms", UsSince(start) / 1000);
	Report("condition variable ring", ok, info);
}

// ---- 6 -------------------------------------------------------------------------------------------------------------
void CaseProducerConsumer() {
	g_case = "producers and consumers with timed waits";
	constexpr int    kProducers = 2, kConsumers = 3, kItems = 3000;
	LK::PthreadMutex m  = NewMutex("pth0401-c6", 1, 0);
	LK::PthreadCond  cv = NewCond("pth0401-c6");
	std::vector<int> queue; // under m
	size_t           head = 0;
	bool             done = false;
	long long        consumed_sum = 0;
	int              consumed     = 0;
	std::atomic<int> inside {0}, overlaps {0}, errors {0}, timeouts {0}, wakes {0}, first {0};
	queue.reserve(kProducers * kItems);

	auto note = [&](int got) {
		if (got != OK) {
			errors++;
			int none = 0;
			first.compare_exchange_strong(none, got);
		}
	};
	auto enter = [&] {
		if (inside.fetch_add(1) != 0) {
			overlaps++;
		}
	};
	auto leave = [&] { inside.fetch_sub(1); };

	std::vector<std::thread> consumers, producers;
	for (int k = 0; k < kConsumers; k++) {
		consumers.push_back(Spawn([&] {
			note(LK::PthreadMutexLock(&m));
			enter();
			for (;;) {
				bool broken = false;
				while (head == queue.size() && !done) {
					leave();
					const int g = LK::PthreadCondTimedwait(&cv, &m, 2000);
					enter();
					if (g == LK::KERNEL_ERROR_ETIMEDOUT) {
						timeouts++;
					} else if (g == OK) {
						wakes++;
					} else {
						note(g);
						broken = true;
						break;
					}
				}
				if (broken || (head == queue.size() && done)) {
					break;
				}
				consumed_sum += queue[head++];
				consumed++;
			}
			leave();
			note(LK::PthreadMutexUnlock(&m));
		}));
	}
	for (int p = 0; p < kProducers; p++) {
		producers.push_back(Spawn([&, p] {
			for (int k = 0; k < kItems; k++) {
				note(LK::PthreadMutexLock(&m));
				enter();
				queue.push_back(p * kItems + k + 1);
				leave();
				note(LK::PthreadCondSignal(&cv));
				note(LK::PthreadMutexUnlock(&m));
				if ((k & 63) == 0) {
					std::this_thread::yield();
				}
			}
		}));
	}
	for (auto& th: producers) {
		th.join();
	}
	note(LK::PthreadMutexLock(&m));
	done = true;
	note(LK::PthreadCondBroadcast(&cv));
	note(LK::PthreadMutexUnlock(&m));
	for (auto& th: consumers) {
		th.join();
	}

	long long want_sum = 0;
	for (int p = 0; p < kProducers; p++) {
		for (int k = 0; k < kItems; k++) {
			want_sum += p * kItems + k + 1;
		}
	}
	const bool ok = consumed == kProducers * kItems && consumed_sum == want_sum && overlaps.load() == 0 && errors.load() == 0;
	Report("producers and consumers with timed waits", ok,
	       Fmt("%d of %d items, sum %s; overlaps %d, errors %d (first %s); consumer waits: %d woken, %d timed out (2 ms)",
	           consumed, kProducers * kItems, consumed_sum == want_sum ? "right" : "WRONG", overlaps.load(), errors.load(),
	           ErrName(first.load()), wakes.load(), timeouts.load()));
}

// ---- 7 -------------------------------------------------------------------------------------------------------------
void CaseNoStaleWaiter() {
	g_case = "failed and priority-protected waits leave no waiter";
	LK::PthreadMutex m  = NewMutex("pth0401-c7", 1, 0);
	LK::PthreadMutex mp = NewMutex("pth0401-c7p", 1, 2); // protocol 2: PTHREAD_PRIO_PROTECT
	LK::PthreadCond  cv = NewCond("pth0401-c7");
	int              e1 = -1, e2 = -1, pl = -1, e3 = -1, pu = -1;

	std::thread x = Spawn([&] {
		e1 = LK::PthreadCondTimedwait(&cv, &m, 10000); // m not held: EPERM, before anything is queued
		e2 = LK::PthreadCondWait(&cv, &m);             // the same, untimed
		pl = LK::PthreadMutexLock(&mp);
		e3 = LK::PthreadCondTimedwait(&cv, &mp, 20000); // a priority-protected mutex: an ordinary wait, times out
		pu = LK::PthreadMutexUnlock(&mp);               // and it was held again
	});
	x.join();

	bool        y_ready = false; // under m
	int         y_lock = -1, y_wait = -1, y_un = -1;
	long long   y_us = -1;
	std::thread y    = Spawn([&] {
		y_lock        = LK::PthreadMutexLock(&m);
		y_ready       = true; // queued on cv before m is released (CondAddWaiter comes before the unlock)
		const auto t0 = Clock::now();
		y_wait        = LK::PthreadCondTimedwait(&cv, &m, 3000000);
		y_us          = UsSince(t0);
		y_un          = LK::PthreadMutexUnlock(&m);
	});
	int         s_sig = -1;
	bool        seen  = false;
	std::thread s     = Spawn([&] {
		for (int k = 0; k < 5000 && !seen; k++) {
			if (LK::PthreadMutexLock(&m) != OK) {
				return;
			}
			seen = y_ready;
			if (seen) {
				s_sig = LK::PthreadCondSignal(&cv); // one signal: it goes to the first waiter in the queue
			}
			LK::PthreadMutexUnlock(&m);
			if (!seen) {
				std::this_thread::sleep_for(std::chrono::milliseconds(1));
			}
		}
	});
	s.join();
	y.join();

	const bool ok = e1 == LK::KERNEL_ERROR_EPERM && e2 == LK::KERNEL_ERROR_EPERM && pl == OK &&
	                e3 == LK::KERNEL_ERROR_ETIMEDOUT && pu == OK && seen && s_sig == OK && y_lock == OK && y_wait == OK &&
	                y_un == OK && y_us < 1000000;
	Report("failed and priority-protected waits leave no waiter", ok,
	       Fmt("wait without the mutex: timed %s, untimed %s; priority-protected: %s, unlock after %s; the real waiter "
	           "woke with %s after %lld us",
	           ErrName(e1), ErrName(e2), ErrName(e3), ErrName(pu), ErrName(y_wait), y_us));
}

// ---- 8 -------------------------------------------------------------------------------------------------------------
void CaseBroadcast() {
	g_case = "broadcast wakes every waiter";
	constexpr int    kWaiters = 8;
	LK::PthreadMutex m        = NewMutex("pth0401-c8", 1, 0);
	LK::PthreadCond  cv       = NewCond("pth0401-c8");
	int              gen = 0, registered = 0, woke = 0; // under m
	std::atomic<int> errors {0}, timeouts {0};

	std::vector<std::thread> waiters;
	for (int i = 0; i < kWaiters; i++) {
		waiters.push_back(Spawn([&, i] {
			if (LK::PthreadMutexLock(&m) != OK) {
				errors++;
				return;
			}
			const int g = gen;
			registered++;
			while (gen == g) {
				const int r = (i % 2) != 0 ? LK::PthreadCondTimedwait(&cv, &m, 5000000) : LK::PthreadCondWait(&cv, &m);
				if (r == LK::KERNEL_ERROR_ETIMEDOUT) {
					timeouts++;
					break;
				}
				if (r != OK) {
					errors++;
					break;
				}
			}
			woke++;
			LK::PthreadMutexUnlock(&m);
		}));
	}
	bool              sent = false;
	int               b_r  = -1;
	Clock::time_point t0 {};
	for (int k = 0; k < 5000 && !sent; k++) {
		if (LK::PthreadMutexLock(&m) != OK) {
			break;
		}
		if (registered == kWaiters) { // all of them are queued: each counted itself under m, then waited
			gen++;
			t0   = Clock::now();
			b_r  = LK::PthreadCondBroadcast(&cv);
			sent = true;
		}
		LK::PthreadMutexUnlock(&m);
		if (!sent) {
			std::this_thread::sleep_for(std::chrono::milliseconds(1));
		}
	}
	for (auto& th: waiters) {
		th.join();
	}
	const long long us = sent ? UsSince(t0) : -1;
	const bool ok = sent && b_r == OK && woke == kWaiters && errors.load() == 0 && timeouts.load() == 0 && us < 1000000;
	Report("broadcast wakes every waiter", ok,
	       Fmt("%d of %d woke (4 untimed, 4 timed), %d timed out, %d errors, all back in %lld us", woke, kWaiters,
	           timeouts.load(), errors.load(), us));
}

// ---- 9 -------------------------------------------------------------------------------------------------------------
void CaseTimedWaitTimeouts() {
	g_case = "timed waits time out and keep the mutex";
	LK::PthreadMutex m  = NewMutex("pth0401-c9", 1, 0);
	LK::PthreadCond  cv = NewCond("pth0401-c9");
	int              l1 = -1, r1 = -1, u1 = -1, l0 = -1, r0 = -1, u0 = -1, l2 = -1, r2 = -1, u2 = -1;
	long long        d1 = -1, d2 = -1;

	std::thread t = Spawn([&] {
		l1            = LK::PthreadMutexLock(&m);
		auto t0       = Clock::now();
		r1            = LK::PthreadCondTimedwait(&cv, &m, 30000);
		d1            = UsSince(t0);
		u1            = LK::PthreadMutexUnlock(&m); // OK only if the wait took the mutex back
		l0            = LK::PthreadMutexLock(&m);
		r0            = LK::PthreadCondTimedwait(&cv, &m, 0);
		u0            = LK::PthreadMutexUnlock(&m);
		timespec now {};
		::clock_gettime(CLOCK_REALTIME, &now); // the condition variable's default clock (KERNEL_CLOCK_REALTIME)
		LK::KernelTimespec deadline_abs {};
		deadline_abs.tv_sec  = static_cast<int64_t>(now.tv_sec);
		deadline_abs.tv_nsec = static_cast<int64_t>(now.tv_nsec) + 30000000;
		if (deadline_abs.tv_nsec >= 1000000000) {
			deadline_abs.tv_sec++;
			deadline_abs.tv_nsec -= 1000000000;
		}
		l2 = LK::PthreadMutexLock(&m);
		t0 = Clock::now();
		r2 = LK::PthreadCondTimedwaitAbs(&cv, &m, &deadline_abs);
		d2 = UsSince(t0);
		u2 = LK::PthreadMutexUnlock(&m);
	});
	t.join();

	const bool ok = l1 == OK && r1 == LK::KERNEL_ERROR_ETIMEDOUT && d1 >= 29000 && d1 < 1000000 && u1 == OK && l0 == OK &&
	                r0 == LK::KERNEL_ERROR_ETIMEDOUT && u0 == OK && l2 == OK && r2 == LK::KERNEL_ERROR_ETIMEDOUT &&
	                d2 >= 20000 && d2 < 1000000 && u2 == OK;
	Report("timed waits time out and keep the mutex", ok,
	       Fmt("30 ms relative: %s after %lld us, unlock %s; 0: %s, unlock %s; absolute now + 30 ms: %s after %lld us, unlock %s",
	           ErrName(r1), d1, ErrName(u1), ErrName(r0), ErrName(u0), ErrName(r2), d2, ErrName(u2)));
}

// ---- 10 ------------------------------------------------------------------------------------------------------------
void CaseTimedOutWriters() {
	g_case = "timed-out writers leave no waiting mark";
	LK::PthreadRwlock b = NewRwlock("pth0401-c10b"), a = NewRwlock("pth0401-c10a");
	constexpr int     kWriters = 8, kTries = 60, kProbes = 3;
	Flag              holds, release;
	int               h_lock = -1, h_un = -1;

	std::thread holder = Spawn([&] {
		h_lock = LK::PthreadRwlockRdlock(&b);
		holds.Set();
		release.Wait(20000);
		h_un = LK::PthreadRwlockUnlock(&b);
	});
	holds.Wait(10000);

	std::atomic<int>  timeouts {0}, acquired {0}, errors {0}, probes_ok {0}, probes_busy {0};
	std::atomic<bool> writers_done {false};
	std::vector<std::thread> writers, probes;
	for (int i = 0; i < kWriters; i++) {
		writers.push_back(Spawn([&, i] {
			for (int k = 0; k < kTries; k++) {
				const int r = LK::PthreadRwlockTimedwrlock(&b, 1000 + ((i + k) % 5) * 1000);
				if (r == LK::KERNEL_ERROR_ETIMEDOUT) {
					timeouts++;
				} else if (r == OK) {
					acquired++;
					LK::PthreadRwlockUnlock(&b);
				} else {
					errors++;
				}
			}
		}));
	}
	for (int j = 0; j < kProbes; j++) {
		probes.push_back(Spawn([&] {
			while (!writers_done.load()) {
				const int r = LK::PthreadRwlockTryrdlock(&b);
				if (r == OK) {
					probes_ok++;
					LK::PthreadRwlockUnlock(&b);
				} else if (r == LK::KERNEL_ERROR_EBUSY) {
					probes_busy++;
				} else {
					errors++;
				}
				std::this_thread::yield();
			}
		}));
	}
	for (auto& th: writers) {
		th.join();
	}
	writers_done = true;
	for (auto& th: probes) {
		th.join();
	}

	// No writer waits now: a thread that holds nothing reads at once although the holder still reads.
	int         f1 = -1, fu1 = -1, f2 = -1;
	std::thread fresh = Spawn([&] {
		f1 = LK::PthreadRwlockTryrdlock(&b);
		if (f1 == OK) {
			fu1 = LK::PthreadRwlockUnlock(&b);
		}
		f2 = LK::PthreadRwlockTimedwrlock(&b, 20000); // the holder still reads: times out, and leaves no mark either
	});
	fresh.join();
	release.Set();
	holder.join();

	// A write owner: readers time out behind it, also one that holds another read lock (the console refuses such a
	// reader only for a write owner, thr_umtx.h _thr_rwlock_tryrdlock).
	Flag        w_holds, w_release;
	int         wl = -1, wu = -1, rt = -1, ra = -1, rt2 = -1, rau = -1, f3 = -1, fu3 = -1;
	std::thread w = Spawn([&] {
		wl = LK::PthreadRwlockWrlock(&b);
		w_holds.Set();
		w_release.Wait(10000);
		wu = LK::PthreadRwlockUnlock(&b);
	});
	w_holds.Wait(10000);
	std::thread rd = Spawn([&] {
		rt  = LK::PthreadRwlockTimedrdlock(&b, 20000);
		ra  = LK::PthreadRwlockRdlock(&a);
		rt2 = LK::PthreadRwlockTimedrdlock(&b, 20000);
		rau = LK::PthreadRwlockUnlock(&a);
	});
	rd.join();
	w_release.Set();
	w.join();
	std::thread last = Spawn([&] {
		f3 = LK::PthreadRwlockTrywrlock(&b);
		if (f3 == OK) {
			fu3 = LK::PthreadRwlockUnlock(&b);
		}
	});
	last.join();

	const bool ok = h_lock == OK && timeouts.load() == kWriters * kTries && acquired.load() == 0 && errors.load() == 0 &&
	                f1 == OK && fu1 == OK && f2 == LK::KERNEL_ERROR_ETIMEDOUT && h_un == OK && wl == OK &&
	                rt == LK::KERNEL_ERROR_ETIMEDOUT && ra == OK && rt2 == LK::KERNEL_ERROR_ETIMEDOUT && rau == OK &&
	                wu == OK && f3 == OK && fu3 == OK;
	Report("timed-out writers leave no waiting mark", ok,
	       Fmt("%d of %d writer time-outs, %d acquired, %d errors; probes read %d, refused %d; after: a thread holding nothing "
	           "reads %s, a writer times out %s; behind a write owner: reader %s, reader holding another lock %s; then a "
	           "writer gets it %s",
	           timeouts.load(), kWriters * kTries, acquired.load(), errors.load(), probes_ok.load(), probes_busy.load(),
	           ErrName(f1), ErrName(f2), ErrName(rt), ErrName(rt2), ErrName(f3)));
}

} // namespace

int main() {
	const char* e = std::getenv("KYTY_BC5_PTHREAD_FIXES");
	g_on          = e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
	Log::Bc5SetLogging(false); // the pthread code's LOGF stays off stdout
	std::thread(Watchdog).detach();

	// The subsystems the pthread code needs, on a helper thread that is the "main thread" for their constructors.
	std::thread init([] {
		Common::ThreadsSubsystem::Instance()->Init(nullptr);
		LK::PthreadSubsystem::Instance()->Init(nullptr);
	});
	init.join();
	LK::PthreadInitSelfForMainThread(); // this thread makes the objects and drives some cases

	std::printf("pth0401: KYTY_BC5_PTHREAD_FIXES=%s, so %s\n", e != nullptr ? e : "(unset)", g_on ? "on" : "off");
	std::fflush(stdout);
	const auto start = Clock::now();

	CaseSameLockRecursion();
	CaseCrossLockReader();
	CaseCrossLockCycle();
	CaseRwlockStress();
	CaseCondRing();
	CaseProducerConsumer();
	CaseNoStaleWaiter();
	CaseBroadcast();
	CaseTimedWaitTimeouts();
	CaseTimedOutWriters();

	g_finished = true;
	const int n = g_cases.load();
	const int p = g_passed.load();
	if (p != n) {
		std::printf("pth0401: %s %d of %d passed in %lld ms; FAIL\n", g_on ? "on" : "off", p, n, UsSince(start) / 1000);
		std::fflush(stdout);
		_exit(1);
	}
	std::printf("pth0401: %s %d of %d; end\n", g_on ? "on" : "off", p, n);
	std::fflush(stdout);
	_exit(0);
}
