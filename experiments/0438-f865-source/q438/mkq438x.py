#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438 (tags labelmap, q438ng): two steps on the stacked unit stack438.cpp (mkstack438.py's output).
Usage: python -I mkq438x.py IN.cpp OUT.cpp   (IN: q438/stack438.cpp, md5 29d02cb5f885f07e60d8eee055638f38)

labelmap (ASTRO BOT, SUBMITQ=1: 213 "early-registered write ... never reached the ring" lines per run). The early scans
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
ng438 (normal build only): counts of BC5_0438_INFLIGHT_NG's gate (holds, longest, releases after the writer's registration,
  releases by the 10-s fallback with a BUG line, busy tries) and a 60-s line while the switch is on.
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
// exp 0438 (tag ng438): what BC5_0438_INFLIGHT_NG's gate does (normal build only). A hold is per label, from its first
// held test to the first test that finds no writer in flight (a release after the writer's registration) or to the queue
// consumer's 10-s fallback (a release with a BUG line, compare-only). Busy: a try of the registry or a slot that failed.
static std::mutex                   g_ng438_mu;
static std::map<uint64_t, uint64_t> g_ng438_held; // label -> its first hold (ns)
static std::atomic<uint64_t>        g_ng438_holds {0}, g_ng438_rel {0}, g_ng438_fb {0}, g_ng438_busy {0}, g_ng438_max {0};
static void ng438_note(uint64_t label, bool in) {
	const uint64_t  now = SoftCp::now_ns();
	std::lock_guard lk(g_ng438_mu);
	const auto      it = g_ng438_held.find(label);
	if (in) {
		if (it == g_ng438_held.end()) {
			g_ng438_held.emplace(label, now);
			g_ng438_holds++;
		}
		return;
	}
	if (it == g_ng438_held.end()) return;
	const uint64_t d = now - it->second;
	for (uint64_t m = g_ng438_max.load(); d > m && !g_ng438_max.compare_exchange_weak(m, d);) {
	}
	g_ng438_rel++;
	g_ng438_held.erase(it);
}
static void ng438_fallback(uint64_t label) { // the queue consumer let an unready acb go after 10 s
	uint64_t held = 0;
	{
		std::lock_guard lk(g_ng438_mu);
		const auto      it = g_ng438_held.find(label);
		if (it == g_ng438_held.end()) return;
		held = SoftCp::now_ns() - it->second;
		g_ng438_held.erase(it);
	}
	const uint64_t k = g_ng438_fb++;
	journal("ng438 (exp 0438, inflight_ng): BUG: the acb waiting on 0x%" PRIx64 " went by the 10-s fallback after %.1f ms held for a writer in flight (%" PRIu64 " so far)\n", label, static_cast<double>(held) / 1e6, k + 1);
}
static void ng438_line() {
	journal("ng438 (exp 0438, inflight_ng): t %.1f s: acbs held for a writer in flight %" PRIu64 ", longest %.3f ms, released after the writer's registration %" PRIu64 ", by the 10-s fallback %" PRIu64 "; busy registry or slot %" PRIu64 "\n",
	        timing_now(), g_ng438_holds.load(), static_cast<double>(g_ng438_max.load()) / 1e6, g_ng438_rel.load(), g_ng438_fb.load(), g_ng438_busy.load());
}
static void ng438_tick() { // from register_label_writes: every 60 s while BC5_0438_INFLIGHT_NG=1
	if (!inflight_ng_on()) return;
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
		ng438_note(label, in);
#endif
		unready = in;
	}
	if (!unready && open_ng_on()) unready = open_ng_writer(label); // exp 0438 (open_ng): a writer appended to a chain not yet taken
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
	if (!g_f10_reg_mu.try_lock()) return true;
	bool in = false;
	for (ChainSlot* cs: g_f10_reg) {
		if (!cs->mu.try_lock()) {
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
    "\t\t\t\t\tif (wd_acb) wd438_record(ib, num_dwords, i, p, op == 0x93, label, ok ? (wd_sat0 ? 4 : 5) : 6); // exp 0438 (wd438)\n"
    "#endif\n"
    "\t\t\t\t\tif (!ok) t_wait_given_up = true;\n\t\t\t\t\tif (dry_here) (ok ? g_dry_ok : g_dry_failed)++;\n")
rep("\tif (!g_dump_dir.empty()) fr412_copy(g_dump_dir + \"/direct.log\", dir + \"/journal-tail.txt\", 4l << 20);\n",
    "\tif (!g_dump_dir.empty()) fr412_copy(g_dump_dir + \"/direct.log\", dir + \"/journal-tail.txt\", 4l << 20);\n"
    "#ifndef BC5_LEAN\n\twd438_dump(dir + \"/journal-tail.txt\"); // exp 0438 (wd438): the last acb wait decisions\n#endif\n")

out = s.encode('utf-8')
open(OUT, 'wb').write(out)
print('IN ', hashlib.md5(src).hexdigest(), IN)
print('OUT', hashlib.md5(out).hexdigest(), OUT, f'({s.count(chr(10))} lines)')
