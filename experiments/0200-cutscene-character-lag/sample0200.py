#!/usr/bin/env python3
# BC5 (experiment 0200): an outside sampler for the second title's cutscene slow motion. Read-only, no ptrace
# attach: it preads the running emulator's memory through /proc/<pid>/mem (yama ptrace_scope 0 on the box) and
# reads /proc. Lines (mono = CLOCK_MONOTONIC seconds):
#   c <mono> <clock> <mode> <div> <framedt> [<player> <clip> <adv> <debt> <last> <target> <rate> <srate> <fl>]...
#       every 1/HZ s, up to 6 players
#       clock  float at 0x90ae007b4: Wwise's GetSourcePlayPosition of the master voice in s (F198, exp 0153),
#              written by game-main, wraps at 10 s; mode byte at 0x90ae007be
#       div    double at 0x90bee5f48: the main player's advance divides the frame dt by it; framedt the double
#              at 0x90bee5f98, the frame dt the other players' path uses (clip advance function 0x903b77670)
#       player the main cinematic player found by find_player.py, and its +0xf8 clip time, +0xfc the advance
#              of its last tick (what the caller passes on to the secondary players), +0x100 debt (the
#              slew filter's carried error: how far the clip trails the clock's advance, x0.98), +0x110 the
#              clock unwrapped as of its last tick, +0x114 target (exp 0153 result 3; 0 between ticks),
#              +0x108 rate and srate (+0x560)->+0x50: the filtered advance is multiplied by
#              clamp(rate, 1e-4, 4) and by srate when fl bit 1 (sync source +0x30 & 0x80); fl bit 0
#              (+0x4c & 8) forces the rate to 1; fl 4: +0xc9 == 1, fl 8: synced (+0x120 & 3 == 3), with 4 the
#              clock-slewed path of 0x903b77670 (else the frame-dt path, 0x90bee5f98 x rate)
#       players are found by find_player.py: synced ones by the clock, then any main player with a vtable
#       learned from them; one is followed while its vtable stays and +0x548 & 1 (playing)
#   v <mono> d_compact_stall d_pgmajfault d_pswpin d_allocstall psi_mem_some10 psi_mem_full10 psi_io_some10
#       psi_io_full10 psi_cpu_some10 avail_MB wrap                                                 every 1 s
#       wrap   the clock's wrap period, float at 0x90bf72470 (10.0 for the clock voice, exp 0153)
#       then: key (u16 at 0x90ae007bc, the clock voice's entry), its playing id (entry +0xc in the table at
#       *(0x90bede218)), and the host's AJM instance counter (EXP0200_AJM_COUNTER, offset in the binary)
#   t <mono> <name>/<tid> run_ms wait_ms R S D other                                   every 1 s, per thread
#       run/wait: deltas of /proc/<pid>/task/<tid>/schedstat (on CPU, waiting for a CPU); R/S/D/other: how
#       many of the second's state samples (at HZ) found the thread running, sleeping, in uninterruptible wait
#   p <mono> scan new <players or none> (<finder output>) | p <mono> <player> lost         per scan / loss
# usage: sample0200.py <out> [hz]   (waits for kyty_emulator, ends with it)
import os, struct, subprocess, sys, time
FINDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "find_player.py")

OUT = sys.argv[1]
HZ = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
CLOCK, MODE = 0x90ae007b4, 0x90ae007be
DIV, FRAME_DT = 0x90bee5f48, 0x90bee5f98  # doubles: the main player's dt divisor; a frame dt (other players)
WRAP = 0x90bf72470
KEY, TABLE = 0x90ae007bc, 0x90bede218  # u16 entry index of the clock's voice; pointer to 32-byte entries (+0xc id)
# The host's AJM instance counter (KytyPlus ajm.cpp g_ajm_next_instance): its offset in the binary, from nm at
# launch (launch0200.sh); ids are codec << 14 | (counter & 0x3fff), so a slot is reissued every 16,384 creations.
AJM_COUNTER = int(os.environ.get("EXP0200_AJM_COUNTER", "0"), 16)
WATCH = ("game-main", "AK::AudioMgr", "AK::AudioOutThr", "AK::IOThread", "AK::BankMgr", "AK::JobWrkr",
         "Archive Resolve", "Archive Asset", "Archive Loose", "bc5-apr-q", "Render Thread", "SDLAudioP",
         "kyty-gpu", "kyty-present", "File Video", "Job Hi")
RESCAN = 20.0

def pgrep():  # no pgrep in the ubuntu distrobox
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                with open("/proc/%s/comm" % d) as f:
                    if f.read().strip() == "kyty_emulator":
                        return int(d)
            except OSError:
                pass
    return None

o = open(OUT, "a", buffering=1)
o.write("# sample0200 start %s hz %g\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), HZ))
pid = None
while pid is None:
    pid = pgrep()
    if pid is None:
        time.sleep(0.5)
time.sleep(2.0)
o.write("# pid %d at mono %.3f\n" % (pid, time.monotonic()))
fd = os.open("/proc/%d/mem" % pid, os.O_RDONLY)
host_base = 0
try:  # the PIE base: the binary's mapping at file offset 0 (guest memory is mapped below it)
    with open("/proc/%d/maps" % pid) as f:
        for line in f:
            q = line.split()
            if len(q) >= 6 and q[5].endswith("/kyty_emulator") and int(q[2], 16) == 0:
                host_base = int(q[0].split("-")[0], 16)
                break
except (OSError, ValueError):
    host_base = 0
o.write("# host base %x, AJM counter offset %x\n" % (host_base, AJM_COUNTER))

def rd(addr, n):
    try:
        return os.pread(fd, n, addr)
    except OSError:
        return None

def f32(addr):
    b = rd(addr, 4)
    return struct.unpack("<f", b)[0] if b and len(b) == 4 else float("nan")

def f64(addr):
    b = rd(addr, 8)
    return struct.unpack("<d", b)[0] if b and len(b) == 8 else float("nan")

def voice_state():  # "<key> <playing id hex> <ajm counter>" ("-" where unknown)
    k = rd(KEY, 2); tp = rd(TABLE, 8)
    pid_s = "-"
    if k and tp:
        e = rd(struct.unpack("<Q", tp)[0] + 32 * struct.unpack("<H", k)[0] + 0xc, 4)
        pid_s = ("%x" % struct.unpack("<I", e)[0]) if e else "-"
    cnt = "-"
    if AJM_COUNTER and host_base:
        b = rd(host_base + AJM_COUNTER, 4)
        cnt = str(struct.unpack("<I", b)[0]) if b else "-"
    return "%s %s %s" % (struct.unpack("<H", k)[0] if k else "-", pid_s, cnt)

def vmstat():
    d = {}
    with open("/proc/vmstat") as f:
        for line in f:
            k, v = line.split()
            d[k] = int(v)
    return (d.get("compact_stall", 0), d.get("pgmajfault", 0), d.get("pswpin", 0),
            d.get("allocstall_normal", 0) + d.get("allocstall_movable", 0) + d.get("allocstall_dma32", 0))

def psi(kind):
    try:
        with open("/proc/pressure/" + kind) as f:
            lines = f.read().split("\n")
        vals = []
        for l in lines[:2]:
            vals.append(l.split()[1].split("=")[1] if l else "-")
        return vals
    except OSError:
        return ["-", "-"]

def avail():
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    return -1

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

def player_ok(p):  # still the object found: same vtable, a main player (+0xc8 == 1) that plays (+0x548 & 1)
    b = rd(p, 0x5f8)
    if not b or len(b) < 0x5f8 or b[0xc8] != 1 or not (b[0x548] & 1):
        return False
    return struct.unpack_from("<Q", b, 0)[0] == vt_of.get(p)

tids = threads(); t_names = time.monotonic()
prev_ss = {t: schedstat(t) for t in tids}
st_count = {t: {"R": 0, "S": 0, "D": 0, "o": 0} for t in tids}
prev_vm = vmstat()
players = []; vt_of = {}; vts = set(); last_scan = 0.0; scan = None
MAXP = 6
t0 = time.monotonic(); nxt = t0; last_sec = t0
while os.path.exists("/proc/%d" % pid):
    now = time.monotonic()
    m = rd(MODE, 1)
    line = "c %.4f %.4f %d %.4f %.5f" % (now, f32(CLOCK), m[0] if m else -1, f64(DIV), f64(FRAME_DT))
    for player in players:
        b = rd(player, 0x568)
        if b and len(b) == 0x568:
            clip, adv, debt, rate, last, target = (struct.unpack_from("<f", b, o_)[0]
                                                   for o_ in (0xf8, 0xfc, 0x100, 0x108, 0x110, 0x114))
            p560 = struct.unpack_from("<Q", b, 0x560)[0]
            srate = f32(p560 + 0x50) if p560 else float("nan")
            src = struct.unpack_from("<Q", b, 0xb0)[0]
            sflag = rd(src + 0x30, 1) if src else None
            # fl: 1 rate forced to 1 (+0x4c & 8), 2 source rate applied (source +0x30 & 0x80), 4 +0xc9 == 1,
            # 8 synced (+0x120 & 3 == 3); 4 and 8 together select the clock-slewed path of 0x903b77670
            fl = ((1 if struct.unpack_from("<I", b, 0x4c)[0] & 8 else 0) | (2 if sflag and sflag[0] & 0x80 else 0)
                  | (4 if b[0xc9] == 1 else 0) | (8 if (b[0x120] & 3) == 3 else 0))
            line += " %x %.4f %.4f %.4f %.4f %.4f %.4f %.4f %d" % (player, clip, adv, debt, last, target, rate, srate, fl)
    o.write(line + "\n")
    for t in st_count:
        s = state(t)
        if s is not None:
            k = s if s in ("R", "S", "D") else "o"
            st_count[t][k] += 1
    if now - last_sec >= 1.0:
        last_sec = now
        vm = vmstat()
        d = [a - b for a, b in zip(vm, prev_vm)]; prev_vm = vm
        pm, pi, pc = psi("memory"), psi("io"), psi("cpu")
        o.write("v %.4f %d %d %d %d %s %s %s %s %s %d %.3f %s\n" % (now, d[0], d[1], d[2], d[3], pm[0], pm[1], pi[0],
                                                                     pi[1], pc[0], avail(), f32(WRAP), voice_state()))
        for t, name in tids.items():
            ss = schedstat(t)
            if ss is not None and prev_ss.get(t) is not None:
                c = st_count[t]
                o.write("t %.4f %s/%d %.1f %.1f %d %d %d %d\n" % (now, name, t, (ss[0] - prev_ss[t][0]) / 1e6,
                                                                (ss[1] - prev_ss[t][1]) / 1e6, c["R"], c["S"], c["D"], c["o"]))
            prev_ss[t] = ss
            st_count[t] = {"R": 0, "S": 0, "D": 0, "o": 0}
        if now - t_names >= 10.0:
            t_names = now
            new = threads()
            for t, name in new.items():
                if t not in tids:
                    prev_ss[t] = schedstat(t); st_count[t] = {"R": 0, "S": 0, "D": 0, "o": 0}
            tids = new
            st_count = {t: st_count.get(t, {"R": 0, "S": 0, "D": 0, "o": 0}) for t in tids}
        for player in [p for p in players if not player_ok(p)]:
            o.write("p %.4f %x lost\n" % (now, player)); players.remove(player)
        # The scan of the 104-MiB pool takes seconds of Python, so it runs as a child process at nice 19, every
        # RESCAN s (a cutscene can start while an ambient cinematic is followed); up to MAXP players are kept.
        if scan is not None and scan.poll() is not None:
            res = scan.stdout.read().decode("ascii", "replace"); scan = None
            syn, _, byv = res.partition("by vtable:")
            found = []
            for part, learn in ((syn.split("candidates:")[-1], True), (byv, False)):
                for w in part.replace(";", " ").split():
                    if w.startswith("0x") and "/" in w:
                        a, v = (int(x, 16) for x in w.split("/"))
                        found.append(a); vt_of.setdefault(a, v)
                        if learn:
                            vts.add(v)
            new = [f for f in dict.fromkeys(found) if f not in players and player_ok(f)][:max(0, MAXP - len(players))]
            players += new
            o.write("p %.4f scan new %s (%s)\n" % (time.monotonic(), " ".join("%x" % f for f in new) or "none",
                                                  res.strip()))
        if scan is None and now - last_scan >= RESCAN:
            last_scan = now
            scan = subprocess.Popen(["nice", "-n", "19", sys.executable, "-I", FINDER, str(pid)]
                                    + ["%x" % v for v in sorted(vts)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    nxt += 1.0 / HZ
    if nxt < time.monotonic():
        nxt = time.monotonic()
    time.sleep(max(0.0, nxt - time.monotonic()))
o.write("# end %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
