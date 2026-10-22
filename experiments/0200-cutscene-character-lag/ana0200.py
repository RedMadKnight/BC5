#!/usr/bin/env python3
# BC5 (experiment 0200): per window of W seconds, on journal time (the play log's "bc5 clock: journal t 0 =
# monotonic" line), next to each other:
#   clock    speed of the sync clock 0x90ae007b4 (Wwise's play position of the master voice; unwrapped at 10 s)
#   clip     speed of a main cinematic player's clip time (+0xf8), when sample0200.py had found one (of several,
#            the one with the largest mean |debt| in the window; n = how many were followed)
#   debt     its slew filter's carried error +0x100, mean over the window: > 0 the clip trails the clock's
#            advance, < 0 the clip runs ahead of a clock that advances slower than the frame time
#   rate     the factor the filtered advance is multiplied by (clamped +0x108, times the source rate when
#            flagged; 1 when forced), mean over the window; div the global dt divisor 0x90bee5f48
#   voice    decode speed of the clock voice (the AJM instance whose passes are 479,352 samples, F242)
#   a/p      AudioOut2 advances / pushes (KYTY_BC5_AUDIO2_TRACE), flips/s (fps counter)
#   pressure compaction stalls/s, major faults/s, PSI memory full / io full avg10, MemAvailable, the clock's wrap,
#            the clock voice's playing id (vid) and the host's AJM instance counter (ajm#; a slot comes round every
#            16,384)
#   threads  ms on CPU and ms waiting for a CPU, and D-state samples, of game-main, AK::AudioMgr, AK::IOThread,
#            the APR workers (summed)
# usage: ana0200.py <sample.txt> <play-pkg.log> [ajm-index.txt] [W]
import collections, re, sys
samp, log = sys.argv[1], sys.argv[2]
idx = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "-" else None
W = float(sys.argv[4]) if len(sys.argv) > 4 else 5.0

t0 = None; a2 = collections.defaultdict(lambda: [0, 0]); fps = collections.defaultdict(list)
pa2 = re.compile(r"^audio2 trace: t ([\d.]+) s: .*advance (\d+), push (\d+)")
pfps = re.compile(r"^fps counter: t ([\d.]+) s: (\d+) flips in ([\d.]+) s")
for line in open(log, errors="replace"):
    if line.startswith("bc5 clock: journal t 0 = monotonic"):
        t0 = float(line.split()[-2])
    m = pa2.match(line)
    if m:
        k = int(float(m.group(1)) // W); a2[k][0] += int(m.group(2)); a2[k][1] += int(m.group(3))
    m = pfps.match(line)
    if m:
        fps[int(float(m.group(1)) // W)].append(int(m.group(2)) / float(m.group(3)))
if t0 is None:
    sys.exit("no journal t 0 line in the log")

clock = []; clip = []; vm = {}; divs = {}; thr = collections.defaultdict(lambda: collections.defaultdict(lambda: [0.0, 0.0, 0]))
events = []
for line in open(samp):
    q = line.split()
    if not q or q[0].startswith("#"):
        continue
    if q[0] == "c":  # c mono clock mode div framedt [player clip adv debt last target rate srate fl]...
        t = float(q[1]) - t0
        clock.append((t, float(q[2])))
        dv = divs.setdefault(int(t // W), [0.0, 0]); dv[0] += float(q[4]); dv[1] += 1
        for j in range(6, len(q) - 8, 9):
            fl = int(q[j + 8])
            eff = 1.0 if fl & 1 else min(max(float(q[j + 6]), 1e-4), 4.0) * (float(q[j + 7]) if fl & 2 else 1.0)
            clip.append((t, int(q[j], 16), float(q[j + 1]), float(q[j + 3]), eff, (fl & 12) == 12))
    elif q[0] == "v":  # per window: compaction stalls and major faults summed, PSI and MemAvailable the last
        k = int((float(q[1]) - t0) // W)
        e = vm.setdefault(k, [0, 0, 0, "-", "-", "-", "-", "-", "-"])
        e[0] += int(q[2]); e[1] += int(q[3]); e[2] += 1; e[3], e[4], e[5] = q[7], q[9], q[11]
        e[6] = q[12] if len(q) > 12 else "-"
        if len(q) > 15:  # the clock voice's playing id and the AJM instance counter
            e[7], e[8] = q[14], q[15]
    elif q[0] == "t":
        k = int((float(q[1]) - t0) // W)
        name = q[2].split("/")[0]
        name = "apr" if name.startswith("bc5-apr") else name
        e = thr[k][name]; e[0] += float(q[3]); e[1] += float(q[4]); e[2] += int(q[7])
    elif q[0] == "p":
        events.append("%.1f %s" % (float(q[1]) - t0, " ".join(q[2:])))

def speeds(series, wrap):
    acc = collections.defaultdict(lambda: [0.0, 0.0])
    for (ta, va), (tb, vb) in zip(series, series[1:]):
        d = vb - va
        if wrap and d < -wrap / 2:
            d += wrap
        if tb - ta > 1.0 or d < -0.5 or d > 5.0:  # a gap in the samples or a jump (new scene)
            continue
        k = int(ta // W); acc[k][0] += d; acc[k][1] += tb - ta
    return {k: v[0] / v[1] for k, v in acc.items() if v[1] > 0.5 * W}

cs = speeds(clock, 10.0)
# Per player: clip speed and mean debt per window; the window shows the player with the largest |debt|.
cl = {}; lag = {}; rate = {}; path = {}; nplay = collections.Counter(); summary = []
by = collections.defaultdict(list)
for t, p, c, d, r, s_ in clip:
    by[p].append((t, c, d, r, s_))
for p, ser in by.items():
    sp = speeds([(t, c) for t, c, d, r, s_ in ser], 0.0)
    dsum = collections.defaultdict(lambda: [0.0, 0.0, 0, 0])
    for t, c, d, r, s_ in ser:
        e = dsum[int(t // W)]; e[0] += d; e[1] += r; e[2] += 1; e[3] += 1 if s_ else 0
    for k, (s, rs, n, ns) in dsum.items():
        nplay[k] += 1
        if k not in lag or abs(s / n) > abs(lag[k]):
            lag[k] = s / n; rate[k] = rs / n; path[k] = "S" if ns == n else ("U" if ns == 0 else "m")
            if k in sp:
                cl[k] = sp[k]
            else:
                cl.pop(k, None)
    ds = [x[2] for x in ser]; rs = [x[3] for x in ser]
    summary.append("%x t %.1f-%.1f, debt %+.3f..%+.3f, rate %.3f..%.3f" % (p, ser[0][0], ser[-1][0], min(ds), max(ds),
                                                                          min(rs), max(rs)))
dvm = {k: v[0] / v[1] for k, v in divs.items() if v[1]}

voice = {}
if idx:
    prev = {}; seg0 = {}; s0 = {}; clockinst = set(); rows = []
    for l in open(idx):
        q = l.split()
        if len(q) < 5:
            continue
        t = float(q[0]) - t0; i = q[1]; s = int(q[4]); rows.append((t, i, s))
        if i in prev and s < prev[i]:
            if prev[i] - s0[i] == 479352:
                clockinst.add(i)
            seg0[i] = t; s0[i] = s
        if i not in prev:
            seg0[i] = t; s0[i] = s
        prev[i] = s
    acc = collections.defaultdict(lambda: [0, None, None]); last = {}
    for t, i, s in rows:
        if i not in clockinst:
            continue
        if i in last:
            d = s - last[i] if s >= last[i] else s  # a new pass starts from 0
            k = int(t // W); acc[k][0] += d
        last[i] = s
    voice = {k: v[0] / 48000.0 / W for k, v in acc.items()}
    print("# clock voice instances: %s" % " ".join(sorted(clockinst)))

print("# windows of %g s on journal time" % W)
for e in events:
    print("# player event: " + e)
for s in summary:
    print("# player " + s)
print("t      clock  clip   debt  rate  div   n/path voice  a/p    fps   | cstall/s majf/s memfull iofull availMB wrap vid ajm# | game-main run/wait/D  AudioMgr run/wait/D  IOThread run/wait/D  apr run/wait/D")
ks = sorted(set(cs) | set(vm))
for k in ks:
    def f(d, fmt="%.2f"):
        return (fmt % d[k]) if k in d else "  -  "
    ap = ("%.2f" % (a2[k][0] / a2[k][1])) if a2[k][1] else "  -  "
    fp = ("%.1f" % (sum(fps[k]) / len(fps[k]))) if fps[k] else "  - "
    v = vm.get(k)
    pres = ("%5.0f %5.0f %6s %6s %6s %5s %6s %6s" % (v[0] / v[2], v[1] / v[2], v[3], v[4], v[5], v[6], v[7], v[8])) if v else "  -"
    th = []
    for n in ("game-main", "AK::AudioMgr", "AK::IOThread", "apr"):
        e = thr[k].get(n)
        th.append(("%5.0f/%4.0f/%2d" % (e[0], e[1], e[2])) if e else "     -      ")
    print("%6.0f %s  %s  %s %s %s %d%s %s  %s  %s | %s | %s" % (k * W, f(cs), f(cl), f(lag, "%+.2f"), f(rate), f(dvm), nplay[k], path.get(k, " "),
                                                          f(voice), ap, fp, pres, "  ".join(th)))
