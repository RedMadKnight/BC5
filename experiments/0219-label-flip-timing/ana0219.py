#!/usr/bin/env python3
# BC5 experiment 0219: when the label of a slow game-thread wait is written, against the GPU jobs.
# Reads the run's extract (run0219.sh extract): the "flip trace:" lines of BC5_DIRECT_FLIP_TRACE=1 (patch_0219.diff).
#   given up  "#ID given up: ... on 0xL (game thread G) after X ms, t T s; value 0xV; in flight cq0 a cq1 b; ..."
#   change    "#ID 0xL: 0xOLD -> 0xNEW at t T s, X ms after the give-up; in flight cq0 a cq1 b"
#   end       "#ID 0xL satisfied|NOT satisfied within 2 s X ms after the give-up (Y ms after the wait began), t T s; in flight cq0 a cq1 b ..."
#   served    "served K N dwords at AT on 0xL after X ms, t T s; in flight cq0 a cq1 b; ..."
#   job       "job #n K N dwords done at t T s (cqQ); in flight cq0 a cq1 b"
# For each flip (a given-up label satisfied, or a served wait of 4 ms or more) it takes the jobs in flight at that moment
# and the first job completion seen after it (journaled while a label is watched and for 20 ms after a flip, 5 ms after
# a served wait). A label that a job writes flips while that job is in flight and just before its completion is seen;
# a label the title's CPU code writes can flip with no job in flight, and its next completion is no closer than at a
# random moment. The baseline is that random moment: points spread evenly over the stretches where completions were
# journaled, with the same "next completion after" measure.
# usage: ana0219.py <extract>
import bisect, re, sys
from collections import defaultdict

GIVE = re.compile(r'^flip trace: #(\d+) given up: (\S+) (\d+) dwords at (\d+) on (0x[0-9a-f]+) \(game thread (\d)\) after ([0-9.]+) ms, t ([0-9.]+) s; value (0x[0-9a-f]+); in flight cq0 (-?\d+) cq1 (-?\d+)')
CHG = re.compile(r'^flip trace: #(\d+) (0x[0-9a-f]+): (0x[0-9a-f]+) -> (0x[0-9a-f]+) at t ([0-9.]+) s, ([0-9.]+) ms after the give-up; in flight cq0 (-?\d+) cq1 (-?\d+)')
END = re.compile(r'^flip trace: #(\d+) (0x[0-9a-f]+) (satisfied|NOT satisfied within 2 s) ([0-9.]+) ms after the give-up \(([0-9.]+) ms after the wait began\), t ([0-9.]+) s; in flight cq0 (-?\d+) cq1 (-?\d+) \(at the give-up (-?\d+) (-?\d+)\); (\d+) jobs done since the give-up, the last (-?[0-9.]+) ms before .*; value (0x[0-9a-f]+), (\d+) changes')
SRV = re.compile(r'^flip trace: served (\S+) (\d+) dwords at (\d+) on (0x[0-9a-f]+) after ([0-9.]+) ms, t ([0-9.]+) s; in flight cq0 (-?\d+) cq1 (-?\d+); (\d+) jobs done during the wait, the last (-?[0-9.]+) ms before its end')
JOB = re.compile(r'^flip trace: job #(\d+) (\S+) (\d+) dwords done at t ([0-9.]+) s \(cq(\d)\); in flight cq0 (-?\d+) cq1 (-?\d+)')


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * (len(xs) - 1) + 0.5))] if xs else float('nan')


def dist(xs):
    return 'n %d, p10 %.3f / p50 %.3f / p90 %.3f' % (len(xs), q(xs, .1), q(xs, .5), q(xs, .9)) if xs else 'n 0'


def main():
    gives, ends, changes, served, jobs = {}, {}, defaultdict(list), [], []
    for line in open(sys.argv[1], errors='replace'):
        if not line.startswith('flip trace: '):
            continue
        m = JOB.match(line)
        if m:
            jobs.append((float(m.group(4)), int(m.group(1)), m.group(2), int(m.group(3)), int(m.group(5))))
            continue
        m = GIVE.match(line)
        if m:
            gives[m.group(1)] = dict(kind=m.group(2), dwords=int(m.group(3)), label=m.group(5), game=m.group(6) == '1', waited=float(m.group(7)),
                                     t=float(m.group(8)), value=m.group(9), q0=int(m.group(10)), q1=int(m.group(11)))
            continue
        m = CHG.match(line)
        if m:
            changes[m.group(1)].append((float(m.group(5)), m.group(3), m.group(4), float(m.group(6)), int(m.group(7)), int(m.group(8))))
            continue
        m = END.match(line)
        if m:
            ends[m.group(1)] = dict(sat=m.group(3) == 'satisfied', after=float(m.group(4)), total=float(m.group(5)), t=float(m.group(6)),
                                    q0=int(m.group(7)), q1=int(m.group(8)), jobs_since=int(m.group(11)), last_ago=float(m.group(12)), value=m.group(13))
            continue
        m = SRV.match(line)
        if m:
            served.append(dict(kind=m.group(1), dwords=int(m.group(2)), label=m.group(4), waited=float(m.group(5)), t=float(m.group(6)),
                               q0=int(m.group(7)), q1=int(m.group(8)), during=int(m.group(9)), last_ago=float(m.group(10))))
            continue
        print('# unparsed: ' + line.rstrip()[:160])
    jobs.sort()
    jt = [j[0] for j in jobs]

    def next_done(t, horizon):
        """ms from t to the first journaled completion after it (None: none within horizon ms)."""
        i = bisect.bisect_right(jt, t)
        if i < len(jt) and (jt[i] - t) * 1000.0 <= horizon:
            return (jt[i] - t) * 1000.0, jobs[i]
        return None, None

    print('# %d give-ups traced, %d ended (%d satisfied), %d served waits of 4 ms or more, %d job completions journaled'
          % (len(gives), len(ends), sum(e['sat'] for e in ends.values()), len(served), len(jobs)))
    print()
    print('# every give-up: the wait, when its label was satisfied, the jobs in flight then, the next completion after it')
    print('#  id  t(give)    label          value at give-up    waited  satisfied after  total ms  in flight (give-up -> flip)  next done ms  (job)  changes')
    flips = []   # (kind, label, in_flight_total, next_ms)
    for gid in sorted(gives, key=lambda k: gives[k]['t']):
        g, e = gives[gid], ends.get(gid)
        if e is None:
            print('%4s %9.3f  %-14s %-18s %6.2f  (no end line: the run ended while it was watched)' % (gid, g['t'], g['label'], g['value'], g['waited']))
            continue
        nd, job = next_done(e['t'], 20.0) if e['sat'] else (None, None)
        chs = '; '.join('%s->%s at +%.3f ms (cq0 %d cq1 %d)' % (c[1], c[2], c[3], c[4], c[5]) for c in changes.get(gid, [])[:4])
        print('%4s %9.3f  %-14s %-18s %6.2f  %15s  %8.2f  cq0 %d cq1 %d -> cq0 %d cq1 %d  %12s  %s  %s' % (
            gid, g['t'], g['label'], g['value'], g['waited'], '%.3f ms' % e['after'] if e['sat'] else 'NOT in 2 s', e['total'],
            g['q0'], g['q1'], e['q0'], e['q1'], '%.3f' % nd if nd is not None else '-', '#%d %s %d' % (job[1], job[2], job[3]) if job else '', chs))
        if e['sat']:
            flips.append(('given up', g['label'], e['q0'] + e['q1'], nd))
    for s in served:
        nd, _ = next_done(s['t'], 5.0)
        flips.append(('served', s['label'], s['q0'] + s['q1'], nd))

    # The baseline: the same "next completion within the horizon" at evenly spread moments inside the journaled stretches
    # (each stretch: completions less than 25 ms apart).
    base = []
    if len(jt) > 1:
        k0 = 0
        for k in range(1, len(jt) + 1):
            if k == len(jt) or jt[k] - jt[k - 1] > 0.025:
                a, b = jt[k0], jt[k - 1]
                n = int((b - a) / 0.0005)
                for s in range(n):
                    t = a + s * 0.0005
                    nd, _ = next_done(t, 20.0)
                    if nd is not None:
                        base.append(nd)
                k0 = k
    print()
    print('# the next job completion after the flip, ms (within 20 ms of a give-up flip, 5 ms of a served wait)')
    for kind in ('given up', 'served'):
        fs = [f for f in flips if f[0] == kind]
        if not fs:
            continue
        idle = [f for f in fs if f[2] == 0]
        near = [f for f in fs if f[3] is not None and f[3] <= 0.5]
        print('%-9s flips %d: %d with no job in flight on either queue; %d with a completion within 0.5 ms after; next completion %s'
              % (kind, len(fs), len(idle), len(near), dist([f[3] for f in fs if f[3] is not None])))
    print('baseline  (evenly spread moments while completions were journaled): next completion %s; within 0.5 ms: %.1f %%'
          % (dist(base), 100.0 * sum(1 for x in base if x <= 0.5) / len(base) if base else float('nan')))
    print()
    print('# per label (given up and served together): flips, with none in flight, with a completion within 0.5 ms after')
    per = defaultdict(list)
    for f in flips:
        per[f[1]].append(f)
    for label, fs in sorted(per.items(), key=lambda kv: -len(kv[1])):
        print('  %-14s %5d %5d %5d   next completion %s' % (label, len(fs), sum(1 for f in fs if f[2] == 0), sum(1 for f in fs if f[3] is not None and f[3] <= 0.5),
                                                           dist([f[3] for f in fs if f[3] is not None])))


main()
