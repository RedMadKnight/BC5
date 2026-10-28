#!/usr/bin/env python3
# BC5 experiment 0354: the label-free page test, written after run J1's labelling failed. With every depth read sized by
# the journal, rdj0312.py's family unions grew to cover almost every hole pixel (X 48 reads; every other family 66-100 %
# inside X's set), so X/Y labels could not be drawn. Here each frame's hole mask is compared directly:
#  - per depth read with a frame size (fr0354.py via rdj0354.py's JSON) whose shear there is at most 3: its depth-0 mask
#    in the lake window at that size (rd0312.py's de-swizzle, ADDR_SW_64KB_Z_X at 16 pipes, swz0248-z4.json), over the
#    pixels valid in every read; a frame's mask is its first such read's;
#  - phi between every two frames' masks;
#  - the structure: the leading eigenvector of the centred phi matrix splits the frames in two (sizes, mean phi within
#    and between), so whether this run's holes fall into two states shows;
#  - per culling page (buf0312.py's 8 MiB read just before each depth read; a frame's content when its reads agree; the
#    order-insensitive key of pg0312.py): the mean phi of frame pairs with the same content minus that of pairs with
#    different content, over pairs from different bursts only (>= 4 s apart; neighbouring frames share the hole state
#    and the page's hold, F344), p by shuffling the frames' contents (the same shuffles for every page);
#    pages 1767, 1768 and 1776 named in advance (exp 0312's P1), then the scan of pages with 2..8 contents against the
#    null of the scan's largest; and a drift check, the Spearman of pair phi with the pairs' time apart.
# Summaries only. usage: python3 -I ph0354.py <capture dir> <rdj json> <swz0248-z4.json> [permutations]   (distrobox)
import json, os, random, sys
import numpy as np

cdir, rjson, zsw = sys.argv[1:4]
nperm = int(sys.argv[4]) if len(sys.argv) > 4 else 1000
PAGE, NPAGE, BASE = 1024, 2048, 0x11934d3900
NAMED = (1767, 1768, 1776)
X0, X1, Y0, Y1 = 300, 1900, 400, 680
pz = json.load(open(zsw))["patterns"]["4"]


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


IDX = {}


def window_of(raw, w):  # rd0312.py's image() and window(), the lake window only
    h = w * 9 // 16
    if w not in IDX:
        fx, fy = coord_offset(pz, "x", w), coord_offset(pz, "y", h)
        pitch = -(-w // 128)
        ys, xs = np.arange(Y0, Y1) * h // 1080, np.arange(X0, X1) * w // 1920
        blk = (ys // 128)[:, None] * pitch + (xs // 128)[None, :]
        IDX[w] = (blk * 65536 + (fx[xs][None, :] ^ fy[ys][:, None])) >> 2
    return raw[np.minimum(IDX[w], raw.size - 1)]


def keys(f):
    a = np.frombuffer(open(f, "rb").read(), dtype="<u4")[:PAGE * NPAGE]
    a = np.sort(np.pad(a, (0, PAGE * NPAGE - a.size)).reshape(NPAGE, PAGE), axis=1)
    return [hash(a[p].tobytes()) for p in range(NPAGE)]


rj = json.load(open(rjson))
frames = {}
for r in rj["reads"]:
    if r["kind"] != "z" or not r.get("frame") or r.get("frame_j") is None or r["sizes"][str(r["frame"])]["shear"] > 3:
        continue
    frames.setdefault(r["frame_j"], []).append(r)
order = sorted(frames)
masks, oks, fwall, fburst, fkeys = [], [], [], [], []
for j in order:
    rs = sorted(frames[j], key=lambda r: r["wall"])
    r = rs[0]
    b, k = r["name"].split(".z")
    raw = np.frombuffer(open(os.path.join(cdir, "%s.z%s.bin" % (b, k)), "rb").read(), dtype="<f4").astype(np.float64)
    z = window_of(raw, r["frame"])
    with np.errstate(invalid="ignore"):
        ok = np.isfinite(z) & (z >= 0) & (z <= 1)
    masks.append((z == 0) & ok)
    oks.append(ok)
    fwall.append(r["wall"])
    fburst.append(b)
    ks = [keys(os.path.join(cdir, "%s.c%s.bin" % tuple(q["name"].split(".z")))) for q in rs]
    fkeys.append([ks[0][p] if all(x[p] == ks[0][p] for x in ks) else None for p in range(NPAGE)])
n = len(order)
common = np.logical_and.reduce(oks)
M = np.array([m[common] for m in masks], dtype=np.float64)
share = M.mean(axis=1)
Z = (M - M.mean(axis=1, keepdims=True)) / np.maximum(M.std(axis=1, keepdims=True), 1e-9)
PHI = Z @ Z.T / M.shape[1]
print("# %d frames with a sized depth read; %d common valid pixels of %d in the lake window; hole share per frame: min %.3f, median %.3f, max %.3f" % (
    n, int(common.sum()), common.size, share.min(), float(np.median(share)), share.max()))
iu = np.triu_indices(n, 1)
print("  phi between frames: quartiles %.3f / %.3f / %.3f" % tuple(np.percentile(PHI[iu], (25, 50, 75))))
C = PHI - PHI.mean(axis=0, keepdims=True) - PHI.mean(axis=1, keepdims=True) + PHI.mean()
w, v = np.linalg.eigh(C)
side = v[:, -1] > 0
a, b2 = np.where(side)[0], np.where(~side)[0]


def mean_phi(i, j):
    sub = PHI[np.ix_(i, j)]
    if i is j or (len(i) == len(j) and (i == j).all()):
        return float(sub[np.triu_indices(len(i), 1)].mean()) if len(i) > 1 else float("nan")
    return float(sub.mean())


print("  leading split of the frames' masks: %d and %d frames; mean phi within %.3f and %.3f, between %.3f (eigenvalue share %.2f)" % (
    len(a), len(b2), mean_phi(a, a), mean_phi(b2, b2), mean_phi(a, b2), w[-1] / max(w[w > 0].sum(), 1e-9)))
print("  split by time (frames in order, A/B): %s" % "".join("A" if s else "B" for s in side))
pairs = [(i, j) for i, j in zip(*iu) if fburst[i] != fburst[j]]
pp = np.array([PHI[i, j] for i, j in pairs])
gap = np.array([abs(fwall[i] - fwall[j]) for i, j in pairs])
rk = lambda x: np.argsort(np.argsort(x))
print("  pairs from different bursts: %d; drift: Spearman of phi with time apart %+.3f" % (len(pairs), float(np.corrcoef(rk(pp), rk(gap))[0, 1])))
pi = np.array([p[0] for p in pairs])
pj = np.array([p[1] for p in pairs])


def stat(cont):  # cont: content id per frame (None: unknown)
    c = np.array([-1 if x is None else x for x in cont])
    use = (c[pi] >= 0) & (c[pj] >= 0)
    same = use & (c[pi] == c[pj])
    diff = use & (c[pi] != c[pj])
    if same.sum() < 3 or diff.sum() < 3:
        return None
    return float(pp[same].mean() - pp[diff].mean()), int(same.sum()), int(diff.sum())


cont = {}
for p in range(NPAGE):
    ids = {}
    cont[p] = [None if fk[p] is None else ids.setdefault(fk[p], len(ids)) for fk in fkeys]
nk = {p: len({x for x in cont[p] if x is not None}) for p in range(NPAGE)}
scan = [p for p in range(NPAGE) if 2 <= nk[p] <= 8 and stat(cont[p]) is not None]
obs = {p: stat(cont[p]) for p in set(scan) | {p for p in NAMED if stat(cont[p]) is not None}}
rng = random.Random(354)
null_max, hits = [], {p: 0 for p in NAMED if p in obs}
for _ in range(nperm):
    perm = list(range(n))
    rng.shuffle(perm)
    sh = {p: [cont[p][q] for q in perm] for p in set(scan) | set(hits)}
    vals = [stat(sh[p]) for p in scan]
    null_max.append(max((v[0] for v in vals if v), default=0.0))
    for p in hits:
        s = stat(sh[p])
        hits[p] += s is not None and s[0] >= obs[p][0] - 1e-12
print("  pages with 2..8 contents over the frames: %d" % len(scan))
for p in NAMED:
    if p not in obs:
        print("  page %d: too few frames with a known content" % p)
        continue
    d, ns, nd = obs[p]
    print("  page %4d (named; 0x%x): %d contents, %d frames known; mean phi same minus different content %+.4f (%d / %d pairs), p %.4f (%d)" % (
        p, BASE + p * PAGE * 4, nk[p], sum(1 for x in cont[p] if x is not None), d, ns, nd, (hits[p] + 1) / (nperm + 1), nperm))
if scan:
    null_max.sort()
    q95 = null_max[int(0.95 * nperm)]
    print("  scan null of the largest difference (contents shuffled, %d): median %+.4f, 95th percentile %+.4f" % (nperm, null_max[nperm // 2], q95))
    for p in sorted(scan, key=lambda q: -obs[q][0])[:8]:
        print("    page %4d (0x%x): difference %+.4f, %d contents, pairs %d same / %d different%s" % (
            p, BASE + p * PAGE * 4, obs[p][0], nk[p], obs[p][1], obs[p][2], "  <- above the 95th percentile" if obs[p][0] > q95 else ""))
