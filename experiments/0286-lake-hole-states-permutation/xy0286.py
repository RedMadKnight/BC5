#!/usr/bin/env python3
# BC5 experiment 0286: are exp 0285's X/Y separators (F346) more than chance, and do the candidate writers' draws differ
# between X and Y frames? Read-only on exp 0283's two journals with its read summaries. The journal parsing, the frames,
# the lag, st0283.py's cell-share labels and the per-frame values are xy0285.py's (copied unchanged). Then:
#  (1) the candidate writers of exp 0285 (0x11d29ea100, 0x11d1d88300, 0x11d1dd6400, 0x11d29c4500, 0x11d373f600): per
#      frame of every window with a labelled frame, their number of draws, all writers' number, and the order of the
#      candidates' draws (one letter per shader, A..E in the order above); per state, the
#      counts in whole labelled frames;
#  (2) a permutation test of the exact separators (xy0285.py's rule: no shared value, >= 3 frames of each state,
#      repeating values) at offsets -1, 0, +1: the count for the real labels against 100 free shuffles of the labels and
#      against every rotation of the labels along the labelled frames' time order (a stricter null that keeps runs of
#      one state together, as the real labels come in runs); also the number of distinct tables (or scalar keys) the
#      separators lie in, since a table's dwords move together;
#  (3) given a key file (xy0285.py's output for the other run), each "SEP" key listed there, in this run, by offset:
#      the value letters in X and Y frames, and whether it separates here.
# Summaries only: counts, keys, positions, value letters. Runs on the box (stdlib only), on the title's data.
# usage: python3 -I xy0286.py <direct.log> <reads json> <L ms> [xy0285 output of the other run]
import collections, json, random, re, statistics, sys

log, rjson = sys.argv[1], sys.argv[2]
L_GIVEN = int(sys.argv[3]) if len(sys.argv) > 3 else None
KEYFILE = sys.argv[4] if len(sys.argv) > 4 else None
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




random.seed(286)
cand_ps = ("11d29ea100", "11d1d88300", "11d1dd6400", "11d29c4500", "11d373f600")
order_t = sorted(lab, key=lambda j: frames[j]["start"])  # labelled frames in time order


def short(ps):
    return "ABCDE"[cand_ps.index(ps)]


# (1) the candidate writers' draws per frame, against the states (every frame of a window with a labelled frame)
print("# the candidate writers' draws per frame: state (X/Y; '.' no label; '*' partial first frame), size, the number of"
      " draws of each candidate shader (%s) and of all writers, and the order of the candidates' draws" % ", ".join(cand_ps))
wins = sorted({frames[j]["win"] for j in lab})
counts = collections.defaultdict(lambda: collections.defaultdict(list))
for w in wins:
    for j, f in enumerate(frames):
        if f["win"] != w:
            continue
        c = collections.Counter(d["ps"] for d in f["writers"])
        seq = [short(d["ps"]) for d in f["writers"] if d["ps"] in cand_ps]
        s = lab.get(j, ".")
        print("  w%02d #%d %s%s %s: %s | all %d | order %s" % (w, j, "*" if f["partial"] else "", s, f["size"].split("x")[0],
                                                              " ".join("%d" % c[p] for p in cand_ps), len(f["writers"]),
                                                              "".join(x[0] for x in seq) if len(seq) < 60 else "%d draws" % len(seq)))
        if s in ("X", "Y") and not f["partial"]:
            for p in cand_ps:
                counts[p][s].append(c[p])
            counts["all"][s].append(len(f["writers"]))
print("# draws per whole labelled frame: shader: X frames' counts | Y frames' counts")
for p in cand_ps + ("all",):
    print("  %s: X %s | Y %s" % (p, " ".join(map(str, sorted(counts[p]["X"]))), " ".join(map(str, sorted(counts[p]["Y"])))))

# (2) the permutation test: exact separators (as xy0285.py) for the real labels and for relabelled frames
feats = {}


def columns(off):
    pairs = []
    for j in order_t:
        k = j + off
        if 0 <= k < len(frames) and frames[k]["win"] == frames[j]["win"]:
            pairs.append((j, k))
    for _, k in pairs:
        if k not in feats:
            feats[k] = features(frames[k])
    cols = collections.defaultdict(dict)  # key -> {pair index: value}
    for i, (_, k) in enumerate(pairs):
        sc, vec = feats[k]
        for key, v in sc.items():
            cols[key][i] = v
        for key, u in vec.items():
            for q, v in enumerate(u):
                cols[(key, q)][i] = v
    varying = {key: c for key, c in cols.items() if len(set(c.values())) > 1}
    return pairs, varying


def separators(labels, varying):
    n, tables = 0, set()
    for key, c in varying.items():
        a = [v for i, v in c.items() if labels[i] == "X"]
        b = [v for i, v in c.items() if labels[i] == "Y"]
        if len(a) < 3 or len(b) < 3 or set(a) & set(b):
            continue
        if len(set(a)) + len(set(b)) <= (len(a) + len(b)) / 2:
            n += 1
            tables.add(key[0] if isinstance(key, tuple) else key)
    return n, len(tables)


print("# permutation test: exact separators (and the tables or scalar keys they lie in) for the real labels, against"
      " 100 free shuffles of the labels and every rotation of the labels along the frames' time order (which keeps"
      " runs of one state together)")
results = {}
for off in (-1, 0, 1):
    pairs, varying = columns(off)
    real = [lab[j] for j, _ in pairs]
    nx, ny = real.count("X"), real.count("Y")
    if nx < 3 or ny < 3:
        print("  offset %+d: %d X and %d Y frames, too few" % (off, nx, ny))
        continue
    obs = separators(real, varying)
    shuf = []
    for _ in range(100):
        p = real[:]
        random.shuffle(p)
        shuf.append(separators(p, varying))
    rot = [separators(real[r:] + real[:r], varying) for r in range(1, len(real))]
    results[off] = (pairs, varying)

    def tail(null, i):
        return sum(1 for x in null if x[i] >= obs[i]) / len(null)

    print("  offset %+d: %d X / %d Y frames, %d varying keys; real: %d separators in %d tables | shuffles: median %s, max"
          " %s, share >= real %.2f (tables %.2f) | rotations: median %s, max %s, share >= real %.2f (tables %.2f)" % (
              off, nx, ny, len(varying), obs[0], obs[1], statistics.median(x[0] for x in shuf), max(x[0] for x in shuf),
              tail(shuf, 0), tail(shuf, 1), statistics.median(x[0] for x in rot), max(x[0] for x in rot), tail(rot, 0),
              tail(rot, 1)))

# (3) the other run's separators (a key file of xy0285.py's "SEP" lines) in this run
if KEYFILE:
    print("# the separators listed in %s, in this run (value letters per state; '-' absent)" % KEYFILE)
    seen = set()
    for l in open(KEYFILE):
        m = re.match(r"\s*SEP (\S+) (.*?) dword (\d+) \|", l) or re.match(r"\s*SEP (\S+) (.*?) \| X:", l)
        if not m:
            continue
        key = ("%s %s" % (m[1], m[2]), int(m[3])) if m.lastindex == 3 else "%s %s" % (m[1], m[2])
        if key in seen:
            continue
        seen.add(key)
        row = []
        for off, (pairs, varying) in sorted(results.items()):
            c = varying.get(key)
            if c is None:
                row.append("%+d: constant or absent" % off)
                continue
            vals = list(dict.fromkeys(c.values()))
            let = {v: "abcdefghij"[i] if i < 10 else "+" for i, v in enumerate(vals)}
            a = "".join(let[c[i]] for i in sorted(c) if lab[pairs[i][0]] == "X")
            b = "".join(let[c[i]] for i in sorted(c) if lab[pairs[i][0]] == "Y")
            row.append("%+d: X %s Y %s%s" % (off, a or "-", b or "-", " SEPARATES" if a and b and not set(a) & set(b) else ""))
        print("  %s | %s" % (key if isinstance(key, str) else "%s dword %d" % key, " | ".join(row)))
