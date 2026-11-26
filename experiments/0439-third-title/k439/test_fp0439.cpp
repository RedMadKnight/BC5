// SPDX-License-Identifier: GPL-2.0-only
// BC5 exp 0439 (tag fp439): det test of fp0439.hpp with fa0439.hpp's rewrite (patch 0001's flat_aperture_fix scan).
// A synthetic program with the console-aperture push idiom (three pushes behind one s_brev_b32, the shape of
// 0x8000387500 in exp 0441's listing) is bound through a LOAD_SH_REG_INDEX pair table inside a chained piece and
// dispatched; the next piece dispatches it again, rebinds through SET_SH_REG and through LOAD_SH_REG, meets an
// unreadable table and dispatches again. The walk must name the program of every dispatch with how it was bound,
// carry the state from piece to piece, count the dispatch after the unreadable table, and the rewrite must turn
// all three pushes to the host's apertures. The identity changes when a program is replaced at the same address.
// Plants (BC5_FP439_PLANT): NOTABLE (tables never readable), NOCARRY (state reset between pieces), TOPONLY (only the
// top-level piece walked, the old reach) must FAIL.
// Build: clang++ -std=c++20 -I. -Ik439inc test_fp0439.cpp   (fa0439.hpp included as bc5/fa0439.hpp)
#include "fp0439.hpp"
#include "bc5/fa0439.hpp"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

static uint32_t t3(uint32_t op, uint32_t count) { return 0xC0000000u | (count << 16u) | (op << 8u); }
static int      g_fail = 0;
#define CHECK(x) do { if (!(x)) { std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #x); g_fail++; } } while (0)

int main() {
	const char* pl = std::getenv("BC5_FP439_PLANT");
	auto        is = [pl](const char* n) { return pl != nullptr && std::strcmp(pl, n) == 0; };
	// the program: s_brev_b32 s39, 1; three v_med3_u32 vD, s39, 0x70000000, v28; s_endpgm (256-byte aligned)
	alignas(256) static uint32_t prog[64] = {};
	uint32_t                     n        = 0;
	prog[n++] = 0xBF800000u;
	prog[n++] = 0xBE800B81u | (39u << 16u);
	for (uint32_t d : {5u, 4u, 3u}) prog[n++] = 0xD5590000u | d, prog[n++] = 39u | (0xffu << 9u) | ((256u + 28u) << 18u), prog[n++] = 0x70000000u;
	prog[n++]           = 0xBF810000u;
	const uint64_t pa   = reinterpret_cast<uint64_t>(prog);
	const uint64_t id0  = bc5::fp439::ident(prog);
	// its 12-pair table, in the shape of run d2211's p65:251
	alignas(8) static uint32_t table[24] = {0x20c, static_cast<uint32_t>(pa >> 8u), 0x20d, static_cast<uint32_t>(pa >> 40u), 0x22a, 0x28001120, 0x22a, 0x259bf67f,
	                                        0x212, 0x402c0307, 0x213, 0x00020089, 0x228, 0, 0x207, 0x20, 0x208, 1, 0x209, 1, 0x218, 0xc500, 0x225, 0};
	// a LOAD_SH_REG area: register offset 0x20c at base + 4 x 0x20c
	alignas(8) static uint32_t area[0x210] = {};
	area[0x20c] = 0x80003b16, area[0x20d] = 0;
	const uint64_t ta = reinterpret_cast<uint64_t>(table), aa = reinterpret_cast<uint64_t>(area);
	std::vector<uint32_t> top = {t3(0x76, 2), 0x240, 1, 2};                                                     // the top level: no dispatch
	std::vector<uint32_t> p1  = {t3(0x76, 4), 0x240, 0x13526130, 0x20, 0x10000, 0x20,                           // UD0-3
	                             t3(0x63, 3), static_cast<uint32_t>(ta), static_cast<uint32_t>(ta >> 32u), 0x80000000u, 12, // pair table
	                             t3(0x16, 1), 0, 0x8041};                                                       // DISPATCH_INDIRECT
	std::vector<uint32_t> p2  = {t3(0x16, 1), 0, 0x8041,                                                        // bound in the piece before
	                             t3(0x76, 2), 0x20c, 0x80001274, 0,                                             // SET_SH_REG PGM_LO/HI
	                             t3(0x15, 3), 1, 1, 1, 0x8041,                                                  // DISPATCH_DIRECT
	                             t3(0x5f, 3), static_cast<uint32_t>(aa), static_cast<uint32_t>(aa >> 32u), 0x20c, 2, // LOAD_SH_REG
	                             t3(0x15, 3), 1, 1, 1, 0x8041,
	                             t3(0x63, 3), 0x1000, 0, 0x80000000u, 12,                                       // an unreadable table
	                             t3(0x15, 3), 1, 1, 1, 0x8041};
	auto covered = [&](uint64_t a, uint64_t b) {
		if (is("NOTABLE")) return false;
		return (a >= ta && a + b <= ta + sizeof(table)) || (a >= aa && a + b <= aa + sizeof(area));
	};
	struct Hit {
		uint64_t           pgm;
		bc5::fp439::Via    via;
	};
	std::vector<Hit>   seen;
	bc5::fa439::Result rw;
	auto fix = [&](uint64_t p, bc5::fp439::Via v) {
		seen.push_back({p, v});
		if (p == pa) {
			const auto r = bc5::fa439::rewrite(prog, n);
			rw.sites += r.sites, rw.brevs += r.brevs;
		}
	};
	bc5::fp439::State st;
	bc5::fp439::Stats ss;
	bc5::fp439::walk(top.data(), static_cast<uint32_t>(top.size()), st, ss, covered, fix);
	if (!is("TOPONLY")) {
		bc5::fp439::walk(p1.data(), static_cast<uint32_t>(p1.size()), st, ss, covered, fix);
		if (is("NOCARRY")) st = {};
		bc5::fp439::walk(p2.data(), static_cast<uint32_t>(p2.size()), st, ss, covered, fix);
	}
	using V = bc5::fp439::Via;
	const std::vector<Hit> want = {{pa, V::LoadShRegIndex}, {pa, V::LoadShRegIndex}, {0x8000127400ull, V::SetShReg}, {0x80003b1600ull, V::LoadShReg}, {0x80003b1600ull, V::LoadShReg}};
	for (size_t i = 0; i < seen.size(); i++) std::printf("dispatch %zu: program 0x%llx via %s\n", i, static_cast<unsigned long long>(seen[i].pgm), bc5::fp439::via_name(seen[i].via));
	CHECK(seen.size() == want.size());
	for (size_t i = 0; i < seen.size() && i < want.size(); i++) CHECK(seen[i].pgm == want[i].pgm && seen[i].via == want[i].via);
	CHECK(ss.dispatches == 5 && ss.no_pgm == 0 && ss.after_unreadable == 1);
	CHECK(rw.sites == 3 && rw.brevs == 1); // the first dispatch rewrites, the second finds nothing left
	CHECK(prog[1] == (0xBE800B84u | (39u << 16u)) && prog[4] == 0x10000000u && prog[7] == 0x10000000u && prog[10] == 0x10000000u);
	CHECK(bc5::fp439::ident(prog) != id0 || prog[4] == 0x70000000u); // the first eight dwords include a rewritten one
	uint32_t other[64] = {};
	other[0] = 0xBF810000u;
	CHECK(bc5::fp439::ident(other) != bc5::fp439::ident(prog)); // a program replaced at the same address
	std::printf("rewrite: %u pushes, %u s_brev_b32\n%s (%d failures)%s%s\n", rw.sites, rw.brevs, g_fail == 0 ? "PASS" : "FAIL", g_fail, pl ? ", plant " : "", pl ? pl : "");
	return g_fail == 0 ? 0 : 1;
}
