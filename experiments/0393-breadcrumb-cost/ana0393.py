#!/usr/bin/env python3
# BC5 exp 0393: the cost per frame of exp 0277's breadcrumbs. Reads each run's frame profile lines in one journal-time
# window, prints a row per run, then each arm against the off arm. A difference counts as resolved only when it is larger
# than the spread of the off runs (README, "Reading rule"). A line that does not parse stops the script.
# usage: python -I ana0393.py <frames dir> <raw dir> [window start s] [window end s]
import glob, os, re, statistics, sys

NUM = r'(-?[\d.]+)'
LINE = re.compile(
    rf'^frame profile: t {NUM} s, {NUM} ms since the last flip; game thread inside the host {NUM} ms '
    rf'\(sync {NUM}, hints {NUM}, prepare {NUM}, list {NUM}, cs {NUM}, fence {NUM}, cap {NUM}, label waits {NUM}, '
    rf'event waits {NUM}\), at the flip {NUM}, outside {NUM}; GPU busy {NUM} ms in {NUM} jobs \(\+{NUM} from the ring '
    rf'thread\); soft-CP passes {NUM} ms in {NUM}, waits polled {NUM} \({NUM} ms, {NUM} timed out\); prepare = filter '
    rf'{NUM} \+ tracker {NUM} \+ cu {NUM} \+ nested {NUM} \+ copy {NUM}\s*$')
NAMES = ('t since inside sync hints prepare list cs fence cap label event flip outside gpu jobs ringjobs softms softn '
         'polled pollms timedout filter tracker cu nested copy').split()
SHOW = ('since', 'gpu', 'inside', 'flip', 'outside', 'label', 'prepare', 'copy', 'filter', 'list', 'cs', 'fence', 'jobs')
BC = re.compile(r'breadcrumbs \(exp 0277\): (\d+) inserted, (\d+) a second; of (\d+) that followed the previous line, '
                r'(\d+) reached and (\d+) done')


def frames(path, lo, hi):
    rows = []
    for k, line in enumerate(open(path, encoding='utf-8', errors='replace'), 1):
        m = LINE.match(line)
        if not m:
            sys.exit(f'{path}:{k}: does not parse: {line[:100]!r}')
        row = dict(zip(NAMES, map(float, m.groups())))
        if lo <= row['t'] < hi:
            rows.append(row)
    return rows


def run_row(rows, lo, hi):
    r = {n: statistics.fmean(x[n] for x in rows) for n in SHOW}
    gaps = sorted(x['since'] for x in rows)
    r['flips'] = len(rows) / (hi - lo)
    r['p99'] = gaps[int(len(gaps) * 0.99)]
    return r


def health(path):
    if not os.path.exists(path):
        return None
    got = [tuple(map(int, m.groups())) for m in map(BC.search, open(path, encoding='utf-8', errors='replace')) if m]
    other = sum(1 for x in open(path, encoding='utf-8', errors='replace') if 'left out of COND_EXEC' in x)
    return got, other


def main():
    fdir, rdir = sys.argv[1:3]
    lo = float(sys.argv[3]) if len(sys.argv) > 3 else 200.0
    hi = float(sys.argv[4]) if len(sys.argv) > 4 else 400.0
    cols = ('flips', 'p99') + SHOW
    runs = {}
    for path in sorted(glob.glob(os.path.join(fdir, '*-frames.txt'))):
        tag = os.path.basename(path)[:-len('-frames.txt')]
        rows = frames(path, lo, hi)
        if not rows:
            sys.exit(f'{tag}: no frame in {lo:.0f}-{hi:.0f} s')
        runs[tag] = run_row(rows, lo, hi)
    print(f'window {lo:.0f}-{hi:.0f} s of journal time; ms per frame unless named')
    print('run  ' + ''.join(f'{c:>9}' for c in cols))
    for tag, r in runs.items():
        print(f'{tag:5}' + ''.join(f'{r[c]:9.2f}' for c in cols))
    arms = {}
    for tag, r in runs.items():
        arms.setdefault(tag[0], []).append(r)
    if 'O' not in arms:
        sys.exit('no off run')
    off = {c: statistics.fmean(r[c] for r in arms['O']) for c in cols}
    spread = {c: max(r[c] for r in arms['O']) - min(r[c] for r in arms['O']) for c in cols}
    print(f'\noff arm, {len(arms["O"])} runs, spread (largest - smallest): ' + ', '.join(f'{c} {spread[c]:.2f}' for c in cols))
    for a in sorted(arms):
        if a == 'O':
            continue
        print(f'\narm {a}, {len(arms[a])} runs, minus off:')
        for c in cols:
            d = statistics.fmean(r[c] for r in arms[a]) - off[c]
            pct = 100 * d / off[c] if off[c] else 0.0
            print(f'  {c:8} {d:+8.2f} ({pct:+5.1f} %) {"resolved" if abs(d) > spread[c] + 1e-9 else "inside the off spread"}')
    print()
    for tag in runs:
        h = health(os.path.join(rdir, f'{tag}-bc.txt'))
        if tag[0] == 'O' or h is None:
            continue
        got, over = h
        if not got:
            print(f'{tag}: no health lines')
            continue
        rate = statistics.fmean(g[1] for g in got)
        short = sum(1 for g in got if g[3] != g[2] or g[4] != g[2])
        print(f'{tag}: {len(got)} health lines, {rate:.0f} breadcrumbs a second, {got[-1][0]} inserted, '
              f'{short} lines with a sample not reached or not done, {over} COND_EXEC overflow lines')


if __name__ == '__main__':
    main()
