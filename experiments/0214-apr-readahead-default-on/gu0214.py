#!/usr/bin/env python3
# BC5 experiment 0214: the given-up CPU waits of the runs' GPU journals by label (the regression check of
# KYTY_BC5_APR_READAHEAD; F262-F265 relate the label 0x12004b3c38 to the machine-downs). Each journal is read as in
# ra0214.py (O_DIRECT, capped rate). usage: gu0214.py <MB/s> <tag>=<journal> ...   (on the box)
import collections, os, re, sys

sys.argv, args = sys.argv[:1] + ['0', '0'], sys.argv[1:]  # ra0214.py's main() then has nothing to do
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python3 -I leaves the script's directory out
import ra0214  # noqa: E402  (the reader only)

GU = re.compile(rb'cpu-wait (\S+) at (\d+) on (0x[0-9a-f]+): GIVEN UP after ([0-9.]+) ms')
rate = float(args[0])
for arg in args[1:]:
    tag, path = arg.split('=', 1)
    by = collections.Counter()
    ms = []
    for ln in ra0214.lines(path, rate):
        m = GU.search(ln)
        if m:
            by[m.group(3).decode()] += 1
            ms.append(float(m.group(4)))
    print('%-4s %3d given up (%s ms max %.1f): %s' % (tag, sum(by.values()), 'median %.1f' % sorted(ms)[len(ms) // 2]
                                                    if ms else '-', max(ms) if ms else 0,
                                                    ', '.join('%s %d' % kv for kv in by.most_common())))
    sys.stdout.flush()
