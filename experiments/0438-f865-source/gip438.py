#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438: where the Render Thread's guest CPU goes, from prof0438's cpu samples (lean P runs). DIAGNOSIS.
Usage: gip438.py OUT_IPS.txt PHASES MARKS.txt PERF.txt.gz MAPS.txt [MARKS PERF MAPS ...]
  PHASES: "fast=140-270,dip=280-290,slow=295-415" (seconds since each run's first frame mark).
  A guest sample is one whose ip lies in a /memfd:KytyPrivateMemory mapping with execute permission. Its module is its
  256-MiB load base (KytyPlus loads each guest module at 0x9N0000000 in this title's maps); it is shown as
  module@base+offset. Per group (vblank class 1 / 2 / 3+; phase x class), over all runs given:
  - guest samples per frame; distinct ips; how many ips, 64-byte lines and 4-KiB pages hold 50 % / 90 % of the samples
    (a spin or busy-wait: a few ips hold most; real work: spread);
  - the top 15 ips and top 10 pages as module@base+offset with their share;
  - whether the 3+ frames' extra samples sit in the same places as the 1-vblank frames' (the overlap of their top-50
    pages, by share).
  OUT_IPS.txt: the top 60 ips over the 3+ and dip frames together, "module_base offset samples", for the bytes read
  (gipbytes438.sh on the box).
"""
import bisect
import gzip
import importlib.util
import os
import sys
from collections import Counter, defaultdict

here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('pf438', os.path.join(here, 'pf438.py'))
pf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pf)
VB = 1000.0 / 60.0


def exec_regions(p):
    regs = []
    with pf.opener(p) as f:
        for ln in f:
            parts = ln.split()
            if len(parts) >= 6 and 'KytyPrivateMemory' in ln and 'x' in parts[1]:
                a, b = (int(x, 16) for x in parts[0].split('-'))
                regs.append((a, b))
    regs.sort()
    return regs


def cover(counter, frac):
    tot = sum(counter.values())
    acc, n = 0, 0
    for _, v in counter.most_common():
        acc += v
        n += 1
        if acc >= frac * tot:
            break
    return n


def name(ip):
    base = ip & ~0xfffffff
    return f'module@{base:x}+{ip - base:x}'


def main():
    out_p, phases_s = sys.argv[1], sys.argv[2]
    phases = []
    for part in phases_s.split(','):
        n, _, r = part.partition('=')
        a, _, b = r.partition('-')
        phases.append((n, float(a), float(b)))
    runs = sys.argv[3:]
    groups = defaultdict(lambda: {'frames': 0, 'ips': Counter(), 'all': 0})
    for k in range(0, len(runs), 3):
        marks = sorted(int(x) for x in open(runs[k]) if x.strip().isdigit())
        samples = pf.load_perf(runs[k + 1])
        regs = exec_regions(runs[k + 2])
        starts = [r[0] for r in regs]
        t0 = marks[0]
        frames = [(marks[i], marks[i + 1]) for i in range(len(marks) - 1)]
        fst = [f[0] for f in frames]
        per = defaultdict(list)
        for s in samples:
            i = bisect.bisect_right(fst, s[0]) - 1
            if i >= 0 and s[0] < frames[i][1]:
                per[i].append(s[2])
        for i, (a, b) in enumerate(frames):
            t = (a - t0) / 1e9
            if not 136 <= t < 416:
                continue
            ms = (b - a) / 1e6
            v = max(1, round(ms / VB))
            c = '1' if v == 1 else '2' if v == 2 else '3+'
            keys = [f'{c} vblank'] + [f'{n} phase, {c} vblank' for n, p0, p1 in phases if p0 <= t < p1] + [f'{n} phase' for n, p0, p1 in phases if p0 <= t < p1]
            g_ips = []
            for ip in per[i]:
                j = bisect.bisect_right(starts, ip) - 1
                if j >= 0 and regs[j][0] <= ip < regs[j][1]:
                    g_ips.append(ip)
            for key in keys:
                G = groups[key]
                G['frames'] += 1
                G['all'] += len(per[i])
                G['ips'].update(g_ips)
    order = ['1 vblank', '2 vblank', '3+ vblank'] + [f'{n} phase{x}' for n, _, _ in phases for x in ('', ', 1 vblank', ', 3+ vblank')]
    for key in order:
        G = groups.get(key)
        if not G or G['frames'] == 0:
            continue
        ips = G['ips']
        tot = sum(ips.values())
        if tot == 0:
            print(f'{key}: {G["frames"]} frames, no guest samples')
            continue
        lines = Counter()
        pages = Counter()
        for ip, v in ips.items():
            lines[ip >> 6] += v
            pages[ip >> 12] += v
        print(f'{key}: {G["frames"]} frames, guest {tot / G["frames"]:.2f} of {G["all"] / G["frames"]:.2f} samples per frame; distinct ips {len(ips)}; '
              f'50 % / 90 % in {cover(ips, .5)} / {cover(ips, .9)} ips, {cover(lines, .5)} / {cover(lines, .9)} lines, {cover(pages, .5)} / {cover(pages, .9)} pages')
        print('   top ips: ' + '; '.join(f'{name(ip)} {v * 100 / tot:.1f}%' for ip, v in ips.most_common(15)))
        print('   top pages: ' + '; '.join(f'{name(p << 12)} {v * 100 / tot:.1f}%' for p, v in pages.most_common(10)))
        mods = Counter()
        for ip, v in ips.items():
            mods[ip & ~0xfffffff] += v
        print('   by module: ' + '; '.join(f'module@{m:x} {v * 100 / tot:.1f}%' for m, v in mods.most_common(6)))
    a, b = groups.get('1 vblank'), groups.get('3+ vblank')
    if a and b:
        pa, pb = Counter(), Counter()
        for ip, v in a['ips'].items():
            pa[ip >> 12] += v
        for ip, v in b['ips'].items():
            pb[ip >> 12] += v
        ta, tb = sum(pa.values()), sum(pb.values())
        top_a = {p for p, _ in pa.most_common(50)}
        share_b_in_a = sum(v for p, v in pb.items() if p in top_a) / max(1, tb)
        top_b = {p for p, _ in pb.most_common(50)}
        share_a_in_b = sum(v for p, v in pa.items() if p in top_b) / max(1, ta)
        print(f'overlap: {share_b_in_a * 100:.1f} % of the 3+ frames\' guest samples lie in the 1-vblank frames\' top-50 pages; {share_a_in_b * 100:.1f} % the other way')
    hot = Counter()
    for key in ('3+ vblank', 'dip phase'):
        if key in groups:
            hot.update(groups[key]['ips'])
    with open(out_p, 'w', newline='\n') as f:
        for ip, v in hot.most_common(60):
            base = ip & ~0xfffffff
            f.write(f'{base:x} {ip - base:x} {v}\n')
    print(f'{out_p}: top {min(60, len(hot))} ips of the 3+ and dip frames')


if __name__ == '__main__':
    main()
