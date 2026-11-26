#!/usr/bin/env python3
# BC5 experiment 0247: stacks of the host's kyty-gpu thread and the title's Render Thread while kyty-gpu is busy.
# The stalls of the bench's frozen view (game thread outside the host for 0.3-0.7 s) come with kyty-gpu (KytyPlus's
# GpuState::ThreadRun) at ~95 % CPU. This watcher reads that thread's schedstat every 0.1 s and, when it has run
# more than 240 ms of the last 300 ms, takes one `eu-stack` of the process (ptrace; all threads stop for its
# duration) and keeps the two threads' frames. At most MAX samples, at least 0.5 s apart, only after T0 seconds
# from the emulator's start; it ends with the emulator. Read-only otherwise.
# usage: stackwatch0247.py <out> [max=30] [t0=150]
import os
import subprocess
import sys
import time

OUT = sys.argv[1]
MAX = int(sys.argv[2]) if len(sys.argv) > 2 else 30
T0 = float(sys.argv[3]) if len(sys.argv) > 3 else 150.0
o = open(OUT, "a", buffering=1)

def find_emu():
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                with open("/proc/%s/comm" % d) as f:
                    if f.read().strip() == "kyty_emulator":
                        return int(d)
            except OSError:
                pass
    return None

pid = None
while pid is None:
    pid = find_emu()
    if pid is None:
        time.sleep(0.5)
start = time.monotonic()
o.write("# stackwatch pid %d start mono %.3f\n" % (pid, start))

def tids():
    out = {}
    for t in os.listdir("/proc/%d/task" % pid):
        try:
            with open("/proc/%d/task/%s/comm" % (pid, t)) as f:
                n = f.read().strip()
        except OSError:
            continue
        if n in ("kyty-gpu", "Render Thread"):
            out[n] = int(t)
    return out

def run_ns(tid):
    try:
        with open("/proc/%d/task/%d/schedstat" % (pid, tid)) as f:
            return int(f.read().split()[0])
    except OSError:
        return None

hist = []
taken = 0
last = 0.0
names = {}
while os.path.exists("/proc/%d" % pid) and taken < MAX:
    now = time.monotonic()
    if not names or int(now) % 10 == 0:
        names = tids() or names
    g = names.get("kyty-gpu")
    v = run_ns(g) if g else None
    if v is not None:
        hist.append((now, v))
        hist = [h for h in hist if now - h[0] <= 0.31]
        busy = (hist[-1][1] - hist[0][1]) / 1e6 if len(hist) > 1 else 0.0
        if now - start >= T0 and busy > 240.0 and now - last >= 0.5:
            last = now
            taken += 1
            try:
                r = subprocess.run(["eu-stack", "-p", str(pid), "-n", "24"], capture_output=True, text=True, timeout=10)
                txt = r.stdout
            except (OSError, subprocess.TimeoutExpired) as e:
                txt = "eu-stack failed: %s\n" % e
            keep = []
            on = False
            want = set("TID %d:" % t for t in names.values())
            for line in txt.split("\n"):
                if line.startswith("TID "):
                    on = line.strip() in want
                if on:
                    keep.append(line)
            o.write("== sample %d mono %.3f (t+%.1f s), kyty-gpu ran %.0f ms of the last 300; tids %s\n" % (taken, now, now - start, busy, names))
            o.write("\n".join(keep) + "\n")
    time.sleep(0.1)
o.write("# end mono %.3f, %d samples\n" % (time.monotonic(), taken))
