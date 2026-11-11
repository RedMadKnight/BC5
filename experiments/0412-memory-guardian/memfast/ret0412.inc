// BC5 experiment 0412 (tag ra412, README section 28): the return-aware orphan release.
// BC5_GUARD_RETURN_EXEMPT=<seconds> (unset, empty, "0": off, and then exempt() is always false: the release decides
// as before). A chunk that the lazy release cut out and that came back under a view is exempt from being cut again
// for <seconds>; every further return doubles that time (at most 64 times the base). A chunk that never came back is
// never exempt, so memory that is really dead is still cut after the release's own idle time. The title's AMM heap,
// which gives up and takes back the same range every few seconds, is then cut once and left pinned afterwards.
// Times are the caller's clock in nanoseconds (the lazy release's `now`). The table is used by the lazy release's
// pass only, which runs under the device mutex. Included by the main unit (mkret0412.py) and by ret0412.cpp.
namespace ra412 {
static constexpr uint64_t kChunkBytes = 2ull << 20;
class Table {
public:
	explicit Table(uint64_t base_ns): base_(base_ns) {}
	bool on() const { return base_ != 0; }
	// The chunk came back under a view after a cut.
	void back(uint64_t chunk, uint64_t now) {
		if (!on()) return;
		Entry& e = tab_[chunk];
		if (e.returns < 1000000u) e.returns++;
		const uint32_t shift = e.returns - 1 < 6u ? e.returns - 1 : 6u;
		e.until = now + (base_ << shift);
		returned_bytes_ += kChunkBytes;
	}
	// May the release cut this chunk now? false = it may; true = it came back lately and stays.
	bool exempt(uint64_t chunk, uint64_t now) {
		if (!on()) return false;
		const auto it = tab_.find(chunk);
		if (it == tab_.end() || now >= it->second.until) return false;
		skipped_++;
		return true;
	}
	uint64_t exempt_bytes(uint64_t now) const {
		uint64_t n = 0;
		for (const auto& kv: tab_) {
			if (now < kv.second.until) n += kChunkBytes;
		}
		return n;
	}
	uint64_t returned_bytes() const { return returned_bytes_; }
	uint64_t skipped() const { return skipped_; }
	size_t   chunks() const { return tab_.size(); }
	uint32_t returns(uint64_t chunk) const {
		const auto it = tab_.find(chunk);
		return it == tab_.end() ? 0u : it->second.returns;
	}

private:
	struct Entry {
		uint64_t until   = 0;
		uint32_t returns = 0;
	};
	uint64_t                  base_;
	std::map<uint64_t, Entry> tab_;
	uint64_t                  returned_bytes_ = 0, skipped_ = 0;
};
inline Table& table() {
	static Table t([]() -> uint64_t {
		const char* e = std::getenv("BC5_GUARD_RETURN_EXEMPT");
		if (e == nullptr || e[0] == 0) return 0;
		return static_cast<uint64_t>(std::strtoull(e, nullptr, 10)) * 1000000000ull;
	}());
	return t;
}
// One line at most every 10 s, from the release's pass (RA412_PRINT is printf-like).
inline void report(uint64_t now, double cut_mib, double back_mib) {
	Table& t = table();
	if (!t.on()) return;
	static uint64_t last = 0;
	if (last != 0 && now - last < 10000000000ull) return;
	last = now;
	const double ex = static_cast<double>(t.exempt_bytes(now)) / 1048576.0;
	RA412_PRINT("return-aware release (exp 0412, tag ra412): cut %.1f MiB in all, returned %.1f MiB, exempt now %.1f MiB in %zu chunks that returned, %" PRIu64 " cut decisions skipped; net released %.1f MiB\n",
	            cut_mib, back_mib, ex, t.chunks(), t.skipped(), cut_mib - back_mib);
}
} // namespace ra412
