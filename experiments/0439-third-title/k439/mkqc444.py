#!/usr/bin/env python3
# BC5 exp 0444 (tag qc444): how many guest compute queues are busy at once, the number behind "would 7 pinned rings be
# enough". Normal build only (compiled out of lean); a diagnosis counter, not a fix.
#   busy queue: a guest queue (the bc5-ring consumer's t_queue_idx) with at least one acb part submitted and not yet done
#   (a pending job: async submission, the journal at "min", as in play; a sync job is never in flight between calls)
#   per flip: the maximum number of busy queues since the previous flip, into a histogram 0..15, 16+
#   stderr every 600 flips, and the overall maximum:
#     "[bc5] exp 0444 (qc444): busy guest compute queues per frame (max between flips) over N frames: 0:a 1:b ...; max M
#      (queues seen Q)"
# Hooks: after ho430::job_submitted in submit_now's pending path (seq, ring, kind; t_queue_idx is the submitting
# bc5-ring thread's queue), in forget_label_writes (completion; all = the ring's jobs cleared), and at the start of the
# normal build's frame_profile_flip (every flip, before its own on/off test).
# Usage: python mkqc444.py IN.cpp OUT.cpp (every anchor exactly once; checked on the shared unit ed489aca)
import hashlib, sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, 'rb').read().decode('utf-8', 'surrogateescape')
assert '\r' not in s and 'qc444' not in s
T = '\t'


def rep(tag, old, new):
    global s
    n = s.count(old)
    assert n == 1, '%s: anchor found %d times' % (tag, n)
    s = s.replace(old, new)


body = r'''#ifndef BC5_LEAN
// exp 0444 (tag qc444): busy guest compute queues at once (mkqc444.py).
namespace qc444 {
static std::mutex                                   g_m;
static std::map<std::pair<int, uint64_t>, int>       g_job_q;  // (ring, seq) -> guest queue
static std::map<int, int>                           g_inflight; // guest queue -> its parts in flight
static std::set<int>                                g_seen;
static int                                          g_busy = 0, g_frame_max = 0, g_max = 0;
static uint64_t                                     g_hist[17] = {}, g_frames = 0;
inline void submitted(uint64_t seq, int ring, const char* kind, int q) {
	if (kind == nullptr || std::strncmp(kind, "acb", 3) != 0 || q < 0) return;
	std::lock_guard lk(g_m);
	g_job_q[{ring, seq}] = q;
	g_seen.insert(q);
	if (g_inflight[q]++ == 0) g_busy++;
	if (g_busy > g_frame_max) g_frame_max = g_busy;
}
inline void drop_locked(std::map<std::pair<int, uint64_t>, int>::iterator it) {
	auto f = g_inflight.find(it->second);
	if (f != g_inflight.end() && --f->second == 0) g_busy--;
	g_job_q.erase(it);
}
inline void done(uint64_t seq, int ring, bool all) {
	std::lock_guard lk(g_m);
	if (all) { // as forget_label_writes: the whole table (a timed-out job's ring reset)
		(void)ring;
		g_job_q.clear();
		g_inflight.clear();
		g_busy = 0;
		return;
	}
	auto it = g_job_q.find({ring, seq});
	if (it != g_job_q.end()) drop_locked(it);
}
inline void flip() {
	std::lock_guard lk(g_m);
	g_hist[g_frame_max < 16 ? g_frame_max : 16]++;
	if (g_frame_max > g_max) g_max = g_frame_max;
	g_frame_max = g_busy;
	if (++g_frames % 600 != 0) return;
	char line[512];
	int  o = std::snprintf(line, sizeof(line), "[bc5] exp 0444 (qc444): busy guest compute queues per frame (max between flips) over %" PRIu64 " frames:", g_frames);
	for (int k = 0; k <= 16 && o > 0 && o < static_cast<int>(sizeof(line)); k++)
		if (g_hist[k] != 0) o += std::snprintf(line + o, sizeof(line) - o, " %d%s:%" PRIu64, k, k == 16 ? "+" : "", g_hist[k]);
	std::fprintf(stderr, "%s; max %d (queues seen %zu)\n", line, g_max, g_seen.size());
}
} // namespace qc444
#endif
'''
rep('qc0', 'static void forget_label_writes(uint64_t seq, int ring, bool all) {\n',
    body + 'static void forget_label_writes(uint64_t seq, int ring, bool all) {\n')
rep('qc1', 'static void forget_label_writes(uint64_t seq, int ring, bool all) {\n' + T + 'std::lock_guard lk(g_plw_mutex);\n',
    'static void forget_label_writes(uint64_t seq, int ring, bool all) {\n'
    '#ifndef BC5_LEAN\n' + T + 'qc444::done(seq, ring, all); // exp 0444 (qc444)\n#endif\n' + T + 'std::lock_guard lk(g_plw_mutex);\n')
rep('qc2', T + T + 'ho430::job_submitted(ib, num_dwords, r.executed_offsets, r.seq_no, r.ring, kind); // exp 0430 (tag ho430)\n',
    T + T + 'ho430::job_submitted(ib, num_dwords, r.executed_offsets, r.seq_no, r.ring, kind); // exp 0430 (tag ho430)\n'
    '#ifndef BC5_LEAN\n' + T + T + 'qc444::submitted(r.seq_no, r.ring, kind, t_queue_idx); // exp 0444 (qc444)\n#endif\n')
rep('qc3', 'static void frame_profile_flip(double drain_ms) {\n' + T + 'if (!g_frame_profile_on()) return;\n',
    'static void frame_profile_flip(double drain_ms) {\n'
    '#ifndef BC5_LEAN\n' + T + 'qc444::flip(); // exp 0444 (qc444): every flip, before the profile\'s own test\n#endif\n' +
    T + 'if (!g_frame_profile_on()) return;\n')
for h in ('#include <set>', '#include <map>'):
    if h not in s:
        rep('inc', '#include "bc5/direct.hpp"\n', h + ' // exp 0444 (qc444)\n#include "bc5/direct.hpp"\n')
b = s.encode('utf-8', 'surrogateescape')
open(dst, 'wb').write(b)
print('mkqc444: wrote', dst, hashlib.md5(b).hexdigest()[:8], 'from', hashlib.md5(open(src, 'rb').read()).hexdigest()[:8])
