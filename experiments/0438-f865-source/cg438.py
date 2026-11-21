#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438: who calls game-main's host memmove while the Render Thread spins (prof0438.sh stacks mode).
DIAGNOSIS. Usage: cg438.py RANGES GM_PERF.txt.gz RT_PERF.txt.gz [DEPTH]
  RANGES   the private file of sp438.py ("spin <lo> <hi>").
  GM_PERF  perf script of game-main with call chains (dwarf): a sample is a header line "tid time:" (optionally with the
           leaf on it) and its frames, one per line "ip sym (dso)", leaf first.
  RT_PERF  perf script of the Render Thread (one line per sample), for the spin episodes (as sp438.py: runs of samples
           in "spin", at most 15 ms apart, 3 or more).
Prints, for game-main's samples inside and outside the spins: the leaf symbols; for those whose leaf is a memmove /
memcpy, the caller chains above libc (DEPTH frames, default 6) by count; and how often a chain ends in guest code
(dso KytyPrivateMemory) after the host frames, i.e. which HLE entry the title called.
"""
import bisect
import gzip
import re
import sys
from collections import Counter

rng_p, gm_p, rt_p = sys.argv[1:4]
depth = int(sys.argv[4]) if len(sys.argv) > 4 else 6
spin = None
for ln in open(rng_p):
    p = ln.split()
    if len(p) == 3 and p[0] == 'spin':
        spin = (int(p[1], 16), int(p[2], 16))
DSO = r'\(((?:[^()]|\([^()]*\))*)\)'
HDR = re.compile(r'^\s*(\d+)\s+([0-9.]+):\s*(.*)$')
FRAME = re.compile(r'^\s+([0-9a-f]+)\s+(.*?)\s+' + DSO + r'\s*$')
ONE = re.compile(r'^\s*(\d+)\s+([0-9.]+):\s+([0-9a-f]+)\s+(.*?)\s+' + DSO + r'\s*$')


def opener(p):
    return gzip.open(p, 'rt', encoding='utf-8', errors='replace') if p.endswith('.gz') else open(p, encoding='utf-8', errors='replace')


rt = []
with opener(rt_p) as f:
    for ln in f:
        m = ONE.match(ln)
        if m:
            rt.append((float(m.group(2)), int(m.group(3), 16)))
rt.sort()
eps, cur = [], []
for t, ip in rt:
    inside = spin[0] <= ip < spin[1]
    if inside and cur and t - cur[-1] <= 0.015:
        cur.append(t)
    else:
        if len(cur) >= 3:
            eps.append((cur[0], cur[-1]))
        cur = [t] if inside else []
if len(cur) >= 3:
    eps.append((cur[0], cur[-1]))
st = [e[0] for e in eps]


def inspin(t):
    i = bisect.bisect_right(st, t) - 1
    return i >= 0 and t <= eps[i][1]


samples = []  # (t, [(ip, sym, dso), ...] leaf first)
with opener(gm_p) as f:
    curs = None
    for ln in f:
        m = ONE.match(ln)
        if m and not ln.startswith((' ', '\t')):
            curs = (float(m.group(2)), [(int(m.group(3), 16), m.group(4), m.group(5))])
            samples.append(curs)
            continue
        m = HDR.match(ln)
        if m and not ln.startswith((' ', '\t')):
            curs = (float(m.group(2)), [])
            samples.append(curs)
            continue
        m = FRAME.match(ln)
        if m and curs is not None:
            curs[1].append((int(m.group(1), 16), m.group(2), m.group(3)))


def clean(sym):
    return re.sub(r'\+0x[0-9a-f]+$', '', sym)


print(f'{len(eps)} spin episodes ({sum(b - a for a, b in eps):.2f} s); game-main samples {len(samples)}, '
      f'with frames {sum(1 for s in samples if len(s[1]) > 1)}')
for label, sel in (('IN the spins', True), ('outside', False)):
    ss = [s for s in samples if s[1] and inspin(s[0]) == sel]
    if not ss:
        print(f'{label}: none')
        continue
    leaves = Counter(clean(s[1][0][1]) + ' @ ' + s[1][0][2].split('/')[-1] for s in ss)
    print(f'{label}: {len(ss)} samples; leaves: ' + '; '.join(f'{k} {v * 100 / len(ss):.1f}%' for k, v in leaves.most_common(6)))
    cps = [s for s in ss if re.search(r'mem(move|cpy)', s[1][0][1])]
    chains, entries = Counter(), Counter()
    for s in cps:
        fr = [x for x in s[1][1:] if 'libc.so' not in x[2]]
        host = []
        for x in fr:
            if 'KytyPrivateMemory' in x[2]:
                entries[(host[-1] if host else '?')] += 1
                break
            host.append(clean(x[1]))
        chains[' <- '.join(host[:depth]) or '(no frames above libc)'] += 1
    if cps:
        print(f'   copies (leaf memmove/memcpy): {len(cps)} ({len(cps) * 100 / len(ss):.1f}%); caller chains:')
        for k, v in chains.most_common(10):
            print(f'      {v} ({v * 100 / len(cps):.1f}%)  {k}')
        if entries:
            print('   the host entry the guest called (the last host frame before guest code): ' + '; '.join(f'{k} {v}' for k, v in entries.most_common(6)))
