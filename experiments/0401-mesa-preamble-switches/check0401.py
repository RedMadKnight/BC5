#!/usr/bin/env python3
"""BC5 experiment 0401: every setting of the two switches against the packets and journal lines they must give, with the
real function compiled by unit0401.cpp. Exit 0 only after all cases ran and the end marker was seen.
usage: check0401.py <test command...>"""
import os
import subprocess
import sys

COHER, REQ = "BC5_DIRECT_CP_COHER_START_DELAY", "BC5_DIRECT_SPI_REQ_CTRL_PS"
C = "c0017900 0000007b 00000020 "
R = "c0017600 00000030 00000007 "
J_C_ON = "exp 0401: CP_COHER_START_DELAY 0x20 in every prefix (SET_UCONFIG_REG 0x7b)"
J_C_OFF = "exp 0401: CP_COHER_START_DELAY off"
J_R_ON = "exp 0401: SPI_SHADER_REQ_CTRL_PS 0x7 in every prefix (SET_SH_REG 0x30)"
J_R_OFF = "exp 0401: SPI_SHADER_REQ_CTRL_PS off"
CASES = (
    ({}, "", J_C_OFF, J_R_OFF),
    ({COHER: ""}, "", J_C_OFF, J_R_OFF),
    ({COHER: "0", REQ: "0"}, "", J_C_OFF, J_R_OFF),
    ({COHER: "1"}, C, J_C_ON, J_R_OFF),
    ({REQ: "1"}, R, J_C_OFF, J_R_ON),
    ({COHER: "1", REQ: "0"}, C, J_C_ON, J_R_OFF),
    ({COHER: "1", REQ: "1"}, C + R, J_C_ON, J_R_ON),
)


def main():
    done = 0
    for env, packets, j1, j2 in CASES:
        e = {k: v for k, v in os.environ.items() if k not in (COHER, REQ)}
        e.update(env)
        r = subprocess.run(sys.argv[1:], env=e, capture_output=True, text=True, timeout=20)
        assert r.returncode == 0, (env, r.returncode)
        want = [j1, j2, "000000aa " + packets * 2, "end"]
        got = r.stdout.split("\n")[:-1]
        assert got == want, (env, got, want)
        done += 1
    assert done == 7 == len(CASES)
    print(f"check0401: {done} of {len(CASES)} settings give the packets and lines they must; end")


if __name__ == "__main__":
    main()
