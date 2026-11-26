// BC5 experiment 0438 (tag h438): a standalone test of h438.hpp's per-frame records. test_h438.sh supplies the stub
// POSIX headers of test_o438.sh plus a thread-CPU clock and a /proc reader (both from the test). Cases:
// 1. the Render Thread's gc calls by code (a nested call counts once, as its outer code), the flip span with its drain,
//    a lock wait of 30 ms recorded by name and a fast lock counted without a wait, the /proc deltas per frame, and
//    o438's guest-sync blocked time in the same line (BC5_0438_OUTSIDE=1);
// 2. a thread that is not the Render Thread records nothing;
// 3. BC5_0438_HOSTWAIT unset: no file;
// 4. built a second time with -DBC5_LEAN: the macros are empty (the lock statement still runs);
// 5. f438: a "bc5-chainwd" thread holds a slot's flush lock 30 ms as a foreign flush (why 9), in F16 phase 1; the Render
//    Thread's wait goes to its frame as "flush<-bc5-chainwd:2003/hold-wd/backpressure", and its own recursive re-entry
//    records no wait.
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

// the stubs the header reads
inline std::atomic<uint64_t> g_cpu {0}, g_runq {0}, g_slices {0}, g_minflt {0}, g_majflt {0};
inline uint64_t stub_cpu() { return g_cpu.load(); }
inline bool     stub_proc(uint32_t, uint64_t& cpu, uint64_t& runq, uint64_t& slices, uint64_t& minflt, uint64_t& majflt) {
    cpu    = g_cpu.load();
    runq   = g_runq.load();
    slices = g_slices.load();
    minflt = g_minflt.load();
    majflt = g_majflt.load();
    return true;
}
#define BC5_H438_CPU_STUB  stub_cpu
#define BC5_H438_PROC_STUB stub_proc
#include "h438.hpp"

struct FakeSlot { // chain_submit's ChainSlot: the members f438 uses
	std::recursive_mutex flush_mu;
	std::atomic<int>     f16_phase {0}; // exp 0430 F16
#ifndef BC5_LEAN
	bc5::f438::Slot f438;
#endif
};
static void submitter(FakeSlot& s, int why, bool foreign, int hold_ms, bool nest) { // chain_submit's shape
	BC5_F438_FLUSH_LOCK(s, why, foreign);
	std::this_thread::sleep_for(std::chrono::milliseconds(hold_ms));
	if (nest) submitter(s, why, foreign, 0, false); // submit_now -> wait_jobs -> chain_flush on the same thread
}
#ifdef BC5_LEAN
int main() {
	FakeSlot fs;
	submitter(fs, 0, false, 0, true);
	std::mutex m;
	int        x = 0;
	BC5_H438_GC(0xc0188132);
	BC5_H438_FLIPSPAN();
	BC5_H438_DRAIN_BEGIN()
	x++;
	BC5_H438_DRAIN_END()
	BC5_H438_LOCK_ID(0, "m", std::lock_guard lk(m));
	x++;
	std::printf("lean: the macros are empty, x %d; %s\n", x, x == 2 ? "PASS" : "FAIL");
	return x == 2 ? 0 : 1;
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

static std::mutex g_a, g_b;
static FakeSlot   g_slot;
static int        gc_ioctl(uint64_t request, int nest) { // the shape mkh438.py gives the unit's gc_ioctl
	BC5_H438_GC(request);
	g_cpu += 100'000; // 0.1 ms of CPU per call
	std::this_thread::sleep_for(std::chrono::milliseconds(2));
	if (nest > 0) gc_ioctl(0xc0048116, nest - 1);
	return 0;
}
static void flip() { // VideoOutSubmitEopFlip's shape
	BC5_H438_FLIPSPAN();
	BC5_H438_DRAIN_BEGIN()
	std::this_thread::sleep_for(std::chrono::milliseconds(3));
	BC5_H438_DRAIN_END()
}

int main() {
	const bool  host = std::getenv("BC5_0438_HOSTWAIT") != nullptr;
	const char* file = std::getenv("BC5_0438_HOSTWAIT_FILE");
	std::thread render([&] {
		stub_set_name("Render Thread", 1001);
		BC5_O438_FLIP(); // no span yet: nothing
		gc_ioctl(0xc0188132, 0);
		BC5_O438_FLIP(); // the base line (the first frame with a tid)
		for (int fr = 0; fr < 70; fr++) {
			gc_ioctl(0xc0188132, 0);
			gc_ioctl(0xc0488131, 1); // nested: one call of 0xc0488131 only
			gc_ioctl(0x12345678, 0); // other
			if (fr == 5) {
				std::atomic<bool> held {false};
				std::thread       holder([&held] {
                    stub_set_name("Job Hi 0", 2002);
                    std::lock_guard l(g_a);
                    held = true;
                    std::this_thread::sleep_for(std::chrono::milliseconds(40));
				});
				while (!held) std::this_thread::yield();
				{ BC5_H438_LOCK_ID(3, "g_a", std::lock_guard la(g_a)); }
				holder.join();
			}
			{ BC5_H438_LOCK_ID(4, "g_b", std::lock_guard lb(g_b)); }
			if (fr == 7) { // case 5
				std::atomic<bool> held {false};
				std::thread       wd([&held] {
                    stub_set_name("bc5-chainwd", 2003);
                    BC5_F438_FLUSH_LOCK(g_slot, 9, true);
                    g_slot.f16_phase = 1; // in the back-pressure
                    held             = true;
                    std::this_thread::sleep_for(std::chrono::milliseconds(30));
				});
				while (!held) std::this_thread::yield();
				submitter(g_slot, 0, false, 0, true);
				wd.join();
				g_slot.f16_phase = 0;
			}
			{
				BC5_O438_WAIT(kWaitSema, &g_b); // a guest wait of 1 ms (o438)
				std::this_thread::sleep_for(std::chrono::milliseconds(1));
			}
			g_runq += 500'000;
			g_slices += 3;
			g_minflt += 7;
			if (fr == 9) g_majflt += 2;
			flip();
			BC5_O438_FLIP();
		}
	});
	render.join();
	std::thread other([] {
		stub_set_name("AK::AudioMgr", 3003);
		gc_ioctl(0xc0188132, 0);
	});
	other.join();
	std::vector<std::string> lines;
	if (file != nullptr) {
		std::ifstream f(file);
		for (std::string l; std::getline(f, l);) lines.push_back(l);
	}
	if (!host) {
		CHECK(lines.empty()); // case 3
	} else {
		// 70 frames after the base: 64 written at the 64th, the rest pending (as at a SIGTERM)
		CHECK(lines.size() == 65);
		if (lines.size() == 65) {
			CHECK(lines[0].rfind("t_s,frame_ms,cpu_ms,runq_ms,slices,minflt,majflt,gc_c0488131_n", 0) == 0);
			auto cols = [](const std::string& l) {
				std::vector<std::string> v;
				std::stringstream        ss(l);
				for (std::string c; std::getline(ss, c, ',');) v.push_back(c);
				return v;
			};
			const auto h = cols(lines[0]);
			auto       ix = [&h](const char* n) {
                for (size_t i = 0; i < h.size(); i++)
                    if (h[i] == n) return static_cast<int>(i);
                return -1;
			};
			const auto f1 = cols(lines[1]), f6 = cols(lines[6]), f10 = cols(lines[10]);
			std::printf("frame 1: %s\nframe 6: %s\n", lines[1].c_str(), lines[6].c_str());
			CHECK(f1.size() == h.size());
			CHECK(std::stoi(f1[ix("gc_c0188132_n")]) == 1);
			CHECK(std::stoi(f1[ix("gc_c0488131_n")]) == 1); // the nested 0xc0048116 is not counted
			CHECK(std::stoi(f1[ix("gc_c0048116_n")]) == 0);
			CHECK(std::stoi(f1[ix("gc_other_n")]) == 1);
			CHECK(std::stod(f1[ix("gc_c0488131_wall_us")]) >= 3500); // two sleeps of 2 ms
			CHECK(std::stod(f1[ix("gc_c0488131_blocked_us")]) >= 3000); // wall - 0.2 ms of CPU
			CHECK(std::stoi(f1[ix("flip_n")]) == 1 && std::stod(f1[ix("drain_wall_us")]) >= 2500);
			CHECK(std::stod(f1[ix("runq_ms")]) == 0.5 && std::stoi(f1[ix("slices")]) == 3 && std::stoi(f1[ix("minflt")]) == 7);
			CHECK(std::stod(f1[ix("cpu_ms")]) == 0.4); // 4 gc calls of 0.1 ms
			CHECK(f1[ix("locks")] == "-");             // g_b fast: counted, no wait
			CHECK(f6[ix("locks")].rfind("g_a=", 0) == 0 && std::stod(f6[ix("locks")].substr(4)) >= 25000); // case 1: the 30-ms wait
			CHECK(std::stoi(f10[ix("majflt")]) == 2);
			const auto f8 = cols(lines[8]);
			std::printf("frame 8 locks: %s\n", f8[ix("locks")].c_str());
			{ // case 5: the wait by holder and reason; no self wait from the recursive re-entry
				const std::string lk = f8[ix("locks")];
				const std::string key = "flush<-bc5-chainwd:2003/hold-wd/backpressure=";
				const auto        at  = lk.find(key);
				CHECK(at != std::string::npos);
				if (at != std::string::npos) CHECK(std::stod(lk.substr(at + key.size())) >= 15000);
				CHECK(lk.find("flush<-Render Thread") == std::string::npos);
				auto& T = bc5::f438::tot();
				CHECK(T.holds.size() == 2); // the watchdog's foreign hold and the Render Thread's own one (the nested one is the same hold)
				CHECK(g_slot.f438.depth.load() == 0 && g_slot.f438.holder.load() == -1);
			}
			const bool guest = std::getenv("BC5_0438_OUTSIDE") != nullptr;
			if (guest) CHECK(f1[ix("guest")].rfind("KernelWaitSema=", 0) == 0 && std::stod(f1[ix("guest_blocked_us")]) >= 900);
			else CHECK(f1[ix("guest")] == "-");
			// case 2: the audio thread's call is in no frame (the last flushed frame ends before it anyway): check counts
			int total = 0;
			for (size_t i = 1; i < lines.size(); i++) total += std::stoi(cols(lines[i])[ix("gc_c0188132_n")]);
			CHECK(total == 64);
		}
	}
	std::printf("%s (%d failures)\n", fails == 0 ? "PASS" : "FAIL", fails);
	return fails == 0 ? 0 : 1;
}
#endif
