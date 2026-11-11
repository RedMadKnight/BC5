// BC5 experiment 0412 (tag zc412, README section 33): the zero skip's blind window, measured.
// The zero skip (exp 0379) maps a canary of zeros for the GPU under chunks it has not pinned and learns of the CPU's
// writes into such a chunk only when zskip_take_back() polls the memfd (SEEK_DATA). Between the write and that poll
// the GPU reads zeros where the title has data (README section 31: the suspected cause of the two ring timeouts).
// BC5_GUARD_ZSKIP_STAT=1 (default off: both calls return after one test of a constant) counts, for every chunk the
// poll finds written: how long ago the previous poll was (the write happened inside that time) and how many
// submissions went to the GPU in between (each of them ran with zeros mapped at that chunk). One journal line per
// chunk for the first 300, then every 20th, and a summary every 30 s. No behaviour changes.
namespace zc412 {
inline bool on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_GUARD_ZSKIP_STAT");
		return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
	}();
	return v;
}
inline uint64_t now_ns() {
	timespec ts {};
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return static_cast<uint64_t>(ts.tv_sec) * 1000000000ull + static_cast<uint64_t>(ts.tv_nsec);
}
struct S {
	uint64_t prev_ns = 0, prev_sub = 0;  // the previous poll
	uint64_t win_ns = 0, win_sub = 0;    // this poll's window: time and submissions since the previous one
	uint64_t polls = 0, found = 0, found_with_sub = 0, max_ns = 0, sum_ns = 0, sub_sum = 0, last_report = 0;
	uint64_t over10 = 0, over50 = 0;     // chunks whose window was over 10 ms / over 50 ms
};
inline S& st() {
	static S s;
	return s;
}
// At the start of a poll; submits is the count of submissions so far.
inline void poll(uint64_t submits) {
	if (!on()) return;
	S&             s   = st();
	const uint64_t now = now_ns();
	s.win_ns  = s.prev_ns != 0 ? now - s.prev_ns : 0;
	s.win_sub = s.prev_ns != 0 ? submits - s.prev_sub : 0;
	s.prev_ns  = now;
	s.prev_sub = submits;
	s.polls++;
	if (s.last_report == 0) s.last_report = now;
	if (now - s.last_report >= 30000000000ull) {
		s.last_report = now;
		ZC412_PRINT("zero skip catcher (exp 0412, tag zc412): t %.0f s: %" PRIu64 " polls; %" PRIu64 " chunks found written by the CPU, %" PRIu64 " of them with a submission since the previous poll (%" PRIu64
		            " submissions in all); the window: mean %.2f ms, longest %.1f ms, over 10 ms for %" PRIu64 " chunks, over 50 ms for %" PRIu64 "\n",
		            ZC412_NOW(), s.polls, s.found, s.found_with_sub, s.sub_sum, s.found != 0 ? static_cast<double>(s.sum_ns) / 1e6 / static_cast<double>(s.found) : 0.0,
		            static_cast<double>(s.max_ns) / 1e6, s.over10, s.over50);
	}
}
// The poll found CPU data in a skipped chunk (file offset c).
inline void found(uint64_t c) {
	if (!on()) return;
	S& s = st();
	s.found++;
	s.sum_ns += s.win_ns;
	s.sub_sum += s.win_sub;
	if (s.win_sub != 0) s.found_with_sub++;
	if (s.win_ns > s.max_ns) s.max_ns = s.win_ns;
	if (s.win_ns > 10000000ull) s.over10++;
	if (s.win_ns > 50000000ull) s.over50++;
	if (s.found <= 300 || s.found % 20 == 0) {
		ZC412_PRINT("zero skip catcher (exp 0412, tag zc412): t %.3f s: chunk at file 0x%" PRIx64 " has CPU data; the previous poll was %.2f ms ago, %" PRIu64 " submissions went out in between\n", ZC412_NOW(), c,
		            static_cast<double>(s.win_ns) / 1e6, s.win_sub);
	}
}
} // namespace zc412
