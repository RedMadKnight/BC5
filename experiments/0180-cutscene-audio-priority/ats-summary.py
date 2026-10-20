#!/usr/bin/env python3
# BC5 (experiment 0180): summary of audio-thread-sampler.py output. For the sound path's threads:
# the count of samples per state, where they were blocked in D state, the samples with the longest
# run-queue wait (a thread ready but not running), and how game-main/Render Thread overlapped.
# usage: ats-summary.py <ats file> [from s] [to s]
import sys, collections
path = sys.argv[1]
t0 = float(sys.argv[2]) if len(sys.argv) > 2 else 0
t1 = float(sys.argv[3]) if len(sys.argv) > 3 else 1e9
AUDIO = ("PulseMainloop", "SDLAudioP", "AK::")
st = collections.Counter(); dwc = collections.Counter(); worst = []; wait_sum = collections.Counter(); n = 0
for line in open(path):
    p = line.split()
    t = float(p[0])
    if t < t0 or t >= t1:
        continue
    n += 1
    for f in p[1:]:
        name, s, wc, cpu, wait = f.rsplit(":", 4)
        wait = float(wait[4:])
        st[(name, s)] += 1
        wait_sum[name] += wait
        if s == "D":
            dwc[(name, wc)] += 1
        if name.startswith(AUDIO) and wait > 3:
            worst.append((round(wait, 1), t, name, s, wc))
print("samples:", n)
print("states:", sorted(st.items()))
print("D-state blocking points:", dwc.most_common(10))
print("run-queue wait in all, ms:", {k: round(v, 1) for k, v in wait_sum.items()})
worst.sort(reverse=True)
print("longest run-queue waits of the sound threads in one 10-ms sample:", worst[:15])
