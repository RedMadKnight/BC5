// BC5 experiment 0412 (tag rl412, README section 62): the lost jobs' label writes when TWO jobs time out in one hang.
// m11_keep_lost() (exp 0401 e11) copies the pending label writes at a timeout so that the reopen can write them
// (BC5_DIRECT_RESET_LABELS). It is called once per timed-out job, and each call is followed by a forget of ALL
// pending writes. With two jobs timed out together (a draw buffer and a compute buffer: his play of 2026-11-13, and
// the pairs of F260, sections 38 and 53) the second call copied the list the first call's forget had just emptied,
// over the kept one: "0 label writes of the lost jobs", nothing written, and the title waited for ever on labels of
// the lost compute buffer. BC5_DIRECT_RESET_LABELS_ADD=1 (default off): a second keep for the SAME reopen adds to
// what is kept instead of replacing it. This text is included by the main unit and by the CPU test rlabels0412.cpp.
namespace rl412 {
inline bool on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_DIRECT_RESET_LABELS_ADD");
		return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
	}();
	return v;
}
// kept, kept_for: what is held for a reopen and which reopen; pending: the list at this timeout; for_reopen: the
// reopen this timeout leads to. add = the switch.
template <typename V> inline void keep(V& kept, uint64_t& kept_for, const V& pending, uint64_t for_reopen, bool add) {
	if (add && kept_for == for_reopen) {
		kept.insert(kept.end(), pending.begin(), pending.end());
	} else {
		kept = pending;
	}
	kept_for = for_reopen;
}
} // namespace rl412
