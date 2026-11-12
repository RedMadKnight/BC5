// BC5 experiment 0412 (tag ng412, README section 37): direct memory the title mapped WITHOUT a GPU protection bit is
// not pinned for the GPU. BC5_GUARD_NOGPU_UNPIN=<heap name>[,<heap name>...] (unset, empty or "-": off, and plan()
// returns nothing after one test). A 2 MiB chunk of the direct file is left unimported when EVERY view that touches
// it is of a listed heap and carries neither GPU bit (0x10 read, 0x20 write: PROT_GPU_READ / PROT_GPU_WRITE of the
// host's memory layer). A chunk that any other view touches (another heap, or the same heap with a GPU bit) is
// imported as before. The caller (the unit's glue, mknogpu0412.py) also keeps a chunk that a hint or a learned window
// forced, maps the shared zero buffer for the GPU under the views of what is left out (a stray GPU access reads zeros
// and cannot fault), and watches that buffer for GPU writes.
// When the title later gives a range a GPU bit (mprotect and the calls that end in VirtualRanges' protection edit),
// the guest ranges' generation changes, the views are rebuilt, the chunk is no longer in plan()'s result, and the
// same sync imports and maps it, before the next submission.
// This text is included by the main unit and by the CPU test nogpu0412.cpp.
namespace ng412 {
static constexpr int kGpuBits = 0x30;
inline const std::vector<std::string>& names() {
	static const std::vector<std::string> v = [] {
		std::vector<std::string> out;
		const char*              e = std::getenv("BC5_GUARD_NOGPU_UNPIN");
		if (e == nullptr || e[0] == 0 || (e[0] == '-' && e[1] == 0)) return out;
		std::string cur;
		for (const char* c = e;; c++) {
			if (*c == ',' || *c == 0) {
				if (!cur.empty()) out.push_back(cur);
				cur.clear();
				if (*c == 0) break;
			} else {
				cur.push_back(*c);
			}
		}
		return out;
	}();
	return v;
}
inline bool listed(const std::vector<std::string>& list, const std::string& name) {
	for (const auto& n: list) {
		if (n == name) return true;
	}
	return false;
}
// The chunks (offsets in the direct file, multiples of `chunk`) to leave unimported, sorted and unique.
// V has off, size (bytes in the file), name and prot.
template <typename Views> inline std::vector<uint64_t> plan(const Views& views, uint64_t chunk, const std::vector<std::string>& list) {
	std::vector<uint64_t> cand, block;
	if (list.empty()) return cand;
	for (const auto& v: views) {
		if (v.size == 0) continue;
		const bool q = (v.prot & kGpuBits) == 0 && listed(list, std::string(v.name));
		for (uint64_t c = v.off - v.off % chunk; c < v.off + v.size; c += chunk) (q ? cand : block).push_back(c);
	}
	std::sort(cand.begin(), cand.end());
	cand.erase(std::unique(cand.begin(), cand.end()), cand.end());
	std::sort(block.begin(), block.end());
	block.erase(std::unique(block.begin(), block.end()), block.end());
	std::vector<uint64_t> out;
	std::set_difference(cand.begin(), cand.end(), block.begin(), block.end(), std::back_inserter(out));
	return out;
}
} // namespace ng412
