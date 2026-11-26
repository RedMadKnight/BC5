#!/usr/bin/env python3
"""BC5 experiment 0412, tag ns412 (README section 39): the search of submitted command buffers for addresses in the
memory BC5_GUARD_NOGPU_UNPIN left unpinned, and the pin before the submission (BC5_GUARD_NOGPU_SCAN=1|2).
Input: the main unit after mknogpu0412.py.
  - nscan0412.inc (the text nscan0412.cpp tests) goes in before nogpu0412.inc's block;
  - the glue goes in before nogpu412_apply(): the ranges of the left-out memory (rebuilt by nogpu412_apply, journaled
    per heap when the left-out set changes, also with the scan off: the line is what an offline check of a dumped
    buffer needs), and nscan412_submit();
  - nogpu412_apply() rebuilds the ranges;
  - submit_now() calls nscan412_submit() before it takes the mapping list for the filter, so that a pin made here is
    in that list.
BC5_GUARD_NOGPU_SCAN unset: nscan412_submit() returns after one test.
Each anchor occurs exactly once; the script undoes its edits and asserts that this gives the input back.
usage: mknscan0412.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
T = b" // exp 0412 (tag ns412)\n"

GLUE = b'''
// Experiment 0412 (tag ns412): BC5_GUARD_NOGPU_SCAN. The guest address ranges BC5_GUARD_NOGPU_UNPIN left unpinned, and
// the search of every submitted buffer (and of the tables it points to) for addresses in them. All of it runs under
// the device mutex (the direct sync and submit_now).
static std::vector<ns412::Range> g_ns412_ranges;
static std::vector<std::string>  g_ns412_names;
static void nscan412_ranges(const std::vector<DView>& views, bool changed) {
	g_ns412_ranges = ns412::ranges(views, g_g412_off, kDChunk, g_ns412_names);
	static uint64_t lines = 0;
	if (!changed) return;
	const uint64_t n = lines++;
	if (n >= 12 && (n & 63u) != 0) return;
	std::string text;
	for (uint32_t k = 0; k < g_ns412_names.size(); k++) {
		uint64_t bytes = 0, lo = ~0ull, hi = 0, cnt = 0;
		for (const auto& r: g_ns412_ranges) {
			if (r.name != k) continue;
			bytes += r.hi - r.lo;
			cnt++;
			if (r.lo < lo) lo = r.lo;
			if (r.hi > hi) hi = r.hi;
		}
		char b[200];
		std::snprintf(b, sizeof(b), "%s %s %.1f MiB in %" PRIu64 " ranges within 0x%" PRIx64 "..0x%" PRIx64, k == 0 ? "" : ";", g_ns412_names[k].c_str(), static_cast<double>(bytes) / 1048576.0, cnt, lo, hi);
		text += b;
	}
	journal("guard nogpu ranges (exp 0412, tag ns412): t %.0f s: scan mode %d;%s\\n", timing_now(), ns412::mode(), text.c_str());
	if (n < 3) {
		size_t shown = 0;
		for (const auto& r: g_ns412_ranges) {
			if (r.hi - r.lo < (8ull << 20) || shown++ >= 40) continue;
			journal("guard nogpu ranges (exp 0412, tag ns412):   0x%" PRIx64 "..0x%" PRIx64 " %s\\n", r.lo, r.hi, g_ns412_names[r.name].c_str());
		}
	}
}
static void nscan412_submit(const uint32_t* ib, uint32_t num_dwords, const char* kind) {
	const int mode = ns412::mode();
	if (mode == 0 || g_ns412_ranges.empty() || ib == nullptr) return;
	static std::vector<ns412::Hit> hits;
	static std::vector<uint64_t>   others, from;
	static std::vector<uint32_t>   tab(ns412::kTable / 4);
	static uint64_t                bufs = 0, bufs_hit = 0, finds_direct = 0, finds_table = 0, pinned = 0, spent_ns = 0, tables = 0, lines = 0, last_ns = 0, last_finds = 0;
	const uint64_t                 t0 = SoftCp::now_ns();
	hits.clear();
	others.clear();
	from.clear();
	DState&        S       = g_d[0];
	const auto     views_p = direct_views(S);
	const auto&    views   = views_p->v;
	const bool     follow  = views_p->sorted && !views.empty();
	const uint64_t win_lo = follow ? views.front().va : 0, win_hi = follow ? views.back().va + views.back().size : 0;
	ns412::scan(ib, num_dwords, g_ns412_ranges, hits, 64, follow ? &others : nullptr, win_lo, win_hi);
	from.assign(hits.size(), 0);
	const size_t direct = hits.size();
	const int    fd     = dstate_fd(S);
	for (const uint64_t a0: others) {
		if (fd < 0 || hits.size() >= 96) break;
		const uint64_t a  = a0 & ~3ull;
		const auto     it = std::partition_point(views.begin(), views.end(), [a](const DView& v) { return v.va + v.size <= a; });
		if (it == views.end() || a < it->va) continue;
		uint64_t bytes = it->va + it->size - a;
		if (bytes > ns412::kTable) bytes = ns412::kTable;
		const ssize_t got = pread(fd, tab.data(), bytes & ~3ull, static_cast<off_t>(it->off + (a - it->va)));
		if (got < 8) continue;
		tables++;
		const size_t before = hits.size();
		ns412::scan(tab.data(), static_cast<uint32_t>(got / 4), g_ns412_ranges, hits, 96, nullptr, 0, 0);
		from.resize(hits.size(), a);
		(void)before;
	}
	bufs++;
	if (!hits.empty()) {
		bufs_hit++;
		finds_direct += direct;
		finds_table += hits.size() - direct;
		for (size_t i = 0; i < hits.size(); i++) {
			const auto&    h = hits[i];
			const auto&    r = g_ns412_ranges[h.range];
			const uint64_t r_lo = r.lo, r_hi = r.hi; // direct_force below rebuilds g_ns412_ranges
			const std::string name = g_ns412_names[r.name];
			uint64_t       got = 0;
			if (mode >= 2) {
				const uint64_t hi = h.addr + (8ull << 20) < r_hi ? h.addr + (8ull << 20) : r_hi;
				got               = direct_force(h.addr, hi);
				pinned += got;
			}
			const uint64_t n = lines++;
			if (n < 160 || (n & 255u) == 0) {
				char through[64] = "";
				if (from[i] != 0) std::snprintf(through, sizeof(through), ", through the table at 0x%" PRIx64, from[i]);
				journal("guard nogpu scan (exp 0412, tag ns412): t %.3f s: %s %u dwords: dword %u names 0x%" PRIx64 " (%s)%s, in %s left unpinned 0x%" PRIx64 "..0x%" PRIx64 "; pinned now %.1f MiB\\n",
				        timing_now(), kind, num_dwords, h.at, h.addr, h.form == 0 ? "pair" : "shifted by 8", through, name.c_str(), r_lo, r_hi, static_cast<double>(got) / 1048576.0);
			}
			if (mode >= 2 && got != 0) break; // the ranges changed under the other finds of this buffer: the next submission sees them again
		}
	}
	const uint64_t t1 = SoftCp::now_ns();
	spent_ns += t1 - t0;
	if (t1 - last_ns >= 10'000'000'000ull) {
		last_ns = t1;
		if (finds_direct + finds_table != last_finds || bufs < 100000) {
			journal("guard nogpu scan (exp 0412, tag ns412): t %.0f s: %" PRIu64 " buffers searched, %" PRIu64 " with a find (%" PRIu64 " in the buffer, %" PRIu64 " through a table; %" PRIu64 " tables read); pinned for finds %.1f MiB; %.1f ms spent in all\\n",
			        timing_now(), bufs, bufs_hit, finds_direct, finds_table, tables, static_cast<double>(pinned) / 1048576.0, static_cast<double>(spent_ns) / 1e6);
		}
		last_finds = finds_direct + finds_table;
	}
}
'''


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    s = open(sys.argv[1], "rb").read()
    inc = open(os.path.join(HERE, "nscan0412.inc"), "rb").read()
    assert b"tag ng412" in s and b"namespace ns412" not in s, "refused: not the expected input"
    assert b"\r" not in s and b"\r" not in inc
    inc.decode("ascii")
    GLUE.decode("ascii")
    edits = []
    a = b"// Experiment 0412 (tag ng412): BC5_GUARD_NOGPU_UNPIN, heaps without a GPU bit are not pinned.\n"
    edits.append((a, b"// Experiment 0412 (tag ns412): BC5_GUARD_NOGPU_SCAN, addresses in the left-out memory.\n" + inc + a))
    a = b"static bool                  g_g412_off_changed = false;\n"
    edits.append((a, a + GLUE))
    a = b"\t\tg_g412_off.swap(off);\n\t}\n\t// The catcher: has the GPU written into the zero buffer?"
    b = (b"\t\tg_g412_off.swap(off);\n\t\tnscan412_ranges(views, true);" + T + b"\t} else if (ns412::mode() != 0) {" + T + b"\t\tnscan412_ranges(views, false);" + T +
         b"\t}\n\t// The catcher: has the GPU written into the zero buffer?")
    edits.append((a, b))
    a = b"\taliases_apply(false); // experiment 0056\n"
    edits.append((a, b"\tnscan412_submit(ib, num_dwords, kind);" + T + a))
    out = s
    for old, new in edits:
        assert out.count(old) == 1, ("an anchor does not occur exactly once", old[:60], out.count(old))
        out = out.replace(old, new)
    back = out
    for old, new in reversed(edits):
        assert back.count(new) == 1, ("undo", new[:60], back.count(new))
        back = back.replace(new, old)
    assert back == s, "undoing the edits does not give the input back"
    g = out.index(b"static void nscan412_submit(const uint32_t* ib, uint32_t num_dwords, const char* kind) {")
    for need in (b"static uint64_t direct_force(uint64_t lo, uint64_t hi) {", b"namespace ns412", b"static std::vector<uint64_t> g_g412_off;", b"static int dstate_fd(const DState& S) {"):
        assert out.index(need) < g, ("must be defined before the glue", need[:40])
    assert g < out.index(b"static void nogpu412_apply(DState& S, const std::vector<DView>& views, std::vector<uint64_t>& need) {")
    call = out.index(b"\tnscan412_submit(ib, num_dwords, kind);")
    sn = out.index(b"static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, int ring, const Chain* chain) {")
    assert sn < call < out.index(b"std::shared_ptr<const std::vector<bc5::direct::Mapping>> maps_p = g_dev->sorted_mappings();", sn), "the call is not before submit_now's mapping list"
    open(sys.argv[2], "wb").write(out)
    print(f"bc5LleAgc.cpp {hashlib.md5(out).hexdigest()}")


if __name__ == "__main__":
    main()
