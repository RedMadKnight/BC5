// BC5 experiment 0438 (tag w438): a standalone test of the watcher's hand-over (namespace w438, cut unchanged from the
// generated unit by test_w438.sh). Cases:
// 1. a move wakes the queue's submitter at once (well under its timeout); no move: it waits out its timeout;
// 2. a move seen while the submitter was busy is not lost (it returns at once on its next wait);
// 3. the same pointer twice is one move;
// 4. claim() starts one submitter per queue;
// 5. the kick wakes the watcher's sleep at once;
// 6. the switches: unset = on; BC5_0438_WATCHER=0 = off (and the kick off with it).
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <mutex>
#include <thread>

#include "w438_cut.inc"

static int fails = 0;
#define CHECK(c)                                             \
	do {                                                     \
		if (!(c)) {                                          \
			std::printf("FAIL line %d: %s\n", __LINE__, #c); \
			fails++;                                         \
		}                                                    \
	} while (0)

static double ms_since(std::chrono::steady_clock::time_point t) {
	return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t).count();
}

int main() {
	std::printf("BC5_0438_WATCHER %s, BC5_0438_KICK %s\n", w438::on() ? "on" : "off", w438::kick_on() ? "on" : "off");
	if (!w438::on()) {
		CHECK(!w438::kick_on());
		std::printf("%s (%d failures)\n", fails == 0 ? "PASS" : "FAIL", fails);
		return fails == 0 ? 0 : 1;
	}
	// 1. a move wakes the submitter at once
	{
		const uint64_t s0 = w438::seq_of(3);
		std::atomic<double> woke {-1};
		std::thread sub([&] {
			const auto t = std::chrono::steady_clock::now();
			const uint64_t s1 = w438::wait_move(3, s0, 500'000); // up to 500 ms
			woke = s1 != s0 ? ms_since(t) : -2.0;
		});
		std::this_thread::sleep_for(std::chrono::milliseconds(20));
		CHECK(w438::observe(3, 100));
		sub.join();
		CHECK(woke.load() >= 15.0 && woke.load() < 100.0); // woken by the move (about 20 ms), not the 500-ms timeout
		std::printf("case 1: woken after %.3f ms\n", woke.load());
		// no move: the timeout
		const auto t = std::chrono::steady_clock::now();
		const uint64_t s2 = w438::seq_of(3);
		CHECK(w438::wait_move(3, s2, 30'000) == s2);
		CHECK(ms_since(t) >= 25.0);
	}
	// 2. a move while busy is not lost
	{
		const uint64_t before = w438::seq_of(3); // the submitter takes this before its pass
		CHECK(w438::observe(3, 101));            // the watcher sees a move during the pass
		const auto t = std::chrono::steady_clock::now();
		CHECK(w438::wait_move(3, before, 500'000) != before);
		CHECK(ms_since(t) < 5.0);
	}
	// 3. the same pointer is one move
	CHECK(!w438::observe(3, 101));
	CHECK(w438::observe(3, 102));
	// 4. one submitter per queue
	CHECK(w438::claim(5));
	CHECK(!w438::claim(5));
	CHECK(w438::claim(6));
	CHECK(!w438::claim(-1) && !w438::claim(w438::kSlots));
	// 5. the kick wakes the watcher
	{
		uint64_t k0 = w438::watcher_sleep(0, 1); // the current kick sequence
		std::atomic<double> woke {-1};
		std::thread wat([&] {
			const auto t = std::chrono::steady_clock::now();
			w438::watcher_sleep(k0, 500'000);
			woke = ms_since(t);
		});
		std::this_thread::sleep_for(std::chrono::milliseconds(20));
		w438::kick();
		wat.join();
		CHECK(woke.load() >= 15.0 && woke.load() < 100.0);
		std::printf("case 5: the watcher woken after %.3f ms\n", woke.load());
		CHECK(w438::g_kick_wakes().load() == 1);
	}
	std::printf("hand-overs %llu\n", static_cast<unsigned long long>(w438::g_handoffs().load()));
	std::printf("%s (%d failures)\n", fails == 0 ? "PASS" : "FAIL", fails);
	return fails == 0 ? 0 : 1;
}
