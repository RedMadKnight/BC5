#!/usr/bin/env python3
# BC5 experiment 0205: the image descriptors a pixel shader's draws carry in their user data, from the draw journal
# (BC5_DIRECT_DRAW_JOURNAL with _PS=<shader>: a "draw journal buf N ... | ps <shader> ..." line, then "bake ud ps|gs buf
# N at P: <dwords>"). Each distinct descriptor is printed once with its count, decoded as a gfx10 image resource
# (Mesa src/amd/registers/gfx10-rsrc.json @ 0866ae7: WORD1 BASE_ADDRESS_HI [0,7], FORMAT [20,28], WIDTH_LO [30,31];
# WORD2 WIDTH_HI [0,11]... as exp 0201 raw/X1-X2.txt; WORD3 BASE_LEVEL [12,15], LAST_LEVEL [16,19], SW_MODE [20,24],
# TYPE [28,31]), with the res0205.py arguments for it.
# usage: python3 -I desc0205.py <direct.log> [pixel shader hex, default 11d01ff900]
import collections, re, sys

FMT = {13: ("16_FLOAT", 2, 1), 71: ("16_16_16_16_FLOAT", 8, 1), 175: ("BC4_UNORM", 8, 4)}
ps = (sys.argv[2] if len(sys.argv) > 2 else "11d01ff900").lower().removeprefix("0x")
DRAW = re.compile(r"^draw journal buf (\d+) \(\d+ dwords\) at (\d+):.*\| ps (\S+) ")
UD = re.compile(r"^bake ud (ps|gs|es|vs) buf (\d+) at (\d+): (.*)$")
mine = set()
seen = collections.Counter()
for line in open(sys.argv[1], errors="replace"):
    m = DRAW.match(line)
    if m:
        if m[3].lower() == ps:
            mine.add((m[1], m[2]))
        continue
    m = UD.match(line)
    if not m or (m[2], m[3]) not in mine:
        continue
    d = [int(x, 16) for x in re.findall(r"\b[0-9a-f]{8}\b", m[4])]
    for k in range(0, len(d) - 3, 4):
        d0, d1, d2, d3 = d[k:k + 4]
        typ, fmt = d3 >> 28, (d1 >> 20) & 0x1ff
        if not 8 <= typ <= 13 or fmt == 0:
            continue
        base = (d0 | (d1 & 0xff) << 32) << 8
        w = ((d2 & 0xfff) << 2 | d1 >> 30) + 1
        h = ((d2 >> 14) & 0x3fff) + 1
        lv = ((d3 >> 16) & 0xf) - ((d3 >> 12) & 0xf) + 1
        seen[(m[1], k // 4, base, w, h, fmt, lv, (d3 >> 20) & 0x1f, typ)] += 1
print("stage slot base           size        format                 levels sw type  draws | res0205.py args")
for (st, slot, base, w, h, fmt, lv, sw, typ), n in sorted(seen.items()):
    name, bpe, e = FMT.get(fmt, ("fmt %d" % fmt, 0, 1))
    args = "%x %d %d %d %d %d %d,%d" % (base, w, h, lv, sw, bpe, e, e) if bpe else "-"
    print("%-5s %4d 0x%-12x %4dx%-5d %-22s %6d %2d %4d %6d | %s" % (st, slot, base, w, h, name, lv, sw, typ, n, args))
