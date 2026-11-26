#!/usr/bin/env python3
# Experiment 0209 (TCP session): how long the game thread's label waits take, from the tcpW extracts.
#
# What the journal holds (patch 0001):
#   "wait trace: t T1 s dcb N dwords at I (ring -1) on LABEL: ..." - a graphics-buffer wait found
#     unsatisfied on the game thread (BC5_DIRECT_WAIT_TRACE; capped at 20,000 lines a run);
#   "timing: t T2 s after that wait (dcb N dwords)" - printed when the CPU-side wait block ends, for
#     every wait that reaches it, also for waits satisfied at once (those are never traced);
#   "cpu-wait ... GIVEN UP after X ms" - a give-up.
# The game thread handles one wait at a time. So a traced wait's own "after that wait" line, if it has
# one, comes before the game thread's next traced wait: duration T2 - T1. A traced wait without such
# a line ended inside the two-ring window (served within the 4 ms of BC5_DIRECT_TWO_RING_WAIT_MS, or
# kept for the GPU): duration < ~4 ms. Compute-queue trace lines ("held back") are another thread and
# are left out. Only the time the trace covers (until its cap) is counted.
# usage: ana0209.py <extract> [label-of-interest]
import re, sys
from collections import defaultdict

WT = re.compile(r'^wait trace: t ([0-9.]+) s dcb (\d+) dwords at (\d+) \(ring (-?\d+)\) on (0x[0-9a-f]+): function (\d) reference (0x[0-9a-f]+) value (0x[0-9a-f]+); (.*)$')
AW = re.compile(r'^timing: t ([0-9.]+) s after that wait \(dcb (\d+) dwords\)')
GU = re.compile(r'^cpu-wait \S+ at (\d+) on (0x[0-9a-f]+): GIVEN UP after ([0-9.]+) ms')
FP = re.compile(r'^frame profile: t ([0-9.]+) s, ([0-9.]+) ms since the last flip; game thread inside the host ([0-9.]+) ms .*?label waits ([0-9.]+)[^)]*\).*?outside ([0-9.]+); GPU busy ([0-9.]+) ms')

def pct(xs, p):
    if not xs: return float('nan')
    xs = sorted(xs); k = min(len(xs) - 1, max(0, int(round(p / 100.0 * (len(xs) - 1)))))
    return xs[k]

def main():
    path = sys.argv[1]
    focus = sys.argv[2] if len(sys.argv) > 2 else '0x12004b3c38'
    cur = None                          # the latest traced dcb wait: [t1, N, label, closed]
    short = defaultdict(int)            # label -> waits that ended inside the two-ring window
    durs = defaultdict(list)            # label -> durations (ms) of waits that reached the CPU-wait block
    events = []                         # (t1, label, ms, gave_up)
    gave_up = defaultdict(int)
    frames = []
    last_trace = 0.0
    pending_giveup = None

    def close_short():
        nonlocal cur
        if cur is not None and not cur[3]:
            short[cur[2]] += 1
        cur = None

    for line in open(path, errors='replace'):
        m = WT.match(line)
        if m:
            close_short()
            cur = [float(m.group(1)), int(m.group(2)), m.group(5), False]
            last_trace = cur[0]
            continue
        m = GU.match(line)
        if m:
            pending_giveup = m.group(2)
            continue
        m = AW.match(line)
        if m:
            t2, n = float(m.group(1)), int(m.group(2))
            gu = pending_giveup is not None
            if gu and t2 > last_trace + 0.5: pending_giveup = None   # beyond the trace's cover
            if cur is not None and not cur[3] and n == cur[1] and t2 >= cur[0]:
                ms = (t2 - cur[0]) * 1000.0
                durs[cur[2]].append(ms)
                if gu and pending_giveup == cur[2]: gave_up[cur[2]] += 1
                events.append((cur[0], cur[2], ms, gu))
                cur[3] = True
            pending_giveup = None
            continue
        m = FP.match(line)
        if m:
            frames.append(tuple(float(m.group(i)) for i in range(1, 7)))
    close_short()

    labels = sorted(set(short) | set(durs), key=lambda l: -(short[l] + len(durs[l])))
    print('file %s: the wait trace covers t <= %.1f s' % (path.split('/')[-1], last_trace))
    print('%-14s %7s %8s %7s %6s %6s %6s %6s %6s %8s %6s' % ('label', 'waits', '<4ms', 'longer', 'p50', 'p90', 'p99', 'p99.9', 'max', '8-100ms', 'gaveup'))
    for l in labels[:9] + ([focus] if focus not in labels[:9] and focus in labels else []):
        d = durs.get(l, [])
        tot = short[l] + len(d)
        mid = sum(1 for x in d if 8.5 < x <= 100.5)
        print('%-14s %7d %8d %7d %6.0f %6.0f %6.0f %6.0f %6.0f %8d %6d' % (l, tot, short[l], len(d), pct(d, 50), pct(d, 90), pct(d, 99), pct(d, 99.9),
              max(d) if d else float('nan'), mid, gave_up.get(l, 0)))
    alld = [x for v in durs.values() for x in v]
    nall = sum(short.values()) + len(alld)
    print('all labels: %d waits, %d under 4 ms, %d longer (p50 %.0f, p90 %.0f, p99 %.0f, max %.0f ms)' % (
        nall, sum(short.values()), len(alld), pct(alld, 50), pct(alld, 90), pct(alld, 99), max(alld) if alld else float('nan')))
    # All waits over 8 ms, with the frame they end in.
    print('waits over 8 ms (t, label, ms, given up?) with their frame: since last flip / inside host / label waits / outside / GPU busy (ms)')
    fi = 0
    for (t1, label, ms, gu) in sorted(events):
        if ms <= 8.5: continue
        while fi < len(frames) and frames[fi][0] < t1 + ms / 1000.0: fi += 1
        f = frames[fi] if fi < len(frames) else None
        fs = ('%.0f / %.0f / %.0f / %.0f / %.0f' % (f[1], f[2], f[3], f[4], f[5])) if f else '-'
        print('  t %8.3f s  %-14s %6.0f ms %-9s frame %s' % (t1, label, ms, 'GIVEN UP' if gu else '', fs))

main()
