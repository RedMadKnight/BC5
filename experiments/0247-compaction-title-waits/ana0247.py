#!/usr/bin/env python3
# BC5 experiment 0247: what the second title's threads do during its long flip gaps. For one bench run, it reads
# the journal extract (frame profile, wait trace), the emulator-log extract ("bc5 clock" line, AMM trace) and the
# hoststate0247.py sampler file. For every flip gap over a threshold it prints: the game thread's time outside the
# host; per watched thread, CPU ms and state samples (R running, S sleeping, D uninterruptible) over the gap; the
# title threads with the most CPU in it; the traced label waits and the AMM trace events inside it. A baseline gives
# the same per-second rates over the rest of a time window.
# usage: ana0247.py <tag> <x.gz> <emu-x.gz> <hs.txt> [gap_ms=300] [base_t0=180 base_t1=300]
import collections
import gzip
import re
import sys

tag, xf, ef, hf = sys.argv[1:5]
gap_min = float(sys.argv[5]) if len(sys.argv) > 5 else 300.0
b0 = float(sys.argv[6]) if len(sys.argv) > 6 else 180.0
b1 = float(sys.argv[7]) if len(sys.argv) > 7 else 300.0

clock = None
amm = []  # (mono, kind)
for line in gzip.open(ef, "rt", errors="replace"):
    if clock is None and "bc5 clock: journal t 0 = monotonic" in line:
        clock = float(re.search(r"monotonic ([0-9.]+)", line).group(1))
    m = re.match(r"mono ([0-9.]+) amm trace: ([a-z-]+)", line)
    if m:
        amm.append((float(m.group(1)), m.group(2)))
if clock is None:
    sys.exit("no bc5 clock line")

flips = []  # (t, gap_ms, outside_ms)
waits = []  # (t, label)
afterw = []  # t of "timing: t X s after that wait"
for line in gzip.open(xf, "rt", errors="replace"):
    if line.startswith("frame profile: t "):
        f = line.split()
        t, g = float(f[3]), float(f[5])
        o = re.search(r"outside ([0-9.]+)", line)
        flips.append((t, g, float(o.group(1)) if o else 0.0))
    elif line.startswith("wait trace: t "):
        m = re.search(r"t ([0-9.]+) s .* on (0x[0-9a-f]+)", line)
        if m:
            waits.append((float(m.group(1)), m.group(2)))
    elif line.startswith("timing: t ") and "after that wait" in line:
        afterw.append(float(line.split()[2]))

per = collections.defaultdict(list)  # thread name -> [(mono, run, wait, R, S, D)]
top = []  # (mono, [(name, run, state)])
for line in open(hf, errors="replace"):
    f = line.split()
    if not f:
        continue
    if f[0] == "t" and len(f) >= 9:
        name = f[2].split("/")[0]
        per[name].append((float(f[1]), float(f[3]), float(f[4]), int(f[5]), int(f[6]), int(f[7])))
    elif f[0] == "k":
        items = []
        for it in f[2:]:
            p = it.rsplit(":", 2)
            if len(p) == 3:
                items.append((p[0].split("/")[0], float(p[1]), p[2]))
        top.append((float(f[1]), items))

def window(m0, m1):
    out = {}
    for name, rows in per.items():
        sel = [r for r in rows if m0 < r[0] <= m1]
        if sel:
            out[name] = (sum(r[1] for r in sel), sum(r[3] for r in sel), sum(r[4] for r in sel), sum(r[5] for r in sel), len(sel))
    busy = collections.Counter()
    for mono, items in top:
        if m0 < mono <= m1:
            for n, r, s in items:
                busy[n] += r
    am = collections.Counter(k for mono, k in amm if m0 < mono <= m1)
    return out, busy, am

def show(label, t0, t1):
    m0, m1 = clock + t0, clock + t1
    out, busy, am = window(m0, m1)
    span = max(t1 - t0, 1e-9)
    print("  %s (%.2f s)" % (label, span))
    for name in ("game-main", "Render_Thread", "bc5-ring", "AK::IOThread", "kyty-gpu"):
        if name in out:
            run, R, S, D, n = out[name]
            print("    %-14s %6.0f ms CPU (%4.0f ms/s); states R %3d S %3d D %3d" % (name, run, run / span, R, S, D))
    print("    busiest title threads: " + ", ".join("%s %.0f" % (n, r) for n, r in busy.most_common(6)))
    wl = [w for w in waits if t0 <= w[0] <= t1]
    aw = [a for a in afterw if t0 <= a <= t1]
    print("    traced label waits %d (labels %s); 'after that wait' lines %d; AMM trace: %s" % (
        len(wl), ",".join(sorted(set(w[1] for w in wl)))[:120] or "-", len(aw), dict(am.most_common(6)) or "-"))

stalls = [(t, g, o) for t, g, o in flips if g > gap_min]
print("%s: %d flips, %d gaps over %.0f ms; bc5 clock %.3f" % (tag, len(flips), len(stalls), gap_min, clock))
for t, g, o in stalls:
    show("gap t %.1f-%.1f, %.0f ms, outside %.0f ms" % (t - g / 1000, t, g, o), t - g / 1000.0, t)
# baseline: the whole window, per second, minus nothing (stalls are a small share)
print("baseline window t %.0f-%.0f:" % (b0, b1))
show("all", b0, b1)
