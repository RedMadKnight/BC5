#!/usr/bin/env python3
# What the threads wait on: every INTERVAL seconds reads, for every thread of kyty_emulator
# (and of bc5-mount, the FUSE process), its state, wchan and the syscall it is blocked in, and
# writes one JSON line per WINDOW seconds: per thread, counts of "state|wchan|syscall" and the
# CPU seconds used. Reads /proc only; no root. Runs until the emulator exits.
import json, os, sys, time
INTERVAL = float(sys.argv[1]) if len(sys.argv) > 1 else 0.2
WINDOW = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
out_path = sys.argv[3] if len(sys.argv) > 3 else os.path.expanduser("~/bc5-work/waits-%s.jsonl" % time.strftime("%Y%m%d-%H%M%S"))
HZ = os.sysconf("SC_CLK_TCK")

def find_pids(comm_wanted):
    res = {}
    for d in os.listdir("/proc"):
        if not d.isdigit(): continue
        try:
            with open("/proc/%s/comm" % d) as f: c = f.read().strip()
        except OSError: continue
        if c in comm_wanted and c not in res: res[c] = int(d)
    return res

def read_small(path):
    try:
        with open(path) as f: return f.read().strip()
    except OSError: return ""

def sample(pid):
    base = "/proc/%d/task" % pid
    try: tids = os.listdir(base)
    except OSError: return None
    res = {}
    for t in tids:
        st = read_small("%s/%s/stat" % (base, t))
        if not st: continue
        lp, rp = st.index("("), st.rindex(")")
        name = st[lp + 1:rp]; fields = st[rp + 2:].split()
        state = fields[0]; cpu = (int(fields[11]) + int(fields[12])) / HZ
        key = "R" if state == "R" else state
        if state != "R":
            wchan = read_small("%s/%s/wchan" % (base, t)) or "?"
            sc = read_small("%s/%s/syscall" % (base, t)).split(" ")[0]
            key = "%s|%s|%s" % (state, wchan, sc)
        res[int(t)] = (name, key, cpu)
    return res

print("wait sampler: waiting for kyty_emulator, writing", out_path, flush=True)
pids = {}
while "kyty_emulator" not in pids:
    pids = find_pids({"kyty_emulator", "bc5-mount"}); time.sleep(0.5)
print("wait sampler: pids", pids, flush=True)
start = time.time()
with open(out_path, "w") as out:
    out.write(json.dumps({"start": start, "pids": pids, "interval": INTERVAL, "window": WINDOW}) + "\n")
    acc = {}      # (proc, tid) -> {"name":..., "keys": {key: n}, "cpu0": cpu, "cpu1": cpu}
    win_start = start
    while True:
        now = time.time()
        gone = False
        for comm, pid in pids.items():
            s = sample(pid)
            if s is None:
                if comm == "kyty_emulator": gone = True
                continue
            for tid, (name, key, cpu) in s.items():
                a = acc.setdefault((comm, tid), {"name": name, "keys": {}, "cpu0": cpu, "cpu1": cpu})
                a["name"] = name; a["keys"][key] = a["keys"].get(key, 0) + 1; a["cpu1"] = cpu
        if now - win_start >= WINDOW or gone:
            io = {}
            for comm, pid in pids.items():
                for line in read_small("/proc/%d/io" % pid).splitlines():
                    k, _, v = line.partition(":")
                    if k in ("rchar", "wchar", "read_bytes"): io["%s.%s" % (comm, k)] = int(v.strip() or 0)
            threads = []
            for (comm, tid), a in acc.items():
                n = sum(a["keys"].values())
                top = sorted(a["keys"].items(), key=lambda kv: -kv[1])[:6]
                threads.append({"proc": comm, "tid": tid, "name": a["name"], "samples": n, "cpu": round(a["cpu1"] - a["cpu0"], 3), "top": top})
            threads.sort(key=lambda t: -t["cpu"])
            out.write(json.dumps({"t": round(now - start, 2), "dt": round(now - win_start, 2), "io": io, "threads": threads}) + "\n"); out.flush()
            acc = {}; win_start = now
        if gone:
            print("wait sampler: emulator gone", flush=True); break
        time.sleep(max(0.0, INTERVAL - (time.time() - now)))
