// BC5 experiment 0412 (tag kl412, README section 71): K1r covers only NEVER-WRITTEN memory, under lazy views too.
// The defect (2026-11-13 15:32, ASTRO BOT on g412zc with K1r on; the watched page 0x3082f6000): K1r covered every
// part of a view that no imported buffer covers. Under a view imported by data that is the never-written memory (a
// written chunk is imported at the next sync). Under a LAZY view (a CPU heap; only hints import it) a chunk the CPU
// HAS written stays unimported, and K1r put the zero cover over it: a GPU read there returned zeros where the title's
// data lies. The console returns the data. A zero is right only where nothing was ever written.
// The rule: under a lazy view a piece whose file chunk holds data gets NO cover; it stays unmapped, as without K1r,
// and a GPU read there is a fault with a record that names it (the cure is then the import of that memory, not a zero).
// BC5_GUARD_K1R_COVER_WRITTEN=1 turns the rule off (the state before, for telling the two apart).
// Which chunks hold data is asked of the file (SEEK_DATA) at most once per BC5_GUARD_K1R_WRITTEN_SCAN_MS (default
// 100) and only at a mapping rebuild; between scans the last answer stands. Limit: a chunk written since the last
// scan keeps its zero cover until the next rebuild after the period.
// The rule is here, free of the host, and tested by kl0412.cpp.
namespace kl412 {
inline bool cover_written() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_GUARD_K1R_COVER_WRITTEN");
		return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
	}();
	return v;
}
inline uint64_t period_ns() {
	static const uint64_t v = [] {
		const char*    e  = std::getenv("BC5_GUARD_K1R_WRITTEN_SCAN_MS");
		const uint64_t ms = e != nullptr && e[0] != 0 ? std::strtoull(e, nullptr, 10) : 100;
		return (ms > 10000 ? 10000 : ms) * 1'000'000ull;
	}();
	return v;
}
struct Known {
	std::set<uint64_t> written;                                         // file chunk offsets that held data at the last scan
	uint64_t           last_ns = 0, scans = 0, asked = 0, scan_ns = 0; // counters for the journal
	bool               scanned = false;
	// A scan is due at the first call and when the period has passed; a due scan forgets the last answer.
	bool begin(uint64_t now_ns, uint64_t period) {
		if (scanned && now_ns - last_ns < period) return false;
		scanned = true;
		last_ns = now_ns;
		scans++;
		written.clear();
		return true;
	}
};
// The pieces of ONE lazy view (mapped at vva, file offset voff; each piece lies inside one chunk): those whose chunk
// holds data are removed, the order of the rest kept. has_data(chunk offset) is asked only during a scan, once per
// chunk. Returns the number removed.
template <typename Piece, typename F> inline uint64_t drop_written(std::vector<Piece>& pieces, uint64_t vva, uint64_t voff, uint64_t chunk, Known& k, bool scan, F&& has_data) {
	uint64_t dropped = 0;
	size_t   w       = 0;
	for (size_t i = 0; i < pieces.size(); i++) {
		const uint64_t choff = ((voff + (pieces[i].va - vva)) / chunk) * chunk;
		bool           wr    = k.written.count(choff) != 0;
		if (!wr && scan) {
			k.asked++;
			if (has_data(choff)) {
				k.written.insert(choff);
				wr = true;
			}
		}
		if (wr) {
			dropped++;
			continue;
		}
		if (w != i) pieces[w] = pieces[i];
		w++;
	}
	pieces.resize(w);
	return dropped;
}
} // namespace kl412
