// BC5 experiment 0412: CPU test of cover0412.inc (tag cv412): a K1r cover is a hole for the host's "is it mapped?".
// A page-level model: an address range with the title's mappings (writable shared, read-only userptr = the title's
// code and constants, writable userptr) and K1r's covers (read-only shared) laid out at random, sorted and disjoint.
//   - with the rule: a range is covered exactly when every page of it lies in a mapping that is not a cover; so the
//     answer is THE SAME as on the list with the covers removed (the host behaves as before K1r);
//   - with BC5_GUARD_K1R_COVERS_VISIBLE: a range is covered exactly when every page lies in any mapping (the state
//     that faulted ASTRO BOT on 2026-11-13);
//   - a read-only userptr mapping (the title's own read-only pages) is never a hole;
//   - the case of 11:32: a write operand under a cover: not mapped with the rule, mapped without.
// build: g++ -std=c++20 -O1 -Wall -Wextra -Werror cover0412.cpp -o cover0412
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <random>
#include <vector>

#include "cover0412.inc"

static uint64_t g_checks = 0, g_ok = 0;
static void     check(bool c, const char* what) {
	g_checks++;
	if (c) g_ok++;
	else if (g_checks - g_ok < 20) std::printf("FAIL: %s\n", what);
}

struct M {
	uint64_t va, size;
	bool     readonly, shared;
};

int main() {
	constexpr uint64_t P = 4096, base = 0x300000000ull;
	std::mt19937_64    rng(0x6376343132);
	for (int it = 0; it < 4000; it++) {
		const uint64_t   pages = 64 + rng() % 192;
		std::vector<int> kind(pages, 0); // 0 nothing, 1 title shared rw, 2 cover, 3 userptr ro, 4 userptr rw
		std::vector<M>   maps, no_covers;
		for (uint64_t p = 0; p < pages;) {
			const uint64_t n = 1 + rng() % 12, k = rng() % 6;
			const uint64_t e = p + n < pages ? p + n : pages;
			if (k >= 1 && k <= 4) {
				const M m{base + p * P, (e - p) * P, k == 2 || k == 3, k == 1 || k == 2};
				maps.push_back(m);
				if (k != 2) no_covers.push_back(m);
				for (uint64_t q = p; q < e; q++) kind[q] = static_cast<int>(k);
			}
			p = e;
		}
		for (int t = 0; t < 40; t++) {
			const uint64_t p0 = rng() % pages, n = 1 + rng() % 24;
			const uint64_t off = rng() % P, bytes = 1 + rng() % (n * P);
			const uint64_t a = base + p0 * P + off;
			bool all_title = true, all_any = true;
			for (uint64_t x = a / P; x <= (a + bytes - 1) / P; x++) {
				const uint64_t q = x - base / P;
				const int      k = q < pages ? kind[q] : 0;
				all_title = all_title && (k == 1 || k == 3 || k == 4);
				all_any   = all_any && k != 0;
			}
			const bool rule = cv412::covered_sorted(maps, a, bytes, false);
			check(rule == all_title, "with the rule: covered exactly when every page is the title's mapping");
			check(rule == cv412::covered_sorted(no_covers, a, bytes, false), "with the rule: the same answer as on the list without the covers");
			check(rule == cv412::covered_sorted(no_covers, a, bytes, true), "the list without covers answers the same with either setting");
			check(cv412::covered_sorted(maps, a, bytes, true) == all_any, "covers visible: covered exactly when every page is in any mapping");
		}
	}
	check(cv412::hole(true, true, false) && !cv412::hole(true, false, false) && !cv412::hole(false, true, false) && !cv412::hole(false, false, false), "only a read-only shared mapping is a hole");
	check(!cv412::hole(true, true, true), "covers visible: no hole");
	// 2026-11-13 11:32: orbis_user_malloc, a cover over the never-written chunk at 0x308200000; the operand 0x3082f6000
	{
		const std::vector<M> maps = {{0x3018c0000ull, 0x6940000ull, false, true}, {0x308200000ull, 0x200000ull, true, true}, {0x308400000ull, 0x200000ull, false, true}};
		check(!cv412::covered_sorted(maps, 0x3082f6000ull, 4, false), "the write operand of 11:32 under a cover: not mapped for the host (the filter drops the packet, or K1 imports its chunk)");
		check(cv412::covered_sorted(maps, 0x3082f6000ull, 4, true), "with covers visible it looked mapped: the state that faulted");
		check(cv412::covered_sorted(maps, 0x308400000ull, 4096, false) && cv412::covered_sorted(maps, 0x3018c0000ull, 4096, false), "the title's own mappings beside it are mapped");
		check(!cv412::covered_sorted(maps, 0x3083ff000ull, 8192, false), "a range that starts in the cover and ends in real memory is not mapped");
		check(!cv412::covered_sorted(maps, 0x3081ff000ull, 8192, false), "a range that starts in real memory and ends in the cover is not mapped");
	}
	check(cv412::hole(true, true) && !cv412::hole(true, false) && !cv412::hole(false, true), "the unit's form: a read-only shared mapping is always a hole (no switch)");
	std::printf("cover0412: %" PRIu64 " of %" PRIu64 "; end\n", g_ok, g_checks);
	return g_ok == g_checks ? 0 : 1;
}
