#!/usr/bin/env python3
"""BC5 exp 0429: the rows of a chain (chain-rows-<set>.txt), counted per arm. Descriptive (R13): no rate, no p-value.
    check0429.py <rows file> [<rows file> ...]
A row: "<tag> <CLASS> pad <n> fps <x> gaps <y> ...", tag h429<arm><n>. The rule, fixed before the runs (README):
an arm is OUT at its first TARGET (the crash at eboot+0x3d7eca0); it SURVIVES a set when all its counted runs
(NO_CRASH to G+600) are clean; KERNEL, NOT_ROUTED and other classes are not counted runs and are listed."""
import collections
import sys

arms = collections.OrderedDict()
for path in sys.argv[1:]:
    for line in open(path, encoding='utf-8'):
        f = line.split()
        if len(f) < 2 or not f[0].startswith('h429'):
            continue
        arm = f[0][4]
        fps = f[f.index('fps') + 1] if 'fps' in f else '-'
        arms.setdefault(arm, []).append((f[0], f[1], fps))
for arm, rows in arms.items():
    c = collections.Counter(r[1] for r in rows)
    verdict = 'control' if arm == 'C' else 'OUT' if c['TARGET'] else ('SURVIVES (%d clean)' % c['NO_CRASH'] if c['NO_CRASH'] else 'NO COUNTED RUN')
    fps = [float(r[2]) for r in rows if r[1] == 'NO_CRASH' and r[2] not in ('-', '')]
    print('arm %s: %s | %s | flips/s of clean runs %s' % (
        arm, ' '.join('%s %d' % kv for kv in sorted(c.items())), verdict,
        ('%.1f-%.1f' % (min(fps), max(fps))) if fps else '-'))
    print('   ' + ' '.join('%s:%s' % (t, k) for t, k, _ in rows))
