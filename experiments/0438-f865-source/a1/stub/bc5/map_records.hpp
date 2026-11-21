// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0415 (tag mr415), stage S1 of experiments/0415-load-times-fps/DESIGN-lock-side.md: the guest's ranges
// leave a record of every change (the span [start, start + size) a mutator of the range table was called with), and a
// list derived from the ranges is brought up to date from those spans instead of being rebuilt from every range.
// KYTY_BC5_MAP_RECORDS=verify (the only mode in S1; default off): the direct path keeps such a list of its views
// beside the rebuilt one and compares the two at every rebuild; the rebuilt list is what is used.
//
// Why a span is enough [C, kernel/memory.cpp VirtualRanges]: each mutator changes ranges inside its span and merges or
// splits only ranges that overlap or touch it. So after a change, every entry that differs from before lies inside the
// extent of the current ranges that overlap or touch the span: those ranges are read again and replace whatever the
// list held there. Reading the CURRENT ranges for an OLD span is right as well (the result is the current state of
// that extent), so several spans can be applied in any order against one snapshot.
// Pure functions; CPU test experiments/0415-load-times-fps/kit/test0415rec.cpp.
#pragma once

#include <algorithm>
#include <cstdint>
#include <utility>
#include <vector>

namespace bc5::map_records {

inline uint64_t end_of(uint64_t start, uint64_t size) {
	return size > UINT64_MAX - start ? UINT64_MAX : start + size;
}

// `ranges` sorted by start, not overlapping (R has .start and .size). The index range [first, last) of the ranges
// that overlap [lo, hi) or touch it (end == lo, or start == hi).
template <class R>
inline std::pair<size_t, size_t> touching(const std::vector<R>& ranges, uint64_t lo, uint64_t hi) {
	// ends are in order too, since the ranges do not overlap
	const auto first = std::lower_bound(ranges.begin(), ranges.end(), lo, [](const R& r, uint64_t x) { return end_of(r.start, r.size) < x; });
	const auto last  = std::upper_bound(ranges.begin(), ranges.end(), hi, [](uint64_t x, const R& r) { return x < r.start; });
	const auto a     = static_cast<size_t>(first - ranges.begin());
	const auto b     = static_cast<size_t>(last - ranges.begin());
	return {a, b < a ? a : b};
}

// `views` sorted by va, not overlapping (V has .va and .size), derived from the ranges by `make` (bool make(const R&,
// V*): false when the range is not a view). Brings `views` up to date for a change inside [lo, hi).
template <class V, class R, class Make>
inline void apply(std::vector<V>& views, const std::vector<R>& ranges, uint64_t lo, uint64_t hi, Make&& make) {
	const auto [a, b] = touching(ranges, lo, hi);
	uint64_t   slo = lo, shi = hi;
	if (a < b) {
		slo = std::min(slo, ranges[a].start);
		shi = std::max(shi, end_of(ranges[b - 1].start, ranges[b - 1].size));
	}
	// the views that overlap [slo, shi), and the ones of zero extent inside it, go
	auto from = std::lower_bound(views.begin(), views.end(), slo, [](const V& v, uint64_t x) { return end_of(v.va, v.size) <= x; });
	auto to   = from;
	while (to != views.end() && to->va < shi) ++to;
	const auto at = static_cast<size_t>(from - views.begin());
	views.erase(from, to);
	std::vector<V> fresh;
	for (size_t i = a; i < b; i++) {
		V v {};
		if (make(ranges[i], &v)) fresh.push_back(std::move(v));
	}
	views.insert(views.begin() + static_cast<std::ptrdiff_t>(at), std::make_move_iterator(fresh.begin()), std::make_move_iterator(fresh.end()));
}

} // namespace bc5::map_records
