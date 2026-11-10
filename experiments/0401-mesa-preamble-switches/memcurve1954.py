# BC5 hang1954-0401.md: the memory curve of a play: the journal's "memory (exp 0401)" lines (every 10 s) with the
# flips per second of the launcher's fps counter over the same 10 s. The launcher's clock runs ahead of the journal's by
# <offset> s (1.95 s for the 19:47 play, fitted on its 12,753 journal flip lines). Numbers only.
# usage: python -I memcurve1954.py <memory lines> <launcher play-last log> <offset s> [<every s, default 60>]
import re
import sys


def main(mem, launcher, off, every):
    fps = []
    for line in open(launcher, errors="replace"):
        m = re.match(r"fps counter: t ([\d.]+) s: (\d+) flips in ([\d.]+) s", line)
        if m:
            fps.append((float(m.group(1)) - off, int(m.group(2)), float(m.group(3))))
    rows = []
    for line in open(mem, errors="replace"):
        m = re.match(r"memory \(exp 0401\): t ([\d.]+) s: available (\d+) MiB, swap used (\d+) MiB, psi some ([\d.]+) full ([\d.]+) .*full total (\d+) ms, gtt (\d+) of", line)
        if m:
            rows.append((float(m.group(1)),) + tuple(m.group(k) for k in range(2, 8)))
    print("| t (journal, s) | available MiB | swap used MiB | GTT MiB | PSI some/full avg10 % | PSI full total ms | flips/s (10 s) |")
    print("|---|---|---|---|---|---|---|")
    last = None
    for k, (t, av, sw, some, full, tot, gtt) in enumerate(rows):
        win = [(n, w) for e, n, w in fps if t - 10 < e <= t]
        f = "%.1f" % (sum(n for n, _ in win) / sum(w for _, w in win)) if win else "-"
        if k == 0 or k == len(rows) - 1 or t >= (last or 0) + every - 0.01:
            print("| %.0f | %s | %s | %s | %s / %s | %s | %s |" % (t, av, sw, gtt, some, full, tot, f))
            last = t
    if rows:
        print("min available %s MiB at t %.0f; max swap %s MiB; max PSI full avg10 %s %%" % (
            min(rows, key=lambda r: int(r[1]))[1], min(rows, key=lambda r: int(r[1]))[0], max(int(r[2]) for r in rows),
            max(float(r[4]) for r in rows)))
    tail = [(e, n, w) for e, n, w in fps if rows and e > rows[-1][0]]
    if tail:
        print("after the last memory line: " + ", ".join("t %.1f %d flips/%.2fs" % x for x in tail[-6:]))


if __name__ == "__main__":
    a = sys.argv
    main(a[1], a[2], float(a[3]), float(a[4]) if len(a) > 4 else 60.0)
