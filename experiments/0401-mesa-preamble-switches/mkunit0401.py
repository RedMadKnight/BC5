#!/usr/bin/env python3
"""BC5 experiment 0401: main 029e0d6b's src/libs/bc5LleAgc.cpp with two default-off switches, mesa_preamble_prefix(), called
from prefix_of() right after tf_ring_prefix(). With --acb (series b, 2026-11-03) also the acb CS prefix, a third default-off
switch; with --acb-restore (series c) also exp 0381's ACB_STATE_RESTORE, a fourth. Each anchor must occur exactly once.
Prints the output's md5.
usage: mkunit0401.py <unit in> <unit out> <function out> [--acb | --acb-restore]"""
import hashlib
import os
import sys

ANCHOR = b"static std::vector<uint32_t> prefix_of(const bc5::full_state::Tracker& t) {\n"
CALL = b"\ttf_ring_prefix(p); // experiment 0160\n"
FUNCTION = b"""// Experiment 0401, behaviour switches, both off by default: two registers of Mesa's gfx10 preamble that neither the
// title's stream nor the host sets (static audit of 2026-11-02, 1,347 captured buffers), written in every prefix as the
// rings are, by the packets Mesa's own preamble sends from an unprivileged user IB (src/amd/common/ac_cmdbuf.c @ 0866ae7,
// through ac_pm4_set_reg). Neither is in Mesa's privileged list (src/amd/common/ac_pm4.c:34 is_privileged_reg).
// - BC5_DIRECT_CP_COHER_START_DELAY=1: CP_COHER_START_DELAY = 0x20 (R_0301EC, uconfig 0x7b, START_DELAY_COUNT bits 0-5,
//   src/amd/registers/gfx10.json), SET_UCONFIG_REG; ac_cmdbuf.c:60 gfx10_init_compute_preamble_state. Mesa gives no reason.
// - BC5_DIRECT_SPI_REQ_CTRL_PS=1: SPI_SHADER_REQ_CTRL_PS = 0x7 (R_00B0C0, SH 0x30: SOFT_GROUPING_EN bit 0 = 1,
//   NUMBER_OF_REQUESTS_PER_CU bits 1-4 = 4 - 1), SET_SH_REG; ac_cmdbuf.c:444 gfx10_init_graphics_preamble_state.
// TODO(verify): what the chip holds before these writes; there is no read-back yet (debugfs needs root).
static void mesa_preamble_prefix(std::vector<uint32_t>& p) {
\tstatic const bool coher  = bc5::env_on(std::getenv("BC5_DIRECT_CP_COHER_START_DELAY"));
\tstatic const bool req_ps = bc5::env_on(std::getenv("BC5_DIRECT_SPI_REQ_CTRL_PS"));
\tstatic std::atomic<bool> told {false};
\tif (!told.exchange(true)) {
\t\tjournal("exp 0401: CP_COHER_START_DELAY %s\\n", coher ? "0x20 in every prefix (SET_UCONFIG_REG 0x7b)" : "off");
\t\tjournal("exp 0401: SPI_SHADER_REQ_CTRL_PS %s\\n", req_ps ? "0x7 in every prefix (SET_SH_REG 0x30)" : "off");
\t}
\tif (coher) p.insert(p.end(), {0xC0017900u, 0x7bu, 0x20u});
\tif (req_ps) p.insert(p.end(), {0xC0017600u, 0x30u, 0x7u});
}
"""


# Series b: the acb side of experiment 0195's CS prefix (BC5_DIRECT_ACB_CS_PREFIX). (anchor, text, where): the text goes
# before or after the anchor, or replaces it.
ACB_DECL = b"""// Experiment 0401 (BC5_DIRECT_ACB_CS_PREFIX), defined with the CS prefix below.
static std::vector<uint32_t> acb_cs_prefix(const uint32_t* part, uint32_t n);
static void                  acb_cs_track(const uint32_t* part, uint32_t n);
static void                  chain_append(const uint32_t* pre, uint32_t pre_n, const uint32_t* ib, uint32_t n, const char* kind, bool host_built);
"""
ACB_SEGMENT_OLD = b"""\tsubmit_one(ib + from, to - from, "acb");
\tt_keep_waits.clear();
}
"""
ACB_SEGMENT_NEW = b"""\t// Experiment 0401: the guest queue's compute registers in front of a part that dispatches before it sets a program, in
\t// the part's own chain segment (ADR 0010); without the chain (BC5_DIRECT_CHAIN=0) as a job of its own just before it.
\tconst std::vector<uint32_t> acb_cs = acb_cs_prefix(ib + from, to - from);
\tif (acb_cs.empty()) {
\t\tsubmit_one(ib + from, to - from, "acb");
\t} else if (chain_on()) {
\t\tchain_append(acb_cs.data(), static_cast<uint32_t>(acb_cs.size()), ib + from, to - from, "acb", false);
\t} else {
\t\tstatic thread_local std::deque<std::vector<uint32_t>> kept; // kept as state_prefix keeps its own
\t\tif (kept.size() >= 256) kept.pop_front();
\t\tkept.push_back(acb_cs);
\t\tsubmit_one(kept.back().data(), static_cast<uint32_t>(kept.back().size()), "acb-state");
\t\tsubmit_one(ib + from, to - from, "acb");
\t}
\tacb_cs_track(ib + from, to - from);
\tt_keep_waits.clear();
}
"""
ACB_FUNCTIONS = b"""// Experiment 0401 (BC5_DIRECT_ACB_CS_PREFIX=1, default off): the acb side of experiment 0195's CS prefix. On the console
// an acb runs on its own compute queue, which keeps the compute registers that queue's previous acb left. The second
// title relies on it: on 2026-11-03 08:49 acb #432910 launched 19612 x 1 x 1 four times before it set a program (its
// last dispatch sets 0x9098eb200 over the same arguments), and with the acbs on the GFX ring the stall sampler saw a
// dcb's program, 0x11d0287900, running those groups when the ring hung. With the switch on, every acb part the ring
// thread submits is applied to its guest queue's own tracker (bc5::full_state, keyed by t_queue_idx), and a part that
// dispatches before it sets COMPUTE_PGM_LO (cs_inherit_at) gets that queue's tracked compute registers in front
// (cs_prefix: SH 0x204-0x3ff). A queue with nothing tracked yet gets nothing. With the switch off nothing is tracked.
static bool acb_cs_prefix_on() {
\tstatic const bool        on = bc5::env_on(std::getenv("BC5_DIRECT_ACB_CS_PREFIX"));
\tstatic std::atomic<bool> told {false};
\tif (!told.exchange(true))
\t\tjournal("exp 0401: acb CS prefix %s\\n", on ? "on (an acb part that dispatches before it sets a program gets its queue's tracked compute registers in front)" : "off");
\treturn on;
}
static std::mutex                              g_acb_cs_mutex;
static std::map<int, bc5::full_state::Tracker> g_acb_cs; // by guest queue (t_queue_idx)
static std::vector<uint32_t> acb_cs_prefix(const uint32_t* part, uint32_t n) {
\tif (!acb_cs_prefix_on() || !g_dev || part == nullptr || n == 0) return {};
\tconst int at = cs_inherit_at(part, n, *g_dev->sorted_mappings());
\tif (at < 0) return {};
\tuint64_t              pgm = 0;
\tstd::vector<uint32_t> cs;
\t{
\t\tstd::lock_guard lk(g_acb_cs_mutex);
\t\tconst auto      it = g_acb_cs.find(t_queue_idx);
\t\tif (it != g_acb_cs.end()) cs = cs_prefix(it->second, &pgm);
\t}
\tstatic std::atomic<uint64_t> n_cs {0};
\tconst uint64_t               k = n_cs++;
\tif (k < 64 || (k & 0x3ffu) == 0)
\t\tjournal("acb cs prefix (exp 0401): t %.3f s queue %d acb part %u dwords dispatches at %d before it sets a program; the queue's program 0x%010" PRIx64 ", %zu dwords in front (%" PRIu64 " such parts)\\n",
\t\t        timing_now(), t_queue_idx, n, at, pgm, cs.size(), k + 1);
\treturn cs;
}
static void acb_cs_track(const uint32_t* part, uint32_t n) {
\tif (!acb_cs_prefix_on() || !g_dev || part == nullptr || n == 0) return;
\tstd::shared_ptr<const std::vector<bc5::direct::Mapping>> maps_p = g_dev->sorted_mappings();
\tconst bc5::full_state::Tracker::Reader read = [&maps_p](uint64_t a, uint64_t bytes) -> const uint32_t* {
\t\treturn covered_sorted(*maps_p, a, bytes) ? reinterpret_cast<const uint32_t*>(a) : nullptr;
\t};
\tbc5::full_state::Stats st;
\tstd::lock_guard        lk(g_acb_cs_mutex);
\tg_acb_cs[t_queue_idx].apply(std::span<const uint32_t>(part, n), read, st);
}
"""
RESTORE_FUNCTIONS = b"""// Experiment 0381 (F679, F685), ported to this unit by experiment 0401 series b: BC5_DIRECT_ACB_STATE_RESTORE=1 puts the
// graphics queue's tracked compute registers (the CS prefix's range without COMPUTE_VMID) in front of every graphics
// buffer that dispatches (or calls an IB2) and gets no other prefix, in the buffer's own chain segment. With the acbs on
// the GFX ring a graphics buffer that inherits them (its table sets the program, so cs_inherit_at finds nothing) ran with
// an acb's USER_DATA_0 and faulted at 0x860xxxxxxxx (F679); with the restore 3 of 3 starts ran clean against 3 of 3 faults
// without it (F685). bc5::acb_restore's wants() and runs() (backend/include/bc5/acb_restore.hpp @ main 029e0d6b) are
// copied here, since the header is not on this build's include path; exp 0381's acb register census (Touched) is left out.
// Off by default.
static bool acb_restore_on() {
\tstatic const bool        on = bc5::env_on(std::getenv("BC5_DIRECT_ACB_STATE_RESTORE"));
\tstatic std::atomic<bool> told {false};
\tif (!told.exchange(true))
\t\tjournal("exp 0401: acb state restore (exp 0381) %s\\n", on ? "on (a graphics buffer that dispatches gets the graphics queue's tracked compute registers in front)" : "off");
\treturn on;
}
static bool acb_restore_wants(const uint32_t* ib, uint32_t num_dwords) {
\tfor (uint32_t i = 0; i < num_dwords;) {
\t\tconst uint32_t h = ib[i], type = h >> 30u;
\t\tuint32_t       len = 1;
\t\tif (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
\t\tif (type == 3) {
\t\t\tconst uint32_t op = (h >> 8u) & 0xffu;
\t\t\tif (op == 0x15 || op == 0x16 || op == 0x3f) return true; // DISPATCH_DIRECT, DISPATCH_INDIRECT, INDIRECT_BUFFER
\t\t}
\t\ti += len;
\t}
\treturn false;
}
static std::vector<uint32_t> acb_restore_runs(const bc5::full_state::Tracker& t, size_t* regs) {
\tstd::vector<uint32_t> p, vals;
\tuint32_t              first = 0;
\tsize_t                n     = 0;
\tconst auto flush = [&] {
\t\tif (vals.empty()) return;
\t\tp.push_back(0xC0007600u | (static_cast<uint32_t>(vals.size()) << 16u)); // SET_SH_REG, COUNT = body dwords - 1
\t\tp.push_back(first);
\t\tp.insert(p.end(), vals.begin(), vals.end());
\t\tn += vals.size();
\t\tvals.clear();
\t};
\tfor (uint32_t o = 0x204u; o < 0x400u; o++) {
\t\tuint32_t v = 0;
\t\tif (o == 0x214u || !t.get(bc5::full_state::Sh, o, v)) { // COMPUTE_VMID is the kernel's: never replayed
\t\t\tflush();
\t\t\tcontinue;
\t\t}
\t\tif (vals.empty()) first = o;
\t\tvals.push_back(v);
\t}
\tflush();
\t*regs = n;
\treturn p;
}
"""
RESTORE_SPLIT = b"""\t// Experiment 0381 (F679): the graphics queue's compute registers back after a merged acb, by the CS prefix's path
\t// (full_prefix + cs_used: same segment, same pieces).
\tif (!full_used && std::strcmp(kind, "dcb") == 0 && g_dev && acb_restore_on() && acb_restore_wants(ib, num_dwords)) {
\t\tsize_t                       regs = 0;
\t\tstd::vector<uint32_t>        re   = acb_restore_runs(t_fs_before, &regs);
\t\tstatic std::atomic<uint64_t> n_re {0};
\t\tconst uint64_t               k = n_re++;
\t\tif (k < 16 || (k & 0x3ffu) == 0)
\t\t\tjournal("acb state restore (exp 0381): t %.3f s dcb %u dwords, %zu registers in %zu dwords (%" PRIu64 " such buffers)\\n", timing_now(), num_dwords, regs, re.size(), k + 1);
\t\tif (!re.empty()) {
\t\t\tfull_prefix.swap(re);
\t\t\tfull_used = cs_used = true;
\t\t}
\t}
"""
ACB_SPLIT = b"""\tif (!full_used && std::strcmp(kind, "acb") == 0) { // experiment 0401: the acb's own queue state, as the CS prefix above for a dcb
\t\tstd::vector<uint32_t> cs = acb_cs_prefix(ib, num_dwords);
\t\tif (!cs.empty()) {
\t\t\tfull_prefix.swap(cs);
\t\t\tfull_used = cs_used = true;
\t\t}
\t}
"""
def acb_edits(restore=False):
    """Series b: the acb CS prefix. Series c (restore): also exp 0381's ACB_STATE_RESTORE."""
    e = [
        (b"static void submit_segment(const uint32_t* ib, uint32_t num_dwords, uint32_t from, uint32_t to) {\n", ACB_DECL, "before"),
        (ACB_SEGMENT_OLD, ACB_SEGMENT_NEW, "replace"),
        (b"static bool ib_has_draw(const uint32_t* ib, uint32_t num_dwords) {\n", ACB_FUNCTIONS + (RESTORE_FUNCTIONS if restore else b""), "before"),
        (b"\t// Experiment 0118: a piece goes to the GPU as one job with its full-state prefix in front. As two\n",
         (RESTORE_SPLIT if restore else b"") + ACB_SPLIT, "before"),
        (b"\t\t\t\t\t\tsubmit_split(t + skip, tn - skip, \"acb\");\n", b"\t\t\t\t\t\tacb_cs_track(t + skip, tn - skip); // experiment 0401\n", "after"),
    ]
    if restore:
        e.append((b"\t\tif (t_fs_valid || prefix_all() || cs_prefix_mode() != 0) t_fs_before = tracker;\n",
                  b"\t\tif (t_fs_valid || prefix_all() || cs_prefix_mode() != 0 || acb_restore_on()) t_fs_before = tracker; // + exp 0381\n", "replace"))
    return tuple(e)


ACB_EDITS = acb_edits()


# Series e (2026-11-03, the top session's GO on the maintainer's "Buduj"): the submit-time table catcher, a fifth switch.
CATCH_FUNCTIONS = b"""// Experiment 0401 series e (BC5_DIRECT_TABLE_CATCHER=1, default off; F403 sub-class B, exp 0402 item 4): the submit-time
// table catcher. The idea is sharpemu 11506fc's (src/SharpEmu.Libs/Agc/AgcExports.Submissions.cs, CaptureSubmittedTables,
// GPL-2.0-or-later: titles rewrite their tables soon after submit); no code is taken from it. At submit, submit_now's walk
// hashes the memory each running indirect packet names: the arguments of DRAW_INDIRECT (0x24, 16 bytes), DRAW_INDEX_INDIRECT
// (0x25, 20), DISPATCH_INDIRECT (0x16, 12; both forms, as the walk reads them) and up to 16 records of the multi-draw packets
// (0x2c, 0x38; count and stride where exp 0054 reads them), at the SET_BASE index-1 base the walk tracks; and the (offset,
// value) tables of LOAD_SH/UCONFIG/CONTEXT_REG_INDEX (0x63, 0x64, 0x9f), in the layout timeout_probe's load_pairs reads
// (exp 0160). The argument sizes are the Vulkan indirect command structs radv passes to these packets unchanged
// (TODO(verify) on the console). At the job's completion, and at a fence timeout before timeout_probe, the same memory is
// hashed again (FNV-1a) and each change is journaled with the first five dwords at submit and now. Not walked: buffers
// reached through INDIRECT_BUFFER (IB2s); the other LOAD_*_REG_INDEX format (offset and size) is counted, not hashed.
// A change says the slot was written between submit and completion; it does not say whether the GPU read the old values
// or the new ones.
struct CatchSlot {
\tuint64_t addr  = 0;
\tuint32_t bytes = 0, at = 0, op = 0;
\tuint64_t hash  = 0;
\tuint32_t v[5]  = {};
};
static bool table_catcher_on() {
\tstatic const bool        on = bc5::env_on(std::getenv("BC5_DIRECT_TABLE_CATCHER"));
\tstatic std::atomic<bool> told {false};
\tif (!told.exchange(true))
\t\tjournal("exp 0401: table catcher %s\\n", on ? "on (indirect arguments and LOAD_*_REG_INDEX tables hashed at submit, compared at completion and at a timeout)" : "off");
\treturn on;
}
static std::atomic<uint64_t> g_catch_bufs {0}, g_catch_slots {0}, g_catch_changed {0}, g_catch_gone {0}, g_catch_skipped {0};
static uint64_t catch_hash(uint64_t a, uint32_t bytes) {
\tconst auto* t = reinterpret_cast<const volatile uint32_t*>(a);
\tuint64_t    h = 0xcbf29ce484222325ull; // FNV-1a, 64 bits, a dword at a time
\tfor (uint32_t k = 0; k < bytes / 4; k++) {
\t\th ^= t[k];
\t\th *= 0x100000001b3ull;
\t}
\treturn h;
}
static void catch_add(std::vector<CatchSlot>& out, const std::vector<bc5::direct::Mapping>& maps, uint32_t op, uint32_t at, uint64_t a, uint32_t bytes) {
\tbytes &= ~3u;
\tif (out.size() >= 256 || a == 0 || bytes < 4 || bytes > 65536 || !covered_sorted(maps, a, bytes)) {
\t\tg_catch_skipped++;
\t\treturn;
\t}
\tCatchSlot s;
\ts.addr       = a;
\ts.bytes      = bytes;
\ts.at         = at;
\ts.op         = op;
\ts.hash       = catch_hash(a, bytes);
\tconst auto* t = reinterpret_cast<const volatile uint32_t*>(a);
\tfor (uint32_t k = 0; k < 5 && k < bytes / 4; k++) s.v[k] = t[k];
\tout.push_back(s);
\tg_catch_slots++;
}
static void catch_check(const std::vector<CatchSlot>& slots, bool at_timeout, uint64_t n, const char* kind) {
\tif (slots.empty() || !g_dev) return;
\tstd::shared_ptr<const std::vector<bc5::direct::Mapping>> maps_p = g_dev->sorted_mappings();
\tuint32_t changed = 0;
\tfor (const CatchSlot& s: slots) {
\t\tif (!covered_sorted(*maps_p, s.addr, s.bytes)) {
\t\t\tg_catch_gone++;
\t\t\tcontinue;
\t\t}
\t\tif (catch_hash(s.addr, s.bytes) == s.hash) continue;
\t\tchanged++;
\t\tconst uint64_t k = g_catch_changed++;
\t\tif (at_timeout ? changed <= 64 : (k < 64 || (k & 0x3ffu) == 0)) {
\t\t\tconst auto* t    = reinterpret_cast<const volatile uint32_t*>(s.addr);
\t\t\tuint32_t    v[5] = {};
\t\t\tfor (uint32_t i = 0; i < 5 && i < s.bytes / 4; i++) v[i] = t[i];
\t\t\tjournal("table catcher (exp 0401): at %s, submit #%" PRIu64 " %s op %02x at %u: 0x%" PRIx64 " %u bytes changed since submit: was %08x %08x %08x %08x %08x, now %08x %08x %08x %08x %08x (%" PRIu64 " changes so far)\\n",
\t\t\t        at_timeout ? "the timeout" : "completion", n, kind, s.op, s.at, s.addr, s.bytes, s.v[0], s.v[1], s.v[2], s.v[3], s.v[4], v[0], v[1], v[2], v[3], v[4], k + 1);
\t\t}
\t}
\tif (at_timeout) journal("table catcher (exp 0401): at the timeout, submit #%" PRIu64 " %s: %zu slots hashed at submit, %u changed\\n", n, kind, slots.size(), changed);
\tstatic std::atomic<uint64_t> n_checks {0};
\tif ((n_checks++ & 0xffffu) == 0)
\t\tjournal("table catcher (exp 0401): %" PRIu64 " buffers, %" PRIu64 " slots hashed, %" PRIu64 " changed, %" PRIu64 " unmapped at the check, %" PRIu64 " not hashed\\n", g_catch_bufs.load(),
\t\t        g_catch_slots.load(), g_catch_changed.load(), g_catch_gone.load(), g_catch_skipped.load());
}

"""
CATCH_DECL = b"""\tconst bool             catch_on = table_catcher_on(); // experiment 0401 series e: the table catcher's slots of this buffer
\tstd::vector<CatchSlot> catch_slots;
\tif (catch_on) g_catch_bufs++;
"""
CATCH_WALK = b"""\t\t\tif (catch_on && type == 3) { // experiment 0401 series e: the table catcher
\t\t\t\tif ((op == 0x24 || op == 0x25 || op == 0x16) && len >= 2) {
\t\t\t\t\tconst bool     cmec = compute_ib && op == 0x16 && len == 4;
\t\t\t\t\tconst uint64_t ca   = cmec ? ((ib[q + 1] & ~3ull) | (static_cast<uint64_t>(ib[q + 2] & 0xffffu) << 32u)) : (base1 != 0 ? base1 + ib[q + 1] : 0);
\t\t\t\t\tcatch_add(catch_slots, *maps_p, op, q, ca, op == 0x16 ? 12u : op == 0x24 ? 16u : 20u);
\t\t\t\t} else if ((op == 0x2c || op == 0x38) && len >= 10) {
\t\t\t\t\tconst uint32_t one = op == 0x2c ? 16u : 20u, count = ib[q + 5], stride = ib[q + 8];
\t\t\t\t\tcatch_add(catch_slots, *maps_p, op, q, base1 != 0 ? base1 + ib[q + 1] : 0, stride >= one && stride <= 256u && count >= 1 ? std::min(count, 16u) * stride : one);
\t\t\t\t} else if ((op == 0x63 || op == 0x64 || op == 0x9f) && len >= 5) {
\t\t\t\t\tif ((ib[q + 3] >> 31u) != 0) catch_add(catch_slots, *maps_p, op, q, (ib[q + 1] & ~3u) | (static_cast<uint64_t>(ib[q + 2] & 0xffffu) << 32u), (ib[q + 4] & 0x3fffu) * 8u);
\t\t\t\t\telse g_catch_skipped++;
\t\t\t\t}
\t\t\t}
"""


def catcher_edits():
    """Series e: the table catcher (BC5_DIRECT_TABLE_CATCHER)."""
    return (
        (b"// ---- experiment 0024: jobs in flight ---------------------------------------------------------\n", CATCH_FUNCTIONS, "before"),
        (b"\tstd::vector<GeProbeSlot> ge_probe; // experiment 0160: the register captures inserted in front of its draws\n",
         b"\tstd::vector<CatchSlot>   catch_slots; // experiment 0401 series e: the table catcher's slots\n", "after"),
        (b"\tbool                  mec_expand_ib = false; // experiment 0038: rebuild the IB with GFX-form dispatches\n", CATCH_DECL, "before"),
        (b"\t\t\tif (type == 3 && op == 0x11 && len >= 4 && (ib[q + 1] & 0xfu) == 1) {\n", CATCH_WALK, "before"),
        (b"\tif (r.timed_out) timeout_probe(sub_ib, sub_n, kind, g_submits.load(), &r.executed_offsets); // experiment 0160\n",
         b"\tif (!catch_slots.empty() && (r.timed_out || !r.pending)) catch_check(catch_slots, r.timed_out, n, kind); // experiment 0401 series e\n", "before"),
        (b"\t\tif (BC5_DIAG_ENV(\"BC5_DIRECT_TIMEOUT_PROBE\") != nullptr) { it.job.ib_copy.assign(sub_ib, sub_ib + sub_n); it.job.ran_copy = r.executed_offsets; } // experiment 0160\n",
         b"\t\tit.job.catch_slots.swap(catch_slots); // experiment 0401 series e\n", "after"),
        (b"\t\t\tif (r.timed_out && !j.ib_copy.empty()) timeout_probe(j.ib_copy.data(), static_cast<uint32_t>(j.ib_copy.size()), j.kind, j.n, &j.ran_copy, &j.ge_probe); // experiment 0160\n",
         b"\t\t\tif (!j.catch_slots.empty() && r.rc != -125) catch_check(j.catch_slots, r.timed_out, j.n, j.kind); // experiment 0401 series e\n", "before"),
    )


# Series e2 (2026-11-03, the top session's GO; exp 0403's Verdict and "Proposed switch", bd3744c5): BC5_DIRECT_ACB_INHERIT.
INHERIT_DECL = b"""static int                   acb_inherit_mode(); // experiment 0403 (BC5_DIRECT_ACB_INHERIT), defined with the CS prefix below
static std::vector<uint32_t> acb_inherit_prefix(const uint32_t* part, uint32_t n, uint32_t from);
static void                  acb_inherit_track(const uint32_t* part, uint32_t n);
static void                  acb_inherit_census(const uint32_t* p, uint32_t len);
static void                  acb_inherit_census_slice();
static bool                  acb_inherit_take(const uint32_t* p);
static thread_local uint32_t t_acb_from = 0; // experiment 0403: where in its title buffer the acb part submit_split gets starts
"""
INHERIT_FUNCTIONS = b"""// Experiment 0403 (exp 0401 series e2; BC5_DIRECT_ACB_INHERIT=journal|wave|skip, default off): an acb part that dispatches
// before it sets a program (cs_inherit_at), after exp 0403's Verdict. The 08:49 head (#432910) dispatched with initiator
// 0x8061, which has CS_W32_EN (bit 15, as exp 0403 reads COMPUTE_DISPATCH_INITIATOR; TODO(verify) in Mesa's gfx10 register
// JSON), before its own wave64 programs. The GFX ring handed it a dcb's wave64 program (the hang), and exp 0401's prefix
// handed it the queue's wave64 0x0909... program (the crashes). Per guest queue (t_queue_idx), the switch keeps the compute
// registers (cs_prefix: SH 0x204-0x3ff) and USER_DATA_0..3 (SH 0x240-0x243) as they stood at the queue's last wave32 and
// last wave64 dispatch. The bit read is the initiator, the last dword of DISPATCH_DIRECT and of both DISPATCH_INDIRECT forms.
// - journal: no submission changes. Each inheriting part is journaled (first 64, then every 1024th): the queue, head or rest,
//   the title offset of its first inheriting dispatch, the initiator, the queue's last W32 and W64 programs with their
//   USER_DATA_0..3, and the queue's previous three parts. Non-IB type-3 packets on each guest ring slice are counted per queue
//   (opcode; for SET_SH_REG the first register and count), journaled at the first slice and every 1024th.
// - wave: a head (offset 0 in its title buffer) gets the slot with its dispatch's wave mode in front, as exp 0401's prefix is
//   laid. With no such slot, it is skipped. A rest or segment, whose head state_prefix replays, is left as it is.
// - skip: a head's inheriting dispatches (each dispatch before the part's first packet that may set COMPUTE_PGM_LO) are
//   dropped by submit_now's filter (FilterOptions::drop_offsets, the way BC5_DIRECT_SKIP_PGM drops), so no wrong program runs.
// With BC5_DIRECT_ACB_CS_PREFIX also set, this switch wins: the acb CS prefix stays off, with one journal line.
static int acb_inherit_mode() { // 0 off, 1 journal, 2 wave, 3 skip
\tstatic const int m = [] {
\t\tconst char* e = std::getenv("BC5_DIRECT_ACB_INHERIT");
\t\tif (e == nullptr || *e == 0 || std::strcmp(e, "0") == 0) return 0;
\t\tif (std::strcmp(e, "journal") == 0) return 1;
\t\tif (std::strcmp(e, "wave") == 0) return 2;
\t\tif (std::strcmp(e, "skip") == 0) return 3;
\t\treturn -1;
\t}();
\tstatic std::atomic<bool> told {false};
\tif (!told.exchange(true)) {
\t\tstatic const char* const names[] = {"an unknown value: off", "off", "journal (no submission changes)", "wave (a head gets the queue's state of its wave mode, else it is skipped)",
\t\t                                    "skip (a head's inheriting dispatches are dropped)"};
\t\tjournal("exp 0403: acb inherit %s\\n", names[m + 1]);
\t\tif (m > 0 && bc5::env_on(std::getenv("BC5_DIRECT_ACB_CS_PREFIX"))) journal("exp 0403: BC5_DIRECT_ACB_CS_PREFIX is set too: BC5_DIRECT_ACB_INHERIT wins, the acb CS prefix stays off\\n");
\t}
\treturn m < 0 ? 0 : m;
}
struct InheritQueue {
\tbc5::full_state::Tracker t;
\tstd::vector<uint32_t>    w32, w64;
\tuint64_t                 pgm32 = 0, pgm64 = 0;
\tuint32_t                 ud32[4] = {}, ud64[4] = {};
\tconst uint32_t*          prev[3] = {};
\tuint32_t                 prev_n[3] = {};
};
struct InheritCensus {
\tstd::map<uint32_t, uint64_t> ops, sh; // by opcode; SET_SH_REG by (first register << 8 | count)
\tuint64_t                     slices = 0;
};
static std::mutex                   g_inh_mutex;
static std::map<int, InheritQueue>  g_inh;        // by guest queue (t_queue_idx)
static std::map<int, InheritCensus> g_inh_census; // by guest queue
static std::set<const uint32_t*>    g_inh_drop;   // skip: the title's dispatch packets submit_now drops
static std::atomic<size_t>          g_inh_drops {0};
static uint32_t inherit_len(uint32_t h) {
\tconst uint32_t type = h >> 30u;
\tif (type != 3 && type != 0) return 1;
\tconst uint32_t c = (h >> 16u) & 0x3fffu;
\treturn c == 0x3fffu ? 1 : c + 2;
}
static void inherit_snapshot(InheritQueue& q, bool w32) {
\tuint64_t              pgm = 0;
\tstd::vector<uint32_t> s   = cs_prefix(q.t, &pgm);
\tuint32_t*             ud  = w32 ? q.ud32 : q.ud64;
\tfor (uint32_t k = 0; k < 4; k++) {
\t\tuint32_t v = 0;
\t\tud[k]      = q.t.get(bc5::full_state::Sh, 0x240u + k, v) ? v : 0u;
\t}
\t(w32 ? q.w32 : q.w64).swap(s);
\t(w32 ? q.pgm32 : q.pgm64) = pgm;
}
static void acb_inherit_track(const uint32_t* part, uint32_t n) {
\tif (acb_inherit_mode() == 0 || !g_dev || part == nullptr || n == 0) return;
\tstd::shared_ptr<const std::vector<bc5::direct::Mapping>> maps_p = g_dev->sorted_mappings();
\tconst bc5::full_state::Tracker::Reader read = [&maps_p](uint64_t a, uint64_t bytes) -> const uint32_t* {
\t\treturn covered_sorted(*maps_p, a, bytes) ? reinterpret_cast<const uint32_t*>(a) : nullptr;
\t};
\tuint32_t end32 = 0, end64 = 0; // the ends of the part's last wave32 and last wave64 dispatch: two snapshots at most
\tfor (uint32_t i = 0; i < n;) {
\t\tconst uint32_t h = part[i], len = inherit_len(h);
\t\tif (i + len > n) break;
\t\tconst uint32_t op = (h >> 8u) & 0xffu;
\t\tif ((h >> 30u) == 3 && (op == 0x15 || op == 0x16) && len >= 3) ((part[i + len - 1] & 0x8000u) != 0 ? end32 : end64) = i + len;
\t\ti += len;
\t}
\tbc5::full_state::Stats st;
\tstd::lock_guard        lk(g_inh_mutex);
\tInheritQueue&          q    = g_inh[t_queue_idx];
\tconst uint32_t         a    = std::min(end32, end64), b = std::max(end32, end64);
\tuint32_t               done = 0;
\tif (a != 0) {
\t\tq.t.apply(std::span<const uint32_t>(part, a), read, st);
\t\tdone = a;
\t\tinherit_snapshot(q, a == end32);
\t}
\tif (b != 0 && b != a) {
\t\tq.t.apply(std::span<const uint32_t>(part + done, b - done), read, st);
\t\tdone = b;
\t\tinherit_snapshot(q, b == end32);
\t}
\tif (done < n) q.t.apply(std::span<const uint32_t>(part + done, n - done), read, st);
\tfor (int k = 2; k > 0; k--) {
\t\tq.prev[k]   = q.prev[k - 1];
\t\tq.prev_n[k] = q.prev_n[k - 1];
\t}
\tq.prev[0]   = part;
\tq.prev_n[0] = n;
}
static std::vector<uint32_t> acb_inherit_prefix(const uint32_t* part, uint32_t n, uint32_t from) {
\tconst int mode = acb_inherit_mode();
\tif (mode == 0 || !g_dev || part == nullptr || n == 0) return {};
\tstd::shared_ptr<const std::vector<bc5::direct::Mapping>> maps_p = g_dev->sorted_mappings();
\tconst int                                                at     = cs_inherit_at(part, n, *maps_p);
\tif (at < 0) return {};
\tstd::vector<uint32_t> inh; // each dispatch before the part's first packet that may set the program
\tfor (uint32_t base = 0; base < n;) {
\t\tconst int k = cs_inherit_at(part + base, n - base, *maps_p);
\t\tif (k < 0) break;
\t\tconst uint32_t o = base + static_cast<uint32_t>(k);
\t\tinh.push_back(o);
\t\tbase = o + inherit_len(part[o]);
\t}
\tconst uint32_t        init = part[static_cast<uint32_t>(at) + inherit_len(part[at]) - 1];
\tconst bool            w32 = (init & 0x8000u) != 0, head = from == 0;
\tstd::vector<uint32_t> pre;
\tuint64_t              pgm32 = 0, pgm64 = 0;
\tuint32_t              ud32[4] = {}, ud64[4] = {}, prev_n[3] = {};
\tconst uint32_t*       prev[3] = {};
\tbool                  have32 = false, have64 = false;
\t{
\t\tstd::lock_guard lk(g_inh_mutex);
\t\tconst auto      it = g_inh.find(t_queue_idx);
\t\tif (it != g_inh.end()) {
\t\t\tconst InheritQueue& q = it->second;
\t\t\tpgm32 = q.pgm32;
\t\t\tpgm64 = q.pgm64;
\t\t\thave32 = !q.w32.empty();
\t\t\thave64 = !q.w64.empty();
\t\t\tstd::memcpy(ud32, q.ud32, sizeof(ud32));
\t\t\tstd::memcpy(ud64, q.ud64, sizeof(ud64));
\t\t\tfor (int k = 0; k < 3; k++) {
\t\t\t\tprev[k]   = q.prev[k];
\t\t\t\tprev_n[k] = q.prev_n[k];
\t\t\t}
\t\t\tif (mode == 2 && head) pre = w32 ? q.w32 : q.w64;
\t\t}
\t}
\tconst bool skip = head && (mode == 3 || (mode == 2 && pre.empty()));
\tif (skip) {
\t\tstd::lock_guard lk(g_inh_mutex);
\t\tif (g_inh_drop.size() > 4096) g_inh_drop.clear(); // parts that never reached submit_now leave entries behind
\t\tfor (const uint32_t o: inh) g_inh_drop.insert(part + o);
\t\tg_inh_drops = g_inh_drop.size();
\t}
\tstatic std::atomic<uint64_t> n_inh {0};
\tconst uint64_t               k = n_inh++;
\tif (k < 64 || (k & 0x3ffu) == 0)
\t\tjournal("acb inherit (exp 0403): t %.3f s queue %d %s part %u dwords from offset %u: %zu inheriting dispatches, the first at %u, initiator 0x%x (%s); the queue's last W32 program 0x%010" PRIx64 "%s ud0-3 %08x %08x %08x %08x, last W64 0x%010" PRIx64 "%s ud0-3 %08x %08x %08x %08x; previous parts %p+%u %p+%u %p+%u; %s, %zu dwords in front (%" PRIu64 " such parts)\\n",
\t\t        timing_now(), t_queue_idx, head ? "head" : "rest", n, from, inh.size(), from + static_cast<uint32_t>(at), init, w32 ? "W32" : "W64", pgm32, have32 ? "" : " (none)", ud32[0], ud32[1],
\t\t        ud32[2], ud32[3], pgm64, have64 ? "" : " (none)", ud64[0], ud64[1], ud64[2], ud64[3], static_cast<const void*>(prev[0]), prev_n[0], static_cast<const void*>(prev[1]), prev_n[1],
\t\t        static_cast<const void*>(prev[2]), prev_n[2], mode == 1 ? "journal only" : !head ? "a rest: left as it is" : skip ? "dropped" : "prefixed", pre.size(), k + 1);
\treturn pre;
}
static bool acb_inherit_take(const uint32_t* p) {
\t{
\t\tstd::lock_guard lk(g_inh_mutex);
\t\tconst auto      it = g_inh_drop.find(p);
\t\tif (it == g_inh_drop.end()) return false;
\t\tg_inh_drop.erase(it);
\t\tg_inh_drops = g_inh_drop.size();
\t}
\tstatic std::atomic<uint64_t> n_drop {0};
\tconst uint64_t               k = n_drop++;
\tif (k < 64 || (k & 0x3ffu) == 0) journal("acb inherit (exp 0403): the inheriting dispatch at %p dropped (%" PRIu64 " so far)\\n", static_cast<const void*>(p), k + 1);
\treturn true;
}
static void acb_inherit_census(const uint32_t* p, uint32_t len) {
\tif (acb_inherit_mode() == 0 || p == nullptr || len == 0) return;
\tconst uint32_t  op = (p[0] >> 8u) & 0xffu;
\tstd::lock_guard lk(g_inh_mutex);
\tInheritCensus&  c = g_inh_census[t_queue_idx];
\tc.ops[op]++;
\tif (op == 0x76 && len >= 3) c.sh[((p[1] & 0xffffu) << 8u) | std::min<uint32_t>(len - 2, 255u)]++;
}
static void acb_inherit_census_slice() {
\tif (acb_inherit_mode() == 0) return;
\tstd::string line;
\tuint64_t    k = 0;
\t{
\t\tstd::lock_guard lk(g_inh_mutex);
\t\tInheritCensus&  c = g_inh_census[t_queue_idx];
\t\tk                 = c.slices++;
\t\tif (k != 0 && (k & 0x3ffu) != 0) return;
\t\tchar b[64];
\t\tfor (const auto& [op, cnt]: c.ops) {
\t\t\tstd::snprintf(b, sizeof(b), " op %02x x%" PRIu64, op, cnt);
\t\t\tif (line.size() < 1400) line += b;
\t\t}
\t\tfor (const auto& [key, cnt]: c.sh) {
\t\t\tstd::snprintf(b, sizeof(b), " sh 0x%x+%u x%" PRIu64, key >> 8u, key & 0xffu, cnt);
\t\t\tif (line.size() < 1400) line += b;
\t\t}
\t}
\tjournal("acb inherit census (exp 0403): queue %d after %" PRIu64 " ring slices, non-IB type-3 packets:%s\\n", t_queue_idx, k + 1, line.empty() ? " none" : line.c_str());
}

"""
INHERIT_DROP = b"""\t\t\tif (type == 3 && (op == 0x15 || op == 0x16) && g_inh_drops.load(std::memory_order_relaxed) != 0) { // experiment 0403: skip
\t\t\t\tconst uint32_t* gq = chain == nullptr ? ib + q : nullptr; // the title's address of this packet
\t\t\t\tif (chain != nullptr) {
\t\t\t\t\tfor (const ChainSeg& s: chain->segs) {
\t\t\t\t\t\tif (s.src != nullptr && q >= s.off + s.prefix && q < s.off + s.prefix + s.n) {
\t\t\t\t\t\t\tgq = s.src + (q - s.off - s.prefix);
\t\t\t\t\t\t\tbreak;
\t\t\t\t\t\t}
\t\t\t\t\t}
\t\t\t\t}
\t\t\t\tif (gq != nullptr && acb_inherit_take(gq)) {
\t\t\t\t\topt.drop_offsets.push_back(q);
\t\t\t\t\tq += len;
\t\t\t\t\tcontinue;
\t\t\t\t}
\t\t\t}
"""


# Series e3 (2026-11-03, the top session after Codex's review of e2): a slot only from a dispatch that follows the part's
# own program write. inherit_plan is pure, so the same text is also written to inherit_scan.inc for the CPU test.
INHERIT_SCAN = b"""// Series e3 (exp 0403, Codex's review of e2: e2 filled a slot by the initiator bit alone, so an inheriting W32 dispatch
// stored the program it inherited as the queue's "W32 program"). Where an acb part's own program binding starts, by
// cs_inherit_at's packets that set COMPUTE_PGM_LO (SH 0x20c), counting only certain writes: SET_SH_REG(_INDEX) 0x76 / 0x9b
// over it, LOAD_SH_REG 0x5f with a range over it, LOAD_SH_REG_INDEX 0x63 in the offset format with a range over it or with
// a pair table (DATA_FORMAT bit 31) that can be read and names it. An unreadable pair table and an INDIRECT_BUFFER (0x3f)
// may set it but do not count. A dispatch (0x15 / 0x16) after a certain write may fill the slot of its wave mode
// (initiator bit 15, CS_W32_EN, the packet's last dword); one before any is counted as unknown and fills nothing.
struct InheritPlan {
\tuint32_t end32 = 0, end64 = 0;         // the end of the part's last W32 / W64 dispatch after its own program write; 0: none
\tuint32_t unknown32 = 0, unknown64 = 0; // dispatches before any certain program write
};
template <class Read>
static InheritPlan inherit_plan(const uint32_t* part, uint32_t n, const Read& read) {
\tconstexpr uint32_t kPgmLo = 0x20cu;
\tInheritPlan        p;
\tbool               bound = false;
\tfor (uint32_t i = 0; i < n;) {
\t\tconst uint32_t h = part[i], type = h >> 30u;
\t\tuint32_t       len = 1;
\t\tif (type == 3 || type == 0) {
\t\t\tconst uint32_t c = (h >> 16u) & 0x3fffu;
\t\t\tlen              = c == 0x3fffu ? 1 : c + 2;
\t\t}
\t\tif (i + len > n) break;
\t\tif (type == 3) {
\t\t\tconst uint32_t  op = (h >> 8u) & 0xffu;
\t\t\tconst uint32_t* q  = part + i;
\t\t\tif ((op == 0x76 || op == 0x9b) && len >= 3 && kPgmLo - (q[1] & 0xffffu) < len - 2) bound = true;
\t\t\tif (op == 0x5f && len >= 5) {
\t\t\t\tfor (uint32_t k = 3; k + 1 < len; k += 2) {
\t\t\t\t\tif (kPgmLo - (q[k] & 0xffffu) < (q[k + 1] & 0x3fffu)) bound = true;
\t\t\t\t}
\t\t\t}
\t\t\tif (op == 0x63 && len >= 5 && (q[4] & 0x3fffu) != 0) {
\t\t\t\tconst uint32_t tn = q[4] & 0x3fffu;
\t\t\t\tif ((q[3] >> 31u) == 0) {
\t\t\t\t\tif (kPgmLo - (q[3] & 0xffffu) < tn) bound = true;
\t\t\t\t} else {
\t\t\t\t\tconst uint64_t  ta = (q[1] & ~3u) | (static_cast<uint64_t>(q[2] & 0xffffu) << 32u);
\t\t\t\t\tconst uint32_t* t  = ta != 0 ? read(ta, static_cast<uint64_t>(tn) * 8u) : nullptr;
\t\t\t\t\tfor (uint32_t k = 0; t != nullptr && k < tn; k++) {
\t\t\t\t\t\tif ((t[2 * k] & 0xffffu) == kPgmLo) bound = true;
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t\tif ((op == 0x15 || op == 0x16) && len >= 3) {
\t\t\t\tconst bool w32 = (part[i + len - 1] & 0x8000u) != 0;
\t\t\t\tif (bound) (w32 ? p.end32 : p.end64) = i + len;
\t\t\t\telse (w32 ? p.unknown32 : p.unknown64)++;
\t\t\t}
\t\t}
\t\ti += len;
\t}
\treturn p;
}
"""


# Series e3 as built (2026-11-03 18:5x, the top session after exp 0403's addendum a423f761): the queue's own live state, not
# per-wave slots. The draft above (--inherit2, unit 989ca24b, binary 8b4efb9b in exp0401e3w) is kept for the record only.
INHERIT_SCAN3 = b"""// Series e3 (exp 0403's addendum, a423f761, and Codex's review of e2): which dispatches of an acb part run a program the
// part set itself. A dispatch (0x15 / 0x16) is "bound" when a packet that certainly sets COMPUTE_PGM_LO (SH 0x20c) comes
// before it in the same part: SET_SH_REG(_INDEX) 0x76 / 0x9b over it, LOAD_SH_REG 0x5f with a range over it,
// LOAD_SH_REG_INDEX 0x63 in the offset format with a range over it or with a pair table (DATA_FORMAT bit 31) that can be
// read and names it (cs_inherit_at's packets). An unreadable pair table and an INDIRECT_BUFFER (0x3f) may set it too, so
// after one the part's own program is no longer known: dispatches are unbound again until the next certain write (Codex's
// second review). w32 is the initiator's bit 15, CS_W32_EN, the packet's last dword (exp 0403 section 2; TODO(verify) in
// the register database). Only bound dispatches say which wave mode the title uses with a program. The return value is
// what the part leaves behind: 1 when its last packet that touches the program is a certain write, 0 when it is one that
// may set it unseen (the queue's program is then not known), -1 when it has none (the queue's state carries over).
struct InheritDispatch {
\tuint32_t at = 0, end = 0; // the packet's offset in the part, and the offset after it
\tbool     w32 = false, bound = false;
};
template <class Read>
static int inherit_scan(const uint32_t* part, uint32_t n, const Read& read, std::vector<InheritDispatch>& out) {
\tconstexpr uint32_t kPgmLo = 0x20cu;
\tbool               bound  = false;
\tint                state  = -1;
\tconst auto         sure   = [&bound, &state] {
\t\tbound = true;
\t\tstate = 1;
\t};
\tconst auto lost = [&bound, &state] {
\t\tbound = false;
\t\tstate = 0;
\t};
\tfor (uint32_t i = 0; i < n;) {
\t\tconst uint32_t h = part[i], type = h >> 30u;
\t\tuint32_t       len = 1;
\t\tif (type == 3 || type == 0) {
\t\t\tconst uint32_t c = (h >> 16u) & 0x3fffu;
\t\t\tlen              = c == 0x3fffu ? 1 : c + 2;
\t\t}
\t\tif (i + len > n) break;
\t\tif (type == 3) {
\t\t\tconst uint32_t  op = (h >> 8u) & 0xffu;
\t\t\tconst uint32_t* q  = part + i;
\t\t\tif ((op == 0x76 || op == 0x9b) && len >= 3 && kPgmLo - (q[1] & 0xffffu) < len - 2) sure();
\t\t\tif (op == 0x5f && len >= 5) {
\t\t\t\tfor (uint32_t k = 3; k + 1 < len; k += 2) {
\t\t\t\t\tif (kPgmLo - (q[k] & 0xffffu) < (q[k + 1] & 0x3fffu)) sure();
\t\t\t\t}
\t\t\t}
\t\t\tif (op == 0x63 && len >= 5 && (q[4] & 0x3fffu) != 0) {
\t\t\t\tconst uint32_t tn = q[4] & 0x3fffu;
\t\t\t\tif ((q[3] >> 31u) == 0) {
\t\t\t\t\tif (kPgmLo - (q[3] & 0xffffu) < tn) sure();
\t\t\t\t} else {
\t\t\t\t\tconst uint64_t  ta = (q[1] & ~3u) | (static_cast<uint64_t>(q[2] & 0xffffu) << 32u);
\t\t\t\t\tconst uint32_t* t  = ta != 0 ? read(ta, static_cast<uint64_t>(tn) * 8u) : nullptr;
\t\t\t\t\tif (t == nullptr) lost(); // may set it: the part's own program is not known any more
\t\t\t\t\tfor (uint32_t k = 0; t != nullptr && k < tn; k++) {
\t\t\t\t\t\tif ((t[2 * k] & 0xffffu) == kPgmLo) sure();
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t\tif (op == 0x3f) lost(); // an IB2 may set it too
\t\t\tif ((op == 0x15 || op == 0x16) && len >= 3) out.push_back(InheritDispatch {i, i + len, (part[i + len - 1] & 0x8000u) != 0, bound});
\t\t}
\t\ti += len;
\t}
\treturn state;
}
"""
INHERIT_FUNCTIONS3 = b"""// Experiment 0403 (exp 0401 series e3; BC5_DIRECT_ACB_INHERIT=journal|queue|skip, default off), after 0403's addendum
// (a423f761). An acb part that dispatches before it sets a program (cs_inherit_at) needs its guest queue's own register
// state at the end of the queue's previous buffer, whatever the wave mode: a console compute queue keeps one state from IB
// to IB, and the driver's 2-dword NOP IB in between does not change it. Series e2's per-wave slots are withdrawn; they also
// recorded inherited programs (Codex's review).
// - Tracking, in every mode: per guest queue (t_queue_idx), the live compute state (bc5::full_state::Tracker over all of
//   its parts). Per program address (COMPUTE_PGM_LO/HI), the wave modes the title used with it in a part that set it itself
//   (inherit_scan's bound dispatches), and the queue and part that last did. Per physical ring, the guest queue of its last
//   tracked part (exp 0403's difference 3).
// - journal: no submission changes. Each inheriting part gets a line (the first 64, then every 1024th): queue, head or rest,
//   the part's address, its first inheriting dispatch and initiator, and the queue's live program with USER_DATA_0..3. Also
//   that program's provenance and own-wave counts, and UNSEEN when no dispatch of the title's own with it in this wave
//   mode has been seen (not observed: no evidence of an illegal shader or of a wrong order, Codex's second review). Also
//   whether the physical ring last ran a part of the same queue, the queue's previous three parts with their first two
//   dwords, and the counts below. The census of non-IB packets on the guest rings stays.
// - queue: a head (offset 0 in its title buffer) gets the queue's live state in front (cs_prefix, SH 0x204-0x3ff), as exp
//   0401's prefix does, but on heads only, and only when that state is known: a tracked program, set by a certain write
//   that no IB2 or unreadable table voided since (inherit_scan's end state), and seen with the dispatch's wave mode.
//   Otherwise nothing is put in front and the part keeps today's behaviour, the ring's state: "unknown, fallback ring"
//   (the top session's decision, 2026-11-03). Prefixes and fallbacks are counted apart, so a clean play in this mode
//   cannot come from silent drops.
// - skip: a head's inheriting dispatches are dropped by submit_now's filter (drop_offsets), the way BC5_DIRECT_SKIP_PGM
//   drops them. This is the only mode that drops.
// Rests and segments, whose head state_prefix replays, are left as they are in every mode. With BC5_DIRECT_ACB_CS_PREFIX
// also set, this switch wins: the acb CS prefix stays off, with one journal line.
""" + INHERIT_SCAN3 + b"""static int acb_inherit_mode() { // 0 off, 1 journal, 2 queue, 3 skip
\tstatic const int m = [] {
\t\tconst char* e = std::getenv("BC5_DIRECT_ACB_INHERIT");
\t\tif (e == nullptr || *e == 0 || std::strcmp(e, "0") == 0) return 0;
\t\tif (std::strcmp(e, "journal") == 0) return 1;
\t\tif (std::strcmp(e, "queue") == 0) return 2;
\t\tif (std::strcmp(e, "skip") == 0) return 3;
\t\treturn -1;
\t}();
\tstatic std::atomic<bool> told {false};
\tif (!told.exchange(true)) {
\t\tstatic const char* const names[] = {"an unknown value: off", "off", "journal (no submission changes)",
\t\t                                    "queue (a head gets its queue's live state when it is known, else the ring's; no drops)", "skip (a head's inheriting dispatches are dropped)"};
\t\tjournal("exp 0403: acb inherit %s\\n", names[m + 1]);
\t\tif (m > 0 && bc5::env_on(std::getenv("BC5_DIRECT_ACB_CS_PREFIX"))) journal("exp 0403: BC5_DIRECT_ACB_CS_PREFIX is set too: BC5_DIRECT_ACB_INHERIT wins, the acb CS prefix stays off\\n");
\t}
\treturn m < 0 ? 0 : m;
}
struct InheritQueue {
\tbc5::full_state::Tracker t;           // the queue's live compute state
\tconst uint32_t*          prev[3] = {}; // its last three parts, newest first
\tuint32_t                 prev_n[3] = {};
\tuint64_t                 unbound = 0; // its dispatches that ran a program their part did not set
\tbool                     known   = false; // the live program came from a certain write that nothing voided since
};
struct InheritProg {
\tuint64_t        own32 = 0, own64 = 0; // the title's own dispatches with this program, by wave mode
\tint             queue = -1;           // the queue and part that last made one
\tconst uint32_t* part  = nullptr;
};
struct InheritCensus {
\tstd::map<uint32_t, uint64_t> ops, sh; // by opcode; SET_SH_REG by (first register << 8 | count)
\tuint64_t                     slices = 0;
};
static std::mutex                     g_inh_mutex;
static std::map<int, InheritQueue>    g_inh;        // by guest queue (t_queue_idx)
static std::map<uint64_t, InheritProg> g_inh_prog;  // by program address
static std::map<int, int>             g_inh_ring;   // physical ring -> the guest queue of its last tracked part
static std::map<int, InheritCensus>   g_inh_census; // by guest queue
static std::set<const uint32_t*>      g_inh_drop;   // skip: the title's dispatch packets submit_now drops
static std::atomic<size_t>            g_inh_drops {0};
static std::atomic<uint64_t>          g_inh_prefixed {0}, g_inh_fb_noprog {0}, g_inh_fb_void {0}, g_inh_fb_unseen {0}; // queue mode
static std::atomic<uint64_t>          g_inh_skip_heads {0}, g_inh_dropped {0};                                     // skip mode
static uint32_t inherit_len(uint32_t h) {
\tconst uint32_t type = h >> 30u;
\tif (type != 3 && type != 0) return 1;
\tconst uint32_t c = (h >> 16u) & 0x3fffu;
\treturn c == 0x3fffu ? 1 : c + 2;
}
static uint64_t inherit_pgm(const bc5::full_state::Tracker& t) { // COMPUTE_PGM_LO/HI as an address, as cs_prefix gives it
\tuint32_t lo = 0, hi = 0;
\tif (!t.get(bc5::full_state::Sh, 0x20cu, lo)) return 0;
\tif (!t.get(bc5::full_state::Sh, 0x20du, hi)) hi = 0;
\treturn (static_cast<uint64_t>(lo) << 8u) | (static_cast<uint64_t>(hi & 0xffu) << 40u);
}
static void acb_inherit_track(const uint32_t* part, uint32_t n) {
\tif (acb_inherit_mode() == 0 || !g_dev || part == nullptr || n == 0) return;
\tstd::shared_ptr<const std::vector<bc5::direct::Mapping>> maps_p = g_dev->sorted_mappings();
\tconst bc5::full_state::Tracker::Reader read = [&maps_p](uint64_t a, uint64_t bytes) -> const uint32_t* {
\t\treturn covered_sorted(*maps_p, a, bytes) ? reinterpret_cast<const uint32_t*>(a) : nullptr;
\t};
\tstd::vector<InheritDispatch> ds;
\tconst int end_state = inherit_scan(part, n, read, ds);
\tbc5::full_state::Stats st;
\tstd::lock_guard        lk(g_inh_mutex);
\tInheritQueue&          q    = g_inh[t_queue_idx];
\tuint32_t               done = 0;
\tfor (const InheritDispatch& d: ds) { // the program at each bound dispatch: the tracker applied up to it
\t\tif (!d.bound) {
\t\t\tq.unbound++;
\t\t\tcontinue;
\t\t}
\t\tq.t.apply(std::span<const uint32_t>(part + done, d.end - done), read, st);
\t\tdone               = d.end;
\t\tconst uint64_t pgm = inherit_pgm(q.t);
\t\tif (pgm == 0) continue;
\t\tInheritProg& p = g_inh_prog[pgm];
\t\t(d.w32 ? p.own32 : p.own64)++;
\t\tp.queue = t_queue_idx;
\t\tp.part  = part;
\t}
\tif (done < n) q.t.apply(std::span<const uint32_t>(part + done, n - done), read, st);
\tif (end_state >= 0) q.known = end_state == 1; // what this part leaves: a certain program, or one an IB2 or table voided
\tfor (int k = 2; k > 0; k--) {
\t\tq.prev[k]   = q.prev[k - 1];
\t\tq.prev_n[k] = q.prev_n[k - 1];
\t}
\tq.prev[0]          = part;
\tq.prev_n[0]        = n;
\tg_inh_ring[t_ring] = t_queue_idx;
}
static std::vector<uint32_t> acb_inherit_prefix(const uint32_t* part, uint32_t n, uint32_t from) {
\tconst int mode = acb_inherit_mode();
\tif (mode == 0 || !g_dev || part == nullptr || n == 0) return {};
\tstd::shared_ptr<const std::vector<bc5::direct::Mapping>> maps_p = g_dev->sorted_mappings();
\tconst int                                                at     = cs_inherit_at(part, n, *maps_p);
\tif (at < 0) return {};
\tstd::vector<uint32_t> inh; // each dispatch before the part's first packet that may set the program
\tfor (uint32_t base = 0; base < n;) {
\t\tconst int k = cs_inherit_at(part + base, n - base, *maps_p);
\t\tif (k < 0) break;
\t\tconst uint32_t o = base + static_cast<uint32_t>(k);
\t\tinh.push_back(o);
\t\tbase = o + inherit_len(part[o]);
\t}
\tconst uint32_t        init = part[static_cast<uint32_t>(at) + inherit_len(part[at]) - 1];
\tconst bool            w32 = (init & 0x8000u) != 0, head = from == 0;
\tstd::vector<uint32_t> pre;
\tuint64_t              pgm = 0;
\tuint32_t              ud[4] = {}, prev_n[3] = {};
\tconst uint32_t*       prev[3] = {};
\tInheritProg           prog;
\tbool                  known = false, qknown = false;
\tint                   ring_q = -1;
\t{
\t\tstd::lock_guard lk(g_inh_mutex);
\t\tconst auto      it = g_inh.find(t_queue_idx);
\t\tif (it != g_inh.end()) {
\t\t\tconst InheritQueue& q = it->second;
\t\t\tpgm                   = inherit_pgm(q.t);
\t\t\tfor (uint32_t k = 0; k < 4; k++) {
\t\t\t\tuint32_t v = 0;
\t\t\t\tud[k]      = q.t.get(bc5::full_state::Sh, 0x240u + k, v) ? v : 0u;
\t\t\t}
\t\t\tfor (int k = 0; k < 3; k++) {
\t\t\t\tprev[k]   = q.prev[k];
\t\t\t\tprev_n[k] = q.prev_n[k];
\t\t\t}
\t\t\tconst auto pit = g_inh_prog.find(pgm);
\t\t\tif (pgm != 0 && pit != g_inh_prog.end()) {
\t\t\t\tprog  = pit->second;
\t\t\t\tknown = true;
\t\t\t}
\t\t\tqknown = q.known;
\t\t\tif (mode == 2 && head && pgm != 0 && qknown && (w32 ? prog.own32 : prog.own64) != 0) {
\t\t\t\tuint64_t live = 0;
\t\t\t\tpre           = cs_prefix(q.t, &live);
\t\t\t}
\t\t}
\t\tconst auto rit = g_inh_ring.find(t_ring);
\t\tif (rit != g_inh_ring.end()) ring_q = rit->second;
\t}
\tconst bool  unseen = pgm != 0 && (w32 ? prog.own32 : prog.own64) == 0;
\tconst bool  skip   = head && mode == 3; // the only mode that drops
\tconst char* why    = pgm == 0  ? "the queue has no tracked program"
\t                     : !qknown ? "an IB2 or an unreadable table voided the state's provenance"
\t                     : unseen  ? "the program is unseen in this wave mode"
\t                               : "";
\tif (head && mode == 2) {
\t\tif (!pre.empty()) g_inh_prefixed++;
\t\telse if (pgm == 0) g_inh_fb_noprog++;
\t\telse if (!qknown) g_inh_fb_void++;
\t\telse g_inh_fb_unseen++;
\t}
\tif (skip) g_inh_skip_heads++;
\tif (skip) {
\t\tstd::lock_guard lk(g_inh_mutex);
\t\tif (g_inh_drop.size() > 4096) g_inh_drop.clear(); // parts that never reached submit_now leave entries behind
\t\tfor (const uint32_t o: inh) g_inh_drop.insert(part + o);
\t\tg_inh_drops = g_inh_drop.size();
\t}
\tuint32_t pw[3][2] = {}; // the previous parts' first two dwords, where they are still mapped
\tfor (int k = 0; k < 3; k++) {
\t\tif (prev[k] != nullptr && prev_n[k] >= 2 && covered_sorted(*maps_p, reinterpret_cast<uint64_t>(prev[k]), 8)) {
\t\t\tpw[k][0] = prev[k][0];
\t\t\tpw[k][1] = prev[k][1];
\t\t}
\t}
\tconst char* action = mode == 1      ? "journal only"
\t                     : !head        ? "a rest: left as it is"
\t                     : mode == 3    ? "dropped (skip mode)"
\t                     : !pre.empty() ? "prefixed with the queue's state"
\t                                    : "unknown, fallback ring";
\tstatic std::atomic<uint64_t> n_inh {0};
\tconst uint64_t               k = n_inh++;
\tif (k < 64 || (k & 0x3ffu) == 0)
\t\tjournal("acb inherit (exp 0403): t %.3f s queue %d %s part %p %u dwords from offset %u: %zu inheriting dispatches, the first at %u, initiator 0x%x (%s); the queue's live program 0x%010" PRIx64 " ud0-3 %08x %08x %08x %08x, %s by queue %d part %p, own W32 %" PRIu64 " W64 %" PRIu64 "%s; ring %d's last tracked part from queue %d (%s); previous parts %p+%u [%08x %08x] %p+%u [%08x %08x] %p+%u [%08x %08x]; %s%s%s%s, %zu dwords in front; so far prefixed %" PRIu64 ", fallback ring %" PRIu64 " (no program %" PRIu64 ", voided %" PRIu64 ", unseen %" PRIu64 "), skip-mode heads %" PRIu64 ", dispatches dropped %" PRIu64 " (%" PRIu64 " such parts)\\n",
\t\t        timing_now(), t_queue_idx, head ? "head" : "rest", static_cast<const void*>(part), n, from, inh.size(), from + static_cast<uint32_t>(at), init, w32 ? "W32" : "W64", pgm, ud[0], ud[1],
\t\t        ud[2], ud[3], known ? "bound last" : "never bound in a part of its own", prog.queue, static_cast<const void*>(prog.part), prog.own32, prog.own64, unseen ? ", UNSEEN (not observed in this wave mode)" : "", t_ring, ring_q,
\t\t        ring_q == t_queue_idx ? "the same queue" : ring_q < 0 ? "none yet" : "another queue", static_cast<const void*>(prev[0]), prev_n[0], pw[0][0], pw[0][1], static_cast<const void*>(prev[1]),
\t\t        prev_n[1], pw[1][0], pw[1][1], static_cast<const void*>(prev[2]), prev_n[2], pw[2][0], pw[2][1], action, why[0] != 0 ? " (" : "", why,
\t\t        why[0] != 0 ? ")" : "", pre.size(), g_inh_prefixed.load(), g_inh_fb_noprog.load() + g_inh_fb_void.load() + g_inh_fb_unseen.load(), g_inh_fb_noprog.load(),
\t\t        g_inh_fb_void.load(), g_inh_fb_unseen.load(), g_inh_skip_heads.load(), g_inh_dropped.load(), k + 1);
\treturn pre;
}
static bool acb_inherit_take(const uint32_t* p) {
\t{
\t\tstd::lock_guard lk(g_inh_mutex);
\t\tconst auto      it = g_inh_drop.find(p);
\t\tif (it == g_inh_drop.end()) return false;
\t\tg_inh_drop.erase(it);
\t\tg_inh_drops = g_inh_drop.size();
\t}
\tconst uint64_t k = g_inh_dropped++;
\tif (k < 64 || (k & 0x3ffu) == 0) journal("acb inherit (exp 0403): the inheriting dispatch at %p dropped (%" PRIu64 " so far)\\n", static_cast<const void*>(p), k + 1);
\treturn true;
}
static void acb_inherit_census(const uint32_t* p, uint32_t len) {
\tif (acb_inherit_mode() == 0 || p == nullptr || len == 0) return;
\tconst uint32_t  op = (p[0] >> 8u) & 0xffu;
\tstd::lock_guard lk(g_inh_mutex);
\tInheritCensus&  c = g_inh_census[t_queue_idx];
\tc.ops[op]++;
\tif (op == 0x76 && len >= 3) c.sh[((p[1] & 0xffffu) << 8u) | std::min<uint32_t>(len - 2, 255u)]++;
}
static void acb_inherit_census_slice() {
\tif (acb_inherit_mode() == 0) return;
\tstd::string line;
\tuint64_t    k = 0;
\t{
\t\tstd::lock_guard lk(g_inh_mutex);
\t\tInheritCensus&  c = g_inh_census[t_queue_idx];
\t\tk                 = c.slices++;
\t\tif (k != 0 && (k & 0x3ffu) != 0) return;
\t\tchar b[64];
\t\tfor (const auto& [op, cnt]: c.ops) {
\t\t\tstd::snprintf(b, sizeof(b), " op %02x x%" PRIu64, op, cnt);
\t\t\tif (line.size() < 1400) line += b;
\t\t}
\t\tfor (const auto& [key, cnt]: c.sh) {
\t\t\tstd::snprintf(b, sizeof(b), " sh 0x%x+%u x%" PRIu64, key >> 8u, key & 0xffu, cnt);
\t\t\tif (line.size() < 1400) line += b;
\t\t}
\t}
\tjournal("acb inherit census (exp 0403): queue %d after %" PRIu64 " ring slices, non-IB type-3 packets:%s\\n", t_queue_idx, k + 1, line.empty() ? " none" : line.c_str());
}

"""


def inherit_functions(v2=False):
    """e2's INHERIT_FUNCTIONS; with v2 (series e3) the slots are filled through inherit_plan and carry their provenance."""
    if not v2:
        return INHERIT_FUNCTIONS
    s = INHERIT_FUNCTIONS
    reps = (
        (b"// With BC5_DIRECT_ACB_CS_PREFIX also set, this switch wins: the acb CS prefix stays off, with one journal line.\n",
         b"// With BC5_DIRECT_ACB_CS_PREFIX also set, this switch wins: the acb CS prefix stays off, with one journal line.\n" + INHERIT_SCAN),
        (b"\tconst uint32_t*          prev[3] = {};\n\tuint32_t                 prev_n[3] = {};\n};\n",
         b"\tconst uint32_t*          prev[3] = {};\n\tuint32_t                 prev_n[3] = {};\n"
         b"\tconst uint32_t*          src32 = nullptr; // series e3: the part each slot was taken from, and the dispatch's end in it\n"
         b"\tconst uint32_t*          src64 = nullptr;\n\tuint32_t                 at32 = 0, at64 = 0;\n"
         b"\tuint64_t                 unknown32 = 0, unknown64 = 0; // series e3: dispatches whose program their part did not set\n};\n"),
        (b"static void inherit_snapshot(InheritQueue& q, bool w32) {\n",
         b"static void inherit_snapshot(InheritQueue& q, bool w32, const uint32_t* part, uint32_t at) {\n"),
        (b"\t(w32 ? q.pgm32 : q.pgm64) = pgm;\n}\n",
         b"\t(w32 ? q.pgm32 : q.pgm64) = pgm;\n\t(w32 ? q.src32 : q.src64) = part;\n\t(w32 ? q.at32 : q.at64)   = at;\n}\n"),
        (b"\tuint32_t end32 = 0, end64 = 0; // the ends of the part's last wave32 and last wave64 dispatch: two snapshots at most\n"
         b"\tfor (uint32_t i = 0; i < n;) {\n\t\tconst uint32_t h = part[i], len = inherit_len(h);\n\t\tif (i + len > n) break;\n"
         b"\t\tconst uint32_t op = (h >> 8u) & 0xffu;\n"
         b"\t\tif ((h >> 30u) == 3 && (op == 0x15 || op == 0x16) && len >= 3) ((part[i + len - 1] & 0x8000u) != 0 ? end32 : end64) = i + len;\n"
         b"\t\ti += len;\n\t}\n",
         b"\t// Series e3: a slot is filled only at a dispatch after the part's own program write (inherit_plan); two snapshots at most.\n"
         b"\tconst InheritPlan plan  = inherit_plan(part, n, read);\n\tconst uint32_t    end32 = plan.end32, end64 = plan.end64;\n"),
        (b"\t\tinherit_snapshot(q, a == end32);\n", b"\t\tinherit_snapshot(q, a == end32, part, a);\n"),
        (b"\t\tinherit_snapshot(q, b == end32);\n", b"\t\tinherit_snapshot(q, b == end32, part, b);\n"),
        (b"\tq.prev[0]   = part;\n\tq.prev_n[0] = n;\n}\n",
         b"\tq.prev[0]   = part;\n\tq.prev_n[0] = n;\n\tq.unknown32 += plan.unknown32;\n\tq.unknown64 += plan.unknown64;\n}\n"),
        (b"\tbool                  have32 = false, have64 = false;\n",
         b"\tbool                  have32 = false, have64 = false;\n\tconst uint32_t*       src32 = nullptr;\n\tconst uint32_t*       src64 = nullptr;\n"
         b"\tuint32_t              at32 = 0, at64 = 0;\n\tuint64_t              unk32 = 0, unk64 = 0;\n"),
        (b"\t\t\tif (mode == 2 && head) pre = w32 ? q.w32 : q.w64;\n",
         b"\t\t\tsrc32 = q.src32;\n\t\t\tsrc64 = q.src64;\n\t\t\tat32  = q.at32;\n\t\t\tat64  = q.at64;\n\t\t\tunk32 = q.unknown32;\n\t\t\tunk64 = q.unknown64;\n"
         b"\t\t\tif (mode == 2 && head) pre = w32 ? q.w32 : q.w64;\n"),
        (b"the queue's last W32 program 0x%010\" PRIx64 \"%s ud0-3 %08x %08x %08x %08x, last W64 0x%010\" PRIx64 \"%s ud0-3 %08x %08x %08x %08x; previous parts",
         b"the queue's last W32 program bound in its own part 0x%010\" PRIx64 \"%s ud0-3 %08x %08x %08x %08x from %p+%u, last W64 0x%010\" PRIx64 \"%s ud0-3 %08x %08x %08x %08x from %p+%u; previous parts"),
        (b"; %s, %zu dwords in front (%\" PRIu64 \" such parts)\\n\",",
         b"; %s, %zu dwords in front; dispatches with no own program so far W32 %\" PRIu64 \" W64 %\" PRIu64 \" (%\" PRIu64 \" such parts)\\n\","),
        (b"ud32[2], ud32[3], pgm64,", b"ud32[2], ud32[3], static_cast<const void*>(src32), at32, pgm64,"),
        (b"ud64[2], ud64[3], static_cast<const void*>(prev[0])", b"ud64[2], ud64[3], static_cast<const void*>(src64), at64, static_cast<const void*>(prev[0])"),
        (b"pre.size(), k + 1);", b"pre.size(), unk32, unk64, k + 1);"),
    )
    for a, b in reps:
        assert s.count(a) == 1, ("inherit v2", a[:60], s.count(a))
        s = s.replace(a, b)
    return s


MEMLINE_FUNCTIONS = b"""// Experiment 0401 series e3 (the top session, 2026-11-03: the next guest crash should show whether memory was at its
// floor): a journal line every 10 s with MemAvailable and swap used (/proc/meminfo), PSI memory (/proc/pressure/memory: some
// and full avg10, full total) and GTT used (amdgpu's sysfs mem_info_gtt_used / mem_info_gtt_total), each file read once, no
// smaps walk; the journal is flushed after it. On by default; BC5_DIRECT_MEM_LINE=0 turns it off.
static bool mem_line_read(const char* path, char* buf, size_t cap) {
\tFILE* f = std::fopen(path, "r");
\tif (f == nullptr) return false;
\tconst size_t n = std::fread(buf, 1, cap - 1, f);
\tstd::fclose(f);
\tbuf[n] = 0;
\treturn n != 0;
}
static uint64_t mem_line_kib(const char* text, const char* key) { // "Key:   1234 kB" -> 1234
\tconst size_t kl = std::strlen(key);
\tfor (const char* l = text; l != nullptr && *l != 0;) {
\t\tif (std::strncmp(l, key, kl) == 0 && l[kl] == ':') return std::strtoull(l + kl + 1, nullptr, 10);
\t\tl = std::strchr(l, '\\n');
\t\tif (l != nullptr) l++;
\t}
\treturn 0;
}
static void mem_line_loop() {
\tstd::string gtt_dir;
\tfor (int c = 0; c < 8 && gtt_dir.empty(); c++) {
\t\tconst std::string d = "/sys/class/drm/card" + std::to_string(c) + "/device/";
\t\tif (access((d + "mem_info_gtt_used").c_str(), R_OK) == 0) gtt_dir = d;
\t}
\tfor (;;) {
\t\tstd::this_thread::sleep_for(std::chrono::seconds(10));
\t\tchar     buf[4096];
\t\tuint64_t avail = 0, swap_total = 0, swap_free = 0, full_total = 0, gtt_used = 0, gtt_total = 0;
\t\tdouble   some10 = -1.0, full10 = -1.0;
\t\tif (mem_line_read("/proc/meminfo", buf, sizeof(buf))) {
\t\t\tavail      = mem_line_kib(buf, "MemAvailable");
\t\t\tswap_total = mem_line_kib(buf, "SwapTotal");
\t\t\tswap_free  = mem_line_kib(buf, "SwapFree");
\t\t}
\t\tif (mem_line_read("/proc/pressure/memory", buf, sizeof(buf))) {
\t\t\tunsigned long long ft   = 0;
\t\t\tconst char*        full = std::strstr(buf, "full ");
\t\t\tif (std::sscanf(buf, "some avg10=%lf", &some10) != 1) some10 = -1.0;
\t\t\tif (full != nullptr && std::sscanf(full, "full avg10=%lf avg60=%*f avg300=%*f total=%llu", &full10, &ft) == 2) full_total = ft;
\t\t}
\t\tif (!gtt_dir.empty()) {
\t\t\tif (mem_line_read((gtt_dir + "mem_info_gtt_used").c_str(), buf, sizeof(buf))) gtt_used = std::strtoull(buf, nullptr, 10);
\t\t\tif (mem_line_read((gtt_dir + "mem_info_gtt_total").c_str(), buf, sizeof(buf))) gtt_total = std::strtoull(buf, nullptr, 10);
\t\t}
\t\tjournal("memory (exp 0401): t %.1f s: available %" PRIu64 " MiB, swap used %" PRIu64 " MiB, psi some %.2f full %.2f (avg10, %%), full total %" PRIu64 " ms, gtt %" PRIu64 " of %" PRIu64 " MiB\\n",
\t\t        timing_now(), avail >> 10u, (swap_total - std::min(swap_free, swap_total)) >> 10u, some10, full10, full_total / 1000u, gtt_used >> 20u, gtt_total >> 20u);
\t\tif (g_journal_min) (void)journal_min_file(true);
\t}
}
static void mem_line_start() {
\tstatic std::once_flag once;
\tstd::call_once(once, [] {
\t\tconst char* e  = std::getenv("BC5_DIRECT_MEM_LINE");
\t\tconst bool  on = e == nullptr || *e == 0 || std::strcmp(e, "0") != 0;
\t\tjournal("exp 0401: memory line %s\\n", on ? "every 10 s (MemAvailable, swap, PSI memory, GTT)" : "off");
\t\tif (on) std::thread(mem_line_loop).detach();
\t});
}

"""


# Series e3 as built (Codex's second review): a field that could not be read is "unknown", never 0. The parsing is pure,
# so its text also goes to memline_parse.inc for the CPU test; the draft (exp0401e3w) keeps MEMLINE_FUNCTIONS above.
MEMLINE_PARSE = b"""// Series e3 (Codex's second review of e3): the memory line's parsing, pure. A field whose file could not be read, or whose
// key or number is missing, is "unknown" in the line, never 0, so a missing file cannot look like memory at its floor or
// like no swap in use.
struct MemLine {
\tbool     avail_ok = false, swap_ok = false, some_ok = false, full_ok = false, gtt_ok = false;
\tuint64_t avail_kib = 0, swap_used_kib = 0, full_total_us = 0, gtt_used = 0, gtt_total = 0;
\tdouble   some10 = 0.0, full10 = 0.0;
};
static bool mem_line_key(const char* text, const char* key, uint64_t* v) { // "Key:   1234 kB" -> 1234
\tconst size_t kl = std::strlen(key);
\tfor (const char* l = text; l != nullptr && *l != 0;) {
\t\tif (std::strncmp(l, key, kl) == 0 && l[kl] == ':') {
\t\t\tchar* end = nullptr;
\t\t\t*v        = std::strtoull(l + kl + 1, &end, 10);
\t\t\treturn end != l + kl + 1;
\t\t}
\t\tl = std::strchr(l, '\\n');
\t\tif (l != nullptr) l++;
\t}
\treturn false;
}
static bool mem_line_number(const char* text, uint64_t* v) {
\tif (text == nullptr) return false;
\tchar* end = nullptr;
\t*v        = std::strtoull(text, &end, 10);
\treturn end != text;
}
// Each argument is a file's text, or nullptr when the file could not be read.
static MemLine mem_line_parse(const char* meminfo, const char* psi, const char* gtt_used, const char* gtt_total) {
\tMemLine m;
\tif (meminfo != nullptr) {
\t\tuint64_t swap_total = 0, swap_free = 0;
\t\tm.avail_ok = mem_line_key(meminfo, "MemAvailable", &m.avail_kib);
\t\tif (mem_line_key(meminfo, "SwapTotal", &swap_total) && mem_line_key(meminfo, "SwapFree", &swap_free)) {
\t\t\tm.swap_ok       = true;
\t\t\tm.swap_used_kib = swap_total - std::min(swap_free, swap_total);
\t\t}
\t}
\tif (psi != nullptr) {
\t\tm.some_ok                 = std::sscanf(psi, "some avg10=%lf", &m.some10) == 1;
\t\tconst char*        full    = std::strstr(psi, "full ");
\t\tunsigned long long total  = 0;
\t\tm.full_ok                 = full != nullptr && std::sscanf(full, "full avg10=%lf avg60=%*f avg300=%*f total=%llu", &m.full10, &total) == 2;
\t\tm.full_total_us           = total;
\t}
\tm.gtt_ok = mem_line_number(gtt_used, &m.gtt_used) && mem_line_number(gtt_total, &m.gtt_total);
\treturn m;
}
static void mem_line_format(const MemLine& m, double t, char* out, size_t cap) {
\tchar a[32] = "unknown", sw[32] = "unknown", so[32] = "unknown", fu[32] = "unknown", ft[32] = "unknown", gu[32] = "unknown", gt[32] = "unknown";
\tif (m.avail_ok) std::snprintf(a, sizeof(a), "%llu", static_cast<unsigned long long>(m.avail_kib >> 10u));
\tif (m.swap_ok) std::snprintf(sw, sizeof(sw), "%llu", static_cast<unsigned long long>(m.swap_used_kib >> 10u));
\tif (m.some_ok) std::snprintf(so, sizeof(so), "%.2f", m.some10);
\tif (m.full_ok) {
\t\tstd::snprintf(fu, sizeof(fu), "%.2f", m.full10);
\t\tstd::snprintf(ft, sizeof(ft), "%llu", static_cast<unsigned long long>(m.full_total_us / 1000u));
\t}
\tif (m.gtt_ok) {
\t\tstd::snprintf(gu, sizeof(gu), "%llu", static_cast<unsigned long long>(m.gtt_used >> 20u));
\t\tstd::snprintf(gt, sizeof(gt), "%llu", static_cast<unsigned long long>(m.gtt_total >> 20u));
\t}
\tstd::snprintf(out, cap, "memory (exp 0401): t %.1f s: available %s MiB, swap used %s MiB, psi some %s full %s (avg10, %%), full total %s ms, gtt %s of %s MiB\\n", t, a, sw, so, fu, ft, gu, gt);
}
"""
MEMLINE_FUNCTIONS2 = b"""// Experiment 0401 series e3 (the top session, 2026-11-03: the next guest crash should show whether memory was at its
// floor): a journal line every 10 s with MemAvailable and swap used (/proc/meminfo), PSI memory (/proc/pressure/memory: some
// and full avg10, full total) and GTT used (amdgpu's sysfs mem_info_gtt_used / mem_info_gtt_total), each file read once, no
// smaps walk; the journal is flushed after it. A value that cannot be read is "unknown" (mem_line_parse). On by default;
// BC5_DIRECT_MEM_LINE=0 turns it off.
""" + MEMLINE_PARSE + b"""static bool mem_line_read(const char* path, char* buf, size_t cap) {
\tFILE* f = std::fopen(path, "r");
\tif (f == nullptr) return false;
\tconst size_t n = std::fread(buf, 1, cap - 1, f);
\tstd::fclose(f);
\tbuf[n] = 0;
\treturn n != 0;
}
static void mem_line_loop() {
\tstd::string gtt_dir;
\tfor (int c = 0; c < 8 && gtt_dir.empty(); c++) {
\t\tconst std::string d = "/sys/class/drm/card" + std::to_string(c) + "/device/";
\t\tif (access((d + "mem_info_gtt_used").c_str(), R_OK) == 0) gtt_dir = d;
\t}
\tfor (;;) {
\t\tstd::this_thread::sleep_for(std::chrono::seconds(10));
\t\tchar       mi[8192], ps[512], gu[64], gt[64], line[512];
\t\tconst bool mi_ok = mem_line_read("/proc/meminfo", mi, sizeof(mi));
\t\tconst bool ps_ok = mem_line_read("/proc/pressure/memory", ps, sizeof(ps));
\t\tconst bool gu_ok = !gtt_dir.empty() && mem_line_read((gtt_dir + "mem_info_gtt_used").c_str(), gu, sizeof(gu));
\t\tconst bool gt_ok = !gtt_dir.empty() && mem_line_read((gtt_dir + "mem_info_gtt_total").c_str(), gt, sizeof(gt));
\t\tmem_line_format(mem_line_parse(mi_ok ? mi : nullptr, ps_ok ? ps : nullptr, gu_ok ? gu : nullptr, gt_ok ? gt : nullptr), timing_now(), line, sizeof(line));
\t\tjournal("%s", line);
\t\tif (g_journal_min) (void)journal_min_file(true);
\t}
}
static void mem_line_start() {
\tstatic std::once_flag once;
\tstd::call_once(once, [] {
\t\tconst char* e  = std::getenv("BC5_DIRECT_MEM_LINE");
\t\tconst bool  on = e == nullptr || *e == 0 || std::strcmp(e, "0") != 0;
\t\tjournal("exp 0401: memory line %s\\n", on ? "every 10 s (MemAvailable, swap, PSI memory, GTT)" : "off");
\t\tif (on) std::thread(mem_line_loop).detach();
\t});
}

"""


def memline_edits(v2=False):
    """Series e3: the 10-s memory line (BC5_DIRECT_MEM_LINE, on unless 0). v2: series e3 as built (unknown fields)."""
    a = b"static void submit(const uint32_t* ib, uint32_t num_dwords, const char* kind) {\n"
    return ((a, (MEMLINE_FUNCTIONS2 if v2 else MEMLINE_FUNCTIONS) + a + b"\tmem_line_start(); // experiment 0401 series e3\n", "replace"),)


def inherit_edits(v2=False, v3=False):
    """Series e2: BC5_DIRECT_ACB_INHERIT (exp 0403). Applies to a unit that has the acb CS prefix (series b and later).
    v2 (the e3 draft): the slots through inherit_plan, with their provenance. v3 (series e3): the queue's live state."""
    return (
        (b"static void                  acb_cs_track(const uint32_t* part, uint32_t n);\n", INHERIT_DECL, "after"),
        (b"// Experiment 0401 (BC5_DIRECT_ACB_CS_PREFIX=1, default off): the acb side of experiment 0195's CS prefix. On the console\n",
         INHERIT_FUNCTIONS3 if v3 else inherit_functions(v2), "before"),
        (b"\tstatic const bool        on = bc5::env_on(std::getenv(\"BC5_DIRECT_ACB_CS_PREFIX\"));\n",
         b"\tstatic const bool        on = bc5::env_on(std::getenv(\"BC5_DIRECT_ACB_CS_PREFIX\")) && acb_inherit_mode() == 0; // + exp 0403: ACB_INHERIT wins\n", "replace"),
        (b"\tconst std::vector<uint32_t> acb_cs = acb_cs_prefix(ib + from, to - from);\n",
         b"\tconst std::vector<uint32_t> acb_cs = acb_inherit_mode() != 0 ? acb_inherit_prefix(ib + from, to - from, from) : acb_cs_prefix(ib + from, to - from); // + exp 0403\n", "replace"),
        (b"\tacb_cs_track(ib + from, to - from);\n", b"\tacb_inherit_track(ib + from, to - from); // experiment 0403\n", "after"),
        (b"\t\tstd::vector<uint32_t> cs = acb_cs_prefix(ib, num_dwords);\n",
         b"\t\tstd::vector<uint32_t> cs = acb_inherit_mode() != 0 ? acb_inherit_prefix(ib, num_dwords, t_acb_from) : acb_cs_prefix(ib, num_dwords); // + exp 0403\n", "replace"),
        (b"\t\t\t\t\t\tsubmit_split(t + skip, tn - skip, \"acb\");\n\t\t\t\t\t\tacb_cs_track(t + skip, tn - skip); // experiment 0401\n",
         b"\t\t\t\t\t\tt_acb_from = skip; // experiment 0403: a rest starts there\n\t\t\t\t\t\tsubmit_split(t + skip, tn - skip, \"acb\");\n\t\t\t\t\t\tt_acb_from = 0;\n"
         b"\t\t\t\t\t\tacb_cs_track(t + skip, tn - skip); // experiment 0401\n\t\t\t\t\t\tacb_inherit_track(t + skip, tn - skip); // experiment 0403\n", "replace"),
        (b"\t\t\t\t\t\tt_ring = bc5::direct::kGfxRing;\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t}\n\t\t\tq += len;\n\t\t}\n\t\treturn;\n\t}\n\tsubmit_split(ib, num_dwords, kind);\n",
         b"\t\t\t\t\t\tt_ring = bc5::direct::kGfxRing;\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t} else if (type == 3) {\n\t\t\t\tacb_inherit_census(ib + q, len); // experiment 0403: a non-IB packet on the guest ring\n"
         b"\t\t\t}\n\t\t\tq += len;\n\t\t}\n\t\tacb_inherit_census_slice(); // experiment 0403\n\t\treturn;\n\t}\n\tsubmit_split(ib, num_dwords, kind);\n", "replace"),
        (b"\t\t\t// Experiment 0059: BC5_DIRECT_SKIP_PGM=<hex list> drops every dispatch (DISPATCH_DIRECT and both\n", INHERIT_DROP, "before"),
    )


def apply_edits(s, edits):
    for anchor, text, where in edits:
        assert s.count(anchor) == 1, ("anchor", anchor[:60], s.count(anchor))
        new = {"before": text + anchor, "after": anchor + text, "replace": text}[where]
        s = s.replace(anchor, new)
    return s


def edit(s, acb=False, restore=False, catcher=False, inherit=False, inherit2=False, memline=False, inherit3=False):
    assert s.count(ANCHOR) == 1, "prefix_of's head"
    assert s.count(CALL) == 1, "the tf_ring_prefix call"
    assert b"mesa_preamble_prefix" not in s, "the unit has the function already"
    assert acb or not restore, "the restore comes with the acb CS prefix"
    s = s.replace(ANCHOR, FUNCTION + ANCHOR)
    s = s.replace(CALL, CALL + b"\tmesa_preamble_prefix(p); // experiment 0401\n")
    if acb:
        assert b"acb_cs_prefix" not in s, "the unit has the acb CS prefix already"
        s = apply_edits(s, acb_edits(restore))
    if catcher:
        assert b"table_catcher_on" not in s, "the unit has the table catcher already"
        s = apply_edits(s, catcher_edits())
    if inherit or inherit2 or inherit3:
        assert acb, "ACB_INHERIT edits the acb CS prefix's code"
        assert int(inherit) + int(inherit2) + int(inherit3) == 1, "one ACB_INHERIT version"
        assert b"acb_inherit_mode" not in s, "the unit has ACB_INHERIT already"
        s = apply_edits(s, inherit_edits(inherit2, inherit3))
    if memline:
        assert b"mem_line_start" not in s, "the unit has the memory line already"
        s = apply_edits(s, memline_edits(inherit3))
    return s


def function_only():
    return FUNCTION


def main():
    with open(sys.argv[1], "rb") as f:
        s = f.read()
    flags = sys.argv[4:]
    assert flags in ([], ["--acb"], ["--acb-restore"], ["--acb-restore", "--catcher"], ["--acb-restore", "--catcher", "--inherit"],
                     ["--acb-restore", "--catcher", "--inherit2", "--memline"], ["--acb-restore", "--catcher", "--inherit3", "--memline"]), "usage"
    out = edit(s, acb=flags != [], restore="--acb-restore" in flags, catcher="--catcher" in flags, inherit="--inherit" in flags,
               inherit2="--inherit2" in flags, memline="--memline" in flags, inherit3="--inherit3" in flags)
    if "--inherit2" in flags or "--inherit3" in flags:   # the pure scan's own text, for the CPU test (inh0401.cpp)
        with open(os.path.join(os.path.dirname(os.path.abspath(sys.argv[3])), "inherit_scan.inc"), "wb") as f:
            f.write(INHERIT_SCAN3 if "--inherit3" in flags else INHERIT_SCAN)
    if "--inherit3" in flags:   # series e3: the memory line's parsing, for the same CPU test
        with open(os.path.join(os.path.dirname(os.path.abspath(sys.argv[3])), "memline_parse.inc"), "wb") as f:
            f.write(MEMLINE_PARSE)
    with open(sys.argv[2], "wb") as f:
        f.write(out)
    with open(sys.argv[3], "wb") as f:
        f.write(FUNCTION)
    print(hashlib.md5(out).hexdigest())


if __name__ == "__main__":
    main()
