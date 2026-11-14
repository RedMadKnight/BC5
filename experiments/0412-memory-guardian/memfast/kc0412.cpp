// BC5 experiment 0412: CPU test of kc0412.inc (tag kc412): what became of a dropped cover piece.
//   - against a model that asks page by page what the new list maps there: data on any page -> kData; else a cover on
//     any page -> kCover; else kGone; on 6,000 generated lists (disjoint, sorted, covers and data mixed, with gaps);
//   - fixed cases: an empty list, a neighbour that only touches, the piece replaced whole, cut in two;
//   - the tally keeps the first data address and counts by kind;
//   - off when the variable is unset.
// build: g++ -std=c++20 -O1 -Wall -Wextra -Werror kc0412.cpp -o kc0412
#include <algorithm>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <random>
#include <vector>

#include "kc0412.inc"

struct M {
	uint64_t va, size;
	uint32_t id;
};
static uint64_t g_checks = 0, g_ok = 0;
static void     check(bool c, const char* what) {
	g_checks++;
	if (c) g_ok++;
	else if (g_checks - g_ok < 20) std::printf("FAIL: %s\n", what);
}
constexpr uint64_t P     = 0x1000;
constexpr uint32_t COVER = 7;
static bool        is_cover(uint32_t id) { return id == COVER; }
static kc412::Kind model(uint64_t va, uint64_t size, const std::vector<M>& want) {
	bool data = false, cover = false;
	for (uint64_t a = va; a < va + size; a += P) {
		for (const auto& m: want) {
			if (a >= m.va && a < m.va + m.size) (m.id == COVER ? cover : data) = true;
		}
	}
	return data ? kc412::kData : (cover ? kc412::kCover : kc412::kGone);
}

int main() {
	{
		const std::vector<M> none;
		check(kc412::after(0x10000, 0x2000, none, is_cover) == kc412::kGone, "an empty list: gone");
		const std::vector<M> touch = {{0xe000, 0x2000, 1}, {0x12000, 0x1000, 1}};
		check(kc412::after(0x10000, 0x2000, touch, is_cover) == kc412::kGone, "neighbours that only touch: gone");
		const std::vector<M> whole = {{0x10000, 0x2000, 3}};
		check(kc412::after(0x10000, 0x2000, whole, is_cover) == kc412::kData, "replaced whole by data");
		const std::vector<M> cut = {{0x10000, 0x1000, COVER}, {0x11000, 0x1000, COVER}};
		check(kc412::after(0x10000, 0x2000, cut, is_cover) == kc412::kCover, "cut in two covers");
		const std::vector<M> mixed = {{0x10000, 0x1000, COVER}, {0x11000, 0x1000, 9}};
		check(kc412::after(0x10000, 0x2000, mixed, is_cover) == kc412::kData, "a cover and data: data");
		const std::vector<M> big = {{0x8000, 0x20000, 4}};
		check(kc412::after(0x10000, 0x2000, big, is_cover) == kc412::kData, "inside one larger data mapping");
	}
	std::mt19937_64 rng(0x6b63343132);
	for (int it = 0; it < 6000; it++) {
		std::vector<M> want;
		uint64_t       at = 0x100000 + (rng() % 4) * P;
		const int      n  = static_cast<int>(rng() % 10);
		for (int i = 0; i < n; i++) {
			at += (rng() % 3) * P; // a gap of 0-2 pages
			const uint64_t size = (1 + rng() % 5) * P;
			want.push_back({at, size, (rng() % 2) != 0 ? COVER : static_cast<uint32_t>(1 + rng() % 5)});
			at += size;
		}
		for (int q = 0; q < 8; q++) {
			const uint64_t va = 0x100000 + (rng() % 48) * P, size = (1 + rng() % 6) * P;
			check(kc412::after(va, size, want, is_cover) == model(va, size, want), "the same answer as the page model");
		}
	}
	{
		kc412::Tally t;
		t.add(kc412::kCover, 0x1000, 0x1000);
		t.add(kc412::kData, 0x5000, 0x2000);
		t.add(kc412::kData, 0x9000, 0x1000);
		t.add(kc412::kGone, 0x3000, 0x1000);
		check(t.n[kc412::kData] == 2 && t.bytes[kc412::kData] == 0x3000 && t.first_data_va == 0x5000, "the tally: data pieces, bytes, the first address");
		check(t.n[kc412::kCover] == 1 && t.n[kc412::kGone] == 1, "the tally: the other kinds");
	}
	check(!kc412::on(), "off when the variable is unset");
	std::printf("kc0412: %" PRIu64 " of %" PRIu64 "; end\n", g_ok, g_checks);
	return g_ok == g_checks ? 0 : 1;
}
