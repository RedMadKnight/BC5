#!/usr/bin/env python3
# BC5 experiment 0333: the zero map's counts per heap and scan, from a run's raw/<tag>-zeromap.txt (the journal's "zero map"
# lines), and per heap the chunks whose class changed between the first and the last scan.
# usage: table0333.py <tag>-zeromap.txt
import re, sys
from collections import defaultdict

HEAD = re.compile(r"zero map \(exp 0333\) scan (\d+) at (\d+) s, (\S+) \((\d+) views, (\d+) chunks\): zero (\d+) MiB \(unforced (\d+), "
                  r"learned (\d+), hint only (\d+)\), data (\d+), not read (\d+); since the last scan (\d+) chunks left the zero set and "
                  r"(\d+) became zero; zero and unforced in every scan so far (\d+) MiB in (\d+) runs \(the largest (\d+) MiB; (\d+) MiB in runs")
ROW = re.compile(r"zero map (\d+) (\S+) +\+ *(\d+) MiB (\S+)$")
heads, maps = [], defaultdict(lambda: defaultdict(str))
for line in open(sys.argv[1], encoding="utf-8", errors="replace"):
    line = line.rstrip("\n")
    m = HEAD.match(line)
    if m:
        heads.append(m.groups())
        continue
    m = ROW.match(line)
    if m:
        maps[m.group(2)][int(m.group(1))] += m.group(4)
print("heap                     scan   t[s] | zero MiB  unforced learned hint | data | left  became | always-zero-unforced MiB runs largest >=8MiB")
for g in heads:
    k, t, name, v, c, z, u, l, h, d, nr, left, became, al, runs, big1, big8 = g
    print(f"{name:24} {k:>4} {t:>6} | {z:>8} {u:>9} {l:>7} {h:>4} | {d:>4} | {left:>4} {became:>7} | {al:>24} {runs:>4} {big1:>7} {big8:>6}")
for name, by in maps.items():
    ks = sorted(by)
    if len(ks) < 2:
        continue
    a, b = by[ks[0]], by[ks[-1]]
    ch = defaultdict(int)
    for x, y in zip(a, b):
        if x != y:
            ch[x + ">" + y] += 1
    print(f"{name}: class changes scan {ks[0]} -> {ks[-1]} (chunks): " + ", ".join(f"{k} {n}" for k, n in sorted(ch.items(), key=lambda p: -p[1])))
