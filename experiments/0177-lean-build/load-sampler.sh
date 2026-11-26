#!/usr/bin/env bash
# BC5 (experiment 0177): once a second while the emulator runs — the whole box's CPU use, the busiest
# processes (bc5-mount, kernel threads, pipewire ... not only the emulator), the NVMe's reads, and the
# emulator's threads over 10 % — keyed by the seconds since the emulator process started (the origin
# of the host's "t" in the fps and audio lines). usage: load-sampler.sh <out> [max seconds] [disk]
set -u
OUT=$1; MAX=${2:-600}; DISK=${3:-nvme0n1}
: > "$OUT"
for _ in $(seq 1 300); do PID=$(pgrep -x kyty_emulator | head -1); [ -n "$PID" ] && break; sleep 0.5; done
[ -z "${PID:-}" ] && { echo "no emulator" >> "$OUT"; exit 1; }
HZ=$(getconf CLK_TCK); NCPU=$(nproc); BT=$(awk '/^btime/{print $2}' /proc/stat)
ST=$(awk '{print $22}' /proc/$PID/stat); START=$(( BT * 100 + ST * 100 / HZ ))
python3 -I - "$OUT" "$MAX" "$DISK" "$PID" "$HZ" "$NCPU" "$START" <<'PY'
import os, sys, time
out, mx, disk, pid, hz, ncpu, start = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]), int(sys.argv[7])
def cpu_total():
    with open("/proc/stat") as f:
        v = [int(x) for x in f.readline().split()[1:]]
    idle = v[3] + v[4]
    return sum(v), idle
def procs():
    d = {}
    for p in os.listdir("/proc"):
        if not p.isdigit(): continue
        try:
            s = open("/proc/%s/stat" % p).read()
        except OSError:
            continue
        name = s[s.index("(") + 1:s.rindex(")")]
        f = s[s.rindex(")") + 2:].split()
        d[int(p)] = (name, int(f[11]) + int(f[12]))
    return d
def threads():
    d = {}
    base = "/proc/%d/task" % pid
    try:
        tids = os.listdir(base)
    except OSError:
        return None
    for t in tids:
        try:
            s = open("%s/%s/stat" % (base, t)).read()
        except OSError:
            continue
        name = s[s.index("(") + 1:s.rindex(")")]
        f = s[s.rindex(")") + 2:].split()
        d[int(t)] = (name, int(f[11]) + int(f[12]))
    return d
def diskstat():
    for l in open("/proc/diskstats"):
        x = l.split()
        if x[2] == disk:
            return int(x[3]), int(x[5])  # reads completed, sectors read
    return 0, 0
pt, pi = cpu_total(); pp = procs(); pth = threads(); pr, ps_ = diskstat(); last = time.time()
with open(out, "a") as o:
    for i in range(mx):
        time.sleep(1.0)
        th = threads()
        if th is None:
            break
        now = time.time(); dt = now - last; last = now
        t_, i_ = cpu_total(); busy = 100.0 * (1 - (i_ - pi) / max(1, t_ - pt)); pt, pi = t_, i_
        cp = procs()
        top = []
        for k, (n, c) in cp.items():
            if k in pp and pp[k][0] == n:
                d = (c - pp[k][1]) * 100.0 / hz / dt
                if d >= 5: top.append((d, n))
        pp = cp
        top.sort(reverse=True)
        r, s = diskstat(); rd = (r - pr) / dt; mb = (s - ps_) * 512 / 1048576 / dt; pr, ps_ = r, s
        tl = []
        for k, (n, c) in th.items():
            if k in pth and pth[k][0] == n:
                d = (c - pth[k][1]) * 100.0 / hz / dt
                if d >= 10: tl.append((d, n))
        pth = th
        tl.sort(reverse=True)
        t = (time.time() * 100 - start) / 100.0
        o.write("load: t %.1f s: box CPU %.0f%% of %d; disk %.0f reads/s %.1f MB/s; procs %s | threads %s\n" % (
            t, busy, ncpu, rd, mb, " ".join("%s=%.0f" % (n, d) for d, n in top[:8]), " ".join("%s=%.0f" % (n, d) for d, n in tl[:12])))
        o.flush()
    o.write("DONE\n")
PY
