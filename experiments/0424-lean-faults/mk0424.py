#!/usr/bin/env python3
r"""BC5 experiment 0424: the private test build's two changes to src/libs/bc5LleAgc.cpp (patch 4945ef1b's unit, md5
3e847e03), the top session's GO of 2026-11-15 21:06.
    mk0424.py <tree root>

1. The fix (tag aq424), behind BC5_DIRECT_ACB_QUEUE_STATE (unset, empty or "0": off; read with std::getenv, so the
   lean build reads it too). On: exp 0401's acb CS prefix path comes back, changed in one point. EVERY acb part that
   dispatches (or calls an IB2; acb_restore_wants) gets its guest queue's tracked compute registers in front: SH
   0x204-0x3ff without COMPUTE_VMID (acb_restore_runs over g_acb_cs[t_queue_idx]), not only a part that dispatches
   before it sets a program. The second title's BVH refit 0x909939900 sets its program and USER_DATA_0..4 and relies
   on its queue's USER_DATA_5 (exp 0424 README). The queue's tracker is applied after each part (acb_cs_track, at the
   two existing call sites), so a part gets the queue's state at its own start, a rest too. A queue with nothing tracked
   gets nothing and is counted.
2. The catcher (tag aq424c), normal build only (#ifndef BC5_LEAN). In submit_now, under g_dev_mutex, i.e. in the order
   the buffers reach each ring, a shadow of each ring's USER_DATA_5, COMPUTE_PGM_LO/HI and SET_BASE 1 follows the
   SET_SH_REG / SET_BASE packets. LOAD_SH_REG(_INDEX) and INDIRECT_BUFFER make the shadow unknown, since they are not
   followed. Each DISPATCH_INDIRECT of 0x909939900 compares USER_DATA_5's low 16 bits with the high dword of its
   argument address (SET_BASE 1 + offset). Counts: match, MISMATCH, unknown, no base. One stderr line at most every
   10 s, never per dispatch.
Every edit must match exactly once (ed0419g.File). Register offsets: SH 0x20c/0x20d COMPUTE_PGM_LO/HI, 0x245
COMPUTE_USER_DATA_5; opcodes 0x76/0x9b SET_SH_REG(_INDEX), 0x5f LOAD_SH_REG, 0x63 LOAD_SH_REG_INDEX, 0x3f
INDIRECT_BUFFER, 0x11 SET_BASE, 0x16 DISPATCH_INDIRECT (the unit's own comments, citing Mesa sid.h / gfx10.json)."""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "0419-switch-cleanup"))
sys.path.insert(0, HERE)
from ed0419g import File

f = File(os.path.join(sys.argv[1], "src", "libs", "bc5LleAgc.cpp"))
f.gone("tag aq424")

# 1a. the switch, and the forward declarations of the restore helpers defined further down
f.sub("static bool acb_cs_prefix_on() {\n"
      "\tstatic const bool        on = false /* exp 0419: option removed */ && acb_inherit_mode() == 0; // + exp 0403: ACB_INHERIT wins\n",
      r'''// Experiment 0424 (tag aq424): BC5_DIRECT_ACB_QUEUE_STATE, the acb's own queue state in front of every acb part that
// dispatches (see acb_cs_prefix). Read with std::getenv: the lean build reads it too. Off by default in the test build.
static bool aq424_on() {
	static const bool on = [] {
		const char* e = std::getenv("BC5_DIRECT_ACB_QUEUE_STATE");
		const bool  v = e != nullptr && e[0] != 0 && std::strcmp(e, "0") != 0;
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0424 (tag aq424): acb queue state %s\n", v ? "ON (every acb part that dispatches gets its queue's compute registers in front)" : "off");
#endif
		return v;
	}();
	return on;
}
static std::atomic<uint64_t> g_aq424_parts {0}, g_aq424_none {0}; // exp 0424: parts given their queue's state; parts whose queue had none
static bool                  acb_restore_wants(const uint32_t* ib, uint32_t num_dwords);
static std::vector<uint32_t> acb_restore_runs(const bc5::full_state::Tracker& t, size_t* regs);
static bool acb_cs_prefix_on() {
	static const bool        on = aq424_on(); // exp 0424 (tag aq424); exp 0419 had removed the option (false)
''')

# 1b. every dispatching part, the queue's whole tracked compute set
f.sub("""	const int at = cs_inherit_at(part, n, *g_dev->sorted_mappings());
	if (at < 0) return {};
	uint64_t              pgm = 0;
	std::vector<uint32_t> cs;
	{
		std::lock_guard lk(g_acb_cs_mutex);
		const auto      it = g_acb_cs.find(t_queue_idx);
		if (it != g_acb_cs.end()) cs = cs_prefix(it->second, &pgm);
	}
""", """	// exp 0424 (tag aq424): every part that dispatches, not only one that dispatches before it sets a program (cs_inherit_at):
	// a console compute queue keeps all of its registers from buffer to buffer, and the BVH refit 0x909939900 sets its program
	// and USER_DATA_0..4 but keeps the queue's USER_DATA_5 (on the shared GFX ring it got another queue's, high half 0x11 for
	// 0x12: exp 0424). The set is SH 0x204-0x3ff without COMPUTE_VMID (acb_restore_runs).
	if (!acb_restore_wants(part, n)) return {};
	const int             at  = cs_inherit_at(part, n, *g_dev->sorted_mappings());
	uint64_t              pgm = 0;
	std::vector<uint32_t> cs;
	{
		std::lock_guard lk(g_acb_cs_mutex);
		const auto      it = g_acb_cs.find(t_queue_idx);
		if (it != g_acb_cs.end()) {
			size_t   regs = 0;
			uint32_t lo = 0, hi = 0;
			cs = acb_restore_runs(it->second, &regs);
			it->second.get(bc5::full_state::Sh, 0x20cu, lo);
			it->second.get(bc5::full_state::Sh, 0x20du, hi);
			pgm = (static_cast<uint64_t>(lo) | (static_cast<uint64_t>(hi & 0xffu) << 32u)) << 8u;
		}
	}
	(cs.empty() ? g_aq424_none : g_aq424_parts)++;
""")

# 2. the catcher, after acb_cs_track
f.sub("""	g_acb_cs[t_queue_idx].apply(std::span<const uint32_t>(part, n), read, st);
}
""", """	g_acb_cs[t_queue_idx].apply(std::span<const uint32_t>(part, n), read, st);
}
#ifndef BC5_LEAN
// Experiment 0424 (tag aq424c): the catcher of the BVH refit's pointer. submit_now calls it under g_dev_mutex, so the
// buffers come in the order they reach each ring. Per ring, a shadow of COMPUTE_USER_DATA_5 (SH 0x245),
// COMPUTE_PGM_LO/HI (0x20c/0x20d) and SET_BASE 1; LOAD_SH_REG(_INDEX) 0x5f/0x63 and INDIRECT_BUFFER 0x3f are not
// followed and make it unknown. For each DISPATCH_INDIRECT 0x16 of 0x909939900, USER_DATA_5's low 16 bits are compared
// with the high dword of the argument address (SET_BASE 1 + the packet's offset): the refit's USER_DATA_4 is that address
// minus 0x80 (1,481 of 1,481 dispatches in the two dumps). One stderr line at most every 10 s.
struct Aq424Ring {
	bool     ud5_known = false, pgm_known = false;
	uint32_t ud5 = 0, pgm_lo = 0, pgm_hi = 0;
	uint64_t base1 = 0;
};
static std::map<int, Aq424Ring> g_aq424_ring;
static uint64_t                 g_aq424_n = 0, g_aq424_match = 0, g_aq424_mis = 0, g_aq424_unk = 0, g_aq424_nobase = 0, g_aq424_last_ns = 0;
static uint32_t                 g_aq424_first_ud5 = 0, g_aq424_first_hi = 0;
static void aq424_catch(const uint32_t* ib, uint32_t n, int ring) {
	Aq424Ring& r = g_aq424_ring[ring];
	for (uint32_t i = 0; i < n;) {
		const uint32_t h = ib[i], type = h >> 30u;
		uint32_t       len = 1;
		if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
		if (i + len > n) break;
		if (type == 3) {
			const uint32_t  op = (h >> 8u) & 0xffu;
			const uint32_t* p  = ib + i;
			if ((op == 0x76 || op == 0x9b) && len >= 3) {
				const uint32_t o = p[1] & 0xffffu;
				for (uint32_t k = 0; k + 2 < len; k++) {
					const uint32_t reg = o + k, v = p[2 + k];
					if (reg == 0x245u) { r.ud5 = v; r.ud5_known = true; }
					else if (reg == 0x20cu) { r.pgm_lo = v; r.pgm_known = true; }
					else if (reg == 0x20du) r.pgm_hi = v;
				}
			} else if (op == 0x5f || op == 0x63 || op == 0x3f) {
				r.ud5_known = false;
				r.pgm_known = false;
			} else if (op == 0x11 && len >= 4 && (p[1] & 0xfu) == 1u) {
				r.base1 = (p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u);
			} else if (op == 0x16 && len >= 3 && r.pgm_known &&
			           ((static_cast<uint64_t>(r.pgm_lo) | (static_cast<uint64_t>(r.pgm_hi & 0xffu) << 32u)) << 8u) == 0x909939900ull) {
				g_aq424_n++;
				if (r.base1 == 0) {
					g_aq424_nobase++;
				} else if (!r.ud5_known) {
					g_aq424_unk++;
				} else {
					const uint32_t want = static_cast<uint32_t>((r.base1 + p[1]) >> 32u);
					if ((r.ud5 & 0xffffu) == want) {
						g_aq424_match++;
					} else if (g_aq424_mis++ == 0) {
						g_aq424_first_ud5 = r.ud5;
						g_aq424_first_hi  = want;
					}
				}
			}
		}
		i += len;
	}
	const uint64_t now = SoftCp::now_ns();
	if (g_aq424_n != 0 && now - g_aq424_last_ns >= 10000000000ull) {
		g_aq424_last_ns = now;
		std::fprintf(stderr,
		             "[bc5] exp 0424 (tag aq424c): t %.1f s: refit 0x909939900 dispatches %" PRIu64 ": USER_DATA_5 low 16 = argument high %" PRIu64
		             ", MISMATCH %" PRIu64 " (first: USER_DATA_5 %08x against high %x), unknown %" PRIu64 ", no SET_BASE %" PRIu64
		             "; acb queue state %s, %" PRIu64 " parts given it, %" PRIu64 " with no tracked queue\\n",
		             timing_now(), g_aq424_n, g_aq424_match, g_aq424_mis, g_aq424_first_ud5, g_aq424_first_hi, g_aq424_unk, g_aq424_nobase,
		             aq424_on() ? "ON" : "off", g_aq424_parts.load(), g_aq424_none.load());
	}
}
#endif
""")

f.sub("""	if (g_dev->wedged()) {
		return;
	}
	// Unthrottled: the game writes a DCB's register tables right before submitting it, and a
""", """	if (g_dev->wedged()) {
		return;
	}
#ifndef BC5_LEAN
	aq424_catch(ib, num_dwords, ring); // exp 0424 (tag aq424c): the refit's USER_DATA_5 against its argument address
#endif
	// Unthrottled: the game writes a DCB's register tables right before submitting it, and a
""")
f.save()
