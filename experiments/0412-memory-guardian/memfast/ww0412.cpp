// BC5 experiment 0412: CPU test of ww0412.inc (tag ww412): the classification of chunks that turned non-zero.
// A model: a heap of slots at base + i * chunk, with base on or off the file's 2 MiB grid; a random set of named grid
// chunks; random flags before and after.
//   - turned = the slots that were zero and are not; named + not named = turned;
//   - a slot is named exactly when a grid chunk it touches is in the set (one chunk when base is on the grid, two
//     when it is not);
//   - the kept list holds the first not-named slots in order, at most `keep`;
//   - a changed span gives no comparison;
//   - the switch is off when the variable is unset.
// build: g++ -std=c++20 -O1 -Wall -Wextra -Werror ww0412.cpp -o ww0412
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <random>
#include <set>
#include <vector>

#include "ww0412.inc"

static uint64_t g_checks = 0, g_ok = 0;
static void     check(bool c, const char* what) {
	g_checks++;
	if (c) g_ok++;
	else if (g_checks - g_ok < 20) std::printf("FAIL: %s\n", what);
}

int main() {
	constexpr uint64_t C = 0x200000;
	std::mt19937_64    rng(0x7777343132);
	for (int it = 0; it < 4000; it++) {
		const size_t         n    = 1 + rng() % 200;
		const uint64_t       base = (rng() % 512) * C + (it % 2 == 0 ? 0 : (1 + rng() % 511) * 0x1000);
		std::vector<uint8_t> prev(n), now(n);
		for (size_t i = 0; i < n; i++) {
			prev[i] = rng() % 2;
			now[i]  = prev[i] == 1 ? (rng() % 3 != 0) : (rng() % 5 == 0); // most zero slots stay zero; a few become zero
		}
		std::set<uint64_t> named;
		for (uint64_t g = (base / C) * C; g <= base + n * C; g += C) {
			if (rng() % 3 == 0) named.insert(g);
		}
		const size_t keep = rng() % 6;
		uint64_t     asked = 0;
		const auto   t = ww412::classify(prev, now, base, C, keep, [&](uint64_t g) {
            asked++;
            check(g % C == 0, "the question is asked on the file's chunk grid");
            return named.count(g) != 0;
        });
		uint64_t              turned = 0, nm = 0;
		std::vector<uint64_t> un;
		for (size_t i = 0; i < n; i++) {
			if (prev[i] != 1 || now[i] != 0) continue;
			turned++;
			const uint64_t c = base + i * C;
			bool           is = false;
			for (uint64_t g = (c / C) * C; g < c + C; g += C) is = is || named.count(g) != 0;
			if (is) nm++;
			else un.push_back(c);
		}
		check(t.turned == turned && t.named == nm, "turned and named as the model counts them");
		check(t.turned - t.named == un.size(), "named + not named = turned");
		if (un.size() > keep) un.resize(keep);
		check(t.unnamed == un, "the kept list: the first not-named slots, in order, at most keep");
		check(asked <= 2 * turned, "at most two questions per turned slot");
	}
	{
		const std::vector<uint8_t> a = {1, 1, 0}, b = {0, 0};
		const auto                 t = ww412::classify(a, b, 0, C, 4, [](uint64_t) { return false; });
		check(t.turned == 0 && t.named == 0 && t.unnamed.empty(), "a changed span: no comparison");
	}
	{ // a slot off the grid, between two chunks: named when either chunk is
		const std::vector<uint8_t> a = {1}, b = {0};
		const uint64_t             base = 5 * C + 0x4000;
		check(ww412::classify(a, b, base, C, 4, [&](uint64_t g) { return g == 5 * C; }).named == 1, "named by the lower chunk");
		check(ww412::classify(a, b, base, C, 4, [&](uint64_t g) { return g == 6 * C; }).named == 1, "named by the upper chunk");
		check(ww412::classify(a, b, base, C, 4, [&](uint64_t g) { return g == 7 * C; }).named == 0, "not named by a chunk it does not touch");
	}
	check(!ww412::on(), "the catcher is off when the variable is unset");
	std::printf("ww0412: %" PRIu64 " of %" PRIu64 "; end\n", g_ok, g_checks);
	return g_ok == g_checks ? 0 : 1;
}
