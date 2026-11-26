// BC5 experiment 0419: CPU test of ajm_trail.hpp (the ring, the id rule, the deferred jobs). No GPU, no emulator.
// build: clang++ -std=c++20 -Wall -Wextra -Werror -I. test0419ajm.cpp -o t && ./t
#include "ajm_trail.hpp"

#include <cstdio>
#include <set>
#include <string>

using namespace bc5::ajm_trail;

static int g_bad = 0;
#define CHECK(c)                                                                                                       \
	do {                                                                                                               \
		if (!(c)) {                                                                                                    \
			std::printf("FAIL line %d: %s\n", __LINE__, #c);                                                           \
			g_bad++;                                                                                                   \
		}                                                                                                              \
	} while (0)

int main() {
	// the ring: 300 records, the last 256 stay, in order
	static Trail t;
	for (uint32_t i = 0; i < 300; i++) {
		Rec r;
		r.kind     = "decode";
		r.instance = i;
		r.out      = 0x1000000ull + 0x10000ull * i;
		r.out_size = 0x2000;
		r.in       = 0x9000000ull + 0x10000ull * i;
		r.in_size  = 0x100;
		t.add(r);
	}
	CHECK(t.end() == 300 && t.first() == 44);
	CHECK(t.at(44).instance == 44 && t.at(299).instance == 299 && t.at(299).seq == 299);
	Rec      r;
	bool     is_out = false;
	uint64_t off    = 0;
	CHECK(t.where(0x1000000ull + 0x10000ull * 100 + 0x1800, &r, &is_out, &off) && r.instance == 100 && is_out && off == 0x1800);
	CHECK(t.where(0x9000000ull + 0x10000ull * 299 + 0xff, &r, &is_out, &off) && r.instance == 299 && !is_out && off == 0xff);
	CHECK(!t.where(0x1000000ull + 0x10000ull * 100 + 0x2000, &r, &is_out, &off)); // one past the end
	CHECK(!t.where(0x1000000ull + 0x10000ull * 10, &r, &is_out, &off));           // fell out of the ring
	CHECK(!t.where(0x2000, &r, &is_out, &off));                                    // the fault's value: in no buffer
	// the newest of two records over the same buffer wins
	Rec again;
	again.instance = 7777;
	again.out      = 0x1000000ull + 0x10000ull * 100;
	again.out_size = 0x2000;
	t.add(again);
	CHECK(t.where(0x1000000ull + 0x10000ull * 100, &r, &is_out, &off) && r.instance == 7777);

	// the id rule
	{
		std::atomic_uint32_t c {1};
		std::set<uint32_t>   live;
		uint32_t             skipped = 0;
		const auto           is_live = [&](uint32_t id) { return live.count(id) != 0; };
		const uint32_t       first   = next_id(c, 1, false, is_live, &skipped);
		CHECK(first == ((1u << 14) | 1u) && skipped == 0);
		live.insert(first);
		for (uint32_t i = 0; i < kSlots - 1; i++) {
			(void)next_id(c, 1, false, is_live, &skipped); // never destroyed here, never made live: 16,383 short voices
			CHECK(skipped == 0);
		}
		// today's rule: the counter has wrapped and the long-lived first voice's id is given out again
		const uint32_t dup = next_id(c, 1, false, is_live, &skipped);
		CHECK(dup == first && skipped == 1);
	}
	{
		std::atomic_uint32_t c {1};
		std::set<uint32_t>   live;
		uint32_t             skipped = 0;
		const auto           is_live = [&](uint32_t id) { return live.count(id) != 0; };
		const uint32_t       first   = next_id(c, 1, true, is_live, &skipped);
		live.insert(first);
		for (uint32_t i = 0; i < kSlots - 1; i++) {
			(void)next_id(c, 1, true, is_live, &skipped);
		}
		// with the fix: the live id is passed over
		const uint32_t fresh = next_id(c, 1, true, is_live, &skipped);
		CHECK(fresh != first && fresh == ((1u << 14) | 2u) && skipped == 1);
		// another codec's ids do not collide with it
		CHECK(next_id(c, 2, true, is_live, &skipped) == ((2u << 14) | 3u) && skipped == 0);
		// all alive: an id is still returned, after 16,384 tries
		const auto all = [](uint32_t) { return true; };
		(void)next_id(c, 1, true, all, &skipped);
		CHECK(skipped == kSlots);
	}

	// the deferred jobs
	{
		Pending     p;
		std::string order;
		int         a = 0, b = 0;
		CHECK(p.run(&a) == 0);
		p.push(&a, [&] { order += "1"; });
		p.push(&b, [&] { order += "x"; });
		p.push(&a, [&] { order += "2"; });
		CHECK(order.empty()); // nothing ran when added
		CHECK(p.run(&a) == 2 && order == "12");
		CHECK(p.run(&a) == 0 && order == "12"); // a batch runs once
		CHECK(p.reset(&b) == 1);                // re-initialised without a start: dropped, counted
		CHECK(p.run(&b) == 0 && order == "12");
		// a job may add to another buffer while running
		p.push(&a, [&] { p.push(&b, [&] { order += "y"; }); });
		CHECK(p.run(&a) == 1 && p.run(&b) == 1 && order == "12y");
	}

	std::printf(g_bad == 0 ? "test0419ajm: all ok\n" : "test0419ajm: %d FAILED\n", g_bad);
	return g_bad == 0 ? 0 : 1;
}
