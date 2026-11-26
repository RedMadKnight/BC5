#!/usr/bin/env python3
# BC5 experiment 0292: the dispatches whose compute user data point into the night lake writers' argument region.
# Patch 0001's BC5_DIRECT_FIND_VA=<lo>:<hi> (experiment 0059) journals, for every submitted buffer, each dispatch
# (op 0x15/0x16) one of whose COMPUTE_USER_DATA pairs (dword k | dword k+1 bits 15:0 << 32) points into [lo, hi), at
# most 4 times per program and offset: "find: <kind> #<submit> <n> dwords, dispatch op <op> at <q>, pgm 0x<cs>, user
# data <k>:<k+1> = 0x<address> (+0x<offset>)". This groups those lines by program and user-data pair and lists the
# addresses they point at, marked against the argument bases (exp 0287's raw/base0283.txt: 0x11934d3900,
# 0x11935d3900, 0x1193ad3900, offsets below 0x1000).
# usage: python3 -I fva0292.py <journal lines>
import collections, re, sys

BASES = [0x11934d3900, 0x11935d3900, 0x1193ad3900]
RE = re.compile(r"^find: (\S+) #(\d+) (\d+) dwords, dispatch op (\S+) at (\d+), pgm 0x([0-9a-f]+), user data (\d+):(\d+) = 0x([0-9a-f]+)")
by = collections.defaultdict(collections.Counter)
kinds = collections.Counter()
for l in open(sys.argv[1], errors="replace"):
    m = RE.match(l)
    if not m:
        continue
    a = int(m[9], 16)
    near = next(("base %x +0x%x" % (b, a - b) for b in BASES if b <= a < b + 0x1000), "outside the ranges")
    by[(m[6], "ud%s:%s" % (m[7], m[8]))][(a, near)] += 1
    kinds[(m[6], m[1], m[4])] += 1
print("# %s: %d FIND_VA lines" % (sys.argv[1], sum(kinds.values())))
for (pgm, kind, op), n in kinds.most_common():
    print("  pgm %s in %s buffers, op %s: %d lines" % (pgm, kind, op, n))
for (pgm, ud), c in sorted(by.items()):
    print("  pgm %s %s:" % (pgm, ud))
    for (a, near), n in sorted(c.items())[:12]:
        print("    %x (%s) x%d" % (a, near, n))
