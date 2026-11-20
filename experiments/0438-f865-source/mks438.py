#!/usr/bin/env python3
"""BC5 experiment 0438, build 10: s438 (direct_sync's scan left out on a merge-only pass) and i438 (records only: the
in-buffers of /dev/gc 0xc0088133 and 0xc0108139). On the u438 unit.

Usage: mks438.py IN.cpp OUT.cpp   (IN: mku438.py's output, md5 78f319da...)

Switches:
  BC5_0438_MERGESCAN  s438, behaviour (so in lean too), on unless "0".
  i438                records only, normal build only (#ifndef BC5_LEAN), no switch: it changes nothing the title sees.

s438. direct_sync_one (under g_dev_mutex) has a fast path: nothing new in the memfd (st_blocks), no new view (the
views' signature), nothing forced, every BO mapped -> return. That path is not taken when the merge is due
(every 250 ms per DState, `merge_due`), so every 250 ms a full pass runs: step 1, the scan of every view for data
chunks not yet imported (a binary search on S.bos per view gap, an lseek(SEEK_DATA) on the memfd per uncovered gap),
then the merge, the lzr pass, and the mapping rebuild only if something changed.
When the merge is the only reason for the full pass, step 1 finds what the fast path's own rule says is not there
(the same blocks, views and forced set). With s438 on, such a pass skips step 1 unless the last full scan of that
DState is 1 s old or more; the merge and everything after it run as before.

What step 1 touches, and the lock (unchanged by s438: it only runs it less often):
| what | lock |
| S.bos, S.forced, S.failed, S.file_size (read), S.bos/S.bytes (import, write) | g_dev_mutex |
| the memfd (lseek SEEK_DATA, read only) | none needed (kernel) |
| g_zskip, zskip_take_back (CPU writes / canaries take skipped chunks back) | g_dev_mutex |
| ls415_import (a udmabuf/dma-buf import: ioctls) | g_dev_mutex |
s438 is off (the scan runs) whenever g_zskip is not empty or zskip_sync_start placed a new zero list, so the zskip
take-back is never left out.

What s438 gives up: a data chunk that appears with st_blocks unchanged (one page freed and one written in the same
window) is found at the next full scan, up to 1 s later instead of up to 250 ms. A packet operand on it is still
imported by k1f412 (S.forced grows, so the next sync is not merge-only).

Records (normal build): an `s438` journal line every 60 s from direct_sync (under g_dev_mutex): passes fast / full,
merge-only passes with the scan skipped / run, and the full passes' time by part (views, scan, merge, drain, maps).

i438 (step 3's follow-up, the top session's order): in gc_ioctl's default case, for 0xc0088133 and 0xc0108139 only,
the in-buffer (the request's _IOC size, 8 or 16 bytes; the first 64 bytes asked for are capped at that size, since
reading past it can fault) before the zero-fill, and the out-buffer after it (what the host returns: zeros), as
journal lines; the first 200 calls of each request, then 1 in 600. No change to what is returned.
"""
import hashlib
import sys

IN, OUT = sys.argv[1], sys.argv[2]
src = open(IN, 'rb').read()
assert hashlib.md5(src).hexdigest() == '78f319da0beee7c0bbb7f6b582470a2e', 'not u438.cpp (mku438 on r438d)'
s = src.decode('utf-8')


def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, (n, old[:120])
    s = s.replace(old, new)


# s438 1: the switch and counters, before direct_sync_one
rep('''static void direct_sync_one(DState& S, bool force) {
	if (!g_dev) return;''', '''// BC5 experiment 0438 (tag s438): direct_sync's scan left out on a merge-only pass (BC5_0438_MERGESCAN, on unless "0").
// The counters are written under g_dev_mutex only (direct_sync_one and direct_sync run under it).
namespace s438 {
inline bool on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_0438_MERGESCAN");
		return !(e != nullptr && e[0] == '0' && e[1] == 0);
	}();
	return v;
}
inline uint64_t g_fast = 0, g_full = 0, g_mo_skipped = 0, g_mo_scanned = 0;
inline uint64_t g_ns[5] = {0, 0, 0, 0, 0}; // full passes: views, scan, merge, drain, maps
inline uint64_t g_last_scan_ns[2] = {0, 0}; // per DState kind: the last full scan
} // namespace s438
static void direct_sync_one(DState& S, bool force) {
	if (!g_dev) return;''')

# s438 2: decide merge-only at the fast-path test
rep('''		const bool merge_due = now - S.merge_ns > 250'000'000ull;
		if (blocks != ~0ull && blocks == S.blocks && sig == S.views_sig && S.forced.size() == S.forced_seen && S.bos.size() == S.bos_mapped && !merge_due) {
			g_dprof_fast++;
			return; // nothing new in the file, no new view, nothing forced, nothing to merge yet
		}''', '''		const bool merge_due = now - S.merge_ns > 250'000'000ull;
		const bool s438_same = blocks != ~0ull && blocks == S.blocks && sig == S.views_sig && S.forced.size() == S.forced_seen && S.bos.size() == S.bos_mapped; // exp 0438 (tag s438)
		if (s438_same && !merge_due) {
			g_dprof_fast++;
			s438::g_fast++;
			return; // nothing new in the file, no new view, nothing forced, nothing to merge yet
		}
		s438::g_full++;
		s438::g_ns[0] += SoftCp::now_ns() - now;
		const int s438_k = S.kind == 0 ? 0 : 1;
		s438_merge_only  = s438::on() && s438_same && merge_due && !zskip_new && g_zskip.empty() && now - s438::g_last_scan_ns[s438_k] < 1'000'000'000ull;
		if (s438_same && merge_due) (s438_merge_only ? s438::g_mo_skipped : s438::g_mo_scanned)++;
		if (!s438_merge_only) s438::g_last_scan_ns[s438_k] = now;''')
rep('''	const bool zskip_new = zskip_sync_start(S, views); // experiment 0379 (exp 0401 e7): place the zero list; a canary hit forces a full sync
	{''', '''	const bool zskip_new = zskip_sync_start(S, views); // experiment 0379 (exp 0401 e7): place the zero list; a canary hit forces a full sync
	bool       s438_merge_only = false; // exp 0438 (tag s438): this full pass is for the merge alone; step 1 left out
	{''')

# s438 3: step 1 under the condition
rep('''	zskip_take_back(S, fd); // experiment 0379: CPU writes''', '''	uint32_t imported = 0;
	if (!s438_merge_only) { // exp 0438 (tag s438): step 1 (the scan and the imports)
	zskip_take_back(S, fd); // experiment 0379: CPU writes''')
rep('''	uint32_t imported = 0;
	for (size_t i = 0; i < need.size();) {''', '''	for (size_t i = 0; i < need.size();) {''')
rep('''		i = j;
	}

	// 1b. Memory''', '''		i = j;
	}
	} // exp 0438 (tag s438): step 1 ends

	// 1b. Memory''')

# s438 4: time by part (the existing stamps)
rep('''	g_dprof_scan_ns += t_merge0 - t_scan0;''', '''	g_dprof_scan_ns += t_merge0 - t_scan0;
	s438::g_ns[1] += t_merge0 - t_scan0; // exp 0438 (tag s438)''')
rep('''	g_dprof_merge_ns += t_drain0 - t_merge0;''', '''	g_dprof_merge_ns += t_drain0 - t_merge0;
	s438::g_ns[2] += t_drain0 - t_merge0; // exp 0438 (tag s438)''')
rep('''	g_dprof_drain_ns += t_maps0 - t_drain0;''', '''	g_dprof_drain_ns += t_maps0 - t_drain0;
	s438::g_ns[3] += t_maps0 - t_drain0; // exp 0438 (tag s438)''')
rep('''	g_dprof_maps_ns += SoftCp::now_ns() - t_maps0; // experiment 0169''', '''	g_dprof_maps_ns += SoftCp::now_ns() - t_maps0; // experiment 0169
	s438::g_ns[4] += SoftCp::now_ns() - t_maps0; // exp 0438 (tag s438)''')

# s438 5: the 60-s line
rep('''static void direct_sync(bool force) {
	bc5::load_stat::Scope ls_scope(bc5::load_stat::kDirectSync); // experiment 0415 (ls415)
	for (auto& S: g_d) direct_sync_one(S, force);''', '''static void direct_sync(bool force) {
	bc5::load_stat::Scope ls_scope(bc5::load_stat::kDirectSync); // experiment 0415 (ls415)
	for (auto& S: g_d) direct_sync_one(S, force);
#ifndef BC5_LEAN
	static double s438_last = 0; // exp 0438 (tag s438): under g_dev_mutex
	if (timing_now() - s438_last >= 60.0) {
		s438_last = timing_now();
		journal("s438 (exp 0438): t %.1f s: merge scan %s; direct syncs fast %" PRIu64 ", full %" PRIu64 "; merge-only passes with the scan left out %" PRIu64 ", scanned %" PRIu64
		        "; full passes' time (ms): views %.1f, scan %.1f, merge %.1f, drain %.1f, maps %.1f\\n",
		        timing_now(), s438::on() ? "ON" : "off", s438::g_fast, s438::g_full, s438::g_mo_skipped, s438::g_mo_scanned, static_cast<double>(s438::g_ns[0]) / 1e6,
		        static_cast<double>(s438::g_ns[1]) / 1e6, static_cast<double>(s438::g_ns[2]) / 1e6, static_cast<double>(s438::g_ns[3]) / 1e6, static_cast<double>(s438::g_ns[4]) / 1e6);
	}
#endif''')

# i438: the two unknown requests' buffers
rep('''			if (out && argp != nullptr && size != 0) {
				std::memset(argp, 0, size);
			}
			return 0;''', '''#ifndef BC5_LEAN
			// exp 0438 (tag i438): records only. The in-buffer of 0xc0088133 / 0xc0108139 before the zero-fill, the out-buffer
			// after it; the first 200 calls of each, then 1 in 600; at most the _IOC size (8 / 16 bytes) is read.
			const bool i438_req = request == 0xc0088133u || request == 0xc0108139u;
			static std::atomic<uint64_t> i438_n[2] = {0, 0};
			const uint64_t i438_i = i438_req ? i438_n[request == 0xc0088133u ? 0 : 1]++ : 0;
			const bool i438_log = i438_req && argp != nullptr && size != 0 && (i438_i < 200 || i438_i % 600 == 0);
			char i438_in[3 * 64 + 1] = {0};
			const uint32_t i438_sz = size < 64 ? size : 64;
			if (i438_log) {
				const auto* b = static_cast<const uint8_t*>(argp);
				for (uint32_t k = 0; k < i438_sz; k++) std::snprintf(i438_in + 3 * k, 4, "%02x ", b[k]);
			}
#endif
			if (out && argp != nullptr && size != 0) {
				std::memset(argp, 0, size);
			}
#ifndef BC5_LEAN
			if (i438_log) {
				char i438_out[3 * 64 + 1] = {0};
				const auto* b = static_cast<const uint8_t*>(argp);
				for (uint32_t k = 0; k < i438_sz; k++) std::snprintf(i438_out + 3 * k, 4, "%02x ", b[k]);
				char tn[16] = {0};
				pthread_getname_np(pthread_self(), tn, sizeof(tn));
				Direct::journal("i438 (exp 0438): t %.3f s: gc ioctl 0x%08" PRIx64 " call %" PRIu64 " on %s: size %u; in [%s] out [%s]\\n", Direct::timing_now(), request, i438_i, tn, size, i438_in,
				        i438_out);
			}
#endif
			return 0;''')

out = s.encode('utf-8')
open(OUT, 'wb').write(out)
print('s438 unit', hashlib.md5(out).hexdigest(), len(out))
