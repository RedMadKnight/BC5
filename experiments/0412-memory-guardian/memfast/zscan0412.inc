// BC5 experiment 0412 (tag zs412, README section 48): the zero skip takes memory back BEFORE the GPU can write it.
// The defect (section 48): a skipped run is mapped onto ONE 2 MiB canary slice at every chunk of the run, the watcher
// looks at a slice once per (runs x 50 ms), and the take-back that follows a hit replaces the canary by the title's
// (zero) memory. So what the GPU writes into a skipped chunk is readable through every other chunk of the run for up
// to seconds, and is then lost. BC5_GUARD_ZSKIP_SCAN=1|2 (unset or 0: off, one test of a constant per submission):
// every submitted command buffer, and the tables it points to, is searched (ns412::scan, nscan0412.inc) for addresses
// inside memory that is under the canary now, and that memory gets its real pages before the buffer is handed to the
// kernel:  1: the whole run of a find;  2: from the find to the end of its run, at most kWindow bytes.
// The search is by value (see nscan0412.inc): an address a shader computes from a base in other memory, or one two
// tables away, is not found; the canary's hit count says whether that happens (it must stay 0 for the skip to be sound).
// This text is included by the main unit and by the CPU test zscan0412.cpp, after nscan0412.inc.
namespace zs412 {
static constexpr uint64_t kWindow = 8ull << 20;
inline int mode() {
	static const int m = [] {
		const char* e = std::getenv("BC5_GUARD_ZSKIP_SCAN");
		return e == nullptr ? 0 : (e[0] == '2' ? 2 : (e[0] == '1' ? 1 : 0));
	}();
	return m;
}
// The canary's mappings as search ranges: pieces is an ordered map from guest address to {size, run}; name = the run.
template <typename Pieces> inline void ranges(const Pieces& pieces, std::vector<ns412::Range>& out) {
	out.clear();
	for (const auto& [va, p]: pieces) {
		if (p.size == 0) continue;
		if (!out.empty() && out.back().hi == va && out.back().name == p.run) out.back().hi = va + p.size;
		else out.push_back({va, va + p.size, p.run});
	}
}
// The distinct runs the hits name, in the order of their first hit.
inline void runs_of(const std::vector<ns412::Hit>& hits, const std::vector<ns412::Range>& r, std::vector<uint32_t>& runs) {
	runs.clear();
	for (const auto& h: hits) {
		if (h.range >= r.size()) continue;
		const uint32_t run = r[h.range].name;
		if (std::find(runs.begin(), runs.end(), run) == runs.end()) runs.push_back(run);
	}
}
// Every run that has memory under the canary (for a search that a capacity limit cut short: review R25).
inline void all_runs(const std::vector<ns412::Range>& r, std::vector<uint32_t>& runs) {
	runs.clear();
	for (const auto& x: r) {
		if (std::find(runs.begin(), runs.end(), x.name) == runs.end()) runs.push_back(x.name);
	}
}
// Mode 2's window for a find at addr in range k: to the end of the ranges of the same run that follow without a gap,
// at most cap bytes from addr.
inline uint64_t window_hi(const std::vector<ns412::Range>& r, size_t k, uint64_t addr, uint64_t cap) {
	uint64_t hi = r[k].hi;
	for (size_t j = k + 1; j < r.size() && r[j].lo == hi && r[j].name == r[k].name && hi - addr < cap; j++) hi = r[j].hi;
	return hi - addr > cap ? addr + cap : hi;
}
} // namespace zs412
