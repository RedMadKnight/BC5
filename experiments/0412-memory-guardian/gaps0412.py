#!/usr/bin/env python3
"""BC5 exp 0412 (README section 23): the frame gaps by cause. Joins the host's "gap" lines (build g412m,
BC5_GUARD_GAP_STAT; one per gap between flips over the limit, with the per-thread milliseconds each host blocking point
took and CLOCK_MONOTONIC at the gap's end) with gapsamp0412.py's 20 ms samples of the same threads.
For every gap [end - ms, end] and every sampled thread: on-CPU time (schedstat run ns, split user/system by the tick
counters summed over the phase), run-queue wait (schedstat), and blocked time = the gap minus those two. The blocked
time is given to the host causes the gap line names for that thread; what is left is split by what the 20 ms samples
inside the gap show the thread blocked in: a futex wait, a sleep (nanosleep), a read, an ioctl, a page fault or
uninterruptible wait (state D, or blocked outside a system call), other.
Printed per phase of the scripted run: for each thread the share of the gaps' time per cause (summing to 100 %),
then the faults and block-I/O delay ticks inside the gaps.
usage: gaps0412.py <journal lines with "gap (exp 0412"> <gapsamp file> [<load at s> default 104]"""
import bisect
import collections
import re
import sys

GAP = re.compile(r"gap \(exp 0412, tag gp412\): t ([\d.]+) s mono ([\d.]+): ([\d.]+) ms since the last flip(.*)")
SYS = {"202": "futex wait", "35": "sleep", "230": "sleep", "0": "read", "17": "read", "19": "read", "295": "read", "16": "ioctl", "7": "poll", "271": "poll", "232": "poll", "281": "poll",
       "9": "mmap/munmap", "11": "mmap/munmap", "10": "mmap/munmap", "28": "mmap/munmap", "25": "mmap/munmap"}


def main():
    load_at = float(sys.argv[3]) if len(sys.argv) > 3 else 104.0
    gaps = []
    for ln in open(sys.argv[1], errors="replace"):
        m = GAP.search(ln)
        if not m:
            continue
        host = {}
        for part in m.group(4).split(" | ")[1:]:
            name, _, rest = part.partition(":")
            host[name.strip()] = {c.strip().rsplit(" ", 1)[0]: float(c.strip().rsplit(" ", 1)[1]) for c in rest.split(",") if c.strip()}
        gaps.append(dict(t=float(m.group(1)), end=float(m.group(2)), ms=float(m.group(3)), host=host))
    names, hz, samp = {}, 100, collections.defaultdict(list)
    for ln in open(sys.argv[2], errors="replace"):
        if ln.startswith("# gapsamp0412"):
            hz = int(re.search(r"HZ (\d+)", ln).group(1))
            for i, n in re.findall(r"(\d+)=([^;\n]+)", ln.split("threads:")[1]):
                names[int(i)] = n.strip()
            continue
        p = ln.split()
        if len(p) < 11 or ln.startswith("#"):
            continue
        samp[int(p[1])].append((float(p[0]), p[2], int(p[3]), int(p[4]), int(p[5]), int(p[6]), int(p[7]), int(p[8]), int(p[9]), p[10]))
    times = {i: [s[0] for s in v] for i, v in samp.items()}
    print(f"{len(gaps)} gaps, {sum(g['ms'] for g in gaps) / 1000:.1f} s; samples per thread: " + ", ".join(f"{names[i]} {len(v)}" for i, v in sorted(samp.items())))

    def at(i, t):  # the last sample at or before t, else the first
        k = bisect.bisect_right(times[i], t) - 1
        return samp[i][max(k, 0)]

    phases = (("scene load", 33, 62), ("menu and list", 62, load_at), ("save load", load_at, load_at + 28), ("play", load_at + 28, 1e9), ("whole run", 0, 1e9))
    for pname, lo, hi in phases:
        gs = [g for g in gaps if lo <= g["t"] < hi]
        if not gs:
            continue
        tot = sum(g["ms"] for g in gs)
        print(f"\n== {pname}: {len(gs)} gaps, {tot / 1000:.1f} s")
        for i in sorted(samp):
            n = names[i]
            acc = collections.Counter()
            ticks_u = ticks_s = minf = majf = blk = 0
            covered = 0.0
            for g in gs:
                a, b = at(i, g["end"] - g["ms"] / 1000), at(i, g["end"])
                span = (b[0] - a[0]) * 1000
                if span <= 0:
                    continue
                k = g["ms"] / span  # the samples bracket the gap to 20 ms; scale their deltas to the gap's length
                run = (b[7] - a[7]) / 1e6 * k
                rq = (b[8] - a[8]) / 1e6 * k
                run, rq = min(run, g["ms"]), min(rq, max(0.0, g["ms"] - run))
                blocked = max(0.0, g["ms"] - run - rq)
                covered += g["ms"]
                ticks_u += b[2] - a[2]
                ticks_s += b[3] - a[3]
                minf += b[4] - a[4]
                majf += b[5] - a[5]
                blk += b[6] - a[6]
                acc["on CPU"] += run
                acc["run-queue wait"] += rq
                named = 0.0
                for cause, ms in g["host"].get(n, {}).items():
                    if cause in ("host submit", "host split"):  # host work, on CPU: not a blocked cause
                        acc["(of the CPU time: " + cause + ")"] += ms
                        continue
                    use = min(ms, blocked - named)
                    if use > 0:
                        acc["blocked: " + cause] += use
                        named += use
                rest = blocked - named
                if rest > 0:
                    lo_k, hi_k = bisect.bisect_left(times[i], g["end"] - g["ms"] / 1000), bisect.bisect_right(times[i], g["end"])
                    kinds = collections.Counter()
                    for s in samp[i][lo_k:hi_k]:
                        if s[9] == "run" or s[1] == "R":
                            continue
                        if s[1] == "D" or s[9] == "-1":
                            kinds["page fault or uninterruptible"] += 1
                        else:
                            kinds[SYS.get(s[9].split(":")[0], "other system call " + s[9].split(":")[0])] += 1
                    tk = sum(kinds.values())
                    if tk == 0:
                        acc["blocked: not sampled"] += rest
                    for kd, c in kinds.items():
                        acc["blocked, not a host stamp: " + kd] += rest * c / tk
            if covered <= 0:
                continue
            cpu = acc["on CPU"]
            tu = ticks_u + ticks_s
            line = f"   {n}: " + ", ".join(f"{k} {100 * v / covered:.1f} %" for k, v in acc.most_common() if not k.startswith("(of") and 100 * v / covered >= 0.5)
            print(line)
            sub = [f"{k[1:-1]} {100 * v / covered:.1f} %" for k, v in acc.items() if k.startswith("(of")]
            print(f"        on-CPU split by ticks: user {100 * ticks_u / tu if tu else 0:.0f} %, system {100 * ticks_s / tu if tu else 0:.0f} % ({tu} ticks at HZ {hz}; CPU {cpu / 1000:.1f} s)"
                  + (("; " + ", ".join(sub)) if sub else "") + f"; minor faults {minf}, major {majf}, block-I/O delay ticks {blk}")


if __name__ == "__main__":
    main()
