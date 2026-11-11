// BC5 experiment 0412: CPU test of nogpu0412.inc (tag ng412), the selection of chunks that are not pinned.
// plan() against a byte-level model on random layouts: a chunk is in the result exactly when at least one view
// touches it and every view that touches it is of a listed heap with neither GPU bit. Also: an empty list gives
// nothing; a GPU bit on one of two views over a chunk keeps the chunk; adding a GPU bit to a view (the title's later
// mprotect) takes its chunks out of the result; the result is sorted and unique.
// build: g++ -std=c++20 -O1 -Wall -Wextra -Werror nogpu0412.cpp -o nogpu0412
#include <algorithm>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <iterator>
#include <map>
#include <random>
#include <string>
#include <vector>

#include "nogpu0412.inc"

static uint64_t g_checks = 0, g_ok = 0;
static void check(bool c, const char* what) {
	g_checks++;
	if (c) g_ok++;
	else if (g_checks - g_ok < 20) std::printf("FAIL: %s\n", what);
}

struct V {
	uint64_t    va, size, off;
	std::string name;
	int         prot;
};

static constexpr uint64_t K = 2ull << 20;

static std::vector<uint64_t> model(const std::vector<V>& views, const std::vector<std::string>& list) {
	std::map<uint64_t, int> state; // chunk -> 1 only qualifying views so far, 2 a blocking view
	for (const auto& v: views) {
		if (v.size == 0) continue;
		const bool q = (v.prot & 0x30) == 0 && std::find(list.begin(), list.end(), v.name) != list.end();
		for (uint64_t b = v.off; b < v.off + v.size; b += 4096) { // every page of the view marks its chunk
			int& s = state[b - b % K];
			if (!q) s = 2;
			else if (s == 0) s = 1;
		}
	}
	std::vector<uint64_t> out;
	for (const auto& kv: state) {
		if (kv.second == 1) out.push_back(kv.first);
	}
	return out;
}

int main() {
	const std::vector<std::string> list = {"Physics", "DynamicHeap", "InitAllocator", "ComponentHeap"};
	const char* const              pool[] = {"Physics", "DynamicHeap", "InitAllocator", "ComponentHeap", "AMM", "RenderGpuWcLarge", "Wwise"};
	const int                      prots[] = {0xc2, 0xc2, 0xc2, 0xf2, 0x32, 0x13, 0x02, 0x3f2};
	std::mt19937_64 rng(4120);
	for (int round = 0; round < 3000; round++) {
		std::vector<V> views;
		const int      n = 1 + static_cast<int>(rng() % 40);
		for (int i = 0; i < n; i++) {
			V v;
			v.off  = (rng() % 4096) * 4096;                // anywhere in the first 16 MiB, page aligned: views share chunks
			v.size = (1 + rng() % 1024) * 4096;            // up to 4 MiB
			v.va   = 0x1000000000ull + v.off;
			v.name = pool[rng() % 7];
			v.prot = prots[rng() % 8];
			if (rng() % 17 == 0) v.size = 0;
			views.push_back(v);
		}
		const auto got = ng412::plan(views, K, list);
		check(got == model(views, list), "plan() equals the byte-level model");
		check(std::is_sorted(got.begin(), got.end()) && std::adjacent_find(got.begin(), got.end()) == got.end(), "sorted and unique");
		check(ng412::plan(views, K, {}).empty(), "an empty list leaves nothing out");
		// the title gives every view a GPU bit: nothing may stay out
		auto all = views;
		for (auto& v: all) v.prot |= 0x10;
		check(ng412::plan(all, K, list).empty(), "with a GPU bit everywhere nothing is left out");
		// one view gets a GPU bit: none of its chunks may stay out
		if (!views.empty()) {
			auto   one = views;
			auto&  v   = one[rng() % one.size()];
			v.prot |= 0x20;
			const auto g2 = ng412::plan(one, K, list);
			bool       ok = true;
			for (uint64_t c = v.off - v.off % K; v.size != 0 && c < v.off + v.size; c += K) ok = ok && !std::binary_search(g2.begin(), g2.end(), c);
			check(ok, "a view that gained a GPU bit has none of its chunks left out");
		}
	}
	{ // the plain case: a heap of 192 MiB without a GPU bit beside a GPU heap that shares its last chunk
		std::vector<V> views = {{0, 192ull << 20, 0, "Physics", 0xc2}, {0, 4096, (192ull << 20) - 4096, "RenderGpuWcLarge", 0x32}};
		const auto     got   = ng412::plan(views, K, list);
		check(got.size() == 95 && got.front() == 0 && got.back() == (188ull << 20), "95 of the 96 chunks are left out; the shared last one is imported");
	}
	std::printf("nogpu0412: %" PRIu64 " of %" PRIu64 "; end\n", g_ok, g_checks);
	return g_ok == g_checks ? 0 : 1;
}
