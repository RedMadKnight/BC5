#!/usr/bin/env python3
# BC5 experiment 0227: load times of each run from its read counters (<tag>-io.txt, io0227.sh) and its play log's
# fps counter (<tag>-play.log), on the box's uptime clock (the log's "bc5 clock: journal t 0 = monotonic" line maps the
# fps counter's t; the start file gives the emulator's start).
# Defined before the runs:
#   phases: "start" from the emulator's start; "level" from the input that starts the load the maintainer meant
#           (astro: the second cross, 75 s into the script; pkg: the Continue sequence, 85 s into the script, plus its
#           3.2 s of menu inputs);
#   load end: the first time, at least 2 s into the phase, from which the read rate (rchar, 1-s steps) stays under
#           5 MB/s for 5 s; load time = load end - phase start; MiB = bytes read in between;
#   gameplay: the first fps-counter second, at least 2 s into the level phase, that starts 3 seconds in a row with at
#           least 20 flips;
#   first frame: the first fps-counter second with a flip, from the emulator's start;
#   first lit: the first flip whose display buffer is at least 1 % non-black (BC5_DIRECT_FLIP_BRIGHT's journal lines,
#           <tag>-bright.txt), from the emulator's start: ASTRO BOT's first logo, "Sony Interactive Entertainment
#           presents" (added 2026-10-23 on the maintainer's report and the top session's request);
#   launch: the emulator's start after the launcher's (the mount and the launcher's own steps).
# The script's input thread starts with the emulator; its offset is the same in every arm.
# usage: load0227.py <title astro|pkg> <raw dir> <tag> ...
import re, sys

title, raw, tags = sys.argv[1], sys.argv[2], sys.argv[3:]
LEVEL_AT = 75.0 if title == "astro" else 85.0 + 3.2
QUIET_MBS, QUIET_S = 5.0, 5


def run(tag):
    start = None
    for line in open(f"{raw}/{tag}-start.txt", encoding="latin-1"):
        m = re.search(r"started at uptime ([0-9.]+)", line)
        if m:
            start = float(m.group(1))
    io = []
    for line in open(f"{raw}/{tag}-io.txt", encoding="latin-1"):
        f = line.split()
        if f and f[0] == "i" and len(f) >= 3:
            io.append((float(f[1]), int(f[2]), int(f[5]) if len(f) >= 6 else 0))
    launch = None
    for line in open(f"{raw}/{tag}-start.txt", encoding="latin-1"):
        m = re.search(r"launch at uptime ([0-9.]+)", line)
        if m:
            launch = float(m.group(1))
    t0 = None
    fps = []
    for line in open(f"{raw}/{tag}-play.log", encoding="latin-1"):
        m = re.match(r"bc5 clock: journal t 0 = monotonic ([0-9.]+)", line)
        if m and t0 is None:
            t0 = float(m.group(1))
        m = re.match(r"fps counter: t ([0-9.]+) s: (\d+) flips in ([0-9.]+) s", line)
        if m:
            fps.append((float(m.group(1)), int(m.group(2)) / float(m.group(3))))
    # 1-s read rates on the uptime clock
    steps = []
    k = 0
    if io:
        t = io[0][0]
        while t + 1 <= io[-1][0]:
            while k + 1 < len(io) and io[k + 1][0] <= t:
                k += 1
            j = k
            while j + 1 < len(io) and io[j + 1][0] <= t + 1:
                j += 1
            steps.append((t, (io[j][1] - io[k][1]) / 1e6 / max(io[j][0] - io[k][0], 1e-3), io[k][1]))
            t += 1

    def phase(p0):
        for i, (t, r, b) in enumerate(steps):
            if t < p0 + 2:
                continue
            nxt = steps[i:i + QUIET_S]
            if len(nxt) == QUIET_S and all(x[1] < QUIET_MBS for x in nxt):
                b0 = next((x[2] for x in steps if x[0] >= p0), steps[0][2])
                return t - p0, (b - b0) / 1048576
        return None, None

    res = {"tag": tag}
    res["start_s"], res["start_mib"] = phase(start)
    lvl = start + LEVEL_AT
    res["level_s"], res["level_mib"] = phase(lvl)
    res["gameplay_s"] = None
    res["first_s"] = None
    res["lit_s"] = None
    res["launch_s"] = start - launch if launch is not None and start is not None else None
    if t0 is not None:
        res["first_s"] = next((t0 + t - start for t, v in fps if v > 0), None)
        try:
            for line in open(f"{raw}/{tag}-bright.txt", encoding="latin-1"):
                m = re.match(r"flip bright: t ([0-9.]+) s flip \d+ buffer \d+: ([0-9.]+)% lit", line)
                if m and float(m.group(2)) >= 1.0:
                    res["lit_s"] = t0 + float(m.group(1)) - start
                    break
        except OSError:
            pass
        f = [(t0 + t, v) for t, v in fps]
        for i in range(len(f) - 2):
            if f[i][0] >= lvl + 2 and all(x[1] >= 20 for x in f[i:i + 3]):
                res["gameplay_s"] = f[i][0] - lvl
                break
    res["total_mib"] = (io[-1][1] - io[0][1]) / 1048576 if io else 0
    # bytes written (write_bytes) from the emulator's start to the end of the startup reads, and in all
    res["wr_start_mib"] = None
    if io and res["start_s"] is not None:
        upto = [x for x in io if x[0] <= start + res["start_s"]]
        res["wr_start_mib"] = (upto[-1][2] - io[0][2]) / 1048576 if upto else None
    res["wr_total_mib"] = (io[-1][2] - io[0][2]) / 1048576 if io else 0
    return res


def fmt(v, p="%.1f"):
    return "-" if v is None else p % v


print(f"{'run':10s} {'launch s':>8s} {'first frame s':>13s} {'first lit s':>11s} {'start load s':>12s} {'MiB':>7s} {'level load s':>12s} {'MiB':>7s} {'gameplay s':>10s} {'read MiB':>9s} {'wr startup':>10s} {'wr MiB':>7s}")
for tag in tags:
    r = run(tag)
    print(f"{tag:10s} {fmt(r.get('launch_s')):>8s} {fmt(r['first_s']):>13s} {fmt(r.get('lit_s')):>11s} {fmt(r['start_s']):>12s} {fmt(r['start_mib'], '%.0f'):>7s} {fmt(r['level_s']):>12s} "
          f"{fmt(r['level_mib'], '%.0f'):>7s} {fmt(r['gameplay_s']):>10s} {r['total_mib']:9.0f} "
          f"{fmt(r['wr_start_mib'], '%.0f'):>10s} {r['wr_total_mib']:7.0f}")
