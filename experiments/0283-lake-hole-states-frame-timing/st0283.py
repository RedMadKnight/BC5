#!/usr/bin/env python3
# BC5 experiment 0283, offline: the reads' hole states against the journalled frames, from the summaries only
# (xy0283.py's output and rd0283.py's JSON; no title data). rd0283.py names X the family with the most of the shots'
# cell mask and Y the next one; in W283b that picked a one-read family as Y, so its xy0283.py states are not used here.
# Instead each depth read is classed at its frame's size by the share of the cell mask's pixels that are depth 0
# ("cells" in rd0283.py), as both runs' families show:
#   X-like: depth 0 on >= 0.5 of the cell mask (W283a's X reads 0.80-0.92, W283b's 0.51-0.72);
#   Y-like: <= 0.3 of the cell mask with depth 0 on >= 0.15 of the lake window (W283a's Y 0.06-0.07, W283b's 0.21-0.29);
#   none: depth 0 on < 0.03 of the window; mixed otherwise; "?" when the read's shear at the frame's size is above 3.
# Per window with such reads (xy0283.py's "frame starts", "sizes and states" and "reads" lines, and its per-frame
# letter sequence of the depth-only writer 11d090d900's first draw packet, i.e. its indirect-argument slot, a or b;
# the other depth-only writers' packets and several table dwords follow the same sequence),
# each read is put on its frame (the latest frame starting at least L ms before it; L from xy0283.py), and it prints:
#   - per window: frame by frame the slot letter, the size and the classes of the reads on it;
#   - the runs of one class in time order (how many frames a state holds), and the switches between X and Y with the
#     frames between the two reads;
#   - a table of read class against the frame's slot letter, and against the previous frame's.
# usage: python3 -I st0283.py <W283x.xy.txt> <W283x.reads.json>
import collections, json, re, sys

xy, rj = sys.argv[1], sys.argv[2]
reads = {r["name"]: r for r in json.load(open(rj))["reads"]}
L = None
starts, sizes, rlist, slots, order = {}, {}, {}, {}, []
for l in open(xy):
    m = re.match(r"# L = (-?\d+) ms", l)
    if m:
        L = int(m[1])
    m = re.match(r"  (w\d+) frame starts \(ms\): (.*)$", l)
    if m:
        order.append(m[1])
        starts[m[1]] = [float(x.lstrip("*")) for x in m[2].split()]
    m = re.match(r"  (w\d+) sizes and states:\s+(.*)$", l)
    if m:
        sizes[m[1]] = [x.split(":")[0] for x in m[2].split()]
    m = re.match(r"  (w\d+) reads \(ms from the first frame's start, state at the frame's size\): (.*)$", l)
    if m:
        rlist[m[1]] = [(x.split("@")[0], float(x.split("@")[1].split(":")[0])) for x in m[2].split()]
    m = re.match(r"  11d090d900#0 pkt: (.*?)  \(", l)
    if m:
        seq = [s.strip() for s in m[1].split("|")]
        for w, s in zip(order, seq):
            slots[w] = s


def klass(r, size):
    e = r["sizes"].get(size)
    if e is None or e["shear"] > 3:
        return "?"
    if e["share"] < 0.03:
        return "0"
    if e["cells"] >= 0.5:
        return "X"
    if e["cells"] <= 0.3 and e["share"] >= 0.15:
        return "Y"
    return "m"


print("# %s: L = %s ms; windows %s" % (xy, L, " ".join(order)))
seqs, tab, tab_prev = [], collections.Counter(), collections.Counter()
for w in order:
    st, sz, sl = starts[w], sizes.get(w, []), slots.get(w, "")
    on = collections.defaultdict(list)
    for name, t in rlist.get(w, []):
        k = None
        for i, s in enumerate(st):
            if s <= t - L:
                k = i
        if k is None:
            continue
        c = klass(reads[name], sz[k])
        on[k].append(c)
        seqs.append((w, k, t, c))
        if c in "XY" and k < len(sl):
            tab[(c, sl[k])] += 1
            if k > 0:
                tab_prev[(c, sl[k - 1])] += 1
    print("  %s: %s" % (w, " ".join("%d:%s:%s:%s" % (i, sl[i] if i < len(sl) else "-", sz[i] if i < len(sz) else "-",
                                                         "".join(on[i]) or ".") for i in range(len(st)))))
print("# runs of one state over consecutive frames (frames with X or Y reads only; a frame with both counts as a switch)")
runs = []
for w in order:
    fr = sorted({(k) for ww, k, t, c in seqs if ww == w})
    states = []
    for k in fr:
        cs = {c for ww, kk, t, c in seqs if ww == w and kk == k and c in "XY"}
        if len(cs) == 1:
            states.append((k, cs.pop()))
        elif len(cs) == 2:
            states.append((k, "XY"))
    print("  %s: %s" % (w, " ".join("%d%s" % s for s in states)))
    for (k1, s1), (k2, s2) in zip(states, states[1:]):
        if s1 in "XY" and s2 in "XY" and len(s1) == len(s2) == 1:
            runs.append((s1 == s2, k2 - k1))
same = collections.Counter(d for eq, d in runs if eq)
diff = collections.Counter(d for eq, d in runs if not eq)
print("  consecutive labelled frames, by the number of frames between them: same state %s; switched %s" % (
    dict(sorted(same.items())), dict(sorted(diff.items()))))
print("# read class against the frame's argument slot (a/b), and against the previous frame's slot")
for c in "XY":
    print("  %s: this frame a %d b %d | previous frame a %d b %d" % (c, tab[(c, "a")], tab[(c, "b")], tab_prev[(c, "a")],
                                                                    tab_prev[(c, "b")]))
# Every per-frame value xy0283.py listed as varying with at most 4 values (its first 40 scalar and 60 dword keys, so not
# all of them), against these frame labels: frames whose reads are all X-like or all Y-like. A value separates the
# states when no letter occurs in both an X frame and a Y frame.
lab = {}
for w, k, t, c in seqs:
    lab.setdefault((w, k), set()).add(c)
lab = {key: v.pop() for key, v in lab.items() if len(v) == 1 and next(iter(v)) in "XY"}
nx, ny = sum(1 for v in lab.values() if v == "X"), sum(1 for v in lab.values() if v == "Y")
print("# listed values against %d X frames and %d Y frames" % (nx, ny))
n_keys, seps = 0, []
for l in open(xy):
    m = re.match(r"  (\S.*?): ((?:[a-d]+ \| )*[a-d]+)(?:  \(.*)?$", l)
    if not m or "@" in l:
        continue
    seq = [s.strip() for s in m[2].split("|")]
    if len(seq) != len(order):
        continue
    n_keys += 1
    lx, ly = set(), set()
    for w, s in zip(order, seq):
        for (ww, k), c in lab.items():
            if ww == w and k < len(s):
                (lx if c == "X" else ly).add(s[k])
    if lx and ly and not lx & ly:
        seps.append((m[1], "".join(sorted(lx)), "".join(sorted(ly))))
print("  %d values listed; %d separate X from Y frames" % (n_keys, len(seps)))
for k, a, b in seps[:30]:
    print("  SEP %s: X frames %s, Y frames %s" % (k, a, b))
