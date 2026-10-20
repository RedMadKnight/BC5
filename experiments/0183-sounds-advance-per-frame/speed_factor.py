#!/usr/bin/env python3
# BC5 (experiment 0183): at what speed does the title play a decoded stream? A segment of the AJM
# output (s16, <ch> channels, summed) starting at the first job after process time <t_dec>, its
# loudness envelope (5 ms) time-compressed by factors 0.8..2.2, each correlated with the envelope
# of the title's own mix (8 ch f32 from <mix_from> s, all channels summed) over lags of 0..8 s.
# The factor with the best correlation is the playback speed.
# usage: speed_factor.py <dump dir> <instance hex> <ch> <mix raw> <mix_from> <t_dec> [seconds]
import sys, array, math
d, inst, ch, mixp, mix_from, t_dec = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], float(sys.argv[5]), float(sys.argv[6])
SEG = float(sys.argv[7]) if len(sys.argv) > 7 else 6.0
SR, HOP = 48000, 240
off = 0; start = None
for l in open(d + "/ajm-index.txt"):
    t, i, w = l.split()[:3]
    if i != inst: continue
    if start is None and float(t) >= t_dec: start = off // (2 * ch)
    off += int(w)
raw = array.array("h", open("%s/ajm-%s.raw" % (d, inst), "rb").read())
n = int(SEG * SR)
v = [sum(raw[(start + k) * ch:(start + k + 1) * ch]) / 32768.0 for k in range(n)]
def env(x):
    return [math.sqrt(sum(y * y for y in x[i:i + HOP]) / HOP) for i in range(0, len(x) - HOP, HOP)]
ev = env(v)
m0 = int((t_dec - 0.5 - mix_from) * SR); m1 = int((t_dec + 9 + SEG - mix_from) * SR)
with open(mixp, "rb") as f:
    f.seek(max(0, m0) * 32); b = f.read((m1 - max(0, m0)) * 32)
a = array.array("f", b)
c = [sum(a[k * 8:k * 8 + 8]) for k in range(len(a) // 8)]
ec = env(c)
def norm(e):
    mu = sum(e) / len(e); sd = math.sqrt(sum((y - mu) ** 2 for y in e) / len(e)) or 1
    return [(y - mu) / sd for y in e]
res = []
for f10 in range(8, 23):
    f = f10 / 10.0
    m = int(len(ev) / f)
    es = norm([ev[min(len(ev) - 1, int(j * f))] for j in range(m)])
    best = (-9, 0)
    for L in range(0, len(ec) - m):
        s = sum(es[j] * ec_n[L + j] for j in range(0, m, 2)) / (m / 2) if False else 0
    ecn = norm(ec)
    for L in range(0, len(ecn) - m):
        s = sum(es[j] * ecn[L + j] for j in range(0, m, 2)) / (m / 2)
        if s > best[0]: best = (s, L)
    res.append((best[0], f, best[1] * HOP / SR - 0.5))
for s, f, lag in sorted(res, reverse=True)[:5]:
    print("speed %.1fx: corr %.3f, heard %.2f s after decode" % (f, s, lag))
