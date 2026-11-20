#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438 (tag h438): the Render Thread's frame, split, from h438's per-frame CSVs. DIAGNOSIS numbers.
Usage: ah438.py FROM_S TO_S [NAME=A-B ...] CSV [CSV ...]
  FROM_S / TO_S: the window in the CSV's own clock (t_s: seconds since the Render Thread's first recorded flip).
  NAME=A-B: a phase [A, B) of the scene, any number, e.g. fast=10-140 dip=145-165 slow=165-290 (the lean round's
  scene: ~45 flips/s, the dip to ~11 at G+150-160 in every run, then ~27; placed from each CSV's own frames per 10 s,
  which the script prints). Without phases, only all frames and the vblank classes.
Per group (all; by vblank class 1 / 2 / 3+; by phase x class), mean ms per frame:
  frame = cpu + runq + blocked, blocked = frame - cpu - runq (off CPU and not waiting for a CPU: asleep in the kernel);
  of blocked: gc calls by code (wall - CPU inside them), the flip span (its drain apart), o438's guest-sync waits, the
  rest ("other": blocked outside our spans and the guest syncs); lock waits (inside or outside the spans, timed
  apart); faults per frame.
"""
import csv
import sys
from collections import defaultdict

VB = 1000.0 / 60.0


def num(x):
    try:
        return float(x)
    except ValueError:
        return 0.0


def load(path):
    with open(path, newline='', encoding='utf-8', errors='replace') as f:
        r = csv.DictReader(f)
        return [row for row in r if row.get('t_s')]


def split(row):
    fr, cpu, rq = num(row['frame_ms']), num(row['cpu_ms']), num(row['runq_ms'])
    d = {'frame': fr, 'cpu': cpu, 'runq': rq, 'blocked': max(0.0, fr - cpu - rq)}
    gcb = 0.0
    for k in row:
        if k.startswith('gc_') and k.endswith('_blocked_us'):
            v = num(row[k]) / 1e3
            d['gc ' + k[3:-11] + ' blocked'] = v
            gcb += v
        if k.startswith('gc_') and k.endswith('_wall_us'):
            d['gc ' + k[3:-8] + ' wall'] = num(row[k]) / 1e3
        if k.startswith('gc_') and k.endswith('_n'):
            d['gc ' + k[3:-2] + ' calls'] = num(row[k])
    d['gc blocked'] = gcb
    d['flip blocked'] = num(row['flip_blocked_us']) / 1e3
    d['flip wall'] = num(row['flip_wall_us']) / 1e3
    d['drain blocked'] = num(row['drain_blocked_us']) / 1e3
    d['guest blocked'] = num(row['guest_blocked_us']) / 1e3
    d['other blocked'] = d['blocked'] - gcb - d['flip blocked'] - d['guest blocked']
    d['lock wait'] = num(row['lock_wait_us']) / 1e3
    d['minflt'] = num(row['minflt'])
    d['majflt'] = num(row['majflt'])
    locks = {}
    if row['locks'] not in ('', '-'):
        for kv in row['locks'].split(';'):
            n, _, v = kv.rpartition('=')
            locks[n] = num(v) / 1e3
    guest = {}
    if row['guest'] not in ('', '-'):
        for kv in row['guest'].split(';'):
            n, _, v = kv.rpartition('=')
            guest[n] = num(v) / 1e3
    return d, locks, guest


def cls(fr):
    v = max(1, round(fr / VB))
    return '1' if v == 1 else '2' if v == 2 else '3+'


MAIN = ['frame', 'cpu', 'runq', 'blocked', 'gc blocked', 'flip blocked', 'drain blocked', 'guest blocked', 'other blocked', 'lock wait', 'minflt', 'majflt']


def show(name, rows):
    if not rows:
        print(f'{name}: no frames')
        return
    n = len(rows)
    acc = defaultdict(float)
    lk = defaultdict(float)
    gu = defaultdict(float)
    for d, locks, guest in rows:
        for k, v in d.items():
            acc[k] += v
        for k, v in locks.items():
            lk[k] += v
        for k, v in guest.items():
            gu[k] += v
    print(f'{name}: {n} frames | ' + ' | '.join(f'{k} {acc[k] / n:.2f}' for k in MAIN))
    gcs = sorted((k for k in acc if k.startswith('gc ') and k.endswith(' blocked') and k != 'gc blocked'), key=lambda k: -acc[k])
    print('   gc by code (blocked / wall ms per frame, calls): ' + '; '.join(f'{k[3:-8]} {acc[k] / n:.2f} / {acc[k[:-8] + " wall"] / n:.2f}, {acc[k[:-8] + " calls"] / n:.1f}' for k in gcs if acc[k[:-8] + ' calls'] > 0))
    if lk:
        by = defaultdict(float)
        for k, v in lk.items():
            by[k.split('@')[0]] += v
        print('   lock waits by mutex (ms per frame): ' + '; '.join(f'{k} {v / n:.3f}' for k, v in sorted(by.items(), key=lambda x: -x[1])[:8]))
        print('   lock waits by site (ms per frame): ' + '; '.join(f'{k} {v / n:.3f}' for k, v in sorted(lk.items(), key=lambda x: -x[1])[:8]))
    if gu:
        print('   guest syncs (ms per frame): ' + '; '.join(f'{k} {v / n:.3f}' for k, v in sorted(gu.items(), key=lambda x: -x[1])))


def main():
    a = sys.argv[1:]
    lo, hi = float(a[0]), float(a[1])
    phases, rest = [], []
    for x in a[2:]:
        if '=' in x and not x.lower().endswith('.csv'):
            n, _, rng = x.partition('=')
            p0, _, p1 = rng.partition('-')
            phases.append((n, float(p0), float(p1)))
        else:
            rest.append(x)
    allr = []
    for p in rest:
        rows = load(p)
        per10 = defaultdict(int)
        for row in rows:
            per10[int(num(row['t_s']) // 10)] += 1
        print(f'{p}: {len(rows)} frames; frames per 10 s from t 0: ' + ' '.join(str(per10[i]) for i in range(0, max(per10) + 1 if per10 else 0)))
        for row in rows:
            t = num(row['t_s'])
            if lo <= t < hi:
                allr.append((t, split(row)))
    show('ALL', [x for _, x in allr])
    for c in ('1', '2', '3+'):
        show(f'{c} vblank', [x for _, x in allr if cls(x[0]['frame']) == c])
    for ph, p0, p1 in phases:
        if True:
            sub = [x for t, x in allr if p0 <= t < p1]
            show(f'{ph} phase [{p0:g}, {p1:g})', sub)
            for c in ('1', '2', '3+'):
                show(f'{ph} phase, {c} vblank', [x for x in sub if cls(x[0]['frame']) == c])


if __name__ == '__main__':
    main()
