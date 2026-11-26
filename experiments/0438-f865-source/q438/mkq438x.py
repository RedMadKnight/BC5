#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438 (tags labelmap, q438ng): two steps on the stacked unit stack438.cpp (mkstack438.py's output).
Usage: python -I mkq438x.py IN.cpp OUT.cpp   (IN: q438/stack438.cpp, md5 29d02cb5f885f07e60d8eee055638f38)

labelmap (the first title, SUBMITQ=1: 213 "early-registered write ... never reached the ring" lines per run). The early scans
(q438_scan for a queued chain, r438_scan for bc5-ring's slice) took every label write; submit_now's filter NOPs a packet
one of whose memory operands opt.mapped rejects (backend policy.cpp, the memory_operands loop), and register_label_writes
registers only the packets that passed. So an early write to an address with no GPU mapping never turned real.
  LM1 the scans' mapping snapshot (thread-local, nullptr: no check) and counters, beside r438's state;
  LM2 r438_scan leaves out a packet lw_packet_mapped rejects (with a snapshot only: inside r438_begin, which runs only
      with BC5_0438_EARLYREG on);
  LM3 r438_begin takes one sorted_mappings() snapshot for its scans, only with BC5_0438_R438_LWM=1 (off unless "1",
      read once): with it off r438 behaves as the baked unit (2e6168de);
  LM4 q438_scan the same; LM5 q438_early_begin takes the snapshot;
  LM6 label_write_mapped (the filter's opt.mapped predicate, moved, unchanged) and lw_packet_mapped (the filter's loop
      over memory_operands, bytes 0 as 4) before submit_now; opt.mapped calls label_write_mapped.

q438ng (the hang hypothesis): bc5-ring's acb_ready decides an acb wait without a queued chain's write of its label:
ring_will_satisfy skips early entries off the game threads, and a stale value in memory passes the wait at once. At the
submit, ho430's F10/F16/F18 wait for the queued writer only up to their bounds (2 + 50 + 50 ms) and then decide without it.
  NG1 acb_wait_unready: acb_ready's test of one wait, factored out unchanged; with Q438 on, also unready while a queued
      chain writes the label (q438_writer_queued), so the acb is deferred as for any unready wait;
  NG2 acb_ready calls it;
  NG3 q438_writer_queued in the q438 block.
ng438 (normal build only): counts of the gate's two tests, INFLIGHT_NG's and OPEN_NG's apart (holds, longest, releases),
  the shared 10-s fallback releases (each with a BUG line) and busy tries; a 60-s line while either switch is on.
held438 (BC5_0438_HELD_EARLY, off unless "1"): an acb acb_ready holds registers its remaining writes early, so a
  game-thread wait on one waits instead of giving up after 8 ms; they go when the acb is submitted.
ngcount: one live count of writers that can be pending (slots with a flight or open-chain write set, early entries),
  kept while INFLIGHT_NG or OPEN_NG is on; at 0 the gate's full tests are skipped (one atomic load).
open_ng (BC5_0438_OPEN_NG, off unless "1"): acb_wait_unready also holds the acb while a registered slot's open chain
  (appended, not taken) writes the label: the state inflight_ng_writer and q438_writer_queued do not see.
wd438 (normal build only, any switch): the last 256 acb wait decisions with the label's writer state, appended to the
  fault record's journal-tail.txt as "wd438:" lines.
inflight_ng (BC5_0438_INFLIGHT_NG, off unless "1"): the same window without the queue. A game thread's chain taken and in
its submit_now (kernel call in flight) has its writes only in f10_flight until it returns; bc5-ring's acb_ready then
passes a stale value. acb_wait_unready also holds the acb while any registered slot has the label in flight, or an early
entry (r438's or Q438's) of the label is in g_plw.
With BC5_0438_SUBMITQ, BC5_0438_R438_LWM and BC5_0438_INFLIGHT_NG off: q438_writer_queued and inflight_ng_writer are never
called and no snapshot is taken (the baked unit's behaviour).
Every replacement must match exactly once, or nothing is written. Writes OUT (LF) and prints both md5s.
"""
import hashlib
import sys

IN, OUT = sys.argv[1], sys.argv[2]
src = open(IN, 'rb').read()
assert hashlib.md5(src).hexdigest() == '29d02cb5f885f07e60d8eee055638f38', 'not q438/stack438.cpp (29d02cb5)'
s = src.decode('utf-8')
assert '\r' not in s


def rep(old, new):
    global s
    n = s.count(old)
    assert n == 1, f'{n} matches for: {old[:100]!r}'
    s = s.replace(old, new)


# LM1
rep("static thread_local uint64_t              t_q438_early = 0;  // that entry's own early id (it is not reordered by its own writes)\n",
    "static thread_local uint64_t              t_q438_early = 0;  // that entry's own early id (it is not reordered by its own writes)\n"
    "// exp 0438 (labelmap): the early scans read the filter's operand check (label_write_mapped, defined before submit_now)\n"
    "static thread_local const bc5::direct::MappingIndex* t_lwm = nullptr; // the scan's mapping snapshot (nullptr: no check)\n"
    "static thread_local uint64_t              t_lwm_fl = 0;      // the crumbs' area at that snapshot\n"
    "static std::atomic<uint64_t>              g_lwm_skipped {0}; // label-write packets the scans left out: the filter NOPs them\n"
    "static std::atomic<uint64_t>              g_q438_ng {0};     // exp 0438 (q438ng): acb waits held back for a queued writer\n"
    "static bool     lw_packet_mapped(const bc5::direct::MappingIndex& maps, uint64_t fl_area, const uint32_t* p, uint32_t len);\n"
    "static bool r438_lwm_on() { // exp 0438 (labelmap): r438_scan reads the filter's check, BC5_0438_R438_LWM, on only when \"1\"\n"
    "\tstatic const bool v = [] {\n"
    "\t\tconst char* e = std::getenv(\"BC5_0438_R438_LWM\");\n"
    "\t\treturn e != nullptr && e[0] == '1' && e[1] == 0;\n"
    "\t}();\n"
    "\treturn v;\n"
    "}\n"
    "static bool inflight_ng_on() { // exp 0438 (inflight_ng): BC5_0438_INFLIGHT_NG, on only when \"1\"\n"
    "\tstatic const bool v = [] {\n"
    "\t\tconst char* e = std::getenv(\"BC5_0438_INFLIGHT_NG\");\n"
    "\t\treturn e != nullptr && e[0] == '1' && e[1] == 0;\n"
    "\t}();\n"
    "\treturn v;\n"
    "}\n"
    "static std::atomic<uint64_t> g_inflight_ng {0}; // exp 0438 (inflight_ng): acb waits held for a writer in flight\n"
    "static uint64_t fl_crumbs_area();\n")

# LM2
rep("\t\t\t\tif ((h >> 30u) == 3) { // as register_label_writes reads them\n",
    "\t\t\t\tif (t_lwm != nullptr && (h >> 30u) == 3 && !lw_packet_mapped(*t_lwm, t_lwm_fl, w, len)) { // exp 0438 (labelmap): the filter NOPs it\n"
    "\t\t\t\t\tg_lwm_skipped++;\n"
    "\t\t\t\t\tq += len;\n"
    "\t\t\t\t\tcontinue;\n"
    "\t\t\t\t}\n"
    "\t\t\t\tif ((h >> 30u) == 3) { // as register_label_writes reads them\n")

# LM3
rep("\tstd::vector<PendingLabelWrite> found;\n\tr438_scan(s1, n1, found);\n\tif (s2 != nullptr) r438_scan(s2, n2, found);\n",
    "\tstd::vector<PendingLabelWrite> found;\n"
    "\tconst auto lwm = g_dev && r438_lwm_on() ? g_dev->sorted_mappings() : nullptr; // exp 0438 (labelmap): one snapshot per scan, BC5_0438_R438_LWM=1\n"
    "\tt_lwm    = lwm.get();\n"
    "\tt_lwm_fl = lwm ? fl_crumbs_area() : 0;\n"
    "\tr438_scan(s1, n1, found);\n\tif (s2 != nullptr) r438_scan(s2, n2, found);\n"
    "\tt_lwm = nullptr;\n")

# LM4
rep("\t\tif ((h >> 30u) == 3) {\n\t\t\tif (op == 0x49 && len >= 8) {\n",
    "\t\tif (t_lwm != nullptr && (h >> 30u) == 3 && !lw_packet_mapped(*t_lwm, t_lwm_fl, w, len)) { // exp 0438 (labelmap): the filter NOPs it\n"
    "\t\t\tg_lwm_skipped++;\n"
    "\t\t\tq += len;\n"
    "\t\t\tcontinue;\n"
    "\t\t}\n"
    "\t\tif ((h >> 30u) == 3) {\n\t\t\tif (op == 0x49 && len >= 8) {\n")

# LM5
rep("\tstd::vector<PendingLabelWrite> found;\n\tq438_scan(c.buf, found);\n",
    "\tstd::vector<PendingLabelWrite> found;\n"
    "\tconst auto lwm = g_dev ? g_dev->sorted_mappings() : nullptr; // exp 0438 (labelmap): one snapshot per scan\n"
    "\tt_lwm    = lwm.get();\n"
    "\tt_lwm_fl = lwm ? fl_crumbs_area() : 0;\n"
    "\tq438_scan(c.buf, found);\n"
    "\tt_lwm = nullptr;\n")

# LM6
rep("\topt.mapped = [&maps_p, fl_area](uint64_t a, uint64_t bytes) {\n"
    "\t\tif (fl_area != 0 && a >= fl_area && a + bytes <= fl_area + kFlAreaBytes) return true; // experiment 0404\n"
    "\t\tif (ge_probe_range().second != 0 && g_dev && g_dev->gds_shadow_va() != 0 && a >= g_dev->gds_shadow_va() && a + bytes <= g_dev->gds_shadow_va() + 65536) return true; // experiment 0160\n"
    "\t\treturn covered_sorted(*maps_p, a, bytes);\n"
    "\t};\n",
    "\topt.mapped = [&maps_p, fl_area](uint64_t a, uint64_t bytes) { return label_write_mapped(*maps_p, fl_area, a, bytes); }; // exp 0438 (labelmap): the early scans read the same check\n")
rep("static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, int ring, const Chain* chain) {\n",
    "// ---- BC5 experiment 0438 (tag labelmap): submit_now's operand check, one source of truth for the filter and the early scans\n"
    "// The filter's opt.mapped, unchanged: the crumbs' area (experiment 0404), the GE probe's slots (experiment 0160), the mappings.\n"
    "static bool label_write_mapped(const bc5::direct::MappingIndex& maps, uint64_t fl_area, uint64_t a, uint64_t bytes) {\n"
    "\tif (fl_area != 0 && a >= fl_area && a + bytes <= fl_area + kFlAreaBytes) return true; // experiment 0404\n"
    "\tif (ge_probe_range().second != 0 && g_dev && g_dev->gds_shadow_va() != 0 && a >= g_dev->gds_shadow_va() && a + bytes <= g_dev->gds_shadow_va() + 65536) return true; // experiment 0160\n"
    "\treturn covered_sorted(maps, a, bytes);\n"
    "}\n"
    "// A packet passes the filter's operand check: backend policy.cpp's loop over memory_operands (a 0-byte operand checked as 4).\n"
    "static bool lw_packet_mapped(const bc5::direct::MappingIndex& maps, uint64_t fl_area, const uint32_t* p, uint32_t len) {\n"
    "\tfor (const auto& [a, bytes]: bc5::policy::memory_operands(p, len))\n"
    "\t\tif (!label_write_mapped(maps, fl_area, a, bytes == 0 ? 4 : bytes)) return false;\n"
    "\treturn true;\n"
    "}\n"
    "// ---- end of exp 0438 (tag labelmap)\n"
    "static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, int ring, const Chain* chain) {\n")

# NG1 + NG2
rep("static bool acb_ready(const uint32_t* ib, uint32_t num_dwords) {\n\tconst int         ring       = acb_ring(ib, num_dwords); // ADR 0009\n",
    "// ---- BC5 experiment 0438 (tag q438ng): acb_ready's test of one wait. Today's: not satisfied, and no pending write will\n"
    "// satisfy it. With Q438 on, also while a queued chain writes the label: that write is not in g_plw for this thread\n"
    "// (ring_will_satisfy skips early entries off the game threads) and a stale value in memory would pass the wait.\n"
    "static bool q438_writer_queued(uint64_t label);\n"
    "static bool inflight_ng_writer(uint64_t label);\n"
    "static bool acb_wait_unready(const uint32_t* p, bool is64, uint64_t label, int ring) {\n"
    "\tif (!wait_satisfied(p, is64) && !ring_will_satisfy(p, is64, ring)) return true;\n"
    "\tif (inflight_ng_on() && inflight_ng_writer(label)) return true; // exp 0438 (inflight_ng): a writer taken, not yet registered for real\n"
    "\treturn q438_on() && q438_writer_queued(label);\n"
    "}\n"
    "// ---- end of exp 0438 (tag q438ng)\n"
    "static bool acb_ready(const uint32_t* ib, uint32_t num_dwords) {\n\tconst int         ring       = acb_ring(ib, num_dwords); // ADR 0009\n")
rep("\t\t\t\tif (i >= done && std::find(written.begin(), written.end(), label) == written.end() && !wait_satisfied(p, op == 0x93) &&\n"
    "\t\t\t\t    !ring_will_satisfy(p, op == 0x93, ring)) {\n",
    "\t\t\t\tif (i >= done && std::find(written.begin(), written.end(), label) == written.end() && acb_wait_unready(p, op == 0x93, label, ring)) { // exp 0438 (q438ng)\n")

# NG3
rep("// ---- end of exp 0438 (tag q438) ---",
    "// exp 0438 (tag q438ng): a queued chain's early write of the label is pending (not yet submittable)\n"
    "static bool q438_writer_queued(uint64_t label) {\n"
    "\tstd::lock_guard lk(g_plw_mutex);\n"
    "\tfor (const auto& w: g_plw)\n"
    "\t\tif (w.label == label && (w.seq & kQ438Early) == kQ438Early) {\n"
    "\t\t\tg_q438_ng++;\n"
    "\t\t\treturn true;\n"
    "\t\t}\n"
    "\treturn false;\n"
    "}\n"
    "// exp 0438 (tag inflight_ng): a writer of the label is taken but not yet registered for real: an early entry (r438's\n"
    "// slice, Q438's queued chain) in g_plw, or a registered slot's chain in its submit_now (its F10 flight set). A busy\n"
    "// registry or slot counts as in flight, as in F10's f10_pending: the acb is decided at the next poll.\n"
    "static bool inflight_ng_writer(uint64_t label) {\n"
    "\t{\n"
    "\t\tstd::lock_guard lk(g_plw_mutex);\n"
    "\t\tfor (const auto& w: g_plw)\n"
    "\t\t\tif (w.label == label && (w.seq & kR438Early) != 0) {\n"
    "\t\t\t\tg_inflight_ng++;\n"
    "\t\t\t\treturn true;\n"
    "\t\t\t}\n"
    "\t}\n"
    "\tif (!g_f10_reg_mu.try_lock()) return true;\n"
    "\tbool in = false;\n"
    "\tfor (ChainSlot* cs: g_f10_reg) {\n"
    "\t\tif (!cs->mu.try_lock()) {\n"
    "\t\t\tin = true;\n"
    "\t\t\tbreak;\n"
    "\t\t}\n"
    "\t\tin = std::find(cs->f10_flight.begin(), cs->f10_flight.end(), label) != cs->f10_flight.end();\n"
    "\t\tcs->mu.unlock();\n"
    "\t\tif (in) break;\n"
    "\t}\n"
    "\tg_f10_reg_mu.unlock();\n"
    "\tif (in) g_inflight_ng++;\n"
    "\treturn in;\n"
    "}\n"
    "// ---- end of exp 0438 (tag q438) ---")

# ---- ng438 + wd438 (follow-up steps on the generated text; normal build only, #ifndef BC5_LEAN) ---------------------------
# ng438: what BC5_0438_INFLIGHT_NG's gate does, counted, with a 60-s line while the switch is on (zeros when nothing was held).
# wd438: the last 256 acb wait decisions (bc5-ring's gate, after ho430::at_wait, kept for the GPU, met at submit / served /
# given up), each with the writer state of its label at that moment; appended to the fault record's journal-tail.txt.
OLD_UNREADY = (
    "static bool acb_wait_unready(const uint32_t* p, bool is64, uint64_t label, int ring) {\n"
    "\tif (!wait_satisfied(p, is64) && !ring_will_satisfy(p, is64, ring)) return true;\n"
    "\tif (inflight_ng_on() && inflight_ng_writer(label)) return true; // exp 0438 (inflight_ng): a writer taken, not yet registered for real\n"
    "\treturn q438_on() && q438_writer_queued(label);\n"
    "}\n")
NEW_UNREADY = r'''#ifndef BC5_LEAN
// exp 0438 (tag ng438): what the gate's two tests do (normal build only), per kind: 0 BC5_0438_INFLIGHT_NG (a writer in
// flight), 1 BC5_0438_OPEN_NG (a writer in an open chain). A hold is per label and kind, from its first held test to the
// first test of that kind that finds no writer (a release), or to the queue consumer's 10-s fallback (a release with a BUG
// line, compare-only; shared). Busy (shared): a try of the registry or a slot that failed.
static std::mutex                   g_ng438_mu;
static std::map<uint64_t, uint64_t> g_ng438_held[2]; // label -> its first hold (ns), per kind
static std::atomic<uint64_t>        g_ng438_holds[2], g_ng438_rel[2], g_ng438_max[2], g_ng438_fb {0}, g_ng438_busy {0};
static void ng438_note(int kind, uint64_t label, bool in) {
	const uint64_t  now = SoftCp::now_ns();
	std::lock_guard lk(g_ng438_mu);
	auto&           held = g_ng438_held[kind & 1];
	const auto      it   = held.find(label);
	if (in) {
		if (it == held.end()) {
			held.emplace(label, now);
			g_ng438_holds[kind & 1]++;
		}
		return;
	}
	if (it == held.end()) return;
	const uint64_t d = now - it->second;
	for (uint64_t m = g_ng438_max[kind & 1].load(); d > m && !g_ng438_max[kind & 1].compare_exchange_weak(m, d);) {
	}
	g_ng438_rel[kind & 1]++;
	held.erase(it);
}
static void ng438_fallback(uint64_t label) { // the queue consumer let an unready acb go after 10 s
	uint64_t held = 0;
	bool     any  = false;
	{
		std::lock_guard lk(g_ng438_mu);
		for (auto& m: g_ng438_held) {
			const auto it = m.find(label);
			if (it == m.end()) continue;
			held = std::max<uint64_t>(held, SoftCp::now_ns() - it->second);
			m.erase(it);
			any = true;
		}
	}
	if (!any) return;
	const uint64_t k = g_ng438_fb++;
	journal("ng438 (exp 0438): BUG: the acb waiting on 0x%" PRIx64 " went by the 10-s fallback after %.1f ms held for a writer in flight or in an open chain (%" PRIu64 " so far)\n", label, static_cast<double>(held) / 1e6, k + 1);
}
static void ng438_line() {
	journal("ng438 (exp 0438): t %.1f s: in flight (INFLIGHT_NG %d): held %" PRIu64 ", longest %.3f ms, released %" PRIu64 "; open chain (OPEN_NG %d): held %" PRIu64 ", longest %.3f ms, released %" PRIu64 "; by the 10-s fallback %" PRIu64 "; busy registry or slot %" PRIu64 "\n",
	        timing_now(), inflight_ng_on() ? 1 : 0, g_ng438_holds[0].load(), static_cast<double>(g_ng438_max[0].load()) / 1e6, g_ng438_rel[0].load(), open_ng_on() ? 1 : 0, g_ng438_holds[1].load(),
	        static_cast<double>(g_ng438_max[1].load()) / 1e6, g_ng438_rel[1].load(), g_ng438_fb.load(), g_ng438_busy.load());
}
static void ng438_tick() { // from register_label_writes: every 60 s while BC5_0438_INFLIGHT_NG=1 or BC5_0438_OPEN_NG=1
	if (!inflight_ng_on() && !open_ng_on()) return;
	static std::atomic<uint64_t> last {0};
	const uint64_t               now = SoftCp::now_ns();
	uint64_t                     l   = last.load();
	if (l == 0) {
		last.compare_exchange_strong(l, now);
		return;
	}
	if (now - l < 60'000'000'000ull || !last.compare_exchange_strong(l, now)) return;
	ng438_line();
}
#endif
// exp 0438 (q438ng, inflight_ng, wd438): ib / n / off: the acb and the wait's offset, for wd438's record (acb_ready's call).
static bool acb_wait_unready(const uint32_t* p, bool is64, uint64_t label, int ring, const uint32_t* ib = nullptr, uint32_t n = 0, uint32_t off = 0) {
	bool unready = !wait_satisfied(p, is64) && !ring_will_satisfy(p, is64, ring);
	if (!unready && inflight_ng_on()) { // exp 0438 (inflight_ng): a writer taken, not yet registered for real
		const bool in = inflight_ng_writer(label);
#ifndef BC5_LEAN
		ng438_note(0, label, in);
#endif
		unready = in;
	}
	if (!unready && open_ng_on()) { // exp 0438 (open_ng): a writer appended to a chain not yet taken
		const bool in2 = open_ng_writer(label);
#ifndef BC5_LEAN
		ng438_note(1, label, in2);
#endif
		unready = in2;
	}
	if (!unready) unready = q438_on() && q438_writer_queued(label);
#ifndef BC5_LEAN
	wd438_record(ib, n, off, p, is64, label, unready ? 0 : 1); // exp 0438 (wd438): bc5-ring's gate
#else
	(void)ib;
	(void)n;
	(void)off;
#endif
	return unready;
}
'''
rep(OLD_UNREADY, NEW_UNREADY)
rep("acb_wait_unready(p, op == 0x93, label, ring)) { // exp 0438 (q438ng)\n",
    "acb_wait_unready(p, op == 0x93, label, ring, ib, num_dwords, i)) { // exp 0438 (q438ng)\n")
rep("static std::atomic<uint64_t> g_inflight_ng {0}; // exp 0438 (inflight_ng): acb waits held for a writer in flight\n",
    "static std::atomic<uint64_t> g_inflight_ng {0}; // exp 0438 (inflight_ng): acb waits held for a writer in flight\n"
    "static bool open_ng_on() { // exp 0438 (open_ng): BC5_0438_OPEN_NG, on only when \"1\"\n"
    "\tstatic const bool v = [] {\n"
    "\t\tconst char* e = std::getenv(\"BC5_0438_OPEN_NG\");\n"
    "\t\treturn e != nullptr && e[0] == '1' && e[1] == 0;\n"
    "\t}();\n"
    "\treturn v;\n"
    "}\n"
    "static bool open_ng_writer(uint64_t label); // exp 0438 (open_ng), defined in the q438 block\n"
    "#ifndef BC5_LEAN\n"
    "static void ng438_fallback(uint64_t label); // exp 0438 (ng438), defined before acb_ready\n"
    "static void wd438_record(const uint32_t* ib, uint32_t n, uint32_t off, const uint32_t* p, bool is64, uint64_t label, int decision); // exp 0438 (wd438)\n"
    "static void wd438_dump(const std::string& path);\n"
    "#endif\n")
rep("\tif (!g_f10_reg_mu.try_lock()) return true;\n\tbool in = false;\n",
    "\tif (!g_f10_reg_mu.try_lock()) {\n#ifndef BC5_LEAN\n\t\tg_ng438_busy++; // exp 0438 (ng438)\n#endif\n\t\treturn true;\n\t}\n\tbool in = false;\n")
rep("\t\tif (!cs->mu.try_lock()) {\n\t\t\tin = true;\n",
    "\t\tif (!cs->mu.try_lock()) {\n#ifndef BC5_LEAN\n\t\t\tg_ng438_busy++; // exp 0438 (ng438)\n#endif\n\t\t\tin = true;\n")
WD = r'''// exp 0438 (tag open_ng): a writer of the label appended to a registered slot's open chain (its F10 write set; not
// taken, so neither in flight nor queued nor early). The chain goes at its owner's next flush or the watchdog's 2-ms
// bound; the acb is decided at the next poll after that. A busy registry or slot counts, as in f10_pending.
static bool open_ng_writer(uint64_t label) {
	if (!g_f10_reg_mu.try_lock()) {
#ifndef BC5_LEAN
		g_ng438_busy++; // exp 0438 (ng438)
#endif
		return true;
	}
	bool in = false;
	for (ChainSlot* cs: g_f10_reg) {
		if (!cs->mu.try_lock()) {
#ifndef BC5_LEAN
			g_ng438_busy++; // exp 0438 (ng438)
#endif
			in = true;
			break;
		}
		in = !cs->c.segs.empty() && std::find(cs->f10_writes.begin(), cs->f10_writes.end(), label) != cs->f10_writes.end();
		cs->mu.unlock();
		if (in) break;
	}
	g_f10_reg_mu.unlock();
	return in;
}
#ifndef BC5_LEAN
// exp 0438 (tag wd438): the last 256 acb wait decisions with the writer state of the label at that moment (normal build,
// whatever BC5_0438_INFLIGHT_NG is). Decisions: 0 deferred at bc5-ring's gate, 1 met at the gate, 2 after ho430::at_wait,
// 3 kept for the GPU, 4 met at submit (the filter drops it), 5 served on the CPU, 6 given up. The ring is written without a
// lock (an atomic index; a reader may see a torn entry, its seq tells); a thread skips a repeat of one of its last 16
// (wait, decision) pairs, so bc5-ring's 1-kHz polls of a deferred acb do not flood it.
struct Wd438 {
	std::atomic<uint64_t> seq {0}; // 0: being written
	uint64_t              t = 0, label = 0, ref = 0, value = 0;
	const uint32_t*       ib = nullptr;
	uint32_t              n = 0, off = 0, func = 0;
	int                   decision = 0, slots = 0, open = 0, phase[2] = {-1, -1};
	bool                  early = false, busy = false;
};
static Wd438                 g_wd438[256];
static std::atomic<uint64_t> g_wd438_n {0};
static void wd438_record(const uint32_t* ib, uint32_t n, uint32_t off, const uint32_t* p, bool is64, uint64_t label, int decision) {
	static thread_local const uint32_t* last_p[16] = {};
	static thread_local int             last_d[16] = {};
	static thread_local unsigned        last_k     = 0;
	for (unsigned k = 0; k < 16; k++)
		if (last_p[k] == p && last_d[k] == decision) return;
	last_p[last_k & 15u] = p;
	last_d[last_k & 15u] = decision;
	last_k++;
	bool early = false, busy = false;
	int  slots = 0, open = 0, phase[2] = {-1, -1};
	{
		std::lock_guard lk(g_plw_mutex);
		for (const auto& w: g_plw)
			if (w.label == label && (w.seq & kR438Early) != 0) early = true;
	}
	if (g_f10_reg_mu.try_lock()) {
		for (ChainSlot* cs: g_f10_reg) {
			if (!cs->mu.try_lock()) {
				busy = true;
				continue;
			}
			if (!cs->c.segs.empty() && std::find(cs->f10_writes.begin(), cs->f10_writes.end(), label) != cs->f10_writes.end()) open++;
			if (std::find(cs->f10_flight.begin(), cs->f10_flight.end(), label) != cs->f10_flight.end()) {
				if (slots < 2) phase[slots] = cs->f16_phase.load();
				slots++;
			}
			cs->mu.unlock();
		}
		g_f10_reg_mu.unlock();
	} else {
		busy = true;
	}
	const uint64_t k = g_wd438_n.fetch_add(1);
	Wd438&         e = g_wd438[k & 255u];
	e.seq.store(0);
	e.t        = SoftCp::now_ns();
	e.ib       = ib;
	e.n        = n;
	e.off      = off;
	e.label    = label;
	e.func     = p[1] & 7u;
	e.ref      = is64 ? (p[4] | (static_cast<uint64_t>(p[5]) << 32u)) : p[4];
	e.value    = is64 ? *reinterpret_cast<const volatile uint64_t*>(label & ~7ull) : *reinterpret_cast<const volatile uint32_t*>(label & ~3ull);
	e.decision = decision;
	e.early    = early;
	e.busy     = busy;
	e.slots    = slots;
	e.open     = open;
	e.phase[0] = phase[0];
	e.phase[1] = phase[1];
	e.seq.store(k + 1);
}
static void wd438_dump_to(FILE* f) { // oldest first, newest last
	static const char* const kDec[7] = {"deferred at the gate", "met at the gate", "after at_wait", "kept for the GPU", "met at submit (dropped)", "served on the CPU", "given up"};
	const uint64_t           n0      = g_wd438_n.load();
	for (uint64_t k = n0 > 256 ? n0 - 256 : 0; k < n0; k++) {
		const Wd438&   e = g_wd438[k & 255u];
		const uint64_t s = e.seq.load();
		if (s != k + 1) {
			std::fprintf(f, "wd438: #%" PRIu64 " (being written or overwritten)\n", k + 1);
			continue;
		}
		std::fprintf(f, "wd438: #%" PRIu64 " t %.6f s acb %p +%u of %u dwords: wait on 0x%" PRIx64 " function %u reference 0x%" PRIx64 ", memory 0x%" PRIx64 ": %s; writer in flight %d (early entry %d, slots %d, phase %d/%d%s); in an open chain %d\n",
		             s, static_cast<double>(e.t) / 1e9, static_cast<const void*>(e.ib), e.off, e.n, e.label, e.func, e.ref, e.value, e.decision >= 0 && e.decision < 7 ? kDec[e.decision] : "?",
		             e.early || e.slots > 0 ? 1 : 0, e.early ? 1 : 0, e.slots, e.phase[0], e.phase[1], e.busy ? ", a slot or the registry was busy" : "", e.open);
	}
}
static void wd438_dump(const std::string& path) { // appended to the fault record's journal-tail.txt
	FILE* f = std::fopen(path.c_str(), "a");
	if (f == nullptr) return;
	std::fprintf(f, "\nwd438 (exp 0438): the last %" PRIu64 " acb wait decisions, newest last\n", std::min<uint64_t>(g_wd438_n.load(), 256));
	wd438_dump_to(f);
	std::fclose(f);
}
#endif
// ---- end of exp 0438 (tag q438) ---'''
rep("// ---- end of exp 0438 (tag q438) ---", WD)
rep("\t\t\t\t\tLOGF_COLOR(Log::Color::Yellow, \"[bc5-q] queue %u/%u/%u/0x%x: cross-queue wait unsatisfied for 10 s, proceeding\\n\", q.a, q.b, q.c, q.d);\n",
    "#ifndef BC5_LEAN\n"
    "\t\t\t\t\tDirect::ng438_fallback(Direct::t_unready.label); // exp 0438 (ng438): a hold of BC5_0438_INFLIGHT_NG let go here gets a BUG line\n"
    "#endif\n"
    "\t\t\t\t\tLOGF_COLOR(Log::Color::Yellow, \"[bc5-q] queue %u/%u/%u/0x%x: cross-queue wait unsatisfied for 10 s, proceeding\\n\", q.a, q.b, q.c, q.d);\n")
rep("static void register_label_writes(const uint32_t* ib, uint32_t num_dwords, const std::vector<uint32_t>& executed, uint64_t seq, int ring) {\n",
    "static void register_label_writes(const uint32_t* ib, uint32_t num_dwords, const std::vector<uint32_t>& executed, uint64_t seq, int ring) {\n"
    "#ifndef BC5_LEAN\n\tng438_tick(); // exp 0438 (ng438): its 60-s line while BC5_0438_INFLIGHT_NG=1\n#endif\n")
rep("\t\t\t\t\tho430::at_wait(p, op == 0x93, label, kind, job_ring(kind), ib, num_dwords, i); // exp 0430 (tag ho430): F10, F2 + F4\n",
    "\t\t\t\t\tho430::at_wait(p, op == 0x93, label, kind, job_ring(kind), ib, num_dwords, i); // exp 0430 (tag ho430): F10, F2 + F4\n"
    "#ifndef BC5_LEAN\n"
    "\t\t\t\t\tconst bool wd_acb  = kind != nullptr && std::strncmp(kind, \"acb\", 3) == 0; // exp 0438 (wd438)\n"
    "\t\t\t\t\tconst bool wd_sat0 = wait_satisfied(p, op == 0x93);\n"
    "\t\t\t\t\tif (wd_acb) wd438_record(ib, num_dwords, i, p, op == 0x93, label, 2);\n"
    "#endif\n")
rep("\t\t\t\t\t\tt_keep_waits.push_back(p);\n\t\t\t\t\t\tSoftCp::set_gpu_executed(p, len, {0});\n\t\t\t\t\t\tif (dry_here) g_dry_kept++;\n",
    "#ifndef BC5_LEAN\n"
    "\t\t\t\t\t\tif (wd_acb) wd438_record(ib, num_dwords, i, p, op == 0x93, label, 3); // exp 0438 (wd438)\n"
    "#endif\n"
    "\t\t\t\t\t\tt_keep_waits.push_back(p);\n\t\t\t\t\t\tSoftCp::set_gpu_executed(p, len, {0});\n\t\t\t\t\t\tif (dry_here) g_dry_kept++;\n")
rep("\t\t\t\t\tif (!ok) t_wait_given_up = true;\n\t\t\t\t\tif (dry_here) (ok ? g_dry_ok : g_dry_failed)++;\n",
    "#ifndef BC5_LEAN\n"
    "\t\t\t\t\tif (wd_acb || !ok) wd438_record(ib, num_dwords, i, p, op == 0x93, label, ok ? (wd_sat0 ? 4 : 5) : 6); // exp 0438 (wd438): every given-up wait too, of any kind\n"
    "#endif\n"
    "\t\t\t\t\tif (!ok) t_wait_given_up = true;\n\t\t\t\t\tif (dry_here) (ok ? g_dry_ok : g_dry_failed)++;\n")
rep("\tif (!g_dump_dir.empty()) fr412_copy(g_dump_dir + \"/direct.log\", dir + \"/journal-tail.txt\", 4l << 20);\n",
    "\tif (!g_dump_dir.empty()) fr412_copy(g_dump_dir + \"/direct.log\", dir + \"/journal-tail.txt\", 4l << 20);\n"
    "#ifndef BC5_LEAN\n\twd438_dump(dir + \"/journal-tail.txt\"); // exp 0438 (wd438): the last acb wait decisions\n#endif\n")

# ---- ngcount: one live count, so the gate's tests cost one atomic load when nothing can be pending ----------------------
# g_ng_live = registered slots whose F10 flight set (taken, not yet registered) or open-chain write set is non-empty
#           + early entries in g_plw (r438's slices, Q438's queued chains).
# Kept only while BC5_0438_INFLIGHT_NG or BC5_0438_OPEN_NG is on (read once). A slot's part changes under its mu, at the end
# of every change of those sets (ng_slot_update); the early part under g_plw_mutex where early entries go in or out. So it
# reads 0 only when no registered slot has such a write and no early entry is in the table. Ordering: the count rises inside
# the writer's chain_append (a locked RMW), before the title's ioctl returns, so before the title can submit the acb whose
# wait bc5-ring then reads; on x86 (TSO, multi-copy atomic) bc5-ring's later load of the count sees it. It falls only when
# the set is empty, after the registration; a stale non-zero read only runs the full test.
rep("static bool open_ng_writer(uint64_t label); // exp 0438 (open_ng), defined in the q438 block\n",
    "static bool open_ng_writer(uint64_t label); // exp 0438 (open_ng), defined in the q438 block\n"
    "static std::atomic<int64_t> g_ng_live {0}; // exp 0438 (ngcount): writers that can be pending (see ng_slot_update)\n"
    "static bool ng_counting() { return inflight_ng_on() || open_ng_on(); }\n")
rep("\tuint64_t                     q_nested = 0; // the submitter thread's own: nested inline takes\n",
    "\tuint64_t                     q_nested = 0; // the submitter thread's own: nested inline takes\n"
    "\tbool                         ng_marked = false; // exp 0438 (ngcount): counted in g_ng_live (under mu)\n")
rep("static thread_local ChainSlot g_chain_tl;\n",
    "static thread_local ChainSlot g_chain_tl;\n"
    "// exp 0438 (ngcount): caller holds s.mu, after a change of s.f10_flight or s.f10_writes (registered slots only, as the\n"
    "// gate's full tests look at g_f10_reg only)\n"
    "static void ng_slot_update(ChainSlot& s) {\n"
    "\tif (!ng_counting() || !s.registered) return;\n"
    "\tconst bool now = !s.f10_flight.empty() || !s.f10_writes.empty();\n"
    "\tif (now == s.ng_marked) return;\n"
    "\ts.ng_marked = now;\n"
    "\tg_ng_live += now ? 1 : -1;\n"
    "}\n")
rep("\t\ts.f10_flight.swap(s.f10_writes); // exp 0430 F10: in flight until submit_now has registered its writes\n\t\ts.f10_writes.clear();\n\t\ts.f10_wanted = false;\n",
    "\t\ts.f10_flight.swap(s.f10_writes); // exp 0430 F10: in flight until submit_now has registered its writes\n\t\ts.f10_writes.clear();\n\t\ts.f10_wanted = false;\n"
    "\t\tng_slot_update(s); // exp 0438 (ngcount)\n")
rep("\t{ // exp 0430 F10: its writes are registered now\n\t\tstd::lock_guard lk(s.mu);\n\t\ts.f10_flight.clear();\n\t}\n",
    "\t{ // exp 0430 F10: its writes are registered now\n\t\tstd::lock_guard lk(s.mu);\n\t\ts.f10_flight.clear();\n\t\tng_slot_update(s); // exp 0438 (ngcount)\n\t}\n")
rep("\t\t\t\tf10_note(s.f10_writes, ib, n); // exp 0430 F10 (graphics and compute chains)\n",
    "\t\t\t\tf10_note(s.f10_writes, ib, n); // exp 0430 F10 (graphics and compute chains)\n"
    "\t\t\t\tng_slot_update(s); // exp 0438 (ngcount)\n")
rep("\tfor (const auto& e: s.q_sets) s.f10_flight.insert(s.f10_flight.end(), e.second.begin(), e.second.end());\n}\n",
    "\tfor (const auto& e: s.q_sets) s.f10_flight.insert(s.f10_flight.end(), e.second.begin(), e.second.end());\n"
    "\tng_slot_update(s); // exp 0438 (ngcount): q438_take_locked's clear of f10_writes is always followed by this\n}\n")
rep("\tif (q438_on()) q438_stop(*this); // exp 0438 (q438): out of g_chains, then the submitter drains its queue and stops\n",
    "\tif (q438_on()) q438_stop(*this); // exp 0438 (q438): out of g_chains, then the submitter drains its queue and stops\n"
    "\t{ // exp 0438 (ngcount): an open chain dropped at the thread's end\n"
    "\t\tstd::lock_guard nk(mu);\n"
    "\t\tif (ng_marked) g_ng_live--;\n"
    "\t\tng_marked = false;\n"
    "\t}\n")
# the early entries
rep("\tg_plw.insert(g_plw.end(), found.begin(), found.end());\n\tg_r438o_live += found.size(); // exp 0438 (r438o)\n",
    "\tg_plw.insert(g_plw.end(), found.begin(), found.end());\n\tg_r438o_live += found.size(); // exp 0438 (r438o)\n"
    "\tif (ng_counting()) g_ng_live += static_cast<int64_t>(found.size()); // exp 0438 (ngcount)\n")
rep("\t\t\t\tit = g_plw.erase(it);\n\t\t\t\tif (g_r438o_live != 0) g_r438o_live--; // exp 0438 (r438o)\n",
    "\t\t\t\tit = g_plw.erase(it);\n\t\t\t\tif (g_r438o_live != 0) g_r438o_live--; // exp 0438 (r438o)\n"
    "\t\t\t\tif (ng_counting()) g_ng_live--; // exp 0438 (ngcount)\n")
rep("\tif (all) {\n\t\tg_plw.clear();\n\t\tg_r438o_live = 0; // exp 0438 (r438o)\n",
    "\tif (all) {\n"
    "\t\tif (ng_counting()) // exp 0438 (ngcount): the early entries cleared with the table\n"
    "\t\t\tfor (const auto& w: g_plw)\n"
    "\t\t\t\tif ((w.seq & kR438Early) != 0) g_ng_live--;\n"
    "\t\tg_plw.clear();\n\t\tg_r438o_live = 0; // exp 0438 (r438o)\n")
rep("\tr438o_trim_locked(); // exp 0438 (stack438): the queued chain's early registration, r438o's trim\n\tg_plw.insert(g_plw.end(), found.begin(), found.end());\n\treturn id;\n",
    "\tr438o_trim_locked(); // exp 0438 (stack438): the queued chain's early registration, r438o's trim\n\tg_plw.insert(g_plw.end(), found.begin(), found.end());\n"
    "\tif (ng_counting()) g_ng_live += static_cast<int64_t>(found.size()); // exp 0438 (ngcount)\n\treturn id;\n")
rep("\t\t\tif (it->seq == id) {\n\t\t\t\tif (std::find(t_q438_real.begin(), t_q438_real.end(), it->label) == t_q438_real.end()) lost.push_back(*it);\n\t\t\t\tit = g_plw.erase(it);\n",
    "\t\t\tif (it->seq == id) {\n\t\t\t\tif (std::find(t_q438_real.begin(), t_q438_real.end(), it->label) == t_q438_real.end()) lost.push_back(*it);\n\t\t\t\tit = g_plw.erase(it);\n"
    "\t\t\t\tif (ng_counting()) g_ng_live--; // exp 0438 (ngcount)\n")
# the gate: one load when nothing can be pending; skip / full counts in ng438's line
rep("\t\tconst bool in = inflight_ng_writer(label);\n#ifndef BC5_LEAN\n\t\tng438_note(0, label, in);\n#endif\n",
    "\t\tconst bool live = g_ng_live.load() != 0; // exp 0438 (ngcount): 0: no writer can be pending, the full test is skipped\n"
    "\t\tconst bool in   = live && inflight_ng_writer(label);\n#ifndef BC5_LEAN\n\t\t(live ? g_ng438_full : g_ng438_skip)[0]++;\n\t\tng438_note(0, label, in);\n#endif\n")
rep("\t\tconst bool in2 = open_ng_writer(label);\n#ifndef BC5_LEAN\n\t\tng438_note(1, label, in2);\n#endif\n",
    "\t\tconst bool live2 = g_ng_live.load() != 0; // exp 0438 (ngcount)\n"
    "\t\tconst bool in2   = live2 && open_ng_writer(label);\n#ifndef BC5_LEAN\n\t\t(live2 ? g_ng438_full : g_ng438_skip)[1]++;\n\t\tng438_note(1, label, in2);\n#endif\n")
rep("static std::atomic<uint64_t>        g_ng438_holds[2], g_ng438_rel[2], g_ng438_max[2], g_ng438_fb {0}, g_ng438_busy {0};\n",
    "static std::atomic<uint64_t>        g_ng438_holds[2], g_ng438_rel[2], g_ng438_max[2], g_ng438_fb {0}, g_ng438_busy {0};\n"
    "static std::atomic<uint64_t>        g_ng438_skip[2], g_ng438_full[2]; // exp 0438 (ngcount): tests skipped by the live count / run in full\n")
rep('released %" PRIu64 "; by the 10-s fallback %" PRIu64 "; busy registry or slot %" PRIu64 "\\n",\n',
    'released %" PRIu64 "; by the 10-s fallback %" PRIu64 "; busy registry or slot %" PRIu64 "; tests skipped by the live count / run in full: in flight %" PRIu64 "/%" PRIu64 ", open %" PRIu64 "/%" PRIu64 "\\n",\n')
rep("static_cast<double>(g_ng438_max[1].load()) / 1e6, g_ng438_rel[1].load(), g_ng438_fb.load(), g_ng438_busy.load());\n",
    "static_cast<double>(g_ng438_max[1].load()) / 1e6, g_ng438_rel[1].load(), g_ng438_fb.load(), g_ng438_busy.load(), g_ng438_skip[0].load(), g_ng438_full[0].load(), g_ng438_skip[1].load(), g_ng438_full[1].load());\n")

# ---- held438: an acb that acb_ready holds keeps its remaining label writes early (BC5_0438_HELD_EARLY, off unless "1") --
# The full set's #67 shape (cq438f1): acb A1 held by acb_ready at its wait on d00 ("acb head: 87 of 1336 dwords go ahead");
# then the game thread's dcb D waits on d40, which only A1 writes. A held acb's writes are in no table (not early: r438
# scans taken slices only; not in a flight set, a chain or the queue), so ring_will_satisfy on the game thread finds no
# writer, the CPU wait polls memory for its 8-ms limit and drops the wait (GIVEN UP), and D runs ahead of its order.
# With the switch: when acb_ready holds an acb, the writes of its part from the held wait on are registered early once
# (seq kR438Early | bit 61 | id), so a game-thread wait on one waits under r438's rule until the acb's real registration;
# they go when the acb is submitted (the consumer's ring branch), or with the table at a reset.
rep("static std::atomic<int64_t> g_ng_live {0}; // exp 0438 (ngcount): writers that can be pending (see ng_slot_update)\n",
    "static std::atomic<int64_t> g_ng_live {0}; // exp 0438 (ngcount): writers that can be pending (see ng_slot_update)\n"
    "static bool held438_on() { // exp 0438 (held438): BC5_0438_HELD_EARLY, on only when \"1\"\n"
    "\tstatic const bool v = [] {\n"
    "\t\tconst char* e = std::getenv(\"BC5_0438_HELD_EARLY\");\n"
    "\t\treturn e != nullptr && e[0] == '1' && e[1] == 0;\n"
    "\t}();\n"
    "\treturn v;\n"
    "}\n"
    "static void held438_hold(const uint32_t* ib, uint32_t num_dwords, uint32_t from); // exp 0438 (held438), in the q438 block\n"
    "static void held438_release(const uint32_t* ib, uint32_t num_dwords);\n")
rep("\t\t\t\t\t\tfor (auto& g: SoftCp::t_gpu_done) e->marks.push_back(std::move(g));\n\t\t\t\t\t\tSoftCp::clear_gpu_executed();\n\t\t\t\t\t}\n\t\t\t\t\treturn false;\n",
    "\t\t\t\t\t\tfor (auto& g: SoftCp::t_gpu_done) e->marks.push_back(std::move(g));\n\t\t\t\t\t\tSoftCp::clear_gpu_executed();\n\t\t\t\t\t}\n"
    "\t\t\t\t\tif (held438_on()) held438_hold(ib, num_dwords, i); // exp 0438 (held438): its writes from the held wait on, early\n"
    "\t\t\t\t\treturn false;\n")
rep("\t\t\t\t\t\tsubmit_split(t + skip, tn - skip, \"acb\");\n",
    "\t\t\t\t\t\tsubmit_split(t + skip, tn - skip, \"acb\");\n"
    "\t\t\t\t\t\tif (held438_on()) held438_release(t, tn); // exp 0438 (held438): submitted: its held early writes go\n")
HELD = r'''// exp 0438 (tag held438): the held acbs' early writes (BC5_0438_HELD_EARLY=1)
static std::mutex                                                  g_held438_mu;
static std::map<std::pair<const uint32_t*, uint32_t>, uint64_t>    g_held438; // (acb, dwords) -> the seq of its early entries
static std::atomic<uint64_t>                                       g_held438_ids {0}, g_held438_holds {0}, g_held438_released {0};
static void held438_hold(const uint32_t* ib, uint32_t num_dwords, uint32_t from) {
	std::lock_guard hk(g_held438_mu);
	if (g_held438.count({ib, num_dwords}) != 0) return; // once per hold
	std::vector<uint32_t>          part(ib + from, ib + num_dwords);
	std::vector<PendingLabelWrite> found;
	q438_scan(part, found);
	const uint64_t id = kR438Early | (1ull << 61u) | (g_held438_ids.fetch_add(1) + 1);
	g_held438[{ib, num_dwords}] = id;
	g_held438_holds++;
	if (found.empty()) return;
	std::lock_guard lk(g_plw_mutex);
	for (auto& w: found) {
		w.seq   = id;
		w.ring  = 0;
		w.order = ++g_plw_order;
	}
	r438o_trim_locked();
	g_plw.insert(g_plw.end(), found.begin(), found.end());
	if (ng_counting()) g_ng_live += static_cast<int64_t>(found.size());
	if (r438_cv()) g_plw_cv.notify_all();
}
static void held438_release(const uint32_t* ib, uint32_t num_dwords) {
	std::lock_guard hk(g_held438_mu);
	const auto      it = g_held438.find({ib, num_dwords});
	if (it == g_held438.end()) return;
	const uint64_t id = it->second;
	g_held438.erase(it);
	g_held438_released++;
	int64_t gone = 0;
	{
		std::lock_guard lk(g_plw_mutex);
		for (auto w = g_plw.begin(); w != g_plw.end();) {
			if (w->seq == id) {
				w = g_plw.erase(w);
				gone++;
			} else {
				++w;
			}
		}
	}
	if (gone != 0 && ng_counting()) g_ng_live -= gone; // only what was still there (a reset may have cleared it)
	if (r438_cv()) g_plw_cv.notify_all();
}
// ---- end of exp 0438 (tag q438) ---'''
rep("// ---- end of exp 0438 (tag q438) ---", HELD)

out = s.encode('utf-8')
open(OUT, 'wb').write(out)
print('IN ', hashlib.md5(src).hexdigest(), IN)
print('OUT', hashlib.md5(out).hexdigest(), OUT, f'({s.count(chr(10))} lines)')
