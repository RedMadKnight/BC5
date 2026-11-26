#!/usr/bin/env python3
# BC5 experiment 0295: do the night lake writers' GPU-written indirect argument VALUES differ between frames with
# different holes? F357: the arguments are rewritten every frame (at L 0 every frame submitted between two reads changed
# them), so F350/F352's "the hole switches fall on argument changes" does not say whether the values carry the hole
# state. In the journalled frozen view a frame lasts about 120 ms (F357, inferred), and the depth image changes as a
# whole from frame to frame (millions of words, exp 0293's raw/W293a.chg.txt), so a burst of reads 30 ms apart
# (capa0287.py's aK/zK) holds runs of identical depth reads, a "plateau" per frame. Per plateau: its reads; the render
# size, clarity, depth-0 share and hole family of its first depth read (rd0287.py's JSON; families of clear reads); its
# depth-0 set in the lake window (chg0287.py's de-swizzle and window); the argument records (the journal's "draw journal
# args" lines) of the read aK taken just before its first depth read; whether they stay the same through the plateau.
# Then, over pairs of labelled plateaus from different bursts (>= 10 s apart, so never neighbouring frames):
#  - the share of varying records with equal values, same-family pairs against different-family pairs, with its
#    permutation null (family labels shuffled over the plateaus) and split by same and different render size;
#  - a Mantel test: Spearman of the pairs' hole phi with that share, permutation null (plateaus shuffled);
#  - per record: equal in same-family pairs minus in different-family pairs, the largest, and the null of the largest;
#  - per record and dword: Spearman of the value with the plateau's depth-0 share, the largest |r| and its null; and of
#    each dword's sum over the varying records;
#  - the first two tests again on plateaus of two reads or more whose arguments stay the same through them.
# Summaries only (counts, shares, correlations, record offsets). The plateaus with their argument values go to
# <priv json> (the title's data, deleted with the reads). Runs on the box in the ubuntu distrobox (numpy), on the title's
# data; --selftest runs the segmentation and the statistics on synthetic plateaus (pure Python, no numpy).
# usage: python3 -I pl0295.py <capture dir> <reads json> <direct.log> <swz0248-z4.json> <priv json> [permutations]
#        python3 -I pl0295.py --selftest
import collections, glob, json, os, random, re, struct, sys

X0, X1, Y0, Y1 = 300, 1900, 400, 680
ARGS = re.compile(r"^draw journal args buf \d+ at \d+: op \S+ base1 ([0-9a-f]+) \+0x([0-9a-f]+)")


def popcount(x):
    return bin(x).count("1")


def segment(dz):
    """The plateaus of one burst, as lists of read positions, from the depth words changed between consecutive reads."""
    runs, cur = [], [0]
    for k, d in enumerate(dz):
        if d == 0:
            cur.append(k + 1)
        else:
            runs.append(cur)
            cur = [k + 1]
    runs.append(cur)
    return runs


def ranks(v):
    o = sorted(range(len(v)), key=lambda i: v[i])
    r, i = [0.0] * len(v), 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = (i + j) / 2
        i = j + 1
    return r


def pearson(x, y):
    n = len(x)
    if n < 3:
        return float("nan")
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx, syy = sum((a - mx) ** 2 for a in x), sum((b - my) ** 2 for b in y)
    return sxy / (sxx * syy) ** 0.5 if sxx > 0 and syy > 0 else float("nan")


def spearman(x, y):
    return pearson(ranks(x), ranks(y))


def nz(v):
    return 0.0 if v != v else v


def stats(pls, phi, nperm, rng, title, full=True):
    """pls: plateaus (dicts: id, burst, ks, family or None, size, share, stable, args {record: 4-tuple});
    phi: {(id, id'): hole phi} for every pair of labelled plateaus, id < id'."""
    lab = [p for p in pls if p["family"]]
    fams = collections.Counter(p["family"] for p in lab)
    print("# %s: %d plateaus, %d labelled (%s)" % (title, len(pls), len(lab), ", ".join("%s %d" % kv for kv in sorted(fams.items()))))
    common = set.intersection(*(set(p["args"]) for p in lab)) if lab else set()
    vary = sorted(r for r in common if len({p["args"][r] for p in lab}) > 1)
    print("  argument records read in every labelled plateau %d, of them varying %d" % (len(common), len(vary)))
    pairs = [(p, q) for a, p in enumerate(lab) for q in lab[a + 1:] if p["burst"] != q["burst"]]
    if len(pairs) < 10 or not vary:
        print("  too few pairs across bursts (%d) or no varying record" % len(pairs))
        return
    full_mask = (1 << len(pairs)) - 1
    eqbits = {}
    for r in vary:
        b = 0
        for k, (p, q) in enumerate(pairs):
            if p["args"][r] == q["args"][r]:
                b |= 1 << k
        eqbits[r] = b
    eqshare = [sum(eqbits[r] >> k & 1 for r in vary) / len(vary) for k in range(len(pairs))]
    hv = [phi[(min(p["id"], q["id"]), max(p["id"], q["id"]))] for p, q in pairs]

    def same_bits(labels):
        s = 0
        for k, (p, q) in enumerate(pairs):
            if labels[p["id"]] == labels[q["id"]]:
                s |= 1 << k
        return s

    def mean_diff(sb):
        same = [eqshare[k] for k in range(len(pairs)) if sb >> k & 1]
        diff = [eqshare[k] for k in range(len(pairs)) if not sb >> k & 1]
        if not same or not diff:
            return None, same, diff
        return sum(same) / len(same) - sum(diff) / len(diff), same, diff

    ids = [p["id"] for p in lab]
    labels = {p["id"]: p["family"] for p in lab}
    sb0 = same_bits(labels)
    obs, same, diff = mean_diff(sb0)
    shuffled = [labels[i] for i in ids]
    if obs is None:
        print("  no same-family pair, or no different-family pair, across bursts")
    else:
        null = []
        for _ in range(nperm):
            rng.shuffle(shuffled)
            d = mean_diff(same_bits(dict(zip(ids, shuffled))))[0]
            null.append(d if d is not None else 0.0)
        print("  equal varying records per pair: same family %.3f (%d pairs), different families %.3f (%d pairs); difference %+.3f, permutation p %.4f" % (
            sum(same) / len(same), len(same), sum(diff) / len(diff), len(diff), obs, (1 + sum(1 for d in null if d >= obs)) / (nperm + 1)))
        for nm, cond in (("same family", lambda p, q: p["family"] == q["family"]), ("different families", lambda p, q: p["family"] != q["family"])):
            ss = [(eqshare[k], hv[k]) for k, (p, q) in enumerate(pairs) if cond(p, q) and p["size"] == q["size"]]
            ds = [(eqshare[k], hv[k]) for k, (p, q) in enumerate(pairs) if cond(p, q) and p["size"] != q["size"]]
            print("    %s: same render size %s (%d pairs), different size %s (%d pairs) [equal share / hole phi]" % (
                nm, "%.3f / %+.3f" % (sum(e for e, _ in ss) / len(ss), sum(h for _, h in ss) / len(ss)) if ss else "-", len(ss),
                "%.3f / %+.3f" % (sum(e for e, _ in ds) / len(ds), sum(h for _, h in ds) / len(ds)) if ds else "-", len(ds)))
    # Mantel: the hole phi of a pair against its share of equal records, plateaus shuffled
    rk_eq = ranks(eqshare)
    r_obs = pearson(ranks(hv), rk_eq)
    perm, ge = list(ids), 0
    for _ in range(nperm):
        rng.shuffle(perm)
        m = dict(zip(ids, perm))
        hp = [phi[(min(m[p["id"]], m[q["id"]]), max(m[p["id"]], m[q["id"]]))] for p, q in pairs]
        if nz(pearson(ranks(hp), rk_eq)) >= nz(r_obs):
            ge += 1
    print("  Mantel: Spearman of hole phi with the share of equal varying records, %d pairs: %+.3f, permutation p %.4f" % (
        len(pairs), nz(r_obs), (1 + ge) / (nperm + 1)))
    # a slow drift over the run would make pairs close in time alike in both; the time between the plateaus, per pair
    dt = [abs(p["wall"] - q["wall"]) for p, q in pairs]
    print("    drift check, Spearman with the time between the two plateaus: of the equal share %+.3f, of the hole phi %+.3f" % (
        nz(spearman(dt, eqshare)), nz(spearman(dt, hv))))
    if not full or obs is None:
        return
    # per record: equal in same-family pairs minus in different-family pairs, against the null of the largest
    def rec_diffs(sb):
        ns, nd = popcount(sb), len(pairs) - popcount(sb)
        return {r: popcount(eqbits[r] & sb) / ns - popcount(eqbits[r] & ~sb & full_mask) / nd for r in vary}

    rd0 = rec_diffs(sb0)
    null_max = []
    for _ in range(nperm):
        rng.shuffle(shuffled)
        sb = same_bits(dict(zip(ids, shuffled)))
        if 0 < popcount(sb) < len(pairs):
            null_max.append(max(rec_diffs(sb).values()))
    null_max.sort()
    top = sorted(rd0.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    ns = popcount(sb0)
    print("  per record, equal in same-family pairs minus in different-family pairs, the largest 10 (null of the largest: median %.3f, 95th percentile %.3f; p of the top %.4f):" % (
        null_max[len(null_max) // 2], null_max[int(0.95 * len(null_max))], (1 + sum(1 for v in null_max if v >= top[0][1])) / (len(null_max) + 1)))
    for r, d in top:
        print("    %x: %+.3f (equal in %d of %d same-family pairs, %d of %d different)" % (
            r, d, popcount(eqbits[r] & sb0), ns, popcount(eqbits[r] & ~sb0 & full_mask), len(pairs) - ns))
    # per record and dword: the value against the plateau's depth-0 share
    sh = [p["share"] for p in lab]
    cells = []
    for r in vary:
        for d in range(4):
            v = [p["args"][r][d] for p in lab]
            if len(set(v)) > 1:
                cells.append((r, d, ranks(v)))
    rs = ranks(sh)
    obs_r = sorted(((abs(nz(pearson(rk, rs))), nz(pearson(rk, rs)), r, d) for r, d, rk in cells), reverse=True)
    shp, nmax = list(sh), []
    for _ in range(min(nperm, 1000)):
        rng.shuffle(shp)
        rp = ranks(shp)
        nmax.append(max(abs(nz(pearson(rk, rp))) for _, _, rk in cells))
    nmax.sort()
    print("  value against the plateau's depth-0 share, %d varying record dwords over %d plateaus; the largest |Spearman| 5 (null of the largest: median %.3f, 95th percentile %.3f; p of the top %.4f):" % (
        len(cells), len(lab), nmax[len(nmax) // 2], nmax[int(0.95 * len(nmax))], (1 + sum(1 for v in nmax if v >= obs_r[0][0])) / (len(nmax) + 1)))
    for a, r_, r, d in obs_r[:5]:
        print("    %x dword %d: %+.3f" % (r, d, r_))
    print("  each dword's sum over the varying records against the depth-0 share: %s" % ", ".join(
        "dword %d %+.3f" % (d, nz(spearman([sum(p["args"][r][d] for r in vary) for p in lab], sh))) for d in range(4)))


def report(pls, phi, nperm, seed):
    print("# plateaus per burst: reads, family (? not clear, - clear without a family), * arguments changed inside, render size")
    for b in sorted({p["burst"] for p in pls}):
        print("  %s: %s" % (b, " | ".join("z%s %s%s %s" % (
            "%d-%d" % (p["ks"][0], p["ks"][-1]) if len(p["ks"]) > 1 else p["ks"][0],
            p["family"] or ("-" if p["clear"] else "?"), "" if p["stable"] else "*", p["size"] or "-") for p in pls if p["burst"] == b)))
    starts = []
    for b in sorted({p["burst"] for p in pls}):
        long_ = [p for p in pls if p["burst"] == b and len(p["ks"]) >= 2]
        starts += [(q["wall"] - p["wall"]) * 1000 for p, q in zip(long_, long_[1:])]
    starts.sort()
    lens = collections.Counter(len(p["ks"]) for p in pls)
    print("  plateau lengths (reads): %s; between the starts of consecutive plateaus of 2+ reads in a burst: %s" % (
        ", ".join("%d: %d" % kv for kv in sorted(lens.items())),
        "median %.0f ms, range %.0f-%.0f ms (%d)" % (starts[len(starts) // 2], starts[0], starts[-1], len(starts)) if starts else "none"))
    nb = []
    for b in sorted({p["burst"] for p in pls}):
        long_ = [p for p in pls if p["burst"] == b and len(p["ks"]) >= 2]
        nb += list(zip(long_, long_[1:]))
    print("  consecutive plateaus of 2+ reads in one burst: %d pairs, arguments different in %d" % (
        len(nb), sum(1 for p, q in nb if any(p["args"].get(r) != q["args"].get(r) for r in set(p["args"]) | set(q["args"])))))
    rng = random.Random(seed)
    stats(pls, phi, nperm, rng, "all plateaus")
    stats([p for p in pls if len(p["ks"]) >= 2 and p["stable"]], phi, nperm, rng, "plateaus of 2+ reads, arguments unchanged inside", full=False)


def collect(cdir, rjson, log, zsw, priv):
    import numpy as np
    pz = json.load(open(zsw))["patterns"]["4"]
    recs = set()
    for l in open(log, errors="replace"):
        if l.startswith("draw journal args"):
            m = ARGS.match(l)
            if m:
                recs.add(int(m[1], 16) + int(m[2], 16))
    rj = json.load(open(rjson))
    reads = {r["name"]: r for r in rj["reads"]}
    famof = {n: f["name"] for f in rj["families"] for n in f["reads"]}

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

    pls, masks = [], {}
    for tf in sorted(glob.glob(os.path.join(cdir, "b*.times.txt"))):
        b = os.path.basename(tf).split(".")[0]
        lines = {l.split()[0]: l for l in open(tf) if l.strip()}
        zpath = lambda k: os.path.join(cdir, "%s.z%d.bin" % (b, k))
        ks, k = [], 0
        while "z%d" % k in lines and "a%d" % k in lines and " error " not in lines["z%d" % k] + lines["a%d" % k] and os.path.exists(zpath(k)):
            ks.append(k)
            k += 1
        if not ks:
            continue
        dz, prev = [], np.frombuffer(open(zpath(ks[0]), "rb").read(), dtype="<u4")
        for k in ks[1:]:
            cur = np.frombuffer(open(zpath(k), "rb").read(), dtype="<u4")
            n = min(prev.size, cur.size)
            dz.append(int((prev[:n] != cur[:n]).sum()) + abs(prev.size - cur.size))
            prev = cur
        for run in segment(dz):
            kk = [ks[i] for i in run]
            r0 = reads.get("%s.z%d" % (b, kk[0]))
            fam = next((famof[n] for n in ("%s.z%d" % (b, k) for k in kk) if n in famof), None)
            a = [args_of(b, "a%d" % k, lines["a%d" % k]) for k in kk]
            p = {"id": len(pls), "burst": b, "ks": kk, "wall": float(lines["z%d" % kk[0]].split()[2]), "family": fam,
                 "size": r0["best"] if r0 else None, "clear": bool(r0 and r0["clear"]),
                 "share": r0["sizes"][str(r0["best"])]["share"] if r0 else None, "stable": all(x == a[0] for x in a[1:]), "args": a[0]}
            if fam:
                masks[p["id"]] = depth0(zpath(kk[0]), r0["best"])
            pls.append(p)
    phi, ids = {}, sorted(masks)
    for x in range(len(ids)):
        for y in range(x + 1, len(ids)):
            (d1, ok1), (d2, ok2) = masks[ids[x]], masks[ids[y]]
            m = ok1 & ok2
            u, v = d1[m].astype(float), d2[m].astype(float)
            phi[(ids[x], ids[y])] = float(np.corrcoef(u, v)[0, 1]) if u.std() > 0 and v.std() > 0 else (1.0 if (u == v).all() else 0.0)
    print("# %s: %d argument records; %d plateaus in %d bursts" % (cdir, len(recs), len(pls), len({p["burst"] for p in pls})))
    json.dump({"plateaus": [dict(p, args={"%x" % r: list(v) for r, v in p["args"].items()}) for p in pls],
               "phi": [[i, j, v] for (i, j), v in sorted(phi.items())]}, open(priv, "w"))
    os.chmod(priv, 0o600)
    return pls, phi


def synthetic(rng, carriers):
    """Bursts of 8 reads 30 ms apart over frames of 4 reads (3 identical reads, then one in the middle of a write);
    a hole state X/Y per frame that holds 1-4 frames; 40 records drawn anew every frame from a few values (so frames
    share some by chance), 5 constant, and `carriers` records whose value follows the hole state in 70 % of frames.
    Unclear reads (no family) one in four."""
    pls, phi_of, recs = [], {}, list(range(0x1000, 0x1000 + 0x20 * (45 + carriers), 0x20))
    state, left = "X", 0
    for bn in range(16):
        b, dz, frames, off = "b%02d" % (bn + 1), [], [], rng.randrange(4)
        for k in range(8):
            fi = (k + off) // 4
            while len(frames) <= fi:
                if left == 0:
                    state, left = rng.choice("XY"), rng.randint(1, 4)
                left -= 1
                vals = {r: (rng.randrange(6), rng.randrange(3), 0, 0) for r in recs[:40]}
                vals.update({r: (7, 1, 0, 0) for r in recs[40:45]})
                vals.update({r: ((300 if state == "X" else 500) + 4 * (r & 0x60) if rng.random() < 0.7 else rng.randrange(6), 1, 0, 0)
                             for r in recs[45:]})
                frames.append((state, vals, rng.random() < 0.75, rng.choice((2560, 3072, 3328))))
            if k:
                dz.append(0 if (k + off) // 4 == (k - 1 + off) // 4 and (k + off) % 4 != 3 else 1000)
        for run in segment(dz):
            fi = (run[0] + off) // 4
            st, vals, clear, size = frames[fi]
            mid = (run[0] + off) % 4 == 3
            fam = st if clear and not mid else None
            pls.append({"id": len(pls), "burst": b, "ks": run, "wall": bn * 11 + run[0] * 0.03, "family": fam, "size": size,
                        "clear": clear and not mid, "share": (0.36 if st == "X" else 0.33) + rng.uniform(-0.03, 0.03),
                        "stable": True, "args": dict(vals)})
            phi_of[len(pls) - 1] = st
    phi = {}
    lab = [p["id"] for p in pls if p["family"]]
    for x in range(len(lab)):
        for y in range(x + 1, len(lab)):
            same = phi_of[lab[x]] == phi_of[lab[y]]
            phi[(lab[x], lab[y])] = (0.85 if same else 0.15) + rng.uniform(-0.1, 0.1)
    return pls, phi


if __name__ == "__main__":
    if sys.argv[1:2] == ["--selftest"]:
        print("# selftest: segment([0, 0, 5, 0, 0, 5, 0]) = %s (expect [[0, 1, 2], [3, 4, 5], [6, 7]])" % segment([0, 0, 5, 0, 0, 5, 0]))
        for carriers, nm in ((5, "five records follow the hole state: expect same > different, small p, carriers on top"),
                             (0, "no record follows it: expect no difference, p not small")):
            print("# selftest, %s" % nm)
            pls, phi = synthetic(random.Random(295 + carriers), carriers)
            report(pls, phi, 400, 1)
        sys.exit(0)
    cdir, rjson, log, zsw, priv = sys.argv[1:6]
    nperm = int(sys.argv[6]) if len(sys.argv) > 6 else 2000
    pls, phi = collect(cdir, rjson, log, zsw, priv)
    report(pls, phi, nperm, 295)
