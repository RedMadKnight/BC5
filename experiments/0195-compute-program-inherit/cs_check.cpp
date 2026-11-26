// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0195: offline check of the host's cs_inherit_at() and cs_prefix() (bc5LleAgc.cpp, extracted verbatim
// into cs_funcs.inc) on captured buffers, with the backend's own bc5::full_state tracker. No GPU access.
//   cs_check <one-off dcb dump> <dump whose first <prefix> dwords are a host full-state prefix> <prefix dwords>
// 1. cs_inherit_at() on the one-off buffer: the first dispatch that comes before a program write.
// 2. The tracker after the full-state prefix (the graphics queue's state as the host tracked it); cs_prefix() of it;
//    a fresh tracker that applies only that compute prefix must hold the same SH 0x204-0x3ff registers.
#include "bc5/full_state.hpp"

#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <vector>

namespace bc5::direct {
struct Mapping {}; // stands in for the host's mapping list: nothing is mapped offline
} // namespace bc5::direct
static bool covered_sorted(const std::vector<bc5::direct::Mapping>&, uint64_t, uint64_t) { return false; }

#include "cs_funcs.inc"

static std::vector<uint32_t> load(const char* path) {
	std::vector<uint32_t> v;
	if (FILE* f = std::fopen(path, "rb")) {
		uint32_t w;
		while (std::fread(&w, 4, 1, f) == 1) v.push_back(w);
		std::fclose(f);
	}
	return v;
}

int main(int argc, char** argv) {
	if (argc != 4) return 2;
	const std::vector<bc5::direct::Mapping> none;
	const auto one = load(argv[1]);
	const int  at  = cs_inherit_at(one.data(), static_cast<uint32_t>(one.size()), none);
	std::printf("one-off %zu dwords: cs_inherit_at = %d\n", one.size(), at);
	const auto     dump = load(argv[2]);
	const uint32_t pre  = static_cast<uint32_t>(std::strtoul(argv[3], nullptr, 0));
	std::printf("prefixed dump %zu dwords: cs_inherit_at = %d (expect -1: its prefix writes COMPUTE_PGM_LO)\n", dump.size(),
	            cs_inherit_at(dump.data(), static_cast<uint32_t>(dump.size()), none));
	bc5::full_state::Tracker t;
	bc5::full_state::Stats   st;
	t.apply(std::span<const uint32_t>(dump.data(), pre), nullptr, st);
	uint64_t   pgm = 0;
	const auto cs  = cs_prefix(t, &pgm);
	std::printf("tracked program 0x%010" PRIx64 "; compute prefix %zu dwords:", pgm, cs.size());
	for (size_t i = 0; i < cs.size();) {
		const uint32_t n = ((cs[i] >> 16u) & 0x3fffu) + 2;
		std::printf(" [SET_SH_REG 0x%x x%u]", cs[i + 1], n - 2);
		i += n;
	}
	std::printf("\n");
	bc5::full_state::Tracker u;
	u.apply(std::span<const uint32_t>(cs.data(), cs.size()), nullptr, st);
	int same = 0, differ = 0;
	for (uint32_t o = 0; o < 0x400u; o++) {
		uint32_t a = 0, b = 0;
		const bool ha = t.get(bc5::full_state::Sh, o, a), hb = u.get(bc5::full_state::Sh, o, b);
		if (o < 0x204u) {
			if (hb) differ++; // the compute prefix must not write graphics SH registers
			continue;
		}
		if (ha != hb || a != b) differ++;
		else if (ha) same++;
	}
	std::printf("compute registers reproduced: %d, differences: %d\n", same, differ);
	return differ == 0 && at >= 0 ? 0 : 1;
}
