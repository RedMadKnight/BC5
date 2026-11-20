#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438: frame-time statistics from MangoHud's own per-frame CSV log (log_interval=0).
Usage: mh0438.py G_SECONDS FROM_G TO_G LOG.csv [LOG.csv ...]
  Frames whose MangoHud 'elapsed' (ns since its log began) lies in [G+FROM_G, G+TO_G) seconds are used. MangoHud's
  clock starts a few seconds after the runner's (at the title's first present), so the window is the same for every
  arm only up to that offset; the route is by time, so G is the same number in every arm.
Prints per log: frames, mean flips/s (frames / span), frame time median / p95 / p99 / max (ms), frames over 50 and
100 ms, and the share of the time spent in frames over 50 ms.
"""
import csv
import sys


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


def pct(v, p):
    k = min(len(v) - 1, max(0, int(round(p / 100.0 * (len(v) - 1)))))
    return v[k]


def stats(rows, a, b):
    w = [x for x in rows if a <= x[0] < b]
    if len(w) < 2:
        return None
    ft = sorted(x[1] for x in w)
    span = w[-1][0] - w[0][0]
    over50 = [x for x in ft if x > 50]
    return {
        'frames': len(w), 'span': span, 'fps': (len(w) - 1) / span if span > 0 else 0.0,
        'p50': pct(ft, 50), 'p95': pct(ft, 95), 'p99': pct(ft, 99), 'max': ft[-1],
        'n50': len(over50), 'n100': sum(1 for x in ft if x > 100), 'share50': 100.0 * sum(over50) / sum(ft),
    }


def main():
    g, a, b = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])
    print('log | frames | span s | flips/s | frame time p50 / p95 / p99 / max ms | frames > 50 / > 100 ms | time in frames > 50 ms')
    for p in sys.argv[4:]:
        s = stats(load(p), g + a, g + b)
        if s is None:
            print('%s | no frames in the window' % p)
            continue
        print('%s | %d | %.0f | %.2f | %.1f / %.1f / %.1f / %.0f | %d / %d | %.1f %%' % (
            p, s['frames'], s['span'], s['fps'], s['p50'], s['p95'], s['p99'], s['max'], s['n50'], s['n100'], s['share50']))


if __name__ == '__main__':
    main()
