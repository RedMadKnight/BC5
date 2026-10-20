#!/usr/bin/env python3
# BC5 (experiment 0184): are two AJM loop streams the same recording? The first 2 s of stream A
# (after 0.2 s) are searched in the first 10 s of stream B by waveform correlation.
# usage: same_loop.py <a.raw> <b.raw>   (mono s16)
import sys, array, math
SR = 48000
a = array.array("h", open(sys.argv[1], "rb").read(SR * 2 * 3))
b = array.array("h", open(sys.argv[2], "rb").read(SR * 2 * 12))
p = [v / 32768.0 for v in a[SR // 5:SR // 5 + 2 * SR]]
e1 = math.sqrt(sum(v * v for v in p[::4])) or 1
best = (-2, 0)
for L in range(0, len(b) - len(p), 24):
    seg = b[L:L + len(p)]
    e2 = math.sqrt(sum((v / 32768.0) ** 2 for v in seg[::4])) or 1
    c = sum(p[i] * seg[i] / 32768.0 for i in range(0, len(p), 4)) / (e1 * e2)
    if c > best[0]: best = (c, L)
print("%s in %s: best correlation %.2f at %.3f s" % (sys.argv[1].split("/")[-1], sys.argv[2].split("/")[-1], best[0], best[1] / SR))
