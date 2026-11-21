#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438: the Render Thread's perf samples (or page faults) by frame, from m438's frame marks. DIAGNOSIS.
Usage: pf438.py MARKS.txt PERF.txt[.gz] [MAPS.txt] [FROM_S TO_S] [NAME=A-B ...]
  MARKS.txt  m438: one steady-clock (CLOCK_MONOTONIC) ns per flip; t = seconds since the first mark.
  PERF.txt   prof0438.sh's perf script (--ns): "tid time: [addr] ip sym (dso)"; the fault mode has the data address
             first (two hex fields before the symbol), the cpu mode one.
  MAPS.txt   a /proc/<pid>/maps snapshot (prof0438's -maps-<n>.txt): fault addresses and ips are named by mapping.
  FROM_S / TO_S: the window in t; NAME=A-B: phases (e.g. fast=140-270 dip=280-290 slow=295-415).
Groups: all; vblank class 1 / 2 / 3+ (the frame's mark-to-mark time / 16.667 ms, rounded); each phase, and phase x class.
Per group: frames; samples per frame (cpu mode: x 1.001 ms at 999 Hz) or faults per frame; the top DSOs and symbols (by
the ip's mapping when perf has no symbol); for faults also the top mappings of the data address.
Prints the marks per 10 s first, to place the phases.
"""
import bisect
import gzip
import re
import sys
from collections import Counter, defaultdict

VB = 1000.0 / 60.0


def opener(p):
    return gzip.open(p, 'rt', encoding='utf-8', errors='replace') if p.endswith('.gz') else open(p, encoding='utf-8', errors='replace')


def load_maps(p):
    regs = []
    with opener(p) as f:
        for ln in f:
            m = re.match(r'^([0-9a-f]+)-([0-9a-f]+) (\S+) \S+ \S+ \S+\s*(.*)$', ln.strip())
            if not m:
                continue
            a, b = int(m.group(1), 16), int(m.group(2), 16)
            name = m.group(4) or f'[anon {m.group(3)} {(b - a) / 2**20:.0f} MiB @{a:x}]'
            regs.append((a, b, name))
    regs.sort()
    return regs


def region(regs, starts, x):
    i = bisect.bisect_right(starts, x) - 1
    if i >= 0 and regs[i][0] <= x < regs[i][1]:
        return regs[i][2]
    return '[no mapping]'


SAMPLE = re.compile(r'^\s*(\d+)\s+([0-9.]+):\s+(.*)$')
HEX = re.compile(r'^[0-9a-f]+$')


def load_perf(p):
    out = []  # (t_ns, addr or None, ip, sym, dso)
    with opener(p) as f:
        for ln in f:
            m = SAMPLE.match(ln)
            if not m:
                continue
            t = int(round(float(m.group(2)) * 1e9))
            rest = m.group(3).strip()
            dso = ''
            dm = re.search(r'\(([^()]*)\)\s*$', rest)
            if dm:
                dso = dm.group(1)
                rest = rest[:dm.start()].strip()
            toks = rest.split()
            hexes = []
            while toks and HEX.match(toks[0]) and len(hexes) < 2:
                hexes.append(int(toks.pop(0), 16))
            sym = ' '.join(toks) or '[unknown]'
            sym = re.sub(r'\+0x[0-9a-f]+$', '', sym)
            if len(hexes) == 2:
                out.append((t, hexes[0], hexes[1], sym, dso))
            elif len(hexes) == 1:
                out.append((t, None, hexes[0], sym, dso))
    return out


def cls(ms):
    v = max(1, round(ms / VB))
    return '1' if v == 1 else '2' if v == 2 else '3+'


def main():
    a = sys.argv[1:]
    marks_p, perf_p = a[0], a[1]
    rest = a[2:]
    maps_p = None
    if rest and not re.match(r'^[0-9.]+$', rest[0]) and '=' not in rest[0]:
        maps_p = rest.pop(0)
    lo, hi = -1e18, 1e18
    if len(rest) >= 2 and re.match(r'^[0-9.]+$', rest[0]) and re.match(r'^[0-9.]+$', rest[1]):
        lo, hi = float(rest[0]), float(rest[1])
        rest = rest[2:]
    phases = []
    for x in rest:
        n, _, rng = x.partition('=')
        p0, _, p1 = rng.partition('-')
        phases.append((n, float(p0), float(p1)))
    marks = [int(x) for x in open(marks_p) if x.strip().isdigit()]
    marks.sort()
    t0 = marks[0]
    per10 = Counter(int((m - t0) / 1e10) for m in marks)
    print(f'{marks_p}: {len(marks)} marks; per 10 s from the first: ' + ' '.join(str(per10[i]) for i in range(0, max(per10) + 1)))
    regs = load_maps(maps_p) if maps_p else []
    starts = [r[0] for r in regs]
    samples = load_perf(perf_p)
    faults = any(s[1] is not None for s in samples)
    print(f'{perf_p}: {len(samples)} {"faults" if faults else "cpu samples"}; maps {len(regs)} regions')
    # frames: [marks[i], marks[i+1])
    frames = []
    for i in range(len(marks) - 1):
        t = (marks[i] - t0) / 1e9
        if lo <= t < hi:
            frames.append((marks[i], marks[i + 1], t, (marks[i + 1] - marks[i]) / 1e6))
    fstarts = [f[0] for f in frames]
    by_frame = defaultdict(list)
    for s in samples:
        i = bisect.bisect_right(fstarts, s[0]) - 1
        if i >= 0 and s[0] < frames[i][1]:
            by_frame[i].append(s)

    def show(name, idx):
        if not idx:
            print(f'{name}: no frames')
            return
        n = len(idx)
        ss = [s for i in idx for s in by_frame[i]]
        ms = sum(frames[i][3] for i in idx) / n
        unit = 'faults' if faults else 'samples (~1 ms each)'
        print(f'{name}: {n} frames, mean frame {ms:.1f} ms, {len(ss) / n:.2f} {unit} per frame')
        if not ss:
            return
        dsos = Counter((s[4] if s[4] and s[4] != '[unknown]' else region(regs, starts, s[2])) for s in ss)
        syms = Counter((s[3] if s[3] != '[unknown]' else '?') + ' @ ' + (s[4] if s[4] and s[4] != '[unknown]' else region(regs, starts, s[2])) for s in ss)
        tot = len(ss)
        print('   by dso/mapping of the ip: ' + '; '.join(f'{k} {v * 100 / tot:.1f}%' for k, v in dsos.most_common(8)))
        print('   by symbol: ' + '; '.join(f'{k} {v * 100 / tot:.1f}%' for k, v in syms.most_common(10)))
        if faults:
            ad = Counter(region(regs, starts, s[1]) for s in ss)
            print('   by mapping of the faulting address: ' + '; '.join(f'{k} {v * 100 / tot:.1f}% ({v / n:.1f}/frame)' for k, v in ad.most_common(8)))
            pages = Counter(s[1] >> 12 for s in ss)
            print(f'   distinct pages {len(pages)}, faults per page {tot / max(1, len(pages)):.2f}')

    allidx = list(range(len(frames)))
    show('ALL', allidx)
    for c in ('1', '2', '3+'):
        show(f'{c} vblank', [i for i in allidx if cls(frames[i][3]) == c])
    for ph, p0, p1 in phases:
        sub = [i for i in allidx if p0 <= frames[i][2] < p1]
        show(f'{ph} phase [{p0:g}, {p1:g})', sub)
        for c in ('1', '3+'):
            show(f'{ph} phase, {c} vblank', [i for i in sub if cls(frames[i][3]) == c])


if __name__ == '__main__':
    main()
