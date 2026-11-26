// BC5 experiment 0412: CPU test of lock0412.inc (the counting device mutex, tag lk412).
// Six named threads take the mutex 20,000 times each around a non-atomic counter, with the switch on (the test sets
// BC5_GUARD_LOCK_STAT=1 before first use) and checks: mutual exclusion (the counter is exact, and a flag is never seen
// set on entry), the acquisitions sum to the number of locks, the per-holder wait times sum to the waited time, the
// time held is no more than the wall-clock time, try_lock works, and a report prints a line per thread name.
// build: g++ -std=c++20 -O1 -Wall -Wextra -Werror -pthread lock0412.cpp -o lock0412
#include <atomic>
#include <chrono>
#include <string>
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
	if (g_lines <= 8 || std::strncmp(buf, "lock hold", 9) == 0 || std::strncmp(buf, "lock wait", 9) == 0 || std::strncmp(buf, "gap (", 5) == 0) std::fputs(buf, stdout);
}
#define LK412_PRINT test_print
static double test_now() { return 1.5; }
#define LK412_NOW test_now
#define GP412_PRINT test_print
#define GP412_NOW test_now
#include "gap0412.inc"
#include "lock0412.inc"

static uint64_t g_checks = 0, g_ok = 0;
static void check(bool c, const char* what) {
	g_checks++;
	if (c) g_ok++;
	else std::printf("FAIL: %s\n", what);
}

int main() {
	setenv("BC5_GUARD_LOCK_STAT", "1", 1);
	setenv("BC5_GUARD_GAP_STAT", "40", 1);
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
				if ((i & 7) == 0) mu.mark(1 + (i >> 3) % 7);
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
	check(mu.total_part_ns() == mu.total_hold_ns(), "the parts sum to the time held");
	check(mu.long_holds() == 0, "no long hold yet");
	{
		const int before = g_lines;
		std::thread waiter;
		{
			std::lock_guard lock(mu);
			mu.mark(2);
			waiter = std::thread([] { pthread_setname_np(pthread_self(), "lk-waiter"); std::lock_guard l2(mu); });
			timespec d {0, 60000000};
			nanosleep(&d, nullptr);
		}
		waiter.join();
		check(mu.long_holds() == 1, "a hold of 60 ms is a long hold");
		check(mu.long_waits() == 1, "the wait behind it is a long wait");
		check(g_lines == before + 2, "one line for the hold, one for the wait");
	}
	check(mu.try_lock(), "try_lock on a free mutex");
	std::thread([] { check(!mu.try_lock(), "try_lock on a held mutex fails"); }).join();
	mu.unlock();
	check(mu.total_acq() == static_cast<uint64_t>(threads) * rounds + 3, "try_lock and the two long-hold locks counted");
	{ // the gap classifier: exclusive scopes, and one line for a gap over the limit (40 ms here)
		check(gp412::on() && gp412::limit_ns() == 40000000ull, "the gap switch reads 40 ms");
		const int me = gp412::slot();
		check(me == gp412::kSlots - 1, "the main thread is in the slot of the others");
		const uint64_t a0 = gp412::g_ns[me][gp412::kSubmit].load(), b0 = gp412::g_ns[me][gp412::kDrain].load();
		const uint64_t t0 = gp412::now_ns();
		gp412::flip();
		{
			gp412::Scope outer(gp412::kSubmit);
			timespec d {0, 20000000};
			nanosleep(&d, nullptr);
			for (int i = 0; i < 30; i++) gp412::poll_sleep(1000, gp412::kDrain);
			nanosleep(&d, nullptr);
		}
		const uint64_t wall = gp412::now_ns() - t0;
		const uint64_t a = gp412::g_ns[me][gp412::kSubmit].load() - a0, b = gp412::g_ns[me][gp412::kDrain].load() - b0;
		check(b >= 30000000ull, "thirty sleeps of 1 ms count as at least 30 ms of the inner cause");
		check(a >= 40000000ull && a < 60000000ull, "the outer cause has its own 40 ms, not the inner time");
		check(a + b <= wall, "the two causes together are within the wall-clock time");
		const uint64_t gaps = gp412::g_gaps;
		const int      lines = g_lines;
		gp412::flip();
		check(gp412::g_gaps == gaps + 1 && g_lines == lines + 1, "a gap over the limit writes one line");
		gp412::flip();
		check(gp412::g_gaps == gaps + 1 && g_lines == lines + 1, "a flip right after it writes none");
	}
	std::printf("lock0412: %" PRIu64 " of %" PRIu64 "; end\n", g_ok, g_checks);
	return g_ok == g_checks ? 0 : 1;
}
