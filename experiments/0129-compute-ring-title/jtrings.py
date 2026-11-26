#!/usr/bin/env python3
"""ADR 0009: GPU busy time per ring and their overlap, from "jt <start> <end> <kind> <dwords> [ring]"
lines (BC5_DIRECT_JOB_TS=<t0>:<t1>, 100 MHz clock; no ring column = GFX ring, -1).
Usage: jtrings.py direct.log"""
import collections
import sys


def union(iv):
    iv = sorted(iv)
    total = 0
    cs, ce = iv[0]
    for s, e in iv[1:]:
        if s > ce:
            total += ce - cs
            cs, ce = s, e
        elif e > ce:
            ce = e
    return total + ce - cs


rings = collections.defaultdict(list)
kinds = collections.Counter()
for line in open(sys.argv[1], errors="replace"):
    if not line.startswith("jt "):
        continue
    p = line.split()
    s, e = int(p[1]), int(p[2])
    if e <= s:
        continue
    ring = int(p[5]) if len(p) > 5 else -1
    rings[ring].append((s, e))
    kinds[(ring, p[3])] += 1
if not rings:
    sys.exit("no jt lines")
allv = [x for v in rings.values() for x in v]
t0, t1 = min(s for s, _ in allv), max(e for _, e in allv)
span = (t1 - t0) / 1e5
tot = union(allv) / 1e5
per = {r: union(v) / 1e5 for r, v in rings.items()}
print("window %.1f ms: GPU busy (any ring) %.1f ms = %.1f %%, idle %.1f ms" % (span, tot, 100 * tot / span, span - tot))
for r in sorted(per):
    print("  ring %2d: %6d jobs, busy %.1f ms (%.1f %%)" % (r, len(rings[r]), per[r], 100 * per[r] / span))
print("  both rings busy at once: %.1f ms (%.1f %% of the window)" % (sum(per.values()) - tot, 100 * (sum(per.values()) - tot) / span))
print("  jobs by ring and kind:", dict(kinds))
