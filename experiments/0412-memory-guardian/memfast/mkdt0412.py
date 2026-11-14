#!/usr/bin/env python3
"""BC5 experiment 0412, tag dt412 (README section 94), default off:
  BC5_GUARD_DESC_TARGETS=1  in submit_now, before the mappings are synced: every buffer the command buffer's user
                            data names (a descriptor or a plain pointer; for a plain pointer also the descriptors
                            and pointers in the first 64 dwords it leads to) is imported with direct_force, so a
                            shader's store through a descriptor does not meet the read-only zero cover (arm b1).
  BC5_GUARD_DESC_TARGETS=2  log only: nothing imported; the journal counts what mode 1 would import.
The walk is dt0412.inc (CPU test dt0412.cpp). A descriptor does not say read or write: all are taken.
Input: a main unit with tag dc412 (mkdw0412.py's output, a53e98b7). Every anchor exactly once.
usage: mkdt0412.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

DT_GLUE = rb'''// Experiment 0412 (tag dt412): the host's part of dt0412.inc.
// The chunks of [lo, hi) that lie under a view and are not imported: what direct_force would ask for (mode 2).
static uint64_t dt412_missing(uint64_t lo, uint64_t hi) {
	uint64_t bytes = 0;
	for (auto& S: g_d) {
		if (dstate_fd(S) < 0) continue;
		const auto views_p = direct_views(S);
		const auto& views = views_p->v;
		size_t      first = 0;
		if (views_p->sorted) first = static_cast<size_t>(std::partition_point(views.begin(), views.end(), [lo](const DView& v) { return v.va + v.size <= lo; }) - views.begin());
		for (size_t vi = first; vi < views.size(); vi++) {
			const auto& v = views[vi];
			if (views_p->sorted && v.va >= hi) break;
			const uint64_t a = lo > v.va ? lo : v.va;
			const uint64_t b = hi < v.va + v.size ? hi : v.va + v.size;
			if (a >= b) continue;
			for (uint64_t c = (v.off + (a - v.va)) & ~(kDChunk - 1); c < v.off + (b - v.va); c += kDChunk) {
				if (direct_covered_end(S, c) == 0) bytes += kDChunk;
			}
		}
	}
	return bytes;
}
static void dt412_pass(const uint32_t* ib, uint32_t n, const char* kind) {
	const int mode = dt412::mode();
	if (mode == 0 || ib == nullptr || n == 0 || !g_dev) return;
	static dt412::Recent recent, tables;
	static uint64_t      seen = 0, acted = 0, acted_bytes = 0, lines = 0, tables_read = 0;
	static double        last_line = 0;
	const double         now = timing_now();
	auto                 have_p = g_dev->sorted_mappings();
	auto take = [&](uint64_t a, uint64_t bytes, int level, uint32_t where) {
		const uint64_t lo = a & ~0xfffull, hi = a + (bytes != 0 ? bytes : 1);
		if (recent.fresh(lo, hi - lo, now)) return;
		seen++;
		const uint64_t asked = mode == 1 ? direct_force(lo, hi) : dt412_missing(lo, hi);
		if (asked == 0) return; // under no view, or imported already
		acted++;
		acted_bytes += asked;
		if (mode == 1) have_p = g_dev->sorted_mappings();
		if (lines++ < 200 || (lines & 255u) == 0) {
			journal("desc targets (exp 0412, tag dt412): t %.3f s: %s %u dwords: %s 0x%" PRIx64 "+0x%" PRIx64 " (level %d, %s %u): %s %.1f MiB; %" PRIu64 " so far, %.1f MiB\n", now, kind, n,
			        bytes != 0 ? "descriptor" : "pointer", a, bytes, level, level == 1 ? "register" : "table dword", where, mode == 1 ? "imported" : "WOULD import", static_cast<double>(asked) / 1048576.0, acted,
			        static_cast<double>(acted_bytes) / 1048576.0);
		}
	};
	auto read = [&](uint64_t a, uint32_t dws, std::vector<uint32_t>& out) {
		if (!covered_sorted(*have_p, a, static_cast<uint64_t>(dws) * 4)) return false;
		const auto* t = reinterpret_cast<const volatile uint32_t*>(a);
		out.resize(dws);
		for (uint32_t k = 0; k < dws; k++) out[k] = t[k];
		return true;
	};
	std::vector<uint32_t> tab;
	dt412::walk(
	    ib, n, [&](uint64_t a, uint32_t pairs, std::vector<uint32_t>& o) { return read(a, 2 * pairs, o); },
	    [&](uint32_t reg, uint64_t a, uint64_t bytes, bool plain) {
		    take(a, bytes, 1, reg);
		    if (!plain || (a & 3u) != 0 || !read(a, dt412::kTableDws, tab)) return;
		    uint64_t sum = 0xcbf29ce484222325ull; // the table as it is now: looked through again only when it changed
		    for (uint32_t w: tab) sum = (sum ^ w) * 0x100000001b3ull;
		    if (tables.fresh(a, sum, now)) return;
		    tables_read++;
		    dt412::block(tab.data(), dt412::kTableDws, [&](uint32_t k, uint64_t a2, uint64_t bytes2, bool) { take(a2, bytes2, 2, k); });
	    });
	if (now - last_line >= 60.0) {
		last_line = now;
		journal("desc targets (exp 0412, tag dt412): t %.0f s: mode %d (%s): %" PRIu64 " buffers looked at, %" PRIu64 " %s, %.1f MiB; %" PRIu64 " tables read\n", now, mode, mode == 1 ? "import" : "log only", seen, acted,
		        mode == 1 ? "imported" : "would be imported", static_cast<double>(acted_bytes) / 1048576.0, tables_read);
	}
}
'''


def once(s, old, new):
    assert s.count(old) == 1, (s.count(old), old[:70])
    return s.replace(old, new)


def body_of(name, ns):
    inc = open(os.path.join(HERE, name), "rb").read()
    assert b"\r" not in inc
    body = inc[inc.index(b"namespace " + ns + b" {"):]
    assert body.rstrip().endswith(b"} // namespace " + ns) and b"#include" not in body
    return body


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    s = open(sys.argv[1], "rb").read()
    assert b"\r" not in s and b"tag dc412" in s and b"tag dt412" not in s, "refused: not a unit with dc412, or already edited"
    DT_GLUE.decode("ascii")
    a = b"static void journal_load_tables(const uint32_t* ib, uint32_t num_dwords,\n"
    s = once(s, a, b"// Experiment 0412 (tag dt412): dt0412.inc, the buffers a command buffer's user data names.\n" + body_of("dt0412.inc", b"dt412") + DT_GLUE + b"\n" + a)
    a = b"\tk1f412_pass(ib, num_dwords, kind); // exp 0412 (tag k1f412)\n"
    s = once(s, a, a + b"\tdt412_pass(ib, num_dwords, kind); // exp 0412 (tag dt412): before the mappings are synced\n")
    open(sys.argv[2], "wb").write(s)
    print(f"bc5LleAgc.cpp {hashlib.md5(s).hexdigest()}")


if __name__ == "__main__":
    main()
