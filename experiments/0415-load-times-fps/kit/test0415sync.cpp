// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0415: CPU test of src/bc5/sync_fast.hpp (tag ls415d): each fast form against its old form.
//   subtract_fast vs subtract_old   random windows, pieces clipped to them, random mappings in any order, overlapping
//                                   each other, zero-sized, touching the window's ends, far outside it
//   inside_fast vs inside_old       ordered VMA lists (touching, with gaps, empty entries, both kinds) with ranges on
//                                   every boundary, empty ranges, reversed ranges; vmas_ordered on ordered and
//                                   disordered lists
//   NameMemo                        the same answers as the function it remembers, the function asked once per name
// Ends with "test0415sync: <passed> of <run>; end". Portable (runs on the laptop and on the box).
#include "bc5/sync_fast.hpp"

#include <cstdio>
#include <random>

namespace sf = bc5::sync_fast;

struct M {
	uint64_t va, size;
};
struct V {
	uint64_t start, end;
	bool     readonly;
};

static int g_run = 0, g_ok = 0;
static void check(bool v, const char* what) {
	g_run++;
	if (v) {
		g_ok++;
	} else {
		std::printf("FAIL: %s\n", what);
	}
}

int main() {
	std::mt19937_64 rng(0x0415'0415ull);
	auto            rnd = [&rng](uint64_t n) { return n == 0 ? 0 : rng() % n; };

	// ---- subtract
	uint64_t cases = 0, differ = 0, nonempty = 0;
	for (int round = 0; round < 20000; round++) {
		const uint64_t unit = round % 3 == 0 ? 1 : 0x1000;
		const uint64_t lo   = (1000 + rnd(2000)) * unit, hi = lo + (1 + rnd(400)) * unit;
		// the window clipped to a few "VMAs": pieces inside [lo, hi), in order, possibly touching
		std::vector<sf::Piece> pieces;
		for (uint64_t p = lo; p < hi;) {
			const uint64_t a = p + rnd(20) * unit, b = a + (1 + rnd(60)) * unit;
			if (a >= hi) break;
			pieces.emplace_back(a, b < hi ? b : hi);
			p = b;
		}
		if (round % 50 == 0) pieces.clear();
		std::vector<M> have;
		const int      n = static_cast<int>(rnd(60));
		for (int k = 0; k < n; k++) {
			const uint64_t kind = rnd(10);
			uint64_t       va, size;
			if (kind < 5) { // around the window
				va   = lo - (lo > 100 * unit ? rnd(100) * unit : 0) + rnd(500) * unit;
				size = rnd(80) * unit;
			} else if (kind < 7) { // exactly at an end
				va   = kind == 5 ? hi : (lo > 30 * unit ? lo - 30 * unit : 0);
				size = kind == 5 ? rnd(50) * unit : 30 * unit;
			} else if (kind < 8) { // zero-sized, inside
				va   = lo + rnd(hi - lo);
				size = 0;
			} else if (kind < 9) { // covering all of it
				va   = lo > 5 * unit ? lo - 5 * unit : 0;
				size = (hi - va) + 5 * unit;
			} else { // far away
				va   = hi + (1000 + rnd(100000)) * unit;
				size = rnd(1000) * unit;
			}
			have.push_back({va, size});
		}
		if (round % 4 == 0) std::sort(have.begin(), have.end(), [](const M& x, const M& y) { return x.va < y.va; });
		auto a = pieces, b = pieces;
		sf::subtract_old(a, have);
		sf::subtract_fast(b, have, lo, hi);
		cases++;
		if (a != b) differ++;
		if (!a.empty()) nonempty++;
	}
	check(differ == 0, "subtract: the fast form gives the old form's pieces in every case");
	check(nonempty > cases / 20 && nonempty < cases, "subtract: the cases include windows left with pieces and windows fully covered");
	std::printf("subtract: %llu cases, %llu differences, %llu with pieces left\n", static_cast<unsigned long long>(cases), static_cast<unsigned long long>(differ),
	            static_cast<unsigned long long>(nonempty));

	// ---- inside
	uint64_t q = 0, qd = 0, qtrue = 0;
	for (int round = 0; round < 3000; round++) {
		std::vector<V> vmas;
		uint64_t       p = 0x40000 + rnd(64) * 0x1000;
		const int      n = static_cast<int>(rnd(40));
		for (int k = 0; k < n; k++) {
			p += (rnd(3) == 0 ? 0 : rnd(8)) * 0x1000; // touching or with a gap
			const uint64_t len = (rnd(12) == 0 ? 0 : 1 + rnd(16)) * 0x1000; // an empty entry now and then
			vmas.push_back({p, p + len, rnd(3) == 0});
			p += len;
		}
		if (!sf::vmas_ordered(vmas)) {
			check(false, "inside: a list built in order is ordered");
			break;
		}
		std::vector<uint64_t> points = {0, 0x3f000, p, p + 0x1000, p + 0x100000};
		for (const auto& v: vmas) {
			for (const uint64_t x: {v.start, v.end, v.start + 0x1000, v.end - 0x1000 > v.end ? v.end : v.end - 0x1000, v.start - 1, v.end + 1}) points.push_back(x);
		}
		for (int k = 0; k < 120; k++) {
			uint64_t a = points[rnd(points.size())];
			uint64_t b = points[rnd(points.size())];
			if (k % 7 == 0) b = a;                    // an empty range
			if (k % 11 != 0 && b < a) std::swap(a, b); // mostly proper ranges, some reversed
			for (const bool ro: {false, true}) {
				const bool o = sf::inside_old(vmas, a, b, ro), f = sf::inside_fast(vmas, a, b, ro);
				q++;
				if (o != f) qd++;
				if (o) qtrue++;
			}
		}
	}
	check(qd == 0, "inside: the fast form answers as the old form in every query");
	check(qtrue > q / 50 && qtrue < q, "inside: the queries include ranges inside a VMA and ranges that are not");
	std::printf("inside: %llu queries, %llu differences, %llu true\n", static_cast<unsigned long long>(q), static_cast<unsigned long long>(qd), static_cast<unsigned long long>(qtrue));
	{
		std::vector<V> v = {{0x1000, 0x3000, false}, {0x3000, 0x3000, true}, {0x3000, 0x8000, false}};
		check(sf::vmas_ordered(v), "ordered: touching entries and an empty one are ordered");
		v[2].start = 0x2000;
		check(!sf::vmas_ordered(v), "ordered: an entry that starts inside the one before is not");
		v = {{0x5000, 0x6000, false}, {0x1000, 0x2000, false}};
		check(!sf::vmas_ordered(v), "ordered: a list out of order is not");
		v = {{0x5000, 0x4000, false}};
		check(!sf::vmas_ordered(v), "ordered: an entry that ends before it starts is not");
		check(sf::vmas_ordered(std::vector<V> {}), "ordered: the empty list is ordered");
		check(!sf::inside_fast(std::vector<V> {}, 1, 2, false) && !sf::inside_old(std::vector<V> {}, 1, 2, false), "inside: nothing is inside an empty list");
	}

	// ---- the name memo
	{
		int  asked    = 0;
		auto classify = [&asked](const char* n) {
			asked++;
			return n != nullptr && (std::strcmp(n, "AMM") == 0 || std::strcmp(n, "RenderAlloc") == 0);
		};
		sf::NameMemo memo;
		const char*  names[] = {"AMM", "Physics", "RenderAlloc", "", "AMM", "AMM", "Physics", "RenderAlloc", "x", ""};
		bool         same    = true;
		for (const char* n: names) same = same && memo.get(n, classify) == (std::strcmp(n, "AMM") == 0 || std::strcmp(n, "RenderAlloc") == 0);
		check(same, "memo: the answers of the function it remembers");
		check(asked == 5, "memo: the function is asked once per distinct name");
		const int before = asked;
		check(!memo.get(nullptr, classify) && asked == before + 1, "memo: a null name goes to the function each time");
		std::string a = "AMM"; // another pointer with the same text
		check(memo.get(a.c_str(), classify) && asked == before + 1, "memo: by the name's text, not by its address");
	}
	check(sf::mode_of(nullptr) == 0 && sf::mode_of("") == 0 && sf::mode_of("0") == 0 && sf::mode_of("1") == 1 && sf::mode_of("verify") == 2 && sf::mode_of("on") == 1,
	      "mode: unset, empty and 0 are off; verify is 2");
	std::printf("test0415sync: %d of %d; end\n", g_ok, g_run);
	return g_ok == g_run ? 0 : 1;
}
