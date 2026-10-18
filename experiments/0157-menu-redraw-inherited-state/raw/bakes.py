#!/usr/bin/env python3
# Experiment 0156: join the draw journal's main line with the "bake draw"/"bake ud"/"bake table" lines of
# the same (buf, offset); per colour target, the draws, scissors, programs and times; optionally the
# draws within a wall-clock window.
# Usage: bakes.py <direct.log> [<T0 epoch> <shot numbers,...>]  (shot k taken at T0 + 2k)
import sys, re, collections
log = sys.argv[1]
T0 = float(sys.argv[2]) if len(sys.argv) > 2 else None
shots = [int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else []
main = {}; bake = {}; ud = collections.defaultdict(dict); tables = collections.defaultdict(dict)
rm = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+):((?: [0-9a-f]{8})+) \| rt0 ([0-9a-f]+) (\d+)x(\d+) info ([0-9a-f]+) mask ([0-9a-f]+) \| vp ([-\d]+)x([-\d]+) at ([-\d]+),([-\d]+) \| ps ([0-9a-f]+) es ([0-9a-f]+) gs ([0-9a-f]+) cs ([0-9a-f]+)")
rb = re.compile(r"^bake draw buf (\d+) at (\d+): t ([\d.]+) wall ([\d.]+) \| win (\d+),(\d+)-(\d+),(\d+) gen (\d+),(\d+)-(\d+),(\d+) \| view (\w+) attrib (\w+) attrib3 (\w+) blend0 (\w+) cc (\w+) colfmt (\w+)")
ru = re.compile(r"^bake ud (ps|gs) buf (\d+) at (\d+):((?: [0-9a-f]{8})+)")
rt = re.compile(r"^bake table (ps|gs) ud(\d+) ([0-9a-f]+):((?: [0-9a-f]{8})+)")
last = None
for line in open(log, errors="replace"):
    m = rm.match(line)
    if m:
        key = (int(m.group(1)), int(m.group(3))); main[key] = m.groups(); continue
    m = rb.match(line)
    if m:
        key = (int(m.group(1)), int(m.group(2))); bake[key] = m.groups(); last = key; continue
    m = ru.match(line)
    if m:
        key = (int(m.group(2)), int(m.group(3))); ud[key][m.group(1)] = m.group(4).split(); last = key; continue
    m = rt.match(line)
    if m and last is not None:
        tables[last][(m.group(1), int(m.group(2)))] = (m.group(3), m.group(4).split()); continue
print("main lines", len(main), "bake lines", len(bake))
per = collections.defaultdict(list)
for key, b in bake.items():
    mm = main.get(key)
    if mm is None: continue
    per[(mm[4], mm[5], mm[6], mm[7])].append((key, mm, b))
for tgt, lst in sorted(per.items(), key=lambda x: -len(x[1])):
    rt0, w, h, info = tgt
    sc = collections.Counter("%s,%s-%s,%s" % (b[8], b[9], b[10], b[11]) for _, _, b in lst)
    ps = collections.Counter(mm[13] for _, mm, _ in lst); gs = collections.Counter(mm[15] for _, mm, _ in lst)
    ops = collections.Counter(mm[3].split()[0][:4] for _, mm, _ in lst)
    ts = sorted(float(b[2]) for _, _, b in lst)
    bufs = len(set(k[0] for k, _, _ in lst))
    print("\n== rt0 %s %sx%s info %s: %d draws in %d buffers, t %.1f..%.1f" % (rt0, w, h, info, len(lst), bufs, ts[0], ts[-1]))
    print("   ops", dict(ops.most_common(4)), "ps", dict(ps.most_common(4)), "gs", dict(gs.most_common(3)))
    print("   gen scissors: %d distinct; %s" % (len(sc), sc.most_common(6)))
    a3 = collections.Counter((b[12], b[13], b[14], b[15], b[16], b[17]) for _, _, b in lst)
    print("   view/attrib/attrib3/blend0/cc/colfmt:", a3.most_common(3))
    # the distinct descriptor tables (first dwords) reached from the PS user data
    tb = collections.Counter()
    for key, _, _ in lst:
        for (st, k), (addr, dw) in tables.get(key, {}).items():
            if st == "ps": tb[(k, addr)] += 1
    print("   ps tables (ud index, address): %d distinct; %s" % (len(tb), tb.most_common(6)))
    if shots and T0 is not None:
        # draws in the 4 s before each listed shot
        for s in shots:
            t_shot = T0 + 2 * s
            near = [(k, mm, b) for k, mm, b in lst if t_shot - 4.5 <= float(b[3]) <= t_shot + 0.5]
            if near:
                print("   shot s%d (wall %.0f): %d draws at wall %s" % (s, t_shot, len(near), sorted(set("%.2f" % (float(b[3]) - t_shot) for _, _, b in near))))
