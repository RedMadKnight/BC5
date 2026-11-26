// BC5 experiment 0438 (tag k438b): a standalone test of hold_release as the unit has it (the function, HoldCond and the
// switch are cut from bc5LleAgc.cpp by test_k438b.sh, unchanged), against stubs of what it calls, on a fake clock.
// Cases: the writer reaches a ring -> released; the label is met -> released; neither for 25 s -> with BC5_0438_HOLD on,
// never dropped, records at 100 ms, 1 s, 11 s, 21 s; with it "0", the old give-up at 100 ms (the wait dropped).
#include <algorithm>
#include <atomic>
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

namespace SoftCp {
static uint64_t g_now = 0;
inline uint64_t now_ns() { return g_now; }
} // namespace SoftCp
namespace bc5::direct {
inline constexpr int kGfxRing = -1;
}
static std::vector<std::string> g_lines;
static void journal(const char* fmt, ...) {
	char    b[1024];
	va_list ap;
	va_start(ap, fmt);
	std::vsnprintf(b, sizeof(b), fmt, ap);
	va_end(ap);
	g_lines.emplace_back(b);
}
static void describe_pending(uint64_t, char* out, size_t cap) { std::snprintf(out, cap, "no pending write"); }
static bool g_writer_on_ring = false;
static uint32_t g_label = 7; // the label's memory (32-bit), "busy"; the wait is label == 0
static bool     wait_satisfied(const uint32_t*, bool) { return g_label == 0; }
static bool ring_will_satisfy(const uint32_t*, bool, int) { return g_writer_on_ring; }
struct ChainSeg {
	const uint32_t*       src;
	uint32_t              n, prefix, off;
	bool                  given_up;
	std::vector<uint32_t> keep;
};
struct Chain {
	std::vector<ChainSeg> segs;
};
#include "k438b_cut_holdcond.inc"
struct ChainSlot {
	Chain                 c;
	std::mutex            mu;
	std::vector<HoldCond> hold;
};
static ChainSlot                     g_chain_tl;
static std::vector<const uint32_t*> t_keep_waits;
static bool                          t_wait_given_up = false;
#include "k438b_cut_release.inc"

static int fails = 0;
#define CHECK(c)                                                                 \
	do {                                                                         \
		if (!(c)) {                                                              \
			std::printf("FAIL line %d: %s\n", __LINE__, #c);                     \
			fails++;                                                             \
		}                                                                        \
	} while (0)

static uint32_t g_wait[9];   // WAIT_REG_MEM: label == 0
static void reset(ChainSlot& s) {
	s.hold.clear();
	s.c.segs.clear();
	g_writer_on_ring = false;
	g_label          = 7;
	SoftCp::g_now    = 1'000'000'000ull;
	g_lines.clear();
	t_keep_waits.clear();
	t_wait_given_up = false;
	std::memset(g_wait, 0, sizeof(g_wait));
	g_wait[0] = 0xC0053C00u;
	g_wait[1] = 0x13u;
	g_wait[4] = 0;
	HoldCond c;
	for (int k = 0; k < 8; k++) c.pkt[k] = g_wait[k];
	c.p     = g_wait;
	c.label = reinterpret_cast<uintptr_t>(&g_label);
	c.t0    = SoftCp::g_now;
	s.hold.push_back(c);
	ChainSeg seg {g_wait, 9, 0, 0, false, {0}};
	s.c.segs.push_back(seg);
}
static size_t count(const char* needle) {
	return static_cast<size_t>(std::count_if(g_lines.begin(), g_lines.end(), [needle](const std::string& l) { return l.find(needle) != std::string::npos; }));
}

int main() {
	const bool on = k438b_on();
	std::printf("BC5_0438_HOLD %s\n", on ? "on" : "off");
	ChainSlot& s = g_chain_tl;
	// 1. the writer reaches a ring
	reset(s);
	CHECK(!hold_release(s, false));
	g_writer_on_ring = true;
	CHECK(hold_release(s, false));
	CHECK(s.hold.empty() && !s.c.segs[0].given_up && s.c.segs[0].keep.size() == 1);
	// 2. the label is met
	reset(s);
	SoftCp::g_now += 5'000'000ull;
	g_label = 0;
	CHECK(hold_release(s, false));
	CHECK(s.hold.empty() && s.c.segs[0].keep.size() == 1);
	// 3. neither, for 25 s
	reset(s);
	for (int ms = 0; ms <= 25'000; ms += 10) {
		SoftCp::g_now = 1'000'000'000ull + static_cast<uint64_t>(ms) * 1'000'000ull;
		const bool released = hold_release(s, false);
		if (on) {
			CHECK(!released);
		} else if (released) {
			std::printf("off: released (given up) at %d ms\n", ms);
			break;
		}
	}
	if (on) {
		CHECK(s.hold.size() == 1);
		CHECK(!s.c.segs[0].given_up && s.c.segs[0].keep.size() == 1); // the kept wait is never dropped
		CHECK(count("GIVEN UP") == 0);
		CHECK(count("STILL HELD") == 4); // 100 ms, 1 s, 11 s, 21 s
		for (const auto& l: g_lines) std::printf("  %s", l.c_str());
	} else {
		CHECK(s.hold.empty() && s.c.segs[0].given_up && s.c.segs[0].keep.empty()); // the old give-up
		CHECK(count("GIVEN UP") == 1 && count("STILL HELD") == 0);
	}
	std::printf("%s (%d failures)\n", fails == 0 ? "PASS" : "FAIL", fails);
	return fails == 0 ? 0 : 1;
}
