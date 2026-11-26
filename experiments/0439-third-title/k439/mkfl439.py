#!/usr/bin/env python3
# BC5 exp 0439 (tag fl439, 11-25 night, the top session's step 1: which flip-label wait is not honoured). Applied after
# mkvlon439.py and mkvt439.py. Normal build only for the catcher; the candidate fix is code for both builds.
#
# The paths that carry a flip-label wait (the title's WAIT_REG_MEM on a sceVideoOutGetBufferLabelAddress label, host
# memory, dropped from the GPU stream by the filter and served on the CPU before the submit):
#   T  top level of a command buffer (experiment 0069's rule, bc5LleAgc.cpp's wait handling): none logged for this
#      title in a 20-min Performance ride ("set by a queued flip" 0, "still set at the wait: cleared" 0);
#   C  a chained or called piece (vl439 b, on by default since vlon439): ~15,000 per ride.
# The flip: with BC5_DIRECT_FLIP_DEFER=1 (bc5-run.env) the title's flip increments g_flip_pending[buffer], is queued
# behind the frame's jobs, submitted once the GPU has finished them, and "bc5-flipdone" clears the label and decrements
# the count once the presenter has copied the buffer.
#
# The hole: the CPU-side serve waits while the flip is pending AND the label reads set. The label is set by frame N's
# last GPU write (RELEASE_MEM); when frame N+2's submit is checked before frame N's GPU work is done, the label still
# reads 0 and the wait passes at once, though the buffer's flip is still pending: frame N+2 renders into a buffer whose
# frame and flip are not done. On the console the GPU runs N+2's wait after N's RELEASE_MEM in ring order.
#   BC5_0439_FLIP_WAIT_PENDING=1 (candidate fix, off by default): a chained-piece flip-label wait waits while the
#     buffer's flip is pending, whatever the label reads (at most 100 ms, as before).
#   BC5_0439_FLIP_WAIT_MS=<ms> (default 100, the old bound): the wait's bound on the C path. WC measured 17 waits in 20 min
#     ended by the 100-ms bound with the flip still pending: the label is then cleared and the next frame renders into
#     a buffer still being flipped. On the console the wait has no bound.
#   BC5_0439_FL_CATCH=1 (diagnosis): a ring of the last 512 events (W: a wait with its buffer, pending count, label
#     satisfied at entry, ms waited, ended by the bound, label cleared; F: a flip queued; D: a flip copied and its label
#     cleared), the count of waits that passed with their buffer's flip pending, a journal line every 10 s, and the ring
#     written to <frame dump dir>/fl439-<t>.txt when the vt439 trigger counts 100 or more.
# Usage: python3 mkfl439.py <d2/new>
import os
import sys

p = os.path.join(sys.argv[1], 'bc5LleAgc.cpp')
s = open(p, 'rb').read().decode('utf-8', 'surrogateescape')
assert '(tag fl439)' not in s
crlf = '\r\n' in s
s = s.replace('\r\n', '\n')


def rep(a, b):
    global s
    assert s.count(a) == 1, (a[:80], s.count(a))
    s = s.replace(a, b)


rep('static std::atomic<int>  g_flip_pending[64];\n', r'''static std::atomic<int>  g_flip_pending[64];
// exp 0439 (tag fl439): the flip-label wait catcher and the candidate fix (see mkfl439.py)
struct Fl439Ev {
	double   t;
	char     kind;
	int      idx, pending;
	uint8_t  sat_entry, bounded, cleared;
	float    waited_ms;
};
static std::mutex          g_fl439_mu;
static Fl439Ev             g_fl439_ring[512];
static uint64_t            g_fl439_n = 0;
static std::atomic<uint64_t> g_fl439_waits {0}, g_fl439_hole {0}, g_fl439_bounded {0};
static double fl439_now() {
	return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
static bool fl439_catch() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_0439_FL_CATCH");
		return e != nullptr && e[0] == '1' && e[1] == 0;
	}();
	return v;
}
static uint64_t fl439_bound_ns() {
	static const uint64_t v = [] {
		const char* e = std::getenv("BC5_0439_FLIP_WAIT_MS");
		const uint64_t ms = e != nullptr && e[0] != 0 ? std::strtoull(e, nullptr, 10) : 100;
		std::fprintf(stderr, "[bc5] exp 0439 (tag fl439): BC5_0439_FLIP_WAIT_MS=%llu (the flip-label wait's bound)\n", static_cast<unsigned long long>(ms));
		return ms * 1'000'000ull;
	}();
	return v;
}
static bool fl439_fix() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_0439_FLIP_WAIT_PENDING");
		const bool  on = e != nullptr && e[0] == '1' && e[1] == 0;
		std::fprintf(stderr, "[bc5] exp 0439 (tag fl439): BC5_0439_FLIP_WAIT_PENDING=%d (1: a flip-label wait waits while its buffer's flip is pending)\n", on ? 1 : 0);
		return on;
	}();
	return v;
}
static void fl439_note(char kind, int idx, int pending, bool sat, float waited, bool bounded, bool cleared) {
	if (!fl439_catch()) return;
	std::lock_guard lk(g_fl439_mu);
	g_fl439_ring[g_fl439_n++ % 512] = {fl439_now(), kind, idx, pending, static_cast<uint8_t>(sat), static_cast<uint8_t>(bounded), static_cast<uint8_t>(cleared), waited};
}
static void fl439_dump(const char* path) {
	if (!fl439_catch()) return;
	FILE* f = std::fopen(path, "w");
	if (f == nullptr) return;
	std::lock_guard lk(g_fl439_mu);
	std::fprintf(f, "# fl439: the last %d events before the trigger; waits %llu, passed with the flip pending %llu, ended by the bound %llu\n# t kind buffer pending sat_at_entry waited_ms bounded cleared\n",
	             static_cast<int>(std::min<uint64_t>(g_fl439_n, 512)), static_cast<unsigned long long>(g_fl439_waits.load()), static_cast<unsigned long long>(g_fl439_hole.load()),
	             static_cast<unsigned long long>(g_fl439_bounded.load()));
	const uint64_t first = g_fl439_n > 512 ? g_fl439_n - 512 : 0;
	for (uint64_t i = first; i < g_fl439_n; i++) {
		const auto& e = g_fl439_ring[i % 512];
		std::fprintf(f, "%.4f %c %d %d %d %.3f %d %d\n", e.t, e.kind, e.idx, e.pending, e.sat_entry, e.waited_ms, e.bounded, e.cleared);
	}
	std::fclose(f);
}
''')

rep('''						const size_t   idx = static_cast<size_t>((label - l0) / sizeof(uint64_t));
						const uint64_t tw  = SoftCp::now_ns();
						while (g_flip_pending[idx].load() > 0 && !wait_satisfied(p, is64) && SoftCp::now_ns() - tw < 100'000'000ull)
							std::this_thread::sleep_for(std::chrono::microseconds(50));
						const bool still = !wait_satisfied(p, is64);
						if (still) *reinterpret_cast<volatile uint64_t*>(label & ~7ull) = 0;
''', '''						const size_t   idx = static_cast<size_t>((label - l0) / sizeof(uint64_t));
						const uint64_t tw  = SoftCp::now_ns();
						const int      pend0 = g_flip_pending[idx].load(); // exp 0439 (tag fl439)
						const bool     sat0  = wait_satisfied(p, is64);
						const bool     fwfix = fl439_fix();
						const uint64_t fl_bound = fl439_bound_ns();
						while (g_flip_pending[idx].load() > 0 && (fwfix || !wait_satisfied(p, is64)) && SoftCp::now_ns() - tw < fl_bound)
							std::this_thread::sleep_for(std::chrono::microseconds(50));
						const bool still = !wait_satisfied(p, is64);
						const bool bnd   = SoftCp::now_ns() - tw >= fl_bound;
						if (still) *reinterpret_cast<volatile uint64_t*>(label & ~7ull) = 0;
						g_fl439_waits++;
						if (pend0 > 0 && sat0) g_fl439_hole++;
						if (bnd) g_fl439_bounded++;
						fl439_note('W', static_cast<int>(idx), pend0, sat0, static_cast<float>(SoftCp::now_ns() - tw) / 1e6f, bnd, still);
#ifndef BC5_LEAN
						if (fl439_catch()) {
							static uint64_t fw_last = 0;
							const uint64_t  fw_now  = SoftCp::now_ns();
							if (fw_now - fw_last >= 10'000'000'000ull) {
								fw_last = fw_now;
								journal("fl439: t %.0f s: flip-label waits %" PRIu64 ", passed with the buffer's flip pending %" PRIu64 ", ended by the 100-ms bound %" PRIu64 " (fix %s)\\n", timing_now(),
								        g_fl439_waits.load(), g_fl439_hole.load(), g_fl439_bounded.load(), fwfix ? "on" : "off");
							}
						}
#endif
''')

rep('''			Bc5Gc::g_flip_pending[index]++; // experiment 0069
''', '''			Bc5Gc::g_flip_pending[index]++; // experiment 0069
			Bc5Gc::fl439_note('F', index, Bc5Gc::g_flip_pending[index].load(), false, 0.0f, false, false); // exp 0439 (tag fl439)
''')
rep('''							Bc5Gc::g_labels[it.second] = 0;
							Bc5Gc::g_flip_pending[it.second]--;
''', '''							Bc5Gc::g_labels[it.second] = 0;
							Bc5Gc::g_flip_pending[it.second]--;
							Bc5Gc::fl439_note('D', it.second, Bc5Gc::g_flip_pending[it.second].load(), false, 0.0f, false, false); // exp 0439 (tag fl439)
''')
a = '(trigger %d): the display surface %s %s\\n", t, v, vt_n, ok ? "written to" : "NOT written to", path);\n'
rep(a, a + '''				if (v >= 100) { // exp 0439 (tag fl439): the flip-label wait ring beside the surface
					std::string fwp = std::string(path) + ".fl439.txt";
					fl439_dump(fwp.c_str());
					std::fprintf(stderr, "[bc5] exp 0439 (tag fl439): the last flip-label waits written to %s\\n", fwp.c_str());
				}
''')
if crlf:
    s = s.replace('\n', '\r\n')
open(p, 'wb').write(s.encode('utf-8', 'surrogateescape'))
print('mkfl439: patched', p)
