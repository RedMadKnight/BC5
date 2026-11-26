#!/usr/bin/env python3
# BC5 exp 0415: per arm, each run's: second at which 6.0 GiB of APR data had been read; second at which the start
# screen first ran at 30 flips/s for three seconds (the end of P2); their difference ("tail"); and the time from the
# Continue key to the first of three seconds with 20 flips or more. Seconds are counted from the first counter line.
# A value a run did not reach is "-". usage: sum0415.py <raw dir> <arm>=<tag>,<tag>... ...
import sys
import phases0415 as P


def row(raw, tag):
    rows, marks = P.parse_stat('%s/%s-loadstat.txt' % (raw, tag))
    t, fl, keys, b = P.cut(rows, marks)
    i2 = b['P2 menu load'][1]
    ab = [r['c'].get('apr_read', (0, 0, 0, 0))[3] for r in rows]
    t6 = next((t[i] for i in range(len(rows)) if ab[i] >= 6.0 * 2**30), None)
    play = None
    for i in range(1, len(rows) - 2):
        if len(keys) >= 3 and t[i] >= keys[2] + 3 and min(fl[i], fl[i + 1], fl[i + 2]) >= 20:
            play = t[i] - keys[2]
            break
    ready = t[i2] if i2 is not None else None
    return t6, ready, (ready - t6) if ready is not None and t6 is not None else None, play, keys[0] if keys else None


def main():
    raw = sys.argv[1]
    print('arm | 6 GiB read at, s | start screen runs at, s | tail, s | first key at, s | Continue to 20 flips/s, s')
    for spec in sys.argv[2:]:
        name, _, tags = spec.partition('=')
        rs = [row(raw, t) for t in tags.split(',')]

        def f(k, fmt):
            return ' '.join('-' if r[k] is None else fmt % r[k] for r in rs)
        print('%-18s | %s | %s | %s | %s | %s' % (name, f(0, '%.0f'), f(1, '%.0f'), f(2, '%.0f'), f(4, '%.1f'), f(3, '%.1f')))


main()
