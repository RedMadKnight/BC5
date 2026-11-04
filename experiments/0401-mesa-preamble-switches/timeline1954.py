# BC5 hang1954-0401.md: a per-interval timeline of a direct.log (and optionally the launcher log's fps counter) over a
# window: flips, frame-profile gaps, buffers submitted, CPU-served label waits given up, jobs whose fence took long, slow
# posts, memory lines. Counts and times only; no buffer contents.
# usage: python -I timeline1954.py <direct.log> <t0> <t1> [<step s, default 1>] [<launcher play-last log>]
import re
import sys


def main(path, t0, t1, step, launcher):
    nb = int((t1 - t0) / step) + 1
    rows = [dict(flip=0, dcb=0, acb=0, dw=0, giveup=0, giveup_ms=0.0, longfence=[], gap=0.0, slow=[], mem="") for _ in range(nb)]
    t_last = None
    pend_wait = None

    def row(t):
        k = int((t - t0) / step)
        return rows[k] if 0 <= k < nb else None

    for line in open(path, errors="replace"):
        m = re.match(r"timing: t ([\d.]+) s (dcb|acb) (\d+) dwords: sync", line)
        if m:
            t_last = float(m.group(1))
            r = row(t_last)
            if r:
                r[m.group(2)] += 1
                r["dw"] += int(m.group(3))
            continue
        m = re.match(r"timing: t ([\d.]+) s flip", line)
        if m:
            t_last = float(m.group(1))
            r = row(t_last)
            if r:
                r["flip"] += 1
            continue
        m = re.match(r"cpu-wait \S+ at \d+ on \S+: GIVEN UP after ([\d.]+) ms", line)
        if m:
            pend_wait = float(m.group(1))
            continue
        m = re.match(r"timing: t ([\d.]+) s after that wait", line)
        if m:
            t_last = float(m.group(1))
            r = row(t_last)
            if r and pend_wait is not None:
                r["giveup"] += 1
                r["giveup_ms"] += pend_wait
            pend_wait = None
            continue
        m = re.match(r"timing: #(\d+) done at t ([\d.]+) s, ([\d.]+) ms after the sync and hints; .*fence ([\d.]+) ms", line)
        if m:
            r = row(float(m.group(2)))
            if r and float(m.group(4)) >= 50:
                r["longfence"].append("#%s %.0f" % (m.group(1), float(m.group(4))))
            continue
        m = re.match(r"frame profile: t ([\d.]+) s, ([\d.]+) ms since the last flip", line)
        if m:
            r = row(float(m.group(1)))
            if r:
                r["gap"] = max(r["gap"], float(m.group(2)))
            continue
        m = re.match(r"slow post: t ([\d.]+) s (\S+) ([\d.]+) ms", line)
        if m:
            r = row(float(m.group(1)))
            if r:
                r["slow"].append("%s %s" % (m.group(2), m.group(3)))
            continue
        m = re.match(r"memory \(exp 0401\): t ([\d.]+) s: available (\d+) MiB, swap used (\d+) MiB, psi some ([\d.]+) full ([\d.]+).*gtt (\d+) of", line)
        if m:
            r = row(float(m.group(1)))
            if r:
                r["mem"] = "avail %s swap %s psi %s/%s gtt %s" % m.group(2, 3, 4, 5, 6)
    fps = {}
    if launcher:
        for line in open(launcher, errors="replace"):
            m = re.match(r"fps counter: t ([\d.]+) s: (\d+) flips in ([\d.]+) s, longest gap ([\d.]+) ms", line)
            if m and t0 <= float(m.group(1)) <= t1 + step:
                fps[float(m.group(1))] = "%s flips/%ss (gap %s)" % (m.group(2), m.group(3), m.group(4))
    print("t        flips dcb acb  kdw  waits-given-up(ms)  frame gap  long fences (>=50 ms) | slow posts | memory")
    for k, r in enumerate(rows):
        t = t0 + k * step
        print("%7.2f  %4d %4d %3d %5d  %3d (%6.1f)  %8.1f  %s %s %s" % (t, r["flip"], r["dcb"], r["acb"], r["dw"] // 1000, r["giveup"], r["giveup_ms"],
              r["gap"], " ".join(r["longfence"]) or "-", ("| " + " ".join(r["slow"])) if r["slow"] else "", ("| " + r["mem"]) if r["mem"] else ""))
    for t in sorted(fps):
        print("launcher fps counter at %.3f: %s" % (t, fps[t]))


if __name__ == "__main__":
    a = sys.argv
    main(a[1], float(a[2]), float(a[3]), float(a[4]) if len(a) > 4 else 1.0, a[5] if len(a) > 5 else None)
