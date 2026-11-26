#!/usr/bin/env python3
# BC5 (experiment 0186): the clock voice's AJM decode jobs per 10-s window from ajm-index.txt
# (time, instance, written bytes, frames, total decoded samples): jobs, frames, bytes written,
# samples advanced (total counter deltas, loop wraps counted as the bytes written / 2), and the
# distribution of (written, frames) per job.
# usage: ajm_jobs.py <ajm-index.txt> [instance hex]
import sys, collections
idx = sys.argv[1]
want = sys.argv[2] if len(sys.argv) > 2 else None
rows = []
for l in open(idx):
    q = l.split()
    if len(q) < 5: continue
    rows.append((float(q[0]), q[1], int(q[2]), int(q[3]), int(q[4])))
if want is None:
    # the instance whose total counter wraps after exactly 479352 samples
    prev = {}; wraps = collections.Counter()
    for t, i, w, f, s in rows:
        if i in prev and s < prev[i][1] and prev[i][1] - prev[i][0] == 479352:
            wraps[i] += 1
        if i not in prev or s < prev[i][1]:
            prev[i] = [s, s]
        prev[i][1] = s
    print("clock-voice wraps per instance:", dict(wraps.most_common(5)))
    want = wraps.most_common(1)[0][0] if wraps else rows[0][1]
W = 10.0
win = collections.defaultdict(lambda: {"jobs": 0, "frames": 0, "bytes": 0, "kinds": collections.Counter(), "adv": 0})
last = None
for t, i, w, f, s in rows:
    if i != want: continue
    k = win[int(t // W)]
    k["jobs"] += 1; k["frames"] += f; k["bytes"] += w; k["kinds"][(w, f)] += 1
    if last is not None:
        k["adv"] += (s - last) if s >= last else w // 2
    last = s
for k in sorted(win):
    v = win[k]
    print("%4d s: %4d jobs, %5d frames, %8d bytes (%.2f s of mono 16-bit at 48 kHz), samples advanced %7d (%.2f s) | %s" % (
        k * W, v["jobs"], v["frames"], v["bytes"], v["bytes"] / 2 / 48000, v["adv"], v["adv"] / 48000, dict(v["kinds"].most_common(4))))
