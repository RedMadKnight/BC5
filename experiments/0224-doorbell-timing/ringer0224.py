#!/usr/bin/env python3
# BC5 experiment 0224: is the thread that waits the one that rings the doorbells? For each given-up game-thread wait,
# the doorbell writes (any queue, from the "doorbell trace:" lines) in three stretches relative to the give-up:
# before the wait began (from -50 ms), during the wait ([-waited, 0]) and in the 2 ms after the give-up. If the
# waiting thread rings them, none fall inside the wait and the first comes soon after the give-up.
# usage: ringer0224.py <extract>
import re, sys
from collections import defaultdict

GIVE = re.compile(r'^flip trace: #(\d+) given up: \S+ \d+ dwords at \d+ on (0x[0-9a-f]+) \(game thread \d\) after ([0-9.]+) ms, t ([0-9.]+) s;')
DBW = re.compile(r'^doorbell trace: #(\d+) queue (\d+) write pointer \d+ -> \d+ at t [0-9.]+ s \(([+-][0-9.]+) ms from the give-up\)')

waited, label, writes = {}, {}, defaultdict(list)
for line in open(sys.argv[1], errors='replace'):
    m = GIVE.match(line)
    if m:
        waited[m.group(1)] = float(m.group(3))
        label[m.group(1)] = (m.group(2), float(m.group(4)))
        continue
    m = DBW.match(line)
    if m:
        writes[m.group(1)].append(float(m.group(3)))
tot_before = tot_during = tot_after = 0
span_before = span_during = 0.0
print('#id  t(s)     label          waited  writes: before the wait (rate /ms)  during the wait  first after the give-up')
for gid in sorted(waited, key=lambda k: label[k][1]):
    w = waited[gid]
    ws = sorted(writes[gid])
    before = [x for x in ws if -50.0 <= x < -w]
    during = [x for x in ws if -w <= x <= 0.0]
    after = [x for x in ws if 0.0 < x]
    tot_before += len(before)
    tot_during += len(during)
    span_before += max(50.0 - w, 0.0)
    span_during += w
    print('%-4s %8.3f %-14s %6.2f  %4d (%.2f)                       %4d             %s' % (
        gid, label[gid][1], label[gid][0], w, len(before), len(before) / max(50.0 - w, 1e-9), len(during), '+%.3f ms' % after[0] if after else '-'))
print('# all give-ups: %d doorbell writes in %.0f ms before the waits (%.3f /ms), %d in %.0f ms during them (%.3f /ms)' % (
    tot_before, span_before, tot_before / max(span_before, 1e-9), tot_during, span_during, tot_during / max(span_during, 1e-9)))
