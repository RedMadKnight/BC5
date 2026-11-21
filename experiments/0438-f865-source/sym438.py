#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438 (tag cpy438): symbolize the shim's records, on the box (in the ubuntu distrobox: addr2line).
Usage: python3 -I sym438.py RECORDS.txt MAPS [RT_PERF.txt.gz SPIN_LO SPIN_HI] > out.txt
  RECORDS  cpy438's "t_ns tid comm size dst src f0 f1 ..." lines (hex addresses).
  MAPS     its /proc/self/maps copy (the later one: the guest's modules mapped).
  RT_PERF  optional: prof0438 cpu-mode perf script of the Render Thread and the spin loop's range (hex, private), to mark
           the records that fall inside a spin episode (runs of samples in the range, <= 15 ms apart, >= 3).
Prints per thread name: copies and bytes, in and out of the spins; the top caller chains (file-backed frames named by
addr2line -f -C as function@file, guest / anonymous frames as [guest] / [anon]); the size distribution; the top
destination and source mappings.
"""
import bisect
import collections
import gzip
import re
import subprocess
import sys

rec_p, maps_p = sys.argv[1], sys.argv[2]
rt_p = sys.argv[3] if len(sys.argv) > 5 else None
regs = []
for ln in open(maps_p):
    p = ln.split()
    if len(p) >= 5:
        a, b = (int(x, 16) for x in p[0].split('-'))
        regs.append((a, b, int(p[2], 16), p[5] if len(p) > 5 else '', p[1]))
regs.sort()
starts = [r[0] for r in regs]


def region(x):
    i = bisect.bisect_right(starts, x) - 1
    return regs[i] if i >= 0 and regs[i][0] <= x < regs[i][1] else None


recs = []
for ln in open(rec_p):
    if ln.startswith('#'):
        continue
    p = ln.split()
    if len(p) < 6:
        continue
    t, tid, comm = int(p[0]), int(p[1]), p[2]  # the shim writes the name with "_" for spaces: one field
    size, dst, src = int(p[3]), int(p[4], 16), int(p[5], 16)
    frames = [int(x, 16) for x in p[6:]]
    recs.append((t, tid, comm, size, dst, src, frames))
# addr2line per file, batched
want = collections.defaultdict(set)
for r in recs:
    for f in r[6]:
        g = region(f)
        if g and g[3].startswith('/') and 'memfd' not in g[3]:
            want[g[3]].add(f - g[0] + g[2])
names = {}
for path, offs in want.items():
    offs = sorted(offs)
    try:
        out = subprocess.run(['addr2line', '-f', '-C', '-e', path] + [hex(o) for o in offs], capture_output=True, text=True, timeout=600).stdout.split('\n')
    except Exception as e:
        out = []
    for i, o in enumerate(offs):
        fn = out[2 * i] if 2 * i < len(out) else '?'
        names[(path, o)] = fn + '@' + path.split('/')[-1]


def fname(f):
    g = region(f)
    if not g:
        return '[none]'
    if 'KytyPrivateMemory' in g[3]:
        return '[guest]'
    if not g[3].startswith('/'):
        return '[anon]'
    return names.get((g[3], f - g[0] + g[2]), '?@' + g[3].split('/')[-1])


def mapname(x):
    g = region(x)
    return (g[3].split('/')[-1] or '[anon]') if g else '[none]'


eps, st = [], []
if rt_p:
    lo, hi = int(sys.argv[4], 16), int(sys.argv[5], 16)
    DSO = r'\(((?:[^()]|\([^()]*\))*)\)'
    ONE = re.compile(r'^\s*(\d+)\s+([0-9.]+):\s+([0-9a-f]+)\s+(.*?)\s+' + DSO + r'\s*$')
    ts = []
    for ln in gzip.open(rt_p, 'rt', errors='replace'):
        m = ONE.match(ln)
        if m:
            ts.append((float(m.group(2)), int(m.group(3), 16)))
    ts.sort()
    cur = []
    for t, ip in ts:
        inside = lo <= ip < hi
        if inside and cur and t - cur[-1] <= 0.015:
            cur.append(t)
        else:
            if len(cur) >= 3:
                eps.append((cur[0], cur[-1]))
            cur = [t] if inside else []
    st = [e[0] for e in eps]


def inspin(t_ns):
    t = t_ns / 1e9
    i = bisect.bisect_right(st, t) - 1
    return i >= 0 and t <= eps[i][1]


print(f'{len(recs)} copies of the bar or more; threads {len({r[1] for r in recs})}; spin episodes {len(eps)}')
by = collections.defaultdict(list)
for r in recs:
    by[r[2]].append(r)
for comm, rs in sorted(by.items(), key=lambda kv: -sum(r[3] for r in kv[1])):
    ins = [r for r in rs if eps and inspin(r[0])]
    print(f'== {comm}: {len(rs)} copies, {sum(r[3] for r in rs) / 2**20:.1f} MiB; in spins {len(ins)} copies, {sum(r[3] for r in ins) / 2**20:.1f} MiB')
    for label, sel in (('in spins', ins), ('all', rs)):
        if not sel:
            continue
        ch = collections.Counter(' <- '.join(fname(f) for f in r[6][:8]) for r in sel)
        print(f'   {label}: top caller chains (copies):')
        for k, v in ch.most_common(6):
            print(f'      {v}  {k}')
    sz = collections.Counter(min(r[3] >> 20, 64) for r in rs)
    print('   sizes (MiB, capped at 64): ' + ', '.join(f'{k}: {v}' for k, v in sorted(sz.items())))
    print('   dst: ' + '; '.join(f'{k} {v}' for k, v in collections.Counter(mapname(r[4]) for r in rs).most_common(4)) +
          ' | src: ' + '; '.join(f'{k} {v}' for k, v in collections.Counter(mapname(r[5]) for r in rs).most_common(4)))
