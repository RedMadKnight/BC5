# Pair each "timing: t T s KIND N dwords" with the next "#k done" line (FIFO) and sum the fence
# (submit to GPU done) per (kind, dwords) between two times; frames = frame profile lines there.
import re, sys, collections
path, t0, t1 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
rs = re.compile(r"timing: t ([0-9.]+) s (\w+) (\d+) dwords: sync")
rd = re.compile(r"timing: #(\d+) done at t ([0-9.]+) s, ([0-9.]+) ms after.*prepare ([0-9.]+) list ([0-9.]+) cs ([0-9.]+) fence ([0-9.]+) ms")
rf = re.compile(r"frame profile: t ([0-9.]+) s")
q = collections.deque(); agg = collections.defaultdict(lambda: [0, 0.0, 0.0]); frames = 0
for line in open(path, errors="replace"):
    m = rs.search(line)
    if m: q.append((float(m[1]), m[2], int(m[3]))); continue
    m = rd.search(line)
    if m and q:
        t, k, n = q.popleft()
        if t0 <= t <= t1:
            a = agg[(k, n)]; a[0] += 1; a[1] += float(m[7]); a[2] = max(a[2], float(m[7]))
        continue
    m = rf.search(line)
    if m and t0 <= float(m[1]) <= t1: frames += 1
print("frames", frames)
tot = 0
for (k, n), (c, s, mx) in sorted(agg.items(), key=lambda kv: -kv[1][1])[:25]:
    tot += s
    print("%s %5d  count %5d  per frame %5.2f  fence ms/frame %6.2f  mean %6.2f  max %6.2f" % (k, n, c, c / max(frames, 1), s / max(frames, 1), s / c, mx))
print("sum of listed fence ms/frame %.1f" % (tot / max(frames, 1)))
