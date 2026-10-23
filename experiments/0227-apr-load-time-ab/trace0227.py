#!/usr/bin/env python3
# BC5 experiment 0227: does ASTRO BOT's startup submit APR buffers with several reads (what KYTY_BC5_APR_PARALLEL can
# run in parallel)? From a run's play log with KYTY_BC5_AMM_TRACE=1: the "mono <s> amm trace: submit <cb>: N reads,
# M maps" lines (one per submit) and the "amm trace: read file ... size 0x..." lines (one per executed read; they do not
# name their buffer). Window: from the first submit to <end> seconds after the emulator's start (the startup reads'
# end, load0227.py). Decision rule, fixed before the run: idea (b) is tested only if at least 25 % of the window's reads
# sit in submits with N >= 2. usage: trace0227.py <play log> <emulator start uptime> <end s>
import collections, re, sys

log, start, end = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
SUB = re.compile(r"mono ([0-9.]+) amm trace: submit 0x[0-9a-f]+: (\d+) reads, (\d+) maps")
RD = re.compile(r"mono ([0-9.]+) amm trace: read file 0x[0-9a-f]+ \+0x[0-9a-f]+ size 0x([0-9a-f]+)")
subs, reads = [], []
for line in open(log, encoding="latin-1"):
    m = SUB.search(line)
    if m:
        subs.append((float(m.group(1)) - start, int(m.group(2)), int(m.group(3))))
        continue
    m = RD.search(line)
    if m:
        reads.append((float(m.group(1)) - start, int(m.group(2), 16)))
win = [s for s in subs if s[0] <= end]
print(f"submits: {len(subs)} in all, {len(win)} up to {end:.1f} s after the emulator's start")
if not win:
    sys.exit("no submit in the window: is KYTY_BC5_AMM_TRACE on, and does the title use APR?")
n_reads = sum(s[1] for s in win)
multi = sum(s[1] for s in win if s[1] >= 2)
hist = collections.Counter(min(s[1], 64) for s in win)
print(f"reads in the window's submits: {n_reads}; in submits with >= 2 reads: {multi} ({100.0 * multi / max(n_reads, 1):.0f} %)")
print("reads per submit (count of submits): " + ", ".join(f"{k if k < 64 else '64+'}: {v}" for k, v in sorted(hist.items())))
rw = [r for r in reads if r[0] <= end]
if rw:
    sizes = sorted(r[1] for r in rw)
    tot = sum(sizes)
    print(f"executed reads up to {end:.1f} s: {len(rw)}, {tot / 1048576:.0f} MiB; size median {sizes[len(sizes) // 2] / 1024:.0f} KiB, "
          f"p90 {sizes[int(0.9 * len(sizes))] / 1024:.0f} KiB, max {sizes[-1] / 1048576:.1f} MiB")
bins = collections.defaultdict(lambda: [0, 0, 0])
for t, n, _ in win:
    b = int(t // 5) * 5
    bins[b][0] += 1
    bins[b][1] += n
    bins[b][2] += n if n >= 2 else 0
print("per 5 s (submits/reads/reads in multi-read submits): " + " ".join(f"{b}:{v[0]}/{v[1]}/{v[2]}" for b, v in sorted(bins.items())))
print("DECISION: " + ("test (b): >= 25 % of the reads are in multi-read submits" if multi >= 0.25 * n_reads else "skip (b): under 25 % of the reads are in multi-read submits"))
