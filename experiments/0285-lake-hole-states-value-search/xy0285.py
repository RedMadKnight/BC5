#!/usr/bin/env python3
# BC5 experiment 0285: exp 0283's full value search, X frames against Y frames, with exp 0283's st0283.py labels. In
# exp 0283 xy0283.py's own labels came from rd0283.py's family naming, which in W283b picked a one-read family as Y, so
# its search over every journalled value never ran (F344). Here, as st0283.py does, each depth read is classed at its
# frame's size by the share of the shots' cell mask at depth 0 (rd0283.py's "cells"): X-like at >= 0.5, Y-like at
# <= 0.3 with depth 0 on >= 0.15 of the lake window, no holes below 0.03, mixed otherwise; "?" when the read's shear at
# that size is above 3. A frame is X or Y when all its classed reads agree.
# The journal (exp 0251's private binary: _EVERY windows, edit0194.py's indirect arguments, patch0245.py's "bake db",
# patch0251.py's "bake db2"; _PS on the full-screen draw 0x11d01d7100 and the depth writers) is parsed as xy0283.py
# does (its line formats and frame rules: a frame is the draws up to its full-screen draw within one window, it starts
# at its first writer draw, its size is DB_DEPTH_SIZE_XY of the full-screen draw; reads go to the latest frame started
# at least L ms before them, L fitted on the clear reads' sizes as there, or given).
# Per frame, every journalled value: the full-screen draw's depth registers, size, user data and tables; each writer's
# number of draws; and per writer draw its packet's first dwords, depth registers, indirect arguments (at submission,
# at completion), user data and table dwords. Writer draws are keyed by shader and their order counted from the end of
# the frame ("@-1" = that shader's last draw in the frame), so a window's first frame, which may lack its first draws,
# still lines up; a key absent in a frame is left out for that frame.
# For lag offsets -1, 0 and +1 (the label of frame j against the values of frame j + offset in the same window, since
# a read's frame is known to about one frame), it prints:
#   - the keys compared and how many vary among the labelled frames;
#   - separators: keys present in >= 3 X and >= 3 Y frames whose X and Y values share none, and whose values repeat
#     (distinct values at most half the frames: a frame counter does not count);
#   - near separators: keys with at most 4 distinct values where the best value-to-state map is right in >= 90 % of
#     the frames (both states >= 3 frames), as the labels may be off by a frame here and there.
# Register, packet and argument values in hex; user-data and table dwords by key and position only. Runs on the box
# (stdlib only), on the title's data.
# usage: python3 -I xy0285.py <direct.log> <reads json> [L ms]
import collections, json, re, statistics, sys

log, rjson = sys.argv[1], sys.argv[2]
L_GIVEN = int(sys.argv[3]) if len(sys.argv) > 3 else None
FS = "11d01d7100"
H = lambda s: [int(x, 16) for x in s.split()]
RE_WIN = re.compile(r"^draw journal window from buf (\d+): t ([\d.]+) wall (\d+)\.(\d+)")
RE_DRAW = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+): ([0-9a-f ]*)\| rt0 .*\| ps ([0-9a-f]+) ")
RE_BAKE = re.compile(r"^bake draw buf (\d+) at (\d+): t ([\d.]+) wall (\d+)\.(\d+)")
RE_DB = re.compile(r"^bake db buf (\d+) at (\d+): depth_control (\S+) stencil_control \S+ refmask \S+ refmask_bf \S+ shader_control (\S+)"
                   r" render_control (\S+) render_override (\S+) \| z_info (\S+) stencil_info (\S+) view (\S+) size_xy (\S+) \| z_read (\S+)"
                   r" stencil_read \S+ z_write (\S+) stencil_write \S+ htile (\S+)")
RE_DB2 = re.compile(r"^bake db2 buf (\d+) at (\d+): htile_surface (\S+) render_override2 (\S+)")
RE_UD = re.compile(r"^bake ud (ps|gs) buf (\d+) at (\d+):((?: [0-9a-f]{8})+)")
RE_TAB = re.compile(r"^bake table (ps|gs) ud(\d+) ([0-9a-f]+):((?: [0-9a-f]{8})+)")
RE_ARGS = re.compile(r"^draw journal args buf (\d+) at (\d+): op (\S+) .*?\| max count (\d+) max inst (\d+), (\d+) zero, (\d+) over the CP limits[^|]*\|(.*)$")
RE_COMPL = re.compile(r"^args at completion: submit #\d+ buf (\d+) at (\d+) \S+: \[([0-9a-f ]+)\]")
draws, by_key, last = [], {}, None
win = -1
for line in open(log, errors="replace"):
    if not line.startswith(("draw journal", "bake ", "args at completion")):
        continue
    m = RE_WIN.match(line)
    if m:
        win += 1
        draws.append({"window": win})
        continue
    m = RE_DRAW.match(line)
    if m:
        d = {"key": (int(m[1]), int(m[3])), "win": win, "ps": m[5].lower(), "pkt": " ".join(m[4].split()[:4]), "ud": {},
             "tab": {}, "compl": []}
        draws.append(d)
        by_key[d["key"]] = d
        last = d
        continue
    m = RE_BAKE.match(line)
    if m and (int(m[1]), int(m[2])) in by_key:
        by_key[(int(m[1]), int(m[2]))].update(t=float(m[3]), wall=int(m[4]) + int(m[5]) / 1000)
        continue
    m = RE_DB.match(line)
    if m and (int(m[1]), int(m[2])) in by_key:
        sz = int(m[10], 16)
        by_key[(int(m[1]), int(m[2]))].update(db={"depth_control": m[3], "shader_control": m[4], "render_control": m[5],
                                                    "render_override": m[6], "z_info": m[7], "stencil_info": m[8], "view": m[9],
                                                    "z_read": m[11], "z_write": m[12], "htile": m[13]},
                                                size="%dx%d" % ((sz & 0x3fff) + 1, ((sz >> 16) & 0x3fff) + 1))
        continue
    m = RE_DB2.match(line)
    if m and (int(m[1]), int(m[2])) in by_key:
        by_key[(int(m[1]), int(m[2]))]["db2"] = "%s %s" % (m[3], m[4])
        continue
    m = RE_UD.match(line)
    if m and (int(m[2]), int(m[3])) in by_key:
        by_key[(int(m[2]), int(m[3]))]["ud"][m[1]] = H(m[4])
        continue
    m = RE_TAB.match(line)
    if m and last is not None:
        last["tab"]["%s%s" % (m[1], m[2])] = H(m[4])
        continue
    m = RE_ARGS.match(line)
    if m and (int(m[1]), int(m[2])) in by_key:
        by_key[(int(m[1]), int(m[2]))]["args"] = "op %s max %s inst %s zero %s |%s" % (m[3], m[4], m[5], m[6], " ".join(m[8].split()[:24]))
        continue
    m = RE_COMPL.match(line)
    if m and (int(m[1]), int(m[2])) in by_key:
        by_key[(int(m[1]), int(m[2]))]["compl"].append(m[3])
frames, cur, first = [], [], True
for d in draws:
    if "window" in d:
        cur, first = [], True
        continue
    cur.append(d)
    if d["ps"] == FS and "wall" in d:
        timed = [w for w in cur[:-1] if "wall" in w]
        frames.append({"win": d["win"], "wall": d["wall"], "size": d.get("size", "?"), "fs": d, "writers": cur[:-1],
                       "start": timed[0]["wall"] if timed else d["wall"], "first": first})
        cur, first = [], False
n_med = statistics.median(len(f["writers"]) for f in frames) if frames else 0
for f in frames:
    f["partial"] = f["first"] and len(f["writers"]) < n_med
gaps = [(b["start"] - a["start"]) * 1000 for a, b in zip(frames, frames[1:]) if a["win"] == b["win"]]
gap_med = statistics.median(gaps) / 1000 if gaps else 0.05
starts = [f["start"] for f in frames]
print("# %s: %d frames (%d partial first frames), median %d writer draws, frame interval median %.1f ms" % (
    log, len(frames), sum(f["partial"] for f in frames), n_med, gap_med * 1000))
reads = [r for r in json.load(open(rjson))["reads"] if r["kind"] == "z"]


def frame_of(r, lag):
    t = r["wall"] - lag / 1000
    j = None
    for i, w in enumerate(starts):
        if w <= t:
            j = i
    if j is None:
        return None
    nxt = starts[j + 1] if j + 1 < len(frames) and frames[j + 1]["win"] == frames[j]["win"] else starts[j] + 1.5 * gap_med
    return j if t < nxt else None


if L_GIVEN is None:
    scan = []
    for lag in range(-250, 255, 5):
        ok = n = 0
        for r in reads:
            if r["clear"] and (j := frame_of(r, lag)) is not None:
                n += 1
                ok += frames[j]["size"].split("x")[0] == str(r["best"])
        scan.append((lag, ok, n))
    n_max = max(n for _, _, n in scan)
    cand = [(ok / n, lag) for lag, ok, n in scan if n >= 0.6 * n_max and n > 0]
    best = max(c[0] for c in cand)
    tied = [lag for frac, lag in cand if frac == best]
    L = tied[len(tied) // 2]
    print("# L = %d ms fitted (%.0f %% of the matched clear reads have their frame's size)" % (L, best * 100))
else:
    L = L_GIVEN
    print("# L = %d ms given" % L)


def klass(r, size):
    e = r["sizes"].get(size.split("x")[0])
    if e is None or e["shear"] > 3:
        return "?"
    if e["share"] < 0.03:
        return "0"
    if e["cells"] >= 0.5:
        return "X"
    if e["cells"] <= 0.3 and e["share"] >= 0.15:
        return "Y"
    return "m"


per = collections.defaultdict(set)
for r in reads:
    j = frame_of(r, L)
    if j is not None:
        per[j].add(klass(r, frames[j]["size"]))
lab = {}
for j, s in per.items():
    s = s - {"?"}
    if len(s) == 1 and s <= {"X", "Y"}:
        lab[j] = s.pop()
print("# labelled frames: X %d (%d partial), Y %d (%d partial); frames with both: %d" % (
    sum(1 for v in lab.values() if v == "X"), sum(1 for j, v in lab.items() if v == "X" and frames[j]["partial"]),
    sum(1 for v in lab.values() if v == "Y"), sum(1 for j, v in lab.items() if v == "Y" and frames[j]["partial"]),
    sum(1 for s in per.values() if {"X", "Y"} <= s)))


def features(f):
    sc, vec = {"fs size": f["size"], "fs db2": f["fs"].get("db2")}, {}
    for k, x in f["fs"].get("db", {}).items():
        sc["fs db " + k] = x
    for st, u in f["fs"]["ud"].items():
        vec["fs ud " + st] = u
    for t, u in f["fs"]["tab"].items():
        vec["fs table " + t] = u
    if not f["partial"]:
        for ps, c in collections.Counter(d["ps"] for d in f["writers"]).items():
            sc["writer %s draws" % ps] = c
    back = collections.Counter()
    for d in reversed(f["writers"]):
        back[d["ps"]] += 1
        k = "%s@-%d" % (d["ps"], back[d["ps"]])
        sc[k + " pkt"] = d["pkt"]
        sc[k + " size"] = d.get("size")
        sc[k + " db2"] = d.get("db2")
        sc[k + " args"] = d.get("args")
        sc[k + " compl"] = " / ".join(d["compl"]) or None
        for a, x in d.get("db", {}).items():
            sc[k + " db " + a] = x
        for st, u in d["ud"].items():
            vec[k + " ud " + st] = u
        for t, u in d["tab"].items():
            vec[k + " table " + t] = u
    return {k: v for k, v in sc.items() if v is not None}, vec


feats = {}
for off in (-1, 0, 1):
    pairs = []  # (state, frame index of the values)
    for j, s in lab.items():
        k = j + off
        if 0 <= k < len(frames) and frames[k]["win"] == frames[j]["win"]:
            pairs.append((s, k))
    for _, k in pairs:
        if k not in feats:
            feats[k] = features(frames[k])
    nx, ny = sum(1 for s, _ in pairs if s == "X"), sum(1 for s, _ in pairs if s == "Y")
    print("== offset %+d: the values of frame j + %d against frame j's label: %d X and %d Y frames" % (off, off, nx, ny))
    if nx < 3 or ny < 3:
        print("   too few frames of a state")
        continue
    cols = collections.defaultdict(lambda: ([], []))
    for s, k in pairs:
        sc, vec = feats[k]
        for key, v in sc.items():
            cols[key][0 if s == "X" else 1].append(v)
        for key, u in vec.items():
            for q, v in enumerate(u):
                cols[(key, q)][0 if s == "X" else 1].append(v)
    n_keys = len(cols)
    vary = seps = 0
    rows_sep, rows_near = [], []
    for key, (a, b) in cols.items():
        if len(set(a + b)) <= 1:
            continue
        vary += 1
        if len(a) < 3 or len(b) < 3:
            continue
        if not set(a) & set(b):
            if len(set(a)) + len(set(b)) <= (len(a) + len(b)) / 2:
                seps += 1
                rows_sep.append((key, a, b))
            continue
        vals = set(a + b)
        if len(vals) <= 4:
            right = sum(max(a.count(v), b.count(v)) for v in vals)
            if right >= 0.9 * (len(a) + len(b)):
                rows_near.append((right / (len(a) + len(b)), key, a, b))
    print("   %d keys (scalars and table/user-data dwords) compared, %d vary among these frames; %d separate the states;"
          " %d near separators" % (n_keys, vary, seps, len(rows_near)))

    def show(key, a, b):
        if isinstance(key, tuple):  # a user-data or table dword: by position, with value letters only
            vals = list(dict.fromkeys(a + b))
            let = {v: "abcdefghij"[i] if i < 10 else "+" for i, v in enumerate(vals)}
            return "%s dword %d | X: %s | Y: %s" % (key[0], key[1], "".join(sorted(let[v] for v in a)),
                                                     "".join(sorted(let[v] for v in b)))
        return "%s | X: %s | Y: %s" % (key, "; ".join("%s x%d" % kv for kv in collections.Counter(a).most_common(3)),
                                        "; ".join("%s x%d" % kv for kv in collections.Counter(b).most_common(3)))

    for key, a, b in sorted(rows_sep, key=lambda r: str(r[0]))[:40]:
        print("   SEP %s" % show(key, a, b))
    for frac, key, a, b in sorted(rows_near, key=lambda r: (-r[0], str(r[1])))[:30]:
        print("   NEAR %.2f %s" % (frac, show(key, a, b)))
