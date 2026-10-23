#!/usr/bin/env python3
# BC5 experiment 0233 (from exp 0232's ana0232.py): the title's AMM/APR requests (KYTY_BC5_AMM_TRACE=1, the run's emu.log) around the changes of its
# bindless texture table (exp 0212: mem0212.py hash.txt, one CRC per 4-KiB page per second, and the table dumps before
# each frozen-view shot). Both stamp CLOCK_MONOTONIC ("mono <s>" in the trace, the second column of hash.txt), so they
# align exactly. Prints:
#  (1) AMM maps / unmaps / package reads per 5 s from WINDOW s before the first frozen-view shot to the end;
#  (2) every table change from the first shot - WINDOW on (pages changed) with the AMM events in the 10 s before it;
#  (3) the textures whose MIN_LOD or LAST_LEVEL differ between the first and last table dump (tab0212.py's decoding),
#      and for each, the AMM maps and reads that touched its address range during the run (time relative to the
#      first shot).
# Runs on the box (the dumps are the title's memory); prints summaries only.
# Exp 0233: with ANCHOR=nudge the anchor t0 is the camera nudge (r-<tag>/nudge.txt "nudge start", mapped to mono
# through hash.txt's wall column) and (3) compares the last dump before the nudge (ts12) with the last one (ts32).
# usage: [ANCHOR=nudge] python3 -I ana0233.py <run dir> [WINDOW s, default 60]
import bisect, collections, glob, os, re, struct, sys

rd = sys.argv[1]
WINDOW = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
TABLE = "0x11e0007aa0"
# hash.txt: "h <mono> <wall> <base> pages <n> changed <n> [idx ...]"
hs = []
for l in open(os.path.join(rd, "hash.txt")):
    p = l.split()
    if len(p) >= 8 and p[0] == "h" and p[3] == TABLE and p[4] == "pages":
        hs.append((float(p[1]), p[2], int(p[7]), p[8:]))
shots = sorted(glob.glob(os.path.join(rd, "shots", "*-ts*.png")))
first_wall = os.path.basename(shots[0])[:6] if shots else None
fw = "%s:%s:%s" % (first_wall[0:2], first_wall[2:4], first_wall[4:6]) if first_wall else None
t0 = next((m for m, w, n, idx in hs if w >= fw), hs[0][0]) if hs and fw else 0.0
if os.environ.get("ANCHOR") == "nudge":
    nw = next((l.split()[2][:8] for l in open(os.path.join(rd, "nudge.txt")) if l.startswith("nudge start")), None)
    t0 = next((m for m, w, n, idx in hs if w >= nw), t0)
    fw = "nudge " + nw
# AMM trace
ev = []
R_MAP = re.compile(r"mono ([\d.]+) amm trace: map (auto|direct) va 0x([0-9a-f]+) size 0x([0-9a-f]+)")
R_UNMAP = re.compile(r"mono ([\d.]+) amm trace: unmap va 0x([0-9a-f]+) size 0x([0-9a-f]+)")
R_READ = re.compile(r"mono ([\d.]+) amm trace: read file 0x([0-9a-f]+) \+0x([0-9a-f]+) size 0x([0-9a-f]+) -> 0x([0-9a-f]+)")
for l in open(os.path.join(rd, "emu.log"), errors="replace"):
    if "amm trace:" not in l:
        continue
    m = R_MAP.search(l)
    if m:
        ev.append((float(m[1]), "map", int(m[3], 16), int(m[4], 16))); continue
    m = R_UNMAP.search(l)
    if m:
        ev.append((float(m[1]), "unmap", int(m[2], 16), int(m[3], 16))); continue
    m = R_READ.search(l)
    if m:
        ev.append((float(m[1]), "read", int(m[5], 16), int(m[4], 16)))
ev.sort()
et = [e[0] for e in ev]
print("# %s: first frozen-view shot %s = mono %.1f; %d AMM events; %d table samples" % (rd, fw, t0, len(ev), len(hs)))
print("(1) AMM events per 5 s (s relative to the first shot): t maps unmaps reads read_MiB")
b = collections.OrderedDict()
for t, k, va, sz in ev:
    if t < t0 - WINDOW:
        continue
    key = int((t - t0) // 5) * 5
    c = b.setdefault(key, collections.Counter())
    c[k] += 1
    if k == "read":
        c["bytes"] += sz
for key, c in b.items():
    print("  %+5d %5d %5d %5d %8.1f" % (key, c["map"], c["unmap"], c["read"], c["bytes"] / 2**20))
print("(2) table changes from %d s before the first shot, with the AMM events of the 10 s before each" % WINDOW)
for m, w, n, idx in hs:
    if n == 0 or m < t0 - WINDOW:
        continue
    i, j = bisect.bisect_left(et, m - 10), bisect.bisect_left(et, m)
    c = collections.Counter(e[1] for e in ev[i:j])
    print("  %s (%+.0f s): %d pages changed (%s) | AMM in the 10 s before: %d maps, %d unmaps, %d reads" % (
        w, m - t0, n, " ".join(idx[:8]), c["map"], c["unmap"], c["read"]))


def table(path):
    data = open(path, "rb").read()
    out = {}
    for i in range(len(data) // 32):
        d = struct.unpack_from("<8I", data, i * 32)
        if not (8 <= d[3] >> 28 <= 13) or (d[1] >> 20) & 0x1ff == 0:
            continue
        base = (d[0] | (d[1] & 0xff) << 32) << 8
        out.setdefault(base, set()).add((((d[1] >> 8) & 0xfff) / 256.0, (d[3] >> 16) & 0xf, (d[1] >> 20) & 0x1ff,
                                         ((d[2] & 0xfff) << 2 | d[1] >> 30) + 1, ((d[2] >> 14) & 0x3fff) + 1))
    return out


dumps = sorted(glob.glob(os.path.join(rd, "dumps", "ts*.11e0007aa0.bin")))
if os.environ.get("ANCHOR") == "nudge":
    dumps = [d for d in dumps if os.path.basename(d).startswith(("ts12.", "ts32."))]
print("(3) textures whose MIN_LOD/LAST_LEVEL differ between %s and %s" % (
    os.path.basename(dumps[0]) if dumps else "-", os.path.basename(dumps[-1]) if dumps else "-"))
if len(dumps) >= 2:
    a, z = table(dumps[0]), table(dumps[-1])
    for base in sorted(set(a) & set(z)):
        if {(x[0], x[1]) for x in a[base]} != {(x[0], x[1]) for x in z[base]}:
            fmt, w, h = next(iter(a[base]))[2:]
            touch = [(e[0] - t0, e[1], e[3]) for e in ev if e[2] < base + w * h and base < e[2] + e[3]]
            print("  0x%x %dx%d fmt %d: %s -> %s; AMM events touching its first w*h bytes: %d %s" % (
                base, w, h, fmt, sorted({(x[0], x[1]) for x in a[base]}), sorted({(x[0], x[1]) for x in z[base]}),
                len(touch), ["%+.1fs %s 0x%x" % x for x in touch[-6:]]))
