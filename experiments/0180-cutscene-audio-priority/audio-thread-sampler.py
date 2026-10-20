#!/usr/bin/env python3
# BC5 (experiment 0180): every 10 ms between two process times, the kernel state of the sound
# path's threads (SDL's PulseAudio client and audio threads, the title's audio output thread):
# state, wchan, run-queue delay and CPU time since the last sample. Read-only (/proc).
# usage: audio-thread-sampler.py <pid> <from s> <to s> <out>
import os, sys, time
pid, t0, t1, out = int(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
WANT = ("PulseMainloop", "SDLAudioP", "AK::", "Render Thread", "game-main", "bc5-apr", "Bink")
hz = os.sysconf("SC_CLK_TCK")
btime = [int(l.split()[1]) for l in open("/proc/stat") if l.startswith("btime")][0]
start = btime + int(open("/proc/%d/stat" % pid).read().rsplit(")", 1)[1].split()[19]) / hz


def threads():
    r = {}
    for t in os.listdir("/proc/%d/task" % pid):
        try:
            c = open("/proc/%d/task/%s/comm" % (pid, t)).read().strip()
        except OSError:
            continue
        if c.startswith(WANT):
            r[int(t)] = c
    return r


tids = {}
prev = {}
with open(out, "w") as o:
    while True:
        now = time.time() - start
        if now >= t1:
            break
        if now < t0 - 2:
            time.sleep(0.5)
            continue
        if not tids or int(now * 100) % 100 == 0:
            tids = threads()
        line = []
        for tid, name in sorted(tids.items()):
            try:
                st = open("/proc/%d/task/%d/stat" % (pid, tid)).read().rsplit(")", 1)[1].split()
                sch = open("/proc/%d/task/%d/schedstat" % (pid, tid)).read().split()
                wc = open("/proc/%d/task/%d/wchan" % (pid, tid)).read().strip() or "-"
            except OSError:
                continue
            cpu, delay = int(sch[0]), int(sch[1])
            p = prev.get(tid, (cpu, delay))
            prev[tid] = (cpu, delay)
            line.append("%s:%s:%s:cpu%.1f:wait%.1f" % (name.replace(" ", "_"), st[0], wc, (cpu - p[0]) / 1e6, (delay - p[1]) / 1e6))
        if now >= t0:
            o.write("%.3f %s\n" % (now, " ".join(line)))
        time.sleep(0.01)
