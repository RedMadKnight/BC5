#!/usr/bin/env python3
# BC5 experiment 0293 (exp 0289's chg0289.py, unchanged): a test that needs no X/Y labels. In the frozen view a depth read changes from one read to the
# next only where the holes change (the drawn pixels hold the same depth every frame). If some GPU-written indirect
# arguments decide which cells the writers draw, those records should change between two consecutive reads when the
# depth-0 set changes, and stay put when it does not. For each burst, consecutive depth reads zK, zK+1 that both have a
# clear size and the same best size (rd0287.py's JSON): phi between their depth-0 sets in the lake window (x 300..1900,
# y 400..680 of 1920x1080, nearest pixel; depth words outside 0..1 left out), and which argument records (ar0287.py's
# addresses, from the journal's "draw journal args" lines) differ between the argument reads aK and aK+1 taken just
# before them. Prints per pair: the time between the reads, phi, the share of depth-0 pixels kept, the number of
# records that changed; then per record: how often it changed in pairs whose holes changed (phi < 0.8) and in pairs
# whose holes stayed (phi >= 0.95), and the records that changed in every holes-changed pair and in no holes-stayed
# pair. De-swizzle as rd0283.py (Z_X at 16 pipes, swz0248-z4.json). Summaries only. Runs on the box in the ubuntu
# distrobox (numpy), on the title's data.
# usage: python3 -I chg0287.py <capture dir> <reads json> <direct.log> <swz0248-z4.json>
import collections, glob, json, os, re, struct, sys
import numpy as np

cdir, rjson, log, zsw = sys.argv[1:5]
pz = json.load(open(zsw))["patterns"]["4"]
X0, X1, Y0, Y1 = 300, 1900, 400, 680
ARGS = re.compile(r"^draw journal args buf \d+ at \d+: op \S+ base1 ([0-9a-f]+) \+0x([0-9a-f]+)")
recs = set()
for l in open(log, errors="replace"):
    if l.startswith("draw journal args"):
        m = ARGS.match(l)
        if m:
            recs.add(int(m[1], 16) + int(m[2], 16))
reads = {r["name"]: r for r in json.load(open(rjson))["reads"]}


def coord_offset(p, key, n):
    v = np.arange(n, dtype=np.int64)
    off = np.zeros(n, dtype=np.int64)
    for i, b in enumerate(p):
        m = b[key]
        if m:
            par = np.zeros(n, dtype=np.int64)
            for k in range(16):
                if m >> k & 1:
                    par ^= (v >> k) & 1
            off |= par << i
    return off


IDX = {}


def depth0(path, w):
    h = w * 9 // 16
    if w not in IDX:
        fx, fy = coord_offset(pz, "x", w), coord_offset(pz, "y", h)
        pitch = -(-w // 128)
        blk = (np.arange(h) // 128)[:, None] * pitch + (np.arange(w) // 128)[None, :]
        IDX[w] = (blk * 65536 + (fx[None, :] ^ fy[:, None])) >> 2
    raw = np.frombuffer(open(path, "rb").read(), dtype="<f4").astype(np.float64)
    img = raw[np.minimum(IDX[w], raw.size - 1)]
    ys, xs = np.arange(Y0, Y1) * h // 1080, np.arange(X0, X1) * w // 1920
    z = img[ys][:, xs]
    with np.errstate(invalid="ignore"):
        ok = np.isfinite(z) & (z >= 0) & (z <= 1)
    return (z == 0) & ok, ok


def args_of(b, name, line):
    m = re.search(r" ranges (.*)$", line)
    data = open(os.path.join(cdir, "%s.%s.bin" % (b, name)), "rb").read()
    vals, pos = {}, 0
    for part in m[1].split():
        a, n = (int(x, 16) for x in part.split(":"))
        for addr in recs:
            if a <= addr and addr + 16 <= a + n:
                vals[addr] = struct.unpack_from("<4I", data, pos + addr - a)
        pos += n
    return vals


pairs = []
for tf in sorted(glob.glob(os.path.join(cdir, "b*.times.txt"))):
    b = os.path.basename(tf).split(".")[0]
    lines = {l.split()[0]: l for l in open(tf) if l.strip()}
    walls = {k: float(v.split()[2]) for k, v in lines.items()}
    k = 0
    while "z%d" % (k + 1) in lines:
        r1, r2 = reads.get("%s.z%d" % (b, k)), reads.get("%s.z%d" % (b, k + 1))
        if r1 and r2 and r1["clear"] and r2["clear"] and r1["best"] == r2["best"] and "a%d" % (k + 1) in lines:
            d1, ok1 = depth0(os.path.join(cdir, "%s.z%d.bin" % (b, k)), r1["best"])
            d2, ok2 = depth0(os.path.join(cdir, "%s.z%d.bin" % (b, k + 1)), r1["best"])
            m = ok1 & ok2
            x, y = d1[m].astype(float), d2[m].astype(float)
            phi = float(np.corrcoef(x, y)[0, 1]) if x.std() > 0 and y.std() > 0 else (1.0 if (x == y).all() else 0.0)
            kept = float((d1 & d2 & m).sum() / max((d1 & m).sum(), 1))
            a1, a2 = args_of(b, "a%d" % k, lines["a%d" % k]), args_of(b, "a%d" % (k + 1), lines["a%d" % (k + 1)])
            changed = {a for a in recs if a in a1 and a in a2 and a1[a][:2] != a2[a][:2]}
            pairs.append((b, k, (walls["z%d" % (k + 1)] - walls["z%d" % k]) * 1000, phi, kept, changed, float(x.mean())))
        k += 1
print("# %s: %d argument records; %d consecutive pairs of clear same-size depth reads" % (cdir, len(recs), len(pairs)))
for b, k, dt, phi, kept, ch, sh in pairs:
    print("  %s z%d-z%d %6.1f ms: phi %+.3f, kept %.3f (depth 0 on %.3f), %d records changed" % (b, k, k + 1, dt, phi, kept, sh, len(ch)))
moved = [p for p in pairs if p[3] < 0.8]
stayed = [p for p in pairs if p[3] >= 0.95]
print("# holes changed (phi < 0.8): %d pairs; holes stayed (phi >= 0.95): %d pairs" % (len(moved), len(stayed)))
if moved and stayed:
    print("  records changed per pair: holes changed median %.0f, holes stayed median %.0f" % (
        float(np.median([len(p[5]) for p in moved])), float(np.median([len(p[5]) for p in stayed]))))
    rows = []
    for a in sorted(recs):
        cm = sum(1 for p in moved if a in p[5])
        cs = sum(1 for p in stayed if a in p[5])
        rows.append((cm / len(moved) - cs / len(stayed), a, cm, cs))
    rows.sort(reverse=True)
    print("# per record: changed in holes-changed pairs | in holes-stayed pairs (the 20 with the largest difference)")
    for diff, a, cm, cs in rows[:20]:
        print("  %x: %d of %d | %d of %d" % (a, cm, len(moved), cs, len(stayed)))
    perfect = [a for d, a, cm, cs in rows if cm == len(moved) and cs == 0]
    print("# records that changed in every holes-changed pair and in no holes-stayed pair: %s" % (
        " ".join("%x" % a for a in perfect) or "none"))
# All consecutive pairs of a burst, with no size needed: how many 32-bit words of the depth image (the whole read)
# differ between zK and zK+1, and how many argument records differ between aK and aK+1; then the two-by-two table of
# "depth memory changed" (any word) against "arguments changed" (any record).
print("# every consecutive pair: depth words changed (of the whole image) and argument records changed")
table = collections.Counter()
for tf in sorted(glob.glob(os.path.join(cdir, "b*.times.txt"))):
    b = os.path.basename(tf).split(".")[0]
    lines = {l.split()[0]: l for l in open(tf) if l.strip()}
    k = 0
    row = []
    while "z%d" % (k + 1) in lines and "a%d" % (k + 1) in lines:
        z1 = np.frombuffer(open(os.path.join(cdir, "%s.z%d.bin" % (b, k)), "rb").read(), dtype="<u4")
        z2 = np.frombuffer(open(os.path.join(cdir, "%s.z%d.bin" % (b, k + 1)), "rb").read(), dtype="<u4")
        n = min(z1.size, z2.size)
        dz = int((z1[:n] != z2[:n]).sum())
        a1, a2 = args_of(b, "a%d" % k, lines["a%d" % k]), args_of(b, "a%d" % (k + 1), lines["a%d" % (k + 1)])
        da = sum(1 for a in recs if a in a1 and a in a2 and a1[a] != a2[a])
        table[(dz > 0, da > 0)] += 1
        row.append("%d/%d" % (dz, da))
        k += 1
    print("  %s: %s" % (b, " ".join(row)))
print("  depth changed and arguments changed %d; depth changed only %d; arguments changed only %d; neither %d" % (
    table[(True, True)], table[(True, False)], table[(False, True)], table[(False, False)]))
# W287b on: the pyramid region read before each depth read (pK). Per consecutive pair: depth words / argument records
# / pyramid words changed, and the table of the three "changed" flags; then, since the pyramid may be built from the
# frame before, the same flags with the pyramid of the pair before (does a pyramid change come one pair ahead?).
tri, lagged, seq = collections.Counter(), collections.Counter(), []
for tf in sorted(glob.glob(os.path.join(cdir, "b*.times.txt"))):
    b = os.path.basename(tf).split(".")[0]
    lines = {l.split()[0]: l for l in open(tf) if l.strip()}
    if "p0" not in lines:
        continue
    k, row, flags = 0, [], []
    while all(("%s%d" % (c, k + 1)) in lines for c in "zap"):
        z1 = np.frombuffer(open(os.path.join(cdir, "%s.z%d.bin" % (b, k)), "rb").read(), dtype="<u4")
        z2 = np.frombuffer(open(os.path.join(cdir, "%s.z%d.bin" % (b, k + 1)), "rb").read(), dtype="<u4")
        p1 = np.frombuffer(open(os.path.join(cdir, "%s.p%d.bin" % (b, k)), "rb").read(), dtype="<u4")
        p2 = np.frombuffer(open(os.path.join(cdir, "%s.p%d.bin" % (b, k + 1)), "rb").read(), dtype="<u4")
        n = min(z1.size, z2.size)
        dz = int((z1[:n] != z2[:n]).sum())
        dp = int((p1 != p2).sum()) if p1.size == p2.size else -1
        a1, a2 = args_of(b, "a%d" % k, lines["a%d" % k]), args_of(b, "a%d" % (k + 1), lines["a%d" % (k + 1)])
        da = sum(1 for a in recs if a in a1 and a in a2 and a1[a] != a2[a])
        f = (dz > 0, da > 0, dp > 0)
        tri[f] += 1
        if flags:
            lagged[(f[0], f[1], flags[-1][2])] += 1
        flags.append(f)
        row.append("%d/%d/%d" % (dz, da, dp))
        k += 1
    seq.append("  %s: %s" % (b, " ".join(row)))
if seq:
    print("# with the pyramid: depth words / argument records / pyramid words changed, per consecutive pair")
    print("\n".join(seq))
    names = lambda f: "".join(c if x else "-" for c, x in zip("DAP", f))
    print("  flags (D depth, A arguments, P pyramid changed): %s" % ", ".join("%s %d" % (names(f), n) for f, n in sorted(tri.items(), reverse=True)))
    print("  with the pyramid of the pair before: %s" % ", ".join("%s %d" % (names(f), n) for f, n in sorted(lagged.items(), reverse=True)))
