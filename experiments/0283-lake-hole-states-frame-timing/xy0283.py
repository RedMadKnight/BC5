#!/usr/bin/env python3
# BC5 experiment 0283: which journalled frames are X and which Y (F342), and what differs between them. Inputs: the run's
# draw journal (exp 0251's private binary: BC5_DIRECT_DRAW_JOURNAL with edit0194.py's _EVERY windows and indirect
# arguments, patch0245.py's "bake db" and patch0251.py's "bake db2" lines; _PS on the full-screen water draw and the
# depth writers) and rd0283.py's per-read summary (JSON).
# The journal, per draw matched by _PS (keyed by buffer number and offset, which keep counting across windows):
#   "draw journal buf N (D dwords) at P: <packet dwords> | rt0 .. | ps PS es .. gs .. cs .."
#   "bake draw buf N at P: t T wall S.MS | .."           (journal time, CLOCK_MONOTONIC based; wall clock, ms)
#   "bake db buf N at P: depth_control .. | z_info .. stencil_info .. view .. size_xy .. | z_read .. z_write .. htile .."
#   "bake db2 buf N at P: htile_surface .. render_override2 .."
#   "bake ud ps|gs buf N at P: <32 user-data dwords>", then "bake table ps|gs udK ADDR: <64 dwords>" (the draw before)
#   "draw journal args buf N at P: op .. | max count A max inst B, Z zero, .. | [args] .."   (at submission)
#   "args at completion: submit #n buf N at P ADDR: [a b c d] submitted [..]"            (as the GPU left them)
#   "draw journal window from buf N: t T wall S.MS"
# A frame is the run of draws up to and including a full-screen draw (PS 0x11d01d7100) within one window; the first
# frame of a window counts as partial when it has fewer writer draws than the median frame. Its start is its first
# writer draw's wall clock (the depth writers run before the full-screen draw is journalled), its size DB_DEPTH_SIZE_XY
# X_MAX+1 x Y_MAX+1 (bits 13:0, 29:16; Mesa gfx10 register JSON, tools/bc5-agc/regdb/gfx10.json) of the full-screen
# draw's "bake db" line.
# Matching: a read at wall time r is taken to show frame j, the latest frame that started at least L ms before r, and
# before the next frame's start (or, for a window's last frame, within 1.5 median frame intervals). L is the lag, in
# -250..250 ms, at which the largest share of the matched clear reads (rd0283.py) has its best size equal to its
# frame's size (among lags that match at least 60 % as many clear reads as the best-matching lag; ties: the middle
# one). A read's state at its frame's size: no holes (depth-0
# share < 0.03), X (>= 80 % of its depth-0 pixels in X's set), Y (likewise), or mixed; "?" when the read's shear at
# that size is above 3 (the decode is doubtful). A frame is X or Y when all its reads agree.
# Then, X frames against Y frames, every journalled value per frame: the full-screen draw's depth registers and size,
# each writer's draw count, and per writer draw (by shader and its order in the frame) the packet's first dwords, the
# depth registers, the indirect arguments at submission and at completion, the 32 user-data dwords of each stage and
# the 64 dwords of each table they point at. A value separates the states when its X frames' and Y frames' values
# have no value in common (both with >= 3 frames) and its values repeat (fewer distinct values than half the frames;
# a value new in every frame, such as a frame counter, is only counted). Prints counts, keys and positions; register, packet and argument
# values in hex; no user-data or table values. Runs on the box (stdlib only), on the title's data.
# usage: python3 -I xy0283.py <direct.log> <reads json>
import collections, json, re, statistics, sys

log, rjson = sys.argv[1], sys.argv[2]
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
        frames.append({"win": d["win"], "wall": d["wall"], "t": d["t"], "size": d.get("size", "?"), "fs": d, "writers": cur[:-1],
                       "start": timed[0]["wall"] if timed else d["wall"], "first": first})
        cur, first = [], False
n_med = statistics.median(len(f["writers"]) for f in frames) if frames else 0
for f in frames:
    f["partial"] = f["first"] and len(f["writers"]) < n_med
spans = [(f["wall"] - f["start"]) * 1000 for f in frames if not f["partial"]]
if spans:
    print("# writers per frame: median %d; first writer draw to the full-screen draw: median %.1f ms, %.1f..%.1f" % (
        n_med, statistics.median(spans), min(spans), max(spans)))
print("# %s: %d windows, %d journalled draws, %d frames (%d whole)" % (log, win + 1, sum(1 for d in draws if "key" in d),
                                                                     len(frames), sum(1 for f in frames if not f["partial"])))
gaps = [(b["start"] - a["start"]) * 1000 for a, b in zip(frames, frames[1:]) if a["win"] == b["win"]]
if gaps:
    print("  frame intervals within windows: %d, median %.1f ms, %.1f..%.1f; the sizes change at %d of %d frame boundaries" % (
        len(gaps), statistics.median(gaps), min(gaps), max(gaps),
        sum(1 for a, b in zip(frames, frames[1:]) if a["win"] == b["win"] and a["size"] != b["size"]), len(gaps)))
data = json.load(open(rjson))
reads = [r for r in data["reads"] if r["kind"] == "z"]
starts = [f["start"] for f in frames]
gap_med = statistics.median(gaps) / 1000 if gaps else 0.05


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


print("# lag L (ms): clear reads whose best size equals their frame's size, of the clear reads matched")
scan = []
for lag in range(-250, 255, 5):
    ok = n = 0
    for r in reads:
        if not r["clear"]:
            continue
        j = frame_of(r, lag)
        if j is None:
            continue
        n += 1
        ok += frames[j]["size"].split("x")[0] == str(r["best"])
    scan.append((lag, ok, n))
    print("  L %4d: %d of %d" % (lag, ok, n))
n_max = max(n for _, _, n in scan)
cand = [(ok / n, lag) for lag, ok, n in scan if n >= 0.6 * n_max and n > 0]
best_frac = max(c[0] for c in cand)
tied = [lag for frac, lag in cand if frac == best_frac]
L = tied[len(tied) // 2]  # the middle of the lags that agree best
okL, nL = next((ok, n) for lag, ok, n in scan if lag == L)
print("# L = %d ms (%d of %d matched clear reads agree; lags %d..%d ms agree as well)" % (L, okL, nL, tied[0], tied[-1]))


def state(r, size):
    e = r["sizes"].get(size.split("x")[0])
    if e is None:
        return "?"
    if e["shear"] > 3:
        return "?"
    if e["share"] < 0.03:
        return "0"
    if e.get("inX", 0) >= 0.8:
        return "X"
    if e.get("inY", 0) >= 0.8:
        return "Y"
    return "m"


labels = collections.defaultdict(list)
print("# reads: frame (window, index in run), time after the frame's start, frame size, best size, state")
for r in reads:
    j = frame_of(r, L)
    if j is None:
        print("  %-7s wall %.4f: no frame (outside the journal windows)" % (r["name"], r["wall"]))
        continue
    f = frames[j]
    s = state(r, f["size"])
    labels[j].append(s)
    print("  %-7s wall %.4f: frame w%02d #%d +%.1f ms after its start, size %s, best %d%s, state %s" % (
        r["name"], r["wall"], f["win"], j, (r["wall"] - f["start"]) * 1000, f["size"], r["best"], "" if r["clear"] else "?", s))
lab = {}
for j, ss in labels.items():
    k = set(ss) - {"?"}
    lab[j] = k.pop() if len(k) == 1 else ("conflict" if len(k) > 1 else "?")
print("# frames by window (size:state; '.' no read matched; '*' partial first frame)")
for w in range(win + 1):
    fr = [(j, f) for j, f in enumerate(frames) if f["win"] == w]
    if fr:
        print("  w%02d t %.3f: %s" % (w, fr[0][1]["t"], " ".join("%s%s:%s" % ("*" if f["partial"] else "", f["size"].split("x")[0],
                                                                             lab.get(j, ".")) for j, f in fr)))
cnt = collections.Counter(lab.values())
print("# frame labels: %s" % ", ".join("%s %d" % kv for kv in sorted(cnt.items())))


def features(f):
    v = {"fs size": f["size"], "fs db2": f["fs"].get("db2", "-"), "interval": None}
    for k, x in f["fs"].get("db", {}).items():
        v["fs db " + k] = x
    n = collections.Counter(d["ps"] for d in f["writers"])
    for ps, c in n.items():
        v["writer %s draws" % ps] = c
    order = collections.Counter()
    vec = {}
    for d in f["writers"]:
        o = order[d["ps"]]
        order[d["ps"]] += 1
        k = "%s#%d" % (d["ps"], o)
        v[k + " pkt"] = d["pkt"]
        v[k + " size"] = d.get("size", "-")
        for a, x in d.get("db", {}).items():
            v[k + " db " + a] = x
        v[k + " db2"] = d.get("db2", "-")
        v[k + " args"] = d.get("args", "-")
        v[k + " compl"] = " / ".join(d["compl"]) or "-"
        for st, u in d["ud"].items():
            vec[k + " ud " + st] = u
        for t, u in d["tab"].items():
            vec[k + " table " + t] = u
    for st, u in f["fs"]["ud"].items():
        vec["fs ud " + st] = u
    for t, u in f["fs"]["tab"].items():
        vec["fs table " + t] = u
    return v, vec


# Latency-robust view: in the windows with an X or Y read, every value that varies between their frames but takes at most
# 4 values (not a counter), as a sequence of value letters per frame (a = the first value seen), next to the frames'
# start offsets and the reads' states, to set against the reads' switch times. Register, packet and argument values
# are listed; user-data and table dwords by letter only.
pw = sorted({frames[j]["win"] for j, s in lab.items() if s in ("X", "Y")})
print("# windows with X or Y reads: %s" % " ".join("w%02d" % w for w in pw))
for w in pw:
    fr = [(j, f) for j, f in enumerate(frames) if f["win"] == w]
    t0 = fr[0][1]["start"]
    print("  w%02d frame starts (ms): %s" % (w, " ".join("%s%.0f" % ("*" if f["partial"] else "", (f["start"] - t0) * 1000) for j, f in fr)))
    print("  w%02d sizes and states:  %s" % (w, " ".join("%s:%s" % (f["size"].split("x")[0], lab.get(j, ".")) for j, f in fr)))
    rs = sorted((r["wall"], r["name"]) for r in reads if frame_of(r, L) is not None and frames[frame_of(r, L)]["win"] == w)
    print("  w%02d reads (ms from the first frame's start, state at the frame's size): %s" % (w, " ".join(
        "%s@%.0f:%s" % (n, (wl - t0) * 1000, state(next(r for r in reads if r["name"] == n), frames[frame_of(next(r for r in reads if r["name"] == n), L)]["size"]))
        for wl, n in rs)))
pf = [j for j, f in enumerate(frames) if f["win"] in pw]
if pf:
    feats = {j: features(frames[j]) for j in pf}
    keys = set()
    for j in pf:
        keys |= set(feats[j][0])
    shown = 0
    print("# scalar values that vary between these frames with at most 4 values, per frame (window by window)")
    for k in sorted(keys - {"interval"}):
        vals = [feats[j][0].get(k, "absent") for j in pf]
        dv = list(dict.fromkeys(vals))
        if 1 < len(dv) <= 4 and shown < 40:
            shown += 1
            letters = {v: "abcd"[i] for i, v in enumerate(dv)}
            seq = " | ".join("".join(letters[feats[j][0].get(k, "absent")] for j in pf if frames[j]["win"] == w) for w in pw)
            print("  %s: %s  (%s)" % (k, seq, "; ".join("%s=%s" % (letters[v], v) for v in dv)))
    vkeys = set()
    for j in pf:
        vkeys |= set(feats[j][1])
    shown = 0
    print("# user-data and table dwords that vary between these frames with at most 4 values (letters only)")
    for k in sorted(vkeys):
        rows = [feats[j][1].get(k) for j in pf]
        if any(r is None for r in rows):
            continue
        for q in range(min(len(r) for r in rows)):
            vals = [r[q] for r in rows]
            dv = list(dict.fromkeys(vals))
            if 1 < len(dv) <= 4 and shown < 60:
                shown += 1
                letters = {v: "abcd"[i] for i, v in enumerate(dv)}
                seq = " | ".join("".join(letters[feats[j][1][k][q]] for j in pf if frames[j]["win"] == w) for w in pw)
                print("  %s dword %d: %s" % (k, q, seq))
X = [j for j, s in lab.items() if s == "X" and not frames[j]["partial"]]
Y = [j for j, s in lab.items() if s == "Y" and not frames[j]["partial"]]
print("# X frames %d, Y frames %d (whole frames only)" % (len(X), len(Y)))
if len(X) >= 3 and len(Y) >= 3:
    fx = {j: features(frames[j]) for j in X + Y}
    keys = set()
    for j in X + Y:
        keys |= set(fx[j][0])
    seps, varying, same, counters = [], 0, 0, 0
    for k in sorted(keys - {"interval"}):
        a = [fx[j][0].get(k, "absent") for j in X]
        b = [fx[j][0].get(k, "absent") for j in Y]
        if len(set(a + b)) == 1:
            same += 1
            continue
        varying += 1
        if not set(a) & set(b):
            if len(set(a)) + len(set(b)) <= (len(a) + len(b)) / 2:
                seps.append((k, collections.Counter(a), collections.Counter(b)))
            else:
                counters += 1
    print("# scalar values: %d keys; %d the same in all X and Y frames, %d vary, %d separate X from Y (and %d differ in"
          " (nearly) every frame)" % (len(keys) - 1, same, varying, len(seps), counters))
    for k, a, b in seps[:40]:
        print("  SEP %s | X: %s | Y: %s" % (k, "; ".join("%s x%d" % kv for kv in a.most_common(3)),
                                             "; ".join("%s x%d" % kv for kv in b.most_common(3))))
    vkeys = set()
    for j in X + Y:
        vkeys |= set(fx[j][1])
    vsep, vvar, vsame, vmiss, vcount = [], 0, 0, 0, 0
    for k in sorted(vkeys):
        rows_x = [fx[j][1].get(k) for j in X]
        rows_y = [fx[j][1].get(k) for j in Y]
        if any(r is None for r in rows_x + rows_y):
            vmiss += 1
            continue
        n = min(len(r) for r in rows_x + rows_y)
        for q in range(n):
            a = [r[q] for r in rows_x]
            b = [r[q] for r in rows_y]
            if len(set(a + b)) == 1:
                vsame += 1
                continue
            vvar += 1
            if not set(a) & set(b):
                if len(set(a)) + len(set(b)) <= (len(a) + len(b)) / 2:
                    vsep.append((k, q, len(set(a)), len(set(b))))
                else:
                    vcount += 1
    print("# user-data and table dwords: %d tables/ud sets in every X and Y frame (%d missing in some); %d dwords the same,"
          " %d vary, %d separate X from Y (and %d differ in (nearly) every frame)" % (
              len(vkeys) - vmiss, vmiss, vsame, vvar, len(vsep), vcount))
    for k, q, na, nb in vsep[:60]:
        print("  SEP %s dword %d: %d distinct values in X frames, %d in Y frames, none shared" % (k, q, na, nb))
    ix = [(frames[j]["start"] - frames[j - 1]["start"]) * 1000 for j in X if j > 0 and frames[j - 1]["win"] == frames[j]["win"]]
    iy = [(frames[j]["start"] - frames[j - 1]["start"]) * 1000 for j in Y if j > 0 and frames[j - 1]["win"] == frames[j]["win"]]
    if ix and iy:
        print("# interval from the previous frame: X median %.1f ms (%d), Y median %.1f ms (%d)" % (
            statistics.median(ix), len(ix), statistics.median(iy), len(iy)))
