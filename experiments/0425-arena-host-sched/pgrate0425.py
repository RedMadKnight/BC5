# BC5 exp 0425: which thread calls PlayGo, and how often per second near G+9 s (descriptive, R11).
# usage (on the box): python3 pgrate0425.py LOG TAG G_SECONDS END_SECONDS
# A PlayGo call line is placed at the t of the last "fps counter" line before it (1 s resolution; 0 = before the
# first fps line, the load). The fps clock is the launch clock within a few seconds (the first fps line is at t 4 s,
# a run that ended at 118 s has its last fps line at t 114 s), so G on the fps clock is taken as G itself, and the
# window G..G+14 s is wide enough for that error.
import re, sys, collections
log, tag, g, end = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
t = 0.0
calls = []  # (fps t, thread)
fps = re.compile(r'^fps counter: t ([0-9.]+) s')
pg = re.compile(r"^\[bc5\] exp 0425 playgo: (\w+) call #\d+ on '([^']*)'")
owner = None
for line in open(log, errors='replace'):
    m = fps.match(line)
    if m:
        t = float(m.group(1)); continue
    m = pg.match(line)
    if m:
        calls.append((t, m.group(2), m.group(1))); continue
    if "the owner's first help call is on" in line:
        owner = line.rstrip().split("'")[-2]
lo, hi = g, g + 14  # the window around G+9 s
tot = collections.Counter(th for _, th, _ in calls)
win = collections.Counter(th for ft, th, _ in calls if lo <= ft < hi)
kinds = collections.Counter(k for _, _, k in calls)
print(f"{tag}: owner '{owner}'; PlayGo calls {len(calls)} ({dict(kinds)}); by thread {dict(tot)}; "
      f"in G..G+14 s: {sum(win.values())} calls = {sum(win.values())/14:.2f}/s, by thread {dict(win)}; "
      f"last call at fps t {max((ft for ft, _, _ in calls), default=0):.0f} s, last fps t {t:.0f} s")
