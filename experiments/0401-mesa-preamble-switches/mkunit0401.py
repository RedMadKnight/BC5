#!/usr/bin/env python3
"""BC5 experiment 0401: main 029e0d6b's src/libs/bc5LleAgc.cpp with two default-off switches, mesa_preamble_prefix(), called
from prefix_of() right after tf_ring_prefix(). With --acb (series b, 2026-11-03) also the acb CS prefix, a third default-off
switch. Each anchor must occur exactly once. Prints the output's md5.
usage: mkunit0401.py <unit in> <unit out> <function out> [--acb]"""
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
ACB_SPLIT = b"""\tif (!full_used && std::strcmp(kind, "acb") == 0) { // experiment 0401: the acb's own queue state, as the CS prefix above for a dcb
\t\tstd::vector<uint32_t> cs = acb_cs_prefix(ib, num_dwords);
\t\tif (!cs.empty()) {
\t\t\tfull_prefix.swap(cs);
\t\t\tfull_used = cs_used = true;
\t\t}
\t}
"""
ACB_EDITS = (
    (b"static void submit_segment(const uint32_t* ib, uint32_t num_dwords, uint32_t from, uint32_t to) {\n", ACB_DECL, "before"),
    (ACB_SEGMENT_OLD, ACB_SEGMENT_NEW, "replace"),
    (b"static bool ib_has_draw(const uint32_t* ib, uint32_t num_dwords) {\n", ACB_FUNCTIONS, "before"),
    (b"\t// Experiment 0118: a piece goes to the GPU as one job with its full-state prefix in front. As two\n", ACB_SPLIT, "before"),
    (b"\t\t\t\t\t\tsubmit_split(t + skip, tn - skip, \"acb\");\n", b"\t\t\t\t\t\tacb_cs_track(t + skip, tn - skip); // experiment 0401\n", "after"),
)


def edit(s, acb=False):
    assert s.count(ANCHOR) == 1, "prefix_of's head"
    assert s.count(CALL) == 1, "the tf_ring_prefix call"
    assert b"mesa_preamble_prefix" not in s, "the unit has the function already"
    s = s.replace(ANCHOR, FUNCTION + ANCHOR)
    s = s.replace(CALL, CALL + b"\tmesa_preamble_prefix(p); // experiment 0401\n")
    if acb:
        assert b"acb_cs_prefix" not in s, "the unit has the acb CS prefix already"
        for anchor, text, where in ACB_EDITS:
            assert s.count(anchor) == 1, ("anchor", anchor[:60], s.count(anchor))
            new = {"before": text + anchor, "after": anchor + text, "replace": text}[where]
            s = s.replace(anchor, new)
    return s


def function_only():
    return FUNCTION


def main():
    with open(sys.argv[1], "rb") as f:
        s = f.read()
    assert sys.argv[4:] in ([], ["--acb"]), "usage"
    out = edit(s, acb=sys.argv[4:] == ["--acb"])
    with open(sys.argv[2], "wb") as f:
        f.write(out)
    with open(sys.argv[3], "wb") as f:
        f.write(FUNCTION)
    print(hashlib.md5(out).hexdigest())


if __name__ == "__main__":
    main()
