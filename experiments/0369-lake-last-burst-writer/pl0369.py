#!/usr/bin/env python3
# BC5 experiment 0369, run K2: exp 0365's pl0365.py unchanged but for its paths and lock text (0365 -> 0369).
# BC5 experiment 0369: the night lake's depth mid-frame and after the frame's last write burst, in consecutive frames.
# exp 0362's pl0362.py with its snapshot points moved. In exp 0362's run H1 a frame's depth sample (D) changed in three
# bursts, at a median +6.5, +8.5 and +18.7 ms after the pyramid's mip 0 changed (the frame's start; F441). The frame's
# image at its width was readable only after the third. From the frozen view (the bench's first ts00 shot) and the
# emulator's MIN_T-th second, for SECS seconds, in a tight loop through /proc/<pid>/mem (read-only), every poll reads:
#   D  256 KiB of the depth image in the lake's block rows (0x1129ec0000 + 0x980000);
#   P  the depth pyramid's mip 0 (0x11d0886000, 0x8000 bytes).
# A poll with a change writes "<mono> <wall> D<0|1> P<0|1>" to <out>/events.txt; a P change within 1 ms of the last
# one does not start a new frame.
# Every CAPGAP s a capture of K consecutive frames begins at the next frame start. Per frame, two snapshots S (the depth
# image at +0x300000 .. +0xa00000, 7 MiB: the lake window's block rows at widths 2048-2560):
#   sM ("mid") once the frame is at least TM0 ms old and D has been quiet for QM ms, at the latest at TM1 ms (else
#      none): between the second and the third burst;
#   sF ("final") once a D change at least TF0 ms into the frame has been followed by QF ms without one; if there is
#      none by TF1 ms, at TF1 ("late" 0 in its line).
# D is read right before and after each snapshot; if they differ, or if D changed since the last poll, or P changed
# during it, the snapshot is torn. A capture's snapshots stay in memory and are written after it to
# <out>/c<NN>.f<k>.s<M|F>.bin, with a line per snapshot in <out>/snaps.txt:
#   "c<NN> f<k> s<M|F> wall <start wall> mono <start mono> since <ms since the frame's start> read <ms> torn <0|1>
#    late <1|0> dch <D changes since the frame's start> dlast <ms of the last D change>"
# and per frame "c<NN> f<k> frame mono <start> end <ms to the next frame start or -1>".
# Stops after SECS, or when the run's BOX-LOCK line or its emulator is gone. Reads go to <out> (mode 700; the title's
# data).
# usage: pl0369.py <tag> <secs> <out dir> [MIN_T s] [CAPGAP s] [K]   (on the box, attended, beside ab0369.sh)
import glob, os, sys, time

tag, secs, out = sys.argv[1], float(sys.argv[2]), sys.argv[3]
min_t = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
capgap = float(sys.argv[5]) if len(sys.argv) > 5 else 2.0
K = int(sys.argv[6]) if len(sys.argv) > 6 else 6
TM0, TM1, QM = 0.0090, 0.0130, 0.0010
TF0, TF1, QF = 0.0150, 0.0250, 0.0015
home = os.path.expanduser("~")
rdir = os.path.join(home, "bc5-work", "exp0369", "r-" + tag)
lock = os.path.join(home, "bc5-work", "BOX-LOCK")
D = (0x1129ec0000 + 0x980000, 256 << 10)
P0 = (0x11d0886000, 0x8000)
S = (0x1129ec0000 + 0x300000, 0x700000)
os.makedirs(out, mode=0o700, exist_ok=True)


def ours():
    try:
        return ("exp 0369 | lake bench %s " % tag) in open(lock).read()
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
polls, nd, npc, nsnap, ntorn, ncap, nfr = 0, 0, 0, 0, 0, 0, 0
t_start = time.monotonic()
next_cap = t_start + 1.0
maxgap, last = 0.0, t_start
last_p = 0.0
cap = None  # {"no", "frames", "buf"} while a capture runs
fr = None   # the frame being captured: {"k", "p", "dch", "dlast", "mid", "fin", "late_seen"}


def snap(j, now_p, late):
    global prev_d, nsnap, ntorn
    w0, m0 = time.time(), time.monotonic()
    d0 = os.pread(fd, D[1], D[0])
    data = os.pread(fd, S[1], S[0])
    d1 = os.pread(fd, D[1], D[0])
    p1 = os.pread(fd, P0[1], P0[0])
    m1 = time.monotonic()
    torn = int(d0 != d1 or d0 != prev_d or p1 != now_p)
    name = "c%02d.f%d.s%s" % (cap["no"], fr["k"], j)
    cap["buf"].append((name, data))
    sl.write("c%02d f%d s%s wall %.4f mono %.6f since %.2f read %.2f torn %d late %d dch %d dlast %.2f\n" % (
        cap["no"], fr["k"], j, w0, m0, (m0 - fr["p"]) * 1000, (m1 - m0) * 1000, torn, late, fr["dch"], (fr["dlast"] - fr["p"]) * 1000))
    prev_d = d0  # a change during the read shows at the next poll
    nsnap += 1
    ntorn += torn


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
        if pch and m - last_p >= 0.001:
            last_p = m
            nfr += 1
            if fr is not None:
                sl.write("c%02d f%d frame mono %.6f end %.2f\n" % (cap["no"], fr["k"], fr["p"], (m - fr["p"]) * 1000))
                fr = None
            if cap is not None and len(cap["frames"]) >= K:
                flush_capture()
                next_cap = time.monotonic() + capgap
            elif cap is None and m >= next_cap:
                cap = {"no": ncap, "frames": [], "buf": []}
                ncap += 1
            if cap is not None:
                fr = {"k": len(cap["frames"]), "p": m, "dch": 0, "dlast": m, "mid": False, "fin": False, "late_seen": False}
                cap["frames"].append(fr)
            continue
        if pch:
            last_p = m
        if fr is None or fr["fin"]:
            continue
        age_f = m - fr["p"]
        if dch:
            fr["dch"] += 1
            fr["dlast"] = m
            if age_f >= TF0:
                fr["late_seen"] = True
            continue
        if not fr["mid"] and TM0 <= age_f <= TM1 and m - fr["dlast"] >= QM:
            snap("M", p, 0)
            fr["mid"] = True
        elif not fr["mid"] and age_f > TM1:
            fr["mid"] = True  # too late for a mid snapshot in this frame
        elif fr["mid"] and fr["late_seen"] and m - fr["dlast"] >= QF:
            snap("F", p, 1)
            fr["fin"] = True
        elif fr["mid"] and not fr["late_seen"] and age_f >= TF1:
            snap("F", p, 0)
            fr["fin"] = True
    except OSError as e:
        print("snapshot read error %s: stop" % e, flush=True)
        break
if cap is not None:
    if fr is not None:
        sl.write("c%02d f%d frame mono %.6f end -1\n" % (cap["no"], fr["k"], fr["p"]))
    flush_capture()
os.close(fd)
ev.close()
sl.close()
dur = time.monotonic() - t_start
print("# %d polls in %.1f s (mean period %.3f ms, largest gap %.1f ms); polls with a change: D %d, P %d; %d frames; %d captures, %d snapshots (%d torn)" % (
    polls, dur, 1000 * dur / max(polls, 1), 1000 * maxgap, nd, npc, nfr, ncap, nsnap, ntorn), flush=True)
