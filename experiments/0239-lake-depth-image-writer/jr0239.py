#!/usr/bin/env python3
# BC5 experiment 0239: summarise a draw journal (patch 0001's BC5_DIRECT_DRAW_JOURNAL lines, "draw journal buf N (D
# dwords) at P: <packet dwords> | rt0 <base> <WxH> info <x> mask <x> | vp ... | ps <a> es <a> gs <a> cs <a>") to find
# the pass that renders into colour target 0 at 0x113cb40000 (the night lake water's vertex-stage slot-4 image,
# exps 0237/0238). Prints:
#  (1) totals: graphics buffers, draws and dispatches by PM4 opcode;
#  (2) the passes in journal order: runs of consecutive draws with the same colour target 0, mask and shaders;
#  (3) the draws whose colour target 0 is TARGET, and the runs just before and after them, and where the water's draws
#      (PS 0x11d01ff900, 0x11d01d7100) fall relative to them;
#  (4) BC5_DIRECT_DRAW_JOURNAL_FIND hits ("draw journal find: ..."), grouped.
# PM4 opcodes (Mesa src/amd/common/sid.h): 0x27 DRAW_INDEX_2, 0x2d DRAW_INDEX_AUTO, 0x15 DISPATCH_DIRECT,
# 0x16 DISPATCH_INDIRECT, 0x38 DRAW_INDEX_MULTI_AUTO, 0x2c DRAW_INDEX_OFFSET_2, 0x25 DRAW_INDIRECT,
# 0x2b DRAW_INDEX_INDIRECT; others printed by number.
# usage: python3 -I jr0239.py <direct.log> [target hex, default 113cb40000]
import collections, re, sys

path = sys.argv[1]
TARGET = (sys.argv[2] if len(sys.argv) > 2 else "113cb40000").lower().removeprefix("0x").zfill(10)
WATER = ("11d01ff900", "11d01d7100")
OPS = {0x27: "DRAW_INDEX_2", 0x2d: "DRAW_INDEX_AUTO", 0x15: "DISPATCH_DIRECT", 0x16: "DISPATCH_INDIRECT",
       0x38: "DRAW_INDEX_MULTI_AUTO", 0x2c: "DRAW_INDEX_OFFSET_2", 0x25: "DRAW_INDIRECT", 0x2b: "DRAW_INDEX_INDIRECT"}
DRAW = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+): ([0-9a-f ]*)\|(.*)$")
FIND = re.compile(r"^draw journal find: (\w+) (\w+) ud(\d+) \(([0-9a-f]+)\) (\w+) ([0-9a-f]+) \| rt0 ([0-9a-f]+) \| ps ([0-9a-f]+) cs ([0-9a-f]+)")
T = re.compile(r"\bt (\d+\.\d+)")


def field(rest, name, n=1):
    m = re.search(r"\b%s ((?:\S+ ?){%d})" % (re.escape(name), n), rest)
    return m[1].strip() if m else "-"


rows, finds, t = [], [], 0.0
bufs = set()
for line in open(path, errors="replace"):
    if line.startswith("timing: t ") or line.startswith("frame profile: t "):
        m = T.search(line)
        if m:
            t = float(m[1])
        continue
    m = DRAW.match(line)
    if m:
        pkt = m[4].split()
        op = (int(pkt[0], 16) >> 8) & 0xff if pkt else -1
        rest = m[5]
        rt = field(rest, "rt0", 2).split()
        rows.append({"t": t, "buf": int(m[1]), "dw": int(m[2]), "at": int(m[3]), "op": op,
                     "rt": rt[0] if rt else "-", "size": rt[1] if len(rt) > 1 else "-",
                     "mask": field(rest, "mask"), "ps": field(rest, "ps"), "es": field(rest, "es"),
                     "gs": field(rest, "gs"), "cs": field(rest, "cs"), "vp": field(rest, "vp")})
        bufs.add((m[1], m[2]))
        continue
    m = FIND.match(line)
    if m:
        finds.append(m.groups())
print("# %s: %d journal lines in %d graphics buffers, t %.3f..%.3f; target %s" % (
    path, len(rows), len(bufs), rows[0]["t"] if rows else 0, rows[-1]["t"] if rows else 0, TARGET))
print("(1) by opcode: " + ", ".join("%s %d" % (OPS.get(k, "0x%02x" % k), v) for k, v in collections.Counter(r["op"] for r in rows).most_common()))
runs = []
for i, r in enumerate(rows):
    compute = r["op"] in (0x15, 0x16)
    key = ("dispatch", r["cs"]) if compute else ("draw", r["rt"], r["size"], r["mask"], r["ps"], r["es"], r["gs"])
    if runs and runs[-1]["key"] == key and runs[-1]["buf"] == r["buf"]:
        runs[-1]["n"] += 1
        runs[-1]["ops"][r["op"]] += 1
    else:
        runs.append({"key": key, "buf": r["buf"], "at": r["at"], "t": r["t"], "n": 1, "first": i,
                     "ops": collections.Counter([r["op"]])})


def show(k, ru):
    key = ru["key"]
    ops = ",".join("%s x%d" % (OPS.get(o, "0x%02x" % o), c) for o, c in ru["ops"].items())
    if key[0] == "dispatch":
        desc = "dispatch cs %s" % key[1]
    else:
        desc = "rt0 %s %s mask %s | ps %s es %s gs %s" % key[1:]
    mark = " <== TARGET" if key[0] == "draw" and key[1] == TARGET else (" <== water" if key[0] == "draw" and key[4] in WATER else "")
    return "  #%-4d t %.3f buf %-3d at %-6d %4d x %-34s %s%s" % (k, ru["t"], ru["buf"], ru["at"], ru["n"], ops, desc, mark)


print("(2) passes in journal order: %d runs" % len(runs))
for k, ru in enumerate(runs):
    print(show(k, ru))
tk = [k for k, ru in enumerate(runs) if ru["key"][0] == "draw" and ru["key"][1] == TARGET]
wk = [k for k, ru in enumerate(runs) if ru["key"][0] == "draw" and ru["key"][4] in WATER]
print("(3) runs into %s: %s; water runs: %s" % (TARGET, " ".join("#%d" % k for k in tk) or "none", " ".join("#%d" % k for k in wk) or "none"))
for k in tk:
    print("  around #%d:" % k)
    for j in range(max(0, k - 4), min(len(runs), k + 5)):
        print("  " + show(j, runs[j]))
print("(4) find hits: %d" % len(finds))
for g, n in collections.Counter((f[0], f[1], f[2], f[4], f[6], f[7], f[8]) for f in finds).most_common():
    print("  %4d x %s %s ud%s %s | rt0 %s | ps %s cs %s" % ((n,) + g))
