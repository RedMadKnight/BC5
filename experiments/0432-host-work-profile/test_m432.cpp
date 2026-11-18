// BC5 exp 0432, item M (tag m432): a CPU test of the two changed passes of the mapping rebuild, against the old ones.
// The two functions below are the statements mkt432.py puts into direct_sync_one, copied by hand (a model of the
// unit's text, not the unit itself): build with  g++ -std=c++20 -O1 -o test_m432 test_m432.cpp && ./test_m432
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <random>
#include <vector>

struct DMap {
	uint64_t va, size, bo_off;
	uint32_t id;
	bool     operator==(const DMap& o) const { return va == o.va && size == o.size && bo_off == o.bo_off && id == o.id; }
};

// the new order pass; returns whether the fast path was taken
static bool order_new(std::vector<DMap>& want, size_t m432_n1) {
	const auto m432_less   = [](const DMap& a, const DMap& b) { return a.va < b.va; };
	const auto m432_rising = [&want](size_t from, size_t to) {
		for (size_t i = from + 1; i < to; i++) {
			if (want[i - 1].va >= want[i].va) return false;
		}
		return true;
	};
	bool m432_fast = m432_rising(0, m432_n1) && m432_rising(m432_n1, want.size());
	if (m432_fast) {
		std::inplace_merge(want.begin(), want.begin() + static_cast<std::ptrdiff_t>(m432_n1), want.end(), m432_less);
		m432_fast = m432_rising(0, want.size());
	}
	if (!m432_fast) std::sort(want.begin(), want.end(), m432_less);
	return m432_fast;
}

// the drop pass: which of `maps` are kept; fast = the new walk
static std::vector<int> kept(const std::vector<DMap>& maps, const std::vector<DMap>& want, bool m432_fast) {
	std::vector<int> out;
	size_t           m432_k    = 0;
	uint64_t         m432_prev = 0;
	for (const auto& m: maps) {
		auto w = want.end();
		if (m432_fast && m.va >= m432_prev) {
			while (m432_k < want.size() && want[m432_k].va < m.va) m432_k++;
			w = want.begin() + static_cast<std::ptrdiff_t>(m432_k);
		} else {
			w      = std::lower_bound(want.begin(), want.end(), m.va, [](const DMap& a, uint64_t va) { return a.va < va; });
			m432_k = static_cast<size_t>(w - want.begin());
		}
		m432_prev = m.va;
		out.push_back(w != want.end() && *w == m ? 1 : 0);
	}
	return out;
}

int main() {
	std::mt19937_64 rng(432);
	int             cases = 0, fast = 0, bad = 0;
	for (int t = 0; t < 20000; t++) {
		const int mode = t % 5; // 0: both runs rising, disjoint addresses; 1: duplicates across the runs; 2: first run unsorted; 3: second unsorted; 4: empty runs
		std::vector<DMap> a, b;
		const size_t      na = mode == 4 ? rng() % 2 : rng() % 60, nb = mode == 4 ? rng() % 2 : rng() % 30;
		uint64_t          va = 0x1000;
		for (size_t i = 0; i < na; i++) { va += 0x1000 * (1 + rng() % 4); a.push_back({va * 2, 0x1000, rng() % 16, static_cast<uint32_t>(1 + rng() % 5)}); }
		va = 0x1000;
		for (size_t i = 0; i < nb; i++) { va += 0x1000 * (1 + rng() % 6); b.push_back({mode == 1 ? va * 2 : va * 2 + 0x1000, 0x1000, 0, 9}); }
		if (mode == 2 && a.size() > 1) std::shuffle(a.begin(), a.end(), rng);
		if (mode == 3 && b.size() > 1) std::shuffle(b.begin(), b.end(), rng);
		std::vector<DMap> want = a;
		want.insert(want.end(), b.begin(), b.end());
		std::vector<DMap> ref = want;
		std::stable_sort(ref.begin(), ref.end(), [](const DMap& x, const DMap& y) { return x.va < y.va; });
		std::vector<DMap> got = want;
		const bool        f   = order_new(got, a.size());
		fast += f ? 1 : 0;
		// the old sort is not stable, so with equal addresses only the address order is fixed; without, the lists are equal
		bool same = got.size() == ref.size();
		for (size_t i = 0; same && i < got.size(); i++) same = got[i].va == ref[i].va && (mode == 1 || got[i] == ref[i]);
		if (f) { // the fast path promises a strictly rising list, which has one order only
			for (size_t i = 0; same && i < got.size(); i++) same = got[i] == ref[i];
		}
		// the maps of the last rebuild: some of want, some changed, some gone; rising by address (as S.maps), once in 50 not
		std::vector<DMap> maps;
		for (const auto& w: got) {
			const uint64_t r = rng() % 10;
			if (r < 6) maps.push_back(w);
			else if (r < 8) { DMap c = w; c.id += 100; maps.push_back(c); }
		}
		for (int i = 0; i < 5; i++) maps.push_back({0x1000 * (1 + rng() % 400), 0x1000, 0, 7});
		std::sort(maps.begin(), maps.end(), [](const DMap& x, const DMap& y) { return x.va < y.va; });
		if (t % 50 == 0 && maps.size() > 2) std::swap(maps[0], maps[maps.size() - 1]);
		const bool ok = same && kept(maps, got, f) == kept(maps, got, false);
		cases++;
		if (!ok) {
			bad++;
			if (bad <= 5) std::printf("FAIL case %d mode %d (%zu + %zu)\n", t, mode, a.size(), b.size());
		}
	}
	std::printf("test_m432: %d cases, fast path in %d, %d failed: %s\n", cases, fast, bad, bad == 0 && fast > 3000 ? "PASS" : "FAIL");
	return bad == 0 && fast > 3000 ? 0 : 1;
}
