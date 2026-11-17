// BC5 exp 0429: a stand-in test of candidate F (fastmutex0429.cpp) with the host's types replaced by minimal stand-ins.
// Built and run on the box (Linux, futex): g++ -std=c++20 -O2 -pthread -Wall -Wextra -Werror test_fm0429.cpp
// Cases: 8 threads x 200,000 rounds on one mutex, half taking it as the title's wrapper does (spinning trylock, then
// lock), half by lock; a plain counter must end exact. A recursive mutex (type 2) locked three times needs three
// unlocks; a non-owner unlock is EPERM; a timed lock on a held mutex times out near its bound; trylock on a held mutex
// is EBUSY. Exit 0 when all pass.
#include <algorithm>
#include <atomic>
#include <cerrno>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <vector>
#include <sys/syscall.h>
#include <unistd.h>
#include <x86intrin.h>

namespace bc5::env_rule {
inline bool on(const char* e) {
	return e != nullptr && *e != 0 && *e != '0';
}
} // namespace bc5::env_rule
constexpr uint32_t SIGNAL_APC_POLL_MICROS = 10000;
static void        KernelDispatchPendingSignalForCurrentThread() {}
struct PthreadPrivate {
	int id;
};
using Pthread        = PthreadPrivate*;
using KernelUseconds = uint32_t;
constexpr int OK     = 0;
struct PthreadMutexPrivate {
	Pthread               owner = nullptr;
	uint32_t              count = 0;
	int                   type  = 1;
	std::atomic<uint32_t> bc5_word {0};
};
#include "fastmutex0429.cpp"

static int fails = 0;
static void check(bool ok, const char* what) {
	std::printf("%s %s\n", ok ? "ok  " : "FAIL", what);
	fails += ok ? 0 : 1;
}

int main() {
	setenv("KYTY_BC5_0429_FAST_MUTEX", std::getenv("FM_MODE") != nullptr ? std::getenv("FM_MODE") : "1", 1);
	setenv("KYTY_BC5_0429_WAITS", "1", 1);
	check(Bc5FastMutex(), "the switch reads on");
	PthreadMutexPrivate m;
	long                counter = 0;
	constexpr int       kThreads = 8, kRounds = 200000;
	std::vector<std::thread> ts;
	std::vector<PthreadPrivate> selves(kThreads);
	for (int t = 0; t < kThreads; t++) {
		selves[t].id = t;
		ts.emplace_back([&, t] {
			Pthread self = &selves[t];
			for (int i = 0; i < kRounds; i++) {
				if (t % 2 == 0) { // the title's wrapper: up to 8 rounds of 16 pause + trylock, then lock
					bool got = false;
					for (int r = 0; r < 8 && !got; r++) {
						for (int p = 0; p < 16; p++) {
							_mm_pause();
						}
						got = Bc5FastMutexTrylock(&m, self) == OK;
					}
					if (!got && Bc5FastMutexLock(&m, self, nullptr) != OK) {
						std::abort();
					}
				} else if (Bc5FastMutexLock(&m, self, nullptr) != OK) {
					std::abort();
				}
				counter++;
				if (Bc5FastMutexUnlock(&m, self, nullptr) != OK) {
					std::abort();
				}
			}
		});
	}
	for (auto& th: ts) {
		th.join();
	}
	check(counter == static_cast<long>(kThreads) * kRounds, "8 threads x 200000: the counter is exact");
	check(m.bc5_word.load() == 0 && m.owner == nullptr, "the word is free at the end");

	PthreadPrivate a {100}, b {101};
	PthreadMutexPrivate r;
	r.type = 2;
	check(Bc5FastMutexLock(&r, &a, nullptr) == OK && Bc5FastMutexLock(&r, &a, nullptr) == OK && Bc5FastMutexTrylock(&r, &a) == OK,
	      "recursive: three takes by the owner");
	check(Bc5FastMutexUnlock(&r, &b, nullptr) == EPERM, "recursive: a non-owner unlock is EPERM");
	check(Bc5FastMutexUnlock(&r, &a, nullptr) == OK && r.bc5_word.load() != 0, "recursive: one unlock keeps it held");
	check(Bc5FastMutexUnlock(&r, &a, nullptr) == OK && Bc5FastMutexUnlock(&r, &a, nullptr) == OK && r.bc5_word.load() == 0,
	      "recursive: the third unlock frees it");

	PthreadMutexPrivate h;
	check(Bc5FastMutexLock(&h, &a, nullptr) == OK, "timed: held by a");
	check(Bc5FastMutexTrylock(&h, &b) == EBUSY, "timed: trylock by b is EBUSY");
	KernelUseconds us = 30000;
	const auto     t0 = std::chrono::steady_clock::now();
	const int      rc = Bc5FastMutexLock(&h, &b, &us);
	const auto     ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - t0).count();
	check(rc == ETIMEDOUT && ms >= 25 && ms < 200, "timed: b times out near 30 ms");
	KernelUseconds zero = 0;
	check(Bc5FastMutexLock(&h, &b, &zero) == ETIMEDOUT, "timed: a zero timeout does not wait");
	std::thread waker([&] {
		std::this_thread::sleep_for(std::chrono::milliseconds(20));
		Bc5FastMutexUnlock(&h, &a, nullptr);
	});
	KernelUseconds big = 2000000;
	check(Bc5FastMutexLock(&h, &b, &big) == OK && h.owner == &b, "timed: b gets it when a unlocks");
	waker.join();
	check(Bc5FastMutexUnlock(&h, &b, nullptr) == OK && h.bc5_word.load() == 0, "timed: free after b's unlock");
	std::printf("== %d failed\n", fails);
	return fails == 0 ? 0 : 1;
}
