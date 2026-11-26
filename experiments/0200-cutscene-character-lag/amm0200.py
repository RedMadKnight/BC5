#!/usr/bin/env python3
# BC5 (experiment 0200): the APR path from filt0200.py's raw/<tag>-amm.txt (KYTY_BC5_AMM_TRACE=1), on journal
# time. Per window of W s: submissions finished, per worker the mean and the longest time from submit to
# finished, MiB read, and the files read most; then every submission that took longer than LONG s.
# usage: amm0200.py <amm.txt> <play-pkg.log> [W] [LONG]
import collections, re, sys
amm, log = sys.argv[1], sys.argv[2]
W = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0
LONG = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5
t0 = None
for line in open(log, errors="replace"):
    if line.startswith("bc5 clock: journal t 0 = monotonic"):
        t0 = float(line.split()[-2]); break
if t0 is None:
    sys.exit("no journal t 0 line in the log")
psub = re.compile(r"^mono ([\d.]+) submit (0x[0-9a-f]+): (\d+) reads, (\d+) maps")
pread = re.compile(r"^mono ([\d.]+) read file (0x[0-9a-f]+) \+0x([0-9a-f]+) size 0x([0-9a-f]+)")
pfin = re.compile(r"^mono ([\d.]+) (?:resumed )?submission (0x[0-9a-f]+) finished(?: on worker (\d+))?")
pending = collections.defaultdict(collections.deque)
win = collections.defaultdict(lambda: {"n": 0, "lat": collections.defaultdict(list), "bytes": 0,
                                       "files": collections.Counter()})
longs = []
for line in open(amm, errors="replace"):
    m = psub.match(line)
    if m:
        pending[m.group(2)].append((float(m.group(1)) - t0, int(m.group(3)))); continue
    m = pread.match(line)
    if m:
        t = float(m.group(1)) - t0; k = int(t // W); sz = int(m.group(4), 16)
        win[k]["bytes"] += sz; win[k]["files"][m.group(2)] += sz; continue
    m = pfin.match(line)
    if m and pending[m.group(2)]:
        ts, nreads = pending[m.group(2)].popleft()
        t = float(m.group(1)) - t0; lat = t - ts; q = m.group(3) or "r"
        e = win[int(t // W)]; e["n"] += 1; e["lat"][q].append(lat)
        if lat > LONG:
            longs.append((ts, lat, q, nreads, m.group(2)))
print("# APR per %g s (journal time): finished submissions, per worker mean/max ms submit->finished, MiB read, top files" % W)
for k in sorted(win):
    e = win[k]
    lat = " ".join("q%s %.0f/%.0f" % (q, 1000 * sum(v) / len(v), 1000 * max(v)) for q, v in sorted(e["lat"].items()))
    top = " ".join("%s:%.1f" % (f, b / 1048576) for f, b in e["files"].most_common(3))
    print("%6.0f n %4d  %-40s  %6.1f MiB  %s" % (k * W, e["n"], lat, e["bytes"] / 1048576, top))
print("# submissions over %g s: t submit, s, worker, reads" % LONG)
for ts, lat, q, n, cb in longs:
    print("%8.2f %6.2f q%s %3d %s" % (ts, lat, q, n, cb))
left = sum(len(v) for v in pending.values())
print("# unfinished at the end: %d" % left)
