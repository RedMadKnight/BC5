// BC5 experiment 0412: CPU test of zscan0412.inc (tag zs412): the canary's mappings as search ranges, the runs a
// buffer's finds name, and mode 2's window.
//   ranges(): against a page-level model on random canary layouts (an address is in a range of run r exactly when a
//   piece of run r holds it); sorted, disjoint, neighbours of one run merged.
//   runs_of() after ns412::scan(): a buffer with planted addresses (both forms) names exactly the planted runs, each
//   once, in the order of the first find; a buffer with no address under the canary names none.
//   window_hi(): against a walk page by page.
// build: g++ -std=c++20 -O1 -Wall -Wextra -Werror zscan0412.cpp -o zscan0412
#include <algorithm>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <random>
#include <set>
#include <string>
#include <vector>

#include "nscan0412.inc"
#include "zscan0412.inc"

static uint64_t g_checks = 0, g_ok = 0;
static void check(bool c, const char* what) {
	g_checks++;
	if (c) g_ok++;
	else if (g_checks - g_ok < 20) std::printf("FAIL: %s\n", what);
}
struct Piece {
	uint64_t size;
	uint32_t run;
};
static constexpr uint64_t P = 0x4000; // the model's page

int main() {
	std::mt19937_64 rng(412048);
	for (int round = 0; round < 400; round++) {
		// A random layout: pieces of 1..6 pages, a gap of 0..3 pages between them, runs 0..5 (a neighbour often of the same run).
		std::map<uint64_t, Piece> pieces;
		std::map<uint64_t, uint32_t> page_run; // the model
		uint64_t va  = 0x1100000000ull + (rng() % 64) * P;
		uint32_t run = static_cast<uint32_t>(rng() % 6);
		const int n  = static_cast<int>(rng() % 40);
		for (int i = 0; i < n; i++) {
			va += (rng() % 4) * P;
			if (rng() % 3 == 0) run = static_cast<uint32_t>(rng() % 6);
			const uint64_t size = (1 + rng() % 6) * P;
			pieces[va] = {size, run};
			for (uint64_t a = va; a < va + size; a += P) page_run[a] = run;
			va += size;
		}
		if (rng() % 8 == 0 && !pieces.empty()) pieces[va + P] = {0, 9}; // an empty piece is ignored
		std::vector<ns412::Range> r;
		zs412::ranges(pieces, r);
		bool sorted = true, merged = true;
		for (size_t i = 0; i < r.size(); i++) {
			if (r[i].lo >= r[i].hi) sorted = false;
			if (i != 0 && r[i - 1].hi > r[i].lo) sorted = false;
			if (i != 0 && r[i - 1].hi == r[i].lo && r[i - 1].name == r[i].name) merged = false;
		}
		check(sorted, "ranges: sorted and disjoint");
		check(merged, "ranges: neighbours of one run merged");
		uint64_t pages = 0;
		bool     same  = true;
		for (const auto& x: r) {
			for (uint64_t a = x.lo; a < x.hi; a += P) {
				pages++;
				const auto it = page_run.find(a);
				if (it == page_run.end() || it->second != x.name) same = false;
			}
		}
		check(same && pages == page_run.size(), "ranges: exactly the model's pages, with their runs");
		for (int k = 0; k < 20 && !page_run.empty(); k++) {
			const uint64_t a  = 0x1100000000ull + (rng() % 400) * P + rng() % P;
			const int      f  = ns412::find(r, a);
			const auto     it = page_run.find(a & ~(P - 1));
			check((f >= 0) == (it != page_run.end()) && (f < 0 || r[static_cast<size_t>(f)].name == it->second), "find: as the model");
		}
		// A buffer: noise that is no address under the canary, then planted addresses in both forms.
		std::vector<uint32_t> w(600);
		for (auto& x: w) x = static_cast<uint32_t>(rng() & 0xffffu); // small numbers: pair form gives < 2^48 with a low address, far below the layout
		std::vector<ns412::Hit> hits;
		ns412::scan(w.data(), static_cast<uint32_t>(w.size()), r, hits, 64, nullptr, 0, 0);
		std::vector<uint32_t> runs;
		zs412::runs_of(hits, r, runs);
		check(hits.empty() && runs.empty(), "runs_of: a buffer without addresses names no run");
		std::vector<uint32_t> want;
		if (!r.empty()) {
			const int plant = 1 + static_cast<int>(rng() % 5);
			uint32_t  at    = 10;
			for (int k = 0; k < plant; k++) {
				const auto&    x = r[rng() % r.size()];
				uint64_t       a = x.lo + rng() % (x.hi - x.lo);
				const bool     shifted = rng() % 2 == 0;
				if (shifted) {
					a &= ~0xffull;
					if (a < x.lo) a = x.lo; // lo is page aligned
					w[at]     = static_cast<uint32_t>(a >> 8);
					w[at + 1] = static_cast<uint32_t>(a >> 40) & 0xffu;
				} else {
					w[at]     = static_cast<uint32_t>(a);
					w[at + 1] = static_cast<uint32_t>(a >> 32) & 0xffffu;
				}
				if (std::find(want.begin(), want.end(), x.name) == want.end()) want.push_back(x.name);
				at += 100;
			}
			hits.clear();
			ns412::scan(w.data(), static_cast<uint32_t>(w.size()), r, hits, 64, nullptr, 0, 0);
			zs412::runs_of(hits, r, runs);
			// A planted pair can make a second, accidental find at the dword before or after it; the planted runs must
			// all be named, in their order, and every named run must be one a hit lies in.
			std::vector<uint32_t> planted_seen;
			for (const uint32_t x: runs) {
				if (std::find(want.begin(), want.end(), x) != want.end()) planted_seen.push_back(x);
			}
			check(planted_seen == want, "runs_of: every planted run, once, in the order of the first find");
			std::set<uint32_t> distinct(runs.begin(), runs.end());
			check(distinct.size() == runs.size(), "runs_of: no run twice");
			bool backed = true;
			for (const uint32_t x: runs) {
				bool any = false;
				for (const auto& h: hits) any = any || r[h.range].name == x;
				backed = backed && any;
			}
			check(backed, "runs_of: every named run has a hit");
		}
		// window_hi against a walk by pages.
		for (int k = 0; k < 10 && !r.empty(); k++) {
			const size_t   i    = rng() % r.size();
			const uint64_t addr = r[i].lo + (rng() % ((r[i].hi - r[i].lo) / P)) * P;
			const uint64_t cap  = (1 + rng() % 12) * P;
			uint64_t       hi   = addr;
			while (hi - addr < cap) {
				const auto it = page_run.find(hi);
				if (it == page_run.end() || it->second != r[i].name) break;
				hi += P;
			}
			check(zs412::window_hi(r, i, addr, cap) == hi, "window_hi: as the walk by pages");
		}
	}
	{
		std::map<uint64_t, Piece> none;
		std::vector<ns412::Range> r {{1, 2, 3}};
		zs412::ranges(none, r);
		check(r.empty(), "ranges: no pieces, nothing");
		std::vector<uint32_t> runs {7};
		zs412::runs_of({}, r, runs);
		check(runs.empty(), "runs_of: no hits, nothing");
	}
	{
		// Capacity (review R25): 64 repeats of address A fill a limit of 64 and a later address B is left out: the search
		// says "incomplete"; with room it is complete and B is found. The same for the table candidates.
		const std::vector<ns412::Range> r {{0x1100000000ull, 0x1100200000ull, 0}, {0x1100400000ull, 0x1100600000ull, 1}, {0x1100600000ull, 0x1100800000ull, 2}};
		std::vector<uint32_t>           w;
		for (int i = 0; i < 64; i++) {
			w.push_back(0x00001000u);
			w.push_back(0x11u);
			w.push_back(0);
		}
		w.push_back(0x00401000u);
		w.push_back(0x11u);
		w.push_back(0);
		std::vector<ns412::Hit> hits;
		std::vector<uint32_t>   runs;
		const bool c64 = ns412::scan(w.data(), static_cast<uint32_t>(w.size()), r, hits, 64, nullptr, 0, 0);
		zs412::runs_of(hits, r, runs);
		check(!c64 && runs == std::vector<uint32_t> {0}, "capacity: 64 repeats then B with a limit of 64 is INCOMPLETE and B's run is not named");
		hits.clear();
		const bool cbig = ns412::scan(w.data(), static_cast<uint32_t>(w.size()), r, hits, 4096, nullptr, 0, 0);
		zs412::runs_of(hits, r, runs);
		check(cbig && runs == (std::vector<uint32_t> {0, 1}), "capacity: with room the search is complete and B's run is named");
		zs412::all_runs(r, runs);
		check(runs == (std::vector<uint32_t> {0, 1, 2}), "all_runs: every run under the canary, once");
		std::vector<uint32_t> t;
		for (uint32_t i = 0; i < 5; i++) {
			t.push_back(0x20000000u + i * 0x1000u);
			t.push_back(0x12u);
			t.push_back(0);
		}
		std::vector<uint64_t> others;
		hits.clear();
		const bool o4 = ns412::scan(t.data(), static_cast<uint32_t>(t.size()), r, hits, 64, &others, 0x1200000000ull, 0x1300000000ull, 4);
		check(!o4 && others.size() == 4, "capacity: a fifth table candidate with a limit of 4 is INCOMPLETE");
		others.clear();
		const bool o8 = ns412::scan(t.data(), static_cast<uint32_t>(t.size()), r, hits, 64, &others, 0x1200000000ull, 0x1300000000ull, 8);
		check(o8 && others.size() == 5, "capacity: with room all five candidates are kept");
	}
	std::printf("zscan0412: %" PRIu64 " of %" PRIu64 "; end\n", g_ok, g_checks);
	return g_ok == g_checks ? 0 : 1;
}
