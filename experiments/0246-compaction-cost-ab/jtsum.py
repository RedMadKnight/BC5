#!/usr/bin/env python3
# Per-job GPU intervals of a BC5_DIRECT_JOB_TS=<t0>:<t1> window ("jt <start> <end> <kind> <dwords> <ring>", 100 MHz
# ticks) read on stdin: the window's span, the union of busy time, and the GPU time per buffer kind and size class
# (the largest classes first), so two arms can be compared by which buffers grew.
# usage: LC_ALL=C grep -a '^jt ' direct.log | jtsum.py <name>
import collections
import sys

name = sys.argv[1]
jobs = []
for line in sys.stdin:
    f = line.split()
    if len(f) >= 6 and f[0] == "jt":
        jobs.append((int(f[1]), int(f[2]), f[3], int(f[4]), f[5]))
if not jobs:
    print(name, "no jt lines")
    sys.exit(0)
jobs.sort()
t0, t1 = jobs[0][0], max(j[1] for j in jobs)
span = (t1 - t0) / 1e5  # ms
union = 0
cur_s, cur_e = jobs[0][0], jobs[0][1]
for s, e, *_ in jobs[1:]:
    if s > cur_e:
        union += cur_e - cur_s
        cur_s, cur_e = s, e
    else:
        cur_e = max(cur_e, e)
union += cur_e - cur_s
print("%s: %d jobs over %.0f ms of GPU time line, busy (union) %.0f ms = %.1f %%" % (name, len(jobs), span, union / 1e5, 100.0 * union / max(t1 - t0, 1)))
cls = collections.defaultdict(lambda: [0, 0, 0])
for s, e, kind, dw, ring in jobs:
    k = (kind, ring, dw)
    cls[k][0] += 1
    cls[k][1] += e - s
    cls[k][2] = max(cls[k][2], e - s)
print("  per buffer (kind ring dwords): jobs, GPU ms in total, ms per second of time line, longest ms")
for (kind, ring, dw), (n, tot, mx) in sorted(cls.items(), key=lambda kv: -kv[1][1])[:25]:
    print("  %s r%s %6d: %5d jobs %8.1f ms %6.1f ms/s %7.2f" % (kind, ring, dw, n, tot / 1e5, tot / 1e5 / (span / 1000.0), mx / 1e5))
