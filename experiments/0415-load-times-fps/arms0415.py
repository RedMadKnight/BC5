#!/usr/bin/env python3
# BC5 exp 0415: one line per run for an A/B of launcher words, from the last N seconds of the run's counter file
# (KYTY_BC5_LOAD_STAT) and, when it is there, its frame file (KYTY_BC5_FRAME_STAT, an "f" line per flip):
#   flips per second; the time between flips (mean, median, 99th percentile, longest; how many over 50 and 100 ms);
#   label_wait: CPU-side label waits (count, total, the longest one);
#   wait_gave_up (build L6 on): waits that ended unserved (count, time waited, of which broken cycles);
#   any further cause named after "--" (calls, seconds).
# The longest label wait is the largest of the per-second maxima the counter file keeps.
# usage: arms0415.py <N seconds> <raw dir> <tag> [...] [-- <cause> ...]
import gzip
import os
import sys


def rows(path):
    out = []
    for line in open(path, encoding='utf-8', errors='replace'):
        p = line.split()
        if not p or p[0] != 's':
            continue
        r = {}
        for x in p[1:]:
            k, _, v = x.partition('=')
            try:
                r[k] = [int(q) for q in v.split(',')] if ',' in v else int(v)
            except ValueError:
                pass
        if 'mono_ns' in r and isinstance(r.get('flip'), list):
            out.append(r)
    return out


def flips(path):
    op = gzip.open if path.endswith('.gz') else open
    t = []
    with op(path, 'rt', encoding='utf-8', errors='replace') as f:
        for line in f:
            if line.startswith('f '):
                p = line.split()
                if len(p) == 4:
                    t.append(int(p[2]))
    return t


def pct(v, q):
    return v[min(len(v) - 1, int(len(v) * q))]


def one(n, raw, tag, causes):
    stat = os.path.join(raw, tag + '-loadstat.txt')
    if not os.path.exists(stat):
        return '%s: no counter file' % tag
    r = rows(stat)
    if len(r) < n + 2:
        return '%s: only %d second lines' % (tag, len(r))
    a, b, win = r[-n - 1], r[-1], r[-n:]
    secs = (b['mono_ns'] - a['mono_ns']) / 1e9
    s = '%s: last %.0f s: %.1f flips/s' % (tag, secs, (b['flip'][0] - a['flip'][0]) / secs)
    for fr in (os.path.join(raw, tag + '-frame.txt.gz'), os.path.join(raw, tag + '-frame.txt')):
        if os.path.exists(fr):
            t = [x for x in flips(fr) if a['mono_ns'] <= x <= b['mono_ns']]
            g = sorted((t[i] - t[i - 1]) / 1e6 for i in range(1, len(t)))
            if len(g) >= 10:
                s += '; between flips mean %.1f median %.1f p99 %.1f longest %.0f ms, %d of %d over 50 ms, %d over 100 ms' % (
                    sum(g) / len(g), pct(g, 0.5), pct(g, 0.99), g[-1], sum(1 for x in g if x > 50), len(g), sum(1 for x in g if x > 100))
            break
    else:
        s += '; no frame file'

    def d(c, i):
        return b[c][i] - a.get(c, [0, 0, 0, 0])[i] if c in b else None

    if 'label_wait' in b:
        s += '; label waits %d, %.0f ms in all, longest %.1f ms' % (d('label_wait', 0), d('label_wait', 1) / 1e6, max(x['label_wait'][2] for x in win if 'label_wait' in x) / 1e6)
    if 'wait_gave_up' in b:
        s += '; unserved waits %d (%.0f ms waited, %d broken cycles)' % (d('wait_gave_up', 0), d('wait_gave_up', 1) / 1e6, d('wait_gave_up', 3))
    else:
        s += '; no wait_gave_up counter in this build'
    for c in causes:
        s += '; %s %d calls %.2f s items %d' % (c, d(c, 0), d(c, 1) / 1e9, d(c, 3)) if c in b else '; %s none' % c
    return s


def main():
    n, raw = int(sys.argv[1]), sys.argv[2]
    rest = sys.argv[3:]
    causes = []
    if '--' in rest:
        cut = rest.index('--')
        rest, causes = rest[:cut], rest[cut + 1:]
    for tag in rest:
        print(one(n, raw, tag, causes))


if __name__ == '__main__':
    main()
