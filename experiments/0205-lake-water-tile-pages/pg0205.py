#!/usr/bin/env python3
# BC5 experiment 0205: an outside, read-only sampler of the water's streamed textures (exp 0201 README, X2/X3). It preads
# the running emulator's memory through /proc/<pid>/mem (yama ptrace_scope 0 on the box, as exp 0200's sampler;
# no ptrace attach) and reads /proc/<pid>/maps. Every STEP s, per 16-KiB tile (the smallest automatic AMM map) of
# each range, one character:
#   '.' no mapping that can hold data (no VMA, or a VMA without read permission: a hole of the AMM window)
#   'z' mapped, all zero
#   'd' mapped, data (some byte non-zero)
#   'e' the read failed
# and per range the counts, the tiles that changed state since the last sample, and the tiles whose backing
# (VMA start and file offset, i.e. the dmem page) changed: a re-map of that tile to other memory.
# Lines: "s <mono> <wall> <range> . <n> z <n> d <n> e <n> | to. <n> toz <n> tod <n> remap <n>" and every
# FULL-th sample "m <mono> <range> <tile string>".
# usage: python3 -I pg0205.py <out> [step s] [full every n] [base:size ...]   (default: the two pixel-stage
#        textures of PS 0x11d01ff900, 8 MiB at 0x8492504000 and 2 MiB at 0x80907c4000)
import bisect, os, sys, time

OUT = sys.argv[1]
STEP = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
FULL = int(sys.argv[3]) if len(sys.argv) > 3 else 6
RANGES = [(int(b, 16), int(s, 16)) for b, s in (a.split(":") for a in sys.argv[4:])] or \
    [(0x8492504000, 0x800000), (0x80907c4000, 0x200000)]
TILE = 0x4000


def find_pid():
    best = None
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                with open("/proc/%s/comm" % d) as f:
                    if f.read().strip() == "kyty_emulator" and (best is None or int(d) > best):
                        best = int(d)
            except OSError:
                pass
    return best


def vmas(pid):
    # /proc/<pid>/maps is sorted by address. In the AMM window a mapped tile is a "rw-s" VMA of
    # /memfd:KytyDirectMemory whose offset is the dmem offset; a hole is "---p" anonymous (seen 2026-10-22, ~23k VMAs).
    out = []
    with open("/proc/%d/maps" % pid) as f:
        for line in f:
            p = line.split()
            lo, hi = (int(x, 16) for x in p[0].split("-"))
            out.append((lo, hi, p[1], int(p[2], 16)))
    return [v[0] for v in out], out


def covering(vs, a):
    los, out = vs
    i = bisect.bisect_right(los, a) - 1
    if i >= 0 and a < out[i][1]:
        lo, hi, perm, off = out[i]
        return lo, perm, off + (a - lo)
    return None


o = open(OUT, "a", buffering=1)
pid = int(os.environ.get("PG0205_PID", "0")) or None  # for a dry test on another process
for _ in range(0 if pid else 120):
    pid = find_pid()
    if pid:
        break
    time.sleep(1)
if not pid:
    sys.exit("no kyty_emulator")
fd = os.open("/proc/%d/mem" % pid, os.O_RDONLY)
o.write("# pid %d ranges %s tile 0x%x step %.1f s\n" % (pid, " ".join("0x%x:0x%x" % r for r in RANGES), TILE, STEP))
prev = {}
n = 0
while os.path.exists("/proc/%d" % pid):
    t = time.monotonic()
    wall = time.strftime("%H:%M:%S")
    try:
        vs = vmas(pid)
    except (OSError, ValueError):
        break
    for base, size in RANGES:
        states, backs = [], []
        for a in range(base, base + size, TILE):
            c = covering(vs, a)
            if c is None or "r" not in c[1]:
                states.append(".")
                backs.append(None)
                continue
            try:
                data = os.pread(fd, TILE, a)
                states.append("z" if data.count(0) == len(data) else "d")
            except OSError:
                states.append("e")
            backs.append((c[0], c[2]))
        s = "".join(states)
        cnt = {k: s.count(k) for k in ".zde"}
        ps, pb = prev.get(base, (None, None))
        ch = {".": 0, "z": 0, "d": 0}
        remap = 0
        if ps is not None:
            for i, (x, y) in enumerate(zip(ps, s)):
                if x != y and y in ch:
                    ch[y] += 1
                if pb[i] is not None and backs[i] is not None and pb[i] != backs[i]:
                    remap += 1
        prev[base] = (s, backs)
        o.write("s %.3f %s 0x%x . %d z %d d %d e %d | to. %d toz %d tod %d remap %d\n" % (
            t, wall, base, cnt["."], cnt["z"], cnt["d"], cnt["e"], ch["."], ch["z"], ch["d"], remap))
        if n % FULL == 0:
            o.write("m %.3f 0x%x %s\n" % (t, base, s))
    n += 1
    time.sleep(max(0.0, STEP - (time.monotonic() - t)))
o.write("# end %s\n" % time.strftime("%H:%M:%S"))
