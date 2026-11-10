import re, sys, os, glob
d = sys.argv[1]
rx = re.compile(r"t ([\d.]+) s: available (\S+) MiB, swap used (\S+) MiB, psi some (\S+) full (\S+) \(avg10, %\), full total (\S+) ms, gtt (\S+) of")
sx = re.compile(r"G (\d+)|after (\d+) s|([\d.]+) flips/s|longest (\d+) ms|(\d+) seconds with a gap")
def num(x):
    try: return float(x)
    except: return None
rows = []
for f in sorted(glob.glob(os.path.join(d, "*-memline.txt"))):
    tag = os.path.basename(f)[:-12]
    L = [m.groups() for m in map(rx.search, open(f, encoding="utf-8", errors="replace")) if m]
    if not L: continue
    t = [num(a[0]) for a in L]; av = [num(a[1]) for a in L]; sw = [num(a[2]) for a in L]
    ft = [num(a[5]) for a in L]; g = [num(a[6]) for a in L]; pf = [num(a[4]) for a in L]
    s = open(os.path.join(d, tag + "-summary.txt"), encoding="utf-8", errors="replace").read() if os.path.exists(os.path.join(d, tag + "-summary.txt")) else ""
    G = re.search(r"\(G (\d+)", s); fl = re.search(r"([\d.]+) flips/s", s); gp = re.search(r"(\d+) seconds with a gap", s)
    Gv = int(G.group(1)) if G else None
    # values in gameplay window G+120 .. end
    if Gv:
        idx = [i for i, x in enumerate(t) if x is not None and x >= Gv + 120]
    else:
        idx = []
    def mn(a, ix): v = [a[i] for i in ix if a[i] is not None]; return min(v) if v else None
    def mx(a, ix): v = [a[i] for i in ix if a[i] is not None]; return max(v) if v else None
    allix = range(len(L))
    pstall = (ft[-1] - ft[0]) / 1000 if ft[0] is not None and ft[-1] is not None else None
    pstall_g = (ft[idx[-1]] - ft[idx[0]]) / 1000 if idx and ft[idx[0]] is not None else None
    rows.append((tag, Gv, fl.group(1) if fl else "", gp.group(1) if gp else "", t[-1], sw[0], mx(sw, allix), mn(av, idx), mx(g, allix), g[0], pstall, pstall_g, mx(pf, allix)))
print("tag G flips gapsec tend swap0 swapmax availfloor(G+120..) gttmax gtt0 psifull_s psifull_s(G+120..) psifull_peak")
for r in rows:
    print(" ".join(str(x) for x in r))
