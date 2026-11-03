#!/usr/bin/env python3
"""BC5 experiment 0401: main 029e0d6b's src/libs/bc5LleAgc.cpp with two default-off switches, mesa_preamble_prefix(), called
from prefix_of() right after tf_ring_prefix(). With --acb (series b, 2026-11-03) also the acb CS prefix, a third default-off
switch; with --acb-restore (series c) also exp 0381's ACB_STATE_RESTORE, a fourth. Each anchor must occur exactly once.
Prints the output's md5.
usage: mkunit0401.py <unit in> <unit out> <function out> [--acb | --acb-restore]"""
import hashlib
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


def inherit_edits():
    """Series e2: BC5_DIRECT_ACB_INHERIT (exp 0403). Applies to a unit that has the acb CS prefix (series b and later)."""
    return (
        (b"static void                  acb_cs_track(const uint32_t* part, uint32_t n);\n", INHERIT_DECL, "after"),
        (b"// Experiment 0401 (BC5_DIRECT_ACB_CS_PREFIX=1, default off): the acb side of experiment 0195's CS prefix. On the console\n", INHERIT_FUNCTIONS, "before"),
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


def edit(s, acb=False, restore=False, catcher=False, inherit=False):
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
    if inherit:
        assert acb, "ACB_INHERIT edits the acb CS prefix's code"
        assert b"acb_inherit_mode" not in s, "the unit has ACB_INHERIT already"
        s = apply_edits(s, inherit_edits())
    return s


def function_only():
    return FUNCTION


def main():
    with open(sys.argv[1], "rb") as f:
        s = f.read()
    flags = sys.argv[4:]
    assert flags in ([], ["--acb"], ["--acb-restore"], ["--acb-restore", "--catcher"], ["--acb-restore", "--catcher", "--inherit"]), "usage"
    out = edit(s, acb=flags != [], restore="--acb-restore" in flags, catcher="--catcher" in flags, inherit="--inherit" in flags)
    with open(sys.argv[2], "wb") as f:
        f.write(out)
    with open(sys.argv[3], "wb") as f:
        f.write(FUNCTION)
    print(hashlib.md5(out).hexdigest())


if __name__ == "__main__":
    main()
