#!/usr/bin/env python3
# BC5 exp 0415, part 2 (builds L5a and L5b, tags fs415b and fs415c): the GPU's time line of whole windows of frames,
# from a KYTY_BC5_FRAME_STAT file that holds EVERY job of the window with the host's stamps and, with
# BC5_DIRECT_JOB_TS=1, the GPU's own start and end stamps. Laptop, offline.
#   f <frame> <flip called ns> <flip returned ns>
#   J <frame> <n> <kind> <ring> <title dw> <filter dw> <packets> <dropped> <BOs> <prepare ms> <list ms> <cs ms>
#     <submit_now entered> <mutex asked> <mutex got> <queued> <fence seen> <gpu start> <gpu end> <a|s>        (L5a)
#   K ... the same, then <chain opened ns> <flush reason> <segments> and the ends of submit_now's parts under the
#     mutex: probe, anonymous sync, direct sync, learned windows, hints, before the device call              (L5b)
#   L ... the same, then what the submitting thread spent inside the two syncs (ns): direct_sync_one's views, scan
#     with its imports, merges, drain, mappings; the imports alone; sync_mappings' read of /proc/self/maps; and
#     sync_mappings' flags (1 walked, 2 urgent, 4 left out)                                                 (L5c)
#     A stretch that falls into the direct sync (or the anonymous sync) of an L job is divided among those parts in
#     proportion to their durations in that job: the parts' own stamps are not recorded, so this is a share, not a
#     position. "of which imports" is counted beside the table the same way.
# What it does, and what it checks before it says anything about gaps:
#   - windows are runs of consecutive frame numbers with job lines; a window's first and last two frames are dropped
#     (their jobs may lie outside the recorded set);
#   - COVERAGE: jobs without GPU stamps, jobs on other rings than the GFX ring and job numbers missing inside a window
#     are counted and printed first. With any of these above 1 % of the jobs the gap table is printed with a warning
#     line. Jobs whose start stamp lies before the previous job's end stamp are counted apart (pipelining);
#   - the GPU's clock is put on the host's clock per window by the smallest (fence seen - GPU end) of its jobs;
#   - a frame is flip returned to flip returned; its jobs are those whose GPU interval overlaps it; busy is the
#     union of their intervals inside the frame; each stretch without one of our jobs is split by the NEXT job's host
#     stamps, in their order: before the chain had its first buffer (the title had not handed it over; without a
#     chain: before submit_now), in our chain until submit_now, before the mutex was asked, waiting for the mutex, the
#     parts of submit_now under the mutex (K lines; one class for J lines), the device call, and from "queued" to the
#     GPU start (in the kernel). The stretch after the frame's last job is its own class.
# Other processes use the same GPU ring (the compositor): a stretch without our jobs is not proof of an idle GPU; the
# next job's stamps say why OUR next job was not there.
# usage: frame0415b.py <file> [from s] [to s]     (seconds after the first flip line)
import statistics as st
import sys

PARTS = ('probe', 'anonymous sync', 'direct sync', 'learned windows', 'hints', 'before the device call')
C_TITLE, C_CHAIN, C_PRE, C_WAIT, C_HOST, C_DEV, C_KERN, C_AFTER = (
    'not handed to the host yet', 'in our chain before submit_now', 'before the mutex', 'waiting for the mutex',
    'under the mutex (not split)', 'under the mutex: the device call', 'in the kernel', 'after the last job')
DS = ('views', 'scan and its imports', 'merges', 'drain', 'mappings')
SUB = tuple('  direct sync: ' + d for d in DS) + ('  direct sync: rest', '  direct sync: (of which imports)', '  anonymous sync: the maps read')
CLASSES = (C_TITLE, C_CHAIN, C_PRE, C_WAIT, C_HOST) + tuple('under the mutex: ' + p for p in PARTS) + (C_DEV, C_KERN, C_AFTER)


def main():
    path = sys.argv[1]
    lo = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    hi = float(sys.argv[3]) if len(sys.argv) > 3 else 1e18
    flips, jobs = {}, {}
    for line in open(path, encoding='utf-8', errors='replace'):
        p = line.split()
        if len(p) == 4 and p[0] == 'f':
            flips[int(p[1])] = (int(p[2]), int(p[3]))
        elif (len(p) == 21 and p[0] == 'J') or (len(p) == 30 and p[0] == 'K') or (len(p) == 38 and p[0] == 'L'):
            n = int(p[2])
            j = dict(frame=int(p[1]), n=n, kind=p[3], ring=int(p[4]), dw=int(p[5]), packets=int(p[7]), dropped=int(p[8]), sub=int(p[13]), ask=int(p[14]),
                     got=int(p[15]), q=int(p[16]), done=int(p[17]), g0=int(p[18]), g1=int(p[19]), how=p[20], open=0, why=-1, segs=0, parts=None, ds=None)
            if p[0] == 'L':
                j['ds'] = [int(x) for x in p[30:38]]
            if p[0] in 'KL':
                j['open'], j['why'], j['segs'] = int(p[21]), int(p[22]), int(p[23])
                j['parts'] = [int(x) for x in p[24:30]]
            jobs[n] = j
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
    lat, why, segs = [], {}, []
    anon = dict(jobs=0, walked=0, urgent=0, skipped=0, walk_ms=[], read_ms=[])
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
        for j in wj:
            if j['parts'] is not None:
                why[j['why']] = why.get(j['why'], 0) + 1
                segs.append(j['segs'])
            if j['ds'] is not None:
                fl = j['ds'][7]
                anon['jobs'] += 1
                anon['urgent'] += 1 if fl & 2 else 0
                anon['skipped'] += 1 if fl & 4 else 0
                if fl & 1:
                    anon['walked'] += 1
                    anon['walk_ms'].append((j['parts'][1] - j['parts'][0]) / 1e6)
                    anon['read_ms'].append(j['ds'][6] / 1e6)
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
            for c in CLASSES + SUB:
                row[c] = 0.0
            end = fa
            for j in js:
                s, e = max(j['h0'], fa), min(j['h1'], fb)
                if s > end:
                    g0, g1 = end, s
                    opened = j['open'] if j['open'] != 0 else j['sub']
                    marks = [(opened, C_TITLE), (j['sub'], C_CHAIN), (j['ask'], C_PRE), (j['got'], C_WAIT)]
                    if j['parts'] is not None:
                        marks += [(j['parts'][k], 'under the mutex: ' + PARTS[k]) for k in range(6)]
                        marks.append((j['q'], C_DEV))
                    else:
                        marks.append((j['q'], C_HOST))
                    pos = g0
                    for t, name in marks:
                        t = min(max(t, g0), g1) if t != 0 else pos
                        if t > pos:
                            row[name] += (t - pos) / 1e6
                            if j['ds'] is not None and name == 'under the mutex: direct sync':
                                whole = max(1, j['parts'][2] - j['parts'][1])
                                share = (t - pos) / 1e6 / whole
                                for k in range(5):
                                    row[SUB[k]] += j['ds'][k] * share
                                row[SUB[5]] += max(0, whole - sum(j['ds'][:5])) * share
                                row[SUB[6]] += j['ds'][5] * share
                            if j['ds'] is not None and name == 'under the mutex: anonymous sync':
                                whole = max(1, j['parts'][1] - j['parts'][0])
                                row[SUB[7]] += j['ds'][6] * (t - pos) / 1e6 / whole
                            pos = t
                    if g1 > pos:
                        row[C_KERN] += (g1 - pos) / 1e6
                if e > end:
                    row['busy'] += (e - max(s, end)) / 1e6
                    end = e
            if fb > end:
                row[C_AFTER] += (fb - end) / 1e6
            tot['frames'] += 1
            (rows_long if row['ms'] > 50 else rows).append(row)
            if row['ms'] > 50:
                tot['long'] += 1
    if not rows and not rows_long:
        print('no complete window in the range')
        return 1
    print('%s: %d windows, %d inner frames (%d over 50 ms = %.0f %%); jobs in the windows %d' % (
        path, len(windows), tot['frames'], tot['long'], 100.0 * tot['long'] / max(1, tot['frames']), cov['jobs']))
    print('COVERAGE: without GPU stamps %d (%.1f %%), completed by the submitter %d, on a compute ring %d, job numbers missing inside a window %d' % (
        cov['nostamp'], 100.0 * cov['nostamp'] / max(1, cov['jobs']), cov['sync'], cov['otherring'], cov['missing']))
    print('pipelining: %d jobs (%.0f %%) have their start stamp before the end stamp of the job before (the start is written when the CP reaches the job, the end when its last work leaves the pipeline); busy time is the union' % (
        cov['overlap'], 100.0 * cov['overlap'] / max(1, cov['jobs'])))
    bad = max(cov['nostamp'], cov['missing'], cov['otherring']) > 0.01 * cov['jobs']
    if bad:
        print('WARNING: coverage is not complete (over 1 % of the jobs in one of the counts above): the table below does not account for every job')
    if lat:
        print('clock: the GPU clock is put on the host clock by each window\'s quickest fence; the other fences are seen median %.3f ms, p90 %.3f ms later than that. The mapping is off by the quickest fence\'s own delay, which is not known' % (st.median(lat), sorted(lat)[int(len(lat) * 0.9)]))
    if segs:
        print('chains: segments per job median %d, mean %.1f; flush reasons (chain_submit\'s number: jobs) %s' % (st.median(segs), st.mean(segs), ' '.join('%d:%d' % kv for kv in sorted(why.items()))))
    if anon['jobs']:
        print('anonymous sync (L lines): of %d jobs %d walked, %d left the walk out, %d were urgent calls; a walk took median %.2f ms, max %.2f ms, its maps read median %.2f ms' % (
            anon['jobs'], anon['walked'], anon['skipped'], anon['urgent'], st.median(anon['walk_ms']) if anon['walk_ms'] else 0, max(anon['walk_ms']) if anon['walk_ms'] else 0,
            st.median(anon['read_ms']) if anon['read_ms'] else 0))
    for name, rr in (('frames up to 50 ms', rows), ('frames over 50 ms', rows_long)):
        if not rr:
            continue
        print('%s: %d; median frame %.1f ms, flip called at %.1f ms, jobs %d; mean per frame, ms:' % (name, len(rr), st.median(r['ms'] for r in rr), st.median(r['called'] for r in rr), st.median(r['jobs'] for r in rr)))
        print('   %-42s %7.2f  (%4.1f %%)' % ('our jobs on the GPU', st.mean(r['busy'] for r in rr), 100 * sum(r['busy'] for r in rr) / sum(r['ms'] for r in rr)))
        for c in CLASSES:
            v = st.mean(r[c] for r in rr)
            if v >= 0.005:
                print('   next job %-33s %7.2f  (%4.1f %%)' % (c, v, 100 * sum(r[c] for r in rr) / sum(r['ms'] for r in rr)))
            subs = SUB[:7] if c == 'under the mutex: direct sync' else SUB[7:] if c == 'under the mutex: anonymous sync' else ()
            for q in subs:
                w = st.mean(r[q] for r in rr)
                if w >= 0.005:
                    print('      %-39s %7.2f' % (q.strip(), w))
    return 0


if __name__ == '__main__':
    sys.exit(main())
