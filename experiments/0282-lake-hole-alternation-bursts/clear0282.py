#!/usr/bin/env python3
# BC5 experiment 0282: ana0282.py's output regrouped by how clearly each read's size was found. The depth image's own
# block-row shear often leaves two sizes close (e.g. 2560 at 1.31, 2304 at 1.41), and a read decoded at the wrong size
# gives a meaningless depth-0 set. A read counts as clear when its next-best size's shear is >= R times its best
# (default 3). Lists the clear reads (size, depth-0 share, phi with the burst's G-buffer read) and the pairs of a burst
# grouped by whether both reads are clear and of one size. Reads only the summary file (no title data).
# usage: python3 -I clear0282.py <W282a.ana.txt> [R]
import re, statistics, sys

path, R = sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
reads, gsize, rows = {}, {}, []
b = st = None
for l in open(path, encoding="utf-8"):
    m = re.match(r"== (b\d+) at \S+ (\S+)", l)
    if m:
        b, st = m[1], m[2]
        continue
    m = re.match(r"\s+g\s+start\s+([\d.]+).*size (\d+)x\d+ \(shear ([\d.]+), next (\d+) at ([\d.]+)\); cleared ([\d.]+)", l)
    if m:
        gsize[b] = (int(m[2]), float(m[5]) / max(float(m[3]), 1e-9))
        continue
    m = re.match(r"\s+(z\d)\s+start\s+([\d.]+) read\s+([\d.]+) ms: size (\d+)x\d+ \(shear ([\d.]+), next (\d+) at ([\d.]+)\)(?: INCOMPLETE)?; depth 0 ([\d.]+).*phi with G-buffer cleared ([+-][\d.]+|\+nan)", l)
    if m:
        reads[(b, m[1])] = dict(t=float(m[2]), w=int(m[4]), ratio=float(m[7]) / max(float(m[5]), 1e-9), d0=float(m[8]),
                                gphi=float(m[9]) if "nan" not in m[9] else float("nan"), st=st)
        continue
    m = re.match(r"\s+pair (z\d)-(z\d) lag\s+([\d.]+) ms sizes (\d+)/(\d+): of \S+ depth-0 pixels ([\d.]+) are depth 0 in \S+; phi ([+-][\d.]+|\+nan)", l)
    if m:
        rows.append((b, m[1], m[2], float(m[3]), int(m[4]), int(m[5]), float(m[6]), float(m[7]) if "nan" not in m[7] else float("nan")))
clear = lambda k: reads[k]["ratio"] >= R
print("# reads: %d, clear (next >= %.1f x best): %d" % (len(reads), R, sum(clear(k) for k in reads)))
print("# clear reads: burst read size depth-0 share, phi with the burst's G-buffer read (its size, clear?)")
for k in sorted(reads):
    if clear(k):
        r = reads[k]
        g = gsize.get(k[0], (0, 0))
        print("  %s %s %d depth-0 %.3f phi-G %+.3f (G %d%s)" % (k[0], k[1], r["w"], r["d0"], r["gphi"], g[0], "" if g[1] >= R else " unclear"))
groups = {}
for b, i, j, lag, wi, wj, kept, p in rows:
    if p != p:
        continue
    ci, cj = clear((b, i)), clear((b, j))
    key = ("both clear" if ci and cj else "one or none clear") + (", same size" if wi == wj else ", different sizes")
    groups.setdefault(key, []).append((lag, p, kept, b, i, j, wi, wj))
for key in sorted(groups):
    g = sorted(groups[key])
    ps = [x[1] for x in g]
    print("# %s: %d pairs, phi median %+.3f, range %+.3f..%+.3f" % (key, len(g), statistics.median(ps), min(ps), max(ps)))
    if key.startswith("both clear"):
        for lag, p, kept, b, i, j, wi, wj in g:
            print("    %s %s-%s lag %6.1f ms %d/%d phi %+.3f kept %.3f" % (b, i, j, lag, wi, wj, p, kept))
