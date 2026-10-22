#!/usr/bin/env python3
# Experiment 0209: the given-up game-thread waits of a run, with their journal times, from an extract
# made by extract0209.sh. A "cpu-wait ... GIVEN UP after X ms" line is followed by "timing: t T s after
# that wait (kind N dwords)": T is when the host stopped waiting (journal clock, seconds since start).
# usage: giveups0209.py <extract> [<name>]
import re, sys

GU = re.compile(r'^cpu-wait \S+ at (\d+) on (0x[0-9a-f]+): GIVEN UP after ([0-9.]+) ms')
AW = re.compile(r'^timing: t ([0-9.]+) s after that wait \((\w+) (\d+) dwords\)')

def main():
    path = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 else path
    pending = None
    rows = []
    for line in open(path, errors='replace'):
        m = GU.match(line)
        if m:
            pending = (m.group(2), int(m.group(1)), float(m.group(3)))
            continue
        m = AW.match(line)
        if m and pending:
            rows.append((float(m.group(1)), pending[0], pending[1], pending[2], m.group(2), int(m.group(3))))
            pending = None
    print('# %s: %d given-up waits (journal t at the end of the wait, label, dword, waited ms, buffer)' % (name, len(rows)))
    for t, label, dw, ms, kind, n in rows:
        print('%9.3f  %s  at %5d  %6.1f ms  %s %d dwords' % (t, label, dw, ms, kind, n))

main()
