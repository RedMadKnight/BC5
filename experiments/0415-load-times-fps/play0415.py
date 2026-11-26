#!/usr/bin/env python3
# BC5 exp 0415: the last N seconds of a run's counter file (the play stretch of a run that ended at G+60), the same
# stretch for every run, independent of the phase cutter: flips per second, and per cause the calls and the time.
# usage: play0415.py <N seconds> <loadstat file> [...] -- <cause> [...]
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
            r[k] = [int(q) for q in v.split(',')] if ',' in v else int(v) if v.isdigit() else v
        out.append(r)
    return out


def main():
    n = int(sys.argv[1])
    cut = sys.argv.index('--')
    files, causes = sys.argv[2:cut], sys.argv[cut + 1:]
    for f in files:
        r = rows(f)
        if len(r) < n + 2:
            print('%s: only %d lines' % (f, len(r)))
            continue
        a, b = r[-n - 1], r[-1]
        secs = (b['mono_ns'] - a['mono_ns']) / 1e9
        per = [r[i]['flip'][0] - r[i - 1]['flip'][0] for i in range(len(r) - n, len(r))]
        s = '%s: last %.0f s: %.1f flips/s (per second min %d, median %d)' % (f.replace('\\', '/').split('/')[-1], secs, (b['flip'][0] - a['flip'][0]) / secs, min(per), sorted(per)[len(per) // 2])
        for c in causes:
            if c in b:
                va = a.get(c, [0, 0, 0, 0])
                s += '; %s %d calls %.2f s' % (c, b[c][0] - va[0], (b[c][1] - va[1]) / 1e9)
            else:
                s += '; %s none' % c
        print(s)


if __name__ == '__main__':
    main()
