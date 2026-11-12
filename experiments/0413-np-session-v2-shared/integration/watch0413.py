#!/usr/bin/env python3
"""Exp 0413: an external watcher for ASTRO BOT's start crash. Waits for a process named kyty_emulator, then samples
/proc/<pid>/task/*/{comm,stat,syscall} as fast as it can until the process is gone or 12 s passed. Reads only; the
emulator's binary and environment are untouched. Output: one line per thread per change of (state, syscall), with the
time since the first sample, so the thread creation order and what each thread blocks in up to the crash can be read.
usage: watch0413.py <out file>"""
import os
import sys
import time

out = open(sys.argv[1], "w")
pid = None
t_wait = time.time()
while pid is None and time.time() - t_wait < 60:
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                if open(f"/proc/{d}/comm").read().strip() == "kyty_emulator":
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
last = {}
mapped = []
n = 0
while time.time() - t0 < 4:
    try:
        tids = os.listdir(f"/proc/{pid}/task")
    except OSError:
        break
    now = time.time() - t0
    for tid in tids:
        try:
            comm = open(f"/proc/{pid}/task/{tid}/comm").read().strip()
            stat = open(f"/proc/{pid}/task/{tid}/stat").read()
            sysc = open(f"/proc/{pid}/task/{tid}/syscall").read().split()
        except OSError:
            continue
        state = stat[stat.rfind(")") + 2]
        key = (comm, state, tuple(sysc[:3]))
        if last.get(tid) != key:
            last[tid] = key
            if comm.startswith("BackgroundTaskW") and not mapped:
                mapped.append(1)
                try:
                    for line in open("/proc/%d/maps" % pid):
                        a = int(line.split("-")[0], 16)
                        if 0x300000000 <= a < 0x301000000 or 0x7efd00000 <= a < 0x7f0000000:
                            out.write("map " + line)
                except OSError:
                    pass
            fdn = ""
            if sysc and sysc[0] in ("0", "17") and len(sysc) > 1:
                try:
                    fdn = " file " + os.readlink("/proc/%d/fd/%d" % (pid, int(sysc[1], 16)))[-60:]
                except (OSError, ValueError):
                    pass
            out.write("%.4f tid %s [%s] %s syscall %s%s\n" % (now, tid, comm, state, " ".join(sysc[:4]) + (" pc " + sysc[-1] if len(sysc) > 8 else ""), fdn))
    n += 1
out.write("end at %.4f after %d samples, %d threads seen\n" % (time.time() - t0, n, len(last)))
