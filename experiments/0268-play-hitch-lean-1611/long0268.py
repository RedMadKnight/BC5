#!/usr/bin/env python3
# BC5 experiment 0268: one pass over a play session's GPU journal (gc/direct.log), read with O_DIRECT at a capped rate
# by exp 0214's reader: flips, long frames and TIMEOUT/fault/reopen/given-up counts (as ra0214.py), given-up waits by
# label, and every frame over <ms> and every TIMEOUT line into <long-out>.
# usage: long0268.py <MB/s> <ms> <journal> <long-out>   (on the box, read-only)
import collections, os, re, sys

sys.argv, args = sys.argv[:1] + ['0', '0'], sys.argv[1:]  # ra0214.py's main() then has nothing to do
sys.path.insert(0, os.path.expanduser('~/bc5-work/exp0214'))
import ra0214  # noqa: E402

GU = re.compile(rb'cpu-wait (\S+) at (\d+) on (0x[0-9a-f]+): GIVEN UP after ([0-9.]+) ms')
rate, lim, path, out = float(args[0]), float(args[1]), args[2], args[3]
fr, cnt, by = [], collections.Counter(), collections.Counter()
with open(out, 'w') as lo:
    for ln in ra0214.lines(path, rate):
        m = ra0214.FR.match(ln)
        if m:
            f = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
            fr.append(f)
            if f[1] > lim:
                lo.write(ln[:420].decode('latin-1') + '\n')
            continue
        for k, pat in ra0214.KINDS:
            if re.search(pat, ln):
                cnt[k] += 1
                if k == 'TIMEOUT':
                    lo.write(ln[:300].decode('latin-1') + '\n')
        g = GU.search(ln)
        if g:
            by[g.group(3).decode()] += 1
print(path)
print('  all      : ' + ra0214.stats(fr))
print('  lines    : ' + ', '.join('%s %d' % (k, cnt[k]) for k, _ in ra0214.KINDS))
print('  given up by label: ' + (', '.join('%s %d' % kv for kv in by.most_common()) or 'none'))
