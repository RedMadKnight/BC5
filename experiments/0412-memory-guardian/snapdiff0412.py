#!/usr/bin/env python3
"""BC5 exp 0412 (README section 24): two whole-box memory snapshots (snap0412.sh) side by side, the lines that moved.
For the block of each file nearest to <second>: /proc/meminfo (MiB), the processes by name (anon + shmem + swap,
MiB), the cgroups' memory.current (MiB), the GPU counters, zram. Printed: every line that differs by <min MiB> or more.
usage: snapdiff0412.py <old snap> <new snap> [<second> default 130] [<min MiB> default 15]"""
import sys


def block(path, sec):
    blocks, cur = [], None
    for ln in open(path, errors="replace"):
        if ln.startswith("######## snapshot at "):
            cur = [int(ln.split()[3]), []]
            blocks.append(cur)
        elif cur is not None:
            cur[1].append(ln.rstrip("\n"))
    assert blocks, path
    t, lines = min(blocks, key=lambda b: abs(b[0] - sec))
    out, sect = {}, ""
    for ln in lines:
        if ln.startswith("## "):
            sect = ln[3:].split(" (")[0].split(":")[0].strip()
            continue
        p = ln.split()
        if not p:
            continue
        if sect == "meminfo" and len(p) >= 2 and p[1].isdigit():
            out["meminfo " + p[0].rstrip(":")] = int(p[1]) / 1024
        elif sect.startswith("processes by name") and len(p) >= 7:
            out["process " + p[0] + " (anon+shmem+swap)"] = (int(p[2]) + int(p[4]) + int(p[5])) / 1024
        elif sect.startswith("cgroups") and len(p) >= 2 and p[1].isdigit():
            out["cgroup " + (p[0] or "/")[-70:]] = int(p[1]) / 1048576
        elif sect.startswith("gpu") and not sect.startswith("gpu clients") and len(p) == 2 and p[1].isdigit():
            out["gpu " + p[0]] = int(p[1]) / 1048576
        elif sect.startswith("zram") and len(p) >= 3:
            out["zram stored (orig)"], out["zram memory used"] = int(p[0]) / 1048576, int(p[2]) / 1048576
        elif sect.startswith("emulator smaps by class") and len(p) >= 8:
            out["emulator smaps " + p[0] + " rss"] = int(p[3]) / 1024
            out["emulator smaps " + p[0] + " swap"] = int(p[6]) / 1024
    return t, out


def main():
    sec = int(sys.argv[3]) if len(sys.argv) > 3 else 130
    lim = float(sys.argv[4]) if len(sys.argv) > 4 else 15.0
    (ta, a), (tb, b) = block(sys.argv[1], sec), block(sys.argv[2], sec)
    print(f"old at {ta} s, new at {tb} s; lines that differ by {lim:.0f} MiB or more (MiB: old, new, new - old)")
    rows = [(k, a.get(k, 0.0), b.get(k, 0.0)) for k in sorted(set(a) | set(b))]
    for k, x, y in sorted(rows, key=lambda r: -abs(r[2] - r[1])):
        if abs(y - x) >= lim:
            print(f"  {k:72s} {x:9.0f} {y:9.0f} {y - x:+8.0f}")
    for k in ("meminfo MemAvailable", "meminfo MemFree", "meminfo SwapFree", "meminfo Cached", "meminfo Shmem", "meminfo Slab", "meminfo AnonPages"):
        print(f"  = {k:70s} {a.get(k, 0):9.0f} {b.get(k, 0):9.0f} {b.get(k, 0) - a.get(k, 0):+8.0f}")


if __name__ == "__main__":
    main()
