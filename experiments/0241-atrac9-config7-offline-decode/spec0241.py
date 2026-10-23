#!/usr/bin/env python3
# BC5 experiment 0241, step 4 (inside the ubuntu distrobox, numpy): (a) for each stream with failed frames, look for a
# stream with the same Wwise sample count in a wem_* archive and report whether that one decoded clean (the soundbank
# copies may hold only Wwise's prefetch, the head of a streamed sound); (b) the spectrum of a spread of decoded streams
# per config: share of energy below 100 Hz, 300 Hz and 1 kHz, the spectral centroid, and the L/R correlation of 2-ch
# ones. WAVs go to the private dir and are deleted after reading.
#   python3 -I spec0241.py <index.tsv> <decode-all.tsv> <streams dir> <wav dir> <dec0241>
import os, re, subprocess, sys
import numpy as np

index_p, dec_p, sdir, wdir, dec = sys.argv[1:6]
os.makedirs(wdir, mode=0o700, exist_ok=True)
idx = [l.rstrip("\n").split("\t") for l in open(index_p, encoding="utf-8")][1:]
rep = {r[0]: r[5] for r in (l.rstrip("\n").split("\t") for l in open(dec_p, encoding="utf-8"))}
clean = lambda copy: "failed 0 " in rep.get(copy, "")

print("== (a) streams with failed frames: a twin with the same sample count in wem_*?")
for file, off, riff, codec, ch, rate, cfg, cfgat, samples, delay, dsize, copy in idx:
    if clean(copy):
        continue
    twins = [r for r in idx if r[8] == samples and r[6] == cfg and r[0] != file and "wem" in r[0]]
    tw = ", ".join(f"{r[11]} {'clean' if clean(r[11]) else 'FAILED'}" for r in twins[:3]) or "none"
    print(f"{copy} {cfg} samples {samples} data {dsize}: twin(s) {tw}")

print("== (b) spectra")
rng = np.random.default_rng(241)
for cfg in sorted({r[6] for r in idx}):
    cand = [r for r in idx if r[6] == cfg and clean(r[11]) and int(r[8]) > 48000 * 0.5]
    pick = [cand[i] for i in sorted(rng.choice(len(cand), size=min(25, len(cand)), replace=False))]
    lo100, lo300, lo1k, cent, corr = [], [], [], [], []
    for r in pick:
        wav = os.path.join(wdir, r[11] + ".wav")
        subprocess.run([dec, cfg, os.path.join(sdir, r[11]), wav], stdout=subprocess.DEVNULL, check=False)
        raw = open(wav, "rb").read()
        os.remove(wav)
        ch = int.from_bytes(raw[22:24], "little")
        x = np.frombuffer(raw[44:], dtype="<i2").astype(np.float64).reshape(-1, ch)
        p = np.zeros(4097)
        for k in range(ch):
            for s in range(0, len(x) - 8192, 8192):
                p += np.abs(np.fft.rfft(x[s:s + 8192, k] * np.hanning(8192))) ** 2
        f = np.fft.rfftfreq(8192, 1 / 48000)
        tot = p.sum() or 1
        lo100.append(p[f < 100].sum() / tot); lo300.append(p[f < 300].sum() / tot); lo1k.append(p[f < 1000].sum() / tot)
        cent.append((p * f).sum() / tot)
        if ch == 2 and x[:, 0].std() > 0 and x[:, 1].std() > 0:
            corr.append(np.corrcoef(x[:, 0], x[:, 1])[0, 1])
    med = lambda a: float(np.median(a)) if a else float("nan")
    print(f"{cfg}: {len(pick)} streams; energy below 100 Hz {med(lo100):.1%}, below 300 Hz {med(lo300):.1%}, "
          f"below 1 kHz {med(lo1k):.1%} (medians; min below 1 kHz {min(lo1k):.1%}); spectral centroid median "
          f"{med(cent):.0f} Hz (p10 {np.percentile(cent, 10):.0f}, p90 {np.percentile(cent, 90):.0f})"
          + (f"; L/R correlation median {med(corr):.2f} (min {min(corr):.2f})" if corr else ""))
