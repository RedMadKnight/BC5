#!/usr/bin/env python3
# BC5 experiment 0226: the A/B of the held tail. For each run (its tag, arm, extract and emulator log from
# run0226.sh), the numbers the comparison reads:
#   - give-ups: "cpu-wait ... GIVEN UP" lines (today's path), "two rings ... NOT served" lines, and the holds given up
#     at the bound ("hold tail: the wait on ... GIVEN UP");
#   - holds: the last "hold tail: N holds; released ..." summary (arm B only);
#   - fence timeouts in the journal ("TIMEOUT");
#   - frames from the emulator log's "fps counter: t T s: N flips in S s, longest gap G ms" lines over a window of
#     journal time (default t 150-590 s, the frozen view): flips per second, and the seconds whose longest gap is over
#     100 ms and over 250 ms.
# Then the arms side by side (the runs of each arm, and their mean).
# usage: ab0226.py <raw dir> <tag>... [--window t0:t1]
import os, re, sys

FPS = re.compile(r'fps counter: t ([0-9.]+) s: (\d+) flips in ([0-9.]+) s, longest gap ([0-9.]+) ms')
SUMMARY = re.compile(r'^hold tail: (\d+) holds; released with the writer on a ring (\d+), satisfied (\d+), GIVEN UP (\d+); held ([0-9.]+) ms on average, ([0-9.]+) ms at most')


def frames(path, t0, t1):
    n = flips = secs = g100 = g250 = 0
    for line in open(path, errors='replace'):
        m = FPS.search(line)
        if not m:
            continue
        t = float(m.group(1))
        if t < t0 or t > t1:
            continue
        n += 1
        flips += int(m.group(2))
        secs += float(m.group(3))
        gap = float(m.group(4))
        g100 += gap > 100.0
        g250 += gap > 250.0
    return dict(samples=n, fps=flips / secs if secs else float('nan'), g100=g100, g250=g250)


PROF = re.compile(r'^frame profile: t ([0-9.]+) s, ([0-9.]+) ms since the last flip; game thread inside the host ([0-9.]+) ms \(.*label waits ([0-9.]+),.*\), at the flip ([0-9.]+), outside ([0-9.]+);')


def profile(path, t0, t1):
    """The journal's per-frame profile lines in the window: means of the frame, the game thread inside the host, its
    label waits, its wait at the flip and its time outside the host; and the frames over 100 ms."""
    n = 0
    s = [0.0] * 5
    over = 0
    for line in open(path, errors='replace'):
        m = PROF.match(line)
        if not m or not (t0 <= float(m.group(1)) <= t1):
            continue
        v = [float(m.group(k)) for k in (2, 3, 4, 5, 6)]
        n += 1
        s = [a + b for a, b in zip(s, v)]
        over += v[0] > 100.0
    return dict(frames=n, mean=[x / n for x in s] if n else [float('nan')] * 5, over=over)


def journal(path):
    d = dict(cpu_given_up=0, not_served=0, hold_given_up=0, timeouts=0, summary=None)
    for line in open(path, errors='replace'):
        if line.startswith('cpu-wait ') and 'GIVEN UP' in line:
            d['cpu_given_up'] += 1
        elif line.startswith('two rings') and 'NOT served' in line:
            d['not_served'] += 1
        elif line.startswith('hold tail: the wait on ') and 'GIVEN UP' in line:
            d['hold_given_up'] += 1
        elif 'TIMEOUT' in line and not line.startswith('hold tail'):
            d['timeouts'] += 1
        m = SUMMARY.match(line)
        if m:
            d['summary'] = tuple(float(x) for x in m.groups())
    return d


def main():
    args = sys.argv[1:]
    t0, t1 = 150.0, 590.0
    if '--window' in args:
        k = args.index('--window')
        t0, t1 = (float(x) for x in args[k + 1].split(':'))
        del args[k:k + 2]
    raw, tags = args[0], args[1:]
    rows = []
    for tag in tags:
        arm = open(os.path.join(raw, tag + '-arm.txt')).read().strip() if os.path.exists(os.path.join(raw, tag + '-arm.txt')) else '?'
        j = journal(os.path.join(raw, tag + '-extract.txt'))
        f = frames(os.path.join(raw, tag + '-emu.log'), t0, t1)
        f['prof'] = profile(os.path.join(raw, tag + '-extract.txt'), t0, t1)
        rows.append((tag, arm, j, f))
    print('# window t %.0f-%.0f s' % (t0, t1))
    print('%-8s %-3s %10s %10s %10s %8s | %8s %8s %6s %6s | %s' % ('run', 'arm', 'cpu-given', 'not-served', 'hold-given', 'timeouts', 'seconds', 'flips/s', '>100ms', '>250ms', 'holds (writer/satisfied/given up; mean/max ms)'))
    for tag, arm, j, f in rows:
        s = j['summary']
        hs = '%d (%d/%d/%d; %.2f/%.1f)' % s if s else '-'
        print('%-8s %-3s %10d %10d %10d %8d | %8d %8.1f %6d %6d | %s' % (tag, arm, j['cpu_given_up'], j['not_served'], j['hold_given_up'], j['timeouts'], f['samples'], f['fps'], f['g100'], f['g250'], hs))
    print()
    print('# frame profile (journal), means per frame in ms: frame, game thread inside the host, of it label waits, at the flip, outside; frames over 100 ms')
    for tag, arm, j, f in rows:
        p = f['prof']
        print('%-8s %-3s %6d frames: %6.1f %6.2f %6.2f %6.2f %6.2f; over 100 ms %d' % ((tag, arm, p['frames']) + tuple(p['mean']) + (p['over'],)))
    print()
    for arm in ('A', 'B'):
        rs = [r for r in rows if r[1] == arm]
        if not rs:
            continue
        mean = lambda xs: sum(xs) / len(xs) if xs else float('nan')
        print('arm %s, %d runs: give-ups %.1f (cpu %.1f, hold %.1f), flips/s %.2f, seconds with a gap over 100 ms %.1f, over 250 ms %.1f, fence timeouts %d' % (
            arm, len(rs), mean([r[2]['cpu_given_up'] + r[2]['hold_given_up'] for r in rs]), mean([r[2]['cpu_given_up'] for r in rs]), mean([r[2]['hold_given_up'] for r in rs]),
            mean([r[3]['fps'] for r in rs]), mean([r[3]['g100'] for r in rs]), mean([r[3]['g250'] for r in rs]), sum(r[2]['timeouts'] for r in rs)))


main()
