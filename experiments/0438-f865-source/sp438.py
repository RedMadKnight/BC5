#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438: who runs, and who waits, while the Render Thread spins (prof0438.sh PROF_MODE=all). DIAGNOSIS.
Usage: sp438.py RANGES PERF.txt.gz THREADS.txt TID.txt
  RANGES   a private file (never committed): "spin <lo> <hi>" (absolute guest addresses, hex: the Render Thread's wait
           loop) and optional "near <lo> <hi>" lines (code near the stores that release it), one per line.
  PERF     perf script -F comm,tid,time,ip,sym,dso --ns of every thread at 199 Hz.
  THREADS  prof0438's per-second "T <uptime>" blocks of "tid comm state run_ns wait_ns slices".
  TID      prof0438's Render Thread tid file.
Spin episodes: runs of the Render Thread's samples inside "spin", no two more than 15 ms apart, of 3 samples or more.
Prints: the episodes (count, total, longest); while they last, the other threads' samples by name (each sample ~5 ms
of CPU); in the 10 ms before each episode's end, the threads with samples, and in "near" which threads ran there; from
schedstat, per thread name: CPU and run-queue wait per second in seconds with a spin episode and in those without.
"""
import bisect
import gzip
import re
import sys
from collections import Counter, defaultdict

rng_p, perf_p, thr_p, tid_p = sys.argv[1:5]
spin, near = None, []
for ln in open(rng_p):
    p = ln.split()
    if len(p) == 3 and p[0] == 'spin':
        spin = (int(p[1], 16), int(p[2], 16))
    elif len(p) == 3 and p[0] == 'near':
        near.append((int(p[1], 16), int(p[2], 16)))
assert spin is not None
rt = int(open(tid_p).read().split()[1])
DSO = r'\(((?:[^()]|\([^()]*\))*)\)'
LINE = re.compile(r'^\s*(.+?)\s+(\d+)\s+([0-9.]+):\s+([0-9a-f]+)\s+(.*?)\s+' + DSO + r'\s*$')
samples = []  # (t_ns, tid, comm, ip, sym, dso)
op = gzip.open(perf_p, 'rt', encoding='utf-8', errors='replace') if perf_p.endswith('.gz') else open(perf_p, encoding='utf-8', errors='replace')
with op as f:
    for ln in f:
        m = LINE.match(ln)
        if m:
            samples.append((int(round(float(m.group(3)) * 1e9)), int(m.group(2)), m.group(1), int(m.group(4), 16), m.group(5), m.group(6)))
samples.sort()
print(f'{len(samples)} samples, {len({s[1] for s in samples})} threads; Render Thread tid {rt}')
rts = [s for s in samples if s[1] == rt]
eps, cur = [], []
for s in rts:
    inside = spin[0] <= s[3] < spin[1]
    if inside and cur and s[0] - cur[-1][0] <= 15_000_000:
        cur.append(s)
    else:
        if len(cur) >= 3:
            eps.append((cur[0][0], cur[-1][0]))
        cur = [s] if inside else []
if len(cur) >= 3:
    eps.append((cur[0][0], cur[-1][0]))
tot = sum(b - a for a, b in eps)
print(f'spin episodes: {len(eps)}, {tot / 1e9:.2f} s in all, longest {max((b - a for a, b in eps), default=0) / 1e6:.1f} ms; '
      f'Render Thread samples in the spin {sum(1 for s in rts if spin[0] <= s[3] < spin[1])} of {len(rts)}')
ts = [s[0] for s in samples]
during = Counter()
during_sym = defaultdict(Counter)
end_before = Counter()
near_end = Counter()
for a, b in eps:
    for s in samples[bisect.bisect_left(ts, a):bisect.bisect_right(ts, b)]:
        if s[1] != rt:
            during[s[2]] += 1
            during_sym[s[2]][(s[4] if s[4] != '[unknown]' else '?') + ' @ ' + s[5].split('/')[-1]] += 1
    seen = set()
    for s in samples[bisect.bisect_left(ts, b - 10_000_000):bisect.bisect_right(ts, b + 2_000_000)]:
        if s[1] != rt and s[2] not in seen:
            seen.add(s[2])
            end_before[s[2]] += 1
        if s[1] != rt and any(lo <= s[3] < hi for lo, hi in near):
            near_end[s[2]] += 1
print(f'other threads\' samples during the spins ({tot / 1e9:.2f} s): ' + '; '.join(f'{k} {v}' for k, v in during.most_common(14)))
for k, _ in during.most_common(6):
    print(f'   {k}: ' + '; '.join(f'{x} {v}' for x, v in during_sym[k].most_common(5)))
print(f'threads with a sample in the 10 ms before a spin ends (of {len(eps)} ends): ' + '; '.join(f'{k} {v}' for k, v in end_before.most_common(12)))
if near:
    allnear = Counter(s[2] for s in samples if s[1] != rt and any(lo <= s[3] < hi for lo, hi in near))
    print(f'samples in "near" (the releasing stores\' code): at spin ends {dict(near_end)}; in the whole run {dict(allnear)}')
# schedstat: per-second deltas, by thread name; a second "with a spin" holds >= 50 ms of episodes
blocks, curb = [], None
for ln in open(thr_p):
    p = ln.split()
    if p and p[0] == 'T':
        curb = (float(p[1]), {})
        blocks.append(curb)
    elif curb is not None and len(p) >= 6:
        curb[1][int(p[0])] = (p[1], p[2], int(p[3]), int(p[4]))
spin_s = defaultdict(int)
for a, b in eps:
    spin_s[int(a / 1e9)] += b - a
acc = {True: defaultdict(lambda: [0, 0, 0]), False: defaultdict(lambda: [0, 0, 0])}
for (t0, b0), (t1, b1) in zip(blocks, blocks[1:]):
    dt = t1 - t0
    if dt <= 0 or dt > 3:
        continue
    with_spin = spin_s.get(int(t0), 0) + spin_s.get(int(t1), 0) >= 50_000_000
    for tid, (comm, st, run, wait) in b1.items():
        if tid in b0:
            a = acc[with_spin][comm]
            a[0] += (run - b0[tid][2]) / dt
            a[1] += (wait - b0[tid][3]) / dt
            a[2] += 1
for w in (True, False):
    rows = sorted(acc[w].items(), key=lambda kv: -kv[1][0])
    print(f'schedstat, seconds {"WITH" if w else "without"} spin episodes (>= 50 ms of them), per thread name (its threads summed):')
    n_sec = sum(1 for (t0, b0), (t1, b1) in zip(blocks, blocks[1:]) if (spin_s.get(int(t0), 0) + spin_s.get(int(t1), 0) >= 50_000_000) == w)
    for k, v in rows[:16]:
        print(f'   {k}: CPU {v[0] / 1e6 / max(1, n_sec):.1f} ms/s, run-queue wait {v[1] / 1e6 / max(1, n_sec):.1f} ms/s')
    print(f'   ({n_sec} seconds)')
