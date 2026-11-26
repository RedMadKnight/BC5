#!/usr/bin/env python3
# BC5 (experiment 0182): discontinuities ("clicks") per second: samples where the second difference
# jumps far above the local level (|x[n]-2x[n-1]+x[n-2]| > k * local RMS of the second difference
# and > an absolute floor). For a raw 8-ch f32 dump (the title's own sound, summed to mono) or a
# 16-bit stereo WAV (summed to mono), over a window. usage: clicks.py <file> <from s> <seconds>
import sys, array, math, wave
path, t0, secs = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
SR = 48000
def mono_seconds():
    if path.endswith(".wav"):
        w = wave.open(path); w.setpos(int(t0 * SR))
        for _ in range(int(secs)):
            a = array.array("h", w.readframes(SR))
            if len(a) < SR * 2: return
            yield [(a[i] + a[i + 1]) / 65536.0 for i in range(0, len(a), 2)]
    else:
        with open(path, "rb") as f:
            f.seek(int(t0 * SR) * 32)
            for _ in range(int(secs)):
                b = f.read(SR * 32)
                if len(b) < SR * 32: return
                a = array.array("f", b)
                yield [sum(a[i:i + 8]) / 8.0 for i in range(0, len(a), 8)]
total = 0; worst = []
for s, x in enumerate(mono_seconds()):
    d2 = [x[n] - 2 * x[n - 1] + x[n - 2] for n in range(2, len(x))]
    blk = 480; c = 0
    for b0 in range(0, len(d2) - blk, blk):
        seg = d2[b0:b0 + blk]
        rms = math.sqrt(sum(v * v for v in seg) / blk) + 1e-9
        c += sum(1 for v in seg if abs(v) > 8 * rms and abs(v) > 0.02)
    total += c
    worst.append((c, s))
worst.sort(reverse=True)
print("%s: %d clicks in %d s; worst seconds %s" % (path.split("/")[-1], total, len(worst), [(round(t0 + s), c) for c, s in worst[:6]]))
