#!/usr/bin/env python3
# BC5 exp 0439 (tag vz439k): MangoHud's per-frame log (csv: a header line starting "fps," with frametime in ms and
# elapsed in ns) in numbers, from FROM s of its own clock (default 60: the save's load is over): frames, flips/s, frame
# time median / p95 / p99 / max, frames over 50 ms.
#   mhstat439.py [--from S] <csv> [<csv> ...]
import sys

args = sys.argv[1:]
t_from = 60.0
if args[:1] == ['--from']:
    t_from = float(args[1])
    args = args[2:]
for f in args:
    ft = []
    ts = []
    hdr = None
    for line in open(f, errors='replace'):
        c = line.rstrip('\n').split(',')
        if hdr is None:
            if c and c[0] == 'fps':
                hdr = {k: i for i, k in enumerate(c)}
            continue
        try:
            t = float(c[hdr['elapsed']]) / 1e9
            v = float(c[hdr['frametime']])
        except (ValueError, IndexError, KeyError):
            continue
        if t < t_from:
            continue
        ts.append(t)
        ft.append(v)
    if len(ft) < 2:
        print(f, 'too few frames')
        continue
    s = sorted(ft)
    q = lambda p: s[min(len(s) - 1, int(len(s) * p))]
    print('%s: frames %d in %.1f s, flips/s %.2f, frame time median %.2f p95 %.2f p99 %.2f max %.1f ms, over 50 ms %d'
          % (f, len(ft), ts[-1] - ts[0], (len(ft) - 1) / (ts[-1] - ts[0]), q(0.5), q(0.95), q(0.99), s[-1], sum(1 for v in ft if v > 50)))
