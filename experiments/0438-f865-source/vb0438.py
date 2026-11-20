#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438: frame-time histogram by vblank count, from MangoHud's per-frame CSV log (log_interval=0).
Usage: vb0438.py G_SECONDS FROM_G TO_G LOG.csv [LOG.csv ...]
A frame of t ms is counted as round(t / 16.667) vblanks (0 counted as 1). Per log, then summed over all logs given:
frames and share of wall time per bucket (1, 2, 3, 4, 5-6, 7-12, >12 vblanks), and how the long frames cluster
(runs of consecutive frames of 3+ vblanks; the gap in seconds between such frames).
"""
import csv
import sys


# the same reader as mh0438.py
def load(path):
    rows = []
    with open(path, newline='', encoding='utf-8', errors='replace') as f:
        r = csv.reader(f)
        ft = el = None
        for row in r:
            if ft is None:
                if row and row[0] == 'fps':
                    ft, el = row.index('frametime'), row.index('elapsed')
                continue
            try:
                rows.append((float(row[el]) / 1e9, float(row[ft])))
            except (ValueError, IndexError):
                continue
    return rows

VB = 1000.0 / 60.0
BUCKETS = [(1, 1), (2, 2), (3, 3), (4, 4), (5, 6), (7, 12), (13, 10**9)]


def name(b):
    lo, hi = b
    return f'{lo}' if lo == hi else (f'>{lo - 1}' if hi > 10**6 else f'{lo}-{hi}')


def stats(frames):
    n = [0] * len(BUCKETS)
    t = [0.0] * len(BUCKETS)
    for _, ft in frames:
        v = max(1, round(ft / VB))
        for i, (lo, hi) in enumerate(BUCKETS):
            if lo <= v <= hi:
                n[i] += 1
                t[i] += ft
                break
    return n, t


def show(label, frames):
    n, t = stats(frames)
    N, T = sum(n), sum(t)
    cells = ' | '.join(f'{name(b)}: {n[i] / N * 100:5.1f} % fr {t[i] / T * 100:5.1f} % time' for i, b in enumerate(BUCKETS))
    # clustering of long frames (3+ vblanks)
    longs = [i for i, (_, ft) in enumerate(frames) if round(ft / VB) >= 3]
    runs, cur = [], 0
    prev = None
    for i in longs:
        cur = cur + 1 if prev is not None and i == prev + 1 else 1
        if prev is not None and i != prev + 1:
            runs.append(last)
        last, prev = cur, i
    if longs:
        runs.append(last)
    gaps = sorted(frames[b][0] - frames[a][0] for a, b in zip(longs, longs[1:]))
    med_gap = gaps[len(gaps) // 2] if gaps else 0
    single = sum(1 for r in runs if r == 1)
    print(f'{label} | frames {N} | {cells} | long frames {len(longs)} in {len(runs)} runs ({single} alone), median gap between long frames {med_gap * 1000:.0f} ms')


def main():
    g, a, b = (float(x) for x in sys.argv[1:4])
    allf = []
    for p in sys.argv[4:]:
        fr = [(s, ft) for s, ft in load(p) if g + a <= s < g + b]
        if not fr:
            continue
        show(p, fr)
        allf += fr
    if allf:
        show('ALL', allf)


if __name__ == '__main__':
    main()
