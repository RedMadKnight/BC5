// BC5 experiment 0412: CPU test of ph0412.inc (tag ph412): the search of a block for words that point into a range.
//   - against a model that looks at every multiple of 4 by itself, on 3,000 generated blocks with planted words
//     (plain pointers, words with fields above bit 40, words just outside the range, words at odd offsets);
//   - a planted word at a multiple of 4 is always found, with its position and value; one at an odd offset is not
//     reported as such (the search steps by 4);
//   - a block shorter than 8 bytes gives nothing; the last full word of a block is seen;
//   - plain() tells a pointer from a word with fields above bit 40; off when the variable is unset.
// build: g++ -std=c++20 -O1 -Wall -Wextra -Werror ph0412.cpp -o ph0412
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <random>
#include <vector>

#include "ph0412.inc"

static uint64_t g_checks = 0, g_ok = 0;
static void     check(bool c, const char* what) {
	g_checks++;
	if (c) g_ok++;
	else if (g_checks - g_ok < 20) std::printf("FAIL: %s\n", what);
}

int main() {
	constexpr uint64_t LO = 0x121a800000ull, HI = LO + 0x200000ull;
	std::mt19937_64    rng(0x7068343132);
	for (int it = 0; it < 3000; it++) {
		const size_t         n = 8 + static_cast<size_t>(rng() % 500);
		std::vector<uint8_t> b(n);
		for (auto& x: b) x = static_cast<uint8_t>(rng());
		const int plant = static_cast<int>(rng() % 5);
		for (int k = 0; k < plant; k++) {
			uint64_t w = LO + (rng() % 0x200000ull);
			switch (rng() % 4) {
				case 0: break;                                // a plain pointer
				case 1: w |= (rng() & 0xffffffull) << 40u; break; // fields above bit 40
				case 2: w = HI + (rng() % 64); break;         // just above the range
				default: w = LO - 1 - (rng() % 64); break;    // just below
			}
			const size_t at = static_cast<size_t>(rng() % (n - 7));
			std::memcpy(b.data() + at, &w, 8);
		}
		std::map<size_t, uint64_t> want, got;
		for (size_t i = 0; i + 8 <= n; i += 4) {
			uint64_t w;
			std::memcpy(&w, b.data() + i, 8);
			if ((w & ph412::kMask40) >= LO && (w & ph412::kMask40) < HI) want[i] = w;
		}
		bool once = true;
		ph412::scan(b.data(), n, LO, HI, [&](size_t i, uint64_t w) { once = once && got.emplace(i, w).second; });
		check(once, "no position comes twice");
		check(got == want, "the same positions and words as the model");
	}
	{
		uint8_t        b[24] = {0};
		const uint64_t w     = LO + 0x7000;
		std::memcpy(b + 16, &w, 8);
		int      hits = 0;
		size_t   at   = 0;
		uint64_t val  = 0;
		ph412::scan(b, sizeof(b), LO, HI, [&](size_t i, uint64_t v) {
			hits++;
			at  = i;
			val = v;
		});
		check(hits == 1 && at == 16 && val == w, "the last full word of a block is seen");
		hits = 0;
		ph412::scan(b + 16, 7, LO, HI, [&](size_t, uint64_t) { hits++; });
		check(hits == 0, "a block shorter than 8 bytes gives nothing");
		uint8_t c[24] = {0};
		std::memcpy(c + 5, &w, 8);
		hits = 0;
		ph412::scan(c, sizeof(c), LO, HI, [&](size_t i, uint64_t v) { hits += (i == 5 && v == w) ? 1 : 0; });
		check(hits == 0, "a word at an odd offset is not reported as one");
	}
	check(ph412::plain(LO + 5) && !ph412::plain((LO + 5) | (1ull << 44u)), "plain() tells a pointer from a word with fields above bit 40");
	check(!ph412::on(), "off when the variable is unset");
	std::printf("ph0412: %" PRIu64 " of %" PRIu64 "; end\n", g_ok, g_checks);
	return g_ok == g_checks ? 0 : 1;
}
