#!/usr/bin/env python3
# BC5 experiment 0289 (exp 0248's gen0248.py, generalised to any PATINFO table and index): extract one gfx10 swizzle
# pattern from Mesa's addrlib (src/amd/addrlib/src/gfx10/gfx10SwizzlePattern.h, MIT, (C) AMD) into a small JSON table
# for de-swizzling. Here: the night lake writers' 32_FLOAT image pyramid, whose image descriptor has SW_MODE 5,
# ADDR_SW_4KB_S (exp 0274, raw/W274ab.find-detail.txt; SW_MODE bits 20-24 of word 3 per Mesa's gfx10-rsrc.json @
# 0866ae7). Which table and index Gfx10Lib::GetSwizzlePatternInfo picks for a mode is read from gfx10addrlib.cpp and
# cited in the README (for a non-XOR mode such as ADDR_SW_4KB_S: TODO(verify) the index is elemLog2 alone, without
# exp 0237's m_colorBaseIndex term, which applies to the XOR modes). The pattern is NIBBLE01 (address bits 0-7),
# NIBBLE2 (8-11), NIBBLE3 (12-15), NIBBLE4 (16-19) of the table entry (gfx10addrlib.h:397-416, as exp 0237); each
# entry is a mask of coordinate bits XORed into that address bit: X/Y/Z/S bit k at bit 16*c + k (core/addrlib.h:244-280).
# usage: python3 -I gen0289.py <gfx10SwizzlePattern.h> <PATINFO table, e.g. GFX10_SW_4K_S_PATINFO> <index> <elemLog2>
#        <address bits: 12 for a 4-KiB block> > out.json
import json, re, sys

src = open(sys.argv[1]).read()
table_name, index, elem_log2, nbits = sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
names = {}
for c, letter, n in ((0, "X", 12), (1, "Y", 12), (2, "Z", 9), (3, "S", 3)):
    for k in range(n):
        names["%s%d" % (letter, k)] = 1 << (16 * c + k)


def value(s):
    # an entry is a decimal number or coordinate bit names joined by "^" (X0^Y1 ...): parsed, never evaluated, since
    # the header is a downloaded file (exps 0237/0248 used eval)
    if s.isdigit():
        return int(s)
    v = 0
    for t in s.replace(" ", "").split("^"):
        if t not in names:
            sys.exit("unexpected pattern term %r" % t)
        v ^= names[t]
    return v


def array(name):
    m = re.search(r"const\s+\w+\s+%s\[\](?:\[\d+\])?\s*=\s*\{(.*?)\n\};" % re.escape(name), src, re.S)
    if m is None:
        sys.exit("table %s not found" % name)
    rows = re.findall(r"\{([^{}]*)\}", m[1])
    out = []
    for r in rows:
        items = [s.strip() for s in r.split(",") if s.strip()]
        out.append([value(s) for s in items])
    return out


pat = array(table_name)
nib = {k: array("GFX10_SW_PATTERN_NIBBLE" + k) for k in ("01", "2", "3", "4")}
_, n01, n2, n3, n4 = pat[index]
full = nib["01"][n01] + nib["2"][n2] + nib["3"][n3] + nib["4"][n4]
entry = [{"x": v & 0xffff, "y": (v >> 16) & 0xffff, "z": (v >> 32) & 0xffff} for v in full[:nbits]]
json.dump({"source": "Mesa src/amd/addrlib/src/gfx10/gfx10SwizzlePattern.h (MIT, AMD); see README for the commit",
           "mode": table_name, "index": index, "elemLog2": elem_log2, "address_bits": nbits,
           "nibbles": [n01, n2, n3, n4], "pattern": entry}, sys.stdout, indent=1)
