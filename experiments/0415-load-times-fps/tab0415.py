#!/usr/bin/env python3
# BC5 exp 0415: one line per run for a set of runs: the phases' lengths and the load phases' key counters.
# usage: tab0415.py <raw dir> <tag> [<tag> ...]
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phases0415 as P  # noqa: E402


def d(rows, i0, i1, k):
    a, b = rows[i0]['c'].get(k, (0, 0, 0, 0)), rows[i1]['c'].get(k, (0, 0, 0, 0))
    return b[0] - a[0], (b[1] - a[1]) / 1e9, b[3] - a[3]


def main():
    raw = sys.argv[1]
    print('run     | P2 menu load s | P5 save load s (reads quiet) | Continue to 20 flips/s, s | P6 flips/s | P2: apr busy s, reads, asked MiB, disk MiB, ms/read, queue wait ms | P5: the same | P2 dev hold/wait s | P5 dev hold/wait s | avail MiB lowest P2/P5 | rsync P2/P5')
    for tag in sys.argv[2:]:
        rows, marks = P.parse_stat(os.path.join(raw, tag + '-loadstat.txt'))
        t, fl, keys, b = P.cut(rows, marks)
        col = os.path.join(raw, tag + '-col.txt')
        if not os.path.exists(col) and os.path.exists(col + '.gz'):
            col += '.gz'
        crows, hz = P.col_rows(col)
        out = ['%-7s' % tag]
        cells = {}
        for name in ('P2 menu load', 'P5 save load', 'P6 play'):
            i0, i1 = b[name]
            if i0 is None or i1 is None or i1 <= i0:
                cells[name] = None
                continue
            dur = t[i1] - t[i0]
            c = P.col_delta(crows, hz, rows[i0]['mono_ns'] / 1e9, rows[i1]['mono_ns'] / 1e9) if crows else None
            nb, sb, _ = d(rows, i0, i1, 'apr_busy')
            nr, sr, br = d(rows, i0, i1, 'apr_read')
            nq, sq, _ = d(rows, i0, i1, 'apr_queue_wait')
            _, hold, _ = d(rows, i0, i1, 'dev_hold')
            _, wait, _ = d(rows, i0, i1, 'dev_wait')
            flips = rows[i1]['c']['flip'][0] - rows[i0]['c']['flip'][0]
            cells[name] = dict(dur=dur, fps=flips / dur, busy=sb, reads=nr, asked=br / 2**20, disk=(c or {}).get('read_disk_mib'), msr=1e3 * sr / nr if nr else 0,
                               qw=1e3 * sq / nq if nq else 0, hold=hold, wait=wait, avail=(c or {}).get('avail_mib', (None, None))[1], rsync=(c or {}).get('rsync'))

        def f(x, fmt='%.1f'):
            return 'n/a' if x is None else fmt % x
        p2, p5, p6 = cells['P2 menu load'], cells['P5 save load'], cells['P6 play']
        out.append(f(p2 and p2['dur']))
        out.append(f(p5 and p5['dur']))
        # "playable": from the Continue key to the first of three seconds with 20 flips or more, at least 3 s after the key
        play = None
        if len(keys) >= 3:
            for i in range(1, len(rows) - 2):
                if t[i] >= keys[2] + 3 and min(fl[i], fl[i + 1], fl[i + 2]) >= 20:
                    play = t[i] - keys[2]
                    break
        out.append(f(play))
        out.append(f(p6 and p6['fps']))
        for p in (p2, p5):
            out.append('not reached' if p is None else '%.1f, %d, %.0f, %s, %.2f, %.0f' % (p['busy'], p['reads'], p['asked'], f(p['disk'], '%.0f'), p['msr'], p['qw']))
        for p in (p2, p5):
            out.append('n/a' if p is None else '%.1f / %.1f' % (p['hold'], p['wait']))
        out.append('%s / %s' % (f(p2 and p2['avail'], '%.0f'), f(p5 and p5['avail'], '%.0f')))
        out.append('%s / %s' % (f(p2 and p2['rsync'], '%d'), f(p5 and p5['rsync'], '%d')))
        print(' | '.join(out))


main()
