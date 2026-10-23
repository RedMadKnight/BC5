#!/usr/bin/env python3
# BC5 experiment 0231: a timeline of one direct journal (play-*/gc/direct.log) in wall-clock bins, for comparing a
# clean and a patched lake run. Journal time is the last "t <seconds>" seen ("timing: t ...", "frame profile: t ... s");
# wall clock = the journal file's mtime minus (last journal time - t), as the TCP session maps it (about +-1 s if the
# tail was flushed). Per bin: direct merges (the host merging imported direct-memory chunks into BOs, ADR 0006: a sign
# that new direct memory got data, e.g. streamed pages), the BO count after the last merge, mappings moved, learned
# applies, scratch windows, gpu-check lines, flips (frame profile lines) and their mean and max "since the last flip".
# usage: python3 -I jr0231.py <direct.log> [bin seconds, default 5] [from HH:MM:SS] [to HH:MM:SS]
import collections, datetime, os, re, sys

path = sys.argv[1]
binw = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
T = re.compile(r"\bt (\d+\.\d+)")
MERGE = re.compile(r"^direct merge: (\d+) BOs became (\d+) \((\d+) BOs now\), (\d+) mappings moved")
FP = re.compile(r"^frame profile: t ([\d.]+) s, ([\d.]+) ms since the last flip")
rows = []  # (t, kind, value...)
t = 0.0
for line in open(path, errors="replace"):
    if line.startswith("timing: t ") or line.startswith("frame profile: t "):
        m = T.search(line)
        if m:
            t = float(m[1])
    if line.startswith("direct merge:"):
        m = MERGE.match(line)
        if m:
            rows.append((t, "merge", int(m[3]), int(m[4])))
    elif line.startswith("learned apply"):
        rows.append((t, "learned", 0, 0))
    elif line.startswith("scratch: window"):
        rows.append((t, "scratch", 0, 0))
    elif line.startswith("gpu check"):
        rows.append((t, "gpucheck", 0, 0))
    elif line.startswith("frame profile:"):
        m = FP.match(line)
        if m:
            rows.append((t, "flip", float(m[2]), 0))
mtime = datetime.datetime.fromtimestamp(os.stat(path).st_mtime)
wall = lambda x: mtime - datetime.timedelta(seconds=t - x)
lo = sys.argv[3] if len(sys.argv) > 3 else "00:00:00"
hi = sys.argv[4] if len(sys.argv) > 4 else "23:59:59"
bins = collections.OrderedDict()
for r in rows:
    w = wall(r[0])
    if not (lo <= w.strftime("%H:%M:%S") <= hi):
        continue
    key = w.replace(microsecond=0) - datetime.timedelta(seconds=w.second % int(binw))
    b = bins.setdefault(key, {"merge": 0, "bos": None, "moved": 0, "learned": 0, "scratch": 0, "gpucheck": 0, "flips": [], })
    if r[1] == "merge":
        b["merge"] += 1; b["bos"] = r[2]; b["moved"] += r[3]
    elif r[1] == "flip":
        b["flips"].append(r[2])
    else:
        b[r[1]] += 1
print("# %s: last journal t %.3f s at %s (file mtime); bins of %g s" % (path, t, mtime.strftime("%H:%M:%S.%f")[:-3], binw))
print("wall      merges BOs moved learned scratch gpuchk flips mean_ms max_ms")
for k, b in bins.items():
    f = b["flips"]
    print("%s %6d %4s %5d %7d %7d %6d %5d %7.1f %6.1f" % (k.strftime("%H:%M:%S"), b["merge"], b["bos"] if b["bos"] is not None else "-",
          b["moved"], b["learned"], b["scratch"], b["gpucheck"], len(f), sum(f) / len(f) if f else 0, max(f) if f else 0))
