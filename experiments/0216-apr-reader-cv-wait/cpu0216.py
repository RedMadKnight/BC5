#!/usr/bin/env python3
# BC5 experiment 0216: the APR threads' CPU per sampling interval (about 10 s) from cpu0214.sh / cpu0216.sh files.
# For each interval: the readers' (bc5-apr-r*) and the workers' (bc5-apr-q*) run time, and, where the file has whole
# schedstat lines (cpu0216.sh), the readers' wake-ups (times run on a CPU). "Quiet" intervals are those in which the
# workers ran under 10 ms (the queues idle; exp 0214's definition): there the readers' CPU is their idle cost.
# usage: cpu0216.py <label>=<cpu file> ...
import sys


def load(path):
    samples = []  # (uptime, {thread: (run_ns, pcount or None)})
    cur_t, cur = None, {}
    for line in open(path, encoding="utf-8", errors="replace"):
        f = line.split()
        if not f or f[0] != "t" or len(f) < 4:
            continue
        t = float(f[1])
        if cur_t is not None and t != cur_t:
            samples.append((cur_t, cur))
            cur = {}
        cur_t = t
        v = (int(f[3]), int(f[5]) if len(f) >= 6 else None)
        # Threads a worker starts inherit its name (S1L had six short-lived "bc5-apr-q3" at once): keep the longest-run
        # thread of each name, the named one.
        if f[2] not in cur or v[0] > cur[f[2]][0]:
            cur[f[2]] = v
    if cur:
        samples.append((cur_t, cur))
    return samples


def report(label, path):
    s = load(path)
    rows = []
    for (t0, a), (t1, b) in zip(s, s[1:]):
        dt = t1 - t0
        r_ns = w_ns = 0
        r_wake = 0
        has_wake = True
        nr = 0
        for n, (ns, pc) in b.items():
            if n not in a:
                continue
            d = ns - a[n][0]
            if n.startswith("bc5-apr-r"):
                r_ns += d
                nr += 1
                if pc is None or a[n][1] is None:
                    has_wake = False
                else:
                    r_wake += pc - a[n][1]
            elif n.startswith("bc5-apr-q"):
                w_ns += d
        rows.append((t1 - s[0][0], dt, nr, r_ns / 1e6, w_ns / 1e6, r_wake if has_wake else None))
    print(f"== {label}: {path}")
    print(f"   {len(s)} samples, {len(rows)} intervals, {s[-1][0] - s[0][0]:.0f} s")
    tot_r = sum(r[3] for r in rows)
    tot_w = sum(r[4] for r in rows)
    span = sum(r[1] for r in rows)
    print(f"   readers {tot_r / 1e3:.2f} s ({100 * tot_r / 1e3 / span:.2f} % of one core), "
          f"workers {tot_w / 1e3:.2f} s ({100 * tot_w / 1e3 / span:.2f} %) over {span:.0f} s")
    quiet = [r for r in rows if r[4] < 10.0]
    if quiet:
        q = sorted(r[3] * 10.0 / r[1] for r in quiet)  # ms per 10 s
        print(f"   quiet intervals (workers < 10 ms): {len(quiet)}; readers' CPU per 10 s: min {q[0]:.2f}, "
              f"median {q[len(q) // 2]:.2f}, max {q[-1]:.2f} ms ({100 * q[len(q) // 2] / 1e4:.3f} % of one core at the median)")
        wk = [r[5] * 1.0 / r[1] for r in quiet if r[5] is not None]
        if wk:
            wk.sort()
            print(f"   quiet intervals: readers' wake-ups per second (all readers): min {wk[0]:.1f}, "
                  f"median {wk[len(wk) // 2]:.1f}, max {wk[-1]:.1f}")
    allw = [r[5] / r[1] for r in rows if r[5] is not None]
    if allw:
        print(f"   all intervals: readers' wake-ups per second: mean {sum(allw) / len(allw):.1f}, max {max(allw):.1f}")
    print("   t(s)   dt  readers  readers ms  workers ms  reader wake-ups")
    for r in rows:
        print(f"   {r[0]:5.0f} {r[1]:4.1f} {r[2]:8d} {r[3]:11.2f} {r[4]:11.2f} {'' if r[5] is None else r[5]:>16}")


for arg in sys.argv[1:]:
    label, path = arg.split("=", 1)
    report(label, path)
