#!/usr/bin/env python3
# BC5 experiment 0212: the water's "per-cell buffer" (0x11e0007aa0, stride 32) read as what its records are: gfx10 image
# descriptors (T#, 8 dwords). Field layout: Mesa src/amd/registers/gfx10-rsrc.json @ 0866ae7:
#   WORD1 BASE_ADDRESS_HI [0,7], MIN_LOD [8,19], FORMAT [20,28], WIDTH_LO [30,31]
#   WORD3 BASE_LEVEL [12,15], LAST_LEVEL [16,19], SW_MODE [20,24], TYPE [28,31]
#   (width/height as exp 0201 raw/X1-X2.txt; MIN_LOD read as unsigned 4.8 fixed point, TODO(verify) the format)
# (1) summary of one dump: records that decode as images, formats, MIN_LOD histogram;
# (2) two or more dumps compared by texture base address (tables of different runs are not aligned by index):
#     per base present in all dumps, MIN_LOD (and LAST_LEVEL) per dump; prints the bases whose values differ.
# usage: python3 -I tab0212.py <label>=<dump> [<label>=<dump> ...]
import collections, struct, sys


def decode(data):
    out = {}
    for i in range(len(data) // 32):
        d = struct.unpack_from("<8I", data, i * 32)
        typ, fmt = d[3] >> 28, (d[1] >> 20) & 0x1ff
        if not (8 <= typ <= 13) or fmt == 0:
            continue
        base = (d[0] | (d[1] & 0xff) << 32) << 8
        w = ((d[2] & 0xfff) << 2 | d[1] >> 30) + 1
        h = ((d[2] >> 14) & 0x3fff) + 1
        minlod = ((d[1] >> 8) & 0xfff) / 256.0
        lo, hi = (d[3] >> 12) & 0xf, (d[3] >> 16) & 0xf
        out.setdefault(base, []).append((i, typ, fmt, w, h, minlod, lo, hi))
    return out


tabs = []
for a in sys.argv[1:]:
    label, path = a.split("=", 1)
    data = open(path, "rb").read()
    t = decode(data)
    tabs.append((label, t))
    recs = [r for v in t.values() for r in v]
    print("%s: %d records, %d decode as images, %d distinct bases; types %s; MIN_LOD %s" % (
        label, len(data) // 32, len(recs), len(t),
        dict(collections.Counter(r[1] for r in recs)),
        dict(sorted(collections.Counter(r[5] for r in recs).items()))))
if len(tabs) > 1:
    common = set(tabs[0][1])
    for _, t in tabs[1:]:
        common &= set(t)
    print("bases in all %d dumps: %d" % (len(tabs), len(common)))
    diff = []
    for b in sorted(common):
        vals = [tuple(sorted({(r[5], r[7]) for r in t[b]})) for _, t in tabs]
        if len(set(vals)) > 1:
            diff.append((b, vals, tabs[0][1][b][0]))
    print("bases whose (MIN_LOD, LAST_LEVEL) differ: %d" % len(diff))
    for b, vals, r in diff[:60]:
        print("  0x%x %dx%d fmt %d type %d: %s" % (b, r[3], r[4], r[2], r[1],
              "  ".join("%s=%s" % (tabs[k][0], ",".join("%.2f/%d" % v for v in vals[k])) for k in range(len(tabs)))))
    only = [(lab, len(set(t) - common)) for lab, t in tabs]
    print("bases not in every dump: %s" % only)
