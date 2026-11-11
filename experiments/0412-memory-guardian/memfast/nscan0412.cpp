// BC5 experiment 0412: CPU test of nscan0412.inc (tag ns412): the ranges of the left-out memory and the search of
// command-buffer words for addresses in them.
//   ranges(): against a page-level model on random layouts (a page is in a range exactly when a view holds it and its
//   chunk is left out; the name is the view's); sorted, disjoint, neighbours of one name merged.
//   find(): against a linear search. scan(): against a brute-force search of both address forms; planted addresses
//   are found at their position; the table candidates are distinct, inside the window and in no range.
// build: g++ -std=c++20 -O1 -Wall -Wextra -Werror nscan0412.cpp -o nscan0412
#include <algorithm>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <random>
#include <string>
#include <vector>

#include "nscan0412.inc"

static uint64_t g_checks = 0, g_ok = 0;
static void check(bool c, const char* what) {
	g_checks++;
	if (c) g_ok++;
	else if (g_checks - g_ok < 20) std::printf("FAIL: %s\n", what);
}

struct V {
	uint64_t    va, size, off;
	std::string name;
};

static constexpr uint64_t K = 2ull << 20;
static constexpr uint64_t P = 4096;

int main() {
	const char* const pool[] = {"Physics", "DynamicHeap", "InitAllocator", "ComponentHeap", "AMM"};
	std::mt19937_64   rng(41239);
	for (int round = 0; round < 1500; round++) {
		// Views: disjoint in address and in the file, page-aligned.
		std::vector<V> views;
		uint64_t       va = 0x1100000000ull + (rng() % 64) * P, off = (rng() % 8) * P;
		const int      n = 1 + static_cast<int>(rng() % 24);
		for (int i = 0; i < n; i++) {
			va += (rng() % 3 == 0 ? 0 : (rng() % 600) * P);
			off += (rng() % 3 == 0 ? 0 : (rng() % 600) * P);
			const uint64_t size = (1 + rng() % 1500) * P;
			views.push_back({va, size, off, pool[rng() % 5]});
			va += size;
			off += size;
		}
		std::vector<uint64_t> chunks;
		for (uint64_t c = 0; c < off + K; c += K) {
			if (rng() % 3 == 0) chunks.push_back(c);
		}
		std::vector<std::string>       names;
		const std::vector<ns412::Range> r = ns412::ranges(views, chunks, K, names);
		// The model: page -> name.
		std::map<uint64_t, std::string> model;
		for (const auto& v: views) {
			for (uint64_t b = 0; b < v.size; b += P) {
				const uint64_t o = v.off + b;
				if (std::binary_search(chunks.begin(), chunks.end(), o - o % K)) model[v.va + b] = v.name;
			}
		}
		uint64_t pages = 0;
		bool     shape = true, right = true;
		for (size_t i = 0; i < r.size(); i++) {
			if (r[i].lo >= r[i].hi || r[i].name >= names.size()) shape = false;
			if (i > 0 && (r[i - 1].hi > r[i].lo || (r[i - 1].hi == r[i].lo && r[i - 1].name == r[i].name))) shape = false;
			for (uint64_t a = r[i].lo; a < r[i].hi; a += P) {
				pages++;
				const auto it = model.find(a);
				if (it == model.end() || it->second != names[r[i].name]) right = false;
			}
		}
		check(shape, "ranges: sorted, disjoint, merged, named");
		check(right, "ranges: every page of a range is a left-out page of that heap");
		check(pages == model.size(), "ranges: every left-out page is in a range");
		// find() against a linear search.
		bool same = true;
		for (int i = 0; i < 300; i++) {
			uint64_t a = 0x1100000000ull + rng() % (va - 0x1100000000ull + 64 * P);
			if (!r.empty() && i % 4 == 0) {
				const auto& q = r[rng() % r.size()];
				a             = (i % 8 == 0) ? q.lo : ((i % 8 == 4) ? q.hi - 1 : q.hi);
			}
			int lin = -1;
			for (size_t k = 0; k < r.size(); k++) {
				if (a >= r[k].lo && a < r[k].hi) lin = static_cast<int>(k);
			}
			if (ns412::find(r, a) != lin) same = false;
		}
		check(same, "find: equal to a linear search");
		// scan(): random words with planted addresses in both forms.
		std::vector<uint32_t> w(400);
		for (auto& x: w) x = static_cast<uint32_t>(rng());
		std::vector<uint32_t> planted;
		if (!r.empty()) {
			for (int i = 0; i < 6; i++) {
				const auto&    q = r[rng() % r.size()];
				const uint64_t a = q.lo + rng() % (q.hi - q.lo);
				const uint32_t at = 10 + static_cast<uint32_t>(i) * 60;
				if (i % 2 == 0) {
					w[at]     = static_cast<uint32_t>(a);
					w[at + 1] = static_cast<uint32_t>(a >> 32) | 0x00100000u;
				} else {
					const uint64_t s = a & ~0xffull; // the shifted form has no low 8 bits
					if (ns412::find(r, s) < 0) continue;
					w[at]     = static_cast<uint32_t>(s >> 8);
					w[at + 1] = static_cast<uint32_t>(s >> 40) | 0xc1600000u;
				}
				planted.push_back(at);
			}
		}
		const uint64_t win_lo = 0x1100000000ull, win_hi = va + 64 * P;
		// A table candidate that is in no range.
		w[395] = static_cast<uint32_t>(win_lo + 8);
		w[396] = static_cast<uint32_t>((win_lo + 8) >> 32);
		std::vector<ns412::Hit> hits;
		std::vector<uint64_t>   others;
		ns412::scan(w.data(), static_cast<uint32_t>(w.size()), r, hits, 1000, &others, win_lo, win_hi);
		std::vector<ns412::Hit> brute;
		for (uint32_t i = 0; i + 1 < w.size(); i++) {
			const uint64_t a = (static_cast<uint64_t>(w[i + 1] & 0xffffu) << 32) | w[i];
			const uint64_t b = (static_cast<uint64_t>(w[i + 1] & 0xffu) << 40) | (static_cast<uint64_t>(w[i]) << 8);
			int            ka = -1, kb = -1;
			for (size_t k = 0; k < r.size(); k++) {
				if (a >= r[k].lo && a < r[k].hi) ka = static_cast<int>(k);
				if (b >= r[k].lo && b < r[k].hi) kb = static_cast<int>(k);
			}
			if (ka >= 0) brute.push_back({i, 0, a, static_cast<uint32_t>(ka)});
			else if (kb >= 0) brute.push_back({i, 1, b, static_cast<uint32_t>(kb)});
		}
		bool eq = hits.size() == brute.size();
		for (size_t i = 0; eq && i < hits.size(); i++) eq = hits[i].at == brute[i].at && hits[i].form == brute[i].form && hits[i].addr == brute[i].addr && hits[i].range == brute[i].range;
		check(eq, "scan: equal to the brute-force search");
		bool found = true;
		for (const uint32_t at: planted) {
			bool f = false;
			for (const auto& h: hits) f = f || h.at == at;
			found = found && f;
		}
		check(found, "scan: every planted address is found at its position");
		bool oth = others.size() <= ns412::kMaxTables;
		for (size_t i = 0; i < others.size(); i++) {
			if (others[i] < win_lo || others[i] >= win_hi || ns412::find(r, others[i]) >= 0) oth = false;
			for (size_t k = 0; k < i; k++) oth = oth && others[k] != others[i];
		}
		check(oth, "scan: table candidates are distinct, in the window, in no range");
		if (!r.empty() && ns412::find(r, win_lo + 8) < 0) check(std::find(others.begin(), others.end(), win_lo + 8) != others.end(), "scan: the planted table candidate is listed");
		// The cap on hits.
		std::vector<ns412::Hit> few;
		ns412::scan(w.data(), static_cast<uint32_t>(w.size()), r, few, 2, nullptr, 0, 0);
		check(few.size() == std::min<size_t>(2, brute.size()), "scan: the cap on hits holds");
	}
	// No ranges: nothing.
	{
		std::vector<ns412::Hit> hits;
		std::vector<uint64_t>   others;
		const uint32_t          w[4] = {1, 2, 3, 4};
		ns412::scan(w, 4, {}, hits, 10, &others, 0, ~0ull);
		check(hits.empty() && others.empty(), "scan: no ranges, nothing");
		std::vector<std::string> names;
		check(ns412::ranges(std::vector<V> {{0x1000, 0x2000, 0, "Physics"}}, {}, K, names).empty(), "ranges: no chunks, nothing");
	}
	std::printf("nscan0412: %" PRIu64 " of %" PRIu64 "; end\n", g_ok, g_checks);
	return g_ok == g_checks ? 0 : 1;
}
