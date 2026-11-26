#!/usr/bin/env python3
# BC5 experiment 0312: one page of the culling buffers against the hole state. In P1, pages 1767 and 1768 (+0x6e7000,
# +0x6e8000 from 0x11934d3900) held one of exactly two contents (order-insensitive key) over the 96 reads, switching
# within bursts and held for 1-4 reads, as the hole state does (F344). For the given page: its state per read (index of
# its content in order of first appearance); over the clear depth reads with holes (as pk0312.py), the hole figures at
# the best size (d = inX - inY, inX, inY, cells, share) by the page's state, with a permutation p for the difference
# in mean d (one page named in advance of this test, two-sided); then the two contents: the multiset difference
# (dwords in one and not the other), the differing dwords' low and high 16-bit halves, and whether the neighbouring
# pages change at all. Summaries only.
# usage: python3 -I pq0312.py <capture dir> <reads json> <page> [permutations]   (on the box, in the ubuntu distrobox)
import collections, glob, json, os, random, sys
import numpy as np

PAGE = 1024
BASE = 0x11934d3900
cdir, rjson, page = sys.argv[1], sys.argv[2], int(sys.argv[3])
nperm = int(sys.argv[4]) if len(sys.argv) > 4 else 2000


def pg(f, p):
    a = np.frombuffer(open(f, "rb").read(), dtype="<u4")
    return a[p * PAGE:(p + 1) * PAGE]


def order(f):
    b, k = os.path.basename(f).split(".")[:2]
    return b, int(k[1:])


fs = sorted(glob.glob(os.path.join(cdir, "b*.c*.bin")), key=order)
ids, state, content = {}, {}, {}
for f in fs:
    v = pg(f, page)
    k = hash(np.sort(v).tobytes())
    if k not in ids:
        ids[k] = len(ids)
        content[ids[k]] = v.copy()
    b, n = order(f)
    state["%s.z%d" % (b, n)] = ids[k]
print("# page %d (+0x%06x, 0x%x): %d reads, %d contents; reads per content %s" % (
    page, page * PAGE * 4, BASE + page * PAGE * 4, len(fs), len(ids), dict(collections.Counter(state.values()))))
rows = []
for r in json.load(open(rjson))["reads"]:
    if r["kind"] != "z" or r["name"] not in state:
        continue
    s = sorted(r["sizes"].values(), key=lambda v: v["shear"])
    if len(s) < 2 or s[1]["shear"] < 3 * s[0]["shear"] or s[0]["share"] <= 0:
        continue
    b = s[0]
    rows.append((state[r["name"]], b["inX"] - b["inY"], b["inX"], b["inY"], b["cells"], b["share"], r["name"]))
for st in sorted({r[0] for r in rows}):
    g = [r for r in rows if r[0] == st]
    print("  state %d: %2d clear reads; mean d %+.3f, inX %.3f, inY %.3f, cells %.3f, share %.3f; reads %s" % (
        st, len(g), *[float(np.mean([r[i] for r in g])) for i in range(1, 6)], " ".join(r[6] for r in g)))
s0 = [r[1] for r in rows if r[0] == 0]
s1 = [r[1] for r in rows if r[0] == 1]
if s0 and s1:
    obs = abs(np.mean(s0) - np.mean(s1))
    d, n0, rng, hit = [r[1] for r in rows if r[0] in (0, 1)], len(s0), random.Random(312), 0
    for _ in range(nperm):
        rng.shuffle(d)
        hit += abs(np.mean(d[:n0]) - np.mean(d[n0:])) >= obs - 1e-12
    print("  difference in mean d between states 0 and 1: %.3f; permutation p %.3f (%d)" % (obs, (hit + 1) / (nperm + 1), nperm))
if len(content) >= 2:
    c0, c1 = collections.Counter(content[0].tolist()), collections.Counter(content[1].tolist())
    only0, only1 = list((c0 - c1).elements()), list((c1 - c0).elements())
    print("  contents 0 and 1: %d dwords only in 0, %d only in 1; positions that differ (raw order) %d of %d" % (
        len(only0), len(only1), int((content[0] != content[1]).sum()), PAGE))
    for nm, xs in (("only in 0", only0), ("only in 1", only1)):
        if xs:
            lo, hi = [x & 0xffff for x in xs], [x >> 16 for x in xs]
            print("    %s: low 16 bits %d..%d, high 16 bits %d..%d; first %s" % (
                nm, min(lo), max(lo), min(hi), max(hi), " ".join("%08x" % x for x in sorted(xs)[:8])))
    allv = content[0].tolist()
    print("  content 0: low 16 bits %d..%d (%d distinct), high 16 bits %d..%d (%d distinct), zeros %d" % (
        min(x & 0xffff for x in allv), max(x & 0xffff for x in allv), len({x & 0xffff for x in allv}),
        min(x >> 16 for x in allv), max(x >> 16 for x in allv), len({x >> 16 for x in allv}), allv.count(0)))
for q in (page - 2, page - 1, page + 1, page + 2):
    print("  page %d: %d contents over the reads" % (q, len({hash(np.sort(pg(f, q)).tobytes()) for f in fs})))
