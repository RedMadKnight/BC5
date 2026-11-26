#!/usr/bin/env python3
# BC5 (experiment 0181): does the headset recording follow the title's own sound sample for sample?
# Loudness envelopes (10 ms) of the title's dump (8 ch f32, all channels) and of the recording
# (2 ch s16); the best lag over the whole dump, then the best lag of 8-s windows every 10 s.
# A constant lag = the output path plays the title's sound as made; a drifting lag = it speeds up,
# slows down or skips. usage: align.py <dump-in.raw> <rec.wav>
import sys, array, wave, math
dump, rec = sys.argv[1], sys.argv[2]
SR, HOP = 48000, 480
def env_dump(path):
    e = []
    with open(path, "rb") as f:
        while True:
            b = f.read(HOP * 8 * 4)
            if len(b) < HOP * 8 * 4: break
            a = array.array("f", b)
            e.append(math.sqrt(sum(x * x for x in a) / len(a)))
    return e
def env_wav(path):
    w = wave.open(path); e = []
    while True:
        b = w.readframes(HOP)
        if len(b) < HOP * 4: break
        a = array.array("h", b)
        e.append(math.sqrt(sum(x * x for x in a) / len(a)) / 32768.0)
    return e
def norm(v):
    m = sum(v) / len(v); s = math.sqrt(sum((x - m) ** 2 for x in v) / len(v)) or 1.0
    return [(x - m) / s for x in v]
def best(a, b, lo, hi):
    # lag L: a[i] ~ b[i + L]
    bl, bc = None, -1e9
    for L in range(lo, hi + 1):
        n = 0; c = 0.0
        for i in range(0, len(a), 2):
            j = i + L
            if 0 <= j < len(b): c += a[i] * b[j]; n += 1
        if n and c / n > bc: bc, bl = c / n, L
    return bl, bc
d = env_dump(dump); r = env_wav(rec)
print("dump %.1f s, recording %.1f s" % (len(d) * HOP / SR, len(r) * HOP / SR))
# the dump starts at process time 150 s; the recording started ~1 s before the process
dn = norm(d[:3000])
g, gc = best(dn, norm(r), 13000, 17000)
print("whole-dump lag %.2f s (corr %.2f)" % (g * HOP / SR, gc))
for start in range(0, len(d) - 800, 1000):
    w = norm(d[start:start + 800])
    lag, c = best(w, norm(r[start + g - 300:start + g + 1100]), 0, 600)
    lag = lag - 300 + g if lag is not None else None
    print("dump t %5.1f s (process t %5.1f): lag %.2f s, drift %+4d ms, corr %.2f" % (start * HOP / SR, 150 + start * HOP / SR, lag * HOP / SR, (lag - g) * HOP * 1000 // SR, c))
