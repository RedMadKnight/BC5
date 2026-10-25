#!/usr/bin/env python3
# BC5 experiment 0311 (exp 0293's capa0293.py, re-aimed): the night lake water's per-cell ping-pong grid, read beside the
# depth image in the frozen view. Exp 0309 (F374): the only buffer swapped every frame among the lake's draws is in the
# full-screen water draw's geometry-stage table (GS user-data pair 4, dword 0): a buffer V# of stride 8 and 65,536
# records (256 x 256), two copies 2 MiB apart (exp 0283's raw/W283a.wr.txt). This reader follows the run's direct.log
# (BC5_DIRECT_DRAW_JOURNAL with _PS=11d01d7100: after each full-screen draw, "bake table gs ud4 <addr>: <dwords>", patch
# 0001, exp 0156), decodes dwords 0-3 there as a buffer V# (exp 0253's wr0253.py: base = dword0 | (dword1 & 0xffff)
# << 32, STRIDE dword1 [16,29], NUM_RECORDS dword2; Mesa gfx10-rsrc.json @ 0866ae7), and keeps the distinct bases with
# stride 8. Once two are known and the frozen view has begun (the bench's first ts00 shot), it takes N bursts, one
# every GAP s: K times (grid A, grid B, the depth image 0x1129ec0000 + 0x1860000) PERIOD ms apart, read-only through
# /proc/<pid>/mem (as exp 0212's mem0212.py), then the G-buffer. The depth reads are held in memory when MemAvailable
# is above HOLD MiB, else written at once; the grids (512 KiB each) are always held. File layout as capa0287.py's
# (bNN.times.txt, bNN.<name>.bin; "gA"/"gB" for the grids, their bases in the times lines), so rd0287.py's lineage
# (rd0309.py) reads the depth reads unchanged. Stops after N bursts, or when the run's BOX-LOCK line or its emulator is
# gone. Reads go to <out dir> (mode 700; the title's data).
# usage: grid0311.py <tag> <N bursts> <K reads> <period ms> <gap s> <out dir> [HOLD MiB]   (on the box, attended)
import glob, os, re, sys, time

tag, n_bursts, k_reads, period, gap, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4]) / 1000, float(sys.argv[5]), sys.argv[6]
hold_kib = int(sys.argv[7]) * 1024 if len(sys.argv) > 7 else 1024 * 1024
home = os.path.expanduser("~")
rdir = os.path.join(home, "bc5-work", "exp0311", "r-" + tag)
lock = os.path.join(home, "bc5-work", "BOX-LOCK")
ZR, GR = (0x1129ec0000, 0x1860000), (0x113f230000, 0x1860000)
FSD = re.compile(rb"^draw journal buf \d+ \(\d+ dwords\) at \d+:.*\| ps 11d01d7100 ")
TAB = re.compile(rb"^bake table gs ud4 ([0-9a-f]+):((?: [0-9a-f]{8})+)")
os.makedirs(out, mode=0o700, exist_ok=True)
caps = open(os.path.join(out, "caps.txt"), "a", buffering=1)


def say(s):
    print(s, flush=True)
    caps.write(s + "\n")


def ours():
    try:
        return ("exp 0311 | lake bench %s " % tag) in open(lock).read()
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


for _ in range(150):
    logs = glob.glob(os.path.join(home, "bc5-data", "captures", "play-*", "gc", "direct.log"))
    log = max(logs, key=os.path.getmtime) if logs else None
    if log is not None and os.path.getmtime(log) >= time.time() - 60 and emulators():
        break
    time.sleep(2)
else:
    say("no journal of this run: stop")
    sys.exit(1)
say("# journal %s" % log)
f = open(log, "rb")
bases, pending, after_fs, burst, frozen, last = {}, b"", False, 0, False, 0.0
while burst < n_bursts:
    if not ours():
        say("lock gone: stop")
        break
    pids = emulators()
    if len(pids) != 1:
        say("%d emulators: stop" % len(pids))
        break
    chunk = f.read()
    if chunk:
        pending += chunk
        lines = pending.split(b"\n")
        pending = lines[-1]
        for l in lines[:-1]:
            if FSD.match(l):
                after_fs = True
                continue
            m = TAB.match(l)
            if m and after_fs:
                d = [int(x, 16) for x in m[2].split()]
                if len(d) >= 4:
                    base, stride, recs = d[0] | (d[1] & 0xffff) << 32, (d[1] >> 16) & 0x3fff, d[2]
                    if stride == 8 and recs > 0:
                        bases[base] = bases.get(base, 0) + 1
                after_fs = False
            elif l.startswith(b"draw journal buf"):
                after_fs = False
    if not frozen:
        frozen = bool(glob.glob(os.path.join(rdir, "shots", "*-ts00.png")))
        if frozen:
            say("# frozen view; grid bases seen: %s" % " ".join("%x(x%d)" % kv for kv in sorted(bases.items())))
    if not frozen or len(bases) < 2 or time.time() - last < gap:
        time.sleep(0.05)
        continue
    two = sorted(bases, key=lambda b: -bases[b])[:2]
    gsize = 65536 * 8
    seen, last = time.time(), time.time()
    burst += 1
    name = "b%02d" % burst
    avail = mem_available_kib()
    hold = avail > hold_kib
    fd = os.open("/proc/%d/mem" % pids[0], os.O_RDONLY)
    rows, held = [], []
    t00 = time.monotonic()

    def take(nm, rng, keep, note=""):
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
        rows.append("%s wall %.4f mono %.4f start %.1f read %.1f write %.1f bytes %d%s" % (
            nm, w0, t0, (t0 - t00) * 1000, (t1 - t0) * 1000, (t2 - t1) * 1000, len(d), note))

    for k in range(k_reads):
        wait = t00 + k * period - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        take("gA%d" % k, (two[0], gsize), True, " base %x" % two[0])
        take("gB%d" % k, (two[1], gsize), True, " base %x" % two[1])
        take("z%d" % k, ZR, hold)
    take("g", GR, hold)
    os.close(fd)
    for nm, d in held:
        with open(os.path.join(out, "%s.%s.bin" % (name, nm)), "wb") as g:
            g.write(d)
    held = None
    open(os.path.join(out, name + ".times.txt"), "w").write("\n".join(rows) + "\n")
    say("%s at %s: grids %x %x, MemAvailable %d MiB, depth %s" % (
        name, time.strftime("%H:%M:%S", time.localtime(seen)), two[0], two[1], avail // 1024, "held in memory" if hold else "written at once"))
say("# %d bursts; grid bases seen: %s" % (burst, " ".join("%x(x%d)" % kv for kv in sorted(bases.items()))))
