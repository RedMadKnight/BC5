#!/usr/bin/env python3
"""BC5 experiment 0412, tag k1f412 (README section 70; the top's order of 2026-11-13): K1 AT THE FILTER.
BC5_GUARD_K1_FILTER=1 (default off); =log names what the filter would drop and imports nothing. Today a packet whose memory operand is not GPU-mapped is DROPPED by the packet
filter. When that operand lies in memory the title mapped (under a view) whose chunk is merely not imported (never
written by the CPU, or a lazy heap), the drop loses something the console does: there the memory exists and the
command processor reads or writes it. The packet NAMES its operand, so the host knows the address before the GPU
touches it. With the switch on, before the sync of each submission, every type-3 packet's memory operands
(bc5::policy::memory_operands, the list the filter itself checks) are looked at; an operand that is not mapped gets
its chunk(s) imported at once (direct_force: real pages, mapped), so the filter then passes the packet. Journal: the
first 200 firings and every 256th after (the buffer's kind, the packet's opcode and place, the operand, what was
imported), and the totals in each line.
Limits: only the buffer handed to the submission is walked, not the INDIRECT_BUFFER targets it names (the backend
filters those; their unmapped operands are still dropped); an operand under no view stays unmapped and its packet
dropped (the K3 case); every import pins memory (the count is in the journal: it is the price to measure).
Needs cv412 when K1r is on (a cover must not make an operand look mapped).
Input: the main unit after mkcv0412.py. One anchor for the glue, one for the call.
usage: mkk1f0412.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import sys

T = b" // exp 0412 (tag k1f412)\n"

GLUE = rb'''// Experiment 0412 (tag k1f412): BC5_GUARD_K1_FILTER, a packet's unmapped operand under a view is imported, not dropped.
namespace k1f412 {
// 0 off (unset, "0"), 1 import ("1" or anything else), 2 log only ("log"): name what the filter would drop, import nothing
inline int mode() {
	static const int v = [] {
		const char* e = std::getenv("BC5_GUARD_K1_FILTER");
		if (e == nullptr || e[0] == 0 || (e[0] == '0' && e[1] == 0)) return 0;
		return std::strcmp(e, "log") == 0 ? 2 : 1;
	}();
	return v;
}
inline bool on() { return mode() != 0; }
} // namespace k1f412
// Log only: every operand the filter would drop is named once per page (the first 400), with its packet, its view and
// whether its chunk is imported; every 10 s a count by packet opcode. Nothing is imported, nothing else changes.
static void k1f412_log(const uint32_t* ib, uint32_t num_dwords, const char* kind) {
	static std::set<uint64_t>           seen;
	static std::map<uint32_t, uint64_t> by_op, by_op_view;
	static uint64_t                     total = 0, under_view = 0, last_ns = 0, lines = 0;
	const auto                          have_p  = g_dev->sorted_mappings();
	const auto                          views_p = direct_views(g_d[0]);
	for (uint32_t q = 0; q < num_dwords;) {
		const uint32_t h   = ib[q];
		uint32_t       len = 1;
		if ((h >> 30u) == 3 || (h >> 30u) == 0) {
			const uint32_t c = (h >> 16u) & 0x3fffu;
			len              = c == 0x3fffu ? 1 : c + 2;
		}
		if (q + len > num_dwords) break;
		if ((h >> 30u) == 3) {
			const uint32_t op = (h >> 8u) & 0xffu;
			for (const auto& [a, bytes]: bc5::policy::memory_operands(ib + q, len)) {
				const uint64_t n = bytes == 0 ? 4 : bytes;
				if (a == 0 || covered_sorted(*have_p, a, n)) continue;
				const DView* v = nullptr;
				for (const auto& x: views_p->v) {
					if (a >= x.va && a < x.va + x.size) {
						v = &x;
						break;
					}
				}
				total++;
				by_op[op]++;
				if (v != nullptr) {
					under_view++;
					by_op_view[op]++;
				}
				if (seen.size() < 400 && seen.insert(a & ~0xfffull).second) {
					const bool imported = v != nullptr && direct_covered_end(g_d[0], (v->off + (a - v->va)) & ~(kDChunk - 1)) != 0;
					journal("k1 at the filter LOG (exp 0412, tag k1f412): t %.3f s: %s %u dwords, packet op 0x%02x at dword %u: operand 0x%" PRIx64 "+%" PRIu64 " is not mapped (the filter drops the packet): %s%s%s%s\n",
					        timing_now(), kind, num_dwords, op, q, a, n, v == nullptr ? "under NO view of the direct file" : "under \"", v == nullptr ? "" : v->name.c_str(),
					        v == nullptr ? "" : (v->eager ? "\" (eager)" : (v->lazy ? "\" (lazy)" : "\" (by data)")), v == nullptr ? "" : (imported ? ", its chunk imported (mapped elsewhere?)" : ", its chunk not imported: an import would let the packet through"));
					lines++;
				}
			}
		}
		q += len;
	}
	const uint64_t now = SoftCp::now_ns();
	if (total != 0 && now - last_ns >= 10'000'000'000ull) {
		last_ns = now;
		std::string ops;
		for (const auto& [op, c]: by_op) {
			char t[64];
			std::snprintf(t, sizeof(t), " 0x%02x:%" PRIu64 "/%" PRIu64, op, c, by_op_view.count(op) != 0 ? by_op_view[op] : 0);
			ops += t;
		}
		journal("k1 at the filter LOG (exp 0412, tag k1f412): t %.0f s: %" PRIu64 " unmapped operands so far, %" PRIu64 " under a view (an import would cure), %zu distinct pages named; by packet opcode (all/under a view):%s\n",
		        timing_now(), total, under_view, seen.size(), ops.c_str());
	}
}
static void k1f412_pass(const uint32_t* ib, uint32_t num_dwords, const char* kind) {
	if (!k1f412::on() || !g_dev) return;
	if (k1f412::mode() == 2) {
		k1f412_log(ib, num_dwords, kind);
		return;
	}
	static uint64_t fired = 0, asked_bytes = 0, lines = 0, no_view = 0;
	auto            have_p = g_dev->sorted_mappings();
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
				const uint64_t n = bytes == 0 ? 4 : bytes;
				if (a == 0 || covered_sorted(*have_p, a, n)) continue;
				const uint64_t asked = direct_force(a & ~0xfffull, a + n);
				if (asked == 0) { // under no view (K3), or its chunk was asked for before and could not be imported
					no_view++;
					continue;
				}
				fired++;
				asked_bytes += asked;
				have_p = g_dev->sorted_mappings();
				if (lines++ < 200 || (lines & 255u) == 0) {
					journal("k1 at the filter (exp 0412, tag k1f412): t %.3f s: %s %u dwords, packet op 0x%02x at dword %u: operand 0x%" PRIx64 "+%" PRIu64 " was not mapped: its chunk(s) imported (+%.1f MiB), now %s; "
					        "%" PRIu64 " imports so far, %.1f MiB; %" PRIu64 " operands left unmapped (no view or no import)\n",
					        timing_now(), kind, num_dwords, (h >> 8u) & 0xffu, q, a, n, static_cast<double>(asked) / 1048576.0, covered_sorted(*have_p, a, n) ? "mapped" : "STILL NOT MAPPED", fired,
					        static_cast<double>(asked_bytes) / 1048576.0, no_view);
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
    assert b"\r" not in s and b"tag cv412" in s and b"tag k1f412" not in s, "refused: not the unit after mkcv0412.py, or already edited"
    GLUE.decode("ascii")
    call = b"\tconst uint64_t ta = SoftCp::now_ns();\n\tsync_mappings(force_sync, urgent_sync);\n"
    s = once(s, call, b"\tk1f412_pass(ib, num_dwords, kind);" + T + call)
    c = s.index(b"\tk1f412_pass(ib, num_dwords, kind);")
    # the glue goes before the function that holds the call: the last top-level "static" function start before it
    a = b"static bool covered_sorted(const std::vector<bc5::direct::Mapping>& maps, uint64_t a, uint64_t bytes) {\n"
    d = s.index(a)
    e = s.index(b"\n}\n", d) + 3
    assert d < c and e < c
    s = s[:e] + GLUE + s[e:]
    g = s.index(b"static void k1f412_pass(")
    for need in (b"static uint64_t direct_force(uint64_t lo, uint64_t hi) {", b"static double timing_now() {"):
        assert s.index(need) < g, ("must be defined before the glue", need[:40])
    assert g < s.index(b"\tk1f412_pass(ib, num_dwords, kind);")
    open(sys.argv[2], "wb").write(s)
    print(f"bc5LleAgc.cpp {hashlib.md5(s).hexdigest()}")


if __name__ == "__main__":
    main()
