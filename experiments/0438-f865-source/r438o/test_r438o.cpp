// SPDX-License-Identifier: GPL-2.0
// BC5 experiment 0438 (tag r438o): is r438's early write passed in g_plw by another thread's real write of the same label?
// test_r438o.sh cuts, unchanged, from a unit (the bake unit ff9e8fe2, or mkr438o.py's): r438's state, PendingLabelWrite /
// g_plw, register_label_writes, r438_scan/begin/end and ring_will_satisfy. Modes:
//   order     bc5-ring takes a slice (r438_begin: an early write of L = 1), another thread's job registers a real write of
//             L = 2 (the Render Thread's or the chain watchdog's submit_now), then a game-thread wait on L == 1. It must
//             wait until the slice's own job registers L = 1 for real (r438_end), then find its writer. Returning at once
//             with "not satisfied" is the give-up path while the writer is still to come.
//   trim      the early write survives g_plw's trim (9,000 real writes of another label), then as order
//   identity  one thread, a fixed sequence of slices and registrations; prints g_plw and the non-game answers after each
//             step (compared between units by the script).
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cinttypes>
#include <condition_variable>
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
static double            timing_now() { return static_cast<double>(SoftCp::now_ns()) / 1e9; }
static int               g_rings = 4;
static int               w428_rings() { return g_rings; }
static thread_local bool t_game = false;
static bool              on_game_thread() { return t_game; }
struct AcbHead {
	const uint32_t* ib;
	uint32_t        num_dwords;
	uint32_t        done;
};
static std::vector<AcbHead> g_acb_heads;
#include "r_state.inc"
#include "r_plw.inc"
#include "r_reg.inc"
#include "r_r438.inc"
#include "r_rws.inc"

static int fails = 0;
#define CHECK(c, ...)                                \
	do {                                             \
		if (!(c)) {                                  \
			std::printf("FAIL line %d: ", __LINE__); \
			std::printf(__VA_ARGS__);                \
			std::printf("  [%s]\n", #c);             \
			fails++;                                 \
		}                                            \
	} while (0)

static uint64_t g_label = 0x907616589ull;
static uint32_t g_ib1[8], g_ib2[8], g_ib3[8]; // RELEASE_MEM 64-bit of 1, 2, 3 to g_label
static uint32_t g_ring[4];                     // the slice: one INDIRECT_BUFFER of g_ib1
static void     release(uint32_t* p, uint64_t a, uint64_t v) {
    p[0] = 0xC0064900u; p[1] = 0x00000528u; p[2] = 0x40010000u; // DATA_SEL 2
    p[3] = static_cast<uint32_t>(a); p[4] = static_cast<uint32_t>(a >> 32u); p[5] = static_cast<uint32_t>(v); p[6] = static_cast<uint32_t>(v >> 32u); p[7] = 0;
}
static bool wait_on(uint64_t v) { // a WAIT_REG_MEM64 on g_label == v, on the calling thread
	uint32_t       p[9];
	const uint64_t a = reinterpret_cast<uintptr_t>(&g_label);
	p[0] = 0xC0079300u; p[1] = 0x00000113u;
	p[2] = static_cast<uint32_t>(a); p[3] = static_cast<uint32_t>(a >> 32u); p[4] = static_cast<uint32_t>(v); p[5] = static_cast<uint32_t>(v >> 32u); p[6] = 0xffffffffu; p[7] = 0xffffffffu; p[8] = 0x19;
	return ring_will_satisfy(p, true, bc5::direct::kGfxRing);
}
static const std::vector<uint32_t> kAt0 {0};

// The bc5-ring thread: its steps are driven one at a time (r438's state is thread-local).
struct Ring {
	std::mutex              m;
	std::condition_variable cv;
	int                     step = 0, done = 0;
	std::thread             t;
	Ring() {
		t = std::thread([this] {
			for (int k = 1; k <= 2; k++) {
				{
					std::unique_lock lk(m);
					cv.wait(lk, [&] { return step >= k; });
				}
				if (k == 1) r438_begin(g_ring, 4, nullptr, 0); // exp 0438 b438: the slice's writes, early (unit line 1682)
				if (k == 2) {
					register_label_writes(g_ib1, 8, kAt0, 501, 0); // the slice's job in submit_now (unit line ~16273)
					r438_end();
				}
				{
					std::lock_guard lk(m);
					done = k;
				}
				cv.notify_all();
			}
		});
	}
	void go(int k) {
		{
			std::lock_guard lk(m);
			step = k;
		}
		cv.notify_all();
		std::unique_lock lk(m);
		cv.wait(lk, [&] { return done >= k; });
	}
};

static void run_order() {
	Ring ring;
	ring.go(1);
	{
		std::lock_guard lk(g_plw_mutex);
		CHECK(g_plw.size() == 1 && (g_plw[0].seq & kR438Early) != 0, "the slice's early write is not registered");
	}
	std::thread([] { register_label_writes(g_ib2, 8, kAt0, 502, bc5::direct::kGfxRing); }).join(); // another thread's job: L = 2
	std::atomic<int> got {-1};
	std::thread      game([&got] {
        t_game = true;
        got    = wait_on(1) ? 1 : 0;
	});
	std::this_thread::sleep_for(std::chrono::milliseconds(40));
	const int before = got.load();
	ring.go(2);
	game.join();
	ring.t.join();
	std::printf("order: the game-thread wait on L == 1 after another thread's real L = 2: %s (%d); after the slice's own real registration: %d\n",
	            before == -1 ? "still waiting for the early writer" : (before == 0 ? "returned NOT SATISFIED at once" : "returned satisfied"), before, got.load());
	CHECK(before == -1, "the wait did not wait for the slice's early writer: another thread's later real write passed it in g_plw");
	CHECK(got.load() == 1, "the wait found no writer after the slice's real registration");
}

// trim: the slice's early write of L = 1, then 9,000 real writes of another label (past g_plw's trim at 8,192 entries),
// then a game-thread wait on L == 1. With r438o the trim keeps the early entry: the wait waits, then finds its writer.
// Today's trim erases the oldest 4,096 entries by position, the early one with them: the wait returns at once.
static uint64_t g_label2 = 0x5a5a5a5a5ull;
static uint32_t g_ib4[8];
static void run_trim() {
	release(g_ib4, reinterpret_cast<uintptr_t>(&g_label2), 7);
	Ring ring;
	ring.go(1);
	size_t peak = 0;
	for (int i = 0; i < 9000; i++) {
		register_label_writes(g_ib4, 8, kAt0, 600 + static_cast<uint64_t>(i), bc5::direct::kGfxRing);
		std::lock_guard lk(g_plw_mutex);
		peak = std::max(peak, g_plw.size());
	}
	size_t n = 0, early = 0;
	{
		std::lock_guard lk(g_plw_mutex);
		n = g_plw.size();
		for (const auto& w: g_plw) early += (w.seq & kR438Early) != 0 ? 1 : 0;
	}
	std::atomic<int> got {-1};
	std::thread      game([&got] {
        t_game = true;
        got    = wait_on(1) ? 1 : 0;
	});
	std::this_thread::sleep_for(std::chrono::milliseconds(40));
	const int before = got.load();
	ring.go(2);
	game.join();
	ring.t.join();
#if defined(R438O_COUNTERS)
	const uint64_t trims = g_r438o_trims.load(), kept = g_r438o_kept.load();
#else
	const uint64_t trims = 0, kept = 0; // the bake unit has no r438o counters
#endif
	std::printf("trim: g_plw %zu entries at the end, peak %zu, early entries %zu; trims %" PRIu64 ", early entries kept %" PRIu64 "; the wait on L == 1: %d before the slice's real registration, %d after\n",
	            n, peak, early, trims, kept, before, got.load());
	CHECK(early == 1, "the slice's early entry was dropped by the trim");
	CHECK(peak <= 8193, "the table grew past 8192 + one batch");
	CHECK(trims >= 1 && kept >= 1, "no trim kept an early entry");
	CHECK(before == -1, "the wait did not wait for the slice's early writer after the trim");
	CHECK(got.load() == 1, "the wait found no writer after the slice's real registration");
}

static void run_identity() {
	auto dump = [](const char* step) {
		std::lock_guard lk(g_plw_mutex);
		std::printf("%s:", step);
		for (const auto& w: g_plw) std::printf(" [v%" PRIu64 " %s r%d o%" PRIu64 "]", w.value, (w.seq & kR438Early) != 0 ? "early" : "real", w.ring, w.order);
		std::printf("\n");
	};
	r438_begin(g_ring, 4, nullptr, 0);
	dump("1 begin");
	register_label_writes(g_ib2, 8, kAt0, 502, bc5::direct::kGfxRing);
	dump("2 other real");
	std::printf("  non-game wait ==1 %d ==2 %d\n", wait_on(1) ? 1 : 0, wait_on(2) ? 1 : 0);
	register_label_writes(g_ib1, 8, kAt0, 501, 0);
	dump("3 own real");
	register_label_writes(g_ib3, 8, kAt0, 503, bc5::direct::kGfxRing);
	dump("4 other real");
	r438_end();
	dump("5 end");
	std::printf("  non-game wait ==1 %d ==3 %d\n", wait_on(1) ? 1 : 0, wait_on(3) ? 1 : 0);
	r438_begin(g_ring, 4, nullptr, 0);
	r438_end(); // never registered: a BUG line (r438's invariant)
	dump("6 lost");
	std::lock_guard l(g_jm);
	for (const auto& x: g_lines)
		if (x.find("BUG") != std::string::npos) std::printf("  journal: %s", x.c_str());
}

int main(int argc, char** argv) {
	const uint64_t a  = reinterpret_cast<uintptr_t>(&g_label);
	const uint64_t ib = reinterpret_cast<uintptr_t>(&g_ib1[0]);
	if ((ib >> 40u) != 0) {
		std::printf("FAIL: the static arrays are not within 40 bits (0x%" PRIx64 ")\n", ib);
		return 2;
	}
	release(g_ib1, a, 1);
	release(g_ib2, a, 2);
	release(g_ib3, a, 3);
	g_ring[0] = 0xC0023F00u; g_ring[1] = static_cast<uint32_t>(ib); g_ring[2] = static_cast<uint32_t>(ib >> 32u) & 0xffu; g_ring[3] = 8;
	const std::string mode = argc > 1 ? argv[1] : "order";
	std::printf("BC5_0438_EARLYREG %s, mode %s\n", r438_on() ? "on" : "off", mode.c_str());
	if (mode == "identity") {
		run_identity();
		return 0;
	}
	if (!r438_on()) {
		std::printf("FAIL: order needs r438 on\n");
		return 2;
	}
	if (mode == "trim") run_trim();
	else run_order();
	std::printf("%s (%d failures)\n", fails == 0 ? "PASS" : "FAIL", fails);
	return fails == 0 ? 0 : 1;
}
