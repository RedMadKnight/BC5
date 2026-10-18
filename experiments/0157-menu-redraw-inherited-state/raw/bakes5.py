#!/usr/bin/env python3
# Experiment 0157: the layer draws of chosen redraw buffers in order, each with its pixel shader, blend,
# T#0 (base, size), index range, vertex box and first vertex; and every "vertex rewrite" line.
# Usage: bakes5.py <direct.log> <T0 epoch> <offset> <buffers,...|near:<shot>> [rewrites]
import sys, re, collections
log, T0, off = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
sel = sys.argv[4]
rm = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+):((?: [0-9a-f]{8})+) \| rt0 ([0-9a-f]+) (\d+)x(\d+) info ([0-9a-f]+) mask ([0-9a-f]+) \| vp .* \| ps ([0-9a-f]+) es")
rb = re.compile(r"^bake draw buf (\d+) at (\d+): t ([\d.]+) wall ([\d.]+) \| win .* gen (\d+),(\d+)-(\d+),(\d+) \| view (\w+) attrib (\w+) attrib3 (\w+) blend0 (\w+) cc (\w+) colfmt (\w+)")
ru = re.compile(r"^bake ud (ps|gs) buf (\d+) at (\d+):((?: [0-9a-f]{8})+)")
rv = re.compile(r"^bake vertices buf (\d+) at (\d+): idx ([0-9a-f]+) \+(\d+) x(\d+) \((\d+)-bit\) -> (\d+)\.\.(\d+) \| vb ([0-9a-f]+) stride (\d+) \| box ([-\d.]+),([-\d.]+)-([-\d.]+),([-\d.]+) \| v0 (.*)$")
rw = re.compile(r"^vertex rewrite: (.*)$")
draws = collections.OrderedDict(); rewrites = []
for line in open(log, errors="replace"):
    m = rm.match(line)
    if m:
        draws[(int(m.group(1)), int(m.group(3)))] = {"pkt": m.group(4).split(), "rt": m.group(5), "w": int(m.group(6)), "mask": m.group(9), "ps": m.group(10)}; continue
    m = rb.match(line)
    if m:
        k = (int(m.group(1)), int(m.group(2)))
        if k in draws: draws[k].update(t=float(m.group(3)), wall=float(m.group(4)), gen=tuple(int(m.group(i)) for i in range(5, 9)), blend0=m.group(12))
        continue
    m = ru.match(line)
    if m:
        k = (int(m.group(2)), int(m.group(3)))
        if k in draws: draws[k]["ud_" + m.group(1)] = m.group(4).split()
        continue
    m = rv.match(line)
    if m:
        k = (int(m.group(1)), int(m.group(2)))
        if k in draws: draws[k].update(idx=(m.group(3), int(m.group(4)), int(m.group(5)), int(m.group(7)), int(m.group(8))), vb=m.group(9), stride=int(m.group(10)), box=tuple(float(m.group(i)) for i in range(11, 15)), v0=m.group(15))
        continue
    m = rw.match(line)
    if m: rewrites.append(m.group(1))


def tbase(ud, i):
    return "%010x" % ((int(ud[i], 16) | ((int(ud[i + 1], 16) & 0xff) << 32)) << 8)


def tsize(ud, i):
    w1, w2 = int(ud[i + 1], 16), int(ud[i + 2], 16)
    return "%dx%d" % ((((w2 & 0x3fff) << 2) | (w1 >> 30)) + 1, ((w2 >> 14) & 0xffff) + 1)


bufs = collections.OrderedDict()
for (b, o), d in draws.items(): bufs.setdefault(b, []).append((o, d))
if sel.startswith("near:"):
    s = int(sel[5:]); want = [b for b, lst in bufs.items() if any(abs((d.get("wall", 0) - T0) - 2 * s) <= 4.2 for _, d in lst)]
else:
    want = [int(x) for x in sel.split(",")]
for b in want:
    lst = bufs.get(b, [])
    if not lst: continue
    w0 = lst[0][1].get("wall", 0)
    print("== buf %d  +%.2f s  (shot s%d next)  %d draws" % (b, w0 - T0, int((w0 - T0) // 2) + 1, len(lst)))
    for o, d in lst:
        tex = ("%s %s" % (tbase(d["ud_ps"], 0), tsize(d["ud_ps"], 0))) if "ud_ps" in d and d["ud_ps"][0] != "00000000" else "-"
        box = ("%.0f,%.0f-%.0f,%.0f" % d["box"]) if "box" in d else "?"
        idx = ("+%d x%d -> %d..%d" % (d["idx"][1], d["idx"][2], d["idx"][3], d["idx"][4])) if "idx" in d else ""
        print("  at %5d %s %s>%s blend %s | %-22s | %-24s | box %-22s | v0 %s" % (o, d["ps"][-4:], d["mask"], d["rt"][:4], d.get("blend0"), tex, idx, box, d.get("v0", "")[:80]))
if len(sys.argv) > 5:
    print("== vertex rewrites: %d" % len(rewrites))
    for r in rewrites[:60]: print("  ", r)
