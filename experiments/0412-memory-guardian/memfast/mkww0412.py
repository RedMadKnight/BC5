#!/usr/bin/env python3
"""BC5 experiment 0412, tag ww412 (PLAN-memory-wall.md step 2; README section 79): the log-only catcher for unnamed
writers, BC5_GUARD_WRITERS=1 (default off; it needs BC5_DIRECT_ZEROSCAN_AT and BC5_DIRECT_ZERO_NAMES).
Three hooks, each anchor exactly once; nothing changes when the switch is off but one branch per hook:
  direct_force     every chunk a hint or force asks for is NAMED
  the submission   every memory operand of the main buffer's packets (bc5::policy::memory_operands) names its chunk(s)
  the zero scan    per heap: the chunks all zero at the last scan and not now, named or not (ww0412.inc, ww0412.cpp)
Input: the main unit after mkkl0412.py.
usage: mkww0412.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import os
import sys

GLUE_A = rb'''static std::mutex         g_ww_mutex;
static std::set<uint64_t> g_ww_named; // file chunk offsets of direct memory that a hint, a force or a packet operand has named
static void ww412_name(uint64_t choff) {
	if (!ww412::on()) return;
	std::lock_guard lk(g_ww_mutex);
	g_ww_named.insert(choff);
}
// The zero scan's hook (its background thread): one heap's flags of this scan against the last scan's.
static void ww412_scan(const std::string& heap, uint64_t base, const std::vector<uint8_t>& now, uint32_t k) {
	if (!ww412::on()) return;
	static std::map<std::string, std::vector<uint8_t>> prev; // only the scan thread comes here, one scan at a time
	auto&          p = prev[heap];
	ww412::Turned  t;
	size_t         named_all = 0;
	const bool     compared  = p.size() == now.size();
	{
		std::lock_guard lk(g_ww_mutex);
		named_all = g_ww_named.size();
		if (compared) t = ww412::classify(p, now, base, kDChunk, 8, [](uint64_t g) { return g_ww_named.count(g) != 0; });
	}
	if (compared) {
		for (const uint64_t c: t.unnamed) {
			journal("writers (exp 0412, tag ww412): scan %u: %s: the chunk at file offset 0x%" PRIx64 " was all zero at the last scan and holds data now; no hint, force or packet operand named it\n", k, heap.c_str(), c);
		}
		journal("writers (exp 0412, tag ww412): scan %u: %s: %" PRIu64 " chunks (%" PRIu64 " MiB) turned non-zero since the last scan: %" PRIu64 " named by a hint, force or packet operand, %" PRIu64
		        " NOT named (upper bound of unknown GPU writers: a CPU write and a chunk that left its view count here too); %zu chunks named so far in all heaps\n",
		        k, heap.c_str(), t.turned, t.turned * (kDChunk >> 20u), t.named, t.turned - t.named, named_all);
	} else {
		journal("writers (exp 0412, tag ww412): scan %u: %s: first scan of this span (%zu slots): nothing to compare yet\n", k, heap.c_str(), now.size());
	}
	p = now;
}
'''

GLUE_B = rb'''// Experiment 0412 (tag ww412): every memory operand of the main buffer's packets names the chunk(s) of direct memory it lies in.
static void ww412_packets(const uint32_t* ib, uint32_t num_dwords) {
	if (!ww412::on() || !g_dev) return;
	const auto  views_p = direct_views(g_d[0]);
	const auto& views   = views_p->v;
	for (uint32_t q = 0; q < num_dwords;) {
		const uint32_t h   = ib[q];
		uint32_t       len = 1;
		if ((h >> 30u) == 3 || (h >> 30u) == 0) {
			const uint32_t c = (h >> 16u) & 0x3fffu;
			len              = c == 0x3fffu ? 1 : c + 2;
		}
		if (q + len > num_dwords) break;
		if ((h >> 30u) == 3) {
			for (const auto& [a, bytes]: bc5::policy::memory_operands(ib + q, len)) {
				if (a == 0) continue;
				const uint64_t e     = a + (bytes == 0 ? 4 : bytes);
				size_t         first = 0;
				if (views_p->sorted) first = static_cast<size_t>(std::partition_point(views.begin(), views.end(), [a](const DView& v) { return v.va + v.size <= a; }) - views.begin());
				for (size_t vi = first; vi < views.size(); vi++) {
					const auto& v = views[vi];
					if (views_p->sorted && v.va >= e) break;
					const uint64_t lo = a > v.va ? a : v.va;
					const uint64_t hi = e < v.va + v.size ? e : v.va + v.size;
					if (lo >= hi) continue;
					for (uint64_t c = (v.off + (lo - v.va)) & ~(kDChunk - 1); c < v.off + (hi - v.va); c += kDChunk) ww412_name(c);
				}
			}
		}
		q += len;
	}
}
'''


def once(s, old, new):
    assert s.count(old) == 1, ("an anchor does not occur exactly once", old[:70], s.count(old))
    return s.replace(old, new)


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    s = open(sys.argv[1], "rb").read()
    assert b"\r" not in s and b"tag kl412" in s and b"tag ww412" not in s, "refused: not the unit after mkkl0412.py, or already edited"
    inc = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ww0412.inc"), "rb").read()
    assert b"\r" not in inc
    body = inc[inc.index(b"namespace ww412 {"):]
    assert body.rstrip().endswith(b"} // namespace ww412") and b"#include" not in body
    GLUE_A.decode("ascii")
    GLUE_B.decode("ascii")
    a = b"// ---- experiment 0379: the zero list (BC5_DIRECT_ZEROSCAN_AT/_OUT) and the skip (BC5_DIRECT_ZERO_SKIP) ---------------\n"
    s = once(s, a, b"// Experiment 0412 (tag ww412): ww0412.inc, BC5_GUARD_WRITERS, the log-only catcher for unnamed writers.\n" + body + GLUE_A + a)
    a = b"\t\tstd::lock_guard lk(g_zscan_mutex);\n"
    s = once(s, a, b"\t\tww412_scan(h.name, h.base, now, k); // exp 0412 (tag ww412)\n" + a)
    a = b"\t\t\tfor (uint64_t c = (v.off + (a - v.va)) & ~(kDChunk - 1); c < v.off + (b - v.va); c += kDChunk) {\n"
    s = once(s, a, a + b"\t\t\t\tww412_name(c); // exp 0412 (tag ww412): a hint or force names this chunk\n")
    a = b"// Experiment 0412 (tag k1f412): BC5_GUARD_K1_FILTER, a packet's unmapped operand under a view is imported, not dropped.\n"
    s = once(s, a, GLUE_B + a)
    a = b"\tk1f412_pass(ib, num_dwords, kind);"
    s = once(s, a, b"\tww412_packets(ib, num_dwords); // exp 0412 (tag ww412)\n" + a)
    g = s.index(b"namespace ww412 {")
    for need in (b"constexpr uint64_t kDChunk", b"static void journal(const char* fmt, ...) {", b"struct DView {"):
        assert s.index(need) < g, ("must be defined before the glue", need[:40])
    assert g < s.index(b"static void zscan_run(") and g < s.index(b"static uint64_t direct_force(uint64_t lo, uint64_t hi) {") < s.index(b"static void ww412_packets(")
    open(sys.argv[2], "wb").write(s)
    print(f"bc5LleAgc.cpp {hashlib.md5(s).hexdigest()}")


if __name__ == "__main__":
    main()
