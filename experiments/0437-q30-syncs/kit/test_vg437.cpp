// BC5 experiment 0437 (tag vg437): laptop test of VirtualRanges' direct generation.
// test_vg437.sh extracts `class VirtualRanges { ... };` and the helpers above it from the patched
// src/kernel/memory.cpp into vr437.inc; this file supplies stand-ins for KytyPlus' Common types and drives random
// edits of every kind. Oracle: after each edit the direct generation must have moved if and only if the table's list
// of direct ranges (start, size, offset, name) changed, the exact input of direct_views_build's kind 0.
#include <algorithm>
#include <atomic>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <random>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

constexpr uint32_t KERNEL_MAXIMUM_NAME_LENGTH = 32;
namespace Common {
using Mutex     = std::recursive_mutex;
using LockGuard = std::lock_guard<std::recursive_mutex>;
} // namespace Common
#define EXIT_IF(x)                                                                                                     \
	do {                                                                                                               \
		if (x) std::abort();                                                                                           \
	} while (0)
// memory.cpp's constants (src/kernel/memory.cpp, the lines after `LIB_NAME("libkernel", ...)`)
constexpr int      PROT_CPU_READ          = 0x01;
constexpr int      PROT_CPU_WRITE         = 0x02;
constexpr int      PROT_CPU_EXEC          = 0x04;
constexpr int      PROT_GPU_READ          = 0x10;
constexpr int      PROT_GPU_WRITE         = 0x20;
constexpr uint64_t PAGE_TABLE_GRANULARITY = 2ull * 1024ull * 1024ull;
#include "bc5/env_rule.hpp"   // the tree's own, copied beside this file by test_vg437.sh
#include "bc5/map_records.hpp" // the same

#include "vr437.inc"

using T = std::tuple<uint64_t, uint64_t, uint64_t, std::string>;
static std::vector<T> direct_list(VirtualRanges& vr) {
	std::vector<VirtualRanges::Range> rs;
	vr.Snapshot(&rs);
	std::vector<T> out;
	for (const auto& r: rs)
		if (r.type == VirtualRangeType::Direct && r.size != 0) out.emplace_back(r.start, r.size, r.offset, std::string(r.name, strnlen(r.name, KERNEL_MAXIMUM_NAME_LENGTH)));
	return out;
}

int main(int argc, char** argv) {
	const uint64_t seeds = argc > 1 ? std::strtoull(argv[1], nullptr, 10) : 200;
	uint64_t       edits = 0, direct_moves = 0, other_moves = 0, bad = 0;
	const char*    names[] = {"GpuGarlicMemory", "GpuOnionMemory", "FileSystem", "orbis_user_malloc", "", "a-very-long-name-of-thirty-one-c"};
	const VirtualRangeType types[] = {VirtualRangeType::Reserved, VirtualRangeType::PoolReserved, VirtualRangeType::Direct, VirtualRangeType::Flexible,
	                                  VirtualRangeType::Pooled, VirtualRangeType::Stack, VirtualRangeType::Code, VirtualRangeType::Runtime};
	for (uint64_t seed = 1; seed <= seeds; seed++) {
		std::mt19937_64 rng(seed);
		VirtualRanges   vr;
		const uint64_t  page = 0x4000, span = 256;
		auto            rnd_start = [&] { return (1 + rng() % span) * page; };
		auto            rnd_size  = [&] { return (1 + rng() % 24) * page; };
		for (int step = 0; step < 4000; step++) {
			const auto     before = direct_list(vr);
			const uint64_t g0 = vr.Generation(), d0 = vr.DirectGeneration();
			const int      op = static_cast<int>(rng() % 9);
			const uint64_t s = rnd_start(), z = rnd_size();
			// whole existing ranges are picked half of the time, so that exact-match paths run too
			std::vector<VirtualRanges::Range> rs;
			vr.Snapshot(&rs);
			uint64_t es = s, ez = z;
			if (!rs.empty() && (rng() & 1)) {
				const auto& r = rs[rng() % rs.size()];
				es = r.start;
				ez = r.size;
			}
			switch (op) {
				case 0:
				case 1: vr.Add(s, z, rng() % 0x100000 * page, static_cast<int>(rng() % 4), static_cast<int>(rng() % 3), types[rng() % 8], names[rng() % 6], (rng() % 8) == 0); break;
				case 2: vr.Remove(es, ez); break;
				case 3: vr.ReleaseReserved(es, ez); break;
				case 4: vr.ConsumeReserved(es, ez, types[rng() % 2]); break;
				case 5: vr.ConsumeReservedSpan(es, ez, nullptr, types[rng() % 8]); break;
				case 6: vr.Rename(es, ez, names[rng() % 6]); break;
				case 7: vr.Protect(es, ez, static_cast<int>(rng() % 4)); break;
				case 8: vr.SetMemoryType(es, ez, static_cast<int>(rng() % 3)); break;
			}
			edits++;
			const auto after   = direct_list(vr);
			const bool changed = after != before;
			const bool moved   = vr.DirectGeneration() != d0;
			if (vr.Generation() == g0) bad++, std::printf("seed %" PRIu64 " step %d op %d: the whole generation did not move\n", seed, step, op);
			if (changed != moved) {
				bad++;
				if (bad < 20) std::printf("seed %" PRIu64 " step %d op %d: direct list %s, direct generation %s\n", seed, step, op, changed ? "CHANGED" : "same", moved ? "moved" : "did not move");
			}
			if (moved) direct_moves++;
			else other_moves++;
		}
	}
	std::printf("vg437 test: %" PRIu64 " edits, direct generation moved %" PRIu64 ", stayed %" PRIu64 ", mismatches %" PRIu64 "\n", edits, direct_moves, other_moves, bad);
	return bad == 0 ? 0 : 1;
}
