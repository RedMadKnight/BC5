#!/usr/bin/env python3
# BC5 experiment 0231: per frozen-view shot of a lake-bench run, the shot's patch share (exp 0197's patch0197.py) against
# the frame times the run's direct journal recorded in the WIN seconds before the shot ("frame profile: t <s> s, <ms> ms
# since the last flip"). Journal time is mapped to wall clock as jr0231.py does (file mtime minus the last journal time).
# Output per shot: run, shot, patch share, frames in the window, mean and max frame ms, frames over 300 ms.
# Run in the ubuntu container (patch0197.py needs PIL), at idle priority.
# usage: python3 -I corr0231.py <run dir> [<run dir> ...]    (run dir = ~/bc5-work/exp0194/r-<tag>)
import datetime, glob, os, re, subprocess, sys

WIN = float(os.environ.get("WIN", "5"))
PATCH = os.path.expanduser("~/bc5-work/exp0197/patch0197.py")
T = re.compile(r"\bt (\d+\.\d+)")
FP = re.compile(r"^frame profile: t ([\d.]+) s, ([\d.]+) ms since the last flip")
print("run    shot  wall      patch%  frames  mean_ms  max_ms  over300")
for rd in sys.argv[1:]:
    tag = os.path.basename(rd.rstrip("/"))[2:]
    jd = open(os.path.join(rd, "journal-dir.txt")).read().strip()
    path = os.path.join(jd, "direct.log")
    flips, t = [], 0.0
    for line in open(path, errors="replace"):
        if line.startswith("timing: t ") or line.startswith("frame profile: t "):
            m = T.search(line)
            if m:
                t = float(m[1])
            if line.startswith("frame profile:"):
                m = FP.match(line)
                if m:
                    flips.append((float(m[1]), float(m[2])))
    mtime = datetime.datetime.fromtimestamp(os.stat(path).st_mtime)
    shots = sorted(glob.glob(os.path.join(rd, "shots", "*-ts*.png")))
    out = subprocess.run([sys.executable, PATCH] + shots, capture_output=True, text=True).stdout
    share = {os.path.basename(l.split(":")[0]): float(l.split()[-2]) for l in out.splitlines() if "patch" in l}
    day = mtime.date()
    for s in shots:
        b = os.path.basename(s)
        hh, mm, ss = int(b[0:2]), int(b[2:4]), int(b[4:6])
        sw = datetime.datetime.combine(day, datetime.time(hh, mm, ss))
        st = t - (mtime - sw).total_seconds()  # the shot's time on the journal clock
        win = [ms for ft, ms in flips if st - WIN <= ft <= st]
        print("%-6s %-5s %s %6.1f  %6d  %7.1f  %6.1f  %7d" % (tag, b[7:11], sw.strftime("%H:%M:%S"), share.get(b, -1),
              len(win), sum(win) / len(win) if win else 0, max(win) if win else 0, sum(1 for x in win if x > 300)))
