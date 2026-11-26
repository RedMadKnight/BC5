#!/usr/bin/env python3
# BC5 experiment 0268: per GPU journal, how often the host's per-frame steps were long: the "prepare = filter X"
# part and the "sync", "hints" and "label waits" parts of each frame profile line. Read with O_DIRECT at a capped
# rate by exp 0214's reader. usage: filt0268.py <MB/s> <tag>=<journal> ...   (on the box, read-only)
import os, re, sys

sys.argv, args = sys.argv[:1] + ['0', '0'], sys.argv[1:]
sys.path.insert(0, os.path.expanduser('~/bc5-work/exp0214'))
import ra0214  # noqa: E402

PARTS = {k: re.compile(p) for k, p in (('filter', rb'prepare = filter ([0-9.]+)'), ('sync', rb'\(sync ([0-9.]+)'),
                                         ('hints', rb'hints ([0-9.]+)'), ('label waits', rb'label waits ([0-9.]+)'))}
rate = float(args[0])
for arg in args[1:]:
    tag, path = arg.split('=', 1)
    n = 0
    stats = {k: [0, 0, 0.0, 0.0] for k in PARTS}  # >50 ms, >100 ms, max, t of max
    for ln in ra0214.lines(path, rate):
        m = ra0214.FR.match(ln)
        if not m:
            continue
        n += 1
        t = float(m.group(1))
        for k, p in PARTS.items():
            g = p.search(ln)
            if g:
                v = float(g.group(1))
                s = stats[k]
                s[0] += v > 50
                s[1] += v > 100
                if v > s[2]:
                    s[2], s[3] = v, t
    print('%-5s %6d frames: ' % (tag, n) + '; '.join('%s >50 ms %d, >100 ms %d, max %.1f at t %.1f' % (k, *stats[k])
                                                    for k in PARTS))
    sys.stdout.flush()
