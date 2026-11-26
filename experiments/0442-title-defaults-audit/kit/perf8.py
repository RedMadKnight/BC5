import sys, glob, os, re, collections
# perf stat -x, --per-thread output: <comm-tid>,<value>,<unit>,<event>,<run time>,<pct>,...
d = sys.argv[1]
EV = ["task-clock:u", "cycles:u", "instructions:u", "branch-misses:u", "L1-icache-load-misses:u", "iTLB-load-misses:u"]
runs = []
for f in sorted(glob.glob(os.path.join(d, "perf-*.csv"))):
    lines = open(f, encoding="utf-8", errors="replace").read().splitlines()
    head = lines[0]
    m = re.search(r"md5 (\w+) start (\S+)", head)
    md5, start = (m.group(1), m.group(2)) if m else ("?", "?")
    tot = collections.Counter()
    by = collections.defaultdict(collections.Counter)
    for ln in lines[1:]:
        if ln.startswith("#") or "," not in ln:
            continue
        p = ln.split(",")
        if len(p) < 4 or p[3] not in EV:
            continue
        try:
            v = float(p[1])
        except ValueError:
            continue
        comm = re.sub(r"-\d+$", "", p[0])
        tot[p[3]] += v
        by[comm][p[3]] += v
    runs.append((start, md5, f, tot, by))
arm = {"05fd749d": "C", "b0f856ed": "N"}
print("run start md5 arm | task-clock s | Gcycles | Ginstr | IPC | br-miss/kI | L1i-miss/kI | iTLB-miss/kI")
for start, md5, f, t, by in runs:
    i = t["instructions:u"] or 1
    print(f"{start} {md5} {arm.get(md5, '?')} | {t['task-clock:u']/1000:.1f} | {t['cycles:u']/1e9:.2f} | {i/1e9:.2f} | {i/(t['cycles:u'] or 1):.3f} | "
          f"{t['branch-misses:u']/i*1000:.3f} | {t['L1-icache-load-misses:u']/i*1000:.3f} | {t['iTLB-load-misses:u']/i*1000:.4f}")
# per thread name: mean per arm (excluding the first run, the warm-up), top 8 by cycles
agg = {a: collections.defaultdict(collections.Counter) for a in "CN"}
cnt = collections.Counter()
for k, (start, md5, f, t, by) in enumerate(runs):
    a = arm.get(md5)
    if k == 0 or a is None:
        continue
    cnt[a] += 1
    for comm, c in by.items():
        agg[a][comm].update(c)
names = sorted(set(agg["C"]) | set(agg["N"]), key=lambda n: -(agg["C"][n]["cycles:u"] + agg["N"][n]["cycles:u"]))[:10]
print("\nthread | C Gcyc | N Gcyc | C Ginstr | N Ginstr | C IPC | N IPC | C L1i/kI | N L1i/kI  (means over the measured runs)")
for n in names:
    c, nn = agg["C"][n], agg["N"][n]
    kc, kn = max(cnt["C"], 1), max(cnt["N"], 1)
    ic, inn = c["instructions:u"] or 1, nn["instructions:u"] or 1
    print(f"{n[:22]:22} | {c['cycles:u']/kc/1e9:.2f} | {nn['cycles:u']/kn/1e9:.2f} | {c['instructions:u']/kc/1e9:.2f} | {nn['instructions:u']/kn/1e9:.2f} | "
          f"{ic/(c['cycles:u'] or 1):.3f} | {inn/(nn['cycles:u'] or 1):.3f} | {c['L1-icache-load-misses:u']/ic*1000:.3f} | {nn['L1-icache-load-misses:u']/inn*1000:.3f}")
