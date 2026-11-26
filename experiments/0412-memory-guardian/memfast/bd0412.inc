// BC5 experiment 0412 (tag bd412, PLAN-memory-wall.md step 3): option B's rule, one switch per heap.
// BC5_GUARD_BYDATA_NAMES=name[,name...] (default unset: nothing changes). A heap named here is NOT imported whole
// even when BC5_DIRECT_EAGER_NAMES names it: it is imported where the file holds data (the CPU wrote) and where a
// hint, a force or a packet operand names a chunk (the write targets the host can name); K1r's read-only zero cover
// (tag k1r412) lies over the rest of its views. What that risks: a GPU write the host did not name lands on a
// read-only page: a GPU fault, with the fault record when the ring reset succeeds and a reboot of the box when it
// does not. So each heap is its own arm, on the maintainer's word (given 2026-11-13 for scripted arms on a private
// build and a private save copy).
// The log-only zero scan and the writers catcher keep reading a heap named here (they asked for eager views only).
// The list's parsing is here, free of the host, and tested by bd0412.cpp.
namespace bd412 {
inline std::vector<std::string> parse(const char* e) {
	std::vector<std::string> v;
	if (e == nullptr) return v;
	std::string cur;
	for (const char* c = e;; c++) {
		if (*c == ',' || *c == 0) {
			if (!cur.empty() && std::find(v.begin(), v.end(), cur) == v.end()) v.push_back(cur);
			cur.clear();
			if (*c == 0) break;
		} else {
			cur.push_back(*c);
		}
	}
	return v;
}
inline bool has(const std::vector<std::string>& names, const char* name) {
	return name != nullptr && std::find(names.begin(), names.end(), name) != names.end();
}
} // namespace bd412
