#!/usr/bin/env python3
# BC5 experiment 0205: the AMM trace of a play log (KYTY_BC5_AMM_TRACE=1). (1) Maps, unmaps and package reads per
# 10 s of wall time. (2) Every automatic map still live at the end, by protection: is it covered by package reads
# logged after it (full / part / none)? Trace lines from the parallel APR workers can lose their "mono" prefix to a
# neighbouring line, so (2) orders by line number in the log, not by timestamp.
# usage: python3 -I amm0205.py <play log> <boot time, s since the epoch (btime in /proc/stat)>
import bisect, collections, re, sys, time

bt = int(sys.argv[2])
maps, reads, per10 = {}, [], collections.defaultdict(collections.Counter)
for n, line in enumerate(open(sys.argv[1], errors="replace")):
    if "amm trace:" not in line:
        continue
    m = re.search(r"mono ([\d.]+)", line)
    t = float(m[1]) if m else None
    k = None
    if "map auto va" in line:
        g = re.search(r"va 0x([0-9a-f]+) size 0x([0-9a-f]+).*prot 0x([0-9a-f]+)", line)
        maps[int(g[1], 16)] = (int(g[2], 16), n, g[3])
        k = "map"
    elif "amm trace: unmap va" in line:
        g = re.search(r"va 0x([0-9a-f]+) size 0x([0-9a-f]+)", line)
        va, sz = int(g[1], 16), int(g[2], 16)
        for x in [x for x in maps if va <= x < va + sz]:
            maps.pop(x)
        k = "unmap"
    elif "read file" in line or "read into the AMM window" in line:
        g = re.search(r"size 0x([0-9a-f]+) -> 0x([0-9a-f]+)", line)
        if g:
            reads.append((int(g[2], 16), int(g[1], 16), n))
        k = "read"
    if k and t is not None:
        per10[int(t // 10) * 10][k] += 1
print("(1) per 10 s: wall maps unmaps reads")
for s in sorted(per10):
    c = per10[s]
    print("  %s %5d %5d %5d" % (time.strftime("%H:%M:%S", time.localtime(bt + s)), c["map"], c["unmap"], c["read"]))
reads.sort()
ra = [r[0] for r in reads]
res, resb = collections.Counter(), collections.Counter()
for va, (sz, n, prot) in maps.items():
    i = bisect.bisect_left(ra, va - (64 << 20))
    cov = []
    while i < len(reads) and reads[i][0] < va + sz:
        a, s, rn = reads[i]
        if a < va + sz and va < a + s and rn > n:
            cov.append((max(a, va), min(a + s, va + sz)))
        i += 1
    cov.sort()
    got, end = 0, va
    for a, b in cov:
        if b > end:
            got += b - max(a, end)
            end = b
    cls = "full" if got >= sz else ("none" if got == 0 else "part")
    res[(prot, cls)] += 1
    resb[(prot, cls)] += sz
print("(2) automatic maps live at the end, covered by later package reads:")
for k in sorted(res):
    print("  prot 0x%s %-4s %6d maps %8.1f MiB" % (k[0], k[1], res[k], resb[k] / 2**20))
