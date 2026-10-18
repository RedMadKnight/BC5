#!/usr/bin/env python3
# Experiment 0156: timeline of the UI redraws (one journaled buffer each): wall time, the next screenshot
# and whether it was flagged, draws per pixel shader and colour target, the T# bases (PS user data 0-7,
# 8-15, 16-23: base = (dw0 | (dw1 & 0xff) << 32) << 8) with their counts, the scissors of the atlas draws.
# Usage: bakes2.py <direct.log> <T0 epoch> <flagged shots,...> [detail]
import sys, re, collections
log, T0 = sys.argv[1], float(sys.argv[2])
flagged = set(int(x) for x in sys.argv[3].split(",")) if len(sys.argv) > 3 and sys.argv[3] else set()
detail = len(sys.argv) > 4
rm = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+):((?: [0-9a-f]{8})+) \| rt0 ([0-9a-f]+) (\d+)x(\d+) info ([0-9a-f]+) mask ([0-9a-f]+) \| vp .* \| ps ([0-9a-f]+) es ([0-9a-f]+)")
rb = re.compile(r"^bake draw buf (\d+) at (\d+): t ([\d.]+) wall ([\d.]+) \| win (\d+),(\d+)-(\d+),(\d+) gen (\d+),(\d+)-(\d+),(\d+) \| view (\w+) attrib (\w+) attrib3 (\w+) blend0 (\w+) cc (\w+) colfmt (\w+)")
ru = re.compile(r"^bake ud (ps|gs) buf (\d+) at (\d+):((?: [0-9a-f]{8})+)")
rt = re.compile(r"^bake table (ps|gs) ud(\d+) ([0-9a-f]+):((?: [0-9a-f]{8})+)")
draws = collections.OrderedDict()
last = None
for line in open(log, errors="replace"):
    m = rm.match(line)
    if m:
        key = (int(m.group(1)), int(m.group(3)))
        draws[key] = {"pkt": m.group(4).split(), "rt": m.group(5), "w": int(m.group(6)), "h": int(m.group(7)), "info": m.group(8), "mask": m.group(9), "ps": m.group(10), "es": m.group(11)}
        last = key; continue
    m = rb.match(line)
    if m:
        key = (int(m.group(1)), int(m.group(2)))
        if key in draws:
            d = draws[key]; d["t"] = float(m.group(3)); d["wall"] = float(m.group(4))
            d["gen"] = tuple(int(m.group(i)) for i in range(9, 13)); d["blend0"] = m.group(16); d["colfmt"] = m.group(18)
        last = key; continue
    m = ru.match(line)
    if m:
        key = (int(m.group(2)), int(m.group(3)))
        if key in draws: draws[key]["ud_" + m.group(1)] = m.group(4).split()
        last = key; continue
    m = rt.match(line)
    if m and last in draws:
        draws[last].setdefault("tables", {})[(m.group(1), int(m.group(2)))] = (m.group(3), m.group(4).split())


def tbase(ud, i):
    return "%010x" % ((int(ud[i], 16) | ((int(ud[i + 1], 16) & 0xff) << 32)) << 8)


def tsize(ud, i):
    w1, w2 = int(ud[i + 1], 16), int(ud[i + 2], 16)
    return "%dx%d" % ((((w2 & 0x3fff) << 2) | (w1 >> 30)) + 1, ((w2 >> 14) & 0xffff) + 1)


bufs = collections.OrderedDict()
for key, d in draws.items():
    bufs.setdefault(key[0], []).append(d)
print("redraw buffers:", len(bufs), "draws:", len(draws))
rows = []
for b, lst in bufs.items():
    wall = min(d.get("wall", 0) for d in lst)
    if wall == 0: continue
    k = int((wall - T0) // 2) + 1  # the first screenshot after this redraw
    nxt = [k2 for k2 in range(k, k + 2)]
    fl = [k2 for k2 in nxt if k2 in flagged]
    per = collections.Counter((d["ps"], d["rt"][:4], d["w"]) for d in lst)
    tex = collections.Counter()
    for d in lst:
        if d["w"] > 2048 and "ud_ps" in d:
            tex[(d["ps"], tbase(d["ud_ps"], 0), tsize(d["ud_ps"], 0))] += 1
    rows.append((b, wall - T0, lst[0].get("t", 0), k, fl, per, tex, lst))
for b, rel, t, k, fl, per, tex, lst in rows:
    mark = "FLAGGED s%s" % ",".join(map(str, fl)) if fl else ""
    pers = " ".join("%s>%s/%d:%d" % (ps[-4:], rt, w, n) for (ps, rt, w), n in sorted(per.items()))
    print("buf %5d  +%6.2f s  t %7.2f  shot s%-3d %-14s %s" % (b, rel, t, k, mark, pers))
    if tex:
        print("          layer draws' T#0: " + "; ".join("%s %s %s x%d" % (ps[-4:], base, sz, n) for (ps, base, sz), n in sorted(tex.items(), key=lambda x: -x[1])))
    if detail:
        for d in lst:
            if d["w"] <= 2048 and d["w"] > 1:
                print("          atlas draw %s -> %s %dx%d gen %s blend0 %s pkt %s T#0 %s %s" % (d["ps"][-4:], d["rt"], d["w"], d["h"], d.get("gen"), d.get("blend0"), " ".join(d["pkt"][1:4]),
                      tbase(d["ud_ps"], 0) if "ud_ps" in d and d["ud_ps"][0] != "00000000" else "-", tsize(d["ud_ps"], 0) if "ud_ps" in d and d["ud_ps"][0] != "00000000" else ""))
