#!/usr/bin/env python3
# BC5 exp 0415, part 2 (build L5, tag fs415b): the GPU's time line of whole windows of frames, from a
# KYTY_BC5_FRAME_STAT file that holds EVERY job of the window (J lines) with the host's stamps and, with
# BC5_DIRECT_JOB_TS=1, the GPU's own start and end stamps. Laptop, offline.
#   f <frame> <flip called ns> <flip returned ns>
#   J <frame> <n> <kind> <ring> <title dw> <filter dw> <packets> <dropped> <BOs> <prepare ms> <list ms> <cs ms>
#     <submit_now entered> <mutex asked> <mutex got> <queued> <fence seen> <gpu start> <gpu end> <a|s>
# What it does, and what it checks before it says anything about gaps:
#   - windows are runs of consecutive frame numbers with J lines; a window's first and last two frames are dropped
#     (their jobs may lie outside the recorded set);
#   - COVERAGE: jobs without GPU stamps, jobs on other rings than the GFX ring, job numbers missing inside a window,
#     and jobs whose GPU interval overlaps the one before on the same ring are counted and printed first. With any
#     of these above 1 % of the jobs the gap table is printed with a warning line;
#   - the GPU's clock is put on the host's clock per window by the smallest (fence seen - GPU end) of its jobs, so a
#     GPU time on the host clock is late by at most that job's fence latency (printed);
#   - a frame is flip returned to flip returned; its jobs are those whose GPU interval overlaps it; busy is the
#     union of their intervals inside the frame; each gap between two busy stretches is split by the NEXT job's host
#     stamps: before submit_now was entered (the title, or the host's chain, had not handed it over), entered to
#     mutex asked (the in-flight cap and what precedes the lock), asked to got (waiting for the device mutex), got to
#     queued (the host's work under the mutex: sync, prepare, the CS ioctl), queued to GPU start (in the kernel: the
#     scheduler, another client's job, a ring switch). The stretch after the frame's last job is "after the last job".
# Other processes use the same GPU ring (the compositor): a gap is time in which none of OUR jobs ran, not proof of
# an idle GPU; the collector's fdinfo rows of the other clients say how much they used.
# usage: frame0415b.py <file> [from s] [to s]     (seconds after the first flip line)
import statistics as st
import sys

CLASSES = ('not handed over yet', 'before the mutex', 'waiting for the mutex', 'host work under the mutex', 'in the kernel', 'after the last job')


def main():
    path = sys.argv[1]
    lo = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    hi = float(sys.argv[3]) if len(sys.argv) > 3 else 1e18
    flips, jobs = {}, {}
    for line in open(path, encoding='utf-8', errors='replace'):
        p = line.split()
        if len(p) == 4 and p[0] == 'f':
            flips[int(p[1])] = (int(p[2]), int(p[3]))
        elif len(p) == 21 and p[0] == 'J':
            n = int(p[2])
            jobs[n] = dict(frame=int(p[1]), n=n, kind=p[3], ring=int(p[4]), dw=int(p[5]), packets=int(p[7]), dropped=int(p[8]), sub=int(p[13]), ask=int(p[14]),
                           got=int(p[15]), q=int(p[16]), done=int(p[17]), g0=int(p[18]), g1=int(p[19]), how=p[20])
    if len(flips) < 8 or not jobs:
        print('%s: %d flip lines, %d job lines: not enough' % (path, len(flips), len(jobs)))
        return 1
    t0 = min(v[1] for v in flips.values())
    fr = sorted({j['frame'] for j in jobs.values()})
    windows, cur = [], [fr[0]]
    for f in fr[1:]:
        if f == cur[-1] + 1:
            cur.append(f)
        else:
            windows.append(cur)
            cur = [f]
    windows.append(cur)
    tot = dict(frames=0, long=0)
    rows, rows_long, cov = [], [], dict(jobs=0, nostamp=0, otherring=0, missing=0, overlap=0, sync=0)
    lat = []
    for w in windows:
        if len(w) < 8:
            continue
        inner = [f for f in w[2:-2] if f in flips and f - 1 in flips and lo <= (flips[f][1] - t0) / 1e9 < hi]
        if not inner:
            continue
        wj = sorted((j for j in jobs.values() if w[0] <= j['frame'] <= w[-1]), key=lambda j: j['n'])
        cov['jobs'] += len(wj)
        cov['missing'] += (wj[-1]['n'] - wj[0]['n'] + 1) - len(wj)
        cov['sync'] += sum(1 for j in wj if j['how'] == 's')
        cov['otherring'] += sum(1 for j in wj if j['ring'] != -1)
        st_j = [j for j in wj if j['g0'] != 0 and j['g1'] > j['g0']]
        cov['nostamp'] += len(wj) - len(st_j)
        if len(st_j) < 4:
            continue
        off = min(j['done'] - j['g1'] * 10 for j in st_j)
        lat.extend((j['done'] - j['g1'] * 10 - off) / 1e6 for j in st_j)
        for j in st_j:
            j['h0'], j['h1'] = j['g0'] * 10 + off, j['g1'] * 10 + off
        by_start = sorted(st_j, key=lambda j: j['h0'])
        for a, b in zip(by_start, by_start[1:]):
            if a['ring'] == b['ring'] and b['h0'] < a['h1']:
                cov['overlap'] += 1
        for f in inner:
            fa, fb = flips[f - 1][1], flips[f][1]
            js = [j for j in by_start if j['h1'] > fa and j['h0'] < fb]
            row = dict(ms=(fb - fa) / 1e6, jobs=len(js), busy=0.0, called=(flips[f][0] - fa) / 1e6)
            for c in CLASSES:
                row[c] = 0.0
            end = fa
            for j in js:
                s, e = max(j['h0'], fa), min(j['h1'], fb)
                if s > end:
                    g0, g1 = end, s
                    marks = [(j['sub'], CLASSES[0]), (j['ask'], CLASSES[1]), (j['got'], CLASSES[2]), (j['q'], CLASSES[3])]
                    pos = g0
                    for t, name in marks:
                        t = min(max(t, g0), g1) if t != 0 else pos
                        if t > pos:
                            row[name] += (t - pos) / 1e6
                            pos = t
                    if g1 > pos:
                        row[CLASSES[4]] += (g1 - pos) / 1e6
                if e > end:
                    row['busy'] += (e - max(s, end)) / 1e6
                    end = e
            if fb > end:
                row[CLASSES[5]] += (fb - end) / 1e6
            tot['frames'] += 1
            (rows_long if row['ms'] > 50 else rows).append(row)
            if row['ms'] > 50:
                tot['long'] += 1
    if not rows and not rows_long:
        print('no complete window in the range')
        return 1
    print('%s: %d windows, %d inner frames (%d over 50 ms); jobs in the windows %d' % (path, len(windows), tot['frames'], tot['long'], cov['jobs']))
    print('COVERAGE: without GPU stamps %d (%.1f %%), completed by the submitter %d, on a compute ring %d, job numbers missing inside a window %d, GPU intervals overlapping the one before %d' % (
        cov['nostamp'], 100.0 * cov['nostamp'] / max(1, cov['jobs']), cov['sync'], cov['otherring'], cov['missing'], cov['overlap']))
    bad = max(cov['nostamp'], cov['missing'], cov['overlap'], cov['otherring']) > 0.01 * cov['jobs']
    if bad:
        print('WARNING: coverage is not complete (over 1 % of the jobs in one of the counts above): the gap table below does not account for every job')
    if lat:
        print('clock: fence seen after the GPU end by median %.3f ms, p90 %.3f ms beyond the window\'s smallest (the error of every GPU time on the host clock)' % (st.median(lat), sorted(lat)[int(len(lat) * 0.9)]))
    for name, rr in (('frames up to 50 ms', rows), ('frames over 50 ms', rows_long)):
        if not rr:
            continue
        print('%s: %d; median frame %.1f ms, flip called at %.1f ms, jobs %d; mean per frame, ms:' % (name, len(rr), st.median(r['ms'] for r in rr), st.median(r['called'] for r in rr), st.median(r['jobs'] for r in rr)))
        print('   %-28s %7.2f  (%4.1f %%)' % ('our jobs on the GPU', st.mean(r['busy'] for r in rr), 100 * sum(r['busy'] for r in rr) / sum(r['ms'] for r in rr)))
        for c in CLASSES:
            print('   gap: %-23s %7.2f  (%4.1f %%)' % (c, st.mean(r[c] for r in rr), 100 * sum(r[c] for r in rr) / sum(r['ms'] for r in rr)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
