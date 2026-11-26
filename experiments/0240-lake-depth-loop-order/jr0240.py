#!/usr/bin/env python3
# BC5 experiment 0240: the order, frame by frame, of the night lake water's draws and the linear-depth pass that makes
# the water's slot-4 image, from a pixel-shader-filtered draw journal (patch 0001: BC5_DIRECT_DRAW_JOURNAL_PS with
# _EVERY; "draw journal buf N (D dwords) at P: ... | rt0 ... | ps ..." lines, in submission order).
# Frames are the intervals between the host's "frame profile: t <s>" lines (one per flip); submissions are the
# "timing: t ... dcb N dwords" lines (direct or "after that wait"). The graphics ring runs submissions in the order the
# journal shows them. Roles by pixel shader (exps 0201, 0239): 11d01ff900 water main (4 DRAW_INDEX_2; its vertex stage
# reads the slot-4 image 0x113cb40000), 11d01d7100 water full-screen, 11d0160b00 the writer of 0x113cb40000,
# 11d015f100 / 11d015f600 the downsamplers.
# Prints, per journal window (a gap of over 5 s in journal time starts one): the flip intervals with the matched draws
# by submission; then, for each water-main group, whether the writer of the same interval ran before or after it, and the
# interval of the last writer before it. Journal time maps to the wall clock as exp 0231's jr0231.py: the file's mtime
# minus (last time - t), +-1 s.
# usage: python3 -I jr0240.py <direct.log>
import collections, datetime, os, re, sys

path = sys.argv[1]
ROLE = {"11d01ff900": "water-main", "11d01d7100": "water-fs", "11d0160b00": "WRITER", "11d015f100": "down1",
        "11d015f600": "down2"}
T = re.compile(r"\bt (\d+\.\d+)")
DCB = re.compile(r"dcb (\d+) dwords")
DRAW = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+):.*\| rt0 (\S+) (\S+) .*\| ps (\S+) ")
events = []  # (kind, t, data)
t = 0.0
frame = 0
sub = 0
for line in open(path, errors="replace"):
    if line.startswith("frame profile: t "):
        m = T.search(line)
        if m:
            t = float(m[1])
        frame += 1
        sub = 0
        events.append(("flip", t, frame))
        continue
    if line.startswith("timing: t "):
        m = T.search(line)
        if m:
            t = float(m[1])
        if DCB.search(line):
            sub += 1
        continue
    m = DRAW.match(line)
    if m:
        ps = m[6].lower()
        events.append(("draw", t, (frame, sub, int(m[1]), int(m[3]), ROLE.get(ps, ps), m[4], m[5])))
last_t = t
end = os.path.getmtime(path)


def wall(tt):
    return datetime.datetime.fromtimestamp(end - (last_t - tt)).strftime("%H:%M:%S")


draws = [e for e in events if e[0] == "draw"]
print("# %s: %d matched draws; journal time %.1f..%.1f; wall = mtime %s - (last t %.1f - t)" % (
    path, len(draws), draws[0][1] if draws else 0, draws[-1][1] if draws else 0, wall(last_t), last_t))
windows = []
for e in draws:
    if not windows or e[1] - windows[-1][-1][1] > 5:
        windows.append([])
    windows[-1].append(e)
summary = collections.Counter()
for w in windows:
    print("== window at t %.1f (wall %s): %d draws" % (w[0][1], wall(w[0][1]), len(w)))
    byframe = collections.OrderedDict()
    for _, tt, (fr, sb, buf, at, role, rt, size) in w:
        byframe.setdefault(fr, []).append((sb, buf, at, role, rt, size, tt))
    for fr, items in byframe.items():
        seq = []
        for sb, buf, at, role, rt, size, tt in items:
            tag = "%s(sub %d, buf %d at %d, rt0 %s %s)" % (role, sb, buf, at, rt, size)
            if seq and seq[-1][0] == role and seq[-1][1] == sb:
                seq[-1][2] += 1
            else:
                seq.append([role, sb, 1, tag])
        print("  frame %d: %s" % (fr, " -> ".join("%s%s" % (s[3], " x%d" % s[2] if s[2] > 1 else "") for s in seq)))
    # the order question, per water-main group
    seen_writer = {}
    for _, tt, (fr, sb, buf, at, role, rt, size) in w:
        if role == "WRITER":
            seen_writer[fr] = (sb, at)
    last_writer_frame = None
    for _, tt, (fr, sb, buf, at, role, rt, size) in w:
        if role == "WRITER":
            last_writer_frame = fr
        if role == "water-main" and (not summary.get(("done", fr, sb))):
            summary[("done", fr, sb)] = 1
            same = seen_writer.get(fr)
            if same is None:
                rel = "no writer journalled in this frame"
            elif (same[0], same[1]) > (sb, at):
                rel = "BEFORE this frame's writer"
            else:
                rel = "after this frame's writer"
            prev = "frame %d" % last_writer_frame if last_writer_frame is not None else "none in the window"
            print("  water-main in frame %d sub %d: %s; last writer before it: %s" % (fr, sb, rel, prev))
            summary[rel] += 1
print("# water-main groups: " + ", ".join("%s %d" % (k, v) for k, v in summary.items() if isinstance(k, str)))
