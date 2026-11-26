# BC5 exp 0439 (tag pw439, mode 3; the top session's order of 11-23 after F916): the unit's half of
# BC5_0439_PIECE_WAITS=3, and the timeout probe's piece dump (both modes). Run after mksr439b in prep439d.sh:
#   python3 -I mkpw439.py <unit in> <unit out>
#   1. bc5_pw439_piece_wait (the backend's weak hook, pw439patch.py): memory meets the wait -> 2 (kept); the label's last
#      pending write in g_plw from a job already in the kernel (r438's early entries left out) meets it -> 1 (kept);
#      neither -> 0 (dropped, as today); g_plw_mutex not had within ~200 us -> 3 (dropped). The compare is
#      ring_will_satisfy's. Normal and lean (a lean binary must not deadlock on mode 3 either).
#   2. bc5_pw439_piece_note (normal build): each dropped open-wait label journaled once (up to 512 labels), with the
#      waiter's ring.
#   3. pw439_flip (from dc439_flip, normal build, mode 3 only): every 64 flips one line with the decisions per frame
#      (bc5_pw439_counts, the backend's totals), and for each dropped label not yet resolved, the ring and value of a
#      writer registered since (journaled once): whether the black-character race can sit in the dropped set.
#   4. timeout_probe: every IB the timed-out buffer calls or chains to (depth 3, at most 64 IBs, read where mapped) is
#      written beside the buffer's own dump (<dump>.piece-NN-<addr>.bin), and its memory waits and label writes are
#      journaled with the label's value now: names the inner wait of a hang inside a piece (F916's GFX piece).
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding='utf-8', newline='').read()


def rep(tag, a, b):
    global s
    assert s.count(a) == 1, (tag, s.count(a))
    s = s.replace(a, b)


A1 = '''	return SoftCp::compare(function, static_cast<uint32_t>(last->value), p[5], p[4]);
}
'''
rep('hook', A1, A1 + '''// ---- exp 0439 (tag pw439, mode 3): the host's test for an open piece wait (the backend's weak hook)
extern "C" int bc5_pw439_piece_wait(const uint32_t* p, int is64, int ring) {
	(void)ring; // under the acb rings a writer on any ring counts, as in ring_will_satisfy
	if (wait_satisfied(p, is64 != 0)) return 2;
	std::unique_lock<std::mutex> lk(g_plw_mutex, std::defer_lock);
	for (int k = 0; k < 200 && !lk.try_lock(); k++) std::this_thread::sleep_for(std::chrono::microseconds(1));
	if (!lk.owns_lock()) return 3;
	const uint32_t           function = p[1] & 7u;
	const uint64_t           a        = (p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u);
	const PendingLabelWrite* last     = nullptr;
	for (const auto& w: g_plw) {
		if (w.label == a && (w.seq & kR438Early) == 0 && (last == nullptr || w.order >= last->order)) last = &w;
	}
	if (last == nullptr) return 0;
	if (is64 != 0) {
		if (!last->is64) return 0;
		const uint64_t ref = p[4] | (static_cast<uint64_t>(p[5]) << 32u), mask = p[6] | (static_cast<uint64_t>(p[7]) << 32u);
		const uint64_t vm = last->value & mask, rm = ref & mask;
		bool           ok = false;
		switch (function) {
			case 1: ok = vm < rm; break;
			case 2: ok = vm <= rm; break;
			case 3: ok = vm == rm; break;
			case 4: ok = vm != rm; break;
			case 5: ok = vm >= rm; break;
			case 6: ok = vm > rm; break;
			default: ok = false;
		}
		return ok ? 1 : 0;
	}
	return SoftCp::compare(function, static_cast<uint32_t>(last->value), p[5], p[4]) ? 1 : 0;
}
extern "C" void bc5_pw439_counts(uint64_t* out) __attribute__((weak)); // the backend's totals (pw439patch.py)
#ifndef BC5_LEAN
struct Pw439Drop {
	int      ring = -1, kind = 0;
	bool     resolved = false;
	double   t        = 0;
};
static std::mutex                            g_pw439_mu;
static std::unordered_map<uint64_t, Pw439Drop> g_pw439_drops; // under g_pw439_mu, at most 512 labels
extern "C" void bc5_pw439_piece_note(uint64_t label, int decision, int ring) {
	if (decision != 0 && decision != 3 && decision != 4) return; // kept waits are counted only
	std::lock_guard lk(g_pw439_mu);
	if (g_pw439_drops.size() >= 512 || g_pw439_drops.count(label) != 0) return;
	g_pw439_drops[label] = {ring, decision, false, timing_now()};
	journal("pw439 (exp 0439, mode 3): piece wait on 0x%" PRIx64 " dropped (%s), the waiter on ring %d, first at t %.3f s\\n", label,
	        decision == 0 ? "no submitted writer" : decision == 3 ? "host table busy" : "written in the same job", ring, timing_now());
}
static void pw439_flip() {
	static const bool on = [] {
		const char* e = std::getenv("BC5_0439_PIECE_WAITS");
		return e != nullptr && e[0] == '3' && e[1] == 0;
	}();
	if (!on || bc5_pw439_counts == nullptr) return;
	static uint64_t flips = 0, last[6] = {};
	if ((++flips & 63u) != 0) return;
	uint64_t now[6] = {};
	bc5_pw439_counts(now);
	double d[6];
	for (int k = 0; k < 6; k++) d[k] = static_cast<double>(now[k] - last[k]) / 64.0;
	for (int k = 0; k < 6; k++) last[k] = now[k];
	std::vector<std::pair<uint64_t, Pw439Drop>> open;
	size_t                                      n_drops = 0, n_resolved = 0;
	{
		std::lock_guard lk(g_pw439_mu);
		n_drops = g_pw439_drops.size();
		for (const auto& [l, e]: g_pw439_drops) {
			if (e.resolved) n_resolved++;
			else open.push_back({l, e});
		}
	}
	journal("pw439 (exp 0439, mode 3): flips %" PRIu64 ", per frame over the last 64: kept by a submitted writer %.1f, kept as met %.1f, dropped with no submitted writer %.1f, "
	        "dropped as written in the same job %.1f, dropped busy %.1f, same piece %.1f; dropped labels so far %zu (a writer seen since for %zu)\\n",
	        flips, d[1], d[2], d[0], d[4], d[3], d[5], n_drops, n_resolved);
	if (open.empty()) return;
	std::vector<std::pair<uint64_t, std::pair<int, uint64_t>>> found;
	{
		std::lock_guard lk(g_plw_mutex);
		for (const auto& [l, e]: open) {
			const PendingLabelWrite* w = nullptr;
			for (const auto& x: g_plw)
				if (x.label == l && (w == nullptr || x.order >= w->order)) w = &x;
			if (w != nullptr) found.push_back({l, {w->ring, w->value}});
		}
	}
	std::lock_guard lk(g_pw439_mu);
	for (const auto& [l, rv]: found) {
		auto& e    = g_pw439_drops[l];
		e.resolved = true;
		journal("pw439 (exp 0439, mode 3): dropped label 0x%" PRIx64 " (waiter ring %d, dropped at t %.3f s) has a writer since: ring %d value 0x%" PRIx64 " (seen at flip %" PRIu64 ")\\n", l, e.ring, e.t,
		        rv.first, rv.second, flips);
	}
}
#else
static void pw439_flip() {}
#endif
// ---- end of exp 0439 (tag pw439, mode 3)
''')

rep('flip', '	sr439b_flip(); // exp 0439 (tag sr439b)\n', '	sr439b_flip(); // exp 0439 (tag sr439b)\n	pw439_flip();  // exp 0439 (tag pw439, mode 3)\n')

A4 = '		journal("timeout probe: %s %u dwords dumped to %s\\n", kind, sub_n, name);\n'
rep('probe', A4, A4 + '''		{ // exp 0439 (tag pw439): the IBs this buffer calls or chains to, written beside it, their waits and label writes journaled
			struct PwIb {
				uint64_t a;
				uint32_t n, parent_off;
				int      depth, parent;
				bool     chain;
			};
			std::vector<PwIb> ibs;
			// d: the call depth of buffer b (the timed-out buffer 0). A called IB is one deeper; a chained IB (CHAIN bit 20 of
			// the size dword, bc5/ib_chain.hpp kChainBit) continues b at b's depth. Calls to depth 3, chains without a depth
			// limit, an address once, 512 IBs in all (a chain that loops ends there).
			auto scan = [&](const uint32_t* b, uint32_t bn, int d, int parent) {
                for (uint32_t i = 0; i < bn && ibs.size() < 512;) {
                    const uint32_t h = b[i], ty = h >> 30u;
                    uint32_t       len = 1;
                    if (ty == 3 || ty == 0) {
                        const uint32_t c = (h >> 16u) & 0x3fffu;
                        len              = c == 0x3fffu ? 1 : c + 2;
                    }
                    if (i + len > bn) break;
                    const uint32_t op = (h >> 8u) & 0xffu;
                    if (ty == 3 && (op == 0x3f || op == 0x33) && len >= 4) {
                        const uint64_t a  = (b[i + 1] & ~3u) | (static_cast<uint64_t>(b[i + 2] & 0xffffu) << 32u);
                        const uint32_t sz = b[i + 3] & 0xfffffu;
                        const bool chain = (b[i + 3] & (1u << 20)) != 0;
                        const int  cd    = chain ? d : d + 1;
                        bool       seen  = false;
                        for (const auto& x: ibs) seen = seen || x.a == a;
                        if (a != 0 && sz != 0 && sz <= (1u << 20) && cd <= 3 && !seen) ibs.push_back({a, sz, i, cd, parent, chain});
                    }
                    i += len;
                }
			};
			scan(sub_ib, sub_n, 0, -1);
			for (size_t k = 0; k < ibs.size(); k++) {
				const PwIb e  = ibs[k];
				const bool ok = covered_sorted(*pm, e.a, static_cast<uint64_t>(e.n) * 4);
				journal("timeout probe: piece %zu (call depth %d, %s at dword %u of %s %d): 0x%" PRIx64 ", %u dwords%s\\n", k, e.depth, e.chain ? "chained" : "called", e.parent_off, e.parent < 0 ? "the buffer" : "piece", e.parent, e.a, e.n,
				        ok ? "" : ", NOT mapped: not read");
				if (!ok) continue;
				const auto* b = reinterpret_cast<const uint32_t*>(e.a);
				char        pn[600];
				std::snprintf(pn, sizeof(pn), "%s.piece-%02zu-%" PRIx64 ".bin", name, k, e.a);
				if (FILE* pf = std::fopen(pn, "wb"); pf != nullptr) {
					std::fwrite(b, sizeof(uint32_t), e.n, pf);
					std::fflush(pf);
					fsync(fileno(pf));
					std::fclose(pf);
				}
				uint32_t nw = 0, nl = 0;
				for (uint32_t i = 0; i < e.n;) {
					const uint32_t h = b[i], ty = h >> 30u;
					uint32_t       len = 1;
					if (ty == 3 || ty == 0) {
						const uint32_t c = (h >> 16u) & 0x3fffu;
						len              = c == 0x3fffu ? 1 : c + 2;
					}
					if (i + len > e.n) break;
					const uint32_t op = (h >> 8u) & 0xffu;
					if (ty == 3 && (op == 0x3c || op == 0x93) && len >= 6 && ((b[i + 1] >> 4u) & 1u) != 0 && nw < 64) {
						const uint64_t l   = (b[i + 2] & ~3u) | (static_cast<uint64_t>(b[i + 3] & 0xffffu) << 32u);
						const bool     mp  = covered_sorted(*pm, l, 8);
						const uint32_t now = mp ? *reinterpret_cast<const volatile uint32_t*>(l) : 0;
						journal("timeout probe:   piece %zu wait at %u on 0x%" PRIx64 " function %u reference 0x%x mask 0x%x; now 0x%x (%s)\\n", k, i, l, b[i + 1] & 7u, b[i + 4], b[i + 5], now,
						        !mp ? "label unmapped" : wait_satisfied(&b[i], op == 0x93) ? "met" : "NOT met");
						nw++;
					} else if (ty == 3 && nl < 64) {
						uint64_t       l       = 0;
						const uint32_t dst_sel = len >= 2 ? (b[i + 1] >> 8u) & 0xfu : 0;
						if (op == 0x37 && len >= 4 && (dst_sel == 1 || dst_sel == 2 || dst_sel == 5)) l = (b[i + 2] & ~3u) | (static_cast<uint64_t>(b[i + 3] & 0xffffu) << 32u);
						else if (op == 0x49 && len >= 6) l = (b[i + 3] & ~3u) | (static_cast<uint64_t>(b[i + 4] & 0xffffu) << 32u);
						else if ((op == 0x47 || op == 0x1e) && len >= 4) l = (b[i + 2] & ~3u) | (static_cast<uint64_t>(b[i + 3] & 0xffffu) << 32u);
						if (l != 0) {
							journal("timeout probe:   piece %zu writes 0x%" PRIx64 " at %u (op %02x)\\n", k, l, i, op);
							nl++;
						}
					}
					i += len;
				}
				scan(b, e.n, e.depth, static_cast<int>(k)); // its calls one deeper (to 3), its chains at its own depth
			}
			if (!ibs.empty()) journal("timeout probe: %zu pieces of %s #%" PRIu64 " written as %s.piece-NN-<address>.bin\\n", ibs.size(), kind, n, name);
		}
''')
open(dst, 'w', encoding='utf-8', newline='').write(s)
print('mkpw439:', dst)
