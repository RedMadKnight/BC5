#!/usr/bin/env python3
# BC5 experiment 0291: GPU time and frame rate of a run, from its GPU journal (gc/direct.log) read with O_DIRECT at a
# capped rate by exp 0214's reader: flips a second, the mean and median GPU-busy ms per frame, the mean ms between
# flips and the frames over 100/250 ms, for the whole run and for t >= <skip> s.
# usage: gpu0291.py <MB/s> <skip s> <tag>=<journal> ...   (on the box, read-only)
import os, sys

sys.argv, args = sys.argv[:1] + ['0', '0'], sys.argv[1:]  # ra0214.py's main() then has nothing to do
sys.path.insert(0, os.path.expanduser('~/bc5-work/exp0214'))
import ra0214  # noqa: E402


def score(fr):
    if len(fr) < 2:
        return 'no frames'
    dur = fr[-1][0] - fr[0][0]
    gpu = sorted(f[2] for f in fr)
    ms = [f[1] for f in fr]
    return ('%6d flips in %6.1f s = %5.1f/s; GPU busy per frame mean %5.1f ms, median %5.1f ms; between flips mean %5.1f ms; '
            '>100 ms %d, >250 ms %d' % (len(fr), dur, len(fr) / dur, sum(gpu) / len(gpu), gpu[len(gpu) // 2],
                                         sum(ms) / len(ms), sum(m > 100 for m in ms), sum(m > 250 for m in ms)))


rate, skip = float(args[0]), float(args[1])
for arg in args[2:]:
    tag, path = arg.split('=', 1)
    fr = []
    for ln in ra0214.lines(path, rate):
        m = ra0214.FR.match(ln)
        if m:
            fr.append((float(m.group(1)), float(m.group(2)), float(m.group(3))))
    print('%-4s all      : %s' % (tag, score(fr)))
    print('%-4s t >= %3.0f : %s' % (tag, skip, score([f for f in fr if f[0] >= skip])))
    sys.stdout.flush()
