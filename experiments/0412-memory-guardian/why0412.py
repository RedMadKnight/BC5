#!/usr/bin/env python3
"""BC5 exp 0412 (README section 25): why the title's own code is slow in the play phase. One run's collectors joined:
  <p>-gaps.txt        the host's gap lines with BC5_GUARD_GAP_STAT=33 (every frame over 33 ms: journal t, monotonic, ms, host causes)
  <p>-frames.txt      every frame: journal t, ms since the last flip
  <p>-gapsamp.txt     20 ms samples of four threads (schedstat run / run-queue ns, ticks, faults, state, syscall)
  <p>-clock.txt.gz    perf cpu-clock 1 kHz, user space (tid time ip sym dso)
  <p>-faults.txt.gz   every page fault of the two threads (tid time addr ip sym dso), <p>-maps.txt.gz for the address classes
  <p>-stat.txt        perf stat -I 100 per thread; <p>.log has "stat starts at monotonic <s>"
  <p>-thr.txt         all threads every 250 ms (cpu, ticks, schedstat), MHz per core, temperature, other processes, affinity
Everything is restricted to the play phase [<load at> + 28 s, end) unless a line says otherwise.
usage: why0412.py <prefix p> [<load at s> default 104]"""
import bisect
import collections
import gzip
import os
import re
import statistics
import sys

GAP = re.compile(r"gap \(exp 0412, tag gp412\): t ([\d.]+) s mono ([\d.]+): ([\d.]+) ms since the last flip(.*)")
CL = re.compile(r"^\s*(\d+)\s+([\d.]+):\s+([0-9a-f]+)\s+(.*?)\s+\(([^()]*(?:\([^()]*\))?[^()]*)\)\s*$")
FL = re.compile(r"^\s*(\d+)\s+([\d.]+):\s+([0-9a-f]+)\s+.*?\s+\((\S+?(?: \(deleted\))?)\)\s+([0-9a-f]+)\s+(.*?)\s+\(([^()]*(?:\([^()]*\))?[^()]*)\)\s*$")


def kind(sym, dso):
    d = dso.rsplit("/", 1)[-1]
    if sym == "[unknown]" and "kyty" not in d and ".so" not in d:
        return "guest code"
    if "kyty_emulator" in d:
        if any(p in sym for p in ("Bc5Gc::", "bc5::", "Bc5Lle", "VideoOut")):
            return "host GPU path"
        if any(p in sym.lower() for p in ("signal", "sigsegv", "exception", "fault")):
            return "host signal / fault handler"
        return "host other (libkernel, loader, memory)"
    if d.startswith(("libc.", "libstdc++", "libm.", "ld-linux")):
        return "restore_rt (signal return)" if "restore_rt" in sym else "libc / libstdc++"
    return "other library"


def main():
    p = sys.argv[1]
    load_at = float(sys.argv[2]) if len(sys.argv) > 2 else 104.0
    P0 = load_at + 28
    gaps = []
    for ln in open(p + "-gaps.txt", errors="replace"):
        m = GAP.search(ln)
        if not m:
            continue
        host = {}
        for part in m.group(4).split(" | ")[1:]:
            name, _, rest = part.partition(":")
            host[name.strip()] = {c.strip().rsplit(" ", 1)[0]: float(c.strip().rsplit(" ", 1)[1]) for c in rest.split(",") if c.strip()}
        gaps.append((float(m.group(1)), float(m.group(2)), float(m.group(3)), host))
    off = statistics.median(g[1] - g[0] for g in gaps)
    frames = [(float(a), float(b)) for a, b, *_ in (ln.split() for ln in open(p + "-frames.txt") if ln.strip())]
    pf = [(t, ms) for t, ms in frames if t >= P0]
    t_end = pf[-1][0]
    play = sum(ms for _, ms in pf) / 1000
    over = [(t, ms) for t, ms in pf if ms > 33]
    over_s = sum(ms for _, ms in over) / 1000
    print(f"play phase {P0:.0f}-{t_end:.0f} s: {len(pf)} frames, {play:.1f} s, median {statistics.median(ms for _, ms in pf):.1f} ms, "
          f"p90 {sorted(ms for _, ms in pf)[int(len(pf) * 0.9)]:.1f} ms; frames over 33 ms: {len(over)} = {100 * over_s / play:.0f} % of the play time; clock offset {off:.3f}")
    M0, M1 = P0 + off, t_end + off
    # --- the 20 ms sampler
    names, samp = {}, collections.defaultdict(list)
    for ln in open(p + "-gapsamp.txt", errors="replace"):
        if ln.startswith("# gapsamp0412"):
            for i, n in re.findall(r"(\d+)=([^;\n]+)", ln.split("threads:")[1]):
                names[int(i)] = n.strip()
            continue
        q = ln.split()
        if len(q) >= 11 and not ln.startswith("#"):
            samp[int(q[1])].append((float(q[0]), q[2], int(q[3]), int(q[4]), int(q[5]), int(q[6]), int(q[8]), int(q[9]), q[10]))
    sched = {}
    for i, v in samp.items():
        w = [s for s in v if M0 <= s[0] <= M1]
        if len(w) < 2:
            continue
        a, b = w[0], w[-1]
        wall = b[0] - a[0]
        kinds = collections.Counter()
        for s in w:
            if s[8] == "run" or s[1] == "R":
                continue
            kinds["page fault / uninterruptible" if s[1] == "D" or s[8] == "-1" else {"202": "futex", "35": "sleep", "230": "sleep", "16": "ioctl", "0": "read", "17": "read"}.get(s[8].split(":")[0], "other syscall")] += 1
        sched[names[i]] = dict(wall=wall, run=(b[6] - a[6]) / 1e9, rq=(b[7] - a[7]) / 1e9, ut=b[2] - a[2], st=b[3] - a[3], minf=b[4] - a[4], majf=b[5] - a[5], kinds=kinds)
    # --- perf cpu-clock
    tids = {}
    log = open(p + ".log").read()
    m = re.search(r"threads (.*?) = ([\d,]+),", log)
    tl = m.group(2).split(",")
    tids[tl[0]], tids[tl[1]] = "Render Thread", "game-main"
    user = collections.defaultdict(collections.Counter)
    per_frame = {n: collections.Counter() for n in tids.values()}
    ends = [t + off for t, _ in frames]
    with gzip.open(p + "-clock.txt.gz", "rt", errors="replace") as f:
        for ln in f:
            m = CL.match(ln)
            if not m or m.group(1) not in tids:
                continue
            t = float(m.group(2))
            n = tids[m.group(1)]
            k = bisect.bisect_left(ends, t)
            if k < len(frames):
                per_frame[n][k] += 1
            if M0 <= t <= M1:
                user[n][kind(re.sub(r"\+0x[0-9a-f]+$", "", m.group(4).strip()), m.group(5))] += 1
    # --- the table: the Render Thread's and the main thread's play time by cause
    hostsum = collections.defaultdict(collections.Counter)
    for t, mono, ms, host in gaps:
        if t >= P0:
            for n, d in host.items():
                for c, v in d.items():
                    hostsum[n][c] += v / 1000
    for n in ("Render Thread", "game-main"):
        s = sched.get(n)
        if not s:
            continue
        w = s["wall"]
        u = user[n]
        usr = sum(u.values()) / 1000
        print(f"\n== {n}: play time by cause, % of {w:.1f} s  [on CPU {100 * s['run'] / w:.1f} %, run-queue wait {100 * s['rq'] / w:.1f} %, blocked {100 * (w - s['run'] - s['rq']) / w:.1f} %]")
        rows = [(k, v / 1000) for k, v in u.most_common()]
        rows.append(("kernel time on the CPU (on-CPU minus user-space samples: system calls, page faults)", max(0.0, s["run"] - usr)))
        rows.append(("run-queue wait", s["rq"]))
        blocked = w - s["run"] - s["rq"]
        named = 0.0
        for c, v in hostsum[n].most_common():
            if c in ("host submit", "host split"):
                continue
            rows.append(("blocked: " + c + " (host stamp, frames over 33 ms)", v))
            named += v
        rest = max(0.0, blocked - named)
        tk = sum(s["kinds"].values())
        for kd, c in s["kinds"].most_common():
            rows.append((f"blocked, no host stamp: {kd} (by the 20 ms samples)", rest * c / tk if tk else 0.0))
        for k, v in rows:
            if 100 * v / w >= 0.3:
                print(f"   {100 * v / w:5.1f} %  {k}")
        print(f"   ticks user {s['ut']} system {s['st']}; minor faults {s['minf']} ({s['minf'] / w:.0f}/s), major {s['majf']} ({s['majf'] / w:.1f}/s); "
              f"host scopes: submit {hostsum[n]['host submit']:.1f} s, split {hostsum[n]['host split']:.1f} s")
    # --- per-frame CPU histogram
    print("\n== frames of the play phase by length: count, mean ms; mean user-space CPU ms of the Render Thread and of the main thread in the frame")
    buckets = ((0, 33), (33, 50), (50, 80), (80, 100), (100, 1e9))
    for lo, hi in buckets:
        idx = [k for k, (t, ms) in enumerate(frames) if t >= P0 and lo < ms <= hi]
        if not idx:
            continue
        fm = statistics.mean(frames[k][1] for k in idx)
        r = statistics.mean(per_frame["Render Thread"][k] for k in idx)
        g = statistics.mean(per_frame["game-main"][k] for k in idx)
        print(f"   {lo:>4.0f}-{hi if hi < 1e8 else 0:<4.0f} ms: {len(idx):5d} frames, mean {fm:6.1f} ms; Render Thread {r:5.1f} ms ({100 * r / fm:.0f} %), main thread {g:5.1f} ms ({100 * g / fm:.0f} %)")
    # --- perf stat
    m = re.search(r"stat starts at monotonic ([\d.]+)", log)
    s0 = float(m.group(1))
    gap_iv = [(mono - ms / 1000, mono) for t, mono, ms, _ in gaps if ms > 100]
    gs = [g[0] for g in gap_iv]
    acc = collections.defaultdict(collections.Counter)
    for ln in open(p + "-stat.txt", errors="replace"):
        q = ln.strip().split(",")
        if len(q) < 5 or not q[0][:1].isdigit() or not q[2].isdigit():
            continue
        t = s0 + float(q[0])
        n = "Render Thread" if q[1].startswith("Render") else "game-main"
        tj = t - off
        ph = "play" if tj >= P0 and tj <= t_end else ("menu and list" if 62 <= tj < load_at else ("save load" if load_at <= tj < P0 else ("scene load" if 33 <= tj < 62 else None)))
        if ph is None:
            continue
        k = bisect.bisect_right(gs, t) - 1
        in_gap = k >= 0 and t - 0.05 <= gap_iv[k][1]
        acc[(n, ph, "all")][q[4]] += int(q[2])
        acc[(n, ph, "all")]["n"] += 1
        if ph == "play":
            acc[(n, ph, "in frames over 100 ms" if in_gap else "in the other frames")][q[4]] += int(q[2])
            acc[(n, ph, "in frames over 100 ms" if in_gap else "in the other frames")]["n"] += 1
    print("\n== hardware counters (user space; event counts per 8 events = 8 lines per interval): IPC, misses per 1,000 instructions, per second of wall clock")
    for key in sorted(acc):
        c = acc[key]
        ins, cyc = c["instructions:u"], c["cycles:u"]
        secs = c["n"] / 8 * 0.1
        if ins == 0 or secs == 0:
            continue
        print(f"   {key[0]:13s} {key[1]:13s} {key[2]:22s}: {secs:5.1f} s, cycles {cyc / secs / 1e9:.2f} G/s, IPC {ins / cyc:.2f}, dTLB load misses {1000 * c['dTLB-load-misses:u'] / ins:.2f}, "
              f"iTLB {1000 * c['iTLB-load-misses:u'] / ins:.3f}, cache misses {1000 * c['cache-misses:u'] / ins:.2f} per 1,000 instr")
    # --- page faults by address class and by who faults
    if os.path.exists(p + "-maps.txt.gz") and os.path.exists(p + "-faults.txt.gz"):
        ms_, me_, mc_ = [], [], []
        with gzip.open(p + "-maps.txt.gz", "rt", errors="replace") as f:
            for ln in f:
                q = ln.split(None, 5)
                a, b = q[0].split("-")
                path = q[5].strip() if len(q) > 5 else ""
                cls = ("guest direct memory (memfd:KytyDirect)" if "KytyDirect" in path else "guest private memory (memfd:KytyPrivate)" if "KytyPrivate" in path else
                       "other memfd" if "memfd:" in path else "host heap" if path == "[heap]" else "stack" if path.startswith("[stack") else
                       "host anonymous" if path == "" else "file mapping (" + path.rsplit("/", 1)[-1][:24] + ")")
                ms_.append(int(a, 16)); me_.append(int(b, 16)); mc_.append(cls + (" writable" if "w" in q[1] else " read-only"))
        fc = collections.defaultdict(collections.Counter)
        fi = collections.defaultdict(collections.Counter)
        nf = collections.Counter()
        with gzip.open(p + "-faults.txt.gz", "rt", errors="replace") as f:
            for ln in f:
                m = FL.match(ln)
                if not m or m.group(1) not in tids:
                    continue
                t = float(m.group(2))
                if not (M0 <= t <= M1):
                    continue
                n = tids[m.group(1)]
                a = int(m.group(3), 16)
                k = bisect.bisect_right(ms_, a) - 1
                ad = m.group(4)
                fc[n][mc_[k] if k >= 0 and a < me_[k] else ("not in the maps snapshot: " + ad.rsplit("/", 1)[-1][:30])] += 1
                sym = re.sub(r"\+0x[0-9a-f]+$", "", m.group(6).strip())
                fi[n]["guest code" if kind(sym, m.group(7)) == "guest code" else sym[:70] if sym != "[unknown]" else "(kernel or no symbol)"] += 1
                nf[n] += 1
        print("\n== page faults in the play phase: by the memory they hit, and by the code that faulted")
        for n in nf:
            w = M1 - M0
            print(f"   {n}: {nf[n]} faults, {nf[n] / w:.0f}/s")
            print("      memory: " + "; ".join(f"{k} {100 * v / nf[n]:.0f} %" for k, v in fc[n].most_common(6)))
            print("      code:   " + "; ".join(f"{k} {100 * v / nf[n]:.0f} %" for k, v in fi[n].most_common(6)))
    # --- threads, cores, frequency
    if os.path.exists(p + "-thr.txt"):
        T = collections.defaultdict(list)
        F, K, N, sib, hz = [], [], {}, [], 100
        procs = collections.defaultdict(list)
        for ln in open(p + "-thr.txt", errors="replace"):
            q = ln.split()
            if ln.startswith("# thr0412"):
                sib = ln.split("siblings")[1].split()
            elif q and q[0] == "T" and len(q) >= 8:
                T[q[2]].append((float(q[1]), int(q[3]), int(q[4]) + int(q[5]), int(q[6]), int(q[7])))
            elif q and q[0] == "F":
                F.append((float(q[1]), [int(x) for x in q[2:]]))
            elif q and q[0] == "K":
                K.append((float(q[1]), int(q[2])))
            elif q and q[0] == "N":
                left, _, comm = ln.partition("|")
                l = left.split()
                N[l[1]] = (comm.strip(), l[2], l[3], l[4], l[5], l[6])
            elif q and q[0] == "P":
                procs[q[2] + " " + " ".join(q[4:])].append((float(q[1]), int(q[3])))
        core_of = {}
        for i, s in enumerate(sib):
            for c in re.split("[-,]", s):
                core_of[int(c)] = i
        rows, tot = [], 0.0
        hot_by_tick = collections.defaultdict(list)
        for tid, v in T.items():
            w = [s for s in v if M0 <= s[0] <= M1]
            if len(w) < 8:
                continue
            wall = M1 - M0  # a thread that lived for a part of the phase counts by the whole phase
            run = (w[-1][3] - w[0][3]) / 1e9
            rq = (w[-1][4] - w[0][4]) / 1e9
            cpus = collections.Counter(s[1] for s in w)
            tot += run
            rows.append((100 * run / wall, 100 * rq / wall, tid, len(cpus), cpus.most_common(1)[0]))
            for a, b in zip(w, w[1:]):
                if (b[3] - a[3]) / 1e9 >= 0.5 * (b[0] - a[0]):
                    hot_by_tick[round(b[0], 1)].append(b[1])
        rows.sort(reverse=True)
        wall = M1 - M0
        print(f"\n== threads in the play phase: all the emulator's threads together use {100 * tot / wall:.0f} % of one CPU ({tot / wall:.1f} of 16 logical CPUs, 8 cores)")
        print("   CPU %  run-queue %  thread (policy, rt priority, priority, nice, CPUs allowed)  logical CPUs it ran on")
        for cpu, rq, tid, ncpu, top in rows[:22]:
            nm = N.get(tid, ("?", "?", "?", "?", "?", "?"))
            print(f"   {cpu:5.1f}  {rq:5.1f}  {nm[0]:18s} (policy {nm[1]}, rt {nm[2]}, prio {nm[3]}, nice {nm[4]}, allowed {nm[5]})  {ncpu} CPUs, most on cpu{top[0]} ({100 * top[1] / sum(c for c in [top[1]]) :.0f} samples)")
        share = both = 0
        for tick, cpus in hot_by_tick.items():
            if len(cpus) >= 2:
                both += 1
                cores = [core_of.get(c, c) for c in cpus]
                if len(set(cores)) < len(cores):
                    share += 1
        print(f"   ticks of 250 ms with two or more threads over 50 % CPU: {both}; in {share} of them ({100 * share / both if both else 0:.0f} %) two such threads were on the two logical CPUs of one core")
        by = collections.Counter()
        for cpu, rq, tid, ncpu, top in rows:
            nm = N.get(tid, ("?",))[0]
            by["host threads (bc5-*, kyty-*, mangohud)" if nm.startswith(("bc5-", "kyty", "mangohud", "kyty_emulator")) else "the title's threads"] += cpu
        print("   " + "; ".join(f"{k}: {v:.0f} % of one CPU" for k, v in by.items()))
        pr = []
        for k, v in procs.items():
            w = [s for s in v if M0 - 5 <= s[0] <= M1 + 5]
            if len(w) >= 2:
                pr.append((100 * (w[-1][1] - w[0][1]) / hz / (w[-1][0] - w[0][0]), k))
        pr.sort(reverse=True)
        print("   other processes in the play phase, % of one CPU: " + "; ".join(f"{k.split(' ', 1)[1]} {c:.1f}" for c, k in pr[:8]))
        fw = [f for t, f in F if M0 <= t <= M1]
        if fw:
            allv = sorted(x for f in fw for x in f)
            print(f"\n== CPU clock in the play phase (/proc/cpuinfo, {len(fw)} readings of {len(fw[0])} logical CPUs): min {allv[0]} MHz, median {allv[len(allv) // 2]}, max {allv[-1]}; "
                  f"readings under 3,000 MHz: {100 * sum(1 for x in allv if x < 3000) / len(allv):.0f} %")
        kw = [k for t, k in K if M0 <= t <= M1]
        if kw:
            print(f"   k10temp: {min(kw) / 1000:.0f}-{max(kw) / 1000:.0f} C")


if __name__ == "__main__":
    main()
