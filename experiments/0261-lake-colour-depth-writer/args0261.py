#!/usr/bin/env python3
# BC5 experiment 0261 (exp 0253's args0253.py, with per-window counts keyed by the matched prefix): the night lake's depth-only writers and their indirect arguments, per journal window, against the
# bench's frozen-view shots. Reads build0251's journal: edit0194.py's lines ("draw journal window from buf N: t T wall
# S.MS", "draw journal args buf N at P: op .. base1 .. +0x.. single count .. | max count .. max inst .., .. zero, .. |
# [args] ...", "args at completion: ... [args] submitted [args]") after each "draw journal buf N (D dwords) at P: ... |
# ps .." line. DRAW_INDIRECT's arguments are {vertex count, instance count, start vertex, start instance} (Mesa
# radv_cs_emit_indirect_draw_packet, 0866ae7, as edit0194.py cites). Arguments the GPU writes are read at submission,
# so they may be the previous frame's; at completion they are read again (with chains on the completed job is the
# chain, exp 0194, so those lines may be missing).
# Prints, per window: the shots before and after it (patch %), and per writer shader the draws, their summed vertex
# counts and zero-count draws; then, per writer shader and argument slot (base1 + offset), the vertex counts seen in
# clean windows (both shots under 5 %) and in patched ones (both 8 % or more, exp 0197's metric).
# usage: python3 -I args0261.py <direct.log> <bench.txt> [writer pixel shaders, default the four of exp 0245]
import collections, re, sys, time

path, bench = sys.argv[1], sys.argv[2]
WRITERS = (sys.argv[3] if len(sys.argv) > 3 else "11d1d88300,11d1dd6400,11d090d900,11d0a98300").lower().split(",")
shots = []
for l in open(bench):
    m = re.match(r"\s*(\d{6})-(ts\d\d)\.png: patch\s+([\d.]+) %", l)
    if m:
        shots.append((m[1], m[2], float(m[3])))
WIN = re.compile(r"^draw journal window from buf (\d+): t ([\d.]+) wall (\d+)\.(\d+)")
DRAW = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+):((?: [0-9a-f]{8})*) \|.*\| ps (\S+) ")
ARGS = re.compile(r"^draw journal args buf (\d+) at (\d+): op (\S+) base1 (\S+) \+0x(\S+)( single)? count (\d+).*\|( \[.*)?$")
COMP = re.compile(r"^args at completion: submit #\d+ buf (\d+) at (\d+) \S+: \[([^\]]*)\] submitted \[([^\]]*)\]")
wins, cur, draws = [], None, {}
for line in open(path, errors="replace"):
    m = WIN.match(line)
    if m:
        hms = time.strftime("%H%M%S", time.localtime(int(m[3])))
        cur = {"t": float(m[2]), "hms": hms, "rows": []}
        wins.append(cur)
        continue
    m = DRAW.match(line)
    if m and cur is not None:
        r = {"buf": int(m[1]), "at": int(m[3]), "ps": m[5].lower(), "args": None, "done": None}
        draws[(m[1], m[3])] = r
        if any(r["ps"].startswith(w) for w in WRITERS):
            cur["rows"].append(r)
        continue
    m = ARGS.match(line)
    if m and (m[1], m[2]) in draws:
        a = re.findall(r"\[([^\]]*)\]", m[8] or "")
        draws[(m[1], m[2])]["args"] = {"slot": "%s+%s" % (m[4], m[5]), "op": m[3], "first": [int(x, 16) for x in a[0].split()] if a else None}
        continue
    m = COMP.match(line)
    if m and (m[1], m[2]) in draws:
        draws[(m[1], m[2])]["done"] = [int(x, 16) for x in m[3].split()]


def around(hms):
    prev = [s for s in shots if s[0] <= hms]
    nxt = [s for s in shots if s[0] >= hms]
    return (prev[-1] if prev else None), (nxt[0] if nxt else None)


def state(p, n):
    if p and n and p[2] < 5 and n[2] < 5:
        return "clean"
    if p and n and p[2] >= 8 and n[2] >= 8:
        return "patched"
    return "mixed"


print("# %s: %d windows; writers %s" % (path, len(wins), ",".join(WRITERS)))
slots = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
for w in wins:
    p, n = around(w["hms"])
    st = state(p, n)
    per = collections.OrderedDict((ps, [0, 0, 0, 0]) for ps in WRITERS)  # draws, summed vertex count, zero, no args
    for r in w["rows"]:
        w0 = next(w for w in WRITERS if r["ps"].startswith(w))  # counts per writer prefix (exp 0253 keyed them wrongly)
        c = per[w0]
        c[0] += 1
        a = r["args"]
        if not a or not a["first"]:
            c[3] += 1
            continue
        v, inst = a["first"][0], a["first"][1] if len(a["first"]) > 1 else 1
        c[1] += v * inst
        c[2] += (v == 0 or inst == 0)
        slots[w0][a["slot"]][(st, v, inst)] += 1
    print("  t %-8.3f wall %s:%s:%s prev %s next %s -> %-7s | %s" % (
        w["t"], w["hms"][:2], w["hms"][2:4], w["hms"][4:], p and "%s %4.1f %%" % (p[1], p[2]), n and "%s %4.1f %%" % (n[1], n[2]), st,
        "; ".join("%s %d draws, %d vertices, %d zero%s" % (ps, c[0], c[1], c[2], ", %d without args" % c[3] if c[3] else "") for ps, c in per.items())))
print("per writer and argument slot: (window state, vertex count, instances) x windows-draws")
for ps in WRITERS:
    for slot, cnt in sorted(slots[ps].items()):
        cl = sorted((k[1], k[2]) for k in cnt if k[0] == "clean")
        pa = sorted((k[1], k[2]) for k in cnt if k[0] == "patched")
        flag = "" if set(cl) == set(pa) or not cl or not pa else "   <- differs"
        print("  %s %s: clean %s | patched %s | mixed %d%s" % (
            ps, slot, " ".join("%dx%d" % x for x in sorted(set(cl))) or "-", " ".join("%dx%d" % x for x in sorted(set(pa))) or "-",
            sum(v for k, v in cnt.items() if k[0] == "mixed"), flag))
