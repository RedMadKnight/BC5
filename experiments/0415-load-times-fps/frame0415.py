#!/usr/bin/env python3
# BC5 exp 0415, part 2: read a KYTY_BC5_FRAME_STAT file (build L4) and say where the GPU's time of the sampled frames
# went. Laptop, offline.
#   f <frame> <mono ns>                                   one per flip
#   j <frame> <n> <kind> <ring> <title dwords> <filter dwords> <packets> <dropped> <BOs> <prepare ms> <list ms>
#     <cs ms> <queued ns> <fence seen ns> <gpu start> <gpu end>      for two frames in sixteen; GPU stamps in 10 ns units,
#     0 when BC5_DIRECT_JOB_TS was not set
# Prints, for the flips inside [from, to) seconds after the first flip: frames and their length; per sampled frame the
# jobs, the GPU's busy time (the union of the jobs' own stamps), its idle time between jobs; and per signature (kind,
# ring, title dwords rounded to 64) the jobs per frame, the median and summed GPU ms and the share. Without GPU stamps
# only the host's side is printed (queued to fence), marked as such. A value that is not there is "-".
# usage: frame0415.py <file> [from s] [to s]
import statistics as st
import sys


def main():
    path = sys.argv[1]
    lo = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    hi = float(sys.argv[3]) if len(sys.argv) > 3 else 1e18
    flips, jobs = [], {}
    for line in open(path, encoding='utf-8', errors='replace'):
        p = line.split()
        if len(p) == 3 and p[0] == 'f':
            flips.append((int(p[1]), int(p[2])))
        elif len(p) == 17 and p[0] == 'j':
            jobs.setdefault(int(p[1]), []).append(dict(n=int(p[2]), kind=p[3], ring=int(p[4]), dw=int(p[5]), fdw=int(p[6]), packets=int(p[7]), dropped=int(p[8]),
                                                       bos=int(p[9]), prep=float(p[10]), lst=float(p[11]), cs=float(p[12]), q=int(p[13]), done=int(p[14]),
                                                       g0=int(p[15]), g1=int(p[16])))
    if len(flips) < 3:
        print('%s: %d flip lines: not enough' % (path, len(flips)))
        return 1
    t0 = flips[0][1]
    sel = [(f, t) for f, t in flips if lo <= (t - t0) / 1e9 < hi]
    lens = [(sel[i][1] - sel[i - 1][1]) / 1e6 for i in range(1, len(sel))]
    if not lens:
        print('no flips in the window')
        return 1
    print('%s: %d flips in %.0f-%.0f s; frame ms median %.1f, p90 %.1f, over 50 ms: %d, over 100 ms: %d' % (
        path, len(sel), (sel[0][1] - t0) / 1e9, (sel[-1][1] - t0) / 1e9, st.median(lens), sorted(lens)[int(len(lens) * 0.9)], sum(1 for x in lens if x > 50), sum(1 for x in lens if x > 100)))
    frames = [f for f, _ in sel if f in jobs]
    all_jobs = [j for f in frames for j in jobs[f]]
    if not all_jobs:
        print('no job lines in the window')
        return 1
    stamped = [j for j in all_jobs if j['g0'] != 0 and j['g1'] > j['g0']]
    print('sampled frames %d, jobs %d (%.1f a frame), with GPU stamps %d' % (len(frames), len(all_jobs), len(all_jobs) / len(frames), len(stamped)))
    print('host side per job: prepare %.3f ms, BO list %.3f, CS %.3f; BOs median %d; queued to fence seen median %.2f ms' % (
        st.mean(j['prep'] for j in all_jobs), st.mean(j['lst'] for j in all_jobs), st.mean(j['cs'] for j in all_jobs), st.median(j['bos'] for j in all_jobs),
        st.median((j['done'] - j['q']) / 1e6 for j in all_jobs)))
    use_gpu = len(stamped) > len(all_jobs) // 2

    def cost(j):
        return (j['g1'] - j['g0']) / 1e5 if use_gpu else (j['done'] - j['q']) / 1e6
    if use_gpu:
        busy, idle = [], []
        for f in frames:
            js = sorted((j for j in jobs[f] if j['g0'] != 0 and j['g1'] > j['g0']), key=lambda j: j['g0'])
            b = i = 0
            end = None
            for j in js:
                if end is None or j['g0'] >= end:
                    if end is not None:
                        i += j['g0'] - end
                    b += j['g1'] - j['g0']
                    end = j['g1']
                elif j['g1'] > end:
                    b += j['g1'] - end
                    end = j['g1']
            busy.append(b / 1e5)
            idle.append(i / 1e5)
        print('per completion group (jobs whose fence was seen in one sampled frame number): stamps cover median %.1f ms, gaps between the RECORDED jobs median %.1f ms (not shown to be idle GPU: a subset, grouped by host completion, no coverage check)' % (st.median(busy), st.median(idle)))
    else:
        print('NO GPU stamps: the table below is queued-to-fence time on the host clock, which overlaps between jobs; not GPU time')
    sig = {}
    for j in all_jobs:
        if use_gpu and not (j['g0'] != 0 and j['g1'] > j['g0']):
            continue
        k = (j['kind'], j['ring'], (j['dw'] + 32) // 64 * 64)
        sig.setdefault(k, []).append(cost(j))
    total = sum(sum(v) for v in sig.values())
    print('signature (kind, ring, title dwords ~64) | jobs a frame | median ms | sum ms a frame | share')
    for k, v in sorted(sig.items(), key=lambda kv: -sum(kv[1]))[:40]:
        print('%-4s ring %d %7d dw | %5.2f | %7.3f | %7.3f | %4.1f %%' % (k[0], k[1], k[2], len(v) / len(frames), st.median(v), sum(v) / len(frames), 100 * sum(v) / total))
    return 0


if __name__ == '__main__':
    sys.exit(main())
