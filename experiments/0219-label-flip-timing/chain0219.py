#!/usr/bin/env python3
# BC5 experiment 0219: for each given-up game-thread wait on label B, the compute side around it, from the extract.
# - the last acb held back (wait trace) on A = B - 0x70 in the 50 ms before the give-up (the pairing seen in the
#   wait trace: the acb that clears B first waits on A);
# - the jobs completed between the give-up and 5 ms after the flip (number, kind, size, time relative to the flip);
# - the lowest-numbered dcb job completed after the give-up against the acb that completed just before the flip:
#   job numbers are taken at submission, so an acb numbered below that dcb was submitted before the frame's dcb.
# usage: chain0219.py <extract>
import re, sys

HB = re.compile(r'^wait trace: t ([0-9.]+) s acb (\d+) dwords at (0x[0-9a-f]+) \(queue (\d+)\) held back by its wait at (\d+) \(ring (-?\d+)\) on (0x[0-9a-f]+): function \d reference (0x[0-9a-f]+) value (0x[0-9a-f]+)')
GIVE = re.compile(r'^flip trace: #(\d+) given up: dcb (\d+) dwords at (\d+) on (0x[0-9a-f]+) .* t ([0-9.]+) s;')
END = re.compile(r'^flip trace: #(\d+) (0x[0-9a-f]+) satisfied ([0-9.]+) ms after the give-up .* t ([0-9.]+) s;')
JOB = re.compile(r'^flip trace: job #(\d+) (\S+) (\d+) dwords done at t ([0-9.]+) s \(cq(\d)\)')

hb, gives, ends, jobs = [], {}, {}, []
for line in open(sys.argv[1], errors='replace'):
    m = HB.match(line)
    if m:
        hb.append((float(m.group(1)), int(m.group(2)), m.group(3), int(m.group(5)), m.group(7), m.group(9)))
        continue
    m = GIVE.match(line)
    if m:
        gives[m.group(1)] = (float(m.group(5)), int(m.group(2)), int(m.group(3)), m.group(4))
        continue
    m = END.match(line)
    if m:
        ends[m.group(1)] = (float(m.group(4)), float(m.group(3)))
        continue
    m = JOB.match(line)
    if m:
        jobs.append((float(m.group(4)), int(m.group(1)), m.group(2), int(m.group(3)), int(m.group(5))))

for gid in sorted(gives, key=lambda k: gives[k][0]):
    tg, dw, at, B = gives[gid]
    if gid not in ends:
        print('#%s give-up t %.4f on %s: no flip' % (gid, tg, B))
        continue
    tf, after = ends[gid]
    A = '0x%x' % (int(B, 16) - 0x70)
    held = [h for h in hb if h[4] == A and tg - 0.05 <= h[0] <= tg + 0.001]
    hs = ('acb %d dwords at %s held back on A at t %.3f (its wait at %d, value %s)' % (held[-1][1], held[-1][2], held[-1][0], held[-1][3], held[-1][5])
          if held else 'no acb seen held back on A in the 50 ms before')
    print('#%s give-up t %.4f: dcb %d dwords at %d on B %s; flip %.3f ms later; A = %s: %s' % (gid, tg, dw, at, B, after, A, hs))
    win = [j for j in jobs if tg <= j[0] <= tf + 0.005]
    before = [j for j in win if j[0] <= tf]
    dcbs = [j[1] for j in jobs if j[0] >= tg and j[2] == 'dcb']
    first_dcb = min(dcbs[:20]) if dcbs else None
    print('    jobs done: ' + ', '.join('#%d %s %d @%+.3f ms cq%d' % (j[1], j[2], j[3], (j[0] - tf) * 1000.0, j[4]) for j in win[:10]))
    if before:
        w = before[-1]
        print('    last completion before the flip: #%d %s (%+.3f ms); lowest dcb number completed after the give-up: %s -> %s'
              % (w[1], w[2], (w[0] - tf) * 1000.0, first_dcb, 'the writer ran before the next dcb was submitted' if first_dcb and w[1] < first_dcb else '-'))
