#!/usr/bin/env python3
# BC5 experiment 0292: every buffer descriptor (V#, 4-dword aligned, type 0, base in the guest range) among the dispatch
# hits' user data and dumped tables in a grep of draw-journal find lines (as vs0292.py reads them), by compute shader,
# with base, size and stride (V# layout as vs0292.py cites). To see which buffers the candidate passes bind at all.
# usage: python3 -I vbuf0292.py <journal lines>
import collections, re, sys

cur, bufs = None, collections.defaultdict(collections.Counter)
for l in open(sys.argv[1], errors="replace"):
    m = re.match(r"^draw journal find: dispatch cs .*cs ([0-9a-f]+) \|", l)
    if m:
        cur = m[1]
        continue
    m = re.match(r"^find (?:table [0-9a-f]+|ud cs [0-9a-f]+ t [\d.]+):((?: [0-9a-f]{8})+)", l)
    if m and cur:
        w = [int(x, 16) for x in m[1].split()]
        for q in range(0, len(w) - 3, 4):
            if (w[q + 3] >> 30) & 3 == 0 and w[q + 2] and (w[q] | w[q + 1]):
                base = w[q] | ((w[q + 1] & 0xffff) << 32)
                stride = (w[q + 1] >> 16) & 0x3fff
                size = w[q + 2] if stride == 0 else w[q + 2] * stride
                if 0x1000000000 <= base < 0x1400000000 and size < 1 << 30:
                    bufs[cur][(base, size, stride)] += 1
print("# buffer descriptors in the dispatch hits' user data and tables, by compute shader")
for cs, c in bufs.items():
    print("cs %s: %d distinct" % (cs, len(c)))
    for (b, s, st), n in sorted(c.items())[:40]:
        print("  base %x size 0x%x stride %d (x%d)" % (b, s, st, n))
