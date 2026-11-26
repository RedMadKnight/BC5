#!/usr/bin/env python3
"""BC5 experiment 0412, tag zs412 (README section 48): BC5_GUARD_ZSKIP_SCAN=1|2, the zero skip takes memory back before
the GPU can write it. Input: the main unit after mkzpoll0412.py (g412v's, 3cea62bc).
  - zscan0412.inc (the text zscan0412.cpp tests) and the glue zscan412_submit() go in before nscan412_submit();
  - submit_now() calls zscan412_submit() before zpoll412_submit(), i.e. before it takes the mapping list for the
    filter, so that what comes back here is pinned and mapped in the canary's place before this buffer goes out.
BC5_GUARD_ZSKIP_SCAN unset: zscan412_submit() returns after one test.
Each anchor occurs exactly once; the script undoes its edits and asserts that this gives the input back.
usage: mkzscan0412.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
T = b" // exp 0412 (tag zs412)\n"

GLUE = b'''// Experiment 0412 (tag zs412): BC5_GUARD_ZSKIP_SCAN. Every submitted buffer and the tables it points to are searched
// for addresses under the zero skip's canary; that memory comes back before the buffer goes out. Under the device mutex.
static void zscan412_submit(const uint32_t* ib, uint32_t num_dwords, const char* kind) {
	const int mode = zs412::mode();
	if (mode == 0 || g_zpieces.empty() || ib == nullptr) return;
	static std::vector<ns412::Range> ranges;
	static std::vector<ns412::Hit>   hits;
	static std::vector<uint64_t>     others, from;
	static std::vector<uint32_t>     runs;
	static std::vector<uint32_t>     tab(ns412::kTable / 4);
	static uint64_t                  bufs = 0, bufs_hit = 0, finds_direct = 0, finds_table = 0, back_bytes = 0, back_times = 0, incomplete = 0, spent_ns = 0, tables = 0, lines = 0, last_ns = 0;
	const uint64_t                   t0 = SoftCp::now_ns();
	DState&                          S  = g_d[0];
	zs412::ranges(g_zpieces, ranges);
	hits.clear();
	others.clear();
	const auto     views_p = direct_views(S);
	const auto&    views   = views_p->v;
	const bool     follow  = views_p->sorted && !views.empty();
	const uint64_t win_lo = follow ? views.front().va : 0, win_hi = follow ? views.back().va + views.back().size : 0;
	// Capacity (review R25): 4096 hits and 1024 table candidates per buffer; a search that still overflows, or a table that
	// cannot be read in full, is INCOMPLETE and every run under the canary comes back before this submission, in both modes.
	bool complete = ns412::scan(ib, num_dwords, ranges, hits, 4096, follow ? &others : nullptr, win_lo, win_hi, 1024);
	from.assign(hits.size(), 0);
	const size_t direct = hits.size();
	const int    fd     = dstate_fd(S);
	for (const uint64_t a0: others) {
		if (fd < 0) { complete = false; break; }
		const uint64_t a  = a0 & ~3ull;
		const auto     it = std::partition_point(views.begin(), views.end(), [a](const DView& v) { return v.va + v.size <= a; });
		if (it == views.end() || a < it->va) continue;
		uint64_t bytes = it->va + it->size - a;
		if (bytes > ns412::kTable) bytes = ns412::kTable;
		const ssize_t got = pread(fd, tab.data(), bytes & ~3ull, static_cast<off_t>(it->off + (a - it->va)));
		if (got < 0 || static_cast<uint64_t>(got) != (bytes & ~3ull)) complete = false;
		if (got < 8) continue;
		tables++;
		complete = ns412::scan(tab.data(), static_cast<uint32_t>(got / 4), ranges, hits, 8192, nullptr, 0, 0) && complete;
		from.resize(hits.size(), a);
	}
	bufs++;
	if (!complete) incomplete++;
	if (!hits.empty() || !complete) {
		bufs_hit++;
		finds_direct += direct;
		finds_table += hits.size() - direct;
		uint64_t back = 0;
		if (mode == 1 || !complete) {
			if (complete) {
				zs412::runs_of(hits, ranges, runs);
			} else {
				zs412::all_runs(ranges, runs);
				journal("zero skip scan (exp 0412, tag zs412): t %.3f s: INCOMPLETE search of %s %u dwords (%zu hits, %zu candidates): all %zu runs under the canary come back\\n", timing_now(), kind, num_dwords, hits.size(), others.size(), runs.size());
			}
			for (const uint32_t r: runs) {
				if (r >= g_zleft.size() || g_zleft[r] == 0) continue;
				back += g_zskip.erase_run(r);
				g_zleft[r] = 0;
			}
			if (back != 0) {
				S.blocks = ~0ull; // a full sync: pin what came back and map it in the canary's place, before this buffer goes out
				direct_sync_one(S, true);
			}
		} else {
			// ranges is this function's copy: direct_force changes g_zpieces, not it.
			for (const auto& h: hits) back += direct_force(h.addr, zs412::window_hi(ranges, h.range, h.addr, zs412::kWindow));
		}
		if (back != 0) {
			back_bytes += back;
			back_times++;
		}
		for (size_t i = 0; i < hits.size() && back != 0; i++) {
			const uint64_t n = lines++;
			if (n >= 120 && (n & 255u) != 0) continue;
			const auto& h = hits[i];
			char        through[64] = "";
			if (from[i] != 0) std::snprintf(through, sizeof(through), ", through the table at 0x%" PRIx64, from[i]);
			journal("zero skip scan (exp 0412, tag zs412): t %.3f s: %s %u dwords before submission %" PRIu64 ": dword %u names 0x%" PRIx64 " (%s)%s in run %u; %.1f MiB taken back for this buffer\\n",
			        timing_now(), kind, num_dwords, g_submits.load(), h.at, h.addr, h.form == 0 ? "pair" : "shifted by 8", through, ranges[h.range].name, static_cast<double>(back) / 1048576.0);
		}
	}
	const uint64_t t1 = SoftCp::now_ns();
	spent_ns += t1 - t0;
	if (t1 - last_ns >= 10'000'000'000ull) {
		last_ns = t1;
		journal("zero skip scan (exp 0412, tag zs412): t %.0f s: mode %d: %" PRIu64 " buffers searched, %" PRIu64 " with a find (%" PRIu64 " in the buffer, %" PRIu64 " through a table; %" PRIu64 " tables read; %" PRIu64 " searches incomplete); %.1f MiB taken back at %" PRIu64 " submissions; %.1f MiB still skipped; canary hits %" PRIu64 "; %.1f ms spent in all\\n",
		        timing_now(), mode, bufs, bufs_hit, finds_direct, finds_table, tables, incomplete, static_cast<double>(back_bytes) / 1048576.0, back_times, static_cast<double>(g_zskip.bytes()) / 1048576.0, g_zstat_hits,
		        static_cast<double>(spent_ns) / 1e6);
	}
}
'''


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    s = open(sys.argv[1], "rb").read()
    inc = open(os.path.join(HERE, "zscan0412.inc"), "rb").read()
    assert b"tag zp412" in s and b"tag ns412" in s and b"tag zs412" not in s, "refused: not the expected input"
    assert b"\r" not in s and b"\r" not in inc
    inc.decode("ascii")
    GLUE.decode("ascii")
    edits = []
    a = b"static void nscan412_submit(const uint32_t* ib, uint32_t num_dwords, const char* kind) {\n"
    edits.append((a, inc + GLUE + a))
    a = b"\tzpoll412_submit(); // exp 0412 (tag zp412)\n"
    edits.append((a, b"\tzscan412_submit(ib, num_dwords, kind);" + T + a))
    out = s
    for old, new in edits:
        assert out.count(old) == 1, ("an anchor does not occur exactly once", old[:60], out.count(old))
        out = out.replace(old, new)
    back = out
    for old, new in reversed(edits):
        assert back.count(new) == 1, ("undo", new[:60], back.count(new))
        back = back.replace(new, old)
    assert back == s, "undoing the edits does not give the input back"
    g = out.index(b"static void zscan412_submit(const uint32_t* ib, uint32_t num_dwords, const char* kind) {")
    for need in (b"static uint64_t direct_force(uint64_t lo, uint64_t hi) {", b"namespace ns412", b"static void direct_sync_one(DState& S, bool force) {", b"static int dstate_fd(const DState& S) {",
                 b"static std::map<uint64_t, ZPiece>               g_zpieces;", b"static std::vector<uint64_t>                    g_zleft;", b"static uint64_t g_zstat_cpu = 0"):
        assert out.index(need) < g, ("must be defined before the glue", need[:40])
    assert b"g_submits" in out[:g], "g_submits is not declared before the glue"
    call = out.index(b"\tzscan412_submit(ib, num_dwords, kind);")
    sn = out.index(b"static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, int ring, const Chain* chain) {")
    assert sn < call < out.index(b"\tzpoll412_submit(); // exp 0412 (tag zp412)\n", sn) < out.index(b"std::shared_ptr<const std::vector<bc5::direct::Mapping>> maps_p = g_dev->sorted_mappings();", sn), "the call is not before the poll and submit_now's mapping list"
    open(sys.argv[2], "wb").write(out)
    print(f"bc5LleAgc.cpp {hashlib.md5(out).hexdigest()}")


if __name__ == "__main__":
    main()
