#!/usr/bin/env python3
"""Per-phase view of the wait sampler's output: for a time window, per thread, the CPU share
and what it was doing when sampled (running, or blocked in which wchan/syscall)."""
import json, sys
path = sys.argv[1]
L = [json.loads(l) for l in open(path)]
head, W = L[0], L[1:]
interval = head.get("interval", 0.2)
SYSCALLS = {"0": "read", "1": "write", "7": "poll", "16": "ioctl", "17": "pread64", "35": "nanosleep", "202": "futex", "230": "clock_nanosleep", "232": "epoll_wait", "270": "pselect6", "271": "ppoll", "281": "epoll_pwait", "257": "openat", "262": "newfstatat", "4": "stat", "6": "lstat", "21": "access", "5": "fstat", "3": "close", "9": "mmap", "11": "munmap", "28": "madvise", "24": "sched_yield", "61": "wait4", "232": "epoll_wait", "-1": "running/none", "running": "running"}

def label(key):
    if key == "R":
        return "running"
    st, wchan, sc = (key.split("|") + ["", ""])[:3]
    name = SYSCALLS.get(sc, "sys" + sc)
    return "%s %s (%s)" % (st, name, wchan if wchan not in ("0", "?", "") else "-")

def phase(name, a, b, top_threads=10, proc="kyty_emulator"):
    sel = [w for w in W if a <= w["t"] < b]
    if not sel:
        print("== %s: no samples" % name); return
    dur = sum(w["dt"] for w in sel)
    per = {}
    for w in sel:
        for t in w["threads"]:
            if t["proc"] != proc: continue
            k = (t["tid"], t["name"]); e = per.setdefault(k, {"cpu": 0.0, "keys": {}, "samples": 0})
            e["cpu"] += t["cpu"]; e["samples"] += t["samples"]
            for key, n in t["top"]: e["keys"][key] = e["keys"].get(key, 0) + n
    total = sum(e["cpu"] for e in per.values())
    print("== %s (%s, %.0f-%.0f s, %.0f s): total %.0f%% of 1600%%, %d threads" % (name, proc, a, b, dur, total / dur * 100, len(per)))
    rows = sorted(per.items(), key=lambda kv: -kv[1]["cpu"])
    for (tid, nm), e in rows[:top_threads]:
        n = max(1, e["samples"])
        top = ", ".join("%s %.0f%%" % (label(k), c / n * 100) for k, c in sorted(e["keys"].items(), key=lambda kv: -kv[1])[:4])
        print("   %-16s %6d %5.0f%% | %s" % (nm[:16], tid, e["cpu"] / dur * 100, top))

if len(sys.argv) > 2:
    for spec in sys.argv[2:]:
        name, a, b = spec.split(":"); phase(name, float(a), float(b))
        phase(name + " / bc5-mount", float(a), float(b), top_threads=4, proc="bc5-mount")
else:
    # a timeline: per 10 s, the total CPU and the three busiest threads
    for i in range(0, int(W[-1]["t"]) + 1, 10):
        sel = [w for w in W if i <= w["t"] < i + 10]
        if not sel: continue
        dur = sum(w["dt"] for w in sel); agg = {}
        for w in sel:
            for t in w["threads"]:
                if t["proc"] != "kyty_emulator": continue
                agg[t["name"]] = agg.get(t["name"], 0) + t["cpu"]
        tot = sum(agg.values())
        top = ", ".join("%s %.0f%%" % (k[:14], v / dur * 100) for k, v in sorted(agg.items(), key=lambda kv: -kv[1])[:4])
        print("%4d s total %4.0f%% | %s" % (i, tot / dur * 100, top))
