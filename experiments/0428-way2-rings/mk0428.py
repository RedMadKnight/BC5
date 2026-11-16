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
// Iteration 2 (the smoke w428Q1: the title touches 56 guest queue slots at start, so an index map put its busy queues
// together on ring 0, 169,922 jobs against 14 on each other ring): every queue starts on ring 0; a queue whose acb count
// reaches 256 is busy and moves ONCE to the next ring of the rotation 1, 2, 3, 0, ... Before the move this thread's
// chain is flushed and every ring is waited idle (2 s at most), so the queue's earlier jobs on ring 0 are done before
// its first job on the new ring (its order holds). One move per busy queue, so the wait is paid a few times per run.
struct W428Queue {
	uint64_t n    = 0;
	int      ring = 0;
	bool     busy = false;
};
static std::mutex               g_w428_mu;
static std::map<int, W428Queue> g_w428_qring; // guest queue (t_queue_idx) -> its count and libdrm compute ring index
static int                      g_w428_busy = 0;
static std::atomic<uint64_t>    g_w428_moves {0}, g_w428_move_late {0};
static void                     chain_flush(int why); // ADR 0010, defined below
static int                      w428_queue_ring() {
	int prev = 0, now = 0;
	{
		std::lock_guard lk(g_w428_mu);
		W428Queue&      e = g_w428_qring[t_queue_idx];
		e.n++;
		if (e.busy || e.n < 256) return e.ring;
		e.busy = true;
		prev   = e.ring;
		e.ring = (++g_w428_busy) % w428_rings();
		now    = e.ring;
	}
	if (now != prev) {
		chain_flush(2); // ring/class
		const bool idle = !g_dev || g_dev->wait_idle(2'000'000'000ull);
		g_w428_moves++;
		if (!idle) g_w428_move_late++;
	}
	return now;
}
#ifndef BC5_LEAN
static std::map<std::string, uint64_t> g_w428_refused; // exp 0428 (tag w428c): acbs kept on the GFX ring, by reason
#endif
// Exp 0428 step 2: BC5_DIRECT_ACB_MEC_INDIRECT (read with std::getenv: lean too). The backend refuses every compute-form
// DISPATCH_INDIRECT on the MEC (exp 0290, kMecIndirectCheckVerified = false) because the CP's argument check was not
// verified there. Exp 0428's userdata-rings --cp-check ran the check (indirect_check::apply, compute_ring = true, the
// default limits) around 18 REAL compute-form DISPATCH_INDIRECTs on compute rings 0..2 on kernel 7.3.3: 6 sane triples
// ran, 12 over-limit triples were skipped, 0 kernel lines (raw/cp-run.txt). With the switch on, a buffer refused ONLY for
// that reason goes to its compute ring; the refusal is asked again with every DISPATCH_INDIRECT NOP-ed, so any other
// reason (graphics-only packet, a PARTIAL_TG_EN dispatch, checked here for the NOP-ed ones) still keeps it on the GFX ring.
static bool w428_mec_ok() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_DIRECT_ACB_MEC_INDIRECT");
		return e != nullptr && e[0] != 0 && std::strcmp(e, "0") != 0;
	}();
	return v;
}
#ifndef BC5_LEAN
static std::atomic<uint64_t> g_w428_mec_moved {0}; // exp 0428 (tag w428c): acbs sent to a compute ring by the switch
#endif
static const char* w428_mec_refusal(const uint32_t* ib, uint32_t n, const char* why) {
	if (why == nullptr || !w428_mec_ok() || std::strcmp(why, "indirect dispatch (MEC check unverified)") != 0) return why;
	std::vector<uint32_t> c(ib, ib + n);
	for (uint32_t i = 0; i < n;) {
		const uint32_t h = c[i], type = h >> 30u;
		uint32_t       len = 1;
		if (type == 3 || type == 0) {
			const uint32_t k = (h >> 16u) & 0x3fffu;
			len              = k == 0x3fffu ? 1 : k + 2;
		}
		if (i + len > n) break;
		if (type == 3 && ((h >> 8u) & 0xffu) == 0x16u) {
			if (len >= 4 && (c[i + 3] & 0x2u) != 0 && (c[i + 3] & 0x20u) == 0) return "PARTIAL_TG_EN dispatch";
			c[i] = 0xC0000000u | (h & 0x3fff0000u) | (0x10u << 8u); // a NOP of the same length
		}
		i += len;
	}
	const char* rest = bc5::policy::compute_ring_refusal(std::span<const uint32_t>(c.data(), c.size()));
#ifndef BC5_LEAN
	if (rest == nullptr) g_w428_mec_moved++;
#endif
	return rest;
}
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
	why             = w428_mec_refusal(ib, num_dwords, why); // exp 0428 step 2 (BC5_DIRECT_ACB_MEC_INDIRECT)
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
						// exp 0428 iterations 3-4 (BC5_DIRECT_ACB_SPLIT_LATE, std::getenv: lean too). The 15:09 hang of the maintainer's play
						// (a GE stall at a partial flush, all compute rings idle) was in a split piece behind a full state prefix, and
						// iteration 2 split ~18 k times per run although ~97 % of those waits were kept for the GPU right after. Iteration
						// 3 (=1) kept a wait whose writer was already on a ring: 0 such waits in w428L1 (17,591 splits), so the writer is the
						// thread's own earlier GFX work, held in its chain or earlier in this IB, which reaches a ring only with the split.
						// Iteration 4 (=2): (a) this IB writes the label before the wait (WRITE_DATA, or RELEASE_MEM with 32/64-bit data)
						// with a value that satisfies it: the GFX ring runs that write first, so the wait is kept with no split and no
						// flush; (b) else the thread's held chain (its earlier buffers) is submitted, with no split of this buffer, and the
						// wait is kept if its writer is now on a ring. Only otherwise the split below. Both are in GPU order on one ring.
						static const int split_late = [] {
							const char* e = std::getenv("BC5_DIRECT_ACB_SPLIT_LATE");
							return e != nullptr && e[0] != 0 ? std::atoi(e) : 0;
						}();
						if (split_late >= 1) {
							int how = 0; // 1 writer on a ring, 2 written earlier in this IB, 3 writer on a ring after the chain went
							if (ring_will_satisfy(p, op == 0x93, bc5::direct::kGfxRing)) how = 1;
							else if (split_late >= 2 && w428_ib_writes_satisfy(ib, i, p, op == 0x93)) how = 2;
							else if (split_late >= 2) {
								chain_flush(1); // ADR 0010: the thread's earlier buffers go; this one is not split
								if (ring_will_satisfy(p, op == 0x93, bc5::direct::kGfxRing)) how = 3;
							}
							if (how != 0) {
#ifndef BC5_LEAN
								g_w428_two[4]++;
								g_w428_late[how]++;
#endif
								t_keep_waits.push_back(p);
								SoftCp::set_gpu_executed(p, len, {0});
								i += len;
								continue;
							}
#ifndef BC5_LEAN
							g_w428_late[0]++;
							static std::atomic<uint32_t> n_left {0};
							if (n_left++ < 40) {
								char pend[160];
								describe_pending(label, pend, sizeof(pend));
								journal("two rings (exp 0428 split-late): %s %u dwords, wait at %u on 0x%" PRIx64 " still splits: %s\\n", kind, num_dwords, i, label, pend);
							}
#endif
						}
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
						(void)split; // only the normal build's counters read it
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
static std::atomic<uint64_t> g_w428_two[5] = {}; // exp 0428 (tag w428c): dcb waits on two rings: kept for the GPU, satisfied, not served; heads split; kept with no split (iteration 3)
#endif
#ifndef BC5_LEAN
static std::atomic<uint64_t> g_w428_late[4] = {}; // exp 0428 iteration 4: still split; kept: writer on a ring, written earlier in the IB, on a ring after the chain went
#endif
// Exp 0428 iteration 4: does this IB write the wait's label before dword `at` with a value that satisfies the wait? The
// last such write counts. WRITE_DATA (0x37: control, address lo, hi, data...) and RELEASE_MEM (0x49: event, DATA_SEL in
// bits 31:29 of dword 2 (1: 32-bit, 2: 64-bit), address lo, hi, data lo, hi), as the unit's own label scans read them;
// a RELEASE_MEM with another DATA_SEL or anything not followed (INDIRECT_BUFFER) makes the answer "no".
static bool w428_ib_writes_satisfy(const uint32_t* ib, uint32_t at, const uint32_t* p, bool is64) {
	const uint64_t a     = (p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u);
	bool           found = false, known = false;
	uint64_t       v     = 0;
	for (uint32_t k = 0; k < at;) {
		const uint32_t h = ib[k], t = h >> 30u;
		uint32_t       lk = 1;
		if (t == 3 || t == 0) {
			const uint32_t c = (h >> 16u) & 0x3fffu;
			lk               = c == 0x3fffu ? 1 : c + 2;
		}
		if (k + lk > at) break;
		if (t == 3) {
			const uint32_t  op = (h >> 8u) & 0xffu;
			const uint32_t* q  = ib + k;
			if (op == 0x3f || op == 0x33) return false; // an IB2 may write it: not followed
			if (op == 0x37 && lk >= 5 && ((q[2] & ~3u) | (static_cast<uint64_t>(q[3] & 0xffffu) << 32u)) == a) {
				found = known = true;
				v             = q[4] | (lk >= 6 ? static_cast<uint64_t>(q[5]) << 32u : 0ull);
			} else if (op == 0x49 && lk >= 7 && ((q[3] & ~3u) | (static_cast<uint64_t>(q[4] & 0xffffu) << 32u)) == a) {
				const uint32_t ds = q[2] >> 29u;
				found             = true;
				known             = ds == 1 || ds == 2;
				v                 = q[5] | (ds == 2 ? static_cast<uint64_t>(q[6]) << 32u : 0ull);
			}
		}
		k += lk;
	}
	if (!found || !known) return false;
	const uint32_t function = p[1] & 7u;
	if (is64) {
		const uint64_t ref = p[4] | (static_cast<uint64_t>(p[5]) << 32u), mask = p[6] | (static_cast<uint64_t>(p[7]) << 32u);
		const uint64_t vm = v & mask, rm = ref & mask;
		switch (function) {
			case 1: return vm < rm;
			case 2: return vm <= rm;
			case 3: return vm == rm;
			case 4: return vm != rm;
			case 5: return vm >= rm;
			case 6: return vm > rm;
			default: return false;
		}
	}
	return SoftCp::compare(function, static_cast<uint32_t>(v), p[5], p[4]);
}
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
	// exp 0428 (cost candidate, BC5_DIRECT_ACB_STATE_NO_WALK, std::getenv: lean too): `at` only names the inheriting
	// dispatch in the journal line below, so the walk can go; -1 is printed then.
	static const bool     no_walk = [] {
		const char* e = std::getenv("BC5_DIRECT_ACB_STATE_NO_WALK");
		return e != nullptr && e[0] != 0 && std::strcmp(e, "0") != 0;
	}();
	const int             at  = no_walk ? -1 : cs_inherit_at(part, n, *g_dev->sorted_mappings());
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
				for (const auto& [k, v]: g_w428_qring)
					if (v.busy) q += " " + std::to_string(k) + "->" + std::to_string(v.ring) + "(" + std::to_string(v.n) + ")";
				q += " moves " + std::to_string(g_w428_moves.load()) + " not-idle-in-2s " + std::to_string(g_w428_move_late.load());
				for (const auto& [k, v]: g_w428_refused) why += " " + k + ":" + std::to_string(v);
			}
			std::fprintf(stderr,
			             "[bc5] exp 0428 (tag w428c): t %.1f s: jobs gfx %" PRIu64 " comp0 %" PRIu64 " comp1 %" PRIu64 " comp2 %" PRIu64 " comp3 %" PRIu64
			             "; acbs kept on gfx:%s; queue->ring:%s; dcb waits on two rings: kept %" PRIu64 " satisfied %" PRIu64 " NOT served %" PRIu64
			             " heads split %" PRIu64 " kept-without-split %" PRIu64 " (on a ring %" PRIu64 ", in the IB %" PRIu64 ", after the chain %" PRIu64 ", still split %" PRIu64 "); aq424 %s, parts given state %" PRIu64 ", parts with no tracked queue %" PRIu64 "; mec-indirect switch %s, acbs moved %" PRIu64 "\\n",
			             timing_now(), jobs[4].load(), jobs[0].load(), jobs[1].load(), jobs[2].load(), jobs[3].load(), why.empty() ? " none" : why.c_str(),
			             q.empty() ? " none" : q.c_str(), g_w428_two[0].load(), g_w428_two[1].load(), g_w428_two[2].load(), g_w428_two[3].load(), g_w428_two[4].load(), g_w428_late[1].load(), g_w428_late[2].load(), g_w428_late[3].load(), g_w428_late[0].load(),
			             aq424_on() ? "ON" : "off", g_aq424_parts.load(), g_aq424_none.load(), w428_mec_ok() ? "ON" : "off", g_w428_mec_moved.load());
		}
	}
#endif
	if (qring != bc5::direct::kGfxRing && (g_comp_jobs++ & 0xffffu) == 0) {
""")
f.save()
