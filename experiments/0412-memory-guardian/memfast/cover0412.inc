// BC5 experiment 0412 (tag cv412): what a K1r cover is to the HOST. GPL-2.0.
// A cover (a read-only shared mapping of the zero buffer over never-written memory) exists for the GPU's own reads.
// For every decision of the host that asks "is this address mapped?" (the packet filter's operand check, the soft CP,
// the probes) it is a hole, as that memory was before K1r: hole() says so for one mapping.
// No switch (BC5_GUARD_K1R_COVERS_VISIBLE was removed on 2026-11-13: no option restores the state that faulted ASTRO
// BOT's start at 11:32). The three-argument forms below are the CPU test's model of that state, not a setting.
// K1 at the filter (tag k1f412): import() says whether an operand's chunk is to be imported: only when the operand
// is not covered by the title's own mappings.
#pragma once
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <vector>

namespace cv412 {
// One mapping of the device's list: is it a hole for the host?
inline bool hole(bool shared, bool readonly, bool covers_visible) { return shared && readonly && !covers_visible; }
inline bool hole(bool shared, bool readonly) { return hole(shared, readonly, false); }

// The unit's covered_sorted() with the rule, over any mapping type with va, size, shared, readonly (sorted by va,
// disjoint): the CPU test's model of it.
template <typename M> inline bool covered_sorted(const std::vector<M>& maps, uint64_t a, uint64_t bytes, bool covers_visible) {
	const uint64_t end = a + bytes;
	uint64_t       pos = a;
	for (int guard = 0; pos < end && guard < 64; guard++) {
		auto it = std::upper_bound(maps.begin(), maps.end(), pos, [](uint64_t v, const M& m) { return v < m.va; });
		if (it == maps.begin()) return false;
		--it;
		if (hole(it->shared, it->readonly, covers_visible)) return false;
		if (pos >= it->va + it->size) return false;
		pos = it->va + it->size;
	}
	return pos >= end;
}
} // namespace cv412
