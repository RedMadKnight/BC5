// BC5 experiment 0412: CPU test of firstfail0412.inc (tag ff412): which failures are written in full, and the ring of
// the last failures against a plain model.
// build: g++ -std=c++20 -O1 -Wall -Wextra -Werror firstfail0412.cpp -o firstfail0412
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <deque>
#include <random>
#include <type_traits>

#include "firstfail0412.inc"

static uint64_t g_checks = 0, g_ok = 0;
static void check(bool c, const char* what) {
	g_checks++;
	if (c) g_ok++;
	else if (g_checks - g_ok < 20) std::printf("FAIL: %s\n", what);
}

int main() {
	// full(): the first kFull, then the powers of two
	check(!ff412::full(0), "full: there is no failure 0");
	uint64_t printed = 0;
	for (uint64_t n = 1; n <= 100000; n++) {
		const bool pow2 = (n & (n - 1)) == 0;
		check(ff412::full(n) == (n <= ff412::kFull || pow2), "full: the first twelve and every power of two");
		printed += ff412::full(n) ? 1u : 0u;
	}
	check(printed == ff412::kFull + 13, "full: 100,000 failures print 25 lines (12, then 16 ... 65536)");
	// the ring against a deque
	std::mt19937_64 rng(0x0412ff);
	for (int it = 0; it < 500; it++) {
		ff412::Ring       r;
		std::deque<uint64_t> model;
		const int         pushes = static_cast<int>(rng() % 40);
		for (int i = 0; i < pushes; i++) {
			ff412::Fail f;
			f.n      = static_cast<uint64_t>(i) + 1;
			f.result = static_cast<int>(rng() & 0xffff);
			f.args   = static_cast<unsigned>(rng() % 7);
			r.push(f);
			model.push_back(f.n);
			if (model.size() > ff412::kRing) model.pop_front();
		}
		const ff412::Fail* kept[ff412::kRing];
		const unsigned     n = r.list(kept);
		check(n == model.size(), "ring: as many kept as the model holds");
		bool same = true;
		for (unsigned i = 0; i < n && i < model.size(); i++) {
			if (kept[i]->n != model[i]) same = false;
		}
		check(same, "ring: the last failures, oldest first");
		check(r.count == static_cast<uint64_t>(pushes), "ring: the count is every failure, kept or not");
	}
	// u(): pointers and integers
	int x = 0;
	check(ff412::u(&x) == reinterpret_cast<uint64_t>(&x), "u: a pointer is its address");
	check(ff412::u(static_cast<int>(-1)) == 0xffffffffffffffffull, "u: a negative int is sign-extended");
	check(ff412::u(static_cast<size_t>(0x4000)) == 0x4000, "u: a size is itself");
	check(ff412::u(static_cast<int64_t>(0x123456789all)) == 0x123456789aull, "u: a 64-bit offset is itself");
	std::printf("firstfail0412: %" PRIu64 " of %" PRIu64 "; end\n", g_ok, g_checks);
	return g_ok == g_checks ? 0 : 1;
}
