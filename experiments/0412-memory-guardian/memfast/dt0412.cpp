// BC5 experiment 0412: CPU test of dt0412.inc (tag dt412): the buffers a command buffer's user data names.
//   - pair(): the descriptor read from arm n8F8's buffer (a5ae8000 03000011 00000800) gives base 0x11a5ae8000 and
//     0x180000 bytes; a plain pointer gives its address and no length; no base byte, nothing; stride 0 counts
//     bytes; the cap; no third dword, no length;
//   - user_reg(): the seven ranges and their edges;
//   - generated buffers (3,000): SET_SH_REG, SET_SH_REG_INDEX and loaded tables over user-data and other
//     registers, with fillers; every pair of neighbouring user-data registers is reported once, in order, with the
//     address and length a reference written apart from the walk computes, and nothing else;
//   - a pair split over two packets is not reported; a table that cannot be read reports nothing; a packet
//     running past the end stops the walk;
//   - block() reports by position; Recent answers fresh only within its time; the switch is off when unset.
// build: g++ -std=c++20 -O1 -Wall -Wextra -Werror dt0412.cpp -o dt0412
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>
#include <map>
#include <random>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>

#include "dt0412.inc"

static uint64_t g_checks = 0, g_ok = 0;
static void     check(bool c, const char* what) {
	g_checks++;
	if (c) g_ok++;
	else if (g_checks - g_ok < 20) std::printf("FAIL: %s\n", what);
}
static uint32_t pkt3(uint32_t op, uint32_t body) { return 0xc0000000u | ((body - 1) << 16u) | (op << 8u); }

struct Hit {
	uint32_t reg;
	uint64_t a, bytes;
	bool     plain;
	bool     operator==(const Hit& o) const { return reg == o.reg && a == o.a && bytes == o.bytes && plain == o.plain; }
};
// The reference: user-data ranges as a table, the pair rule spelled out.
static bool ref_user(uint32_t r) {
	static const uint32_t lo[7] = {0x0c, 0x4c, 0x8c, 0xcc, 0x10c, 0x14c, 0x240}, cnt[7] = {32, 32, 32, 32, 32, 32, 16};
	for (int i = 0; i < 7; i++) {
		if (r >= lo[i] && r - lo[i] < cnt[i]) return true;
	}
	return false;
}
static void ref_packet(const std::vector<std::pair<uint32_t, uint32_t>>& rv, std::vector<Hit>& out) {
	for (size_t k = 0; k + 1 < rv.size(); k++) {
		const uint32_t r = rv[k].first;
		if (!ref_user(r) || !ref_user(r + 1) || rv[k + 1].first != r + 1) continue;
		const uint32_t w0 = rv[k].second, w1 = rv[k + 1].second;
		if ((w1 & 0xff) == 0) continue;
		Hit h {r, w0 + (static_cast<uint64_t>(w1 & 0xff) << 32), 0, (w1 & 0xffffff00u) == 0};
		if (!h.plain && k + 2 < rv.size() && rv[k + 2].first == r + 2 && ref_user(r + 2)) {
			const uint64_t stride = (w1 >> 16) & 0x3fff, rec = rv[k + 2].second;
			h.bytes = stride ? stride * rec : rec;
			if (h.bytes > (256ull << 20)) h.bytes = 256ull << 20;
		}
		out.push_back(h);
	}
}

int main() {
	// pair()
	{
		std::vector<std::tuple<uint64_t, uint64_t, bool>> got;
		auto f = [&](uint64_t a, uint64_t b, bool p) { got.emplace_back(a, b, p); };
		dt412::pair(0xa5ae8000u, 0x03000011u, true, 0x800u, f);
		check(got.size() == 1 && got[0] == std::make_tuple(0x11a5ae8000ull, 0x180000ull, false), "the descriptor of n8F8");
		got.clear();
		dt412::pair(0xe0d2c810u, 0x11u, true, 0x12345u, f);
		check(got.size() == 1 && got[0] == std::make_tuple(0x11e0d2c810ull, 0ull, true), "a plain pointer");
		got.clear();
		dt412::pair(0xe0d2c810u, 0x03000000u, true, 5u, f);
		check(got.empty(), "no base byte, nothing");
		dt412::pair(0x1000u, 0x00000112u, true, 4096u, f);
		check(got.size() == 1 && got[0] == std::make_tuple(0x1200001000ull, 4096ull, false), "stride 0 counts bytes");
		got.clear();
		dt412::pair(0x1000u, 0x3fff0012u, true, 0xffffffffu, f);
		check(got.size() == 1 && std::get<1>(got[0]) == dt412::kMaxSpan, "the cap");
		got.clear();
		dt412::pair(0x1000u, 0x00100012u, false, 77u, f);
		check(got.size() == 1 && got[0] == std::make_tuple(0x1200001000ull, 0ull, false), "no third dword, no length");
	}
	// user_reg()
	for (uint32_t r = 0; r < 0x400; r++) check(dt412::user_reg(r) == ref_user(r), "user_reg against the table");
	check(!dt412::user_reg(0x0b) && dt412::user_reg(0x0c) && dt412::user_reg(0x2b) && !dt412::user_reg(0x2c), "PS edges");
	check(!dt412::user_reg(0x23f) && dt412::user_reg(0x240) && dt412::user_reg(0x24f) && !dt412::user_reg(0x250), "compute edges");

	std::mt19937_64 rng(0x6474343132);
	static const uint32_t bases[8] = {0x0c, 0x4c, 0x8c, 0xcc, 0x10c, 0x14c, 0x240, 0x200};
	for (int it = 0; it < 3000; it++) {
		std::vector<uint32_t>                     ib;
		std::map<uint64_t, std::vector<uint32_t>> mem;
		std::vector<Hit>                          want, got;
		uint64_t                                  table_no = 0;
		auto value = [&]() -> uint32_t {
			switch (rng() % 6) {
			case 0: return 0x11u;                                         // a plain pointer's high dword
			case 1: return 0x03000011u;                                   // a descriptor's
			case 2: return static_cast<uint32_t>(rng()) & 0xffffff00u;    // no base byte
			case 3: return static_cast<uint32_t>(rng() % 0x100000);       // a small count
			default: return static_cast<uint32_t>(rng());
			}
		};
		const int packets = 1 + static_cast<int>(rng() % 40);
		for (int p = 0; p < packets; p++) {
			const uint32_t kind = static_cast<uint32_t>(rng() % 10);
			if (kind < 5) { // SET_SH_REG or SET_SH_REG_INDEX
				const uint32_t base = bases[rng() % 8];
				const uint32_t reg  = base + static_cast<uint32_t>(rng() % 36) - 2; // may start below and run past a range
				const uint32_t cnt  = 1 + static_cast<uint32_t>(rng() % 12);
				ib.push_back(pkt3(kind == 4 ? 0x9b : 0x76, cnt + 1));
				ib.push_back(reg | (kind == 4 ? 0x30000000u : 0u)); // the index bits above bit 15 are not a register
				std::vector<std::pair<uint32_t, uint32_t>> rv;
				for (uint32_t k = 0; k < cnt; k++) {
					const uint32_t v = value();
					ib.push_back(v);
					rv.emplace_back(reg + k, v);
				}
				ref_packet(rv, want);
			} else if (kind < 7) { // a loaded table
				const uint64_t ta       = 0x1100000000ull + (table_no++ << 16u);
				const uint32_t pairs    = 1 + static_cast<uint32_t>(rng() % 10);
				const bool     readable = rng() % 5 != 0, direct = rng() % 6 != 0;
				std::vector<uint32_t>                      t;
				std::vector<std::pair<uint32_t, uint32_t>> rv;
				uint32_t reg = bases[rng() % 8] + static_cast<uint32_t>(rng() % 8);
				for (uint32_t k = 0; k < pairs; k++) {
					const uint32_t v = value();
					t.push_back(reg | 0x80000000u * static_cast<uint32_t>(rng() % 2)); // upper bits are not the register
					t.back() = (t.back() & 0xffff0000u & 0x7fff0000u) | reg;
					t.push_back(v);
					rv.emplace_back(reg, v);
					reg += rng() % 4 == 0 ? 2 : 1; // sometimes a gap
				}
				if (readable) mem[ta] = t;
				ib.push_back(pkt3(0x63, 4));
				ib.push_back(static_cast<uint32_t>(ta));
				ib.push_back(static_cast<uint32_t>(ta >> 32u));
				ib.push_back(direct ? 0x80000000u : 0u);
				ib.push_back(pairs);
				if (readable && direct) ref_packet(rv, want);
			} else if (kind == 7) {
				ib.push_back(0xffff1000u); // a one-dword NOP
			} else if (kind == 8) {
				ib.push_back(0x80000000u); // a type-2 filler
			} else { // another packet whose body looks like user data
				ib.push_back(pkt3(0x69, 3));
				ib.push_back(0x240u);
				ib.push_back(0xa5ae8000u);
				ib.push_back(0x03000011u);
			}
		}
		const bool whole = dt412::walk(
		    ib.data(), static_cast<uint32_t>(ib.size()),
		    [&](uint64_t a, uint32_t pairs, std::vector<uint32_t>& out) {
			    auto f = mem.find(a);
			    if (f == mem.end() || f->second.size() < 2ull * pairs) return false;
			    out = f->second;
			    return true;
		    },
		    [&](uint32_t reg, uint64_t a, uint64_t bytes, bool plain) { got.push_back(Hit {reg, a, bytes, plain}); });
		check(whole, "a generated buffer is walked whole");
		check(got == want, "the walk reports what the reference computes, in order");
	}
	// a pair split over two packets is not one
	{
		const uint32_t ib[] = {pkt3(0x76, 2), 0x240u, 0xa5ae8000u, pkt3(0x76, 2), 0x241u, 0x00000011u};
		int            n    = 0;
		check(dt412::walk(ib, 6, [](uint64_t, uint32_t, std::vector<uint32_t>&) { return false; }, [&](uint32_t, uint64_t, uint64_t, bool) { n++; }), "split: whole");
		check(n == 0, "a pair split over two packets is not reported");
	}
	// a packet running past the end
	{
		const uint32_t ib[] = {pkt3(0x76, 3), 0x240u, 0xa5ae8000u, 0x00000011u, pkt3(0x76, 9), 0x240u, 1u};
		int            n    = 0;
		check(!dt412::walk(ib, 7, [](uint64_t, uint32_t, std::vector<uint32_t>&) { return false; }, [&](uint32_t, uint64_t, uint64_t, bool) { n++; }), "past the end: false");
		check(n == 1, "what came before the bad packet was reported");
	}
	// block()
	{
		const uint32_t w[] = {0u, 0u, 0xa5ae8000u, 0x03000011u, 0x800u, 0x5204u, 0xe0d2c810u, 0x11u};
		std::vector<std::tuple<uint32_t, uint64_t, uint64_t, bool>> got;
		dt412::block(w, 8, [&](uint32_t k, uint64_t a, uint64_t b, bool p) { got.emplace_back(k, a, b, p); });
		bool d = false, p = false;
		for (const auto& g: got) {
			d = d || g == std::make_tuple(2u, 0x11a5ae8000ull, 0x180000ull, false);
			p = p || g == std::make_tuple(6u, 0x11e0d2c810ull, 0ull, true);
		}
		check(d && p, "block: the descriptor at 2 and the pointer at 6");
		for (const auto& g: got) check(std::get<0>(g) + 1 < 8, "block: positions inside");
	}
	// Recent
	{
		dt412::Recent r;
		check(!r.fresh(0x1000, 64, 10.0), "first time: not fresh");
		check(r.fresh(0x1000, 64, 10.5), "within a second: fresh");
		check(!r.fresh(0x1000, 128, 10.5), "another length: not fresh");
		check(!r.fresh(0x1000, 64, 11.2), "after a second: not fresh");
		check(r.fresh(0x1000, 64, 11.3), "and fresh again");
		check(!r.fresh(0x1000, 64, 5.0), "a clock that went back: not fresh");
	}
	check(dt412::mode() == 0, "off when unset");
	std::printf("dt0412: %" PRIu64 " of %" PRIu64 "\n", g_ok, g_checks);
	return g_ok == g_checks ? 0 : 1;
}
