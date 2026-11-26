#!/usr/bin/env python3
# BC5 exp 0381: read a BC5_DIRECT_DISPATCH_JOURNAL=1 direct.log for the F443/F677 job. Prints, per program
# 0x909977100 (the adjacency build), the host tracker's user data 0-5 as journaled at submit, a histogram of ud0
# over all dispatches, and for every run of 0x909977100 dispatches the dispatch line just before the run (the
# tracker's ud0 carried into that dcb). Register values and counts only.
# usage: python3 dj0381.py direct.log
import collections
import re
import sys

PGM = 0x909977100
pat = re.compile(r"^\s+(\S+) dispatch op (\w+) at (\d+): pgm 0x([0-9a-f]+) ud0-3 (\w+) (\w+) (\w+) (\w+) ud4-7 (\w+) (\w+)")
ud0_all = collections.Counter()
hits = collections.Counter()
runs = []
prev = None
in_run = False
n = 0
with open(sys.argv[1], errors="replace") as f:
    for ln, line in enumerate(f, 1):
        m = pat.match(line)
        if not m:
            continue
        n += 1
        kind, op, at, pgm = m.group(1), m.group(2), int(m.group(3)), int(m.group(4), 16)
        ud = [int(m.group(k), 16) for k in range(5, 11)]
        ud0_all[ud[0]] += 1
        if pgm == PGM:
            hits[tuple(ud[:6])] += 1
            if not in_run:
                runs.append((ln, at, kind, ud, prev))
            in_run = True
        else:
            in_run = False
        prev = (ln, kind, at, pgm, ud)
print("dispatch lines %d; 0x%x dispatches %d in %d runs" % (n, PGM, sum(hits.values()), len(runs)))
print("ud0 histogram (top 12):", ", ".join("0x%x:%d" % kv for kv in ud0_all.most_common(12)))
print("0x%x ud0-5 (top 10):" % PGM)
for k, v in hits.most_common(10):
    print("  %6d  %s" % (v, " ".join("%08x" % x for x in k)))
print("runs (first 0x%x dispatch of each, with the dispatch before it):" % PGM)
for ln, at, kind, ud, p in runs[:40]:
    before = "none" if p is None else "line %d %s at %d pgm 0x%x ud0-2 %08x %08x %08x" % (p[0], p[1], p[2], p[3], p[4][0], p[4][1], p[4][2])
    print("  line %d %s at %d ud0-5 %s | before: %s" % (ln, kind, at, " ".join("%08x" % x for x in ud), before))
