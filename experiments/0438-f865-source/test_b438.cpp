// BC5 experiment 0438 (tag b438; from test_r438.cpp, mode 2 case dropped): a standalone test of the early registration's invariant. test_r438.sh cuts, unchanged,
// from the generated unit: r438's state, PendingLabelWrite/g_plw, register_label_writes, r438_scan/begin/end and
// ring_will_satisfy; this file supplies stubs. Cases:
// 1. a slice's RELEASE_MEM is registered early; a game-thread wait on its label (another thread) waits until the slice's
//    job registers it for real and the slice ends, then returns true (kept in ring order); 0 lost;
// 2. a slice whose job never registers the write: r438_end counts it lost and journals a BUG line; the early entry goes;
// 3. the part of an acb already submitted as a head (g_acb_heads done) is not registered again;
// 4. bc5-ring's own ring_will_satisfy ignores early entries.
// 6. (PLWCV) the latency from the writer's registration to the game thread's return, 20 rounds: with the condition
//    variable (BC5_0438_PLWCV unset or 1) the median must be under 2 ms; with the poll (=0) it is printed only.
// The ring's INDIRECT_BUFFER carries a 40-bit address: the IBs are static arrays (the Windows image base fits).
#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cinttypes>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace bc5::direct {
inline constexpr int kGfxRing = -1;
}
namespace SoftCp {
inline uint64_t now_ns() { return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count()); }
inline bool compare(uint32_t f, uint32_t v, uint32_t mask, uint32_t ref) {
	const uint32_t vm = v & mask, rm = ref & mask;
	return f == 3 ? vm == rm : f == 4 ? vm != rm : false;
}
} // namespace SoftCp
static std::mutex               g_jm;
static std::vector<std::string> g_lines;
static void journal(const char* fmt, ...) {
	char    b[1024];
	va_list ap;
	va_start(ap, fmt);
	std::vsnprintf(b, sizeof(b), fmt, ap);
	va_end(ap);
	std::lock_guard l(g_jm);
	g_lines.emplace_back(b);
}
static int                     w428_rings() { return 4; }
static double                  timing_now() { return 0.0; }
static thread_local bool       t_game = false;
static bool                    on_game_thread() { return t_game; }
struct AcbHead {
	const uint32_t* ib;
	uint32_t        num_dwords;
	uint32_t        done;
};
static std::vector<AcbHead> g_acb_heads;
#include "b438_cut_state.inc"
#include "b438_cut_plw.inc"
#include "b438_cut_register.inc"
#include "b438_cut_r438.inc"
#include "b438_cut_rws.inc"

static int fails = 0;
#define CHECK(c)                                             \
	do {                                                     \
		if (!(c)) {                                          \
			std::printf("FAIL line %d: %s\n", __LINE__, #c); \
			fails++;                                         \
		}                                                    \
	} while (0)

static uint64_t g_label1 = 0x907616589ull; // busy
static uint64_t g_label2 = 0x907616589ull;
static uint32_t g_ib[16];   // RELEASE_MEM (data 64-bit 0) to g_label1 at 0, to g_label2 at 8
static uint32_t g_ring[4];  // one INDIRECT_BUFFER of g_ib
static uint32_t g_wait1[9], g_wait2[9];
static void release(uint32_t* p, uint64_t a) {
	p[0] = 0xC0064900u; p[1] = 0x00000528u; p[2] = 0x40010000u; // DATA_SEL 2
	p[3] = static_cast<uint32_t>(a); p[4] = static_cast<uint32_t>(a >> 32u); p[5] = 0; p[6] = 0; p[7] = 0;
}
static void wait64(uint32_t* p, uint64_t a) {
	p[0] = 0xC0079300u; p[1] = 0x00000113u; // == , memory, pfp
	p[2] = static_cast<uint32_t>(a); p[3] = static_cast<uint32_t>(a >> 32u); p[4] = 0; p[5] = 0; p[6] = 0xffffffffu; p[7] = 0xffffffffu; p[8] = 0x19;
}
static size_t count(const char* needle) {
	std::lock_guard l(g_jm);
	return static_cast<size_t>(std::count_if(g_lines.begin(), g_lines.end(), [needle](const std::string& x) { return x.find(needle) != std::string::npos; }));
}
static size_t early_entries() {
	std::lock_guard lk(g_plw_mutex);
	return static_cast<size_t>(std::count_if(g_plw.begin(), g_plw.end(), [](const PendingLabelWrite& w) { return (w.seq & kR438Early) != 0; }));
}

int main() {
	const uint64_t a1 = reinterpret_cast<uintptr_t>(&g_label1), a2 = reinterpret_cast<uintptr_t>(&g_label2);
	const uint64_t ib = reinterpret_cast<uintptr_t>(&g_ib[0]);
	if ((ib >> 40u) != 0 || (a1 >> 48u) != 0) {
		std::printf("SKIP: the static arrays are not within 40 bits (ib 0x%" PRIx64 ")\n", ib);
		return 0;
	}
	release(g_ib, a1);
	release(g_ib + 8, a2);
	g_ring[0] = 0xC0023F00u; g_ring[1] = static_cast<uint32_t>(ib); g_ring[2] = static_cast<uint32_t>(ib >> 32u) & 0xffu; g_ring[3] = 16;
	wait64(g_wait1, a1);
	wait64(g_wait2, a2);
#ifdef BC5_LEAN
	std::printf("lean; ");
#endif
	std::printf("BC5_0438_EARLYREG %s, PLWCV %s\n", r438_on() ? "on" : "off", r438_cv() ? "on" : "off");
	if (!r438_on()) {
		r438_begin(g_ring, 4, nullptr, 0);
		CHECK(early_entries() == 0);
		r438_end();
		std::printf("%s (%d failures)\n", fails == 0 ? "PASS" : "FAIL", fails);
		return fails == 0 ? 0 : 1;
	}
	// 1. early, a game-thread wait that waits for the real registration
	r438_begin(g_ring, 4, nullptr, 0);
	CHECK(early_entries() == 2);
	CHECK(!ring_will_satisfy(g_wait1, true, 0)); // 4. bc5-ring (not the game thread) ignores the early entry: no writer
	std::atomic<int> got {-1}, entered {0};
	std::atomic<uint64_t> took {0};
	std::thread game([&] {
		t_game = true;
		const uint64_t t0 = SoftCp::now_ns();
		entered = 1;
		got  = ring_will_satisfy(g_wait1, true, bc5::direct::kGfxRing) ? 1 : 0;
		took = SoftCp::now_ns() - t0;
	});
	while (entered.load() == 0) std::this_thread::yield(); // the game thread is at its wait
	std::this_thread::sleep_for(std::chrono::milliseconds(30));
	CHECK(got.load() == -1); // still waiting while the writer is only early
	const std::vector<uint32_t> executed {0, 8};
	register_label_writes(g_ib, 16, executed, 5, 0); // the slice's job reached the ring
	r438_end();
	game.join();
	CHECK(got.load() == 1);
	CHECK(took.load() >= 25'000'000ull); // it waited for the real registration (30 ms after it entered)
	std::printf("took %.3f ms, got %d\n", static_cast<double>(took.load()) / 1e6, got.load());
	CHECK(early_entries() == 0);
#ifndef BC5_LEAN
	CHECK(g_r438_lost.load() == 0 && count("never reached the ring") == 0); // the 100 ms watchdog line may come: the laptop's scheduler can delay the writer
	CHECK(g_r438_waits.load() == 1);
#else
	CHECK(g_lines.empty()); // lean: no line
#endif
	// 2. a job that never registers: lost, BUG line, the early entry goes
	r438_begin(g_ring, 4, nullptr, 0);
	r438_end();
#ifndef BC5_LEAN
	CHECK(g_r438_lost.load() == 2 && count("never reached the ring") == 2);
#else
	CHECK(g_lines.empty());
	CHECK(g_r438_lost_lean.load() == 2); // lean's one counter
#endif
	CHECK(early_entries() == 0);
	// 3. the head already submitted: only the second write is early
	g_acb_heads.push_back({g_ib, 16, 8});
	r438_begin(g_ring, 4, nullptr, 0);
	{
		std::lock_guard lk(g_plw_mutex);
		size_t n = 0, n2 = 0;
		for (const auto& w: g_plw)
			if ((w.seq & kR438Early) != 0) {
				n++;
				if (w.label == a2) n2++;
			}
		CHECK(n == 1 && n2 == 1);
	}
	const std::vector<uint32_t> exec2 {8};
	register_label_writes(g_ib, 16, exec2, 6, 0);
	r438_end();
#ifndef BC5_LEAN
	CHECK(g_r438_lost.load() == 2);
#endif
	// 5. mode 1 only: a real older pending write that satisfies does not cut the wait for a newer early one
	{
		g_acb_heads.clear(); // case 3's head is gone: both writes are early again
		const std::vector<uint32_t> ex1 {0};
		register_label_writes(g_ib, 16, ex1, 7, 0); // a real, older pending write of g_label1 = 0
		r438_begin(g_ring, 4, nullptr, 0);           // and a newer early one
		std::atomic<int> got5 {-1}, in5 {0};
		std::thread g5([&] {
			t_game = true;
			in5    = 1;
			got5   = ring_will_satisfy(g_wait1, true, bc5::direct::kGfxRing) ? 1 : 0;
		});
		while (in5.load() == 0) std::this_thread::yield();
		std::this_thread::sleep_for(std::chrono::milliseconds(30));
		CHECK(got5.load() == -1); // waits for the early write
		const std::vector<uint32_t> ex2 {0, 8};
		register_label_writes(g_ib, 16, ex2, 8, 0);
		r438_end();
		g5.join();
		CHECK(got5.load() == 1);
		std::printf("case 5: waited for the early write\n");
	}
	// 6. PLWCV: registration -> return latency, 20 rounds
	{
		g_acb_heads.clear();
		std::vector<double> lat;
		for (int round = 0; round < 20; round++) {
			r438_begin(g_ring, 4, nullptr, 0);
			std::atomic<int>      in6 {0};
			std::atomic<uint64_t> ret {0};
			std::thread           g6([&] {
                t_game = true;
                in6    = 1;
                (void)ring_will_satisfy(g_wait1, true, bc5::direct::kGfxRing);
                ret = SoftCp::now_ns();
            });
			while (in6.load() == 0) std::this_thread::yield();
			std::this_thread::sleep_for(std::chrono::milliseconds(30));
			const std::vector<uint32_t> ex6 {0, 8};
			const uint64_t              t_reg = SoftCp::now_ns();
			register_label_writes(g_ib, 16, ex6, 100 + static_cast<uint64_t>(round), 0);
			r438_end();
			g6.join();
			lat.push_back(static_cast<double>(ret.load() - t_reg) / 1e6);
		}
		std::sort(lat.begin(), lat.end());
		std::printf("case 6 (%s): registration -> return, 20 rounds: median %.3f ms, p90 %.3f ms, max %.3f ms\n", r438_cv() ? "condition variable" : "poll", lat[10], lat[18], lat[19]);
		if (r438_cv()) CHECK(lat[10] < 2.0);
	}
	for (const auto& l: g_lines) std::printf("  %s", l.c_str());
	std::printf("%s (%d failures)\n", fails == 0 ? "PASS" : "FAIL", fails);
	return fails == 0 ? 0 : 1;
}
