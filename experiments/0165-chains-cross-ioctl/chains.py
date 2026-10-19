#!/usr/bin/env python3
# exp 0165 (as 0163's chains.py, with the dwords per submission by kind): one run's measurement from its files — flips per second (KYTY_BC5_VIDEOOUT_TRACE), the
# per-thread CPU of cpu-sampler.sh, and from the direct journal the submissions per second
# ("timing: t ... kind N dwords" lines, one per kernel submission), the chain statistics, CPU-side
# waits and failures. Usage: chains.py <stderr log> <cpu file> <direct.log> <t0> <t1>
import re, sys, collections, statistics

stderr, cpu, journal, t0, t1 = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5])

flips = []
rx_vo = re.compile(r"videoout trace: t ([0-9.]+) s: flips mode0 (\d+) mode1 (\d+) mode2 (\d+) mode3 (\d+),.* in ([0-9.]+) s")
for line in open(stderr, encoding="latin1"):
    m = rx_vo.search(line)
    if m:
        t = float(m.group(1))
        if t0 <= t < t1:
            flips.append(sum(int(m.group(k)) for k in (2, 3, 4, 5)) / float(m.group(6)))

threads = collections.defaultdict(list)
rx_thr = re.compile(r"([A-Za-z][A-Za-z0-9 :_.-]*?)=(\d+)%")
n_cpu = 0
for line in open(cpu, encoding="latin1"):
    if not line.startswith("=="):
        continue
    n_cpu += 1
    for name, pct in rx_thr.findall(line.split(":", 3)[-1] if "MiB:" in line else line):
        threads[name.strip()].append(int(pct))

per = collections.defaultdict(lambda: dict(subs=0, dwords=0, kinds=collections.Counter(), kind_dwords=collections.Counter(), waits=0, given_up=0))
chain_lines, failures, drops = [], [], []
rx_sub = re.compile(r"^timing: t ([0-9.]+) s (\w+) (\d+) dwords: sync")
rx_wait = re.compile(r"^cpu-wait .* after ([0-9.]+) ms")
rx_wait_t = re.compile(r"^timing: t ([0-9.]+) s after that wait")
last_t = 0.0
for raw in open(journal, "rb"):
    line = raw.decode("latin1")
    m = rx_sub.match(line)
    if m:
        last_t = float(m.group(1))
        if t0 <= last_t < t1:
            b = per[int(last_t)]
            b["subs"] += 1
            b["dwords"] += int(m.group(3))
            b["kinds"][m.group(2)] += 1
            b["kind_dwords"][m.group(2)] += int(m.group(3))
        continue
    if line.startswith("chains:"):
        chain_lines.append(line.strip())
        continue
    if line.startswith("cpu-wait") and t0 <= last_t < t1:
        per[int(last_t)]["waits"] += 1
        if "GIVEN UP" in line or "TIMEOUT" in line or "CYCLE" in line:
            per[int(last_t)]["given_up"] += 1
        continue
    if ("FAILED" in line or "TIMEOUT" in line) and line.startswith("submit #"):
        failures.append(line.strip()[:160])
    if line.startswith("drop tally"):
        drops.append(line.strip()[:300])

print("window t %.0f-%.0f s" % (t0, t1))
if flips:
    print("flips/s: n %d mean %.1f median %.1f min %.1f max %.1f" % (len(flips), statistics.mean(flips), statistics.median(flips), min(flips), max(flips)))
else:
    print("flips/s: no trace lines in the window")
print("cpu samples: %d" % n_cpu)
for name in ("Render Thread", "game-main", "bc5-ring", "bc5-cq0", "bc5-cq1", "kyty-gpu"):
    v = threads.get(name)
    if v:
        print("  %-14s mean %5.1f%%  median %5.1f%%  max %3d%%  (n %d)" % (name, statistics.mean(v), statistics.median(v), max(v), len(v)))
secs = sorted(per)
if secs:
    subs = [per[s]["subs"] for s in secs]
    dw = [per[s]["dwords"] for s in secs]
    kinds = collections.Counter()
    for s in secs:
        kinds.update(per[s]["kinds"])
    print("submissions/s: mean %.0f median %.0f min %d max %d; dwords/s mean %.0f; kinds %s" % (statistics.mean(subs), statistics.median(subs), min(subs), max(subs), statistics.mean(dw), dict(kinds)))
    kd = collections.Counter()
    for s in secs:
        kd.update(per[s]["kind_dwords"])
    print("dwords per submission by kind: %s" % {k: round(kd[k] / kinds[k]) for k in kinds})
    print("cpu-side waits in the window: %d, of which given up/timed out/cycle: %d" % (sum(per[s]["waits"] for s in secs), sum(per[s]["given_up"] for s in secs)))
print("chain lines: %d" % len(chain_lines))
for l in chain_lines[-3:]:
    print("  " + l)
print("submit failures: %d" % len(failures))
for l in failures[:5]:
    print("  " + l)
if drops:
    print("last drop tally: " + drops[-1])
