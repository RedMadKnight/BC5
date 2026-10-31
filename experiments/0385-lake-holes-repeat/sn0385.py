#!/usr/bin/env python3
# BC5 experiment 0385: exp 0369's sn0369.py with 0369 -> 0385 (mkkit0385.py). Older comments below keep their wording.
# BC5 experiment 0385, run K2: exp 0365's sn0365.py with 0365 -> 0385 (its reads and definitions; tz0385.py loads them).
# BC5 experiment 0385: what the night lake's hole pixels hold mid-frame and after the frame's last burst, and where the
# final values of pixels that were 0 mid-frame come from, from pl0385.py's snapshots (the depth image at +0x300000 ..
# +0xa00000; sM between the frame's second and third D burst, sF after its last).
#
# "reads": each snapshot's block-row shear at widths 2048-3328 (exp 0362's sn0362.py: rd0312.py's ADDR_SW_64KB_Z_X at
#   16 pipes, swz0248-z4.json, over the block rows whole inside the snapshot); clear when the next-best shear is >= 3 x
#   the best (and the best > 0.05). Writes <out json> {"reads": [{name, wall, since, torn, late, clear, best, shear}]}.
# "ana": a frame is used when its sF is untorn and clear at 2048-2816; its width W is sF's. sF and sM (untorn) are
#   decoded at W into the lake window (x 300..1900, y 400..680 of the 1920 x 1080 shot, nearest pixel; pixels inside the
#   snapshot and in 0..1).
#   - States from the finals: depth-0 share over the pixels valid in all of them; below FLOOR "0", the rest split into
#     A and B by the leading eigenvector of the centred phi matrix (ph0357.py's method); X and Y the pixels at 0 in at
#     least half of the A and of the B frames; O the rest of the window.
#   - Per frame and region (X, Y, O, all): z_mid (sM == 0), z_fin (sF == 0), filled (0 mid-frame, not 0 at the end),
#     stayed (0 in both), late zero (not 0 mid-frame, 0 at the end).
#   - Per pair of consecutive frames with finals at the same width (g-1, g): over g's filled pixels, the share whose
#     final equals g-1's final bitwise (copy) and the share where g-1's final was 0; the same equality over g's other
#     valid pixels that are not 0 in either final (the baseline: in exp 0362 no pixel kept its value between frames).
#   - The mid-frame zero masks: phi of each with X and with Y; whether the half that is 0 mid-frame (by phi) changes
#     between consecutive frames.
#   Prints the frames, then the tables by this and the previous frame's state. Summaries only.
# "--selftest": a synthetic window with checkerboard halves X and Y; three planted lakes, each with clean frames and
#   hole frames: (copy) half the cells 0 mid-frame, alternating, filled at the end with the previous frame's final;
#   (late) the same, filled with new values; (early) no zeros mid-frame in clean frames. The copy share over filled
#   pixels in clean frames must be ~1, ~0, and (no filled pixels) absent.
# usage: python3 -I sn0385.py reads <snap dir> <swz0248-z4.json> <out json>
#        python3 -I sn0385.py ana <snap dir> <reads json> <swz0248-z4.json> <out json> [FLOOR]
#        python3 -I sn0385.py --selftest        (on the box, in the distrobox)
import json, os, re, sys
import numpy as np

WIDTHS = (2048, 2304, 2560, 2816, 3072, 3328)
USE_W = (2048, 2304, 2560, 2816)
LABEL_W = (2048, 2304, 2560)
X0, X1, Y0, Y1 = 300, 1900, 400, 680
S_OFF, S_LEN = 0x300000, 0x700000
SNAP = re.compile(r"(c\d+) f(\d+) s([MF]) wall ([\d.]+) mono ([\d.]+) since ([-\d.]+) read ([\d.]+) torn (\d) late (\d) dch (\d+) dlast ([-\d.]+)")


def coord_offset(p, key, n):  # rd0312.py's
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


class Swz:  # exp 0362's
    def __init__(self, path):
        self.p = json.load(open(path))["patterns"]["4"]
        self.win, self.rows = {}, {}

    def local(self, w, ys, xs):
        h = w * 9 // 16
        fx, fy = coord_offset(self.p, "x", w), coord_offset(self.p, "y", h)
        pitch = -(-w // 128)
        blk = (ys // 128)[:, None] * pitch + (xs // 128)[None, :]
        return ((blk * 65536 + (fx[xs][None, :] ^ fy[ys][:, None])) >> 2) - S_OFF // 4

    def window(self, raw, w):
        if w not in self.win:
            h = w * 9 // 16
            self.win[w] = self.local(w, np.arange(Y0, Y1) * h // 1080, np.arange(X0, X1) * w // 1920)
        li = self.win[w]
        inside = (li >= 0) & (li < raw.size)
        z = raw[np.clip(li, 0, raw.size - 1)]
        with np.errstate(invalid="ignore"):
            ok = inside & np.isfinite(z) & (z >= 0) & (z <= 1)
        return z, ok

    def shear(self, raw, w):
        if w not in self.rows:
            h, pitch = w * 9 // 16, -(-w // 128)
            row = pitch * 65536
            lo, hi = -(-S_OFF // row), min((S_OFF + S_LEN) // row - 1, (h - 1) // 128)
            if hi - lo < 1:
                self.rows[w] = None
            else:
                ys = np.arange(lo * 128, (hi + 1) * 128)
                self.rows[w] = (ys, self.local(w, ys, np.arange(0, w, 4)))
        if self.rows[w] is None:
            return float("nan")
        ys, li = self.rows[w]
        img = raw[np.clip(li, 0, raw.size - 1)]
        good = np.isfinite(img) & (np.abs(img) < 1e30)
        l = np.log1p(np.abs(np.where(good, img, 0.0)))
        d = np.abs(np.diff(l, axis=0))
        at = ys[:-1] % 128 == 127
        den = d[~at].mean()
        return float(d[at].mean() / den) if den > 0 else float("nan")


def snaps_of(sdir):
    out = []
    for l in open(os.path.join(sdir, "snaps.txt")):
        m = SNAP.match(l)
        if m:
            out.append({"name": "%s.f%s.s%s" % (m[1], m[2], m[3]), "cap": m[1], "f": int(m[2]), "s": m[3], "wall": float(m[4]),
                        "since": float(m[6]), "read": float(m[7]), "torn": int(m[8]), "late": int(m[9]), "dch": int(m[10])})
    return out


def load(sdir, name):
    with np.errstate(invalid="ignore"):
        return np.frombuffer(open(os.path.join(sdir, name + ".bin"), "rb").read(), dtype="<f4").astype(np.float64)


def cmd_reads(sdir, zsw, out):
    sw = Swz(zsw)
    reads = []
    for s in snaps_of(sdir):
        raw = load(sdir, s["name"])
        sh = {w: sw.shear(raw, w) for w in WIDTHS}
        fin = sorted((v, w) for w, v in sh.items() if v == v)
        clear = len(fin) >= 2 and fin[0][0] > 0.05 and fin[1][0] >= 3 * fin[0][0]
        reads.append(dict(s, clear=bool(clear), best=fin[0][1] if fin else None, shear={str(w): round(v, 3) for w, v in sh.items()},
                          zeros=round(float((raw[::16] == 0).mean()), 4)))
    json.dump({"reads": reads}, open(out, "w"), indent=0)
    for j in "MF":
        rs = [r for r in reads if r["s"] == j]
        ws = {}
        for r in rs:
            if r["clear"]:
                ws[r["best"]] = ws.get(r["best"], 0) + 1
        print("# s%s: %d snapshots, %d torn, %d with a clear size %s; since the frame's start median %.1f ms; zero words median %.3f%s" % (
            j, len(rs), sum(r["torn"] for r in rs), sum(r["clear"] for r in rs), dict(sorted(ws.items())),
            float(np.median([r["since"] for r in rs])) if rs else float("nan"), float(np.median([r["zeros"] for r in rs])) if rs else float("nan"),
            "; after a late burst %d, at the cap %d" % (sum(r["late"] for r in rs), sum(1 - r["late"] for r in rs)) if j == "F" else ""))


def states(frames, floor):
    lab = [f for f in frames if f["w"] in LABEL_W]
    for f in frames:
        f["state"] = "?"
    if len(lab) < 2:
        return None, None, "too few finals (%d)" % len(lab)
    common = np.logical_and.reduce([f["okF"] for f in lab])
    M = np.array([((f["zF"] == 0) & f["okF"])[common] for f in lab], dtype=np.float64)
    share = M.mean(axis=1)
    keep = share >= floor
    for f, k in zip(lab, keep):
        if not k:
            f["state"] = "0"
    hz = [f for f, k in zip(lab, keep) if k]
    note = "%d finals at widths %s (common pixels %.3f of the window): %d below the floor %.2f, %d with holes" % (
        len(lab), LABEL_W, common.mean(), int((~keep).sum()), floor, len(hz))
    shape = lab[0]["zF"].shape
    X, Y = np.zeros(shape, bool), np.zeros(shape, bool)
    if len(hz) < 2:
        return X, Y, note + "; too few with holes to split"
    Mh = M[keep]
    Z = (Mh - Mh.mean(axis=1, keepdims=True)) / np.maximum(Mh.std(axis=1, keepdims=True), 1e-9)
    PHI = Z @ Z.T / Mh.shape[1]
    C = PHI - PHI.mean(axis=0, keepdims=True) - PHI.mean(axis=1, keepdims=True) + PHI.mean()
    _, v = np.linalg.eigh(C)
    side = v[:, -1] > 0
    for f, s in zip(hz, side):
        f["state"] = "A" if s else "B"
    a, b = np.where(side)[0], np.where(~side)[0]
    within = [float(PHI[np.ix_(g, g)][np.triu_indices(len(g), 1)].mean()) if len(g) > 1 else float("nan") for g in (a, b)]
    between = float(PHI[np.ix_(a, b)].mean()) if len(a) and len(b) else float("nan")
    if len(a):
        X[common] = Mh[a].mean(axis=0) >= 0.5
    if len(b):
        Y[common] = Mh[b].mean(axis=0) >= 0.5
    note += "; A %d, B %d, phi within %.2f / %.2f, between %.2f; X %.3f, Y %.3f of the window, both %.4f" % (
        len(a), len(b), within[0], within[1], between, X.mean(), Y.mean(), (X & Y).mean())
    return X, Y, note


def phi(m, R, ok):
    x, y = m[ok].astype(float), R[ok].astype(float)
    return float(np.corrcoef(x, y)[0, 1]) if x.size > 1 and x.std() > 0 and y.std() > 0 else float("nan")


def analyse(frames, floor, out=None, quiet=False):
    X, Y, note = states(frames, floor)
    print("# states: " + note)
    if X is None:
        return None
    regions = (("X", X), ("Y", Y), ("O", ~(X | Y)), ("all", np.ones(X.shape, bool)))
    byk = {(f["cap"], f["f"]): f for f in frames}
    acc, rows = {}, []

    def add(key, q, v):
        if v is not None and v == v:
            acc.setdefault((key, q), []).append(v)

    for f in frames:
        pv = byk.get((f["cap"], f["f"] - 1))
        pst = pv["state"] if pv is not None else "-"
        key = "%s>%s" % (pst, f["state"])
        r = {"frame": "%s.f%d" % (f["cap"], f["f"]), "w": f["w"], "state": f["state"], "prev": pst}
        zf = (f["zF"] == 0) & f["okF"]
        if f.get("zM") is not None:
            okm = f["okM"] & f["okF"]
            zm = (f["zM"] == 0) & okm
            filled, stayed, latez = zm & ~zf, zm & zf, ~zm & zf & okm
            for nm, R in regions:
                m = R & okm
                if m.sum() == 0:
                    continue
                for q, a in (("z_mid", zm), ("z_fin", zf), ("filled", filled), ("stayed", stayed), ("late0", latez)):
                    r[nm + "." + q] = float(a[m].mean())
                    add(key, nm + "." + q, r[nm + "." + q])
            r["midphiX"], r["midphiY"] = phi(zm, X, okm), phi(zm, Y, okm)
            add(key, "mid phi X", r["midphiX"])
            add(key, "mid phi Y", r["midphiY"])
            if pv is not None and pv["w"] == f["w"]:
                both = f["okF"] & pv["okF"] & okm
                eq = (f["zF"] == pv["zF"]) & both
                fp, other = filled & both, both & ~filled & ~zf & (pv["zF"] != 0)
                if fp.sum():
                    r["copy"] = float(eq[fp].mean())
                    r["from0"] = float((pv["zF"] == 0)[fp].mean())
                    add(key, "filled: equal to previous final", r["copy"])
                    add(key, "filled: previous final 0", r["from0"])
                if other.sum():
                    r["eq_other"] = float(eq[other].mean())
                    add(key, "other: equal to previous final", r["eq_other"])
                r["n_filled"] = int(fp.sum())
        else:
            for nm, R in regions:
                m = R & f["okF"]
                if m.sum():
                    r[nm + ".z_fin"] = float(zf[m].mean())
                    add(key, nm + ".z_fin", r[nm + ".z_fin"])
        rows.append(r)
        if not quiet:
            print("  %s w %d %s>%s mid %s | all: z_mid %s z_fin %.3f filled %s stayed %s late0 %s | X filled %s Y filled %s | mid phi X %s Y %s | copy %s (n %s) from0 %s other-eq %s" % (
                r["frame"], f["w"], pst, f["state"], "yes" if f.get("zM") is not None else "no",
                *["%.3f" % r[k] if k in r else "-" for k in ("all.z_mid",)], r.get("all.z_fin", float(zf[f["okF"]].mean())),
                *["%.3f" % r[k] if k in r else "-" for k in ("all.filled", "all.stayed", "all.late0", "X.filled", "Y.filled")],
                *["%+.2f" % r[k] if k in r and r[k] == r[k] else "-" for k in ("midphiX", "midphiY")],
                *["%.3f" % r[k] if k in r else "-" for k in ("copy",)], r.get("n_filled", "-"),
                *["%.3f" % r[k] if k in r else "-" for k in ("from0", "eq_other")]))
    sides = []
    for i in range(1, len(frames)):
        a, b = frames[i - 1], frames[i]
        if a["cap"] == b["cap"] and a["f"] == b["f"] - 1 and "midphiX" in rows[i] and "midphiX" in rows[i - 1]:
            sa = rows[i - 1]["midphiX"] > rows[i - 1]["midphiY"]
            sb = rows[i]["midphiX"] > rows[i]["midphiY"]
            sides.append(sa != sb)
    print("# mid-frame zero masks: the half nearer by phi changes between consecutive frames in %d of %d pairs" % (sum(sides), len(sides)))
    keys = sorted({k for k, _ in acc})
    print("# means by previous>this final state (n):")
    for key in keys:
        print("  %-5s %s" % (key, "; ".join("%s %.3f (%d)" % (q, float(np.mean(v)), len(v)) for (k2, q), v in sorted(acc.items()) if k2 == key and (
            q.startswith("all.") or q.startswith("filled") or q.startswith("other") or q.startswith("mid") or q.endswith(".filled") or q.endswith("z_fin")))))
    if out:
        json.dump({"note": note, "rows": rows, "pairs_mid_side_changes": [sum(sides), len(sides)]}, open(out, "w"), indent=0)
    return acc


def cmd_ana(sdir, rjson, zsw, out, floor):
    sw = Swz(zsw)
    reads = {r["name"]: r for r in json.load(open(rjson))["reads"]}
    by = {}
    for s in snaps_of(sdir):
        by.setdefault((s["cap"], s["f"]), {})[s["s"]] = s
    frames, skip = [], {"no final": 0, "final torn": 0, "final unclear": 0, "width": 0}
    for (cap, k) in sorted(by):
        sF = by[(cap, k)].get("F")
        if sF is None:
            skip["no final"] += 1
            continue
        r = reads[sF["name"]]
        if sF["torn"]:
            skip["final torn"] += 1
            continue
        if not r["clear"]:
            skip["final unclear"] += 1
            continue
        if r["best"] not in USE_W:
            skip["width"] += 1
            continue
        w = int(r["best"])
        zF, okF = sw.window(load(sdir, sF["name"]), w)
        f = {"cap": cap, "f": k, "w": w, "zF": zF, "okF": okF, "zM": None}
        sM = by[(cap, k)].get("M")
        if sM is not None and not sM["torn"]:
            f["zM"], f["okM"] = sw.window(load(sdir, sM["name"]), w)
        frames.append(f)
    print("# %d frames with a usable final (skipped: %s); %d with an untorn mid snapshot" % (
        len(frames), skip, sum(1 for f in frames if f["zM"] is not None)))
    analyse(frames, floor, out)


def selftest():
    rng = np.random.default_rng(365)
    H, W = 40, 96
    yy, xx = np.mgrid[0:H, 0:W]
    lake = yy >= 8
    Xc = lake & (((yy // 8) + (xx // 8)) % 2 == 0)
    Yc = lake & ~Xc
    ok = np.ones((H, W), bool)
    print("# selftest: a 40 x 96 window, X and Y a checkerboard of 8-pixel cells below an 8-row band; 8 captures of 6"
          " frames; finals at random clean (0), A (X at 0) or B (Y at 0)")
    res = {}
    for mode in ("copy", "late", "early"):
        frames = []
        for c in range(8):
            prev = rng.uniform(0.1, 0.9, (H, W))
            seq = rng.choice(["0", "0", "A", "B"], size=6)
            for k in range(6):
                new = rng.uniform(0.1, 0.9, (H, W))
                half = Xc if (c + k) % 2 == 0 else Yc  # the half not drawn by mid-frame (copy, late)
                if mode == "early":
                    mid = new.copy()
                    fin = new.copy()
                else:
                    mid = np.where(half, 0.0, new)
                    fin = np.where(half, prev if mode == "copy" else rng.uniform(0.1, 0.9, (H, W)), new)
                if seq[k] == "A":
                    fin = np.where(Xc, 0.0, fin)
                    mid = np.where(Xc, 0.0, mid)
                elif seq[k] == "B":
                    fin = np.where(Yc, 0.0, fin)
                    mid = np.where(Yc, 0.0, mid)
                frames.append({"cap": "c%02d" % c, "f": k, "w": 2560, "zF": fin, "okF": ok, "zM": mid, "okM": ok})
                prev = fin
        print("# mode %s:" % mode)
        acc = analyse(frames, 0.03, quiet=True)
        v = (acc or {}).get(("0>0", "filled: equal to previous final"))
        res[mode] = (round(float(np.mean(v)), 2), len(v)) if v else None
    print("# clean after clean, filled pixels equal to the previous final: %s" % res)
    ok1 = res["copy"] is not None and res["copy"][0] > 0.9
    ok2 = res["late"] is not None and res["late"][0] < 0.1
    ok3 = res["early"] is None
    print("# selftest: copy -> ~1 %s; late -> ~0 %s; early -> no filled pixels %s" % (ok1, ok2, ok3))
    sys.exit(0 if ok1 and ok2 and ok3 else 1)


if sys.argv[1:2] == ["--selftest"]:
    selftest()
elif sys.argv[1:2] == ["reads"]:
    cmd_reads(*sys.argv[2:5])
elif sys.argv[1:2] == ["ana"]:
    cmd_ana(*sys.argv[2:6], float(sys.argv[6]) if len(sys.argv) > 6 else 0.03)
else:
    print("usage: see the header")
    sys.exit(2)
