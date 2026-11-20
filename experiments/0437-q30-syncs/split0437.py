import gzip, re, sys
FP = re.compile(r"frame profile: t ([\d.]+) s, ([\d.]+) ms since the last flip; game thread inside the host ([\d.]+) ms \(sync ([\d.]+), hints ([\d.]+)")
TS = re.compile(r"timing split over 128 submissions: probe ([\d.]+) ms, anon sync ([\d.]+), direct sync ([\d.]+) \(views ([\d.]+); (\d+) full, (\d+) fast; scan ([\d.]+), merge ([\d.]+), drain ([\d.]+) in \d+, maps ([\d.]+) = want ([\d.]+) \+ drop ([\d.]+) \+ zero ([\d.]+) \+ add ([\d.]+)\), learned ([\d.]+), hints ([\d.]+)")
N = ["probe", "anon", "direct", "views", "full", "fast", "scan", "merge", "drain", "maps", "want", "drop", "zero", "add", "learned", "hints"]
for p in sys.argv[1:]:
    t = 0.0
    tot = [0.0] * len(N); n = 0
    big = []  # windows over 50 ms of sync+hints
    domin = {}
    with gzip.open(p, "rt", errors="replace") as f:
        for line in f:
            m = FP.search(line)
            if m:
                t = float(m.group(1)); continue
            m = TS.search(line)
            if m and t >= 130:
                v = [float(x) for x in m.groups()]
                n += 1
                for i, x in enumerate(v): tot[i] += x
                s = v[0] + v[1] + v[2] + v[14] + v[15]
                if s > 50:
                    parts = {"probe": v[0], "anon": v[1], "views": v[3], "scan": v[6], "merge": v[7], "drain": v[8], "maps": v[9], "learned": v[14], "hints": v[15]}
                    k = max(parts, key=parts.get)
                    domin.setdefault(k, [0, 0.0]); domin[k][0] += 1; domin[k][1] += s
                    big.append((s, t, parts, v[4]))
    print("==", p, "windows of 128 after t 130:", n)
    print("  sums [s]: " + ", ".join("%s %.1f" % (N[i], tot[i] / 1000) for i in range(len(N)) if N[i] not in ("full", "fast")) + "; full view builds %d, fast %d" % (tot[4], tot[5]))
    print("  windows with sync+hints > 50 ms: %d, %.1f s; by largest part: " % (len(big), sum(b[0] for b in big) / 1000) + ", ".join("%s %d/%.1fs" % (k, c, s / 1000) for k, (c, s) in sorted(domin.items(), key=lambda x: -x[1][1])))
    for s, tt, parts, full in sorted(big, key=lambda x: -x[0])[:5]:
        print("   %.0f ms at t %.1f (full %d): " % (s, tt, full) + ", ".join("%s %.1f" % kv for kv in parts.items()))
