#!/usr/bin/env python3
# exp 0165 follow-up: the audio pacing of a run from KYTY_BC5_AUDIO_TRACE=1 lines in the stderr log
# ("audio trace: t T s port P ...: N calls, F frames = S s of sound in W s (rate R), held H ms, C clears,
# sdl queued A-B bytes (X-Y ms), ..."), per port, over t0..t1: the rate's mean/min/max, the seconds
# outside 0.97..1.03, the held time, the clears, the SDL queue depth.
# Usage: audio.py <stderr log> <t0> <t1>
import re, sys, collections, statistics

log, t0, t1 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
rx = re.compile(r"audio trace: t ([0-9.]+) s port (\d+) .*?\(rate ([0-9.]+)\), held ([0-9.]+) ms, (\d+) clears, sdl queued (\d+)-(\d+) bytes \((\d+)-(\d+) ms\)")
per = collections.defaultdict(list)
for line in open(log, encoding="latin1"):
    m = rx.search(line)
    if not m:
        continue
    t = float(m.group(1))
    if t0 <= t < t1:
        per[int(m.group(2))].append((t, float(m.group(3)), float(m.group(4)), int(m.group(5)), int(m.group(8)), int(m.group(9))))
print("window t %.0f-%.0f s" % (t0, t1))
for port in sorted(per):
    rows = per[port]
    rates = [r[1] for r in rows]
    held = [r[2] for r in rows]
    clears = sum(r[3] for r in rows)
    off = [r for r in rows if r[1] > 1.03 or r[1] < 0.97]
    qmin = min(r[4] for r in rows)
    qmax = max(r[5] for r in rows)
    print("port %d: %d lines; rate mean %.3f median %.3f min %.3f max %.3f; outside 0.97-1.03: %d (%s); held mean %.0f ms median %.0f min %.0f max %.0f; clears %d; sdl queue %d-%d ms" % (
        port, len(rows), statistics.mean(rates), statistics.median(rates), min(rates), max(rates), len(off),
        " ".join("t%.0f:%.3f" % (r[0], r[1]) for r in off[:12]), statistics.mean(held), statistics.median(held), min(held), max(held), clears, qmin, qmax))
