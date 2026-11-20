#!/usr/bin/env python3
"""BC5 experiment 0438 (tag u438): k1f412's walk out of g_dev_mutex. On the r438 + c438 + c438d unit (r438d.cpp).

Usage: mku438.py IN.cpp OUT.cpp   (IN: mkc438d.py's output on r438.cpp, md5 fdfa45be...)

Switch BC5_0438_SPLIT (on in this test build unless "0"; behaviour, so in lean too).

What k1f412_pass touches (A = the unit), and which lock covers it, today and with u438:
| what | today | with u438 |
| the IB's packets (read) | g_dev_mutex (not needed: the title's buffer, unchanged while it is submitted) | none: read before the lock |
| bc5::policy::memory_operands, ud434::scan (pure parses) | g_dev_mutex | none |
| g_dev->sorted_mappings() (a shared_ptr snapshot; the backend builds it under its own impl mutex, a new object at every change of the list: Device::sorted_mappings, backend direct.cpp) | g_dev_mutex + the backend's mutex | the backend's mutex only (as today, inside the call) |
| covered_sorted on the snapshot (pure) | g_dev_mutex | none |
| direct_force (imports: g_d state S.forced/S.bos/views, device mappings) | g_dev_mutex | g_dev_mutex (unchanged) |
| the pass's static counters and journal lines | g_dev_mutex | g_dev_mutex (they move with the imports) |
The walk runs in submit_now before the back-pressure wait and the locks, on the snapshot of that moment, and keeps
the operands not covered there. Under g_dev_mutex, at k1f412's place, the snapshot is compared with the current one
(pointer identity = the same mapping list): unchanged, only the kept operands are looked at again and imported as
today; changed (a sync or an import since), the walk is done again under the lock, as today. So what is imported is
what today's pass would import whenever the mapping list did not change in between, and exactly today's pass
otherwise.
"""
import hashlib
import sys

IN, OUT = sys.argv[1], sys.argv[2]
src = open(IN, 'rb').read()
assert hashlib.md5(src).hexdigest() == 'fdfa45be5341a1b709a409c297623593', 'not r438d.cpp (mkc438d on r438)'
s = src.decode('utf-8')


def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, (n, old[:120])
    s = s.replace(old, new)


rep('''static void k1f412_pass(const uint32_t* ib, uint32_t num_dwords, const char* kind) {
	if (!k1f412::on() || !g_dev) return;
	if (k1f412::mode() == 2) {
		k1f412_log(ib, num_dwords, kind);
		return;
	}''', '''// BC5 experiment 0438 (tag u438): k1f412's walk before g_dev_mutex (BC5_0438_SPLIT, on unless "0"). The walk reads only
// the IB and a mapping snapshot; what it found not covered is kept per thread for the pass under the lock.
namespace u438 {
inline bool on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_0438_SPLIT");
		return !(e != nullptr && e[0] == '0' && e[1] == 0);
	}();
	return v;
}
struct Miss {
	uint32_t q, op, reg;
	uint64_t a, n;
	bool     ud; // a user-data V# (ud434), else a packet operand
};
struct Pre {
	const uint32_t*                                          ib = nullptr;
	uint32_t                                                 n  = 0;
	std::shared_ptr<const std::vector<bc5::direct::Mapping>> snap;
	std::vector<Miss>                                        miss;
	bool                                                     valid = false;
};
inline thread_local Pre t_pre;
inline std::atomic<uint64_t> g_pre {0}, g_used {0}, g_redo {0}, g_pre_ns {0};
} // namespace u438
// The walk, outside any host lock (submit_now, before the back-pressure wait).
static void k1f412_collect(const uint32_t* ib, uint32_t num_dwords) {
	u438::Pre& p = u438::t_pre;
	p.valid      = false;
	if (!u438::on() || !k1f412::on() || k1f412::mode() == 2 || !g_dev || ib == nullptr) return;
	const uint64_t t0 = SoftCp::now_ns();
	p.ib              = ib;
	p.n               = num_dwords;
	p.snap            = g_dev->sorted_mappings();
	p.miss.clear();
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
				if (a == 0 || covered_sorted(*p.snap, a, n)) continue;
				p.miss.push_back({q, (h >> 8u) & 0xffu, 0, a, n, false});
			}
			ud434::scan(ib + q, len, [&](uint64_t a, uint64_t n) {
				if (covered_sorted(*p.snap, a, n)) return;
				p.miss.push_back({q, (h >> 8u) & 0xffu, ib[q + 1] & 0xffffu, a, n, true});
			});
		}
		q += len;
	}
	p.valid = true;
	u438::g_pre++;
	u438::g_pre_ns += SoftCp::now_ns() - t0;
}
static void k1f412_pass(const uint32_t* ib, uint32_t num_dwords, const char* kind) {
	if (!k1f412::on() || !g_dev) return;
	if (k1f412::mode() == 2) {
		k1f412_log(ib, num_dwords, kind);
		return;
	}
	if (u438::on()) { // exp 0438 (tag u438): the walk was done before the lock; only its misses are looked at again
		u438::Pre& p  = u438::t_pre;
		const bool ok = p.valid && p.ib == ib && p.n == num_dwords && g_dev->sorted_mappings() == p.snap;
		p.valid       = false;
		if (ok) {
			u438::g_used++;
			static uint64_t fired = 0, asked_bytes = 0, lines = 0, no_view = 0, ud_fired = 0, ud_bytes = 0, ud_lines = 0;
			auto            have_p = p.snap;
			for (const auto& m: p.miss) {
				if (covered_sorted(*have_p, m.a, m.n)) continue; // an import for an earlier miss covered it
				const uint64_t asked = direct_force(m.a & ~0xfffull, m.a + m.n);
				if (asked == 0) {
					if (!m.ud) no_view++;
					continue;
				}
				have_p = g_dev->sorted_mappings();
				if (!m.ud) {
					fired++;
					asked_bytes += asked;
					if (lines++ < 200 || (lines & 255u) == 0)
						journal("k1 at the filter (exp 0412, tag k1f412; u438): t %.3f s: %s %u dwords, packet op 0x%02x at dword %u: operand 0x%" PRIx64 "+%" PRIu64 " was not mapped: its chunk(s) imported (+%.1f MiB), now %s; "
						        "%" PRIu64 " imports so far, %.1f MiB; %" PRIu64 " operands left unmapped (no view or no import)\\n",
						        timing_now(), kind, num_dwords, m.op, m.q, m.a, m.n, static_cast<double>(asked) / 1048576.0, covered_sorted(*have_p, m.a, m.n) ? "mapped" : "STILL NOT MAPPED", fired,
						        static_cast<double>(asked_bytes) / 1048576.0, no_view);
				} else {
					ud_fired++;
					ud_bytes += asked;
					if (ud_lines++ < 200 || (ud_lines & 255u) == 0)
						journal("user-data target (exp 0434, tag ud434; u438): t %.3f s: %s %u dwords, SET_SH_REG at dword %u, reg 0x%x: V# 0x%" PRIx64 "+%" PRIu64 " was not mapped: its chunk(s) imported (+%.1f MiB), now %s; %" PRIu64 " imports so far, %.1f MiB\\n",
						        timing_now(), kind, num_dwords, m.q, m.reg, m.a, m.n, static_cast<double>(asked) / 1048576.0, covered_sorted(*have_p, m.a, m.n) ? "mapped" : "STILL NOT MAPPED", ud_fired,
						        static_cast<double>(ud_bytes) / 1048576.0);
				}
			}
#ifndef BC5_LEAN
			static double u438_last = 0;
			if (timing_now() - u438_last >= 60.0) {
				u438_last = timing_now();
				journal("u438 (exp 0438): t %.1f s: k1f412 walks before the lock %" PRIu64 " (%.1f ms in all), used under the lock %" PRIu64 ", walked again (the mappings changed) %" PRIu64 "\\n", timing_now(), u438::g_pre.load(),
				        static_cast<double>(u438::g_pre_ns.load()) / 1e6, u438::g_used.load(), u438::g_redo.load());
			}
#endif
			return;
		}
		u438::g_redo++;
	}''')

rep('''	if (g_async) {
		// Experiment 0045: 24 jobs in flight before the game's''', '''	k1f412_collect(ib, num_dwords); // exp 0438 (tag u438): k1f412's walk before the back-pressure wait and the locks
	if (g_async) {
		// Experiment 0045: 24 jobs in flight before the game's''')

out = s.encode('utf-8')
open(OUT, 'wb').write(out)
print('u438 unit', hashlib.md5(out).hexdigest(), len(out))
