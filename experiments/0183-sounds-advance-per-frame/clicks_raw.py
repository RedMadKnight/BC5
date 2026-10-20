#!/usr/bin/env python3
# BC5 (experiment 0183): discontinuities ("clicks") in a raw s16 PCM stream with N channels (the
# AJM decoder's output as handed to the title), summed to mono: per second of audio, samples where
# the second difference jumps far above its local level. Also the largest single jumps with their
# positions (seconds into the stream). usage: clicks_raw.py <file.raw> <channels>
import sys, array, math
path, ch = sys.argv[1], int(sys.argv[2])
SR = 48000
data = array.array("h", open(path, "rb").read())
n = len(data) // ch
x = [sum(data[i * ch:(i + 1) * ch]) / (32768.0 * ch) for i in range(n)]
total = 0; per = []; big = []
for s0 in range(0, n - SR, SR):
    seg = x[s0:s0 + SR]
    d2 = [seg[k] - 2 * seg[k - 1] + seg[k - 2] for k in range(2, len(seg))]
    c = 0
    for b0 in range(0, len(d2) - 480, 480):
        blk = d2[b0:b0 + 480]
        rms = math.sqrt(sum(v * v for v in blk) / 480) + 1e-9
        for k, v in enumerate(blk):
            if abs(v) > 8 * rms and abs(v) > 0.02:
                c += 1; big.append((abs(v), (s0 + b0 + k + 2) / SR))
    per.append(c); total += c
big.sort(reverse=True)
print("%s: %.1f s of audio, %d clicks (%.1f/s); biggest jumps at %s" % (path.split("/")[-1], n / SR, total, total / max(1, len(per)), [round(t, 2) for v, t in big[:8]]))
