#!/usr/bin/env python3
# BC5 experiment 0212: the resources the water's draws carry in their journalled user data, image AND buffer
# descriptors, from the draw journal (BC5_DIRECT_DRAW_JOURNAL with _PS=<shaders>: "draw journal buf N ... | ps <ps> ..."
# then "bake ud ps|gs buf N at P: <dwords>"). exp 0205's desc0205.py decoded the images only.
# gfx10 field layout: Mesa src/amd/registers/gfx10-rsrc.json @ 0866ae7 (the box's sparse checkout):
#   image  SQ_IMG_RSRC_WORD1 BASE_ADDRESS_HI [0,7], FORMAT [20,28]; WORD3 BASE_LEVEL [12,15], LAST_LEVEL [16,19],
#          SW_MODE [20,24], TYPE [28,31]; width/height as exp 0201 raw/X1-X2.txt
#   buffer SQ_BUF_RSRC_WORD1 BASE_ADDRESS_HI [0,15], STRIDE [16,29]; WORD2 = NUM_RECORDS;
#          WORD3 FORMAT [12,18], TYPE [30,31] (0 for a buffer)
# Each distinct descriptor is printed once with the number of draws that carry it, per shader, stage and slot.
# usage: python3 -I desc0212.py <direct.log> [pixel shader hex ...]   (default 11d01ff900 11d01d7100)
import collections, re, sys

pss = [p.lower().removeprefix("0x") for p in sys.argv[2:]] or ["11d01ff900", "11d01d7100"]
DRAW = re.compile(r"^draw journal buf (\d+) \(\d+ dwords\) at (\d+):.*\| ps (\S+) ")
UD = re.compile(r"^bake ud (ps|gs|es|vs) buf (\d+) at (\d+): (.*)$")
owner = {}
seen = collections.Counter()
for line in open(sys.argv[1], errors="replace"):
    m = DRAW.match(line)
    if m:
        if m[3].lower() in pss:
            owner[(m[1], m[2])] = m[3].lower()
        continue
    m = UD.match(line)
    if not m or (m[2], m[3]) not in owner:
        continue
    ps = owner[(m[2], m[3])]
    d = [int(x, 16) for x in re.findall(r"\b[0-9a-f]{8}\b", m[4])]
    k = 0
    while k + 3 < len(d):
        d0, d1, d2, d3 = d[k:k + 4]
        typ, fmt = d3 >> 28, (d1 >> 20) & 0x1ff
        if 8 <= typ <= 13 and fmt != 0 and k % 8 == 0:
            base = (d0 | (d1 & 0xff) << 32) << 8
            w = ((d2 & 0xfff) << 2 | d1 >> 30) + 1
            h = ((d2 >> 14) & 0x3fff) + 1
            seen[(ps, m[1], k // 4, "image", "0x%x %dx%d fmt %d levels %d sw %d" % (
                base, w, h, fmt, ((d3 >> 16) & 0xf) - ((d3 >> 12) & 0xf) + 1, (d3 >> 20) & 0x1f))] += 1
            k += 8
            continue
        base = d0 | (d1 & 0xffff) << 32
        stride, nrec, bfmt = (d1 >> 16) & 0x3fff, d2, (d3 >> 12) & 0x7f
        if d3 >> 30 == 0 and bfmt != 0 and 0 < stride <= 1024 and 0 < nrec < (1 << 26) and 0x1000000000 <= base < 0x9000000000:
            seen[(ps, m[1], k // 4, "buffer", "0x%x stride %d records %d (%d bytes) fmt %d" % (
                base, stride, nrec, stride * nrec, bfmt))] += 1
            k += 4
            continue
        k += 1
print("shader      stage slot kind    draws  descriptor")
for (ps, st, slot, kind, desc), n in sorted(seen.items()):
    print("%-11s %-5s %4d %-7s %6d  %s" % (ps, st, slot, kind, n, desc))
