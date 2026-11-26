// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0415: CPU test of src/bc5/load_stat.hpp (tag ls415). Two processes, because every word is read once:
//   test0415 off            nothing set: the counters stay zero, the knobs read today's values, nothing is written
//   test0415 on <file>      KYTY_BC5_LOAD_STAT=<file> and the knobs set by the test itself before the first use
// The last part of "on" is a MODEL of the guest mutex of src/kernel/pthread.cpp (std::mutex + condition variable + owner
// field) with the spin window of NativeMutexLock copied by hand: it checks mutual exclusion and progress of that loop,
// not the host's function itself. Ends with "test0415: <passed> of <run>; end".
#include "bc5/load_stat.hpp"

#include <condition_variable>
#include <fstream>
#include <string>
#include <vector>

#if defined(__linux__)
#include <time.h>
#endif

namespace ls = bc5::load_stat;

static int g_run = 0, g_ok = 0;
static void check(bool v, const char* what) {
	g_run++;
	if (v) {
		g_ok++;
	} else {
		std::printf("FAIL: %s\n", what);
	}
}

static void put(const char* k, const char* v) {
#if defined(_WIN32)
	_putenv_s(k, v);
#else
	setenv(k, v, 1);
#endif
}

static void sleep_ms(int ms) {
	std::this_thread::sleep_for(std::chrono::milliseconds(ms));
}

static uint64_t n_of(unsigned c) {
	return ls::state().slot[c].n.load();
}
static uint64_t ns_of(unsigned c) {
	return ls::state().slot[c].ns.load();
}
static uint64_t items_of(unsigned c) {
	return ls::state().slot[c].items.load();
}

struct ModelMutex {
	std::mutex              m;
	std::condition_variable cv;
	const void*             owner = nullptr;
};

static void model_lock(ModelMutex* mutex, const void* self, uint64_t spin) {
	std::unique_lock lock(mutex->m);
	const bool       contended = mutex->owner != nullptr;
	if (contended && spin != 0) {
		const uint64_t t0 = ls::now_ns();
		for (;;) {
			lock.unlock();
			for (int k = 0; k < 32; k++) ls::cpu_relax();
			lock.lock();
			if (mutex->owner == nullptr) break;
			if (ls::now_ns() - t0 >= spin) break;
		}
	}
	while (mutex->owner != nullptr) mutex->cv.wait_for(lock, std::chrono::milliseconds(10));
	mutex->owner = self;
}

static void model_unlock(ModelMutex* mutex) {
	std::unique_lock lock(mutex->m);
	mutex->owner = nullptr;
	mutex->cv.notify_one();
}

static int run_off() {
	check(!ls::on(), "off: on() is false with nothing set");
	check(ls::begin() == 0, "off: begin() is 0");
	{
		ls::Scope s(ls::kAprRead);
		s.items = 4096;
	}
	ls::count(ls::kMutexLock);
	ls::flip(12.5);
	ls::mark("nothing");
	ls::apr_enter();
	ls::apr_leave();
	bool any = false;
	for (unsigned c = 0; c < ls::kCount; c++) any = any || n_of(c) != 0 || ns_of(c) != 0 || items_of(c) != 0;
	check(!any, "off: every slot is zero after scopes, counts, a flip and an apr pair");
	check(ls::state().file == nullptr, "off: no file is open");
	check(ls::ring_poll_us() == 200, "off: the ring poll is 200 us");
	check(ls::ring_spin_ns() == 0, "off: no ring spin");
	check(ls::mutex_spin_ns() == 0, "off: no mutex spin");
	for (unsigned c = 0; c < ls::kCount; c++) check(ls::delay_ns_of(c) == 0, "off: no delay for any cause");
	const uint64_t t0 = ls::now_ns();
	for (int k = 0; k < 1000; k++) ls::delay(ls::kAmmCmd);
	check(ls::now_ns() - t0 < 5'000'000ull, "off: 1000 delays take under 5 ms");
	std::mutex m;
	{
		ls::CountedLock<std::mutex> l(m, ls::kMemLockWait);
		check(!m.try_lock(), "off: CountedLock holds the mutex");
	}
	check(m.try_lock(), "off: CountedLock released the mutex");
	m.unlock();
	// The grammar of the numeric words.
	put("T0415_A", "");
	put("T0415_B", "0");
	put("T0415_C", "abc");
	put("T0415_D", "12x");
	put("T0415_E", "999999999");
	put("T0415_F", "150");
	check(ls::env_num("T0415_NONE", 7, 100) == 7, "env_num: unset is the default");
	check(ls::env_num("T0415_A", 7, 100) == 7, "env_num: empty is the default");
	check(ls::env_num("T0415_B", 7, 100) == 0, "env_num: 0 is 0");
	check(ls::env_num("T0415_C", 7, 100) == 7, "env_num: a word is the default");
	check(ls::env_num("T0415_D", 7, 100) == 7, "env_num: trailing text is the default");
	check(ls::env_num("T0415_E", 7, 100) == 7, "env_num: over the cap is the default");
	check(ls::env_num("T0415_F", 7, 1000) == 150, "env_num: a number is read");
	check(!ls::env_set(nullptr) && !ls::env_set("") && !ls::env_set("0") && ls::env_set("1") && ls::env_set("00") && ls::env_set("/tmp/x"), "env_set: unset, empty and 0 are off");
	return 0;
}

static int run_on(const char* path) {
	std::remove(path);
	put("KYTY_BC5_LOAD_STAT", path);
	put("KYTY_BC5_LOAD_DELAY", "amm_cmd:2000");
	put("KYTY_BC5_RING_POLL_US", "0"); // 0 is not a period: today's 200
	put("KYTY_BC5_RING_SPIN_US", "150");
	put("KYTY_BC5_MUTEX_SPIN_US", "40");
	check(ls::on(), "on: on() is true");
	check(ls::begin() != 0, "on: begin() is a time");
	check(ls::ring_poll_us() == 200, "on: a ring poll of 0 reads as 200");
	check(ls::ring_spin_ns() == 150'000, "on: the ring spin is 150 us");
	check(ls::mutex_spin_ns() == 40'000, "on: the mutex spin is 40 us");
#if defined(__linux__)
	{
		timespec ts {};
		clock_gettime(CLOCK_MONOTONIC, &ts);
		const uint64_t a = static_cast<uint64_t>(ts.tv_sec) * 1'000'000'000ull + static_cast<uint64_t>(ts.tv_nsec);
		const uint64_t b = ls::now_ns();
		check(b >= a && b - a < 50'000'000ull, "on: now_ns() is CLOCK_MONOTONIC");
	}
#endif
	{
		ls::Scope s(ls::kAprRead);
		s.items = 4096;
		sleep_ms(20);
	}
	{
		ls::Scope s(ls::kAprRead);
		s.items = 100;
		sleep_ms(5);
	}
	check(n_of(ls::kAprRead) == 2 && items_of(ls::kAprRead) == 4196, "on: two scopes, their items summed");
	check(ns_of(ls::kAprRead) >= 25'000'000ull && ns_of(ls::kAprRead) < 400'000'000ull, "on: the scopes' time is at least the 25 ms slept");
	check(ls::state().slot[ls::kAprRead].max_ns.load() >= 20'000'000ull, "on: the longest single time is the 20 ms scope");
	ls::count(ls::kSemaSignal, 9);
	ls::count(ls::kSemaSignal, 3);
	check(n_of(ls::kSemaSignal) == 2 && items_of(ls::kSemaSignal) == 12 && ns_of(ls::kSemaSignal) == 0, "on: counts with items and no time");
	// Outstanding command buffers: two overlapping ones are one busy stretch.
	ls::apr_enter();
	sleep_ms(15);
	ls::apr_enter();
	sleep_ms(15);
	ls::apr_leave();
	check(n_of(ls::kAprBusy) == 0, "on: one of two buffers left: still busy");
	ls::apr_leave();
	check(n_of(ls::kAprBusy) == 1 && ns_of(ls::kAprBusy) >= 30'000'000ull && ns_of(ls::kAprBusy) < 400'000'000ull, "on: one busy stretch of at least 30 ms");
	ls::apr_enter();
	ls::apr_leave();
	check(n_of(ls::kAprBusy) == 2, "on: a second stretch counts again");
	// The delay: only its cause.
	check(ls::delay_ns_of(ls::kAmmCmd) == 2'000'000ull, "on: the delay of amm_cmd is 2 ms");
	bool other = false;
	for (unsigned c = 0; c < ls::kCount; c++) other = other || (c != ls::kAmmCmd && ls::delay_ns_of(c) != 0);
	check(!other, "on: no other cause has a delay");
	uint64_t t0 = ls::now_ns();
	ls::delay(ls::kAmmCmd);
	const uint64_t d = ls::now_ns() - t0;
	check(d >= 2'000'000ull && d < 100'000'000ull, "on: delay(amm_cmd) takes at least 2 ms");
	t0 = ls::now_ns();
	ls::delay(ls::kAprBuffer);
	check(ls::now_ns() - t0 < 1'000'000ull, "on: delay(apr_buffer) takes nothing");
	// A contended lock's wait is counted, an uncontended one is not.
	std::mutex m;
	{
		ls::CountedLock<std::mutex> l(m, ls::kMemLockWait);
	}
	check(n_of(ls::kMemLockWait) == 0, "on: an uncontended lock counts no wait");
	{
		std::thread holder([&m] {
			m.lock();
			sleep_ms(40);
			m.unlock();
		});
		sleep_ms(10);
		{
			ls::CountedLock<std::mutex> l(m, ls::kMemLockWait);
		}
		holder.join();
	}
	check(n_of(ls::kMemLockWait) == 1 && ns_of(ls::kMemLockWait) >= 15'000'000ull, "on: a contended lock counts its wait");
	{
		std::recursive_mutex        rm;
		ls::CountedLock<std::recursive_mutex> a(rm, ls::kMemLockWait);
		ls::CountedLock<std::recursive_mutex> b(rm, ls::kMemLockWait);
		check(n_of(ls::kMemLockWait) == 1, "on: a recursive second lock by the owner is not a wait");
	}
	ls::flip(12.5);
	ls::flip(12.75);
	check(n_of(ls::kFlip) == 2 && ls::state().journal_t_us.load() == 12'750'000ull, "on: flips and the journal's time");
	ls::mark("key press cross");
	// Many threads on one slot: nothing lost.
	{
		std::vector<std::thread> ts;
		for (int k = 0; k < 8; k++) ts.emplace_back([] { for (int i = 0; i < 100000; i++) ls::add(ls::kMutexLock, 3, 2); });
		for (auto& t: ts) t.join();
	}
	check(n_of(ls::kMutexLock) == 800000 && ns_of(ls::kMutexLock) == 2400000 && items_of(ls::kMutexLock) == 1600000, "on: 8 threads x 100,000 adds, none lost");
	check(ls::state().slot[ls::kMutexLock].max_ns.load() == 3, "on: the longest of equal times");
	// The writer: a line per second with a field per cause.
	sleep_ms(2300);
	{
		std::ifstream f(path);
		std::string   line, last_s, mark;
		int           header = 0, s_lines = 0;
		while (std::getline(f, line)) {
			if (line.rfind("# ", 0) == 0) header++;
			if (line.rfind("s mono_ns=", 0) == 0) {
				s_lines++;
				last_s = line;
			}
			if (line.rfind("mark mono_ns=", 0) == 0) mark = line;
		}
		check(header == 1, "file: one header line");
		check(s_lines >= 2 && s_lines <= 3, "file: two or three second lines in 2.3 s");
		bool all = true;
		for (unsigned c = 0; c < ls::kCount; c++) all = all && last_s.find(std::string(" ") + ls::kNames[c] + "=") != std::string::npos;
		check(all, "file: a field for every cause");
		check(last_s.find(" mutex_lock=800000,2400000,") != std::string::npos, "file: the slot's count and time as written");
		check(last_s.find(" jt_us=12750000 ") != std::string::npos, "file: the journal's time");
		check(mark.find(" jt_us=12750000 key press cross") != std::string::npos, "file: the mark line");
		check(last_s.size() < 6000, "file: a second line fits its buffer");
	}
	// The model of the guest mutex with the spin window: mutual exclusion and progress.
	for (const uint64_t spin: {uint64_t {0}, uint64_t {40'000}}) {
		ModelMutex               mu;
		long                     inside = 0, total = 0;
		bool                     broken = false;
		std::vector<std::thread> ts;
		for (int k = 0; k < 8; k++) {
			ts.emplace_back([&, k] {
				for (int i = 0; i < 20000; i++) {
					model_lock(&mu, &ts + k + 1, spin);
					if (++inside != 1) broken = true;
					total++;
					if ((i & 1023) == 0) std::this_thread::yield();
					--inside;
					model_unlock(&mu);
				}
			});
		}
		for (auto& t: ts) t.join();
		check(!broken && total == 160000 && mu.owner == nullptr, spin == 0 ? "model mutex without spin: exclusion, 160,000 sections" : "model mutex with a 40 us spin: exclusion, 160,000 sections");
	}
	return 0;
}

int main(int argc, char** argv) {
	if (argc >= 2 && std::strcmp(argv[1], "off") == 0) {
		run_off();
	} else if (argc >= 3 && std::strcmp(argv[1], "on") == 0) {
		run_on(argv[2]);
	} else {
		std::printf("usage: test0415 off | on <file>\n");
		return 2;
	}
	std::printf("test0415: %d of %d; end\n", g_ok, g_run);
	return g_ok == g_run ? 0 : 1;
}
