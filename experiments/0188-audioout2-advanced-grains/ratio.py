#!/usr/bin/env python3
# BC5 (experiment 0188): per 10-s window, the title's AudioOut2 advances and pushes (KYTY_BC5_AUDIO2_TRACE
# lines) next to the clock voice's speed (KYTY_BC5_AJM_DUMP index, complete passes of 479,352 samples).
# usage: ratio.py <log> <ajm-index.txt>
import sys, collections, re
log, idx = sys.argv[1], sys.argv[2]
W = 10.0
adv = collections.Counter(); push = collections.Counter(); lvl = collections.Counter(); polls = collections.Counter()
pat = re.compile(r"t ([\d.]+) s: .*advance (\d+), push (\d+), get queue level (\d+) \(level sum (\d+)")
for line in open(log, errors="replace"):
    if not line.startswith("audio2 trace"):
        continue
    m = pat.search(line)
    if not m:
        continue
    k = int(float(m.group(1)) // W)
    adv[k] += int(m.group(2)); push[k] += int(m.group(3)); polls[k] += int(m.group(4)); lvl[k] += int(m.group(5))
speed = {}
prev = {}; s0 = {}; seg0 = {}
for l in open(idx):
    q = l.split()
    if len(q) < 5:
        continue
    t = float(q[0]); i = q[1]; s = int(q[4])
    if i in prev and s < prev[i]:
        if prev[i] - s0[i] == 479352:
            sp = 479352 / 48000 / (t - seg0[i])
            for k in range(int(seg0[i] // W), int(t // W) + 1):
                speed[k] = sp
        seg0[i] = t; s0[i] = s
    if i not in prev:
        seg0[i] = t; s0[i] = s
    prev[i] = s
print("window | advances | pushes | advances/pushes | clock voice | mean queue level told")
for k in sorted(adv):
    if push[k] == 0:
        continue
    print("%4d s | %4d | %4d | %.2f | %s | %.2f" % (k * W, adv[k], push[k], adv[k] / push[k],
          ("%.2fx" % speed[k]) if k in speed else "  -  ", lvl[k] / polls[k] if polls[k] else 0))
