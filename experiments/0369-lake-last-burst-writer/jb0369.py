#!/usr/bin/env python3
# BC5 experiment 0369: GPU completion times of the jobs around the night lake's depth work in exp 0362's run H1, against
# its poll log. The draw journal prints, per job, "timing: t T s <kind> N dwords: sync ..." when it is submitted and
# "timing: #n done at t T s, X ms after the sync and hints; ..." when its fence signals (the patch's timing lines). A done
# line is paired with the submit line whose t is closest to T - X (within 1 ms, in file order). The jobs of interest:
#   R  the job submitted right before the "find ud cs 11d02d0a00" line (the first depth reader after the water draw; in
#      W257a/Z2 the readers follow the in-place decompress in the same buffer);
#   W  the job submitted right before the water draw's "bake draw" line.
# Emulator time t maps to wall time through the water draws' "bake draw ... t T wall W" pairs (median of W - t). For each
# frame (a pyramid change P, as in al0369.py) the times of R's and W's completion, and of the depth bursts, since P.
# usage: python3 -I jb0369.py <H1.events.txt.gz> <direct.log> [frames to list, 2]   (prints a summary only)
import bisect, gzip, re, statistics, sys

SUB = re.compile(r"^timing: t ([0-9.]+) s (\w+) (\d+) dwords: sync")
DONE = re.compile(r"^timing: #(\d+) done at t ([0-9.]+) s, ([0-9.]+) ms after the sync")
BAKE = re.compile(r"^bake draw buf \d+ at 222: t ([0-9.]+) wall ([0-9.]+)")
READ = re.compile(r"^find ud cs 11d02d0a00 t ([0-9.]+)")
subs, dones, offs, marks = [], [], [], []
for l in open(sys.argv[2], errors="replace"):
    m = SUB.match(l)
    if m:
        subs.append([float(m[1]), m[2], int(m[3]), None])
        continue
    m = DONE.match(l)
    if m:
        dones.append((int(m[1]), float(m[2]), float(m[3])))
        continue
    m = BAKE.match(l)
    if m:
        offs.append(float(m[2]) - float(m[1]))
        marks.append(("W", len(subs) - 1))
        continue
    m = READ.match(l)
    if m:
        marks.append(("R", len(subs) - 1))
off = statistics.median(offs)
st = [s[0] for s in subs]
paired = 0
for n, T, X in dones:
    s = T - X / 1000
    i = bisect.bisect_left(st, s)
    best = min((j for j in (i - 1, i) if 0 <= j < len(subs)), key=lambda j: abs(st[j] - s), default=None)
    if best is not None and abs(st[best] - s) < 0.001 and subs[best][3] is None:
        subs[best][3] = T
        paired += 1
print("# %d submit lines, %d done lines, %d paired; wall - t offset %.4f s (spread %.4f)" % (len(subs), len(dones), paired, off, max(offs) - min(offs)))

ev = [l.split() for l in gzip.open(sys.argv[1], "rt")]
P, D, last_p = [], [], -1.0
for mono, wall, d, p in ev:
    w = float(wall)
    if p == "P1":
        if w - last_p >= 0.001:
            P.append(w)
        last_p = w
    if d == "D1":
        D.append(w)
bursts = []
for w in D:
    if bursts and w - bursts[-1][1] < 0.0005:
        bursts[-1][1] = w
    else:
        bursts.append([w, w])


def since_p(t):
    i = bisect.bisect_right(P, t) - 1
    return (t - P[i]) * 1000 if 0 <= i and t - P[i] < 0.034 else None


def q(v):
    v = sorted(x for x in v if x is not None)
    return "n %d, 10 %% %.1f, median %.1f, 90 %% %.1f ms" % (len(v), v[len(v) // 10], statistics.median(v), v[9 * len(v) // 10]) if v else "none"


for kind in "WR":
    sub_t, done_t = [], []
    for k, i in marks:
        if k == kind and 0 <= i < len(subs) and subs[i][3] is not None:
            sub_t.append(since_p(subs[i][0] + off))
            done_t.append(since_p(subs[i][3] + off))
    print("# %s job (%s): submitted %s after the frame start; done %s" % (kind, {"W": "the water draw's", "R": "the first depth reader's"}[kind], q(sub_t), q(done_t)))
for k, (lo, hi) in enumerate(((0, 7.5), (7.5, 12), (15, 24))):
    sel = [b for b in bursts if since_p(b[0]) is not None and lo <= since_p(b[0]) < hi]
    print("# burst %d: start %s; end %s" % (k + 1, q([since_p(b[0]) for b in sel]), q([since_p(b[1]) for b in sel])))

# Prepare times: a "find ud cs X t T" or water "bake draw" line is printed by the ring thread while it prepares that
# pass's job, so the pass cannot run on the GPU before T. The job of the last submit line before such a line is that
# job or a later one (the game thread's submit lines can run ahead), so its completion is an upper bound for the pass.
FIND = re.compile(r"^find ud cs ([0-9a-f]+) t ([0-9.]+)")
prep, cur = {}, -1
for l in open(sys.argv[2], errors="replace"):
    if SUB.match(l):
        cur += 1
        continue
    m = FIND.match(l)
    if m:
        prep.setdefault(m[1], []).append((float(m[2]) + off, cur))
        continue
    m = BAKE.match(l)
    if m:
        prep.setdefault("water", []).append((float(m[1]) + off, cur))
for k in ("water", "11d02d0a00", "11d0404200", "11d039cd00", "11d0288800"):
    v = prep.get(k, [])
    print("# %-10s prepared %s; the job of the last submit line before it done %s" % (
        k, q([since_p(t) for t, j in v]), q([since_p(subs[j][3] + off) if subs[j][3] else None for t, j in v])))
# two frames in full: every job submitted from 2 ms before the frame start to 30 ms after, with its completion
nshow = int(sys.argv[3]) if len(sys.argv) > 3 else 2
lab, cur = {}, -1
JF = re.compile(r"^draw journal find: (\w+) (?:cs|ps) ud\d+ \([0-9a-f]+\) .*?ps ([0-9a-f]+) cs ([0-9a-f]+) \| pkt (c0[0-9a-f]+(?: [0-9a-f]+){0,3})")
for l in open(sys.argv[2], errors="replace"):
    if SUB.match(l):
        cur += 1
        continue
    m = JF.match(l)
    if m:
        w = m[4].split()
        lab.setdefault(cur, []).append("%s %s%s" % (m[1], m[3] if m[1] == "dispatch" else m[2], " %s" % "x".join(str(int(x, 16)) for x in w[1:4]) if m[1] == "dispatch" else ""))
    elif BAKE.match(l):
        lab.setdefault(cur, []).append("water draw")
for fi in range(100, 100 + nshow):
    p0 = P[fi]
    print("## frame at pyramid change %d; bursts (ms): %s" % (fi, ", ".join("%.1f-%.1f" % ((b[0] - p0) * 1000, (b[1] - p0) * 1000) for b in bursts if 0 <= b[0] - p0 < 0.034)))
    for j, s in enumerate(subs):
        t = s[0] + off
        if -0.002 <= t - p0 < 0.030:
            print("   job %d submitted %+5.1f done %5s  %s %5d  %s" % (j, (t - p0) * 1000, "%.1f" % ((s[3] + off - p0) * 1000) if s[3] else "-", s[1], s[2], "; ".join(lab.get(j, []))))
