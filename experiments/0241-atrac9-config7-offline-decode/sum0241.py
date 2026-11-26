#!/usr/bin/env python3
# BC5 experiment 0241, step 3: summarise raw/decode-all.tsv (decode0241.sh) per ATRAC9 config word.
#   python3 -I sum0241.py raw/decode-all.tsv
import collections, re, sys

rows = [l.rstrip("\n").split("\t") for l in open(sys.argv[1], encoding="utf-8")]
by = collections.defaultdict(lambda: collections.Counter())
rmss = collections.defaultdict(list)
for copy, file, cfg, ch, samples, rep in rows:
    d = by[cfg]
    d["streams"] += 1
    m = re.search(r"frames ok (\d+) failed (\d+).*?samples/ch (\d+) \(([\d.]+) s\)", rep)
    if not m:
        d["not decoded"] += 1
        continue
    ok, bad, spc, secs = int(m[1]), int(m[2]), int(m[3]), float(m[4])
    d["frames ok"] += ok
    d["frames failed"] += bad
    d["streams with a failed frame" if bad else "streams decoded clean"] += 1
    d["centiseconds"] += int(secs * 100)
    if int(samples) > 0 and spc >= int(samples):
        d["samples >= Wwise count"] += 1
    chans = re.findall(r"ch(\d) peak (\d+) rms ([\d.]+) zero ([\d.]+)%", rep)
    rms = [float(c[2]) for c in chans]
    peaks = [int(c[1]) for c in chans]
    rmss[cfg] += rms
    if rms and max(rms) < 1:
        d["silent"] += 1
    if peaks and max(peaks) >= 32767:
        d["reach full scale"] += 1
    if len(chans) == 2:
        d["2-ch"] += 1
        if chans[0][1:] == chans[1][1:]:
            d["2-ch with identical channel stats"] += 1
for cfg, d in sorted(by.items()):
    r = sorted(rmss[cfg])
    q = lambda f: r[min(len(r) - 1, int(f * len(r)))] if r else 0
    print(f"{cfg}: " + "; ".join(f"{k} {v}" for k, v in d.items() if k != "centiseconds")
          + f"; total {d['centiseconds'] / 100:.0f} s; per-channel RMS p10/median/p90 {q(.1):.0f}/{q(.5):.0f}/{q(.9):.0f}")
