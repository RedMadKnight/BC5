#!/usr/bin/env python3
r"""BC5 experiment 0428: way 2's private test build, edits to src/libs/bc5LleAgc.cpp of shared patch 700fd4c2 (unit md5
3e847e03, the same unit as 4945ef1b's). The maintainer's consent for way 2 through deployment, relayed by the top session
2026-11-16; exp 0427 for why a ring index alone does not carry a queue's state.
    mk0428.py <tree root>

Every edit must match exactly once (ed0419g.File). Behaviour switches are read with std::getenv, so the lean build reads
them too; counters and their lines are normal-build only (#ifndef BC5_LEAN), as the lean rule asks.

1. (tag w428) BC5_DIRECT_ACB_RINGS=<n>, 0..4 (unset, empty, "0": off, today's one GFX ring). n >= 1 turns ADR 0009's
   compute rings back on for the ring thread's acbs: each guest queue (t_queue_idx) gets a libdrm compute ring index
   (first seen, first served, modulo n). bc5::policy::compute_ring_refusal still keeps a buffer on the GFX ring, as in
   October; those are counted by reason.
2. (tag w428) Cross-ring waits stay for the GPU when the label's last pending write is on another ring (ADR 0009 waits
   step 3, "all", the setting of F178): ring_will_satisfy no longer requires the same ring when the switch is on. Only
   writes of jobs already submitted are pending, so the waits form no cycle (the October comment).
3. (tag w428) The game thread's dcb wait with the switch on, exp 0132's form without the held tail (ADR 0013's helpers
   are gone since build W): the head before the wait is split off and submitted, then the wait is kept for the GPU as
   soon as its writer is on a ring, or satisfied on the CPU, within 8 ms; otherwise the existing path below (its limit,
   "GIVEN UP"). Counted: kept, satisfied, not served, splits.
4. (tag aq424, exp 0424's mk0424.py edits 1a and 1b, unchanged) BC5_DIRECT_ACB_QUEUE_STATE: every acb part that
   dispatches gets its own guest queue's tracked SH 0x204-0x3ff (without COMPUTE_VMID) in front, from that queue's
   tracker at submit time; a queue with nothing tracked gets nothing and is counted (g_aq424_none).
5. (tag w428c, normal only) One stderr line at most every 10 s: jobs per ring, acbs kept on the GFX ring by reason, the
   queue -> ring map, the two-ring wait counts, aq424's parts and untracked parts."""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "0419-switch-cleanup"))
sys.path.insert(0, HERE)  # on the box ed0419g.py lies beside this script
from ed0419g import File

f = File(os.path.join(sys.argv[1], "src", "libs", "bc5LleAgc.cpp"))
f.gone("tag w428", "tag aq424")

# ---- 1. the switch, the queue -> ring map, the refusal count by reason --------------------------------------------------
f.sub("""static int compute_ring_env() {
	static const int v = [] {
		const char* e = BC5_DIAG_ENV("BC5_DIRECT_COMPUTE_RING");
		return e != nullptr ? std::atoi(e) : bc5::direct::kGfxRing;
	}();
	return v;
}
static std::atomic<uint64_t> g_comp_jobs {0}, g_comp_refused {0};
static thread_local int      t_ring = bc5::direct::kGfxRing; // the ring of the compute buffer being submitted
static int                   acb_ring(const uint32_t* ib, uint32_t num_dwords) {
	int ring = compute_ring_env();
	if (ring < 0) return bc5::direct::kGfxRing;
	const char* why = bc5::policy::compute_ring_refusal(std::span<const uint32_t>(ib, num_dwords));
	if (why == nullptr) return ring;
""", """// Experiment 0428 (tag w428): BC5_DIRECT_ACB_RINGS=<n>, way 2. 0 (unset, empty, "0") is today's one GFX ring; 1..4 put
// the ring thread's acbs on compute rings, each guest queue on its own libdrm ring index (modulo n). Read with
// std::getenv: the lean build reads it too. Exp 0427: a ring index is not a fixed hardware queue (the kernel's scheduler
// re-picks one when the index is idle), so the queue's compute state comes from aq424's prefix, not from the ring.
static int w428_rings() {
	static const int v = [] {
		const char* e = std::getenv("BC5_DIRECT_ACB_RINGS");
		int         n = e != nullptr && e[0] != 0 ? std::atoi(e) : 0;
		if (n < 0) n = 0;
		if (n > bc5::direct::kComputeRings) n = bc5::direct::kComputeRings;
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0428 (tag w428): acb rings %d%s\\n", n, n == 0 ? " (off: every acb on the GFX ring)" : " (compute rings, one per guest queue, cross-ring waits kept for the GPU)");
#endif
		return n;
	}();
	return v;
}
static std::mutex         g_w428_mu;
static std::map<int, int> g_w428_qring; // guest queue (t_queue_idx) -> libdrm compute ring index
static int                w428_queue_ring() {
	std::lock_guard lk(g_w428_mu);
	const auto      it = g_w428_qring.find(t_queue_idx);
	if (it != g_w428_qring.end()) return it->second;
	const int r = static_cast<int>(g_w428_qring.size()) % w428_rings();
	g_w428_qring.emplace(t_queue_idx, r);
	return r;
}
#ifndef BC5_LEAN
static std::map<std::string, uint64_t> g_w428_refused; // exp 0428 (tag w428c): acbs kept on the GFX ring, by reason
#endif
static int compute_ring_env() {
	static const int v = [] {
		if (w428_rings() > 0) return 0; // exp 0428 (tag w428)
		const char* e = BC5_DIAG_ENV("BC5_DIRECT_COMPUTE_RING");
		return e != nullptr ? std::atoi(e) : bc5::direct::kGfxRing;
	}();
	return v;
}
static std::atomic<uint64_t> g_comp_jobs {0}, g_comp_refused {0};
static thread_local int      t_ring = bc5::direct::kGfxRing; // the ring of the compute buffer being submitted
static int                   acb_ring(const uint32_t* ib, uint32_t num_dwords) {
	int ring = compute_ring_env();
	if (ring < 0) return bc5::direct::kGfxRing;
	if (w428_rings() > 1) ring = w428_queue_ring(); // exp 0428 (tag w428): this guest queue's ring index
	const char* why = bc5::policy::compute_ring_refusal(std::span<const uint32_t>(ib, num_dwords));
	if (why == nullptr) return ring;
#ifndef BC5_LEAN
	if (w428_rings() > 0) {
		std::lock_guard lk(g_w428_mu);
		g_w428_refused[why]++;
	}
#endif
""")

# ---- 2. cross-ring waits for the GPU --------------------------------------------------------------------------------------
f.sub("""	if (last->ring != ring) return false; // one ring since exp 0342: never taken (exp 0419, candidate G)
""", """	// exp 0428 (tag w428): with the acb rings on, a wait whose label's last pending write is on another ring stays for the GPU
	// (ADR 0009 waits step 3, "all", as F178); only jobs already submitted are pending, so the waits form no cycle.
	if (last->ring != ring && w428_rings() == 0) return false; // one ring since exp 0342 (exp 0419, candidate G)
""")

# ---- 3. the game thread's dcb wait on two rings (exp 0132's form, no held tail) -----------------------------------------
f.sub("""					// Run 123: the compute queue's blocked buffer waits for a
					// label this buffer writes — on the console the two run side by side and this one would
""", """					// Experiment 0428 (tag w428), exp 0132's form without ADR 0013's held tail (gone since build W): with the acb rings on,
					// the compute rings run beside this buffer, and a wait on a label that compute work writes is a real race. The head
					// goes at once (its label writes may be what the compute queue waits for), then the wait is kept for the GPU as soon
					// as its writer is on a ring, or satisfied on the CPU, within 8 ms; otherwise the path below and its limit.
					if (w428_rings() > 0 && on_game_thread() && std::strcmp(kind, "dcb") == 0 && (!g_dev || !g_dev->wedged()) && !wait_satisfied(p, op == 0x93)) {
						bool split = false;
						if (dry_here && i > start) {
							if ((start > 0 || prefix_all() || cs_used) && !full_prefix.empty()) submit_prefixed(full_prefix, ib + start, i - start);
							else submit_one(ib + start, i - start, kind);
							chain_flush(1); // ADR 0010: the head goes before the wait is polled
							full_prefix = prefix_of(*dry);
							start       = i;
							full_used   = true;
							split       = true;
							g_full_pieces++;
						}
						const uint64_t t1   = SoftCp::now_ns();
						bool           kept = false;
						while (!(ok = wait_satisfied(p, op == 0x93))) {
							if (ring_will_satisfy(p, op == 0x93, bc5::direct::kGfxRing)) {
								kept = true;
								break;
							}
							if (SoftCp::now_ns() - t1 >= 8'000'000ull) break;
							std::this_thread::sleep_for(std::chrono::microseconds(20));
						}
#ifndef BC5_LEAN
						static std::atomic<uint64_t> n_two {0};
						g_w428_two[kept ? 0 : (ok ? 1 : 2)]++;
						if (split) g_w428_two[3]++;
						if ((n_two++ & 0x3ffu) == 0)
							journal("two rings (exp 0428): %s %u dwords waits at %u on 0x%" PRIx64 ": %s after %.2f ms%s\\n", kind, num_dwords, i, label,
							        kept ? "kept for the GPU" : (ok ? "satisfied" : "NOT served"), static_cast<double>(SoftCp::now_ns() - t1) / 1e6, split ? ", head split off" : "");
#endif
						if (kept) {
							t_keep_waits.push_back(p);
							SoftCp::set_gpu_executed(p, len, {0});
							i += len;
							continue;
						}
						if (ok) {
							SoftCp::set_gpu_executed(p, len, {0});
							i += len;
							continue;
						}
						// not served within 8 ms: the path below (its limit)
					}
					// Run 123: the compute queue's blocked buffer waits for a
					// label this buffer writes — on the console the two run side by side and this one would
""")

# the two-ring wait counters, declared before the function that uses them (next to g_full_pieces)
f.sub("""static std::atomic<uint64_t> g_full_pieces {0}, g_full_ok {0}, g_full_failed {0};
""", """static std::atomic<uint64_t> g_full_pieces {0}, g_full_ok {0}, g_full_failed {0};
#ifndef BC5_LEAN
static std::atomic<uint64_t> g_w428_two[4] = {}; // exp 0428 (tag w428c): dcb waits on two rings: kept for the GPU, satisfied, not served; heads split
#endif
""")

# ---- 4. aq424 (exp 0424 mk0424.py 1a and 1b, unchanged) -----------------------------------------------------------------
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

# ---- 5. the counters' line (normal only), at the submit site that already counts compute-ring jobs ----------------------
f.sub("""	if (qring != bc5::direct::kGfxRing && (g_comp_jobs++ & 0xffffu) == 0) {
""", """#ifndef BC5_LEAN
	if (w428_rings() > 0) { // exp 0428 (tag w428c): jobs per ring and the rest, one stderr line at most every 10 s
		static std::atomic<uint64_t> jobs[bc5::direct::kComputeRings + 1] = {};
		static std::atomic<uint64_t> last_ns {0};
		jobs[qring == bc5::direct::kGfxRing ? bc5::direct::kComputeRings : qring]++;
		const uint64_t now = SoftCp::now_ns();
		uint64_t       was = last_ns.load();
		if (now - was >= 10'000'000'000ull && last_ns.compare_exchange_strong(was, now)) {
			std::string q, why;
			{
				std::lock_guard lk(g_w428_mu);
				for (const auto& [k, v]: g_w428_qring) q += " " + std::to_string(k) + "->" + std::to_string(v);
				for (const auto& [k, v]: g_w428_refused) why += " " + k + ":" + std::to_string(v);
			}
			std::fprintf(stderr,
			             "[bc5] exp 0428 (tag w428c): t %.1f s: jobs gfx %" PRIu64 " comp0 %" PRIu64 " comp1 %" PRIu64 " comp2 %" PRIu64 " comp3 %" PRIu64
			             "; acbs kept on gfx:%s; queue->ring:%s; dcb waits on two rings: kept %" PRIu64 " satisfied %" PRIu64 " NOT served %" PRIu64
			             " heads split %" PRIu64 "; aq424 %s, parts given state %" PRIu64 ", parts with no tracked queue %" PRIu64 "\\n",
			             timing_now(), jobs[4].load(), jobs[0].load(), jobs[1].load(), jobs[2].load(), jobs[3].load(), why.empty() ? " none" : why.c_str(),
			             q.empty() ? " none" : q.c_str(), g_w428_two[0].load(), g_w428_two[1].load(), g_w428_two[2].load(), g_w428_two[3].load(),
			             aq424_on() ? "ON" : "off", g_aq424_parts.load(), g_aq424_none.load());
		}
	}
#endif
	if (qring != bc5::direct::kGfxRing && (g_comp_jobs++ & 0xffffu) == 0) {
""")
f.save()
