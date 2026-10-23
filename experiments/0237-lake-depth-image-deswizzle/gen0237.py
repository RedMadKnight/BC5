#!/usr/bin/env python3
# BC5 experiment 0237: extract the gfx10 swizzle patterns of ADDR_SW_64KB_R_X (1 sample, 2-byte elements) for every
# pipe count from Mesa's addrlib (src/amd/addrlib/src/gfx10/gfx10SwizzlePattern.h @ ab2374a, MIT, (C) AMD) into a
# small JSON table for deswz0237.py. Selection as Gfx10Lib::GetSwizzlePatternInfo (gfx10addrlib.cpp:4392-4670): an
# XOR mode on a part without RB+ (gfx10.1, Navi1x) uses GFX10_SW_64K_R_X_1xaa_PATINFO[m_colorBaseIndex + elemLog2]
# with m_colorBaseIndex = pipesLog2 * MaxNumOfBpp (5) (gfx10addrlib.cpp:939-941); the 20-bit pattern is NIBBLE01 (bits
# 0-7), NIBBLE2 (8-11), NIBBLE3 (12-15), NIBBLE4 (16-19) of that entry (gfx10addrlib.h:397-416). Each pattern entry is
# a mask of coordinate bits XORed into that address bit: X/Y/Z/S bit k at bit 16*c + k (core/addrlib.h:244-280).
# usage: python3 -I gen0237.py <gfx10SwizzlePattern.h> > swz0237.json
import json, re, sys

src = open(sys.argv[1]).read()
names = {}
for c, letter, n in ((0, "X", 12), (1, "Y", 12), (2, "Z", 9), (3, "S", 3)):
    for k in range(n):
        names["%s%d" % (letter, k)] = 1 << (16 * c + k)


def array(name):
    m = re.search(r"const\s+\w+\s+%s\[\](?:\[\d+\])?\s*=\s*\{(.*?)\n\};" % re.escape(name), src, re.S)
    rows = re.findall(r"\{([^{}]*)\}", m[1])
    out = []
    for r in rows:
        items = [s.strip() for s in r.split(",") if s.strip()]
        out.append([eval(s, {"__builtins__": {}}, names) if not s.isdigit() else int(s) for s in items])
    return out


pat = array("GFX10_SW_64K_R_X_1xaa_PATINFO")
nib = {k: array("GFX10_SW_PATTERN_NIBBLE" + k) for k in ("01", "2", "3", "4")}
ELEM_LOG2 = 1
table = {"source": "Mesa src/amd/addrlib/src/gfx10/gfx10SwizzlePattern.h @ ab2374a (MIT, AMD)",
         "mode": "ADDR_SW_64KB_R_X 1xaa", "elemLog2": ELEM_LOG2, "patterns": {}}
for p in range(7):
    _, n01, n2, n3, n4 = pat[p * 5 + ELEM_LOG2]
    full = nib["01"][n01] + nib["2"][n2] + nib["3"][n3] + nib["4"][n4]
    table["patterns"][str(p)] = [{"x": v & 0xffff, "y": (v >> 16) & 0xffff, "z": (v >> 32) & 0xffff} for v in full[:16]]
json.dump(table, sys.stdout, indent=1)
