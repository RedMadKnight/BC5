// BC5 experiment 0412: CPU test of bd0412.inc (tag bd412): the list of heaps imported by data.
//   - unset, empty and commas alone give no name (nothing changes);
//   - names keep their spaces ("Decal Job Scheduler"), empty items are skipped, a repeated name is listed once;
//   - has() is exact: no prefix match ("DynamicHeap" does not take "DynamicHeap Small"), no null name;
//   - a random list parses to the set a model splits it into.
// build: g++ -std=c++20 -O1 -Wall -Wextra -Werror bd0412.cpp -o bd0412
#include <algorithm>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <random>
#include <string>
#include <vector>

#include "bd0412.inc"

static uint64_t g_checks = 0, g_ok = 0;
static void     check(bool c, const char* what) {
	g_checks++;
	if (c) g_ok++;
	else if (g_checks - g_ok < 20) std::printf("FAIL: %s\n", what);
}

int main() {
	check(bd412::parse(nullptr).empty(), "unset: no name");
	check(bd412::parse("").empty(), "empty: no name");
	check(bd412::parse(",,,").empty(), "commas alone: no name");
	{
		const auto v = bd412::parse("CommitIABufferAllocator,,Decal Job Scheduler,DynamicHeap,CommitIABufferAllocator,");
		check(v.size() == 3, "three names, the repeated one once");
		check(bd412::has(v, "CommitIABufferAllocator") && bd412::has(v, "Decal Job Scheduler") && bd412::has(v, "DynamicHeap"), "each name is found");
		check(!bd412::has(v, "DynamicHeap Small") && !bd412::has(v, "Dynamic") && !bd412::has(v, "") && !bd412::has(v, nullptr), "exact match only");
		check(!bd412::has(v, "commitiabufferallocator"), "the case counts");
	}
	check(!bd412::has({}, "AMM"), "an empty list has nothing");
	const char*     words[] = {"AMM", "RenderGpuWcLarge", "RenderGpuRwLarge", "Physics", "Physics query allocator", "DynamicHeap", "DynamicHeap Small", "ComponentHeap"};
	std::mt19937_64 rng(0x6264343132);
	for (int it = 0; it < 3000; it++) {
		std::string              s;
		std::vector<std::string> model;
		const int                n = static_cast<int>(rng() % 7);
		for (int i = 0; i < n; i++) {
			if (rng() % 4 == 0) s += ",";
			const std::string w = words[rng() % 8];
			s += w;
			if (std::find(model.begin(), model.end(), w) == model.end()) model.push_back(w);
			if (i + 1 < n || rng() % 3 == 0) s += ",";
		}
		const auto v = bd412::parse(s.c_str());
		check(v == model, "the list as the model splits it, in order");
		for (const char* w: words) check(bd412::has(v, w) == (std::find(model.begin(), model.end(), std::string(w)) != model.end()), "has() as the model");
	}
	std::printf("bd0412: %" PRIu64 " of %" PRIu64 "; end\n", g_ok, g_checks);
	return g_ok == g_checks ? 0 : 1;
}
