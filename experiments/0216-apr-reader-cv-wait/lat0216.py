#!/usr/bin/env python3
# BC5 experiment 0216: from a run's APR journal (the "apr journal (exp 0203)" lines of play-pkg.log, the clock voice's
# archive with KYTY_BC5_APR_FILE_JOURNAL=7cd713df): per priority queue, the time from each submit to its finish
# (count, median, 95th percentile, max), and how many of the queue's buffers were read ahead. Times are the journal's
# monotonic stamps (ms resolution). usage: lat0216.py <label>=<apr-journal.txt> ...
import re, sys

LN = re.compile(r'mono ([0-9.]+) (submit|finish|readahead) cb (0x[0-9a-f]+)(?: prio (\d+))?')


def pct(v, p):
    return v[min(len(v) - 1, int(p * len(v)))]


for arg in sys.argv[1:]:
    label, path = arg.split('=', 1)
    open_ = {}  # cb -> (submit time, queue)
    lat = {}
    ra = {}
    fin = {}
    for line in open(path, encoding='latin-1'):
        m = LN.search(line)
        if not m:
            continue
        t, kind, cb = float(m.group(1)), m.group(2), m.group(3)
        if kind == 'submit':
            q = int(m.group(4))
            open_[cb] = (t, q)
        elif kind == 'readahead' and cb in open_:
            ra[open_[cb][1]] = ra.get(open_[cb][1], 0) + 1
        elif kind == 'finish' and cb in open_:
            t0, q = open_.pop(cb)
            lat.setdefault(q, []).append(t - t0)
            fin[q] = fin.get(q, 0) + 1
    print(f'== {label}: {path}')
    for q in sorted(lat):
        v = sorted(lat[q])
        print(f'   prio {q}: {len(v):4d} finished, submit->finish median {1e3 * pct(v, .5):7.1f} ms, '
              f'p95 {1e3 * pct(v, .95):7.1f} ms, max {1e3 * v[-1]:7.1f} ms; read-ahead lines {ra.get(q, 0)}')
    if open_:
        print(f'   not finished in the journal: {len(open_)}')
