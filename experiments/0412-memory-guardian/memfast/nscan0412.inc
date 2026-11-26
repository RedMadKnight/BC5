// BC5 experiment 0412 (tag ns412, README section 39): does the GPU's work name memory that BC5_GUARD_NOGPU_UNPIN left
// unpinned? BC5_GUARD_NOGPU_SCAN=0|1|2 (unset or 0: off, one test of a constant per submission).
//   1: every submitted command buffer is searched for addresses inside the left-out ranges, and so is the first
//      kTable bytes behind every address in it that points into other direct memory (the tables shaders reach their
//      buffers through); a find is journaled with its heap.
//   2: as 1, and the memory around a find is pinned before the buffer is handed to the kernel (the glue's direct_force).
// An address is looked for in the two forms the title's buffers and tables carry (the timeout probe's lines of the
// hang of 2026-11-11 22:32 show both): a pair of dwords "low 32 bits, high bits in the low 16 of the next dword", and
// a dword that is the address shifted right by 8 with bits 40.. in the low 8 of the next one (image descriptors).
// It is a search by value: a number that only looks like an address is a false find and costs one journal line and,
// in mode 2, some pinned memory; an address a shader computes, or one two tables away, is not found.
// This text is included by the main unit and by the CPU test nscan0412.cpp.
namespace ns412 {
static constexpr uint64_t kTable = 2048; // bytes read behind an address that points into direct memory
static constexpr size_t   kMaxTables = 96; // distinct table addresses followed per buffer
struct Range {
	uint64_t lo, hi; // guest addresses, hi exclusive
	uint32_t name;   // index into the names the ranges were made with
};
struct Hit {
	uint32_t at;    // dword index in the searched words
	uint32_t form;  // 0: pair, 1: shifted by 8
	uint64_t addr;
	uint32_t range; // index into the ranges
};
inline int mode() {
	static const int m = [] {
		const char* e = std::getenv("BC5_GUARD_NOGPU_SCAN");
		return e == nullptr ? 0 : (e[0] == '2' ? 2 : (e[0] == '1' ? 1 : 0));
	}();
	return m;
}
// The guest address ranges of the views' parts that lie over the left-out chunks (`off`: sorted chunk offsets in the
// direct file). Sorted by address; neighbours of one name are merged. V has va, off, size, name.
template <typename Views> inline std::vector<Range> ranges(const Views& views, const std::vector<uint64_t>& off, uint64_t chunk, std::vector<std::string>& names) {
	std::vector<Range> out;
	names.clear();
	if (off.empty()) return out;
	for (const auto& v: views) {
		if (v.size == 0) continue;
		const uint64_t vend = v.off + v.size;
		auto           it = std::lower_bound(off.begin(), off.end(), v.off - v.off % chunk);
		for (; it != off.end() && *it < vend; ++it) {
			const uint64_t lo = *it > v.off ? *it : v.off;
			const uint64_t hi = *it + chunk < vend ? *it + chunk : vend;
			if (lo >= hi) continue;
			uint32_t n = 0;
			for (; n < names.size(); n++) {
				if (names[n] == v.name) break;
			}
			if (n == names.size()) names.push_back(std::string(v.name));
			out.push_back({v.va + (lo - v.off), v.va + (hi - v.off), n});
		}
	}
	std::sort(out.begin(), out.end(), [](const Range& a, const Range& b) { return a.lo < b.lo; });
	std::vector<Range> merged;
	for (const auto& r: out) {
		if (!merged.empty() && merged.back().hi == r.lo && merged.back().name == r.name) merged.back().hi = r.hi;
		else merged.push_back(r);
	}
	return merged;
}
// The range that holds a, or -1. r: sorted by lo, disjoint.
inline int find(const std::vector<Range>& r, uint64_t a) {
	if (r.empty() || a < r.front().lo || a >= r.back().hi) return -1;
	const auto it = std::upper_bound(r.begin(), r.end(), a, [](uint64_t x, const Range& y) { return x < y.lo; });
	if (it == r.begin()) return -1;
	const auto& c = *(it - 1);
	return a < c.hi ? static_cast<int>(&c - r.data()) : -1;
}
inline uint64_t pair_addr(uint32_t lo, uint32_t hi) { return (static_cast<uint64_t>(hi & 0xffffu) << 32) | lo; }
inline uint64_t shifted_addr(uint32_t lo, uint32_t hi) { return (static_cast<uint64_t>(hi & 0xffu) << 40) | (static_cast<uint64_t>(lo) << 8); }
// Returns false when a hit or a candidate table was left out by a capacity limit (review of 2026-11-12, R25): true means
// no truncation, NOT that every address the GPU can reach was seen. max_others: the limit of the candidates (kMaxTables
// for the callers of g412t..g412v).
// Searches n dwords. hits: every dword position whose pair or shifted form lies in a range (at most max_hits).
// others (may be null): the distinct pair-form addresses in [win_lo, win_hi) that lie in no range, at most kMaxTables:
// the candidates for a table to follow.
inline bool scan(const uint32_t* w, uint32_t n, const std::vector<Range>& r, std::vector<Hit>& hits, size_t max_hits, std::vector<uint64_t>* others, uint64_t win_lo,
                 uint64_t win_hi, size_t max_others = kMaxTables) {
	if (r.empty() || n < 2) return true;
	bool complete = true;
	for (uint32_t i = 0; i + 1 < n; i++) {
		const uint64_t a = pair_addr(w[i], w[i + 1]);
		int            k = find(r, a);
		if (k >= 0) {
			if (hits.size() < max_hits) hits.push_back({i, 0, a, static_cast<uint32_t>(k)});
			else complete = false;
			continue;
		}
		const uint64_t b = shifted_addr(w[i], w[i + 1]);
		k                = find(r, b);
		if (k >= 0) {
			if (hits.size() < max_hits) hits.push_back({i, 1, b, static_cast<uint32_t>(k)});
			else complete = false;
			continue;
		}
		if (others != nullptr && a >= win_lo && a < win_hi && std::find(others->begin(), others->end(), a) == others->end()) {
			if (others->size() < max_others) others->push_back(a);
			else complete = false;
		}
	}
	return complete;
}
} // namespace ns412
