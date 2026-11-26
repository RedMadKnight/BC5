// SPDX-License-Identifier: GPL-2.0-only
// BC5 exp 0439 (tag vl439): det test of fp0439.hpp flip_label_waits, the recognition behind candidate (b): a chained
// piece in the shape of the third title's last piece (WAIT_REG_MEM64 on the flip label at dword 32, RELEASE_MEM to it at
// dword 333; here shortened) plus a plain WAIT_REG_MEM on another label and a register poll on the label's value. Only
// the memory waits on the labels' range count. Plants (BC5_VL439_PLANT): RANGE (the range one label too short) and
// SPACE (the MEM_SPACE bit ignored) must FAIL.
// Build: clang++ -std=c++20 -I. test_vl0439.cpp
#include "fp0439.hpp"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

static uint32_t t3(uint32_t op, uint32_t count) { return 0xC0000000u | (count << 16u) | (op << 8u); }

int main() {
	const char* pl = std::getenv("BC5_VL439_PLANT");
	auto        is = [pl](const char* n) { return pl != nullptr && std::strcmp(pl, n) == 0; };
	const uint64_t l0 = 0x7f4209a75000ull, bytes = 64 * 8, lab3 = l0 + 3 * 8, other = 0x2013458150ull;
	std::vector<uint32_t> piece = {
	    t3(0x93, 7), 0x06000113, static_cast<uint32_t>(lab3), static_cast<uint32_t>(lab3 >> 32u), 0, 0, 0xffffffffu, 0xffffffffu, 4, // WAIT_REG_MEM64 == 0 on label 3
	    t3(0x3c, 5), 0x00000013, static_cast<uint32_t>(other), static_cast<uint32_t>(other >> 32u), 1, 0xffffffffu, 4,              // WAIT_REG_MEM on another label
	    t3(0x3c, 5), 0x00000003, static_cast<uint32_t>(l0), static_cast<uint32_t>(l0 >> 32u), 0, 0xffffffffu, 4,                    // a register poll (MEM_SPACE 0)
	    t3(0x49, 6), 0x06200504, 0x42010000, static_cast<uint32_t>(lab3), static_cast<uint32_t>(lab3 >> 32u), 1, 0, 0,             // RELEASE_MEM to label 3
	    t3(0x93, 7), 0x06000113, static_cast<uint32_t>(l0 + bytes - 8), static_cast<uint32_t>((l0 + bytes - 8) >> 32u), 0, 0, 0xffffffffu, 0xffffffffu, 4}; // the last label
	std::vector<uint64_t> got;
	const uint64_t        range = is("RANGE") ? bytes - 8 : bytes;
	std::vector<uint32_t> w     = piece;
	if (is("SPACE")) w[9 + 7 + 1] |= 0x10u; // the plant: the register poll looks like a memory wait
	bc5::fp439::flip_label_waits(w.data(), static_cast<uint32_t>(w.size()), l0, range, [&](const uint32_t*, bool, uint64_t label) { got.push_back(label); });
	const bool ok = got.size() == 2 && got[0] == lab3 && got[1] == l0 + bytes - 8;
	for (const auto g : got) std::printf("flip-label wait on 0x%llx\n", static_cast<unsigned long long>(g));
	std::printf("%s (%zu waits)%s%s\n", ok ? "PASS" : "FAIL", got.size(), pl ? ", plant " : "", pl ? pl : "");
	return ok ? 0 : 1;
}
