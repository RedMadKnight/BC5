#!/usr/bin/env python3
# BC5 experiment 0283: depth read bursts timed to the draw journal's windows, so that each read can be matched to the
# journalled frames around it. Exp 0282 (F342): the lake's holes switch between two fixed, disjoint pixel sets X and Y;
# which frames are X and which Y needs the reads' times next to the frames' times. The journal (BC5_DIRECT_DRAW_JOURNAL
# with edit0194.py's _EVERY, exp 0251's private binary) opens a window of <buffers> buffers every few seconds and starts
# it with "draw journal window from buf N: t T wall S.MS"; its filtered draws carry "bake draw buf N at P: t T wall
# S.MS". This reader follows the run's direct.log from the first frozen-view shot on and, at each new window line,
# takes one burst, read-only through /proc/<pid>/mem (as exp 0212's mem0212.py): K reads of the depth image
# (0x1129ec0000 + 0x1860000, F309) started PERIOD ms apart, then one read of the G-buffer (0x113f230000 + 0x1860000).
# The reads are held in memory and written after the burst when MemAvailable is above HOLD MiB (default 2048; W283b:
# 1024), so the writes do not spread them (in W283a, with every read written at once, the journalled frames ran
# 150-350 ms apart during most bursts), else each is written at once; MemAvailable is logged per burst. Per read it logs the wall clock (time.time(), the clock the journal's
# "wall" uses) and time.monotonic() (CLOCK_MONOTONIC, the clock behind the journal's t: steady_clock, "bc5 clock" line
# in emu.log), the read and write times. Stops after N bursts, or when the run's BOX-LOCK line or its emulator is gone.
# Reads go to <out dir> (mode 700; the title's data).
# usage: capw0283.py <tag> <N bursts> <K reads> <period ms> <out dir> [HOLD MiB]   (on the box, by hand, attended)
import glob, os, sys, time

tag, n_bursts, k_reads, period, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4]) / 1000, sys.argv[5]
hold_kib = int(sys.argv[6]) * 1024 if len(sys.argv) > 6 else 2 * 1024 * 1024
home = os.path.expanduser("~")
rdir = os.path.join(home, "bc5-work", "exp0194", "r-" + tag)
lock = os.path.join(home, "bc5-work", "BOX-LOCK")
ZR, GR = (0x1129ec0000, 0x1860000), (0x113f230000, 0x1860000)
os.makedirs(out, mode=0o700, exist_ok=True)
caps = open(os.path.join(out, "caps.txt"), "a", buffering=1)


def say(s):
    print(s, flush=True)
    caps.write(s + "\n")


def ours():
    try:
        return ("exp 0283 | bench %s " % tag) in open(lock).read()
    except OSError:
        return False


def emulators():
    pids = []
    for p in os.listdir("/proc"):
        if p.isdigit():
            try:
                if open("/proc/%s/comm" % p).read().strip() == "kyty_emulator":
                    pids.append(int(p))
            except OSError:
                pass
    return pids


def mem_available_kib():
    for l in open("/proc/meminfo"):
        if l.startswith("MemAvailable:"):
            return int(l.split()[1])
    return 0


def last_shot():
    s = sorted(glob.glob(os.path.join(rdir, "shots", "*-ts*.png")))
    return os.path.basename(s[-1]) if s else "-"


for _ in range(240):
    if glob.glob(os.path.join(rdir, "shots", "*-ts00.png")):
        break
    time.sleep(1)
else:
    say("no ts00 shot: stop")
    sys.exit(1)
# the run's journal: the direct.log written to last (one emulator runs, ours), and within the last minute
logs = glob.glob(os.path.join(home, "bc5-data", "captures", "play-*", "gc", "direct.log"))
log = max(logs, key=os.path.getmtime) if logs else None
if log is None or os.path.getmtime(log) < time.time() - 60:
    say("no journal of this run: stop")
    sys.exit(1)
say("# journal %s, from %s" % (log, last_shot()))
f = open(log, "rb")
f.seek(0, 2)
pending, burst = b"", 0
while burst < n_bursts:
    if not ours():
        say("lock gone: stop")
        break
    pids = emulators()
    if len(pids) != 1:
        say("%d emulators: stop" % len(pids))
        break
    chunk = f.read()
    if not chunk:
        time.sleep(0.01)
        continue
    pending += chunk
    lines = pending.split(b"\n")
    pending = lines[-1]
    win = [l for l in lines[:-1] if l.startswith(b"draw journal window from buf")]
    if not win:
        continue
    seen = time.time()
    burst += 1
    name = "b%02d" % burst
    avail = mem_available_kib()
    hold = avail > hold_kib
    fd = os.open("/proc/%d/mem" % pids[0], os.O_RDONLY)
    rows, held = [], []
    t00 = time.monotonic()

    def take(nm, rng):
        w0, t0 = time.time(), time.monotonic()
        try:
            d = os.pread(fd, rng[1], rng[0])
        except OSError as e:
            rows.append("%s wall %.4f mono %.4f error %s" % (nm, w0, t0, e))
            return
        t1 = time.monotonic()
        if hold:
            held.append((nm, d))
            t2 = t1
        else:
            with open(os.path.join(out, "%s.%s.bin" % (name, nm)), "wb") as g:
                g.write(d)
            t2 = time.monotonic()
        rows.append("%s wall %.4f mono %.4f start %.1f read %.1f write %.1f bytes %d" % (
            nm, w0, t0, (t0 - t00) * 1000, (t1 - t0) * 1000, (t2 - t1) * 1000, len(d)))

    for k in range(k_reads):
        wait = t00 + k * period - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        take("z%d" % k, ZR)
    take("g", GR)
    os.close(fd)
    for nm, d in held:
        with open(os.path.join(out, "%s.%s.bin" % (name, nm)), "wb") as g:
            g.write(d)
    held = None
    open(os.path.join(out, name + ".times.txt"), "w").write("\n".join(rows) + "\n")
    say("%s at %s after %s: %s, seen at wall %.4f, MemAvailable %d MiB, %s" % (
        name, time.strftime("%H:%M:%S", time.localtime(seen)) + ".%03d" % int(seen % 1 * 1000), last_shot(),
        win[-1].decode(errors="replace").strip(), seen, avail // 1024, "held in memory" if hold else "written at once"))
say("# %d bursts" % burst)
