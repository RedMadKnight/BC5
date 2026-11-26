import re, sys, statistics as st
# Summarise the direct path's "frame profile" lines of a journal between two times.
path = sys.argv[1]; t0 = float(sys.argv[2]); t1 = float(sys.argv[3])
rx = re.compile(r"frame profile: t ([0-9.]+) s, ([0-9.]+) ms since the last flip; game thread inside the host ([0-9.]+) ms \(sync ([0-9.]+), hints ([0-9.]+), prepare ([0-9.]+), list ([0-9.]+), cs ([0-9.]+), fence ([0-9.]+), cap ([0-9.]+), label waits ([0-9.]+), event waits ([0-9.]+)\), at the flip ([0-9.]+), outside ([0-9.]+); GPU busy ([0-9.]+) ms in (\d+) jobs \(\+(\d+) from the ring thread\)")
names = ["frame", "inside", "sync", "hints", "prepare", "list", "cs", "fence", "cap", "label", "event", "atflip", "outside", "gpu", "jobs", "ringjobs"]
rows = []
for line in open(path, errors="replace"):
    m = rx.search(line)
    if not m: continue
    t = float(m[1])
    if t0 <= t <= t1:
        rows.append([float(x) for x in m.groups()[1:]])
print("frames", len(rows), "fps %.2f" % (len(rows) / (t1 - t0) if rows else 0))
for i, n in enumerate(names):
    v = [r[i] for r in rows]
    if v: print("%-9s mean %7.1f median %7.1f p90 %7.1f" % (n, st.mean(v), st.median(v), sorted(v)[int(len(v) * 0.9)]))
