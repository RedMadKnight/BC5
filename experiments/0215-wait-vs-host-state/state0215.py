#!/usr/bin/env python3
# TCP session, tcpW4: the host's state around each game-thread label wait.
# Inputs: the journal extract (extract0209.sh lines: wait trace, after that wait, cpu-wait, frame profile),
# the hoststate.py sampler output (v/g/t lines on CLOCK_MONOTONIC), and the emulator log, whose
# "bc5 clock: journal t 0 = monotonic X s" line maps journal t to the sampler's clock.
# For every traced dcb wait it takes the duration as ana0209.py does (its own "after that wait" line before
# the game thread's next traced wait; none = ended inside the 4-ms window) and integrates the sampler's
# 0.1-s periods over [start, end] and over the 500 ms before the start (each period weighted by its overlap):
#   gcpu  the title's threads' CPU (ms)      gD    the title's threads in D state (mean count)
#   memf  PSI memory full (ms stalled)       iof   PSI io full (ms)        majf  major faults
# Then it compares waits by kind: short (< 4 ms), long (> 8 ms, served), given up.
# usage: state0215.py <extract> <hoststate.txt> <emulator-log>
import bisect, re, sys
from collections import defaultdict

WT = re.compile(r'^wait trace: t ([0-9.]+) s dcb (\d+) dwords at (\d+) \(ring (-?\d+)\) on (0x[0-9a-f]+):')
AW = re.compile(r'^timing: t ([0-9.]+) s after that wait \(dcb (\d+) dwords\)')
GU = re.compile(r'^cpu-wait \S+ at (\d+) on (0x[0-9a-f]+): GIVEN UP after ([0-9.]+) ms')
T0 = re.compile(r'bc5 clock: journal t 0 = monotonic ([0-9.]+) s')

def load_sampler(path):
    v, g = [], []
    for line in open(path, errors='replace'):
        p = line.split()
        if not p: continue
        if p[0] == 'v' and len(p) >= 12:
            # v mono dcompact dmajf dpswpin dalloc mem_some mem_full io_some io_full cpu_some avail
            v.append((float(p[1]), int(p[3]), int(p[4]), int(p[6]) / 1000.0, int(p[8]) / 1000.0, int(p[11])))
        elif p[0] == 'g' and len(p) >= 10:
            # g mono grun gwait R S D n hrun hn  -> (mono, title CPU ms, D count, title threads)
            g.append((float(p[1]), float(p[2]), int(p[6]), int(p[7])))
    return v, g

def integrate(series, idx_t, lo, hi, cols, period=0.1):
    """Sum of the given columns over the periods (end time t, covering [t - period, t]) weighted by overlap."""
    out = [0.0] * len(cols)
    if hi <= lo: return out
    i = bisect.bisect_left(idx_t, lo)
    while i < len(series) and idx_t[i] - period < hi:
        t = idx_t[i]
        a, b = max(lo, t - period), min(hi, t)
        if b > a:
            w = (b - a) / period
            for k, c in enumerate(cols):
                out[k] += series[i][c] * w
        i += 1
    return out

def main():
    ext, samp, log = sys.argv[1], sys.argv[2], sys.argv[3]
    t0 = None
    for line in open(log, errors='replace'):
        m = T0.search(line)
        if m: t0 = float(m.group(1)); break
    if t0 is None:
        sys.exit('no "bc5 clock: journal t 0 = monotonic" line in %s' % log)
    v, g = load_sampler(samp)
    vt, gt = [r[0] for r in v], [r[0] for r in g]
    cover = next((r[0] for r in g if r[3] > 0), None)   # the first period with the title's threads counted
    if cover is None: sys.exit('the sampler never saw any threads of the title')
    print('# journal t 0 = mono %.3f; sampler: %d v, %d g periods, mono %.1f..%.1f' % (t0, len(v), len(g), vt[0] if vt else 0, vt[-1] if vt else 0))

    waits = []                           # (t1, t2_or_None, label, given_up)
    cur = None; pending = None; last_trace = 0.0
    for line in open(ext, errors='replace'):
        m = WT.match(line)
        if m:
            if cur is not None and not cur[3]: waits.append((cur[0], None, cur[2], False))
            cur = [float(m.group(1)), int(m.group(2)), m.group(5), False]; last_trace = cur[0]
            continue
        m = GU.match(line)
        if m: pending = m.group(2); continue
        m = AW.match(line)
        if m:
            t2, n = float(m.group(1)), int(m.group(2))
            if cur is not None and not cur[3] and n == cur[1] and t2 >= cur[0]:
                waits.append((cur[0], t2, cur[2], pending == cur[2])); cur[3] = True
            pending = None
    if cur is not None and not cur[3]: waits.append((cur[0], None, cur[2], False))

    groups = defaultdict(list)
    rows = []
    skipped = 0
    for (t1, t2, label, gu) in waits:
        if t0 + t1 - 0.5 < cover: skipped += 1; continue   # before the sampler counted the title's threads
        dur = None if t2 is None else (t2 - t1) * 1000.0
        kind = 'short' if dur is None or dur <= 4.5 else ('given up' if gu else ('long' if dur > 8.5 else 'mid'))
        s = t0 + t1; e = t0 + (t2 if t2 is not None else t1 + 0.004)
        dg = integrate(g, gt, s, e, (1, 2))           # title CPU ms, D count (summed over period-weights)
        dv = integrate(v, vt, s, e, (3, 4, 1))        # memfull ms, iofull ms, majf
        bg = integrate(g, gt, s - 0.5, s, (1, 2))
        bv = integrate(v, vt, s - 0.5, s, (3, 4, 1))
        span = max(e - s, 1e-9)
        r = dict(t=t1, label=label, kind=kind, dur=dur if dur is not None else 0.0,
                 gcpu=dg[0], gcpu_rate=dg[0] / (span * 1000.0), memf=dv[0], iof=dv[1], majf=dv[2],
                 b_gcpu_rate=bg[0] / 500.0, b_gD=bg[1] / 5.0, b_memf=bv[0], b_iof=bv[1], b_majf=bv[2])
        groups[kind].append(r); rows.append(r)

    print('# %d waits before mono %.1f (journal t %.1f s) left out: the sampler had not yet counted the threads of the title' % (skipped, cover, cover - t0))
    def q(xs, p):
        xs = sorted(xs); return xs[min(len(xs) - 1, int(p * (len(xs) - 1) + 0.5))] if xs else float('nan')
    print('# distributions (p10 / p50 / p90) per kind of wait')
    for key, name in (('gcpu_rate', 'title CPU per wall ms, during'), ('b_gcpu_rate', 'title CPU per wall ms, 500 ms before'),
                      ('b_gD', 'title threads in D, 500 ms before (mean)'), ('b_memf', 'PSI memory full ms, 500 ms before'),
                      ('b_iof', 'PSI io full ms, 500 ms before'), ('b_majf', 'major faults, 500 ms before')):
        print('  %-42s' % name + '  '.join('%s %d: %.2f / %.2f / %.2f' % (k, len(groups.get(k, [])), q([r[key] for r in groups.get(k, [])], .1),
              q([r[key] for r in groups.get(k, [])], .5), q([r[key] for r in groups.get(k, [])], .9)) for k in ('short', 'long', 'given up') if groups.get(k)))
    def med(xs):
        xs = sorted(xs); return xs[len(xs) // 2] if xs else float('nan')
    print('%-9s %6s %8s | during: title CPU/wall %-6s | 500 ms before: title CPU/wall  D-threads  PSI mem full ms  io full ms  major faults' % ('kind', 'n', 'dur p50', ''))
    for kind in ('short', 'mid', 'long', 'given up'):
        rs = groups.get(kind, [])
        if not rs: continue
        print('%-9s %6d %8.1f | %22.2f | %26.2f %10.1f %16.1f %11.1f %13.0f' % (kind, len(rs), med([r['dur'] for r in rs]),
              med([r['gcpu_rate'] for r in rs]), med([r['b_gcpu_rate'] for r in rs]), med([r['b_gD'] for r in rs]),
              med([r['b_memf'] for r in rs]), med([r['b_iof'] for r in rs]), med([r['b_majf'] for r in rs])))
    print('# medians; "title CPU/wall" = CPU ms of the title\'s threads per ms of wall time (several threads run at once)')
    print()
    print('# every wait over 8 ms and every give-up:')
    print('# t(journal)  label           kind      dur  | during: gCPU ms  CPU/wall memfull iofull majf | before: CPU/wall  D   memfull iofull majf')
    for r in rows:
        if r['kind'] in ('long', 'given up'):
            print('%9.3f  %-14s %-9s %5.0f | %8.1f %8.2f %7.1f %6.1f %4.0f | %8.2f %4.1f %7.1f %6.1f %4.0f' % (
                r['t'], r['label'], r['kind'], r['dur'], r['gcpu'], r['gcpu_rate'], r['memf'], r['iof'], r['majf'],
                r['b_gcpu_rate'], r['b_gD'], r['b_memf'], r['b_iof'], r['b_majf']))

main()
