#!/usr/bin/env python3
# BC5 experiment 0245: compare, between the journal windows of one run (BC5_DIRECT_DRAW_JOURNAL=<t0>:<pieces> with
# _EVERY, unfiltered, build0245's binary), the draws that write depth into the buffer the water's full-screen draw
# (PS 0x11d01d7100) tests, from the flip before it up to it. Each such draw is listed by pixel shader, colour mask and
# the first dwords of its draw packet (draw size), the multiset per full-screen draw is the frame's signature, and the
# signatures are printed per window with the window's wall clock (file mtime minus (last journal time - t), +-1 s, as
# jr0231.py) and the patch share of the first shot after it (exp 0197's metric, from the bench output).
# usage: python3 -I cmp0245.py <direct.log> <bench.txt>
import collections, datetime, os, re, sys

path, bench = sys.argv[1], sys.argv[2]
shots = []
for l in open(bench):
    m = re.match(r"\s*(\d\d)(\d\d)(\d\d)-(ts\d\d)\.png: patch\s+([\d.]+) %", l)
    if m:
        shots.append(("%s:%s:%s" % m.groups()[:3], m[4], float(m[5])))
DRAW = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+): ([0-9a-f ]*)\| rt0 (\S+) (\S+) .*mask (\S+) .*\| ps (\S+) ")
DB = re.compile(r"^bake db buf (\d+) at (\d+): depth_control (\S+) .*\| z_read (\S+) stencil_read \S+ z_write (\S+) ")
T = re.compile(r"\bt (\d+\.\d+)")
t, pend, frame, frames = 0.0, {}, [], []
for line in open(path, errors="replace"):
    if line.startswith("frame profile: t "):
        m = T.search(line)
        t = float(m[1]) if m else t
        frame = []
        continue
    if line.startswith("timing: t "):
        m = T.search(line)
        t = float(m[1]) if m else t
        continue
    m = DRAW.match(line)
    if m:
        pend[(m[1], m[3])] = (m[8].lower(), m[7], " ".join(m[4].split()[:4]))
        continue
    m = DB.match(line)
    if m and (m[1], m[2]) in pend:
        ps, mask, pkt = pend.pop((m[1], m[2]))
        dc = int(m[3], 16)
        if ps == "11d01d7100":
            frames.append((t, m[4], collections.Counter(frame)))
        elif (dc >> 1) & 1 and (dc >> 2) & 1:
            frame.append((ps, mask, pkt, m[5]))
end = os.path.getmtime(path)


def wall(tt):
    return datetime.datetime.fromtimestamp(end - (t - tt)).strftime("%H:%M:%S")


def state(w):
    nxt = next((s for s in shots if s[0] >= w), None)
    return "%s %s %.1f %%" % (nxt[1], nxt[0], nxt[2]) if nxt else "-"


base = None
print("# %s: %d full-screen water draws journalled" % (path, len(frames)))
for tt, zbuf, sig in frames:
    w = wall(tt)
    total = sum(sig.values())
    if base is None:
        base = sig
        print("== t %.3f (wall %s, next shot %s): %d depth writers before it into %s (the reference):" % (tt, w, state(w), total, zbuf))
        for (ps, mask, pkt, zw), n in sorted(base.items()):
            print("     %3d x ps %s mask %s pkt %s z %s" % (n, ps, mask, pkt, zw))
        continue
    plus, minus = sig - base, base - sig
    print("== t %.3f (wall %s, next shot %s): %d depth writers; vs the reference +%d -%d" % (tt, w, state(w), total, sum(plus.values()), sum(minus.values())))
    for (ps, mask, pkt, zw), n in sorted(plus.items()):
        print("     + %2d x ps %s mask %s pkt %s" % (n, ps, mask, pkt))
    for (ps, mask, pkt, zw), n in sorted(minus.items()):
        print("     - %2d x ps %s mask %s pkt %s" % (n, ps, mask, pkt))
