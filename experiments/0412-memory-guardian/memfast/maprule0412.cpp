// BC5 experiment 0412: CPU test of maprule0412.inc (tag mr412).
//   view_chunks(): against a page-level model on random views (a chunk is named exactly when a page of the view lies
//   in it; ascending, each once), and the rule's selection over random layouts of views in a file (the union of the
//   views' chunks is exactly the set of chunks that hold a page of any view).
//   in_bg(): the span's ends. env_digit(): what counts as on. classify(): one label per case, the order of the questions.
// build: g++ -std=c++20 -O1 -Wall -Wextra -Werror maprule0412.cpp -o maprule0412
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <set>
#include <vector>

#include "maprule0412.inc"

#ifdef _WIN32 // the laptop's compiler: the same checks, the C runtime's names
static int setenv(const char* n, const char* v, int) { return _putenv_s(n, v); }
static int unsetenv(const char* n) { return _putenv_s(n, ""); }
#endif

static uint64_t g_checks = 0, g_ok = 0;
static void check(bool c, const char* what) {
	g_checks++;
	if (c) g_ok++;
	else if (g_checks - g_ok < 20) std::printf("FAIL: %s\n", what);
}

int main() {
	constexpr uint64_t kChunk = 2ull << 20, kPage = 4096;
	std::mt19937_64 rng(0x412412);
	// view_chunks against pages
	for (int it = 0; it < 4000; it++) {
		const uint64_t off  = (rng() % (64 * kChunk / kPage)) * kPage;
		const uint64_t size = (rng() % 3 == 0) ? (1 + rng() % 8) * kPage : (1 + rng() % (6 * kChunk / kPage)) * kPage;
		std::vector<uint64_t> got;
		mr412::view_chunks(off, size, kChunk, got);
		std::set<uint64_t> want;
		for (uint64_t p = off; p < off + size; p += kPage) want.insert(p & ~(kChunk - 1));
		check(got.size() == want.size(), "view_chunks: as many chunks as the pages touch");
		bool same = true, asc = true;
		size_t i = 0;
		for (const uint64_t w: want) {
			if (i >= got.size() || got[i] != w) same = false;
			if (i > 0 && i < got.size() && got[i] <= got[i - 1]) asc = false;
			i++;
		}
		check(same, "view_chunks: exactly the chunks that hold a page of the view");
		check(asc, "view_chunks: ascending, each once");
	}
	{
		std::vector<uint64_t> got;
		mr412::view_chunks(5 * kChunk, 0, kChunk, got);
		check(got.empty(), "view_chunks: an empty view names nothing");
		mr412::view_chunks(5 * kChunk, kChunk, kChunk, got);
		check(got.size() == 1 && got[0] == 5 * kChunk, "view_chunks: an aligned view of one chunk names that chunk only");
		got.clear();
		mr412::view_chunks(5 * kChunk - kPage, 2 * kPage, kChunk, got);
		check(got.size() == 2 && got[0] == 4 * kChunk && got[1] == 5 * kChunk, "view_chunks: a view across a boundary names both");
	}
	// the rule over a layout: the union of the views' chunks against a page model of the file
	for (int it = 0; it < 1500; it++) {
		const uint64_t file_chunks = 8 + rng() % 56;
		std::vector<char> page(file_chunks * kChunk / kPage, 0);
		std::set<uint64_t> got;
		const int views = 1 + static_cast<int>(rng() % 24);
		for (int v = 0; v < views; v++) {
			const uint64_t off  = (rng() % page.size()) * kPage;
			uint64_t       size = (1 + rng() % 700) * kPage;
			if (off + size > page.size() * kPage) size = page.size() * kPage - off;
			for (uint64_t p = off; p < off + size; p += kPage) page[p / kPage] = 1;
			std::vector<uint64_t> c;
			mr412::view_chunks(off, size, kChunk, c);
			got.insert(c.begin(), c.end());
		}
		std::set<uint64_t> want;
		for (size_t p = 0; p < page.size(); p++) {
			if (page[p]) want.insert((p * kPage) & ~(kChunk - 1));
		}
		check(got == want, "rule: the chunks selected are exactly those that hold a page under any view");
		bool every = true;
		for (size_t p = 0; p < page.size(); p++) {
			if (page[p] && got.count((p * kPage) & ~(kChunk - 1)) == 0) every = false;
		}
		check(every, "rule: no page under a view is left without its chunk");
	}
	// the background span
	check(mr412::in_bg(mr412::kBgLo, mr412::kBgLo + 4096), "in_bg: the first page");
	check(mr412::in_bg(mr412::kBgHi - 4096, mr412::kBgHi), "in_bg: the last page");
	check(!mr412::in_bg(mr412::kBgLo - 4096, mr412::kBgLo + 4096), "in_bg: a piece across the lower end is not inside");
	check(!mr412::in_bg(mr412::kBgHi - 4096, mr412::kBgHi + 4096), "in_bg: a piece across the upper end is not inside");
	check(!mr412::in_bg(0, 0x200000), "in_bg: address 0 is outside");
	check(!mr412::in_bg(0x800000005000ull, 0x800000006000ull), "in_bg: a junk address is outside");
	check(!mr412::in_bg(mr412::kBgLo + 8192, mr412::kBgLo + 8192), "in_bg: an empty piece is not inside");
	check(mr412::kBgLo >= 0x100000000ull, "span: above libdrm's 32-bit range");
	check(mr412::kBgHi <= 0xFE00000000ull, "span: below the device's code page");
	check(((mr412::kBgLo | (mr412::kBgHi - mr412::kBgLo)) & 0xffff) == 0, "span: 64 KiB aligned, as map_prt_window asks");
	check(mr412::kBgLo <= 0x8000000000ull && mr412::kBgHi >= 0x9000000000ull, "span: holds the AMM window");
	// env_digit
	setenv("MR412_T", "1", 1);
	check(mr412::env_digit("MR412_T", 2) == 1, "env: 1 is 1");
	setenv("MR412_T", "2", 1);
	check(mr412::env_digit("MR412_T", 2) == 2 && mr412::env_digit("MR412_T", 1) == 0, "env: 2 is 2 where 2 exists and off where it does not");
	setenv("MR412_T", "0", 1);
	check(mr412::env_digit("MR412_T", 2) == 0, "env: 0 is off");
	setenv("MR412_T", "", 1);
	check(mr412::env_digit("MR412_T", 2) == 0, "env: empty is off");
	setenv("MR412_T", "10", 1);
	check(mr412::env_digit("MR412_T", 2) == 0, "env: 10 is off");
	setenv("MR412_T", "yes", 1);
	check(mr412::env_digit("MR412_T", 2) == 0, "env: a word is off");
	unsetenv("MR412_T");
	check(mr412::env_digit("MR412_T", 2) == 0, "env: unset is off");
	check(mr412::rule() == 0 && !mr412::rule_for(0) && !mr412::rule_for(1) && !mr412::prt_bg() && mr412::learn_log() == 0, "all three switches are off when unset");
	// classify: every case has a label, and the labels follow the order of the questions
	for (int m = 0; m < 128; m++) {
		const bool  junk = m & 1, range = m & 2, view = m & 4, lazy = m & 8, eager = m & 16, imp = m & 32, mapped = m & 64;
		const char* s = mr412::classify(junk, range, view, lazy, eager, imp, mapped);
		check(s != nullptr && s[0] == 'K', "classify: a label for every case");
		if (junk) check(std::strncmp(s, "K4", 2) == 0, "classify: a junk address is K4 whatever else");
		else if (!range && !view) check(std::strncmp(s, "K3", 2) == 0, "classify: no range and no view is a hole");
		else if (view && !imp) check(std::strncmp(s, "K1", 2) == 0, "classify: a view whose chunk is not imported is K1");
		else if (view && !mapped) check(std::strncmp(s, "K5", 2) == 0, "classify: imported, not mapped is K5");
		else if (view) check(std::strncmp(s, "K6", 2) == 0, "classify: imported and mapped is K6");
		else check(std::strncmp(s, mapped ? "K6" : "K2", 2) == 0, "classify: a guest range outside direct memory is K2 unless mapped");
	}
	check(std::strstr(mr412::classify(false, true, true, true, false, false, false), "LAZY") != nullptr, "classify: the lazy view is named");
	check(std::strstr(mr412::classify(false, true, true, false, false, false, false), "BY-DATA") != nullptr, "classify: the by-data view is named");
	check(std::strstr(mr412::classify(false, true, true, false, true, false, false), "EAGER") != nullptr, "classify: the eager view is named");
	std::printf("maprule0412: %" PRIu64 " of %" PRIu64 "; end\n", g_ok, g_checks);
	return g_ok == g_checks ? 0 : 1;
}
