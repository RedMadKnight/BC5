#!/usr/bin/env python3
"""BC5 exp 0412 (README section 51): what the learned windows are, read from one run's journal.

usage: learnclass0412.py <learned file> <journal (gc/direct.log)> [more journals]

Reads only. For every window "0x<lo> 0x<bytes>" of the learned file it sums what the host's own journal
lines say the window brought in during the run (the lines of map_window and scratch_fill in the unit):
  "learned 0x..: window 0x..+0x.., direct memory +N MiB"   chunks of the direct/private file under views, forced
  "learned 0x..: window 0x..+0x.., mapped +N MiB"          anonymous rw VMAs handed over as userptr
  "scratch: window 0x..+0x.., N MiB of holes get a zero buffer"   addresses with no guest range
Limits: "direct memory" counts every chunk under a view in the window that no earlier window or hint had
forced, whether or not it would have been imported anyway (data, eager heap), so it is an upper bound of
what the window adds; scratch lines repeat when a hole is given back and filled again (the highest single
value per window is kept, and the count of lines). Windows are also grouped by where they lie.
"""
import re
import sys

MIB = 1048576.0


def region(lo, n):
    hi = lo + n
    if lo >= 1 << 47:
        return "beyond 2^47 (garbage address)"
    if lo >> 40:
        return "address byte 47:40 set"
    if hi <= 0x100000000:
        return "below 4 GiB (address 0 and modules)"
    if 0x8000000000 <= lo < 0x9000000000:
        return "AMM window 0x80..."
    return "0x%02x00000000 block" % (lo >> 32)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    wins = []
    with open(sys.argv[1]) as f:
        for line in f:
            p = line.split()
            if len(p) == 2:
                wins.append((int(p[0], 16), int(p[1], 16)))
    wins = sorted(set(wins))
    stat = {w: {"direct": 0.0, "userptr": 0.0, "scratch": 0.0, "scratch_lines": 0} for w in wins}
    re_d = re.compile(r"learned 0x[0-9a-f]+: window 0x([0-9a-f]+)\+0x([0-9a-f]+), direct memory \+([0-9.]+) MiB")
    re_m = re.compile(r"learned 0x[0-9a-f]+: window 0x([0-9a-f]+)\+0x([0-9a-f]+), mapped \+([0-9.]+) MiB")
    re_s = re.compile(r"scratch: window 0x([0-9a-f]+)\+0x([0-9a-f]+), ([0-9.]+) MiB of holes")
    re_a = re.compile(r"learned apply: ([0-9.]+) ms")
    re_n = re.compile(r"learned: fault 0x([0-9a-f]+) -> region")
    applies, apply_ms, new, other_scratch = 0, 0.0, [], 0.0
    for path in sys.argv[2:]:
        with open(path, errors="replace") as f:
            for line in f:
                if "learned" not in line and "scratch" not in line:
                    continue
                m = re_d.search(line)
                if m:
                    w = (int(m.group(1), 16), int(m.group(2), 16))
                    if w in stat:
                        stat[w]["direct"] += float(m.group(3))
                    continue
                m = re_m.search(line)
                if m:
                    w = (int(m.group(1), 16), int(m.group(2), 16))
                    if w in stat:
                        stat[w]["userptr"] += float(m.group(3))
                    continue
                m = re_s.search(line)
                if m:
                    w = (int(m.group(1), 16), int(m.group(2), 16))
                    if w in stat:
                        stat[w]["scratch"] = max(stat[w]["scratch"], float(m.group(3)))
                        stat[w]["scratch_lines"] += 1
                    else:
                        other_scratch += float(m.group(3))
                    continue
                m = re_a.search(line)
                if m:
                    applies += 1
                    apply_ms += float(m.group(1))
                    continue
                m = re_n.search(line)
                if m:
                    new.append(int(m.group(1), 16))
    # the union of the windows in bytes
    union, end = 0, -1
    for lo, n in wins:
        a, b = max(lo, end), lo + n
        if b > a:
            union += b - a
            end = b
    print("windows on file: %d, their union %.0f MiB of address space" % (len(wins), union / MIB))
    groups = {}
    for (lo, n), s in stat.items():
        g = groups.setdefault(region(lo, n), [0, 0.0, 0.0, 0.0, 0])
        g[0] += 1
        g[1] += s["direct"]
        g[2] += s["userptr"]
        g[3] += s["scratch"]
        g[4] += 1 if (s["direct"] == 0 and s["userptr"] == 0 and s["scratch"] == 0) else 0
    print("%-36s %7s %12s %12s %12s %10s" % ("where", "windows", "direct MiB", "userptr MiB", "scratch MiB", "brought 0"))
    for k in sorted(groups):
        g = groups[k]
        print("%-36s %7d %12.1f %12.1f %12.1f %10d" % (k, g[0], g[1], g[2], g[3], g[4]))
    t = [sum(s[k] for s in stat.values()) for k in ("direct", "userptr", "scratch")]
    print("%-36s %7d %12.1f %12.1f %12.1f" % ("all", len(wins), t[0], t[1], t[2]))
    print("scratch outside learned windows (the 2 MiB guards after eager heaps and others): %.1f MiB" % other_scratch)
    print("learned apply lines over 5 ms: %d, %.1f ms in all" % (applies, apply_ms))
    print("new faults learned in these journals: %d %s" % (len(new), " ".join("0x%x" % a for a in new[:20])))
    print()
    print("per window: lo size direct userptr scratch(scratch lines)")
    for (lo, n), s in sorted(stat.items()):
        print("0x%012x 0x%x %8.1f %8.1f %8.1f (%d)" % (lo, n, s["direct"], s["userptr"], s["scratch"], s["scratch_lines"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
