#!/usr/bin/env python3
"""BC5 exp 0432: read prof0432.sh's records of one run.
    prof_an0432.py <prefix>          (<prefix>-prof-threads.txt, -prof-gpu.txt, -prof-perf-sym.txt)
Prints: CPU seconds per thread over the window (user, system, waiting for a core) from /proc/<pid>/task/*/stat and
schedstat; the GPU engines' busy share from the DRM fdinfo; user-mode samples by object and the top symbols from the
perf report (cpu-clock:u, user mode only: kernel time is in the "system" column of the first table, not in perf)."""
import re, sys
from collections import defaultdict

pre = sys.argv[1]
HZ = 100.0

# threads
snaps = []
cur = None
for line in open(pre + "-prof-threads.txt", errors="replace"):
    f = line.split()
    if not f:
        continue
    if f[0] == "T":
        cur = (float(f[1]), {})
        snaps.append(cur)
    elif cur is not None and len(f) >= 7:
        cur[1][f[0]] = (f[1], int(f[2]), int(f[3]), int(f[4]), int(f[5]))
t0, a = snaps[0]
t1, b = snaps[-1]
wall = t1 - t0
rows = []
for tid, (name, ut, st, run, wait) in b.items():
    if tid in a:
        _, ut0, st0, run0, wait0 = a[tid]
    else:
        ut0 = st0 = run0 = wait0 = 0
    rows.append((name, (ut - ut0) / HZ, (st - st0) / HZ, (run - run0) / 1e9, (wait - wait0) / 1e9))
grp = defaultdict(lambda: [0, 0.0, 0.0, 0.0, 0.0])
for name, u, s, r, w in rows:
    g = re.sub(r"[_ ]?\d+$", "", name) if re.match(r"(Job_(Hi|Lo|Bk)|bc5-apr|BinkAsy|bc5-cq|SDLAudio)", name) else name
    x = grp[g]
    x[0] += 1
    x[1] += u
    x[2] += s
    x[3] += r
    x[4] += w
tu = sum(x[1] for x in grp.values())
ts = sum(x[2] for x in grp.values())
tw = sum(x[4] for x in grp.values())
print("%s: window %.0f s; all threads: user %.0f s, system %.0f s (%.2f cores busy of 16), waiting for a core %.0f s" % (pre.split("/")[-1], wall, tu, ts, (tu + ts) / wall, tw))
print("  %-22s %3s %8s %8s %8s %9s" % ("thread (group)", "n", "user s", "sys s", "% wall", "runq s"))
for g, x in sorted(grp.items(), key=lambda kv: -(kv[1][1] + kv[1][2]))[:22]:
    print("  %-22s %3d %8.1f %8.1f %7.1f%% %9.1f" % (g, x[0], x[1], x[2], 100 * (x[1] + x[2]) / wall / x[0], x[4]))

# GPU engines
first = {}
last = {}
tf = tl = None
t = None
for line in open(pre + "-prof-gpu.txt", errors="replace"):
    if line.startswith("T "):
        t = float(line.split()[1])
        if tf is None:
            tf = t
        tl = t
        continue
    m = re.search(r"drm-client-id:\s*(\d+)", line)
    if not m:
        continue
    cid = m.group(1)
    for eng, ns in re.findall(r"drm-engine-(\w+):\s*(\d+) ns", line):
        first.setdefault((cid, eng), int(ns))
        last[(cid, eng)] = int(ns)
print("  GPU engines busy over %.0f s (DRM fdinfo; a client's engine time, 100 %% = one ring always running):" % (tl - tf))
for k in sorted(last):
    d = (last[k] - first[k]) / 1e9
    if d > 0.05:
        print("    client %s %-8s %6.1f s  %5.1f%%" % (k[0], k[1], d, 100 * d / (tl - tf)))

# perf, user mode
dso = defaultdict(float)
sym = []
seen = 0.0
for line in open(pre + "-prof-perf-sym.txt", errors="replace"):
    m = re.match(r"\s+([0-9.]+)%\s+(.+?)\s+\[\.\]\s+(.*\S)", line)
    if not m:
        continue
    p = float(m.group(1))
    d = "guest code" if m.group(2).startswith("memfd:") or m.group(2).startswith("[JIT]") else m.group(2)
    dso[d] += p
    seen += p
    if d != "guest code":
        sym.append((p, d, m.group(3)[:110]))
print("  perf, user mode: the report's %.1f%% of samples by object (the rest is below the report's cut):" % seen)
for d, p in sorted(dso.items(), key=lambda kv: -kv[1])[:8]:
    print("    %5.2f%%  %s" % (p, d))
print("  top host symbols:")
for p, d, s in sym[:20]:
    print("    %5.2f%%  %-18s %s" % (p, d, s))
