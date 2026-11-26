#!/usr/bin/env python3
"""GPU time line from the jobs' own start/end timestamps ("jt <start> <end> <kind> <dwords>" lines,
BC5_DIRECT_JOB_TS=<t0>:<t1>, 100 MHz clock). Sorted by start: the union of the intervals is the
time the GPU had a job; the holes between are idle. Also the gap from each job's start to the
previous end (negative = queued behind it) and the busy time by buffer kind (union per kind).
Usage: jtunion.py direct.log"""
import collections
import sys

jobs = []
for line in open(sys.argv[1], errors="replace"):
    if not line.startswith("jt "):
        continue
    p = line.split()
    s, e = int(p[1]), int(p[2])
    if e > s:
        jobs.append((s, e, p[3], int(p[4])))
jobs.sort()
if not jobs:
    sys.exit("no jt lines")
t0, t1 = jobs[0][0], max(j[1] for j in jobs)
busy = idle = 0
holes = []
cur_s, cur_e = jobs[0][0], jobs[0][1]
for s, e, _, _ in jobs[1:]:
    if s > cur_e:
        busy += cur_e - cur_s
        holes.append(s - cur_e)
        idle += s - cur_e
        cur_s, cur_e = s, e
    else:
        cur_e = max(cur_e, e)
busy += cur_e - cur_s
span = t1 - t0
print(f"{len(jobs)} jobs over {span / 1e5:.1f} ms: GPU had work {busy / 1e5:.1f} ms ({100 * busy / span:.1f} %), idle {idle / 1e5:.1f} ms in {len(holes)} holes")
holes.sort()
if holes:
    q = lambda f: holes[min(len(holes) - 1, int(f * len(holes)))] / 100
    print(f"  holes: median {q(0.5):.1f} us, p90 {q(0.9):.1f} us, p99 {q(0.99):.1f} us; under 50 us {sum(1 for h in holes if h < 5000)}, 50-500 us {sum(1 for h in holes if 5000 <= h < 50000)}, over 500 us {sum(1 for h in holes if h >= 50000)} ({sum(h for h in holes if h >= 50000) / 1e5:.1f} ms)")
dur = collections.defaultdict(int)
n = collections.Counter()
for s, e, k, d in jobs:
    dur[k] += e - s
    n[k] += 1
for k in sorted(dur, key=lambda x: -dur[x]):
    print(f"  {k}: {n[k]} jobs, summed start-to-end {dur[k] / 1e5:.1f} ms (mean {dur[k] / n[k] / 100:.1f} us)")
