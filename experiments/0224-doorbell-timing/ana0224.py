#!/usr/bin/env python3
# BC5 experiment 0224: for each given-up game-thread wait, when the title rang each queue's doorbell and when the ring
# consumer took and submitted those entries, against the give-up and the flip of the waited label B. Reads the run's
# extract (run0224.sh extract): "flip trace:" (exp 0221 v3), "doorbell trace:" and "ts trace:" lines (patch_0224.diff),
# and the "queue N: a .. ring 0x..-0x.." registration lines (for each ring's size and whether it is compute, a == 2).
# Per give-up it pairs each consumer take (queue q, read pointer r) with the doorbell write that made entry r pending
# (the write with r in [old, new) modulo the ring size). Then:
#   the last take before the flip, on any queue, is taken as the likely writer's submission. Its doorbell came before
#   the give-up and was taken after it: the consumer was late. The doorbell itself came after the give-up: the title
#   rang late. No matching doorbell write in the window (50 ms before the give-up onwards): rung more than 50 ms
#   before, so the consumer was late.
# Also every "ts trace:" line (a timestamp rewrite on a wait label).
# usage: ana0224.py <extract>
import re, sys
from collections import Counter, defaultdict

QREG = re.compile(r'^queue (\d+): a (\d+) b (\d+) c (\d+) d (\d+) ring (0x[0-9a-f]+)-(0x[0-9a-f]+)')
GIVE = re.compile(r'^flip trace: #(\d+) given up: \S+ (\d+) dwords at (\d+) on (0x[0-9a-f]+) .* t ([0-9.]+) s; value (0x[0-9a-f]+); in flight cq0 (-?\d+) cq1 (-?\d+)')
CHG = re.compile(r'^flip trace: #(\d+) (0x[0-9a-f]+): (0x[0-9a-f]+) -> (0x[0-9a-f]+) at t ([0-9.]+) s, ([0-9.]+) ms after the give-up')
END = re.compile(r'^flip trace: #(\d+) (0x[0-9a-f]+) (satisfied|NOT satisfied within 2 s) ([0-9.]+) ms after the give-up')
DB = re.compile(r'^doorbell trace: #(\d+) queue (\d+) (write pointer (\d+) -> (\d+)|consumer takes (\d+) dwords at (\d+)|consumer\'s submit of (\d+) dwords at (\d+) returned|deferred, (\d+) dwords pending at (\d+)), at t ([0-9.]+) s \(([+-][0-9.]+) ms from the give-up\)')
DB2 = re.compile(r'^doorbell trace: #(\d+) queue (\d+) (write pointer (\d+) -> (\d+)|consumer takes (\d+) dwords at (\d+)|consumer\'s submit of (\d+) dwords at (\d+) returned) at t ([0-9.]+) s \(([+-][0-9.]+) ms from the give-up\)')
TS = re.compile(r'^ts trace: (.*)$')

qs = {}
g = defaultdict(lambda: dict(ev=[]))
ts = []
for line in open(sys.argv[1], errors='replace'):
    m = QREG.match(line)
    if m:
        qs[int(m.group(1))] = dict(a=int(m.group(2)), n=(int(m.group(7), 16) - int(m.group(6), 16)) // 4)
        continue
    if line.startswith('ts trace: '):
        ts.append(line.rstrip())
        continue
    m = GIVE.match(line)
    if m:
        g[m.group(1)].update(t=float(m.group(5)), label=m.group(4), q=(int(m.group(7)), int(m.group(8))))
        continue
    m = CHG.match(line)
    if m:
        g[m.group(1)].setdefault('flip', float(m.group(6)))
        continue
    m = END.match(line)
    if m:
        d = g[m.group(1)]
        d['sat'] = m.group(3) == 'satisfied'
        d.setdefault('flip', float(m.group(4)) if d['sat'] else None)
        continue
    m = DB.match(line) or DB2.match(line)
    if m:
        gid, q, rel = m.group(1), int(m.group(2)), float(m.groups()[-1])
        if m.group(4) is not None:
            g[gid]['ev'].append((rel, q, 'write', int(m.group(4)), int(m.group(5))))
        elif m.group(6) is not None:
            g[gid]['ev'].append((rel, q, 'take', int(m.group(7)), int(m.group(6))))
        elif m.group(8) is not None:
            g[gid]['ev'].append((rel, q, 'done', int(m.group(9)), int(m.group(8))))
        else:
            g[gid]['ev'].append((rel, q, 'deferred', int(m.group(11)) if m.lastindex >= 11 and m.group(11) else 0, int(m.group(10)) if m.group(10) else 0))

def posted_by(writes, r, n, t_take):
    """The doorbell write (rel, old, new) before t_take that made entry r pending: r in [old, new) modulo n."""
    best = None
    for (rel, old, new) in writes:
        if rel > t_take or n <= 0:
            continue
        o, w = old % n, new % n
        if (r - o) % n < (w - o) % n:
            best = (rel, old, new)
    return best

verdicts = Counter()
print('# queues: %s' % ', '.join('%d (%s, %d dwords)' % (k, 'compute' if v['a'] == 2 else 'a=%d' % v['a'], v['n']) for k, v in sorted(qs.items())))
for gid in sorted((k for k in g if 't' in g[k]), key=lambda k: g[k]['t']):
    d = g[gid]
    flip = d.get('flip')
    ev = sorted(d['ev'])
    writes = defaultdict(list)
    for e in ev:
        if e[2] == 'write':
            writes[e[1]].append((e[0], e[3], e[4]))
    print('#%s t %.3f %s; in flight at the give-up cq0 %d cq1 %d; B flips %s; %d doorbell events' % (
        gid, d['t'], d['label'], d['q'][0], d['q'][1], '+%.3f ms' % flip if flip is not None else 'never', len(ev)))
    takes = [e for e in ev if e[2] == 'take' and (flip is None or e[0] <= flip)]
    for e in takes:
        rel, q, _, r, take = e
        n = qs.get(q, {}).get('n', 0)
        p = posted_by(writes[q], r, n, rel)
        done = next((x[0] for x in ev if x[2] == 'done' and x[1] == q and x[3] == r and x[0] >= rel), None)
        print('      queue %d%s take %u dwords at %u: rung %s, taken %+.3f, submit returned %s' % (
            q, ' (compute)' if qs.get(q, {}).get('a') == 2 else '', take, r,
            '%+.3f' % p[0] if p else 'before the window (< -50 ms)', rel, '%+.3f' % done if done is not None else '-'))
    deferred = [e for e in ev if e[2] == 'deferred' and (flip is None or e[0] <= flip)]
    for e in deferred:
        print('      queue %d deferred at %+.3f (%u dwords pending at %u)' % (e[1], e[0], e[4], e[3]))
    if flip is None or not takes:
        verdicts['no take before the flip'] += 1
        continue
    last = takes[-1]
    n = qs.get(last[1], {}).get('n', 0)
    p = posted_by(writes[last[1]], last[3], n, last[0])
    if p is None:
        v = 'consumer late (rung before the window, taken %+.1f ms)' % last[0]
        verdicts['consumer late'] += 1
    elif p[0] < 0 and last[0] >= 0:
        v = 'consumer late (rung %+.1f ms, taken %+.1f ms)' % (p[0], last[0])
        verdicts['consumer late'] += 1
    elif p[0] >= 0:
        v = 'title rang late (rung %+.1f ms, taken %+.1f ms)' % (p[0], last[0])
        verdicts['title rang late'] += 1
    else:
        v = 'taken before the give-up (rung %+.1f, taken %+.1f ms)' % (p[0], last[0])
        verdicts['taken before the give-up'] += 1
    print('      -> the last take before the flip, queue %d: %s' % (last[1], v))
print()
print('# the last take before each flip: %s' % dict(verdicts))
print('# timestamp rewrites on wait labels: %d' % len(ts))
for line in ts[:40]:
    print('  ' + line[:260])
