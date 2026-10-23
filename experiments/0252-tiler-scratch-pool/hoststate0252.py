#!/usr/bin/env python3
# BC5 experiment 0252 (copy of exp 0247's): exp 0215's hoststate.py (the TCP session's) plus a per-period 'k' line of the busiest title threads.
# TCP session: a /proc-only host-state sampler for the wait-latency question, reduced from experiment
# 0200's sample0200.py (the cutscene session's): no reads of the emulator's memory, no player scanner.
# Read-only. Lines (mono = CLOCK_MONOTONIC seconds, the clock the journal's "bc5 clock: journal t 0 =
# monotonic X s" line names):
#   v <mono> d_compact_stall d_pgmajfault d_pswpin d_allocstall mem_some_us mem_full_us io_some_us io_full_us
#     cpu_some_us avail_MB                                                         every PERIOD s
#     the d_ fields are /proc/vmstat deltas over the period; the _us fields are deltas of the PSI "total="
#     counters (microseconds stalled in the period) of /proc/pressure/{memory,io,cpu}
#   t <mono> <name>/<tid> run_ms wait_ms R S D other                             every PERIOD s, per thread
#     run/wait: deltas of /proc/<pid>/task/<tid>/schedstat (on CPU, waiting for a CPU) in the period;
#     R/S/D/other: how many of the period's state samples (at HZ) found the thread in that state
#   g <mono> guest_run_ms guest_wait_ms guest_R guest_S guest_D guest_n host_run_ms host_n     every PERIOD s
#     CPU of ALL the emulator's threads, split by name: host threads (HOST prefixes: bc5-*, kyty*, SDL*, ...)
#     against the title's own (every other name). run/wait: schedstat deltas summed over the threads (ns
#     precision, unlike utime/stime's 10-ms ticks); R/S/D: how many of the title's threads were in each state
#     at the end of the period; n: how many threads of each kind
#   k <mono> <name>/<tid>:<run_ms>:<state> ...   every PERIOD s: the six title threads with the most CPU in the period
# usage: hoststate0252.py <out> [period_s] [hz]   (waits for kyty_emulator, ends with it)
import os, sys, time

OUT = sys.argv[1]
PERIOD = float(sys.argv[2]) if len(sys.argv) > 2 else 0.1
HZ = float(sys.argv[3]) if len(sys.argv) > 3 else 50.0
WATCH = ("game-main", "bc5-ring", "bc5-apr-q", "Render Thread", "kyty-gpu", "AK::IOThread")
HOST = ("bc5-", "kyty", "SDL", "gmain", "gdbus", "dconf", "pool-", "pw-", "threaded-ml", "llvmpipe", "radv", "disk_cache",
        "vkd3d", "wayland", "Xwayland", "pipewire", "pulse", "alsa", "dbus", "gvfs", "glib")

def find_emu():
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                with open("/proc/%s/comm" % d) as f:
                    if f.read().strip() == "kyty_emulator":
                        return int(d)
            except OSError:
                pass
    return None

def vmstat():
    d = {}
    with open("/proc/vmstat") as f:
        for line in f:
            k, v = line.split()
            d[k] = int(v)
    return (d.get("compact_stall", 0), d.get("pgmajfault", 0), d.get("pswpin", 0),
            d.get("allocstall_normal", 0) + d.get("allocstall_movable", 0) + d.get("allocstall_dma32", 0))

def psi_totals():  # cumulative microseconds: memory some/full, io some/full, cpu some
    out = []
    for kind, n in (("memory", 2), ("io", 2), ("cpu", 1)):
        try:
            with open("/proc/pressure/" + kind) as f:
                lines = f.read().split("\n")
            for l in lines[:n]:
                out.append(int(l.split("total=")[1].split()[0]))
        except (OSError, IndexError, ValueError):
            out += [0] * n
    return out

def avail():
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    return -1

o = open(OUT, "a", buffering=1)
o.write("# hoststate start %s period %g s, state hz %g\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), PERIOD, HZ))
pid = None
while pid is None:
    pid = find_emu()
    if pid is None:
        time.sleep(0.5)
time.sleep(2.0)
o.write("# pid %d at mono %.3f\n" % (pid, time.monotonic()))

def threads():
    out = {}
    try:
        for tid in os.listdir("/proc/%d/task" % pid):
            try:
                with open("/proc/%d/task/%s/comm" % (pid, tid)) as f:
                    name = f.read().strip()
            except OSError:
                continue
            if name.startswith(WATCH):
                out[int(tid)] = name.replace(" ", "_")
    except OSError:
        pass
    return out

def schedstat(tid):
    try:
        with open("/proc/%d/task/%d/schedstat" % (pid, tid)) as f:
            a = f.read().split()
        return int(a[0]), int(a[1])
    except OSError:
        return None

def state(tid):
    try:
        with open("/proc/%d/task/%d/stat" % (pid, tid)) as f:
            s = f.read()
        return s[s.rindex(")") + 2]
    except (OSError, ValueError):
        return None

all_names = {}; all_prev = {}
def all_threads():  # every task of the process: tid -> (name, is_host)
    out = {}
    try:
        for tid in os.listdir("/proc/%d/task" % pid):
            t = int(tid)
            if t in all_names:
                out[t] = all_names[t]; continue
            try:
                with open("/proc/%d/task/%s/comm" % (pid, tid)) as f:
                    name = f.read().strip()
            except OSError:
                continue
            out[t] = (name, name.startswith(HOST) or name == "kyty_emulator")
    except OSError:
        pass
    return out

tids = threads(); t_names = time.monotonic()
all_names = all_threads()
all_prev = {t: schedstat(t) for t in all_names}
prev_ss = {t: schedstat(t) for t in tids}
st_count = {t: {"R": 0, "S": 0, "D": 0, "o": 0} for t in tids}
prev_vm = vmstat(); prev_psi = psi_totals()
nxt = time.monotonic(); last_p = nxt
while os.path.exists("/proc/%d" % pid):
    now = time.monotonic()
    for t in st_count:
        s = state(t)
        if s is not None:
            st_count[t][s if s in ("R", "S", "D") else "o"] += 1
    if now - last_p >= PERIOD:
        last_p = now
        vm = vmstat(); ps = psi_totals()
        d = [a - b for a, b in zip(vm, prev_vm)]; prev_vm = vm
        dp = [a - b for a, b in zip(ps, prev_psi)]; prev_psi = ps
        o.write("v %.4f %d %d %d %d %d %d %d %d %d %d\n" % ((now,) + tuple(d) + tuple(dp) + (avail(),)))
        for t, name in tids.items():
            ss = schedstat(t)
            if ss is not None and prev_ss.get(t) is not None:
                c = st_count[t]
                o.write("t %.4f %s/%d %.1f %.1f %d %d %d %d\n" % (now, name, t, (ss[0] - prev_ss[t][0]) / 1e6,
                                                                (ss[1] - prev_ss[t][1]) / 1e6, c["R"], c["S"], c["D"], c["o"]))
            prev_ss[t] = ss
            st_count[t] = {"R": 0, "S": 0, "D": 0, "o": 0}
        g_run = g_wait = h_run = 0.0; gR = gS = gD = gn = hn = 0
        top = []
        for t, (name, is_host) in all_names.items():
            ss = schedstat(t)
            pv = all_prev.get(t)
            if ss is not None and pv is not None:
                dr, dw = (ss[0] - pv[0]) / 1e6, (ss[1] - pv[1]) / 1e6
                if is_host:
                    h_run += dr; hn += 1
                else:
                    g_run += dr; g_wait += dw; gn += 1
                    st = state(t)
                    if st == "R": gR += 1
                    elif st == "S": gS += 1
                    elif st == "D": gD += 1
                    top.append((dr, name.replace(" ", "_"), t, st or "?"))
            all_prev[t] = ss
        o.write("g %.4f %.1f %.1f %d %d %d %d %.1f %d\n" % (now, g_run, g_wait, gR, gS, gD, gn, h_run, hn))
        top.sort(reverse=True)
        o.write("k %.4f %s\n" % (now, " ".join("%s/%d:%.1f:%s" % (n, t, r, s) for r, n, t, s in top[:6])))
        if now - t_names >= 10.0:
            new_all = all_threads()
            for t in new_all:
                if t not in all_names:
                    all_prev[t] = schedstat(t)
            all_names = new_all
            t_names = now
            new = threads()
            for t in new:
                if t not in tids:
                    prev_ss[t] = schedstat(t)
            tids = new
            st_count = {t: st_count.get(t, {"R": 0, "S": 0, "D": 0, "o": 0}) for t in tids}
    nxt += 1.0 / HZ
    if nxt < time.monotonic():
        nxt = time.monotonic()
    time.sleep(max(0.0, nxt - time.monotonic()))
o.write("# end %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
