#!/usr/bin/env python3
"""BC5 experiment 0438, for the build after build 10 (tag y438, records only, normal build): what direct_sync's scans
find. On the s438 unit.

Usage: mks438y.py IN.cpp OUT.cpp   (IN: mks438.py's output, md5 a5629394...)

The top session's question (from the maintainer): on the console the GPU sees memory from the map call on, with no
polling. If gameplay scans find ~0 new chunks, the design should be event-driven (import at the title's map/commit
call, and packet operands at submit as k1f412 does), not a slower poll.

Added to the s438 60-s line, split into load (journal time < 60 s) and play (the rest):
- per full pass kind: passes, chunks imported, MiB imported:
    forced  (S.forced grew: k1f412/ud434/hints' direct_force, or a forced sync),
    change  (st_blocks, the views' signature or the BO mapping changed, nothing new forced),
    merge   (a merge-only pass that scanned: every one with s438 off, the 1-s catch-up with it on);
- the layout generation's changes (the views' signature changed: g_layout_gen) and the guest's mapped-ranges
  generation changes seen by direct_sync_one (each one is at least one map, unmap or protect call).
Counters are written under g_dev_mutex only, as s438's.
"""
import hashlib
import sys

IN, OUT = sys.argv[1], sys.argv[2]
src = open(IN, 'rb').read()
assert hashlib.md5(src).hexdigest() == 'a56293942679688016778eef88c704c1', 'not s438.cpp (mks438 on u438)'
s = src.decode('utf-8')


def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, (n, old[:120])
    s = s.replace(old, new)


rep('''inline uint64_t g_last_scan_ns[2] = {0, 0}; // per DState kind: the last full scan
} // namespace s438''', '''inline uint64_t g_last_scan_ns[2] = {0, 0}; // per DState kind: the last full scan
// exp 0438 (tag y438): what the scans find. [phase 0 load (< 60 s) / 1 play][kind 0 forced / 1 change / 2 merge]
inline uint64_t y_passes[2][3] = {}, y_chunks[2][3] = {}, y_bytes[2][3] = {};
inline uint64_t y_layout[2] = {0, 0}, y_ranges[2] = {0, 0};
inline int phase() { return timing_now() < 60.0 ? 0 : 1; }
} // namespace s438''')

# the mapped-ranges generation's changes
rep('''	if (!force && now - S.sync_ns < 50'000'000ull && ranges_gen == S.ranges_gen) return;
	S.ranges_gen = ranges_gen;''', '''	if (!force && now - S.sync_ns < 50'000'000ull && ranges_gen == S.ranges_gen) return;
	if (ranges_gen != S.ranges_gen) s438::y_ranges[s438::phase()]++; // exp 0438 (tag y438)
	S.ranges_gen = ranges_gen;''')
rep('''	if (sig != S.views_sig) g_layout_gen++;''', '''	if (sig != S.views_sig) {
		g_layout_gen++;
		s438::y_layout[s438::phase()]++; // exp 0438 (tag y438)
	}''')

# the pass kind, decided before forced_seen is updated
rep('''		s438::g_full++;''', '''		s438::g_full++;
		y438_kind = S.forced.size() != S.forced_seen ? 0 : (s438_same ? 2 : 1); // exp 0438 (tag y438)''')
rep('''	bool       s438_merge_only = false; // exp 0438 (tag s438): this full pass is for the merge alone; step 1 left out''',
    '''	bool       s438_merge_only = false; // exp 0438 (tag s438): this full pass is for the merge alone; step 1 left out
	int        y438_kind       = 1;     // exp 0438 (tag y438): 0 forced, 1 change, 2 merge''')
rep('''	uint32_t imported = 0;
	if (!s438_merge_only) { // exp 0438 (tag s438): step 1 (the scan and the imports)''', '''	uint32_t imported = 0;
	if (!s438_merge_only) s438::y_passes[s438::phase()][y438_kind]++; // exp 0438 (tag y438): a pass that scans
	if (!s438_merge_only) { // exp 0438 (tag s438): step 1 (the scan and the imports)''')
rep('''			S.bytes += size;
			guard0412_imported(S.kind, fd, off, size);''', '''			S.bytes += size;
			s438::y_chunks[s438::phase()][y438_kind] += size / kDChunk; // exp 0438 (tag y438)
			s438::y_bytes[s438::phase()][y438_kind] += size;
			guard0412_imported(S.kind, fd, off, size);''')

# the line
rep('''		        static_cast<double>(s438::g_ns[1]) / 1e6, static_cast<double>(s438::g_ns[2]) / 1e6, static_cast<double>(s438::g_ns[3]) / 1e6, static_cast<double>(s438::g_ns[4]) / 1e6);
	}
#endif''', '''		        static_cast<double>(s438::g_ns[1]) / 1e6, static_cast<double>(s438::g_ns[2]) / 1e6, static_cast<double>(s438::g_ns[3]) / 1e6, static_cast<double>(s438::g_ns[4]) / 1e6);
		for (int ph = 0; ph < 2; ph++) { // exp 0438 (tag y438)
			const auto mib = [](uint64_t b) { return static_cast<double>(b) / 1048576.0; };
			journal("y438 (exp 0438): t %.1f s: %s: scanning passes / chunks imported / MiB: forced %" PRIu64 " / %" PRIu64 " / %.1f, change %" PRIu64 " / %" PRIu64 " / %.1f, merge %" PRIu64 " / %" PRIu64
			        " / %.1f; layout changes %" PRIu64 ", mapped-ranges generation changes %" PRIu64 "\\n",
			        timing_now(), ph == 0 ? "load (t < 60 s)" : "play (t >= 60 s)", s438::y_passes[ph][0], s438::y_chunks[ph][0], mib(s438::y_bytes[ph][0]), s438::y_passes[ph][1],
			        s438::y_chunks[ph][1], mib(s438::y_bytes[ph][1]), s438::y_passes[ph][2], s438::y_chunks[ph][2], mib(s438::y_bytes[ph][2]), s438::y_layout[ph], s438::y_ranges[ph]);
		}
	}
#endif''')

out = s.encode('utf-8')
open(OUT, 'wb').write(out)
print('y438 unit', hashlib.md5(out).hexdigest(), len(out))
