#!/usr/bin/env python3
# BC5 exp 0415: per run and phase, the device mutex and the mapping maintenance beside the kernel's own memory work,
# for the A/B of build L3's switches. One line per run and phase (P2 menu load, P5 save load, P6 play):
# phase seconds; flips/s; seconds under 15 flips; mutex held and waited; learned windows (time, full applications,
# windows that mapped something); anonymous sync; view list; mappings; device call; fast_diff; kcompactd0 and kswapd0
# CPU seconds; lowest available MiB. A value that is not there is "-".
# usage: hold0415.py <raw dir> <tag> [<tag> ...]
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phases0415 as P  # noqa: E402


def main():
    raw = sys.argv[1]
    print('run phase | s | flips/s | s<15 | held | waited | learned s (apps, changed) | anon | views | maps | dev call | fast_diff | kcompactd s | kswapd s | avail min')
    for tag in sys.argv[2:]:
        rows, marks = P.parse_stat(os.path.join(raw, tag + '-loadstat.txt'))
        t, fl, keys, b = P.cut(rows, marks)
        col = os.path.join(raw, tag + '-col.txt')
        if not os.path.exists(col) and os.path.exists(col + '.gz'):
            col += '.gz'
        crows, hz = P.col_rows(col)
        for name, short in (('P2 menu load', 'P2'), ('P5 save load', 'P5'), ('P6 play', 'P6')):
            i0, i1 = b[name]
            if i0 is None or i1 is None or i1 <= i0:
                print('%-6s %s | not reached' % (tag, short))
                continue

            def d(k, j=1):
                a, c = rows[i0]['c'].get(k), rows[i1]['c'].get(k)
                if a is None or c is None:
                    return None
                return (c[j] - a[j]) / (1e9 if j == 1 else 1)

            def f(x, fmt='%.1f'):
                return '-' if x is None else fmt % x
            dur = t[i1] - t[i0]
            flips = d('flip', 0)
            slow = sum(1 for i in range(i0 + 1, i1 + 1) if fl[i] < 15)
            c = P.col_delta(crows, hz, rows[i0]['mono_ns'] / 1e9, rows[i1]['mono_ns'] / 1e9) if crows else None
            c = c or {}
            print('%-6s %s | %.0f | %.1f | %d | %s | %s | %s (%s, %s) | %s | %s | %s | %s | %s | %s | %s | %s' % (
                tag, short, dur, flips / dur, slow, f(d('dev_hold')), f(d('dev_wait')), f(d('learned')), f(d('learned_apply', 0), '%d'), f(d('learned_changed', 0), '%d'),
                f(d('anon_sync')), f(d('ds_views')), f(d('ds_maps')), f(d('dev_call')), f(d('fast_diff', 0), '%d'),
                f(c.get('kcompactd0_s')), f(c.get('kswapd0_s')), f(c.get('avail_mib', (None, None))[1], '%.0f')))


if __name__ == '__main__':
    main()
