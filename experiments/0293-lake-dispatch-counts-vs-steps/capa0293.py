#!/usr/bin/env python3
# BC5 experiment 0293 (exp 0289's capa0289.py, unchanged but for the lock tag; run with CAPA_PYRAMID=0): the night lake's depth writers' indirect arguments as the GPU leaves them in memory, read next
# to the depth image, in bursts timed to the draw journal's windows (exp 0283's capw0283.py, extended). Exps 0283-0286
# (F344, F346, F348): nothing the CPU submits tells the lake's X frames from its Y frames; the writers' arguments are
# GPU-written (edit0194.py reads them only at submission: "the previous frame's, the scene standing still", and its
# values at completion are missing for chained jobs). This reader follows the run's direct.log and learns the argument
# addresses from its "draw journal args buf N at P: op .. base1 B +0xO" lines (DRAW_INDIRECT arguments at base1 +
# offset, Mesa radv_cs_emit_indirect_draw_packet as edit0194.py cites): per base, the range from its lowest to its
# highest offset + 32 bytes (both argument slots of exp 0283 are 0x20 apart), at most 1 MiB per base. At each new
# window line from the first frozen-view shot on, one burst, read-only through /proc/<pid>/mem (as exp 0212's
# mem0212.py): K times the argument ranges ("aK", held in memory: a few KiB), the region of the 32_FLOAT image pyramid
# the depth writers' vertex stage reads (0x11d0880000 + 0x20000, exp 0274: mips 128x64 .. 8x4 at 0x11d0886000 ..
# 0x11d0892000; "pK", held in memory; W287b on) and then the depth image (0x1129ec0000 + 0x1860000, "zK"), PERIOD ms apart, then the argument ranges once more ("aE") and the G-buffer (0x113f230000 +
# 0x1860000). The depth and G-buffer reads are held in memory when MemAvailable is above HOLD MiB, else written at
# once. Per read: wall clock, CLOCK_MONOTONIC, read and write time; an argument read's file holds its ranges one after
# the other, as listed in its line ("ranges addr:len ..."). Stops after N bursts, or when the run's BOX-LOCK line or its
# emulator is gone. Reads go to <out dir> (mode 700; the title's data).
# usage: capa0287.py <tag> <N bursts> <K reads> <period ms> <out dir> [HOLD MiB]   (on the box, by hand, attended)
import glob, os, re, sys, time

tag, n_bursts, k_reads, period, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4]) / 1000, sys.argv[5]
hold_kib = int(sys.argv[6]) * 1024 if len(sys.argv) > 6 else 2 * 1024 * 1024
home = os.path.expanduser("~")
rdir = os.path.join(home, "bc5-work", "exp0194", "r-" + tag)
lock = os.path.join(home, "bc5-work", "BOX-LOCK")
ZR, GR = (0x1129ec0000, 0x1860000), (0x113f230000, 0x1860000)
PR = (0x11d0880000, 0x20000)
pyramid = os.environ.get("CAPA_PYRAMID", "1") == "1"
ARGS = re.compile(rb"^draw journal args buf \d+ at \d+: op \S+ base1 ([0-9a-f]+) \+0x([0-9a-f]+)")
os.makedirs(out, mode=0o700, exist_ok=True)
caps = open(os.path.join(out, "caps.txt"), "a", buffering=1)


def say(s):
    print(s, flush=True)
    caps.write(s + "\n")


def ours():
    try:
        return ("exp 0293 | bench %s " % tag) in open(lock).read()
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


# the argument offsets seen so far, per base; the journal is followed from the emulator's start, so the first window
# (t 150, before the frozen view) has given them by the first burst
for _ in range(120):
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
offs, pending, burst = {}, b"", 0
frozen = False
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
    win = []
    for l in lines[:-1]:
        m = ARGS.match(l)
        if m:
            b, o = int(m[1], 16), int(m[2], 16)
            lo, hi = offs.get(b, (o, o))
            offs[b] = (min(lo, o), max(hi, o))
        elif l.startswith(b"draw journal window from buf"):
            win.append(l)
    if not frozen:
        frozen = bool(glob.glob(os.path.join(rdir, "shots", "*-ts00.png")))
        if frozen:
            say("# frozen view from %s; argument bases so far: %s" % (last_shot(), " ".join(
                "%x+%x..%x" % (b, lo, hi) for b, (lo, hi) in sorted(offs.items()))))
    if not win or not frozen or not offs:
        continue
    seen = time.time()
    burst += 1
    name = "b%02d" % burst
    ranges = [(b + lo, min(hi - lo + 32, 1 << 20)) for b, (lo, hi) in sorted(offs.items())]
    avail = mem_available_kib()
    hold = avail > hold_kib
    fd = os.open("/proc/%d/mem" % pids[0], os.O_RDONLY)
    rows, held = [], []
    t00 = time.monotonic()

    def take(nm, rngs, keep):
        w0, t0 = time.time(), time.monotonic()
        parts = []
        try:
            for a, n in rngs:
                parts.append(os.pread(fd, n, a))
        except OSError as e:
            rows.append("%s wall %.4f mono %.4f error %s" % (nm, w0, t0, e))
            return
        t1 = time.monotonic()
        d = b"".join(parts)
        if keep:
            held.append((nm, d))
            t2 = t1
        else:
            with open(os.path.join(out, "%s.%s.bin" % (name, nm)), "wb") as g:
                g.write(d)
            t2 = time.monotonic()
        rows.append("%s wall %.4f mono %.4f start %.1f read %.1f write %.1f bytes %d%s" % (
            nm, w0, t0, (t0 - t00) * 1000, (t1 - t0) * 1000, (t2 - t1) * 1000, len(d),
            "" if nm[0] in "zgp" else " ranges " + " ".join("%x:%x" % r for r in rngs)))

    for k in range(k_reads):
        wait = t00 + k * period - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        take("a%d" % k, ranges, True)
        if pyramid:
            take("p%d" % k, [PR], True)
        take("z%d" % k, [ZR], hold)
    take("aE", ranges, True)
    take("g", [GR], hold)
    os.close(fd)
    for nm, d in held:
        with open(os.path.join(out, "%s.%s.bin" % (name, nm)), "wb") as g:
            g.write(d)
    held = None
    open(os.path.join(out, name + ".times.txt"), "w").write("\n".join(rows) + "\n")
    say("%s at %s after %s: %s, seen at wall %.4f, MemAvailable %d MiB, %d argument ranges (%d bytes), depth %s" % (
        name, time.strftime("%H:%M:%S", time.localtime(seen)) + ".%03d" % int(seen % 1 * 1000), last_shot(),
        win[-1].decode(errors="replace").strip(), seen, avail // 1024, len(ranges), sum(n for _, n in ranges),
        "held in memory" if hold else "written at once"))
say("# %d bursts" % burst)
