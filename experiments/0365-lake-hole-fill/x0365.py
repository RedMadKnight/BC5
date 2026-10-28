#!/usr/bin/env python3
# BC5 experiment 0365, added after sn0365.py ana showed filled pixels never equal to the previous final: what the
# mid-frame snapshot holds. Per frame with an untorn mid snapshot (sn0365.py ana's frames), at the final's width:
#   - mid vs this final: over pixels non-zero in both, the share bitwise equal (the last burst rewrote them or not);
#   - mid vs the previous frame's final (same capture, consecutive, same width): over pixels non-zero in both, the share
#     bitwise equal; phi of the mid zero mask with the previous final's zero mask and with this final's;
#   - the late zeros (non-zero mid-frame, 0 at the end): the share whose mid value equals the previous final's.
# Means by the previous>this final state, as in sn0365.py.
# usage: python3 -I x0365.py <snapshot dir> <reads json> <swizzle json> [FLOOR]   (on the box, beside sn0365.py)
import json, os, sys, types
import numpy as np

S = types.ModuleType("sn0365")  # sn0365.py's definitions, without its command dispatch at the end
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "sn0365.py")).read()
exec(compile(src[:src.index('\nif sys.argv[1:2] == ["--selftest"]:\n    selftest()')], "sn0365.py", "exec"), S.__dict__)

sdir, rjson, zsw = sys.argv[1:4]
floor = float(sys.argv[4]) if len(sys.argv) > 4 else 0.03
sw = S.Swz(zsw)
reads = {r["name"]: r for r in json.load(open(rjson))["reads"]}
by = {}
for s in S.snaps_of(sdir):
    by.setdefault((s["cap"], s["f"]), {})[s["s"]] = s
frames = []
for (cap, k) in sorted(by):
    sF = by[(cap, k)].get("F")
    if sF is None or sF["torn"] or not reads[sF["name"]]["clear"] or reads[sF["name"]]["best"] not in S.USE_W:
        continue
    w = int(reads[sF["name"]]["best"])
    zF, okF = sw.window(S.load(sdir, sF["name"]), w)
    f = {"cap": cap, "f": k, "w": w, "zF": zF, "okF": okF, "zM": None}
    sM = by[(cap, k)].get("M")
    if sM is not None and not sM["torn"]:
        f["zM"], f["okM"] = sw.window(S.load(sdir, sM["name"]), w)
    frames.append(f)
S.states(frames, floor)
byk = {(f["cap"], f["f"]): f for f in frames}
acc = {}


def add(key, q, v):
    if v == v:
        acc.setdefault((key, q), []).append(v)


for f in frames:
    if f["zM"] is None:
        continue
    pv = byk.get((f["cap"], f["f"] - 1))
    key = "%s>%s" % (pv["state"] if pv is not None else "-", f["state"])
    ok = f["okM"] & f["okF"]
    zm, zf = (f["zM"] == 0) & ok, (f["zF"] == 0) & ok
    nz = ok & ~zm & ~zf
    if nz.sum():
        add(key, "mid = this final (both non-zero)", float((f["zM"] == f["zF"])[nz].mean()))
    add(key, "phi mid zeros, this final zeros", S.phi(zm, zf, ok))
    if pv is not None and pv["w"] == f["w"]:
        okp = ok & pv["okF"]
        zp = (pv["zF"] == 0) & okp
        nzp = okp & ~zm & ~zp
        if nzp.sum():
            add(key, "mid = previous final (both non-zero)", float((f["zM"] == pv["zF"])[nzp].mean()))
        add(key, "phi mid zeros, previous final zeros", S.phi(zm, zp, okp))
        late = okp & ~zm & zf & ~zp
        if late.sum():
            add(key, "late zeros: mid = previous final", float((f["zM"] == pv["zF"])[late].mean()))
        add(key, "share mid zero where previous final zero", float(zm[zp].mean()) if zp.sum() else float("nan"))
        add(key, "share mid zero where previous final non-zero", float(zm[okp & ~zp].mean()) if (okp & ~zp).sum() else float("nan"))
print("# x0365: %d frames, %d with a mid snapshot" % (len(frames), sum(1 for f in frames if f["zM"] is not None)))
for q in ("mid = previous final (both non-zero)", "mid = this final (both non-zero)", "share mid zero where previous final non-zero"):
    v = sorted(x for (k2, q2), l in acc.items() if q2 == q for x in l)
    if v:
        print("# per frame, %s: n %d, min %.3f, 10 %% %.3f, median %.3f, 90 %% %.3f, max %.3f" % (
            q, len(v), v[0], *np.percentile(v, [10, 50, 90]), v[-1]))
for key in sorted({k for k, _ in acc}):
    print("  %-5s %s" % (key, "; ".join("%s %.3f (%d)" % (q, float(np.mean(v)), len(v)) for (k2, q), v in sorted(acc.items()) if k2 == key)))
