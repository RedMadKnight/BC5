#!/usr/bin/env python3
# BC5 exp 0439 (tag vz439k, step 4): the third title's two pacing states in MangoHud's per-frame log. Per run: the
# share of frames near 33 ms (25-45), near 66 ms (55-80) and other, overall from FROM s and per 10-s window (a run that
# switches state shows it as a change of the window shares).
#   pace439.py [--from S] <csv> [<csv> ...]
import sys

args = sys.argv[1:]
t_from = 30.0
if args[:1] == ['--from']:
    t_from = float(args[1])
    args = args[2:]
for f in args:
    hdr = None
    rows = []
    for line in open(f, errors='replace'):
        c = line.rstrip('\n').split(',')
        if hdr is None:
            if c and c[0] == 'fps':
                hdr = {k: i for i, k in enumerate(c)}
            continue
        try:
            rows.append((float(c[hdr['elapsed']]) / 1e9, float(c[hdr['frametime']])))
        except (ValueError, IndexError, KeyError):
            pass
    rows = [r for r in rows if r[0] >= t_from]
    if not rows:
        print(f, 'no frames')
        continue

    def share(rs):
        a = sum(1 for _, v in rs if 25 <= v <= 45)
        b = sum(1 for _, v in rs if 55 <= v <= 80)
        return a, b, len(rs) - a - b

    a, b, o = share(rows)
    w = {}
    for t, v in rows:
        w.setdefault(int(t // 10) * 10, []).append((t, v))
    win = ' '.join('%d:%s' % (k, 'F' if share(r)[0] > 0.7 * len(r) else ('S' if share(r)[1] > 0.7 * len(r) else 'M')) for k, r in sorted(w.items()))
    print('%s: from %.0f s: %d frames: 33-ms %d (%.0f %%), 66-ms %d (%.0f %%), other %d; windows (F 33-ms, S 66-ms, M mixed): %s'
          % (f, t_from, len(rows), a, 100.0 * a / len(rows), b, 100.0 * b / len(rows), o, win))
