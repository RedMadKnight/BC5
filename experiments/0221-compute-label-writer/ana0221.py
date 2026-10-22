#!/usr/bin/env python3
# BC5 experiment 0221: who writes the labels of the given-up game-thread waits (B) and of the compute queue's own
# wait (C). Reads the run's extract (run0221.sh extract), the "flip trace:" lines of patch_0221.diff. Per give-up:
#   - the compute queue's state at the give-up: held back on C (g_unready_label) or not; whether B is among the
#     labels C's buffer writes past its wait (g_unready_writes); whether C is among the labels the waiting buffer
#     writes;
#   - when B and C changed after the give-up;
#   - the write breakpoints (kept armed once a label has come up): the CPU writes read at each change, by thread.
#     A change of a label whose breakpoints were armed before it, with no CPU write counted, is a GPU write.
#     "At the watch start" counts are the writes since the previous read: who else writes the label.
# Then the totals, and the served waits of 4 ms or more by the compute queue's state at their end.
# usage: ana0221.py <extract>
import re, sys
from collections import Counter, defaultdict

GIVE = re.compile(r'^flip trace: #(\d+) given up: (\S+) (\d+) dwords at (\d+) on (0x[0-9a-f]+) \(game thread (\d)\) after ([0-9.]+) ms, t ([0-9.]+) s; value (0x[0-9a-f]+); in flight cq0 (-?\d+) cq1 (-?\d+)')
HELD = re.compile(r'^flip trace: #(\d+) compute queue held back on (0x[0-9a-f]+) \(value (0x[0-9a-f]+)\); its buffer writes (\d+) label\(s\) past that wait, the given-up label (AMONG them|not among them); the waiting buffer writes (\d+) label\(s\), the compute label (AMONG them|not among them)')
FREE = re.compile(r'^flip trace: #(\d+) compute queue not held back \(g_unready_label 0\); the waiting buffer writes (\d+) label')
ARM = re.compile(r'^flip trace: #(\d+) write breakpoints on the (given-up|compute) label (0x[0-9a-f]+): (\d+) armed, (\d+) failed \(errno (\d+)\), in ([0-9.]+) ms, armed ([0-9.]+) ms after the give-up; value then (0x[0-9a-f]+)')
BPS = re.compile(r'^flip trace: #(\d+) breakpoints: given-up label (.*); compute label (.*)$')
CHG = re.compile(r'^flip trace: #(\d+) (0x[0-9a-f]+): (0x[0-9a-f]+) -> (0x[0-9a-f]+) at t ([0-9.]+) s, ([0-9.]+) ms after the give-up; in flight cq0 (-?\d+) cq1 (-?\d+)')
CCHG = re.compile(r'^flip trace: #(\d+) compute label (0x[0-9a-f]+): (0x[0-9a-f]+) -> (0x[0-9a-f]+) at t ([0-9.]+) s, ([0-9.]+) ms after the give-up; in flight cq0 (-?\d+) cq1 (-?\d+)')
CPUW = re.compile(r'^flip trace: #(\d+) CPU write to the (given-up|compute) label (0x[0-9a-f]+): thread (\d+) \((.*)\)( = the thread that gave up)?, (\d+) write\(s\), seen (at the watch start \(since the last read\)|at a change|at the end) at t ([0-9.]+) s, ([0-9.]+) ms after the give-up')
NOCPU = re.compile(r'^flip trace: #(\d+) no CPU write counted for that change of the (given-up|compute) label')
END = re.compile(r'^flip trace: #(\d+) (0x[0-9a-f]+) (satisfied|NOT satisfied within 2 s) ([0-9.]+) ms after the give-up \(([0-9.]+) ms after the wait began\)')
SRV = re.compile(r'^flip trace: served (\S+) (\d+) dwords at (\d+) on (0x[0-9a-f]+) after ([0-9.]+) ms, .*compute queue blocked on (0x[0-9a-f]+)')

g = defaultdict(lambda: dict(chg=[], cchg=[], cpu=[], nocpu=[], arm={}))
served = []
for line in open(sys.argv[1], errors='replace'):
    if not line.startswith('flip trace: ') or ' job #' in line[:20]:
        continue
    m = None
    for rx, key in ((GIVE, 'give'), (HELD, 'held'), (FREE, 'free'), (ARM, 'arm'), (BPS, 'bps'), (CHG, 'chg'), (CCHG, 'cchg'), (CPUW, 'cpu'), (NOCPU, 'nocpu'), (END, 'end')):
        m = rx.match(line)
        if not m:
            continue
        d = g[m.group(1)]
        if key == 'give':
            d.update(t=float(m.group(8)), label=m.group(5), dwords=int(m.group(3)), waited=float(m.group(7)), q=(int(m.group(10)), int(m.group(11))), v_give=m.group(9))
        elif key == 'held':
            d.update(c=m.group(2), cval=m.group(3), n_after=int(m.group(4)), b_in_after=m.group(5) == 'AMONG them', n_written=int(m.group(6)), c_in_written=m.group(7) == 'AMONG them')
        elif key == 'free':
            d.update(c=None, n_written=int(m.group(2)))
        elif key == 'arm':
            d['arm'][m.group(2)] = (float(m.group(8)), int(m.group(4)), int(m.group(5)), int(m.group(6)), float(m.group(7)), m.group(9))
        elif key == 'bps':
            d.update(bp_b=m.group(2), bp_c=m.group(3))
        elif key == 'chg':
            d['chg'].append((float(m.group(6)), m.group(3), m.group(4), int(m.group(7)), int(m.group(8))))
        elif key == 'cchg':
            d['cchg'].append((float(m.group(6)), m.group(3), m.group(4), int(m.group(7)), int(m.group(8))))
        elif key == 'cpu':
            d['cpu'].append((m.group(2), m.group(5), m.group(6) is not None, int(m.group(7)), m.group(8), float(m.group(10))))
        elif key == 'nocpu':
            d['nocpu'].append(m.group(2))
        elif key == 'end':
            d.update(sat=m.group(3) == 'satisfied', after=float(m.group(4)), total=float(m.group(5)))
        break
    else:
        m = SRV.match(line)
        if m:
            served.append((m.group(4), float(m.group(5)), m.group(6)))
        else:
            print('# unparsed: ' + line.rstrip()[:200])

gives = sorted((k for k in g if 't' in g[k]), key=lambda k: g[k]['t'])
print('# %d give-ups' % len(gives))
tot, writers, others = Counter(), Counter(), Counter()
for k in gives:
    d = g[k]
    held = d.get('c') is not None
    tot['compute queue held back' if held else 'compute queue not held back'] += 1
    if held:
        tot['  B among the held-back buffer\'s writes' if d['b_in_after'] else '  B not among them'] += 1
        tot['  C among the waiting buffer\'s writes (a cycle)' if d['c_in_written'] else '  C not among them'] += 1
    b_flip = next((c[0] for c in d['chg']), None)
    c_flip = next((c[0] for c in d['cchg']), None)
    if held and b_flip is not None:
        tot['  C changed before B' if c_flip is not None and c_flip <= b_flip else '  C not changed before B'] += 1
    for which, flip, state in (('given-up', b_flip, d.get('bp_b', 'none')), ('compute', c_flip, d.get('bp_c', 'none'))):
        if flip is None:
            continue
        # Armed with this give-up: covered only if the label still held its value at the give-up when arming ended
        # (the watcher does not poll while it arms, so a flip during arming is detected late, after the arming).
        v_give = d.get('v_give') if which == 'given-up' else d.get('cval')
        covered = state.startswith('armed before') or (state == 'armed now' and which in d['arm'] and d['arm'][which][5] == v_give)
        cpu = [c for c in d['cpu'] if c[0] == which and c[4] == 'at a change']
        if cpu:
            kind = 'CPU: ' + ', '.join(sorted({c[1] + (' (the waiter)' if c[2] else '') for c in cpu}))
        elif not covered:
            kind = 'unknown (breakpoints %s)' % ('armed after the change' if state == 'armed now' else state)
        elif which in d['nocpu']:
            kind = 'no CPU write: GPU'
        else:
            kind = 'unknown (no read at the change)'
        writers[(which, kind)] += 1
        d['w_' + which] = kind
    for c in d['cpu']:
        if c[4].startswith('at the watch start'):
            others[(c[0], c[1])] += c[3]
    print('#%s t %.3f %s waited %.2f ms, flip +%s ms (total %s); compute queue %s; B flips +%s, C flips +%s'
          % (k, d['t'], d['label'], d['waited'], '%.3f' % d['after'] if d.get('sat') else 'NOT', '%.2f' % d['total'] if 'total' in d else '-',
             ('held back on %s (value %s; B %s its %d writes; C %s the waiting buffer\'s %d writes)' % (d['c'], d['cval'], 'IN' if d['b_in_after'] else 'not in', d['n_after'],
              'IN' if d['c_in_written'] else 'not in', d['n_written'])) if held else 'not held back',
             '%.3f' % b_flip if b_flip is not None else '-', '%.3f' % c_flip if c_flip is not None else '-'))
    print('      breakpoints: B %s; C %s%s' % (d.get('bp_b', '-'), d.get('bp_c', '-'),
          ''.join('; armed on the %s label +%.3f ms (%d threads, %d failed, errno %d, %.1f ms)' % (w, a[0], a[1], a[2], a[3], a[4]) for w, a in d['arm'].items())))
    for which in ('given-up', 'compute'):
        if 'w_' + which in d:
            print('      %-8s label writer: %s' % (which, d['w_' + which]))
    for c in d['cpu']:
        print('      CPU write: %s label by %s%s, %d write(s), seen %s +%.3f ms' % (c[0], c[1], ' (the thread that gave up)' if c[2] else '', c[3], c[4], c[5]))
print()
print('# totals')
for key, n in sorted(tot.items(), key=lambda kv: kv[0].lstrip()):
    print('  %-50s %d' % (key, n))
print('# writers at the flip (label, finding): count')
for (which, kind), n in sorted(writers.items()):
    print('  %-8s %-60s %d' % (which, kind, n))
print('# other CPU writes, between watches (label, thread): writes')
for (which, name), n in sorted(others.items()):
    print('  %-8s %-30s %d' % (which, name, n))
print()
blocked = Counter('blocked' if s[2] != '0x0' else 'not blocked' for s in served)
print('# served game-thread waits of 4 ms or more: %d; compute queue at their end: %s' % (len(served), dict(blocked)))
