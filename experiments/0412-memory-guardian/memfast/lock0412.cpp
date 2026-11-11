// BC5 experiment 0412: CPU test of lock0412.inc (the counting device mutex, tag lk412).
// Six named threads take the mutex 20,000 times each around a non-atomic counter, with the switch on (the test sets
// BC5_GUARD_LOCK_STAT=1 before first use) and checks: mutual exclusion (the counter is exact, and a flag is never seen
// set on entry), the acquisitions sum to the number of locks, the per-holder wait times sum to the waited time, the
// time held is no more than the wall-clock time, try_lock works, and a report prints a line per thread name.
// build: g++ -std=c++20 -O1 -Wall -Wextra -Werror -pthread lock0412.cpp -o lock0412
#include <atomic>
#include <cinttypes>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <pthread.h>
#include <thread>
#include <time.h>
#include <vector>

static int g_lines = 0;
static void test_print(const char* fmt, ...) __attribute__((format(printf, 1, 2)));
static void test_print(const char* fmt, ...) {
	char    buf[1024];
	va_list ap;
	va_start(ap, fmt);
	std::vsnprintf(buf, sizeof(buf), fmt, ap);
	va_end(ap);
	g_lines++;
	if (g_lines <= 8) std::fputs(buf, stdout);
}
#define LK412_PRINT test_print
#include "lock0412.inc"

static uint64_t g_checks = 0, g_ok = 0;
static void check(bool c, const char* what) {
	g_checks++;
	if (c) g_ok++;
	else std::printf("FAIL: %s\n", what);
}

int main() {
	setenv("BC5_GUARD_LOCK_STAT", "1", 1);
	check(lk412::on(), "the switch reads as on");
	static lk412::Mutex mu;
	static uint64_t     counter = 0;
	static bool         inside  = false;
	static std::atomic<uint64_t> clashes {0};
	const int      threads = 6, rounds = 20000;
	const uint64_t t0      = lk412::now_ns();
	std::vector<std::thread> ts;
	for (int t = 0; t < threads; t++) {
		ts.emplace_back([t] {
			char name[16];
			std::snprintf(name, sizeof(name), "lk-test-%d", t % 3); // two threads per name: names, not threads, are counted
			pthread_setname_np(pthread_self(), name);
			for (int i = 0; i < rounds; i++) {
				std::lock_guard lock(mu);
				if (inside) clashes++;
				inside = true;
				counter++;
				if ((i & 1023) == 0) { timespec d {0, 20000}; nanosleep(&d, nullptr); } // some holds long enough to be waited behind
				inside = false;
			}
		});
	}
	for (auto& t: ts) t.join();
	const uint64_t wall = lk412::now_ns() - t0;
	check(counter == static_cast<uint64_t>(threads) * rounds, "the counter is exact");
	check(clashes.load() == 0, "no two threads inside");
	check(mu.total_acq() == static_cast<uint64_t>(threads) * rounds, "acquisitions sum to the locks taken");
	check(mu.total_behind_ns() == mu.total_wait_ns(), "the waits behind holders sum to the time waited");
	check(mu.total_wait_ns() > 0, "some waiting was seen");
	check(mu.total_hold_ns() <= wall, "the time held is within the wall-clock time");
	check(mu.names() == 3, "three thread names");
	check(mu.try_lock(), "try_lock on a free mutex");
	std::thread([] { check(!mu.try_lock(), "try_lock on a held mutex fails"); }).join();
	mu.unlock();
	check(mu.total_acq() == static_cast<uint64_t>(threads) * rounds + 1, "try_lock counted");
	std::printf("lock0412: %" PRIu64 " of %" PRIu64 "; end\n", g_ok, g_checks);
	return g_ok == g_checks ? 0 : 1;
}
