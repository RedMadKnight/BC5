#!/usr/bin/env python3
# BC5 (experiment 0183): is a decoded voice played at its own speed in the title's mix?
# The AJM dump of one mono voice instance (s16) and its index (process time of each decode job),
# the title's own mix (8 ch f32 from process time <mix_from>). A voice segment decoded around
# <t_dec> is found in the mix's centre channel by envelope correlation, then its exact lag is
# measured by waveform correlation in windows along the segment: a lag that changes along the
# segment means the voice is played faster or slower than decoded.
# usage: voice_speed.py <dump dir> <instance hex> <mix raw> <mix_from s> <t_dec s> [seconds]
import sys, array, math
d, inst, mixp, mix_from, t_dec = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5])
SEG = float(sys.argv[6]) if len(sys.argv) > 6 else 6.0
SR = 48000
off = 0; start = None
for l in open(d + "/ajm-index.txt"):
    t, i, w = l.split()[:3]
    if i != inst: continue
    if start is None and float(t) >= t_dec: start = off // 2
    off += int(w)
raw = array.array("h", open("%s/ajm-%s.raw" % (d, inst), "rb").read())
if start is None: sys.exit("no job after t_dec")
n = int(SEG * SR)
v = [x / 32768.0 for x in raw[start:start + n]]
print("voice: samples %d..%d of %d (decoded from process t %.2f s), rms %.4f" % (start, start + n, len(raw), t_dec, math.sqrt(sum(x * x for x in v) / len(v))))
# the mix centre channel (7.1: FL FR FC LFE BL BR SL SR -> index 2) over [t_dec - 1, t_dec + 4 + SEG]
m0 = int((t_dec - 1 - mix_from) * SR); m1 = int((t_dec + 4 + SEG - mix_from) * SR)
with open(mixp, "rb") as f:
    f.seek(max(0, m0) * 32); b = f.read((m1 - max(0, m0)) * 32)
a = array.array("f", b)
c = [a[k * 8 + 2] for k in range(len(a) // 8)]
HOP = 240
def env(x): return [math.sqrt(sum(y * y for y in x[i:i + HOP]) / HOP) for i in range(0, len(x) - HOP, HOP)]
ev, ec = env(v), env(c)
def norm(e):
    mu = sum(e) / len(e); sd = math.sqrt(sum((y - mu) ** 2 for y in e) / len(e)) or 1
    return [(y - mu) / sd for y in e]
ev, ec = norm(ev), norm(ec)
best = (-9, 0)
for L in range(0, len(ec) - len(ev)):
    s = sum(ev[i] * ec[i + L] for i in range(0, len(ev), 2)) / (len(ev) / 2)
    if s > best[0]: best = (s, L)
coarse = best[1] * HOP
print("envelope match: corr %.2f, voice heard %.3f s after it was decoded" % (best[0], (m0 + coarse) / SR + mix_from - t_dec))
# fine: waveform correlation of 0.5-s windows along the segment, +-30 ms around the coarse lag
W = SR // 2
for k in range(0, n - W, SR):
    win = v[k:k + W]
    e1 = math.sqrt(sum(y * y for y in win)) or 1
    bl, bc = 0, -2
    for L in range(coarse + k - 1440, coarse + k + 1440, 2):
        if L < 0 or L + W > len(c): continue
        seg = c[L:L + W]
        e2 = math.sqrt(sum(y * y for y in seg[::4])) * 2 or 1
        s = sum(win[i] * seg[i] for i in range(0, W, 4)) * 4 / (e1 * e2)
        if s > bc: bc, bl = s, L
    print("  voice +%.1f s: lag %+.2f ms against the start, corr %.2f" % (k / SR, (bl - coarse - k) * 1000.0 / SR, bc))
