#!/usr/bin/env python3
# BC5 exp 0439 (tag mp439, 11-24, the top session's order after F927): memory pressure applied from outside while the
# third title runs, to show whether BC5_0439_MLOCK_IMPORTS ends the reclaim thrash without the maintainer riding.
# Allocates and touches anonymous memory in 64 MiB steps until MemAvailable reaches the target, holds it, then frees it.
# Safety brake: it stops growing and frees everything when memory PSI "full" avg10 passes MP_PSI_STOP (default 10 %)
# or MemAvailable falls under MP_FLOOR_MB (default 700). Its own oom_score_adj is 1000, so the kernel kills it first.
# One line per second to stdout: time, MemAvailable MiB, held MiB, PSI some/full avg10, pgscan_direct delta per s.
#   memp439.py <target MemAvailable MiB> <hold s>
import os, sys, time

target = int(sys.argv[1]) * 1024 * 1024
hold = float(sys.argv[2])
psi_stop = float(os.environ.get("MP_PSI_STOP", "10"))
floor = int(os.environ.get("MP_FLOOR_MB", "700")) * 1024 * 1024
step = 64 * 1024 * 1024
try:
    with open("/proc/self/oom_score_adj", "w") as f:
        f.write("1000")
except OSError:
    pass


def avail():
    with open("/proc/meminfo") as f:
        for l in f:
            if l.startswith("MemAvailable:"):
                return int(l.split()[1]) * 1024
    return 0


def psi():
    s = f = 0.0
    with open("/proc/pressure/memory") as fh:
        for l in fh:
            v = float(l.split()[1].split("=")[1])
            if l.startswith("some"):
                s = v
            else:
                f = v
    return s, f


def scan():
    n = 0
    with open("/proc/vmstat") as fh:
        for l in fh:
            if l.startswith("pgscan_direct"):
                n += int(l.split()[1])
    return n


chunks = []
t0 = time.time()
last = scan()
last_t = time.time()
phase = "grow"
held_since = None
why = ""
while True:
    a = avail()
    s, f = psi()
    now = scan()
    if f > psi_stop or a < floor:
        why = "brake: PSI full %.2f, MemAvailable %d MiB" % (f, a >> 20)
        break
    if phase == "grow":
        if a - step > target:
            b = bytearray(step)
            for i in range(0, step, 4096):
                b[i] = 1
            chunks.append(b)
        else:
            phase = "hold"
            held_since = time.time()
    elif time.time() - held_since >= hold:
        why = "held %.0f s" % hold
        break
    if time.time() - last_t >= 1:
        print("%s %.1f avail %d held %d psi %.2f/%.2f pgscan_direct/s %d %s" % (time.strftime("%T"), time.time() - t0, a >> 20, len(chunks) * 64, s, f, (now - last) / (time.time() - last_t), phase), flush=True)
        last, last_t = now, time.time()
    time.sleep(1 if phase == "hold" else 0.05)
chunks.clear()
print("%s end: %s" % (time.strftime("%T"), why), flush=True)
