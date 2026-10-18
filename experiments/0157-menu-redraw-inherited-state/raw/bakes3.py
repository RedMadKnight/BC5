#!/usr/bin/env python3
# Experiment 0156: for the layer draws of one pixel shader sampling one texture (T#0 base), the distinct
# user-data variants (T#0..T#2 full, ud24-31) and table contents per redraw buffer, to compare broken
# redraws with clean ones. Usage: bakes3.py <direct.log> <ps suffix> <T#0 base hex> [<buffers to detail,...>]
import sys, re, collections
log, want_ps, want_base = sys.argv[1], sys.argv[2], sys.argv[3]
detail = set(int(x) for x in sys.argv[4].split(",")) if len(sys.argv) > 4 else set()
rm = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+):((?: [0-9a-f]{8})+) \| rt0 ([0-9a-f]+) (\d+)x(\d+) .* \| ps ([0-9a-f]+) es")
ru = re.compile(r"^bake ud (ps|gs) buf (\d+) at (\d+):((?: [0-9a-f]{8})+)")
rt = re.compile(r"^bake table (ps|gs) ud(\d+) ([0-9a-f]+):((?: [0-9a-f]{8})+)")
draws = collections.OrderedDict(); last = None
for line in open(log, errors="replace"):
    m = rm.match(line)
    if m:
        last = (int(m.group(1)), int(m.group(3)))
        draws[last] = {"pkt": m.group(4).split(), "w": int(m.group(6)), "ps": m.group(8), "tables": {}}; continue
    m = ru.match(line)
    if m:
        last = (int(m.group(2)), int(m.group(3)))
        if last in draws: draws[last]["ud_" + m.group(1)] = m.group(4).split()
        continue
    m = rt.match(line)
    if m and last in draws: draws[last]["tables"][(m.group(1), int(m.group(2)))] = (m.group(3), m.group(4).split())


def tbase(ud, i):
    return "%010x" % ((int(ud[i], 16) | ((int(ud[i + 1], 16) & 0xff) << 32)) << 8)


variants = collections.Counter(); where = collections.defaultdict(set); gsv = collections.Counter(); gwhere = collections.defaultdict(set)
tabv = collections.Counter(); twhere = collections.defaultdict(set)
for (b, off), d in draws.items():
    if not d["ps"].endswith(want_ps) or d["w"] <= 2048 or "ud_ps" not in d or tbase(d["ud_ps"], 0) != want_base: continue
    ud = d["ud_ps"]
    key = " ".join(ud[0:24])  # the three T#s
    variants[key] += 1; where[key].add(b)
    g = d.get("ud_gs", [])
    gk = " ".join(g[1:2] + g[2:4] + g[5:6] + g[7:8])  # V# dwords but the rotating bases
    gsv[gk] += 1; gwhere[gk].add(b)
    for (st, k), (addr, dw) in d["tables"].items():
        if st != "ps": continue
        tk = "ud%d %s" % (k, " ".join(x if i not in (8, 12, 20) else "........" for i, x in enumerate(dw[:40])))
        tabv[tk] += 1; twhere[tk].add(b)
    if b in detail:
        print("buf %d at %d pkt %s" % (b, off, " ".join(d["pkt"][1:4])))
        print("   ud ps:", " ".join(ud)); print("   ud gs:", " ".join(g))
        for (st, k), (addr, dw) in sorted(d["tables"].items()): print("   table %s ud%d %s: %s" % (st, k, addr, " ".join(dw)))
print("T# variants (ud0-23) of %s draws sampling %s:" % (want_ps, want_base))
for k, n in variants.most_common(): print("  x%d in buffers %s: %s" % (n, sorted(where[k]), k))
print("GS user data variants (stride/records/format dwords):")
for k, n in gsv.most_common(): print("  x%d in buffers %s: %s" % (n, sorted(gwhere[k])[:12], k))
print("PS table variants (bases masked):")
for k, n in tabv.most_common(8): print("  x%d in buffers %s: %s" % (n, sorted(twhere[k])[:12], k[:400]))
