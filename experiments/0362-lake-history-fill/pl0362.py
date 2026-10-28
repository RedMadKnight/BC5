#!/usr/bin/env python3
# BC5 experiment 0362: the night lake's depth within each frame, by snapshots. exp 0357's pl0357.py, its full reads and
# culling records replaced by per-frame snapshots. From the frozen view (the bench's first ts00 shot) and the emulator's
# MIN_T-th second, for SECS seconds, in a tight loop through /proc/<pid>/mem (read-only), every poll reads:
#   D  256 KiB of the depth image in the lake's block rows (0x1129ec0000 + 0x980000): the frame's depth activity;
#   P  the depth pyramid's mip 0 (0x11d0886000, 0x8000 bytes): it changes once per frame, at the frame's start (F441).
# A poll with a change writes "<mono> <wall> D<0|1> P<0|1>" to <out>/events.txt.
# Every CAPGAP s a capture of K consecutive frames begins at the next P change. Per frame, snapshots S (the depth image
# at +0x300000 .. +0xa00000, 7 MiB: the lake window's block rows at widths 2048-2560):
#   s0 once D has been quiet for Q0 ms after the frame's start;
#   s1 once a D change has been followed by Q ms without one; s2 likewise after the next one.
# D is read right before and after each snapshot; if they differ, or if P changed during it, the snapshot is torn.
# A capture's snapshots stay in memory and are written after it to <out>/c<NN>.f<k>.s<j>.bin, with a line per
# snapshot in <out>/snaps.txt:
#   "c<NN> f<k> s<j> wall <start wall> mono <start mono> since <ms since the frame's P change> read <ms> torn <0|1>"
# and per frame "c<NN> f<k> frame mono <P change> dbursts <D changes before s1>,<s1..s2>,<after s2 to the next P>".
# Stops after SECS, or when the run's BOX-LOCK line or its emulator is gone. Reads go to <out> (mode 700; the title's
# data).
# usage: pl0362.py <tag> <secs> <out dir> [MIN_T s] [CAPGAP s] [K]   (on the box, attended, beside ab0362.sh)
import glob, os, sys, time

tag, secs, out = sys.argv[1], float(sys.argv[2]), sys.argv[3]
min_t = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
capgap = float(sys.argv[5]) if len(sys.argv) > 5 else 2.5
K = int(sys.argv[6]) if len(sys.argv) > 6 else 5
Q0, Q = 0.001, 0.0015
home = os.path.expanduser("~")
rdir = os.path.join(home, "bc5-work", "exp0362", "r-" + tag)
lock = os.path.join(home, "bc5-work", "BOX-LOCK")
D = (0x1129ec0000 + 0x980000, 256 << 10)
P0 = (0x11d0886000, 0x8000)
S = (0x1129ec0000 + 0x300000, 0x700000)
os.makedirs(out, mode=0o700, exist_ok=True)


def ours():
    try:
        return ("exp 0362 | lake bench %s " % tag) in open(lock).read()
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
sl = open(os.path.join(out, "snaps.txt"), "w")
prev_d = prev_p = None
polls, nd, npc, nsnap, ntorn, ncap = 0, 0, 0, 0, 0, 0
t_start = time.monotonic()
next_cap = t_start + 1.0
maxgap, last = 0.0, t_start
cap = None  # {"no", "frames": [...], "buf": [(name, bytes)]} while a capture runs
fr = None   # the frame being captured: {"k", "p", "snaps", "phase", "dlast", "dseen", "bursts"}


def snap(j, now_p):
    global prev_d, nsnap, ntorn
    w0, m0 = time.time(), time.monotonic()
    d0 = os.pread(fd, D[1], D[0])
    data = os.pread(fd, S[1], S[0])
    d1 = os.pread(fd, D[1], D[0])
    p1 = os.pread(fd, P0[1], P0[0])
    m1 = time.monotonic()
    torn = int(d0 != d1 or d0 != prev_d or p1 != now_p)
    name = "c%02d.f%d.s%d" % (cap["no"], fr["k"], j)
    cap["buf"].append((name, data))
    sl.write("c%02d f%d s%d wall %.4f mono %.6f since %.2f read %.2f torn %d\n" % (
        cap["no"], fr["k"], j, w0, m0, (m0 - fr["p"]) * 1000, (m1 - m0) * 1000, torn))
    prev_d = d0  # a change during the read shows at the next poll
    nsnap += 1
    ntorn += torn


def end_frame():
    sl.write("c%02d f%d frame mono %.6f dbursts %s\n" % (cap["no"], fr["k"], fr["p"], ",".join(str(b) for b in fr["bursts"])))


def flush_capture():
    global cap
    for name, data in cap["buf"]:
        with open(os.path.join(out, name + ".bin"), "wb") as g:
            g.write(data)
    sl.flush()
    cap = None


while True:
    now = time.monotonic()
    if now - t_start > secs:
        break
    if polls % 2000 == 0 and (not ours() or not os.path.exists("/proc/%d" % pid)):
        print("lock or emulator gone: stop", flush=True)
        break
    w = time.time()
    m = time.monotonic()
    try:
        d = os.pread(fd, D[1], D[0])
        p = os.pread(fd, P0[1], P0[0])
    except OSError as e:
        print("poll read error %s: stop" % e, flush=True)
        break
    polls += 1
    maxgap = max(maxgap, m - last)
    last = m
    dch = prev_d is not None and d != prev_d
    pch = prev_p is not None and p != prev_p
    prev_d, prev_p = d, p
    if dch or pch:
        ev.write("%.6f %.4f D%d P%d\n" % (m, w, int(dch), int(pch)))
        nd += dch
        npc += pch
    try:
        if pch:
            if fr is not None:
                end_frame()
                fr = None
            if cap is not None and len(cap["frames"]) >= K:
                flush_capture()
                next_cap = time.monotonic() + capgap
            elif cap is None and m >= next_cap:
                cap = {"no": ncap, "frames": [], "buf": []}
                ncap += 1
            if cap is not None:
                fr = {"k": len(cap["frames"]), "p": m, "phase": 0, "dlast": m, "dseen": False, "bursts": [0, 0, 0]}
                cap["frames"].append(fr)
            continue
        if fr is None:
            continue
        if dch:
            fr["dlast"], fr["dseen"] = m, True
            fr["bursts"][min(fr["phase"] - 1, 2) if fr["phase"] > 0 else 0] += 1
            continue
        if fr["phase"] == 0 and m - fr["dlast"] >= Q0:
            snap(0, p)
            fr["phase"], fr["dseen"] = 1, False
        elif fr["phase"] in (1, 2) and fr["dseen"] and m - fr["dlast"] >= Q:
            snap(fr["phase"], p)
            fr["phase"], fr["dseen"] = fr["phase"] + 1, False
    except OSError as e:
        print("snapshot read error %s: stop" % e, flush=True)
        break
if cap is not None:
    if fr is not None:
        end_frame()
    flush_capture()
os.close(fd)
ev.close()
sl.close()
dur = time.monotonic() - t_start
print("# %d polls in %.1f s (mean period %.3f ms, largest gap %.1f ms); polls with a change: D %d, P %d; %d captures, %d snapshots (%d torn)" % (
    polls, dur, 1000 * dur / max(polls, 1), 1000 * maxgap, nd, npc, ncap, nsnap, ntorn), flush=True)
