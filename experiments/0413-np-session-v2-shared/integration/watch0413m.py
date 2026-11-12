#!/usr/bin/env python3
"""Exp 0413: an external watcher of the emulator's memory map near the collision, for ASTRO BOT's start crash. Waits for
a process named kyty_emulator, then reads /proc/<pid>/maps as fast as it can for 4 s (or until the process is gone) and
writes every CHANGE of the mappings that touch guest 0x300900000-0x300b00000, with the time and the names of the threads
alive at that moment. Reads only; the emulator's binary and environment are untouched.
usage: watch0413m.py <out file>"""
import os
import sys
import time

LO, HI = 0x300900000, 0x300B00000
out = open(sys.argv[1], "w")
pid = None
t_wait = time.time()
while pid is None and time.time() - t_wait < 60:
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                if open("/proc/%s/comm" % d).read().strip() == "kyty_emulator":
                    pid = int(d)
                    break
            except OSError:
                pass
    if pid is None:
        time.sleep(0.005)
if pid is None:
    out.write("no emulator seen\n")
    sys.exit(1)
t0 = time.time()
last = None
n = 0
while time.time() - t0 < 4:
    try:
        lines = open("/proc/%d/maps" % pid).read().split("\n")
    except OSError:
        break
    now = time.time() - t0
    cur = []
    for line in lines:
        rng = line.split(" ", 1)[0]
        if "-" not in rng:
            continue
        a, b = rng.split("-")
        try:
            a, b = int(a, 16), int(b, 16)
        except ValueError:
            continue
        if a < HI and b > LO:
            cur.append(line[:62].rstrip())
    if cur != last:
        last = cur
        try:
            names = sorted(open("/proc/%d/task/%s/comm" % (pid, t)).read().strip() for t in os.listdir("/proc/%d/task" % pid))
        except OSError:
            names = []
        out.write("%.4f maps changed, %d lines; %d threads, last: %s\n" % (now, len(cur), len(names), " ".join(names[-0:][:0]) or ",".join(sorted(set(names)))[:160]))
        for line in cur:
            out.write("   " + line + "\n")
    n += 1
out.write("end at %.4f after %d samples\n" % (time.time() - t0, n))
