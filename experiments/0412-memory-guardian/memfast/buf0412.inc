// BC5 experiment 0412 (tag bf412, README section 26): the time line of every command buffer, for the question whether
// the host hands the title's buffers to the kernel late. BC5_GUARD_BUF_STAT=<file> (unset or empty: off, every call
// below is one test of a constant). Lines, times in seconds on the journal's clock (GP412_NOW):
//   B <t> <slot> <kind> <dwords>                         the title (or the ring thread for it) hands a buffer to submit_split
//   S <n> <t open> <t flush> <t kernel> <slot> <kind> <dwords> <segments> <why>
//                                                        submission n: its chain was opened, flushed, and the kernel had it
//   D <n> <t> <kind> <dwords> <ok>                       the completion thread saw submission n's fence
//   W <t start> <t end> <label hex> <slot>               a label wait in submit_split (50 us polls of one label)
//   f <t> / F <t>                                        the title called the flip / the flip's drain ended
// <slot> is gp412's (0 Render Thread, 1 game-main, 2 bc5-ring, 3 bc5-cq0, 4 bc5-chainwd, 5 others). No behaviour
// changes: label_sleep is gp412::poll_sleep(us, kLabel). Included by the main unit after gap0412.inc (mkbuf0412.py).
namespace bf412 {
inline FILE* file() {
	static FILE* const f = []() -> FILE* {
		const char* e = std::getenv("BC5_GUARD_BUF_STAT");
		if (e == nullptr || e[0] == 0) return nullptr;
		FILE* o = std::fopen(e, "w");
		if (o != nullptr) setvbuf(o, nullptr, _IOFBF, 1 << 20);
		return o;
	}();
	return f;
}
inline bool on() { return file() != nullptr; }
inline std::mutex& mu() {
	static std::mutex m;
	return m;
}
inline const char* ks(const char* k) { return k != nullptr ? k : "?"; }
inline const char* ks(const std::string& k) { return k.c_str(); }
inline thread_local uint64_t t_open_ns = 0, t_flush_ns = 0, t_kernel_ns = 0;
inline thread_local int      t_why = -1;
inline thread_local uint64_t w_label = 0, w_start_ns = 0, w_last_ns = 0;
inline double to_t(uint64_t ns, uint64_t now_ns, double now_t) { return ns == 0 ? now_t : now_t - static_cast<double>(now_ns - ns) / 1e9; }
inline void wait_flush() { // the pending label wait of this thread, if any
	if (w_start_ns == 0) return;
	const uint64_t now_ns = gp412::now_ns();
	const double   now_t  = GP412_NOW();
	std::lock_guard lk(mu());
	std::fprintf(file(), "W %.6f %.6f %" PRIx64 " %d\n", to_t(w_start_ns, now_ns, now_t), to_t(w_last_ns, now_ns, now_t), w_label, gp412::slot());
	w_start_ns = 0;
}
template <typename K> inline void handed(const K& kind, uint32_t dwords) {
	if (!on()) return;
	wait_flush();
	std::lock_guard lk(mu());
	std::fprintf(file(), "B %.6f %d %s %u\n", GP412_NOW(), gp412::slot(), ks(kind), dwords);
}
inline void chain_taken(uint64_t open_ns, int why) { // in chain_submit, with the chain's lock held
	if (!on()) return;
	t_open_ns  = open_ns;
	t_flush_ns = gp412::now_ns();
	t_why      = why;
}
inline void kernel_has_it() { // right after Device::submit returned
	if (!on()) return;
	t_kernel_ns = gp412::now_ns();
}
template <typename K> inline void submitted(uint64_t n, const K& kind, uint32_t dwords, size_t segs) {
	if (!on()) return;
	const uint64_t now_ns = gp412::now_ns();
	const double   now_t  = GP412_NOW();
	std::lock_guard lk(mu());
	std::fprintf(file(), "S %" PRIu64 " %.6f %.6f %.6f %d %s %u %zu %d\n", n, to_t(t_open_ns != 0 ? t_open_ns : t_flush_ns, now_ns, now_t), to_t(t_flush_ns, now_ns, now_t),
	             to_t(t_kernel_ns, now_ns, now_t), gp412::slot(), ks(kind), dwords, segs, t_why);
	t_open_ns = t_flush_ns = t_kernel_ns = 0;
	t_why = -1;
}
template <typename K> inline void done(uint64_t n, const K& kind, uint32_t dwords, bool ok) {
	if (!on()) return;
	std::lock_guard lk(mu());
	std::fprintf(file(), "D %" PRIu64 " %.6f %s %u %d\n", n, GP412_NOW(), ks(kind), dwords, ok ? 1 : 0);
}
inline void flip_mark(char c) {
	if (!on()) return;
	wait_flush();
	std::lock_guard lk(mu());
	std::fprintf(file(), "%c %.6f\n", c, GP412_NOW());
	if (c == 'F') std::fflush(file());
}
inline void label_sleep(int us, uint64_t label) {
	if (on()) {
		const uint64_t now = gp412::now_ns();
		if (w_start_ns != 0 && (w_label != label || now - w_last_ns > 2000000ull)) wait_flush();
		if (w_start_ns == 0) {
			w_start_ns = now;
			w_label    = label;
		}
	}
	gp412::poll_sleep(us, gp412::kLabel);
	if (on()) w_last_ns = gp412::now_ns();
}
} // namespace bf412
