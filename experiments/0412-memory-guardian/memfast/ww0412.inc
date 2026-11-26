// BC5 experiment 0412 (tag ww412, PLAN-memory-wall.md step 2): the catcher for UNNAMED WRITERS. Log only.
// BC5_GUARD_WRITERS=1 (default off). It needs the log-only zero scan (BC5_DIRECT_ZEROSCAN_AT, BC5_DIRECT_ZERO_NAMES).
// Option B wants an eager heap imported by data, with K1r's read-only zero cover over what nobody wrote, and every GPU
// write target imported before the write. The host can name a write target in two ways today: a hint or force (the
// render-target and depth binds; everything that goes through direct_force) and a memory operand of a packet in a
// submitted buffer. What a shader writes through the descriptor tables it cannot name. This catcher counts, per
// eager heap and per interval between two zero scans, the 2 MiB chunks that were all zero at the last scan and hold
// data now, split into NAMED (a hint, a force or a packet operand named the chunk at any time before) and NOT NAMED.
// A not-named chunk is one the rule of option B would have left under a read-only cover while something wrote it.
// Limits, stated in every summary line: a CPU write counts as not named (the catcher cannot tell it from a shader's
// write), so the count is an upper bound of the unknown GPU writers; only the main buffer's packets are read, not
// the buffers they call; a chunk that left its view between two scans reads as "not zero" and is counted too.
// The classification is here, free of the host, and tested by ww0412.cpp.
namespace ww412 {
inline bool on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_GUARD_WRITERS");
		return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
	}();
	return v;
}
struct Turned {
	uint64_t              turned = 0, named = 0; // chunks all zero before and not now; of them named
	std::vector<uint64_t> unnamed;               // file offsets of the first not-named ones (at most keep)
};
// prev and now: one flag per scan slot of a heap (1 = all zero), slot i at file offset base + i * chunk (base need not
// lie on the file's chunk grid). is_named(file chunk offset on the grid) says whether that chunk was ever named. A
// slot that straddles two grid chunks is named when either is.
template <typename F> inline Turned classify(const std::vector<uint8_t>& prev, const std::vector<uint8_t>& now, uint64_t base, uint64_t chunk, size_t keep, F&& is_named) {
	Turned t;
	if (prev.size() != now.size()) return t; // the heap's span changed: no comparison for this interval
	for (size_t i = 0; i < now.size(); i++) {
		if (prev[i] != 1 || now[i] != 0) continue;
		t.turned++;
		const uint64_t c  = base + static_cast<uint64_t>(i) * chunk;
		const uint64_t g0 = (c / chunk) * chunk, g1 = ((c + chunk - 1) / chunk) * chunk;
		if (is_named(g0) || (g1 != g0 && is_named(g1))) t.named++;
		else if (t.unnamed.size() < keep) t.unnamed.push_back(c);
	}
	return t;
}
} // namespace ww412
