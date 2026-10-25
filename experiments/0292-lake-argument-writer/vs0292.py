#!/usr/bin/env python3
# BC5 experiment 0292: which dispatch writes the night lake depth writers' indirect arguments (F350, F352)? The
# arguments sit at three SET_BASE index-1 bases, 0x11934d3900, 0x11935d3900 and 0x1193ad3900, offsets below 0x1000
# (exp 0287, raw/base0283.txt). This reads draw-journal lines, a grep of "draw journal find: dispatch", "find ud cs" and
# "find table" (patch 0001, experiment 0092/0156: a dispatch whose user data or a table behind a user-data pair holds a
# _FIND value is journalled with its 16 user-data dwords and that table's 64 dwords), and lists every buffer descriptor
# among them whose range covers one of the argument ranges: in the user data (inline V#s) and in the tables, at every
# dword offset. A V# (Mesa gfx10-rsrc.json @ 0866ae7, as exp 0212's desc0212.py cites): word 0 base [31:0], word 1 bits
# 15:0 base [47:32] and bits 29:16 the stride, word 2 the number of records, word 3 bits 31:30 the type (0 for a buffer);
# its size is the records in bytes when the stride is 0, else records x stride. Prints per dispatch kind (compute
# shader address) the covering descriptors with their base, size and where they sit; the counts of dispatches seen.
# usage: python3 -I vs0292.py <journal lines> [base hex ...]
import collections, re, sys

path = sys.argv[1]
BASES = [int(b, 16) for b in sys.argv[2:]] or [0x11934d3900, 0x11935d3900, 0x1193ad3900]
RANGES = [(b, b + 0x1000) for b in BASES]
RE_D = re.compile(r"^draw journal find: dispatch cs ud(\d+) \(([0-9a-f]+)\) (\S+) ([0-9a-f]+) \| rt0 \S+ \| ps \S+ cs ([0-9a-f]+) \| pkt(.*)$")
RE_U = re.compile(r"^find ud cs ([0-9a-f]+) t ([\d.]+):((?: [0-9a-f]{8})+)")
RE_T = re.compile(r"^find table ([0-9a-f]+):((?: [0-9a-f]{8})+)")


def covers(w):
    if len(w) < 4 or (w[3] >> 30) & 3 != 0:
        return None
    base = w[0] | ((w[1] & 0xffff) << 32)
    stride = (w[1] >> 16) & 0x3fff
    size = w[2] if stride == 0 else w[2] * stride
    if size == 0 or size > 1 << 32:
        return None
    for lo, hi in RANGES:
        if base < hi and lo < base + size:
            return base, size, stride
    return None


cur, seen, hits = None, collections.Counter(), collections.defaultdict(collections.Counter)
for l in open(path, errors="replace"):
    m = RE_D.match(l)
    if m:
        cur = m[5]
        seen[(cur, " ".join(m[6].split()[:4]))] += 1
        continue
    m = RE_U.match(l)
    if m and cur:
        u = [int(x, 16) for x in m[3].split()]
        for q in range(len(u) - 3):
            c = covers(u[q:q + 4])
            if c:
                hits[cur][("user data %d" % q, c)] += 1
        continue
    m = RE_T.match(l)
    if m and cur:
        t = [int(x, 16) for x in m[2].split()]
        for q in range(len(t) - 3):
            c = covers(t[q:q + 4])
            if c:
                hits[cur][("table %s dword %d" % (m[1], q), c)] += 1
print("# %s: dispatch hits by compute shader and packet (first 4 dwords)" % path)
for (cs, pkt), n in seen.most_common(20):
    print("  cs %s pkt %s: %d" % (cs, pkt, n))
print("# buffer descriptors covering the argument ranges %s" % " ".join("%x..%x" % r for r in RANGES))
if not hits:
    print("  none")
for cs, c in sorted(hits.items()):
    for (where, (base, size, stride)), n in c.most_common(20):
        print("  cs %s: %s: base %x size 0x%x stride %d (x%d)" % (cs, where, base, size, stride, n))
