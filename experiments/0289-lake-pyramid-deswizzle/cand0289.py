#!/usr/bin/env python3
# BC5 experiment 0289: candidate in-block patterns for the night lake writers' 32_FLOAT pyramid (ADDR_SW_4KB_S at 4-byte
# elements, exp 0274), written while Mesa's addrlib tables were not at hand. Since then the tables give the pattern
# (gen0289.py -> swz4k-addrlib.json: X0 X1 Y0 Y1 Y2 X2 Y3 X3 Y4 X4, not dss below); the guesses stay as a cross-check of
# fb0289.py's smoothness score. Each candidate maps address bits 0-11 of a 4-KiB block (bits 0-1: the byte in
# the element) to element coordinate bits, in exp 0248's JSON form (one mask per address bit), 32 x 32 elements:
#   dss:      X0 X1 Y0 Y1 X2 Y2 X3 Y3 X4 Y4 (the guess before addrlib was at hand; wrong above bit 5)
#   dss_y:    Y0 Y1 X0 X1 Y2 X2 Y3 X3 Y4 X4
#   morton_x: X0 Y0 X1 Y1 X2 Y2 X3 Y3 X4 Y4
#   morton_y: Y0 X0 Y1 X1 Y2 X2 Y3 X3 Y4 X4
#   rows:     X0 X1 X2 X3 X4 Y0 Y1 Y2 Y3 Y4 (row-major in the block)
# fb0289.py decodes the pyramid with each and keeps the one whose images are smoothest; a wrong pattern scrambles every
# 32 x 32 block, so the right one stands out on real data (TODO(verify) against addrlib when its tables are at hand).
# usage: python3 -I cand0289.py <out dir>   (writes swz4k-<name>.json)
import json, os, sys

CANDS = {"dss": "X0 X1 Y0 Y1 X2 Y2 X3 Y3 X4 Y4", "dss_y": "Y0 Y1 X0 X1 Y2 X2 Y3 X3 Y4 X4",
         "morton_x": "X0 Y0 X1 Y1 X2 Y2 X3 Y3 X4 Y4", "morton_y": "Y0 X0 Y1 X1 Y2 X2 Y3 X3 Y4 X4",
         "rows": "X0 X1 X2 X3 X4 Y0 Y1 Y2 Y3 Y4"}
out = sys.argv[1]
for name, bits in CANDS.items():
    pat = [{"x": 0, "y": 0, "z": 0}, {"x": 0, "y": 0, "z": 0}]
    for b in bits.split():
        pat.append({"x": 1 << int(b[1]) if b[0] == "X" else 0, "y": 1 << int(b[1]) if b[0] == "Y" else 0, "z": 0})
    json.dump({"source": "candidate %s (exp 0289, cand0289.py; TODO(verify) against Mesa addrlib)" % name, "mode": "ADDR_SW_4KB_S",
               "elemLog2": 2, "address_bits": 12, "pattern": pat}, open(os.path.join(out, "swz4k-%s.json" % name), "w"), indent=1)
    print(name, bits)
