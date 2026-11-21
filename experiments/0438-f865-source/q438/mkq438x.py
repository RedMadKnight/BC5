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

out = s.encode('utf-8')
open(OUT, 'wb').write(out)
print('IN ', hashlib.md5(src).hexdigest(), IN)
print('OUT', hashlib.md5(out).hexdigest(), OUT, f'({s.count(chr(10))} lines)')
