#!/usr/bin/env python3
# Experiment 0157: per redraw buffer, the colour state of the layer draws (ps, CB_TARGET_MASK, blend0, cc,
# colfmt, rt) as a multiset, to compare flagged redraws with clean ones; buffers with a state no other
# buffer has are listed. Usage: bakes4.py <direct.log> <T0 epoch> <flagged shots,...>
import sys, re, collections
log, T0 = sys.argv[1], float(sys.argv[2])
flagged = set(int(x) for x in sys.argv[3].split(",")) if len(sys.argv) > 3 and sys.argv[3] else set()
rm = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+):((?: [0-9a-f]{8})+) \| rt0 ([0-9a-f]+) (\d+)x(\d+) info ([0-9a-f]+) mask ([0-9a-f]+) \| vp .* \| ps ([0-9a-f]+) es")
rb = re.compile(r"^bake draw buf (\d+) at (\d+): t ([\d.]+) wall ([\d.]+) \| win .* \| view (\w+) attrib (\w+) attrib3 (\w+) blend0 (\w+) cc (\w+) colfmt (\w+)")
draws = collections.OrderedDict()
for line in open(log, errors="replace"):
    m = rm.match(line)
    if m:
        draws[(int(m.group(1)), int(m.group(3)))] = {"pkt": m.group(4).split(), "rt": m.group(5), "w": int(m.group(6)), "mask": m.group(9), "ps": m.group(10)}; continue
    m = rb.match(line)
    if m:
        k = (int(m.group(1)), int(m.group(2)))
        if k in draws: draws[k].update(wall=float(m.group(4)), blend0=m.group(8), cc=m.group(9), colfmt=m.group(10))
bufs = collections.OrderedDict()
for (b, off), d in draws.items(): bufs.setdefault(b, []).append(d)
states = collections.Counter(); per = {}
for b, lst in bufs.items():
    st = collections.Counter((d["ps"][-4:], d["mask"], d.get("blend0"), d.get("cc"), d.get("colfmt"), d["w"] > 2048) for d in lst)
    per[b] = st
    for k in st: states[k] += 1
print("distinct (ps, mask, blend0, cc, colfmt, layer?) states over %d buffers:" % len(bufs))
for k, n in states.most_common(): print("  in %2d buffers: %s" % (n, k))
for b, lst in bufs.items():
    wall = min(d.get("wall", 0) for d in lst); k = int((wall - T0) // 2) + 1
    fl = [s for s in (k, k + 1) if s in flagged]
    rare = [(s, n) for s, n in per[b].items() if states[s] < len(bufs) // 3]
    print("buf %3d +%6.2f shot s%-3d %-14s draws %3d  %s" % (b, wall - T0, k, "FLAGGED " + ",".join(map(str, fl)) if fl else "", len(lst), ("rare: " + str(rare)) if rare else ""))
