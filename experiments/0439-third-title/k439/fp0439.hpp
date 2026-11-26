// SPDX-License-Identifier: GPL-2.0-only
// BC5 exp 0439 (tag fp439): the program address of every dispatch in a command buffer and its chained or called
// pieces, as the GPU will see it, for experiment 0190's flat-aperture rewrite (F249). The rewrite was only called
// from the top-level buffer scan, so a program bound and dispatched inside a chained or called piece, the third
// title's way (every program through LOAD_SH_REG_INDEX pair tables, exp 0441's decode of dcb #9544), was never
// rewritten: its BVH stack pushes address the console's apertures, the waves take a memory violation and are halted
// (exp 0439 run d2211: all 768 waves of 0x8000387500 with FATAL_HALT and TRAPSTS 0x40000100, s39 = 0x80000000, as in
// exp 0190). The fourth defect of the "chained frame treated as top level" class (F899, F901, F902).
//
// Packets (PM4 type 3; header bits 8-15 opcode, 16-29 count): SET_SH_REG 0x76 (dword 1 = register offset from the SH
// base, then values), LOAD_SH_REG 0x5f (dwords 1-2 the base address, then (register offset, count) pairs; the value
// of a register at base + 4 x offset, TODO(verify) the indexing), LOAD_SH_REG_INDEX 0x63 (pair form when dword 3 bit
// 31 is set: dwords 1-2 the table address, dword 4 bits 0-13 the pair count; pairs of (register offset, value)),
// DISPATCH_DIRECT 0x15, DISPATCH_INDIRECT 0x16 (either form). The same decode as the top-level scan in bc5LleAgc.cpp
// (experiments 0050, 0159). COMPUTE_PGM_LO 0x20c gives address bits 8-39, COMPUTE_PGM_HI 0x20d bits 40-47.
#pragma once
#include <cstdint>

namespace bc5::fp439 {

enum class Via : uint8_t { None, SetShReg, LoadShReg, LoadShRegIndex };
inline const char* via_name(Via v) {
	switch (v) {
	case Via::SetShReg: return "SET_SH_REG";
	case Via::LoadShReg: return "LOAD_SH_REG";
	case Via::LoadShRegIndex: return "LOAD_SH_REG_INDEX";
	default: return "nothing in this buffer";
	}
}

struct State {
	uint64_t pgm = 0;          // the program the next dispatch runs (0: not set in this buffer yet)
	Via      via = Via::None;  // how its low dword was last set
	bool     unreadable = false; // a table that could have set it was unreadable since
};
struct Stats {
	uint32_t dispatches = 0, no_pgm = 0, after_unreadable = 0;
};

inline void pgm_reg(State& st, uint32_t r, uint32_t v, Via via) {
	if (r == 0x20cu) st.pgm = (st.pgm & ~0xffffffff00ull) | (static_cast<uint64_t>(v) << 8u), st.via = via, st.unreadable = false;
	if (r == 0x20du) st.pgm = (st.pgm & 0xffffffff00ull) | (static_cast<uint64_t>(v & 0xffu) << 40u);
}

// Walks w[0..n). st carries the state in and out (pieces run in order). covered(a, bytes): is it readable. At each
// dispatch fix(pgm, via) is called with the program it runs (pgm 0 when none is known).
template <class Covered, class Fix>
void walk(const uint32_t* w, uint32_t n, State& st, Stats& ss, Covered covered, Fix fix) {
	for (uint32_t q = 0; q < n;) {
		const uint32_t h = w[q], ty = h >> 30u;
		uint32_t       len = 1;
		if (ty == 3 || ty == 0) {
			const uint32_t c = (h >> 16u) & 0x3fffu;
			len = c == 0x3fffu ? 1 : c + 2;
		}
		if (q + len > n) break;
		const uint32_t op = (h >> 8u) & 0xffu;
		if (ty == 3 && op == 0x76 && len >= 3)
			for (uint32_t j = 0; j + 2 < len; j++) pgm_reg(st, (w[q + 1] & 0xffffu) + j, w[q + 2 + j], Via::SetShReg);
		if (ty == 3 && op == 0x5f && len >= 5) {
			const uint64_t a = (w[q + 1] & ~3u) | (static_cast<uint64_t>(w[q + 2] & 0xffffu) << 32u);
			for (uint32_t j = 3; j + 1 < len; j += 2) {
				const uint32_t ro = w[q + j] & 0xffffu, cnt = w[q + j + 1] & 0x3fffu;
				if (ro + cnt <= 0x20cu || ro > 0x20du) continue; // the range does not touch PGM_LO/HI
				if (!covered(a + 4ull * ro, 4ull * cnt)) {
					st.unreadable = true;
					continue;
				}
				const auto* t = reinterpret_cast<const volatile uint32_t*>(a);
				for (uint32_t i = 0; i < cnt; i++) pgm_reg(st, ro + i, t[ro + i], Via::LoadShReg);
			}
		}
		if (ty == 3 && op == 0x63 && len >= 5 && (w[q + 3] >> 31u) != 0) {
			const uint64_t ta = (w[q + 1] & ~3u) | (static_cast<uint64_t>(w[q + 2] & 0xffffu) << 32u);
			const uint32_t tn = w[q + 4] & 0x3fffu;
			if (ta != 0 && tn != 0 && tn <= 4096 && covered(ta, static_cast<uint64_t>(tn) * 8)) {
				const auto* t = reinterpret_cast<const volatile uint32_t*>(ta);
				for (uint32_t k = 0; k < tn; k++) pgm_reg(st, t[2 * k] & 0xffffu, t[2 * k + 1], Via::LoadShRegIndex);
			} else if (tn != 0)
				st.unreadable = true;
		}
		if (ty == 3 && (op == 0x15 || op == 0x16)) {
			ss.dispatches++;
			if (st.pgm == 0) ss.no_pgm++;
			if (st.unreadable) ss.after_unreadable++;
			fix(st.pgm, st.via);
		}
		q += len;
	}
}

// exp 0439 (tag vl439): the flip-label waits of one piece: WAIT_REG_MEM 0x3c / WAIT_REG_MEM64 0x93 with MEM_SPACE
// (dword 1 bit 4) on an address in [l0, l0 + bytes); fn(packet, is64, label) for each.
template <class Fn>
void flip_label_waits(const uint32_t* w, uint32_t n, uint64_t l0, uint64_t bytes, Fn fn) {
	for (uint32_t q = 0; q < n;) {
		const uint32_t h = w[q], ty = h >> 30u;
		uint32_t       len = 1;
		if (ty == 3 || ty == 0) {
			const uint32_t c = (h >> 16u) & 0x3fffu;
			len = c == 0x3fffu ? 1 : c + 2;
		}
		if (q + len > n) break;
		const uint32_t op = (h >> 8u) & 0xffu;
		if (ty == 3 && (op == 0x3c || op == 0x93) && len >= 4 && ((w[q + 1] >> 4u) & 1u) != 0) {
			const uint64_t label = (w[q + 2] & ~3u) | (static_cast<uint64_t>(w[q + 3] & 0xffffu) << 32u);
			if (label >= l0 && label < l0 + bytes) fn(&w[q], op == 0x93, label);
		}
		q += len;
	}
}

// The program's identity for the rewrite cache: its first eight dwords (a program replaced at the same address
// changes them), cheap enough for every dispatch.
inline uint64_t ident(const volatile uint32_t* w) {
	uint64_t h = 1469598103934665603ull;
	for (int i = 0; i < 8; i++) h = (h ^ w[i]) * 1099511628211ull;
	return h;
}

} // namespace bc5::fp439
