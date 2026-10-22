#!/usr/bin/env python3
# BC5 experiment 0221, v3 (patch0221b.py, run tcpW7): who writes the compute labels that the given-up game-thread waits
# depend on. Reads the "flip trace:" lines of the run's extract. Per give-up on label B:
#   - the compute labels acb_ready() found unsatisfied in the 50 ms before (the candidates C), their values, and
#     which of them have write breakpoints (the fixed list BC5_DIRECT_FLIP_TRACE_WP_LABELS);
#   - every change of a candidate after the give-up, before or after B's flip, and its writer: the threads whose
#     breakpoint count rose at that change (a CPU write), "no CPU write counted" (a GPU write), or unknown (no
#     breakpoints on that label);
#   - B's flip (its writer is the GPU in tcpW6, 13 of 13).
# Then the totals by writer for the candidate changes before B's flip, and the CPU writers of the fixed labels
# between watches ("at the watch start").
# usage: ana0221b.py <extract>
import re, sys
from collections import Counter, defaultdict

GIVE = re.compile(r'^flip trace: #(\d+) given up: (\S+) (\d+) dwords at (\d+) on (0x[0-9a-f]+) \(game thread (\d)\) after ([0-9.]+) ms, t ([0-9.]+) s; value (0x[0-9a-f]+); in flight cq0 (-?\d+) cq1 (-?\d+)')
CAND = re.compile(r'^flip trace: #(\d+) compute candidate (0x[0-9a-f]+): held back ([0-9.]+) ms before the give-up, value (0x[0-9a-f]+)(; it has write breakpoints)?')
ARM = re.compile(r'^flip trace: #(\d+) write breakpoints on the compute label (0x[0-9a-f]+): (\d+) armed, (\d+) failed \(errno (\d+)\), in ([0-9.]+) ms, armed ([0-9.]+) ms after the give-up; value then (0x[0-9a-f]+)')
CHG = re.compile(r'^flip trace: #(\d+) (0x[0-9a-f]+): (0x[0-9a-f]+) -> (0x[0-9a-f]+) at t ([0-9.]+) s, ([0-9.]+) ms after the give-up; in flight cq0 (-?\d+) cq1 (-?\d+)')
CCHG = re.compile(r'^flip trace: #(\d+) compute label (0x[0-9a-f]+): (0x[0-9a-f]+) -> (0x[0-9a-f]+) at t ([0-9.]+) s, ([0-9.]+) ms after the give-up; in flight cq0 (-?\d+) cq1 (-?\d+)')
CPUW = re.compile(r'^flip trace: #(\d+) CPU write to the (given-up|compute) label (0x[0-9a-f]+): thread (\d+) \((.*)\)( = the thread that gave up)?, (\d+) write\(s\), seen (at the watch start \(since the last read\)|at a change|at the end) at t ([0-9.]+) s, ([0-9.]+) ms after the give-up')
NOCPU = re.compile(r'^flip trace: #(\d+) no CPU write counted for that change of the compute label (0x[0-9a-f]+)')
END = re.compile(r'^flip trace: #(\d+) (0x[0-9a-f]+) (satisfied|NOT satisfied within 2 s) ([0-9.]+) ms after the give-up \(([0-9.]+) ms after the wait began\)')

g = defaultdict(lambda: dict(cand={}, chg=[], cchg=[], cpu=[], nocpu=[], arm=[]))
for line in open(sys.argv[1], errors='replace'):
    if not line.startswith('flip trace: #'):
        continue
    for rx, key in ((GIVE, 'give'), (CAND, 'cand'), (ARM, 'arm'), (CCHG, 'cchg'), (CHG, 'chg'), (CPUW, 'cpu'), (NOCPU, 'nocpu'), (END, 'end')):
        m = rx.match(line)
        if not m:
            continue
        d = g[m.group(1)]
        if key == 'give':
            d.update(t=float(m.group(8)), label=m.group(5), dwords=int(m.group(3)), at=int(m.group(4)), waited=float(m.group(7)), q=(int(m.group(10)), int(m.group(11))))
        elif key == 'cand':
            d['cand'][m.group(2)] = (float(m.group(3)), m.group(4), m.group(5) is not None)
        elif key == 'arm':
            d['arm'].append((m.group(2), int(m.group(3)), int(m.group(4)), int(m.group(5)), float(m.group(6)), float(m.group(7)), m.group(8)))
        elif key == 'cchg':
            d['cchg'].append((float(m.group(6)), m.group(2), m.group(3), m.group(4), int(m.group(7)), int(m.group(8))))
        elif key == 'chg':
            d['chg'].append((float(m.group(6)), m.group(3), m.group(4), int(m.group(7)), int(m.group(8))))
        elif key == 'cpu':
            d['cpu'].append((m.group(2), m.group(3), m.group(5), m.group(6) is not None, int(m.group(7)), m.group(8), float(m.group(10))))
        elif key == 'nocpu':
            d['nocpu'].append(m.group(2))
        elif key == 'end':
            d.update(sat=m.group(3) == 'satisfied', after=float(m.group(4)), total=float(m.group(5)))
        break

gives = sorted((k for k in g if 't' in g[k]), key=lambda k: g[k]['t'])
armed_labels = {}  # label -> the first give-up time at which its breakpoints were armed
for k in gives:
    for a in g[k]['arm']:
        armed_labels.setdefault(a[0], g[k]['t'] + a[5] / 1000.0)
print('# %d give-ups; breakpoints armed on %s' % (len(gives), ', '.join('%s (from t %.3f)' % kv for kv in sorted(armed_labels.items()))))
tot = Counter()
for k in gives:
    d = g[k]
    b_flip = next((c[0] for c in d['chg']), None)
    print('#%s t %.3f %s (%s %d at %d) waited %.2f ms; B flips +%s ms; in flight at the give-up cq0 %d cq1 %d; %d candidates'
          % (k, d['t'], d['label'], 'dcb', d['dwords'], d['at'], d['waited'], '%.3f' % b_flip if b_flip is not None else 'never', d['q'][0], d['q'][1], len(d['cand'])))
    for lab, (ago, val, wp) in sorted(d['cand'].items(), key=lambda kv: kv[1][0]):
        print('      candidate %s held back %.3f ms before, value %s%s' % (lab, ago, val, ', breakpoints' if wp else ''))
    seen_change = set()
    for (t, lab, old, new, q0, q1) in d['cchg']:
        if (lab, t) in seen_change:
            continue
        seen_change.add((lab, t))
        cpu = [c for c in d['cpu'] if c[1] == lab and c[5] == 'at a change' and abs(c[6] - t) < 0.5]
        armed = lab in armed_labels and armed_labels[lab] <= d['t'] + t / 1000.0
        # armed during this very watch: the watcher does not poll while it arms, so the change counts as covered only
        # if the label still held its give-up value when the arming ended
        same = [a for a in d['arm'] if a[0] == lab]
        if armed and same and same[0][6] != d['cand'].get(lab, (0, None, False))[1]:
            armed = False
        if cpu:
            who = 'CPU: ' + ', '.join(sorted({c[2] + (' (the waiter)' if c[3] else '') for c in cpu}))
        elif armed and lab in d['nocpu']:
            who = 'no CPU write: GPU'
        elif armed:
            who = 'no read at the change'
        else:
            who = 'unknown (no breakpoints)'
        when = 'before B' if b_flip is None or t <= b_flip else 'after B'
        print('      %s %s -> %s at +%.3f ms (%s), in flight cq0 %d cq1 %d: %s' % (lab, old, new, t, when, q0, q1, who))
        tot[(when, 'release (-> 0)' if new == '0x0' else 'other change', who.split(':')[0] if who.startswith('CPU') else who)] += 1
    for c in d['cpu']:
        if c[5].startswith('at the watch start'):
            print('      between watches: %s written %d time(s) by %s%s' % (c[1], c[4], c[2], ' (the thread that gave up)' if c[3] else ''))
            tot[('between watches', c[1], c[2])] += c[4]
print()
print('# candidate changes after the give-up: (before/after B, kind, writer) -> count; between watches: (label, thread) -> writes')
for key, n in sorted(tot.items()):
    print('  %-70s %d' % (' / '.join(key), n))
