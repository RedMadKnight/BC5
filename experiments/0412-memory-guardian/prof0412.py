#!/usr/bin/env python3
"""BC5 exp 0412: prof0412.sh's samples as shares of a thread's wall-clock time, by phase of the scripted run.
A sample is classed by the host call chain between its innermost frame and the first guest frame (a frame with no
symbol): "guest code" when the innermost frame is the guest's, "wait" when it sits in a futex/condvar/semaphore wait,
otherwise the host library function the guest called (the outermost host frame of the chain) and the innermost one.
Also per phase: the thread's user and system CPU share, faults, context switches, and the process's read counters.
usage: prof0412.py <prof file> [<load at s> default 104]"""
import collections
import re
import sys

HDR = re.compile(r"== t ([\d.]+) rel (\d+) (\S+) tid (\d+) \| state utime stime minflt majflt: (\S) (\d+) (\d+) (\d+) (\d+) \| ctxsw vol invol: (\d+) (\d+) "
                 r"\| schedstat run_ns wait_ns slices: (\d+) (\d+) (\d+) \| io: rchar: (\d+) wchar: (\d+) syscr: (\d+) syscw: (\d+) read_bytes: (\d+)")
WAITS = ("futex", "syscall_cancel", "epoll", "nanosleep", "poll", "cond_wait", "cond_clockwait", "cond_timedwait", "sem_wait", "__atomic_wait", "atomic_semaphore")


def load(path):
    out, cur = [], None
    for ln in open(path, errors="replace"):
        if ln.startswith("== t"):
            m = HDR.match(ln)
            cur = None
            if m:
                g = m.groups()
                cur = dict(t=float(g[0]), rel=int(g[1]), name=g[2], ut=int(g[5]), st=int(g[6]), minf=int(g[7]), majf=int(g[8]), vol=int(g[9]), inv=int(g[10]),
                           wait=int(g[12]), rchar=int(g[14]), syscr=int(g[16]), rbytes=int(g[18]), fr=[])
                out.append(cur)
        elif ln.startswith("#") and cur is not None:
            p = ln.split(None, 2)
            cur["fr"].append(re.sub(r"\(.*", "", p[2].strip())[:80] if len(p) > 2 else "<guest>")
    return out


def klass(fr):
    host = []
    for f in fr:
        if f == "<guest>":
            break
        host.append(f)
    if not host:
        return "guest code", ""
    named = [f for f in host if not f.startswith("__") and "syscall" not in f]
    if not named:
        return "guest code", ""
    outer = named[-1]  # what the guest called
    inner = named[0]
    if len(host) == len(fr):  # no guest frame at all: a host thread function
        outer = named[-1]
    if any(w in " ".join(host[:5]) for w in WAITS):
        return "wait: " + outer, ""
    return outer, inner


def main():
    path = sys.argv[1]
    ld = int(sys.argv[2]) if len(sys.argv) > 2 else 104
    s = load(path)
    if not s:
        print("no samples")
        return
    phases = [("scene load 33-62", 33, 62), (f"save load {ld}-{ld + 28}", ld, ld + 28), (f"play {ld + 28}-end", ld + 28, 10**6)]
    print(f"{s[0]['name']}: {len(s)} samples, {s[0]['rel']}-{s[-1]['rel']} s")
    for pn, a, b in phases:
        w = [x for x in s if a <= x["rel"] < b]
        if len(w) < 3:
            continue
        dt = w[-1]["t"] - w[0]["t"]
        d = lambda k: w[-1][k] - w[0][k]
        print(f" -- {pn}: {len(w)} samples in {dt:.0f} s; cpu user {d('ut') / dt:.0f} % sys {d('st') / dt:.0f} %; minor faults {d('minf') / dt:.0f}/s, major {d('majf') / dt:.0f}/s; "
              f"ctx switches {d('vol') / dt:.0f}/s voluntary, {d('inv') / dt:.0f}/s not; run-queue wait {100 * d('wait') / 1e9 / dt:.1f} %")
        print(f"      process reads: {d('syscr') / dt:.0f} calls/s, {d('rchar') / dt / 1048576:.1f} MiB/s asked, {d('rbytes') / dt / 1048576:.1f} MiB/s from the disk")
        c, inner = collections.Counter(), collections.defaultdict(collections.Counter)
        for x in w:
            k, i = klass(x["fr"])
            c[k] += 1
            if i:
                inner[k][i] += 1
        for k, n in c.most_common(9):
            top = ", ".join(f"{i} {m}" for i, m in inner[k].most_common(3))
            print(f"      {100 * n / len(w):4.0f} %  {k[:90]}" + (f"   [innermost: {top[:150]}]" if top else ""))


if __name__ == "__main__":
    main()
