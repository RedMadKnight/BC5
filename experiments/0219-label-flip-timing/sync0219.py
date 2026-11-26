#!/usr/bin/env python3
# BC5 experiment 0219: every job that finished between a give-up and its label's flip, synchronous ones included.
# The flip trace counts and journals only the jobs of the completion queues (cq0, cq1); a submission the calling
# thread finishes inline (r.pending false) is journaled only as "timing: #N done at t ..." (BC5_DIRECT_TIMING,
# ms resolution). This lists, per give-up, the "timing: #N done" lines from 1 ms before the give-up to 1 ms after
# the flip, marking each N that is also a queued job ("flip trace: job #N") and each that is not (inline).
# usage: sync0219.py <flip-trace lines> <timing lines>
import re, sys

GIVE = re.compile(r'^flip trace: #(\d+) given up: dcb (\d+) dwords at (\d+) on (0x[0-9a-f]+) .* t ([0-9.]+) s;')
END = re.compile(r'^flip trace: #(\d+) (0x[0-9a-f]+) satisfied ([0-9.]+) ms after the give-up .* t ([0-9.]+) s;')
JOB = re.compile(r'^flip trace: job #(\d+) (\S+) (\d+) dwords done at t ([0-9.]+) s \(cq(\d)\)')
TIM = re.compile(r'^timing: #(\d+) done at t ([0-9.]+) s, ([0-9.]+) ms after the sync and hints; device: prepare ([0-9.]+) list ([0-9.]+) cs ([0-9.]+) fence ([0-9.]+) ms')

gives, ends, queued = {}, {}, {}
for line in open(sys.argv[1], errors='replace'):
    m = GIVE.match(line)
    if m:
        gives[m.group(1)] = (float(m.group(5)), m.group(4))
        continue
    m = END.match(line)
    if m:
        ends[m.group(1)] = float(m.group(4))
        continue
    m = JOB.match(line)
    if m:
        queued[int(m.group(1))] = (m.group(2), int(m.group(3)), int(m.group(5)))
wins = [(gives[g][0] - 0.001, ends[g] + 0.001, g) for g in gives if g in ends]
hits = {g: [] for _, _, g in wins}
for line in open(sys.argv[2], errors='replace'):
    m = TIM.match(line)
    if not m:
        continue
    t = float(m.group(2))
    for a, b, g in wins:
        if a <= t <= b:
            hits[g].append((t, int(m.group(1)), float(m.group(7))))
inline_total = 0
for a, b, g in sorted(wins):
    tg, B = gives[g]
    rows = sorted(hits[g])
    inline = [r for r in rows if r[1] not in queued]
    inline_total += len(inline)
    print('#%s give-up t %.4f on %s, flip t %.4f: %d jobs done in [give-up - 1 ms, flip + 1 ms], %d of them inline (not queued)' % (g, tg, B, ends[g], len(rows), len(inline)))
    for t, n, fence in rows:
        q = queued.get(n)
        print('    #%d done t %.3f  %s  fence %.2f ms' % (n, t, ('queued: %s %d dwords cq%d' % q) if q else 'INLINE (finished by the submitting thread)', fence))
print('# %d inline jobs in all the windows' % inline_total)
