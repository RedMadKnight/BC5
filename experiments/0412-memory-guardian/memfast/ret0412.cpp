// BC5 experiment 0412: CPU test of ret0412.inc (the return-aware orphan release, tag ra412), old against new.
// A model of the lazy release's decision for one heap: a chunk under no view for `idle` is cut ("old"), and with the
// table it is cut only when it is not exempt ("new"). Checks: with the switch off new == old at every step of a
// random run; with it on, a chunk that never came back is cut exactly when old cuts it; a chunk that breathes
// (leaves and returns every few seconds) is cut once and then not again inside the exemption; the exemption doubles
// with every return up to 64 times the base and ends; counters add up.
// build: g++ -std=c++20 -O1 -Wall -Wextra -Werror ret0412.cpp -o ret0412
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <random>
#include <set>
#include <vector>

static int g_lines = 0;
#define RA412_PRINT(...) (g_lines++, std::printf(__VA_ARGS__))
#include "ret0412.inc"

static uint64_t g_checks = 0, g_ok = 0;
static void check(bool c, const char* what) {
	g_checks++;
	if (c) g_ok++;
	else if (g_checks - g_ok < 20) std::printf("FAIL: %s\n", what);
}

static constexpr uint64_t S = 1000000000ull;

// One heap of n chunks; viewed[c] says whether a view covers chunk c now. Returns the number of cuts.
struct Model {
	explicit Model(uint64_t base_ns, uint64_t idle_ns, size_t n): tab(base_ns), idle(idle_ns), since(n, 0), pinned(n, true) {}
	ra412::Table          tab;
	uint64_t              idle;
	std::vector<uint64_t> since;
	std::vector<bool>     pinned;
	uint64_t              cuts = 0;
	void step(const std::vector<bool>& viewed, uint64_t now) {
		for (size_t c = 0; c < since.size(); c++) {
			if (viewed[c]) {
				if (!pinned[c]) { // a released chunk under a view again: imported, noted
					pinned[c] = true;
					tab.back(c, now);
				}
				since[c] = 0;
				continue;
			}
			if (!pinned[c]) continue;
			if (since[c] == 0) since[c] = now;
			if (now - since[c] >= idle && !tab.exempt(c, now)) {
				pinned[c] = false;
				cuts++;
			}
		}
	}
};

int main() {
	{ // off: the table changes nothing, against a model without it
		std::mt19937_64 rng(412);
		Model a(0, 4 * S, 64), b(0, 4 * S, 64);
		check(!a.tab.on(), "base 0 is off");
		std::vector<bool> viewed(64, true);
		for (uint64_t t = 1; t <= 600; t++) {
			for (size_t c = 0; c < 64; c++) {
				if (rng() % 7 == 0) viewed[c] = !viewed[c];
			}
			a.step(viewed, t * S);
			b.step(viewed, t * S);
			check(a.pinned == b.pinned && a.cuts == b.cuts, "off: the same decisions");
		}
		check(a.cuts > 100 && a.tab.returned_bytes() == 0 && a.tab.skipped() == 0 && a.tab.chunks() == 0, "off: cuts happen, nothing is recorded");
	}
	{ // on: a dead chunk is cut as before; a breathing chunk is cut once
		Model old(0, 4 * S, 2), neu(300 * S, 4 * S, 2);
		// chunk 0 dies at t = 10 and stays dead; chunk 1 is unviewed for 6 s of every 10 s
		for (uint64_t t = 1; t <= 900; t++) {
			const std::vector<bool> viewed = {t < 10, t % 10 < 4};
			old.step(viewed, t * S);
			neu.step(viewed, t * S);
			check(old.pinned[0] == neu.pinned[0], "the dead chunk: cut at the same step with and without the table");
		}
		check(!neu.pinned[0], "the dead chunk is released");
		check(old.cuts == 1 + 90, "old: the breathing chunk is cut in every one of its 90 periods");
		// base 300 s, then 600 s after the second return: cut at ~8 s, again after 300 s, and not again within 900 s
		check(neu.cuts == 1 + 2, "new: the breathing chunk is cut twice in 900 s (the second time after the first exemption ended)");
		check(neu.tab.returns(1) == 2 && neu.tab.returns(0) == 0, "returns are counted per chunk");
		check(neu.tab.returned_bytes() == 2 * ra412::kChunkBytes, "returned bytes add up");
		check(neu.tab.skipped() > 100, "skipped decisions are counted");
	}
	{ // the exemption's length: base << min(returns - 1, 6)
		ra412::Table t(10 * S);
		uint64_t     now = 1000 * S;
		for (uint32_t r = 1; r <= 9; r++) {
			t.back(7, now);
			const uint64_t len = (10 * S) << (r - 1 < 6 ? r - 1 : 6);
			check(t.exempt(7, now) && t.exempt(7, now + len - 1), "exempt until the end of the period");
			check(!t.exempt(7, now + len), "not exempt at the period's end");
			check(t.exempt_bytes(now) == ra412::kChunkBytes && t.exempt_bytes(now + len) == 0, "exempt bytes follow the clock");
			now += len + S;
		}
		check(!t.exempt(8, now) && t.returns(8) == 0, "another chunk is untouched");
		check(t.chunks() == 1, "one chunk in the table");
	}
	std::printf("ret0412: %" PRIu64 " of %" PRIu64 "; end\n", g_ok, g_checks);
	return g_ok == g_checks ? 0 : 1;
}
