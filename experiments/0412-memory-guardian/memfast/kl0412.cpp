// BC5 experiment 0412: CPU test of kl0412.inc (tag kl412): under a lazy view K1r covers only never-written chunks.
// A model: one lazy view over a file, its uncovered pieces cut at chunk boundaries (as k1r412::cover cuts them), a
// set of chunks that hold data, changing over time.
//   - at a scan: exactly the pieces whose chunk holds no data are kept, in order; each chunk is asked at most once
//     per piece and never when already known;
//   - between scans nothing is asked and the last answer stands;
//   - data that appears is seen at the next scan (the piece loses its cover); data that vanishes too (cover back);
//   - the period: no scan before it has passed, one at the first call;
//   - the case of 15:32: orbis_user_malloc's chunk at file offset 0x8200000, written at 0.5 s: no cover.
// build: g++ -std=c++20 -O1 -Wall -Wextra -Werror kl0412.cpp -o kl0412
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <random>
#include <set>
#include <vector>

#include "kl0412.inc"

static uint64_t g_checks = 0, g_ok = 0;
static void     check(bool c, const char* what) {
	g_checks++;
	if (c) g_ok++;
	else if (g_checks - g_ok < 20) std::printf("FAIL: %s\n", what);
}

struct P {
	uint64_t va, size;
	bool     operator==(const P& o) const { return va == o.va && size == o.size; }
};

int main() {
	constexpr uint64_t C = 0x200000, PG = 0x1000;
	std::mt19937_64    rng(0x6b6c343132);
	for (int it = 0; it < 3000; it++) {
		const uint64_t voff = (rng() % 64) * C + (rng() % 4) * PG * 16, vva = 0x300000000ull + (rng() % 512) * PG;
		const uint64_t chunks = 4 + rng() % 40;
		std::vector<P> all;
		for (uint64_t lo = voff, end = voff + chunks * C - (rng() % 8) * PG; lo < end;) { // pieces: some chunks skipped (imported), the rest cut at chunk ends
			const uint64_t stop = (lo / C + 1) * C, e = stop < end ? stop : end;
			if (rng() % 4 != 0) all.push_back({vva + (lo - voff), e - lo});
			lo = e;
		}
		std::set<uint64_t> data;
		kl412::Known       k;
		uint64_t           now = 1000;
		for (int step = 0; step < 6; step++) {
			for (uint64_t c = voff / C; c <= (voff + chunks * C) / C; c++) {
				if (rng() % 5 == 0) data.insert(c * C);
				if (rng() % 11 == 0) data.erase(c * C);
			}
			const std::set<uint64_t> before = k.written;
			const bool               scan   = k.begin(now, 100);
			check(scan == (step == 0 || step % 2 == 0), "a scan at the first call and when the period has passed, none before");
			std::vector<P> p     = all;
			uint64_t       calls = 0;
			const uint64_t d     = kl412::drop_written(p, vva, voff, C, k, scan, [&](uint64_t c) {
                calls++;
                return data.count(c) != 0;
            });
			const std::set<uint64_t>& truth = scan ? data : before;
			std::vector<P>            want;
			for (const auto& x: all) {
				if (truth.count(((voff + (x.va - vva)) / C) * C) == 0) want.push_back(x);
			}
			check(p == want, "kept: exactly the pieces whose chunk held no data at the last scan, in order");
			check(d == all.size() - want.size(), "the count removed");
			check(scan || calls == 0, "between scans the file is not asked");
			check(calls <= all.size(), "at most one question per piece");
			if (!scan) check(k.written == before, "between scans the answer stands");
			now += step % 2 == 0 ? 40 : 70; // 40 then 70: the period of 100 passes every second step
		}
	}
	{ // 2026-11-13 15:32: orbis_user_malloc at 0x3018c0000, the page 0x3082f6000 is 0x6a36000 into it, file chunk 0x8200000
		const uint64_t vva = 0x3018c0000ull, voff = 0x8200000ull - (0x6a36000ull & ~(C - 1));
		std::vector<P> p = {{vva + 0x6800000ull, C}, {vva + 0x6a00000ull, C}, {vva + 0x6c00000ull, C}};
		kl412::Known   k;
		check(k.begin(5, 100), "the first scan");
		const uint64_t d = kl412::drop_written(p, vva, voff, C, k, true, [](uint64_t c) { return c == 0x8200000ull; });
		check(d == 1 && p.size() == 2 && p[0].va == vva + 0x6800000ull && p[1].va == vva + 0x6c00000ull, "the written chunk of 15:32 gets no cover; its never-written neighbours keep theirs");
	}
	check(kl412::kPeriodNs == 100'000'000ull, "the period is 100 ms (no switch)");
	std::printf("kl0412: %" PRIu64 " of %" PRIu64 "; end\n", g_ok, g_checks);
	return g_ok == g_checks ? 0 : 1;
}
