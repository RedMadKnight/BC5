#!/usr/bin/env python3
"""BC5 experiment 0401: main 029e0d6b's src/libs/bc5LleAgc.cpp with two default-off switches, mesa_preamble_prefix(), called
from prefix_of() right after tf_ring_prefix(). Each anchor must occur exactly once. Prints the output's md5.
usage: mkunit0401.py <unit in> <unit out> <function out>"""
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


def edit(s):
    assert s.count(ANCHOR) == 1, "prefix_of's head"
    assert s.count(CALL) == 1, "the tf_ring_prefix call"
    assert b"mesa_preamble_prefix" not in s, "the unit has the function already"
    s = s.replace(ANCHOR, FUNCTION + ANCHOR)
    return s.replace(CALL, CALL + b"\tmesa_preamble_prefix(p); // experiment 0401\n")


def function_only():
    return FUNCTION


def main():
    with open(sys.argv[1], "rb") as f:
        s = f.read()
    out = edit(s)
    with open(sys.argv[2], "wb") as f:
        f.write(out)
    with open(sys.argv[3], "wb") as f:
        f.write(FUNCTION)
    print(hashlib.md5(out).hexdigest())


if __name__ == "__main__":
    main()
