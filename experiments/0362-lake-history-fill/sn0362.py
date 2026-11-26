#!/usr/bin/env python3
# BC5 experiment 0362: what each of the night lake's per-frame depth bursts writes, per hole half, from pl0362.py's
# snapshots (the depth image at +0x300000 .. +0xa00000; s0 after the frame's start, s1 after its first D burst, s2 after
# its second).
#
# "reads": each snapshot's size by the block-row shear (rd0312.py's: ADDR_SW_64KB_Z_X at 16 pipes, swz0248-z4.json; the
#   mean log-depth step across block-row boundaries over the mean step elsewhere), over the block rows that lie whole
#   inside the snapshot; clear when the next-best shear is at least 3 x the best. Writes a reads JSON in rd0312.py's
#   layout ({"reads": [{name, kind "z", wall, clear, best, shear}]}) for fr0354.py's journal fit.
# "ana": each snapshot decoded into the lake window (x 300..1900, y 400..680 of the 1920 x 1080 shot, nearest pixel),
#   only pixels inside the snapshot and in 0..1. A snapshot's width: its own when clear, else fr0354.py's journal width.
#   States from each frame's s2 (untorn, width 2048-2560): depth-0 share over the pixels valid in all of them; below
#   FLOOR "0", the rest split into A and B by the leading eigenvector of the centred phi matrix (ph0357.py's method).
#   X, Y: the pixels at 0 in at least half of the A frames and of the B frames; O: the rest of the window.
#   Per frame (s0, s1, s2 untorn) and per region, the shares of: s1 != s0 (c01), s2 != s1 (c12), s0 != the previous
#   frame's s2 (cP0), s2 == the previous frame's s2 (kP), and sJ == 0 (z0, z1, z2); a pair only when both snapshots have
#   the same width. Each half gets a class: "b1" (written in burst 1: c01 >= 0.5 and >= 2 x c12), "b2" (likewise in
#   burst 2), "b12" (both >= 0.5), "kept" (both < 0.2 and kP >= 0.9), "zero" (both < 0.2 and z2 >= 0.5), "none" (both
#   < 0.2 otherwise), "mix" (the rest), "?" (a pair missing). Prints the frames, the class pairs by the previous and
#   this frame's state, and the region means. Summaries only.
# "--selftest": three planted lakes on a synthetic window (checkerboard halves X and Y, an O band): both halves in
#   burst 1; one half drawn in burst 1 and the other filled in burst 2; one half drawn and the other kept. Each must
#   come out as its class pair.
# usage: python3 -I sn0362.py reads <snap dir> <swz0248-z4.json> <out json>
#        python3 -I sn0362.py ana <snap dir> <reads json> <fr json> <swz0248-z4.json> <out json> [FLOOR]
#        python3 -I sn0362.py --selftest        (on the box, in the distrobox)
import json, os, re, sys
import numpy as np

WIDTHS = (2048, 2304, 2560, 2816, 3072)
LABEL_W = (2048, 2304, 2560)
X0, X1, Y0, Y1 = 300, 1900, 400, 680
S_OFF, S_LEN = 0x300000, 0x700000
SNAP = re.compile(r"(c\d+) f(\d+) s(\d) wall ([\d.]+) mono ([\d.]+) since ([-\d.]+) read ([\d.]+) torn (\d)")


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


class Swz:
    def __init__(self, path):
        self.p = json.load(open(path))["patterns"]["4"]
        self.win, self.rows = {}, {}

    def local(self, w, ys, xs):  # word index within the snapshot of pixels (ys x xs) at width w
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
            lo, hi = -(-S_OFF // row), (S_OFF + S_LEN) // row - 1
            hi = min(hi, (h - 1) // 128)
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
            out.append({"name": "%s.f%s.s%s" % (m[1], m[2], m[3]), "cap": m[1], "f": int(m[2]), "s": int(m[3]),
                        "wall": float(m[4]), "mono": float(m[5]), "since": float(m[6]), "read": float(m[7]), "torn": int(m[8])})
    return out


def load(sdir, name):
    return np.frombuffer(open(os.path.join(sdir, name + ".bin"), "rb").read(), dtype="<f4").astype(np.float64)


def cmd_reads(sdir, zsw, out):
    sw = Swz(zsw)
    reads = []
    for s in snaps_of(sdir):
        raw = load(sdir, s["name"])
        sh = {w: sw.shear(raw, w) for w in WIDTHS}
        fin = sorted((v, w) for w, v in sh.items() if v == v)
        best = fin[0][1] if fin else None
        clear = len(fin) >= 2 and fin[1][0] >= 3 * fin[0][0]
        reads.append({"name": s["name"], "kind": "z", "wall": s["wall"], "clear": bool(clear), "best": best,
                      "shear": {str(w): round(v, 3) for w, v in sh.items()}, "torn": s["torn"], "since": s["since"]})
    json.dump({"reads": reads}, open(out, "w"), indent=0)
    for j in range(3):
        rs = [r for r in reads if r["name"].endswith(".s%d" % j)]
        ws = {}
        for r in rs:
            if r["clear"]:
                ws[r["best"]] = ws.get(r["best"], 0) + 1
        print("# s%d: %d snapshots, %d torn, %d with a clear size %s; since the frame's start: median %.1f ms" % (
            j, len(rs), sum(r["torn"] for r in rs), sum(r["clear"] for r in rs), dict(sorted(ws.items())),
            float(np.median([r["since"] for r in rs])) if rs else float("nan")))


def states(frames, floor):  # frames: list of dicts with "s2": (z, ok, w) or None; sets f["state"]
    lab = [f for f in frames if f.get("s2") is not None and f["s2"][2] in LABEL_W]
    for f in frames:
        f["state"] = "?"
    if len(lab) < 4:
        return None, None, "too few labelled frames (%d)" % len(lab)
    common = np.logical_and.reduce([f["s2"][1] for f in lab])
    M = np.array([((f["s2"][0] == 0) & f["s2"][1])[common] for f in lab], dtype=np.float64)
    share = M.mean(axis=1)
    keep = share >= floor
    for f, k in zip(lab, keep):
        if not k:
            f["state"] = "0"
    hz = [f for f, k in zip(lab, keep) if k]
    note = "%d frames labelled at widths %s: %d below the floor %.2f, %d with holes" % (
        len(lab), LABEL_W, int((~keep).sum()), floor, len(hz))
    if len(hz) < 4:
        return None, None, note + "; too few with holes to split"
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
    shape = lab[0]["s2"][0].shape
    X = np.zeros(shape, bool)
    Y = np.zeros(shape, bool)
    X[common] = Mh[a].mean(axis=0) >= 0.5 if len(a) else False
    Y[common] = Mh[b].mean(axis=0) >= 0.5 if len(b) else False
    note += "; A %d, B %d, phi within %.2f / %.2f, between %.2f; X %.3f, Y %.3f of the window, X and Y share %.4f" % (
        len(a), len(b), within[0], within[1], between, X.mean(), Y.mean(), (X & Y).mean())
    return X, Y, note


def klass(st):
    w1, w2, k, z2 = st.get("c01"), st.get("c12"), st.get("kP"), st.get("z2")
    if w1 is None or w2 is None:
        return "?"
    if w1 >= 0.5 and w2 >= 0.5:
        return "b12"
    if w1 >= 0.5 and w1 >= 2 * w2:
        return "b1"
    if w2 >= 0.5 and w2 >= 2 * w1:
        return "b2"
    if w1 < 0.2 and w2 < 0.2:
        if k is not None and k >= 0.9:
            return "kept"
        if z2 is not None and z2 >= 0.5:
            return "zero"
        return "none"
    return "mix"


def region_stats(f, prev, R):
    out = {}
    s = {j: f.get("s%d" % j) for j in range(3)}

    def share(a, b, eq):
        if a is None or b is None or a[2] != b[2]:
            return None
        m = R & a[1] & b[1]
        if m.sum() == 0:
            return None
        return float(((a[0] == b[0]) if eq else (a[0] != b[0]))[m].mean())

    out["c01"] = share(s[0], s[1], False)
    out["c12"] = share(s[1], s[2], False)
    pv = prev.get("s2") if prev is not None else None
    out["cP0"] = share(pv, s[0], False)
    out["kP"] = share(pv, s[2], True)
    for j in range(3):
        if s[j] is not None:
            m = R & s[j][1]
            out["z%d" % j] = float((s[j][0] == 0)[m].mean()) if m.sum() else None
    return out


def analyse(frames, floor, out=None, quiet=False):
    X, Y, note = states(frames, floor)
    print("# states: " + note)
    if X is None:
        return None
    O = ~(X | Y)
    regions = (("X", X), ("Y", Y), ("O", O))
    groups, means = {}, {}
    rows = []
    for i, f in enumerate(frames):
        prev = frames[i - 1] if i > 0 and frames[i - 1]["cap"] == f["cap"] and frames[i - 1]["f"] == f["f"] - 1 else None
        st = {nm: region_stats(f, prev, R) for nm, R in regions}
        cls = (klass(st["X"]), klass(st["Y"]))
        pst = prev["state"] if prev is not None else "-"
        key = "%s>%s" % (pst, f["state"])
        groups.setdefault(key, {}).setdefault("%s/%s" % cls, 0)
        groups[key]["%s/%s" % cls] += 1
        for nm in ("X", "Y", "O"):
            for q, v in st[nm].items():
                if v is not None:
                    means.setdefault((key, nm, q), []).append(v)
        rows.append({"frame": f["name"], "w": [f["s%d" % j][2] if f.get("s%d" % j) else None for j in range(3)],
                     "since": f.get("since"), "state": f["state"], "prev": pst, "class": cls, "stats": st})
        if not quiet:
            def fm(d):
                return " ".join("%s %s" % (q, "-" if d.get(q) is None else "%.2f" % d[q]) for q in ("z0", "z1", "z2", "c01", "c12", "cP0", "kP"))
            print("  %s w %s since %s %s>%s X %-4s Y %-4s | X %s | Y %s | O %s" % (
                f["name"], "/".join(str(w) if w else "-" for w in rows[-1]["w"]),
                "/".join("%.1f" % x if x is not None else "-" for x in (f.get("since") or [None] * 3)), pst, f["state"],
                cls[0], cls[1], fm(st["X"]), fm(st["Y"]), fm(st["O"])))
    print("# class pairs (X/Y) by previous>this frame's state:")
    for key in sorted(groups):
        print("  %-5s %s" % (key, ", ".join("%s %d" % kv for kv in sorted(groups[key].items(), key=lambda kv: -kv[1]))))
    print("# region means by previous>this state (n frames):")
    for key in sorted(groups):
        for nm in ("X", "Y", "O"):
            print("  %-5s %s %s" % (key, nm, " ".join("%s %s" % (q, "-" if (key, nm, q) not in means else "%.2f(%d)" % (
                np.mean(means[(key, nm, q)]), len(means[(key, nm, q)]))) for q in ("z0", "z1", "z2", "c01", "c12", "cP0", "kP"))))
    if out:
        json.dump({"note": note, "groups": groups, "rows": rows}, open(out, "w"), indent=0, default=str)
    return groups


def cmd_ana(sdir, rjson, fjson, zsw, out, floor):
    sw = Swz(zsw)
    reads = {r["name"]: r for r in json.load(open(rjson))["reads"]}
    fr = json.load(open(fjson))
    jsz = fr.get("sizes", {})
    agree = [(r["best"], jsz[n]) for n, r in reads.items() if r["clear"] and n in jsz]
    print("# journal lag %s ms (%s field); own clear size and journal size agree in %d of %d snapshots" % (
        fr.get("lag_ms"), fr.get("field"), sum(a == b for a, b in agree), len(agree)))
    snaps = snaps_of(sdir)
    by = {}
    for s in snaps:
        by.setdefault((s["cap"], s["f"]), {})[s["s"]] = s
    frames = []
    nw = {"own": 0, "journal": 0, "none": 0, "torn": 0}
    for (cap, k) in sorted(by):
        f = {"name": "%s.f%d" % (cap, k), "cap": cap, "f": k, "since": [None] * 3}
        for j, s in by[(cap, k)].items():
            f["since"][j] = s["since"]
            if s["torn"]:
                nw["torn"] += 1
                continue
            r = reads.get(s["name"], {})
            w = r.get("best") if r.get("clear") else jsz.get(s["name"])
            if w is None:
                nw["none"] += 1
                continue
            nw["own" if r.get("clear") else "journal"] += 1
            z, ok = sw.window(load(sdir, s["name"]), int(w))
            f["s%d" % j] = (z, ok, int(w))
        frames.append(f)
    print("# %d frames; snapshot widths: own %d, journal %d, none %d; torn %d" % (
        len(frames), nw["own"], nw["journal"], nw["none"], nw["torn"]))
    analyse(frames, floor, out)


def selftest():
    rng = np.random.default_rng(362)
    H, W = 40, 96
    yy, xx = np.mgrid[0:H, 0:W]
    lake = yy >= 8
    Xc = lake & (((yy // 8) + (xx // 8)) % 2 == 0)
    Yc = lake & ~Xc
    ok = np.ones((H, W), bool)
    print("# selftest: a 40 x 96 window, X and Y a checkerboard of 8-pixel cells below an 8-row band O; 8 captures"
          " of 5 frames, states held at random (clean, A = X at 0, B = Y at 0)")
    res = {}
    for mode in ("burst1", "fill2", "kept"):
        frames = []
        for c in range(8):
            prev_final = rng.uniform(0.1, 0.9, (H, W))
            seq = rng.choice(["0", "0", "A", "B"], size=5)
            for k in range(5):
                stt = seq[k]
                s0 = prev_final.copy()
                anim = rng.uniform(0.1, 0.9, (H, W))
                drawn = Xc if (c + k) % 2 == 0 else Yc  # the half drawn this frame (fill and kept modes)
                if mode == "burst1":
                    s1 = np.where(lake, anim, s0)
                    s2 = s1.copy()
                elif mode == "fill2":
                    s1 = np.where(drawn, anim, s0)
                    s2 = np.where(lake & ~drawn, rng.uniform(0.1, 0.9, (H, W)), s1)
                else:
                    s1 = np.where(drawn, anim, s0)
                    s2 = s1.copy()
                if stt == "A":
                    s2 = np.where(Xc, 0.0, s2)
                elif stt == "B":
                    s2 = np.where(Yc, 0.0, s2)
                s2 = np.where(lake, s2, np.where(rng.random((H, W)) < 0.5, anim, s2))
                f = {"name": "c%02d.f%d" % (c, k), "cap": "c%02d" % c, "f": k, "since": [1.0, 8.0, 20.0],
                     "s0": (s0, ok, 2560), "s1": (s1, ok, 2560), "s2": (s2, ok, 2560)}
                frames.append(f)
                prev_final = s2
        print("# mode %s:" % mode)
        g = analyse(frames, 0.03, quiet=True)
        tot = {}
        for key, d in (g or {}).items():
            if key == "0>0":
                for cl, n in d.items():
                    tot[cl] = tot.get(cl, 0) + n
        res[mode] = tot
    print("# clean frames after clean frames, class pairs: %s" % res)
    ok1 = max(res["burst1"], key=res["burst1"].get) == "b1/b1"
    ok2 = set(max(res["fill2"], key=res["fill2"].get).split("/")) == {"b1", "b2"}
    ok3 = set(max(res["kept"], key=res["kept"].get).split("/")) == {"b1", "kept"}
    print("# selftest: burst1 -> b1/b1 %s; fill2 -> b1 + b2 %s; kept -> b1 + kept %s" % (ok1, ok2, ok3))
    sys.exit(0 if ok1 and ok2 and ok3 else 1)


if sys.argv[1:2] == ["--selftest"]:
    selftest()
elif sys.argv[1:2] == ["reads"]:
    cmd_reads(*sys.argv[2:5])
elif sys.argv[1:2] == ["ana"]:
    cmd_ana(*sys.argv[2:7], float(sys.argv[7]) if len(sys.argv) > 7 else 0.03)
else:
    print(__doc__ or "usage: see the header")
    sys.exit(2)
