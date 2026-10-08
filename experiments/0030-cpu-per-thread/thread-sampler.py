#!/usr/bin/env python3
# Per-thread CPU sampler for kyty_emulator: waits for the process, then every INTERVAL seconds
# writes one JSON line with the wall clock, the process's total CPU seconds and, per thread,
# name and CPU seconds (user+system) used in the interval. Reads /proc, no tools needed.
import json, os, sys, time
INTERVAL = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser("~/bc5-work/threads-%s.jsonl" % time.strftime("%Y%m%d-%H%M%S"))
HZ = os.sysconf("SC_CLK_TCK")

def find_pid():
    for d in os.listdir("/proc"):
        if not d.isdigit(): continue
        try:
            with open("/proc/%s/comm" % d) as f:
                if f.read().strip() == "kyty_emulator": return int(d)
        except OSError: pass
    return None

def read_threads(pid):
    res = {}
    base = "/proc/%d/task" % pid
    try: tids = os.listdir(base)
    except OSError: return None
    for t in tids:
        try:
            with open("%s/%s/stat" % (base, t)) as f: st = f.read()
        except OSError: continue
        # comm is in parentheses and may contain spaces
        lp, rp = st.index("("), st.rindex(")")
        name = st[lp + 1:rp]
        fields = st[rp + 2:].split()
        utime, stime = int(fields[11]), int(fields[12])
        res[int(t)] = (name, (utime + stime) / HZ)
    return res

print("sampler: waiting for kyty_emulator, writing", out_path, flush=True)
pid = None
while pid is None:
    pid = find_pid(); time.sleep(0.5)
print("sampler: pid", pid, flush=True)
prev = read_threads(pid); prev_t = time.time()
with open(out_path, "w") as out:
    out.write(json.dumps({"start": prev_t, "pid": pid}) + "\n")
    while True:
        time.sleep(INTERVAL)
        cur = read_threads(pid)
        if cur is None:
            print("sampler: process gone", flush=True); break
        now = time.time()
        threads = []
        for tid, (name, cpu) in cur.items():
            d = cpu - prev.get(tid, (name, 0.0))[1]
            if d > 0.0005: threads.append([tid, name, round(d, 3)])
        threads.sort(key=lambda x: -x[2])
        out.write(json.dumps({"t": round(now, 2), "dt": round(now - prev_t, 2), "total": round(sum(x[2] for x in threads), 3), "n": len(cur), "threads": threads}) + "\n")
        out.flush()
        prev, prev_t = cur, now
