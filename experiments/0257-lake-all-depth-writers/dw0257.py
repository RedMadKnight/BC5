#!/usr/bin/env python3
# BC5 experiment 0257: every draw that writes the night lake's depth buffer before the full-screen water draw, per frame,
# from an UNFILTERED draw journal repeated through one run (BC5_DIRECT_DRAW_JOURNAL=<t0>:<buffers> with
# BC5_DIRECT_DRAW_JOURNAL_EVERY, no _PS; exp 0251's private binary). Lines read:
#   "draw journal window from buf N: t T wall S.MS" (edit0194.py), "draw journal buf N (D dwords) at P: <packet> | rt0
#   <base> <w>x<h> info .. mask <mask> | vp .. | ps <ps> es .. gs .. cs ..", the "bake db buf N at P: depth_control ..
#   | z_info .. | z_read .. stencil_read .. z_write <base> .." line after it (patch0245.py), and "draw journal args buf
#   N at P: ... | [args]" for indirect draws (edit0194.py).
# DB_DEPTH_CONTROL Z_ENABLE bit 1, Z_WRITE_ENABLE bit 2 (Mesa gfx10 register JSON, tools/bc5-agc/regdb/gfx10.json). A
# depth writer is a draw (not a dispatch) with both set whose z_write base is the lake's depth buffer (0x1129ec0000,
# F305). Frames are split at the full-screen water draw (PS 0x11d01d7100); a frame's writers are those since the
# frame's own HTILE + stencil fill (CS 0x11d0288a00, 2752 or more groups, F310); a frame without its fill in the window is
# not counted. Window state from the bench's shots (exp 0197's metric: clean both under 5 %, patched both 8 % or more).
# Prints:
#  (1) per state: frames, writers per frame (median, range), colour-mask-0 writers per frame;
#  (2) per pixel shader: draws per frame by state (median and range), colour mask 0 or not, packet opcodes, and the summed
#      first indirect argument (vertex or index count x instances) per frame by state;
#  (3) shaders seen in one state's frames and never in the other's.
# Prints summaries only.
# usage: python3 -I dw0257.py <direct.log> <bench.txt> [z base hex, default 1129ec0000]
import collections, re, statistics, sys, time

path, bench = sys.argv[1], sys.argv[2]
ZB = (sys.argv[3] if len(sys.argv) > 3 else "1129ec0000").lower()
FS = "11d01d7100"
shots = []
for l in open(bench):
    m = re.match(r"\s*(\d{6})-(ts\d\d)\.png: patch\s+([\d.]+) %", l)
    if m:
        shots.append((m[1], float(m[3])))
WIN = re.compile(r"^draw journal window from buf (\d+): t ([\d.]+) wall (\d+)\.(\d+)")
DRAW = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+):((?: [0-9a-f]{8})*) \| rt0 (\S+) (\S+) info \S+ mask (\S+) .*\| ps (\S+) .* cs (\S+)")
DB = re.compile(r"^bake db buf (\d+) at (\d+): depth_control (\S+) .* z_write (\S+) ")
ARGS = re.compile(r"^draw journal args buf (\d+) at (\d+): .*\|( \[.*)?$")


def state_of(hms):
    if hms is None:
        return "unknown"
    prev = [s for s in shots if s[0] <= hms]
    nxt = [s for s in shots if s[0] >= hms]
    p, n = (prev[-1] if prev else None), (nxt[0] if nxt else None)
    if p and n and p[1] < 5 and n[1] < 5:
        return "clean"
    if p and n and p[1] >= 8 and n[1] >= 8:
        return "patched"
    return "mixed"


frames, cur_frame, hms, pend = [], None, None, {}
win_key = None
for line in open(path, errors="replace"):
    m = WIN.match(line)
    if m:
        h = time.strftime("%H%M%S", time.localtime(int(m[3])))
        if h != hms:
            # A new window: frames do not run across windows. Its first frame runs from the window's start; it counts
            # as complete only if the frame's HTILE + stencil fill (CS 0x11d0288a00 with 2752 or more 1-KiB groups,
            # F310) comes before its first depth write.
            hms, cur_frame = h, {"writers": [], "size": None, "from_start": True, "fill": False}
        continue
    m = DRAW.match(line)
    if m:
        words = m[4].split()
        op = (int(words[0], 16) >> 8) & 0xff if words else -1
        ps = m[8].lower()
        if ps == FS:
            if cur_frame is not None and cur_frame.get("fill"):
                cur_frame["state"] = state_of(hms)
                cur_frame["size"] = m[6]
                frames.append(cur_frame)
            cur_frame = {"writers": [], "size": m[6], "fill": False}
            continue
        if op == 0x15 and m[9].lower() == "11d0288a00" and len(words) > 1 and int(words[1], 16) >= 2752 and cur_frame is not None:
            # The frame's own HTILE + stencil fill: its depth starts here, so writers before it (the previous frame's
            # passes after its full-screen draw) are dropped and every frame counts from fill to full-screen draw.
            cur_frame["fill"] = True
            cur_frame["writers"] = []
        if op in (0x15, 0x16) or cur_frame is None:
            continue
        pend = {"key": (m[1], m[3]), "ps": ps, "mask": m[7], "op": op, "args": None, "frame": cur_frame}
        continue
    m = DB.match(line)
    if m and pend and (m[1], m[2]) == pend["key"]:
        dc = int(m[3], 16)
        if (dc >> 1) & 1 and (dc >> 2) & 1 and m[4].lower() == ZB:
            pend["frame"]["writers"].append(pend)
            pend["counted"] = True
        continue
    m = ARGS.match(line)
    if m and pend and (m[1], m[2]) == pend["key"] and pend.get("counted"):
        a = re.findall(r"\[([^\]]*)\]", m[3] or "")
        if a:
            v = [int(x, 16) for x in a[0].split()]
            pend["args"] = v[0] * (v[1] if len(v) > 1 else 1)

print("# %s: %d complete frames in the journal windows (frames split at PS %s; depth buffer %s)" % (path, len(frames), FS, ZB))
by_state = collections.defaultdict(list)
for f in frames:
    by_state[f["state"]].append(f)


def med(v):
    return "%s (%s..%s)" % (statistics.median(v), min(v), max(v)) if v else "-"


print("(1) per state")
for st, fs in sorted(by_state.items()):
    print("  %-8s %3d frames: writers/frame %s; colour-mask-0 writers/frame %s; sizes %s" % (
        st, len(fs), med([len(f["writers"]) for f in fs]), med([sum(w["mask"] == "00000000" for w in f["writers"]) for f in fs]),
        ", ".join("%s %d" % kv for kv in sorted(collections.Counter(f["size"] for f in fs).items()))))
print("(2) per pixel shader: draws per frame and summed first indirect argument per frame, by state")
shaders = sorted({w["ps"] for f in frames for w in f["writers"]})
for ps in shaders:
    ws = [w for f in frames for w in f["writers"] if w["ps"] == ps]
    masks = collections.Counter("mask0" if w["mask"] == "00000000" else "colour" for w in ws)
    ops = collections.Counter("%02x" % w["op"] for w in ws)
    parts = []
    for st, fs in sorted(by_state.items()):
        n = [sum(w["ps"] == ps for w in f["writers"]) for f in fs]
        a = [sum(w["args"] or 0 for w in f["writers"] if w["ps"] == ps) for f in fs]
        parts.append("%s %s draws, args %s" % (st, med(n), med(a) if any(a) else "-"))
    print("  %s [%s; ops %s]: %s" % (ps, ", ".join("%s %d" % kv for kv in masks.items()), ",".join(sorted(ops)), " | ".join(parts)))
print("(3) shaders in one state's frames and never in another's")
seen = {st: {w["ps"] for f in fs for w in f["writers"]} for st, fs in by_state.items()}
for a in sorted(seen):
    for b in sorted(seen):
        if a != b:
            print("  in %s, never in %s: %s" % (a, b, " ".join(sorted(seen[a] - seen[b])) or "-"))
