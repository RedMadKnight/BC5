import re, sys, collections
p = sys.argv[1]; t0 = float(sys.argv[2]); t1 = float(sys.argv[3])
rx_start = re.compile(rb"^timing: t ([0-9.]+) s (\w+) (\d+) dwords: sync(?: \(lazy\))? ([0-9.]+) ms, hints ([0-9.]+) ms")
rx_done = re.compile(rb"^timing: #\d+ done at t ([0-9.]+) s, ([0-9.]+) ms after the sync")
rx_split = re.compile(rb"^timing split over (\d+) submissions: (.*)")
rx_wait = re.compile(rb"^timing: t ([0-9.]+) s after that wait \((\w+) (\d+) dwords\)")
per = collections.defaultdict(lambda: dict(n=0, sync=0.0, hints=0.0, after=0.0, dwords=0, kinds=collections.Counter(), waits=0))
splits = []
pend = None
with open(p, "rb") as f:
    for line in f:
        m = rx_start.match(line)
        if m:
            t = float(m.group(1))
            if t0 <= t < t1:
                b = per[int(t)]
                b["n"] += 1; b["sync"] += float(m.group(4)); b["hints"] += float(m.group(5)); b["dwords"] += int(m.group(3)); b["kinds"][m.group(2).decode()] += 1
            continue
        m = rx_done.match(line)
        if m:
            t = float(m.group(1))
            if t0 <= t < t1:
                per[int(t)]["after"] += float(m.group(2))
            continue
        m = rx_wait.match(line)
        if m:
            t = float(m.group(1))
            if t0 <= t < t1:
                per[int(t)]["waits"] += 1
            continue
        m = rx_split.match(line)
        if m and splits is not None:
            splits.append(line.decode("latin1").strip()[:200])
print("sec  subs  dwords   sync+hints ms  after-sync ms  waits  kinds")
for s in sorted(per):
    b = per[s]
    print("%4d %5d %8d %10.1f %12.1f %6d  %s" % (s, b["n"], b["dwords"], b["sync"] + b["hints"], b["after"], b["waits"], dict(b["kinds"])))
print("last split lines:")
for l in splits[-4:]:
    print(l)
