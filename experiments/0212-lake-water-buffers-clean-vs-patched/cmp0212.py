#!/usr/bin/env python3
# BC5 experiment 0212: compare memory dumps (mem0212.py dump) of one range: record by record (stride bytes each),
# how many records differ between each dump and the first, and between consecutive dumps; with --show N, the first N
# differing records of each pair as hex. Dumps are given in shot order, optionally as name=path to label them
# (e.g. with the shot's patch share).
# usage: python3 -I cmp0212.py <stride> [--show N] <dump> [<dump> ...]
import sys

args = sys.argv[1:]
stride = int(args.pop(0))
show = 0
if args and args[0] == "--show":
    show = int(args[1])
    args = args[2:]
named = [(a.split("=", 1) if "=" in a else (a, a)) for a in args]
data = [(n, open(p, "rb").read()) for n, p in named]


def diff(a, b):
    n = min(len(a), len(b)) // stride
    return [i for i in range(n) if a[i * stride:(i + 1) * stride] != b[i * stride:(i + 1) * stride]]


first = data[0]
print("%d dumps, %d bytes, %d records of %d bytes" % (len(data), len(first[1]), len(first[1]) // stride, stride))
for k, (n, d) in enumerate(data):
    vs_first = diff(first[1], d)
    vs_prev = diff(data[k - 1][1], d) if k else []
    print("  %-24s vs first %6d   vs previous %6d" % (n, len(vs_first), len(vs_prev)))
    for i in (vs_prev if k else [])[:show]:
        print("      record %6d: %s -> %s" % (i, data[k - 1][1][i * stride:(i + 1) * stride].hex(),
                                              d[i * stride:(i + 1) * stride].hex()))
