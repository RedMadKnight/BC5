#!/usr/bin/env python3
# BC5 experiment 0312 (exp 0311's grid0311.py, re-aimed): the night lake's culling buffers, read whole beside the depth
# image in the frozen view. The lake depth writers' indirect arguments sit at small offsets in four buffers the culling
# chain binds (F355): 0x11934d3900 (1 MiB), 0x11935d3900 (4 MiB), 0x11939d3900 and 0x1193ad3900, the same addresses in
# every run read so far (exps 0289, 0293, 0295: capa's "argument bases so far" lines) and contiguous (0x11934d3900 +
# 6 MiB = 0x1193ad3900). Only the argument records were ever read (F350-F359). If the water cells are culled in two
# phases (GPU-driven two-phase occlusion culling: an early pass draws what was visible last frame, a late pass what
# became visible; Bevy's documentation, Haar & Aaltonen SIGGRAPH 2015), the per-cell state and the visible lists the
# draws consume are likely in the rest of these buffers.
# Once the frozen view has begun (the bench's first ts00 shot), N bursts, one every GAP s: K times (the 8 MiB from
# 0x11934d3900, "c"; the depth image 0x1129ec0000 + 0x1860000, "z") PERIOD ms apart, read-only through /proc/<pid>/mem
# (as exp 0212's mem0212.py), then the G-buffer. All reads are held in memory when MemAvailable is above HOLD MiB, else
# the depth reads are written at once. capa0287.py's file layout (bNN.times.txt, bNN.<name>.bin), so rd0312.py
# (exp 0289's rd0289.py) labels the depth reads. Stops after N bursts, or when the run's BOX-LOCK line or its emulator
# is gone. Reads go to <out dir> (mode 700; the title's data).
# Run J1: with MIN_T, the first burst also waits until the emulator has run MIN_T s (/proc/<pid>/stat's start time), so
# that every burst falls in the draw journal's window (BC5_DIRECT_DRAW_JOURNAL=<t>:<n>, t from the emulator's start).
# usage: buf0312.py <tag> <N bursts> <K reads> <period ms> <gap s> <out dir> [HOLD MiB] [MIN_T s]   (on the box, attended)
import glob, os, sys, time

tag, n_bursts, k_reads, period, gap, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4]) / 1000, float(sys.argv[5]), sys.argv[6]
hold_kib = int(sys.argv[7]) * 1024 if len(sys.argv) > 7 else 1024 * 1024
min_t = float(sys.argv[8]) if len(sys.argv) > 8 else 0.0
home = os.path.expanduser("~")
rdir = os.path.join(home, "bc5-work", "exp0312", "r-" + tag)
lock = os.path.join(home, "bc5-work", "BOX-LOCK")
CR, ZR, GR = (0x11934d3900, 8 << 20), (0x1129ec0000, 0x1860000), (0x113f230000, 0x1860000)
os.makedirs(out, mode=0o700, exist_ok=True)
caps = open(os.path.join(out, "caps.txt"), "a", buffering=1)


def say(s):
    print(s, flush=True)
    caps.write(s + "\n")


def ours():
    try:
        return ("exp 0312 | lake bench %s " % tag) in open(lock).read()
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


def age(pid):  # seconds since the process started
    try:
        st = open("/proc/%d/stat" % pid).read().rsplit(")", 1)[1].split()
        return float(open("/proc/uptime").read().split()[0]) - int(st[19]) / os.sysconf("SC_CLK_TCK")
    except (OSError, IndexError, ValueError):
        return 0.0


def mem_available_kib():
    for l in open("/proc/meminfo"):
        if l.startswith("MemAvailable:"):
            return int(l.split()[1])
    return 0


burst, frozen, last = 0, False, 0.0
for _ in range(600):
    if emulators():
        break
    time.sleep(1)
while burst < n_bursts:
    if not ours():
        say("lock gone: stop")
        break
    pids = emulators()
    if len(pids) != 1:
        say("%d emulators: stop" % len(pids))
        break
    if not frozen:
        frozen = bool(glob.glob(os.path.join(rdir, "shots", "*-ts00.png"))) and age(pids[0]) >= min_t
        if frozen:
            say("# frozen view%s: bursts begin" % (", emulator at %.1f s" % age(pids[0]) if min_t else ""))
    if not frozen or time.time() - last < gap:
        time.sleep(0.05)
        continue
    seen = last = time.time()
    burst += 1
    name = "b%02d" % burst
    avail = mem_available_kib()
    hold = avail > hold_kib
    fd = os.open("/proc/%d/mem" % pids[0], os.O_RDONLY)
    rows, held = [], []
    t00 = time.monotonic()

    def take(nm, rng, keep):
        w0, t0 = time.time(), time.monotonic()
        try:
            d = os.pread(fd, rng[1], rng[0])
        except OSError as e:
            rows.append("%s wall %.4f mono %.4f error %s" % (nm, w0, t0, e))
            return
        t1 = time.monotonic()
        if keep:
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
        take("c%d" % k, CR, True)
        take("z%d" % k, ZR, hold)
    take("g", GR, hold)
    os.close(fd)
    for nm, d in held:
        with open(os.path.join(out, "%s.%s.bin" % (name, nm)), "wb") as g:
            g.write(d)
    held = None
    open(os.path.join(out, name + ".times.txt"), "w").write("\n".join(rows) + "\n")
    say("%s at %s: MemAvailable %d MiB, depth %s" % (name, time.strftime("%H:%M:%S", time.localtime(seen)), avail // 1024,
                                                     "held in memory" if hold else "written at once"))
say("# %d bursts" % burst)
