#!/usr/bin/env python3
# BC5 (experiment 0183): do the 10-s chunks of one AJM instance overlap? The decoder's sample
# counter restarts at each chunk (ajm-index.txt, column 5); for each boundary, the first 0.5 s of
# the next chunk (after 0.1 s) is searched in the previous chunk by waveform correlation. A strong
# match at offset X means the stream was re-opened X seconds into what had already been decoded.
# usage: chunk_overlap.py <dump dir> <instance hex>
import sys, array, math
d, inst = sys.argv[1], sys.argv[2]
SR = 48000
starts = []; off = 0; prev = None
for l in open(d + "/ajm-index.txt"):
    p = l.split()
    if p[1] != inst: continue
    s = int(p[4])
    if prev is not None and s < prev: starts.append(off // 2)
    if prev is None: starts.append(0)
    prev = s; off += int(p[2])
raw = array.array("h", open("%s/ajm-%s.raw" % (d, inst), "rb").read())
x = [v / 32768.0 for v in raw]
W = SR // 2
for k in range(1, min(len(starts), 12)):
    a0, b0 = starts[k - 1], starts[k]
    probe = x[b0 + SR // 10:b0 + SR // 10 + W]
    e1 = math.sqrt(sum(v * v for v in probe[::4])) or 1
    best = (-2, 0)
    for L in range(a0, b0 - W, 48):
        seg = x[L:L + W]
        e2 = math.sqrt(sum(v * v for v in seg[::4])) or 1
        c = sum(probe[i] * seg[i] for i in range(0, W, 4)) / (e1 * e2)
        if c > best[0]: best = (c, L)
    print("chunk %d starts at %.2f s of decoded audio; its 0.1-0.6 s best matches chunk %d at %.2f s into it (corr %.2f); chunk %d is %.2f s long" % (
        k, b0 / SR, k - 1, (best[1] - a0) / SR - 0.1, best[0], k - 1, (b0 - a0) / SR))
