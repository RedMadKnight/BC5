#!/usr/bin/env python3
"""BC5 exp 0432: what the long "sync + hints" parts of a submission are made of, from exp 0415's per-job record
(KYTY_BC5_FRAME_STAT, "L" lines; written for 64 of every 512 frames, so the sums are of a sample).
    fs0432.py <tag>-fs.txt [...]
L fields (bc5LleAgc.cpp, fs415_job): 0 "L", 1 frame, 2 job, 3 kind, 4 ring, 5 dwords, 6-8 filter stats, 9 BOs,
10-12 prepare/list/cs ms, 13 submit_now entered, 14 lock asked, 15 lock got, 16 queued, 17 written, 18-19 GPU stamps,
20 how, 21 chain open, 22 why, 23 segments, 24-29 the ends of probe, anonymous sync, direct sync, learned, hints, the
work before the device call (ns), 30-37 direct_sync_one's parts (views, scan, merge, drain, maps, imports alone), the
anonymous sync's maps read, flags."""
import sys

PARTS = ["lock wait", "probe", "anon sync", "direct sync", "learned", "hints", "pre-device", "device call"]
DS = ["views", "scan", "merge", "drain", "maps", "(imports)", "(anon maps read)"]
for path in sys.argv[1:]:
    n = bad = 0
    tot = [0.0] * 8
    long_n = 0
    long_tot = [0.0] * 8
    long_ds = [0.0] * 7
    all_ds = [0.0] * 7
    top = []
    for line in open(path, errors="replace"):
        f = line.split()
        if len(f) < 38 or f[0] != "L":
            continue
        try:
            sub, ask, got, queued = (int(f[k]) for k in (13, 14, 15, 16))
            p = [int(f[k]) for k in range(24, 30)]
            ds = [int(f[k]) for k in range(30, 37)]
        except ValueError:
            bad += 1
            continue
        if got == 0 or p[4] < got:
            bad += 1
            continue
        parts = [got - ask, p[0] - got, p[1] - p[0], p[2] - p[1], p[3] - p[2], p[4] - p[3], p[5] - p[4], queued - p[5]]
        n += 1
        for i, v in enumerate(parts):
            tot[i] += v
        for i, v in enumerate(ds):
            all_ds[i] += v
        sh = p[4] - got  # sync + hints, as the d432 line counts it
        if sh > 20_000_000:
            long_n += 1
            for i, v in enumerate(parts):
                long_tot[i] += v
            for i, v in enumerate(ds):
                long_ds[i] += v
            top.append((sh, f[3], int(f[5]), parts, ds))
    print("== %s: %d job lines (%d unreadable)" % (path.replace("\\", "/").split("/")[-1], n, bad))
    if n == 0:
        continue
    ms = lambda v: v / 1e6
    print("  all jobs [ms]: " + ", ".join("%s %.0f" % (PARTS[i], ms(tot[i])) for i in range(8)))
    print("    direct sync by part [ms]: " + ", ".join("%s %.0f" % (DS[i], ms(all_ds[i])) for i in range(7)))
    print("  jobs with sync+hints over 20 ms: %d, [ms]: " % long_n + ", ".join("%s %.0f" % (PARTS[i], ms(long_tot[i])) for i in range(8)))
    print("    their direct sync by part [ms]: " + ", ".join("%s %.0f" % (DS[i], ms(long_ds[i])) for i in range(7)))
    for sh, kind, dw, parts, ds in sorted(top, key=lambda x: -x[0])[:6]:
        print("    %.0f ms %s %d dwords: " % (ms(sh), kind, dw) + ", ".join("%s %.0f" % (PARTS[i], ms(parts[i])) for i in range(1, 6)) + " | "
              + ", ".join("%s %.0f" % (DS[i], ms(ds[i])) for i in range(7)))
