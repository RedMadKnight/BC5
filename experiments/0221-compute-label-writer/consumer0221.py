#!/usr/bin/env python3
# BC5 experiment 0221: what the doorbell consumer was doing between a give-up and its label's flip. Its CPU waits on
# compute buffers (acb, 2-s limit) end with "timing: t X s after that wait (acb N dwords)" (BC5_DIRECT_TIMING, ms
# resolution). For each give-up [t_give, t_flip] this lists the consumer's wait ends from 50 ms before the give-up to
# 2 ms after the flip, and the gap from the last one at or before the flip to the flip. If the label's writer is a
# compute buffer the consumer could only submit once its own wait on another buffer ended, the flips follow such ends.
# Also: the game thread's own waits that ended in the window ("after that wait (dcb ...)").
# usage: consumer0221.py <extract with flip trace + timing lines>
import bisect, re, sys

GIVE = re.compile(r'^flip trace: #(\d+) given up: \S+ (\d+) dwords at (\d+) on (0x[0-9a-f]+) .* t ([0-9.]+) s;')
END = re.compile(r'^flip trace: #(\d+) (0x[0-9a-f]+) satisfied ([0-9.]+) ms after the give-up .* t ([0-9.]+) s;')
AW = re.compile(r'^timing: t ([0-9.]+) s after that wait \((acb|dcb) (\d+) dwords\)')

gives, ends, acb, dcb = {}, {}, [], []
for line in open(sys.argv[1], errors='replace'):
    m = AW.match(line)
    if m:
        (acb if m.group(2) == 'acb' else dcb).append((float(m.group(1)), int(m.group(3))))
        continue
    m = GIVE.match(line)
    if m:
        gives[m.group(1)] = (float(m.group(5)), m.group(4))
        continue
    m = END.match(line)
    if m:
        ends[m.group(1)] = float(m.group(4))
acb.sort()
at = [a[0] for a in acb]
gaps = []
for g in sorted(gives, key=lambda k: gives[k][0]):
    if g not in ends:
        continue
    tg, B = gives[g]
    tf = ends[g]
    i0, i1 = bisect.bisect_left(at, tg - 0.050), bisect.bisect_right(at, tf + 0.002)
    win = acb[i0:i1]
    inside = [a for a in win if tg <= a[0] <= tf + 0.0005]
    last = [a for a in win if a[0] <= tf + 0.0005]
    gap = (tf - last[-1][0]) * 1000.0 if last else None
    if inside:
        gaps.append(gap)
    print('#%s give-up %.4f on %s, flip %.4f (+%.1f ms): consumer wait ends %s; %d inside [give-up, flip]; last before the flip %s'
          % (g, tg, B, tf, (tf - tg) * 1000.0, ' '.join('%+.1f(acb %d)' % ((a[0] - tg) * 1000.0, a[1]) for a in win) or '-', len(inside),
             '%.1f ms before it' % gap if gap is not None else '-'))
print('# give-ups with a consumer wait ending between the give-up and the flip: %d of %d; gap from that end to the flip (ms, ms resolution): %s'
      % (len(gaps), len([g for g in gives if g in ends]), sorted(round(x, 1) for x in gaps)))
