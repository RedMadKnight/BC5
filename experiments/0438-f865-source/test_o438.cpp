// BC5 experiment 0438 (tag o438): a standalone test of o438.hpp's bookkeeping. test_o438.sh supplies stub POSIX headers
// on the laptop (a thread's name and tid come from the test). Cases:
// 1. a Render Thread wait on an object signalled by a "worker" thread: counted as blocked, waker = the worker;
// 2. a nested wait (a cond wait re-locking its mutex) counts once, as the outer function;
// 3. a thread that is neither role records nothing;
// 4. a frame over 100 ms prints one frame line with the wait inside it; a short frame prints none;
// 5. BC5_0438_OUTSIDE unset: nothing is recorded.
// Built a second time with -DBC5_LEAN: the macros are empty and the test only checks that it compiles and runs.
#include <atomic>
#include <chrono>
#include <cstdio>
#include <string>
#include <thread>
#include <vector>

#include "o438.hpp"

#ifdef BC5_LEAN
int main() {
	int x = 0;
	(void)x;
	BC5_O438_WAIT(kWaitSema, &x);
	BC5_O438_SIGNAL(&x);
	BC5_O438_FLIP();
	std::printf("lean: the macros are empty; PASS\n");
	return 0;
}
#else
static int fails = 0;
#define CHECK(c)                                             \
	do {                                                     \
		if (!(c)) {                                          \
			std::printf("FAIL line %d: %s\n", __LINE__, #c); \
			fails++;                                         \
		}                                                    \
	} while (0)

int obj_sema = 0, obj_mutex = 0, obj_cond = 0;
static void wait_on(void* o, int ms) {
	BC5_O438_WAIT(kWaitSema, o);
	std::this_thread::sleep_for(std::chrono::milliseconds(ms));
}
// a wait that ends because of a post, as a semaphore wait does: blocked until *posted, at least ms. The waker case
// once slept a fixed 20 ms against a worker's 5-ms sleep and post; on the laptop the worker's thread start and sleep
// took ~40 ms, the post landed after the wait, and the case failed with waker 0 (a race of the test, not of o438).
static void wait_until_posted(void* o, const std::atomic<bool>* posted, int ms) {
	BC5_O438_WAIT(kWaitSema, o);
	const auto t0 = std::chrono::steady_clock::now();
	while (!posted->load() || std::chrono::steady_clock::now() - t0 < std::chrono::milliseconds(ms)) std::this_thread::sleep_for(std::chrono::milliseconds(1));
}
static void cond_wait(int ms) { // outer cond wait with an inner mutex lock
	BC5_O438_WAIT(kCondWait, &obj_cond);
	std::this_thread::sleep_for(std::chrono::milliseconds(ms));
	{
		BC5_O438_WAIT(kMutexLock, &obj_mutex);
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	}
}

int main() {
	using namespace bc5::o438;
	const bool enabled = on();
	std::printf("BC5_0438_OUTSIDE %s\n", enabled ? "1" : "unset");
	BC5_O438_FLIP(); // the first flip: the clock starts
	std::thread render([&] {
		stub_set_name("Render Thread", 1001);
		std::atomic<bool> posted {false};
		std::thread       worker([&posted] {
            stub_set_name("Job Hi 0", 2002);
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
            BC5_O438_SIGNAL(&obj_sema); // the worker posts; the Render Thread's wait ends after it
            posted = true;
		});
		wait_until_posted(&obj_sema, &posted, 20);
		worker.join();
		cond_wait(5);
	});
	render.join();
	std::thread other([] {
		stub_set_name("AK::AudioMgr", 3003);
		wait_on(&obj_sema, 5);
	});
	other.join();
	{
		Rec&            R = rec();
		std::lock_guard lk(R.m);
		if (enabled) {
			CHECK(R.tot[1][kWaitSema].n == 1 && R.tot[1][kWaitSema].blocked == 1);              // case 1
			CHECK((R.wake[1].count({static_cast<int>(kWaitSema), 2002u}) == 1));                  // waker = the worker
			CHECK(R.tot[1][kCondWait].n == 1 && R.tot[1][kMutexLock].n == 0);                    // case 2
			CHECK(R.tot[0][kWaitSema].n == 0 && R.tot[2][kWaitSema].n == 0);                    // case 3
		} else {
			CHECK(R.tot[1][kWaitSema].n == 0 && R.tot[1][kCondWait].n == 0); // case 5
		}
	}
	// case 4: the frame since the first flip lasted > 100 ms only if we wait; make it so, then a short one
	std::this_thread::sleep_for(std::chrono::milliseconds(110));
	stub_capture(true);
	BC5_O438_FLIP();
	BC5_O438_FLIP();
	const std::string out = stub_captured();
	stub_capture(false);
	std::printf("%s", out.c_str());
	if (enabled) {
		CHECK(out.find("o438 (exp 0438): frame of") != std::string::npos);
		CHECK(out.find("KernelWaitSema 1/1 calls") != std::string::npos);
		CHECK(out.find("Job Hi 0:2002") != std::string::npos);
		size_t n = 0;
		for (size_t p = out.find("frame of"); p != std::string::npos; p = out.find("frame of", p + 1)) n++;
		CHECK(n == 1); // the short frame prints nothing
	} else {
		CHECK(out.empty());
	}
	std::printf("%s (%d failures)\n", fails == 0 ? "PASS" : "FAIL", fails);
	return fails == 0 ? 0 : 1;
}
#endif
