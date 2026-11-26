#!/usr/bin/env python3
# BC5 experiment 0357: the night lake's GPU order per frame, by polling. From the frozen view (the bench's first ts00
# shot) and the emulator's MIN_T-th second, for SECS seconds, in a tight loop through /proc/<pid>/mem (read-only), every
# poll reads and compares with the previous poll:
#   D  256 KiB of the depth image in the lake's block rows (0x1129ec0000 + 0x980000): the frame's depth activity;
#   P  the lake writers' depth pyramid (F352, exp 0274): five single-level 32_FLOAT images, mip 0 128 x 64 at
#      0x11d0886000 (0x8000 bytes), mip 1 at +0x8000 (0x2000), mips 2-4 at +0xa000, +0xb000, +0xc000 (one 4 KiB
#      4KB_S block each); a change flag per mip;
#   A  the first 4 KiB at each of the four culling bases (F355, F440: 0x11934d3900, 0x11935d3900, 0x11939d3900,
#      0x1193ad3900) as 128 records of 32 bytes; the records that changed.
# A poll with any change writes a line "<mono> <wall> D<0|1> P<5 flags> A<base:record,...>" to <out>/events.txt. Every
# FULLGAP s one full depth read (0x1860000 bytes at 0x1129ec0000, as buf0312.py's "z") goes to <out>/b01.z<K>.bin with
# its line in <out>/b01.times.txt (buf0312.py's layout, so rd0312.py/rdj0312.py/fr0354.py read it). Polling pauses
# during a full read; the pause is in the log as a gap. Stops after SECS, or when the run's BOX-LOCK line or its emulator
# is gone. Prints the poll period, the change counts and the full reads. Reads go to <out> (mode 700; the title's data).
# usage: pl0357.py <tag> <secs> <full gap s> <out dir> [MIN_T s]   (on the box, attended, beside ab0357.sh)
import glob, os, sys, time

tag, secs, fgap, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
min_t = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0
home = os.path.expanduser("~")
rdir = os.path.join(home, "bc5-work", "exp0357", "r-" + tag)
lock = os.path.join(home, "bc5-work", "BOX-LOCK")
DEPTH = (0x1129ec0000, 0x1860000)
D = (0x1129ec0000 + 0x980000, 256 << 10)
PYR = (0x11d0886000, 0xd000)
MIPS = ((0x0, 0x8000), (0x8000, 0x2000), (0xa000, 0x1000), (0xb000, 0x1000), (0xc000, 0x1000))
BASES = (0x11934d3900, 0x11935d3900, 0x11939d3900, 0x1193ad3900)
os.makedirs(out, mode=0o700, exist_ok=True)


def ours():
    try:
        return ("exp 0357 | lake bench %s " % tag) in open(lock).read()
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


for _ in range(600):
    if emulators():
        break
    time.sleep(1)
while True:
    pids = emulators()
    if len(pids) != 1 or not ours():
        print("no single emulator or lock gone before the start: stop", flush=True)
        sys.exit(1)
    if glob.glob(os.path.join(rdir, "shots", "*-ts00.png")) and age(pids[0]) >= min_t:
        break
    time.sleep(0.05)
pid = pids[0]
print("# frozen view, emulator at %.1f s: polling begins" % age(pid), flush=True)
fd = os.open("/proc/%d/mem" % pid, os.O_RDONLY)
ev = open(os.path.join(out, "events.txt"), "w", buffering=1 << 20)
tl = []
prev_d = prev_p = None
prev_a = [None] * 4
polls, nd, np_, na, nfull = 0, 0, [0] * 5, 0, 0
t_start = time.monotonic()
t_full = t_start
maxgap, last = 0.0, t_start
while True:
    now = time.monotonic()
    if now - t_start > secs:
        break
    if polls % 2000 == 0 and (not ours() or not os.path.exists("/proc/%d" % pid)):
        print("lock or emulator gone: stop", flush=True)
        break
    if now - t_full >= fgap:
        t_full = now
        w0, m0 = time.time(), time.monotonic()
        try:
            data = os.pread(fd, DEPTH[1], DEPTH[0])
        except OSError as e:
            print("full read error %s: stop" % e, flush=True)
            break
        m1 = time.monotonic()
        with open(os.path.join(out, "b01.z%d.bin" % nfull), "wb") as g:
            g.write(data)
        data = None
        tl.append("z%d wall %.4f mono %.4f start %.1f read %.1f write %.1f bytes %d" % (
            nfull, w0, m0, (m0 - t_start) * 1000, (m1 - m0) * 1000, (time.monotonic() - m1) * 1000, DEPTH[1]))
        nfull += 1
    w = time.time()
    m = time.monotonic()
    try:
        d = os.pread(fd, D[1], D[0])
        p = os.pread(fd, PYR[1], PYR[0])
        a = [os.pread(fd, 4096, b) for b in BASES]
    except OSError as e:
        print("poll read error %s: stop" % e, flush=True)
        break
    polls += 1
    maxgap = max(maxgap, m - last)
    last = m
    dch = prev_d is not None and d != prev_d
    pch = [prev_p is not None and p[o:o + n] != prev_p[o:o + n] for o, n in MIPS]
    ach = []
    for i in range(4):
        if prev_a[i] is not None and a[i] != prev_a[i]:
            ach.extend("%d:%d" % (i, r) for r in range(128) if a[i][32 * r:32 * r + 32] != prev_a[i][32 * r:32 * r + 32])
    prev_d, prev_p, prev_a = d, p, a
    if dch or any(pch) or ach:
        ev.write("%.6f %.4f D%d P%s A%s\n" % (m, w, int(dch), "".join("1" if x else "0" for x in pch), ",".join(ach) or "-"))
        nd += dch
        na += bool(ach)
        for i in range(5):
            np_[i] += pch[i]
os.close(fd)
ev.close()
open(os.path.join(out, "b01.times.txt"), "w").write("\n".join(tl) + "\n")
dur = time.monotonic() - t_start
print("# %d polls in %.1f s (mean period %.3f ms, largest gap %.1f ms); polls with a change: D %d, P mips %s, A %d; %d full depth reads" % (
    polls, dur, 1000 * dur / max(polls, 1), 1000 * maxgap, nd, np_, na, nfull), flush=True)
