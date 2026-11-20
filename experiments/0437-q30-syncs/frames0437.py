import gzip, re, sys
FP = re.compile(r"frame profile: t ([\d.]+) s, ([\d.]+) ms since the last flip; game thread inside the host ([\d.]+) ms \(sync ([\d.]+), hints ([\d.]+), prepare ([\d.]+), list ([\d.]+), cs ([\d.]+)")
for p in sys.argv[1:]:
    op = gzip.open if p.endswith(".gz") else open
    rows = []
    with op(p, "rt", errors="replace") as f:
        for line in f:
            m = FP.search(line)
            if m:
                rows.append(tuple(float(x) for x in m.groups()))
    if not rows:
        print(p, "no frames"); continue
    tmax = rows[-1][0]
    print("==", p, "frames", len(rows), "t end %.0f" % tmax)
    top = sorted(rows, key=lambda r: -r[3])[:8]
    for r in top:
        print("  t %.1f period %.1f inside %.1f sync %.1f hints %.1f prep %.1f cs %.1f" % (r[0], r[1], r[2], r[3], r[4], r[5], r[7]))
    g = [r for r in rows if r[0] >= 130]
    for lo, hi in ((20, 50), (50, 100), (100, 1e9)):
        s = [r for r in g if lo <= r[3] < hi]
        print("  t>=130 sync in [%g,%g): %d frames, %.1f s" % (lo, hi, len(s), sum(r[3] for r in s) / 1000))
    for lo, hi in ((50, 100), (100, 1e9)):
        s = [r for r in g if lo <= r[1] < hi]
        print("  t>=130 period in [%g,%g): %d; of them sync>20: %d" % (lo, hi, len(s), sum(1 for r in s if r[3] > 20)))
