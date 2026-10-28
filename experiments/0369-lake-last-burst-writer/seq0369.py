#!/usr/bin/env python3
# BC5 experiment 0369: the order of the night lake's depth work in each journalled frame, from a draw journal with
# exp 0245's "bake db" lines (exp 0251's private binary: runs Z2, W251b, W257a). Per draw or dispatch line ("draw journal
# buf N (D dwords) at O: <packet> | rt0 ... | ps ... cs ..."), the next "bake db" line of the same buffer and offset gives
# DB_DEPTH_CONTROL, DB_RENDER_CONTROL, DB_Z_INFO and the depth bases; "bake draw" gives the time when present.
# Printed: (1) one letter per pass in journal order, runs folded ("Z17"): draws with the lake's depth (0x1129ec0000) as
# their depth target, any draw with a non-zero DB_RENDER_CONTROL, the full-screen water draw (PS 0x11d01d7100) and every
# dispatch (H the HTILE fill CS 0x11d0288a00, P CS 0x11d0288800, c the rest); (2) each draw with DB_RENDER_CONTROL 0x60
# with the 14 passes before it and 3 after (the first N per pixel shader).
# DB_DEPTH_CONTROL: Z_ENABLE bit 1, Z_WRITE_ENABLE bit 2, ZFUNC bits 6:4. DB_RENDER_CONTROL: DEPTH_CLEAR_ENABLE bit 0,
# STENCIL_CLEAR_ENABLE 1, DEPTH_COPY 2, STENCIL_COPY 3, RESUMMARIZE_ENABLE 4, STENCIL_COMPRESS_DISABLE 5,
# DEPTH_COMPRESS_DISABLE 6 (tools/bc5-agc/regdb/gfx10.json, Mesa's gfx10 register JSON).
# usage: python3 -I seq0369.py <direct.log> [N, 2]   (prints a summary only; the journal stays private)
import re, sys

DEPTH = 0x1129ec0000
HTILE_FILL, PYRAMID, WATER = 0x11d0288a00, 0x11d0288800, 0x11d01d7100
LINE = re.compile(r"draw journal buf (\d+) \((\d+) dwords\) at (\d+):((?: [0-9a-f]{8})+) \| rt0 ([0-9a-f]+) (\d+)x(\d+) info ([0-9a-f]+) mask ([0-9a-f]+) \| vp (-?\d+)x(-?\d+) at (-?\d+),(-?\d+) \| ps ([0-9a-f]+) es ([0-9a-f]+) gs ([0-9a-f]+) cs ([0-9a-f]+)")
DB = re.compile(r"bake db buf (\d+) at (\d+): depth_control ([0-9a-f]+) stencil_control ([0-9a-f]+) .*?render_control ([0-9a-f]+) .*?z_info ([0-9a-f]+) .*?z_read ([0-9a-f]+) .*?z_write ([0-9a-f]+) .*?htile ([0-9a-f]+).*?clear z (\S+)")
T = re.compile(r"bake draw buf (\d+) at (\d+): t ([0-9.]+)")
OPS = {0x2d: "DRAW_INDEX_AUTO", 0x27: "DRAW_INDEX_2", 0x24: "DRAW_INDIRECT", 0x25: "DRAW_INDEX_INDIRECT", 0x38: "DRAW_INDEX_INDIRECT_MULTI",
       0x2c: "DRAW_INDIRECT_MULTI", 0x35: "DRAW_INDEX_OFFSET_2", 0x15: "DISPATCH_DIRECT", 0x16: "DISPATCH_INDIRECT"}


def zdesc(dc):
    if not dc & 2:
        return "Z off"
    return "Z on%s %s" % ("+write" if dc & 4 else "", ["NEVER", "LESS", "EQUAL", "LEQUAL", "GREATER", "NOTEQUAL", "GEQUAL", "ALWAYS"][(dc >> 4) & 7])


def rcdesc(rc):
    names = ["DEPTH_CLEAR", "STENCIL_CLEAR", "DEPTH_COPY", "STENCIL_COPY", "RESUMMARIZE", "STENCIL_COMPRESS_DISABLE", "DEPTH_COMPRESS_DISABLE"]
    return "+".join(n for i, n in enumerate(names) if rc >> i & 1) or "0"


path = sys.argv[1]
maxf = int(sys.argv[2]) if len(sys.argv) > 2 else 2
pend, rows = {}, []
for l in open(path, errors="replace"):
    m = LINE.search(l)
    if m:
        words = m[4].split()
        op = (int(words[0], 16) >> 8) & 0xff
        d = {"buf": int(m[1]), "off": int(m[3]), "op": OPS.get(op, "op%02x" % op), "count": int(words[1], 16) if op == 0x2d and len(words) > 1 else None,
             "rt": int(m[5], 16), "w": int(m[6]), "h": int(m[7]), "mask": int(m[9], 16), "vp": (int(m[10]), int(m[11])), "ps": int(m[14], 16), "cs": int(m[17], 16),
             "disp": op in (0x15, 0x16), "groups": words[1:4] if op == 0x15 else None, "t": None, "db": None}
        pend[(d["buf"], d["off"])] = d
        rows.append(d)
        continue
    m = DB.search(l)
    if m and (int(m[1]), int(m[2])) in pend:
        pend[(int(m[1]), int(m[2]))]["db"] = {"dc": int(m[3], 16), "sc": int(m[4], 16), "rc": int(m[5], 16), "zi": int(m[6], 16), "zr": int(m[7], 16), "zw": int(m[8], 16),
                                              "htile": int(m[9], 16), "clear": m[10]}
        continue
    m = T.search(l)
    if m and (int(m[1]), int(m[2])) in pend:
        pend[(int(m[1]), int(m[2]))]["t"] = float(m[3])


def kept(d):
    db = d["db"] or {}
    if d["disp"]:
        return d["cs"] in (HTILE_FILL, PYRAMID)
    return d["ps"] == WATER or db.get("zw") == DEPTH or db.get("rc", 0) != 0


def desc(d):
    db = d["db"] or {}
    if d["disp"]:
        return "dispatch CS %010x %s" % (d["cs"], "x".join(str(int(g, 16)) for g in d["groups"]) if d["groups"] else d["op"])
    s = "%s%s PS %010x rt0 %010x %dx%d mask %x vp %dx%d | %s" % (d["op"], " %d" % d["count"] if d["count"] is not None else "", d["ps"], d["rt"], d["w"], d["h"], d["mask"],
                                                              d["vp"][0], -d["vp"][1], zdesc(db.get("dc", 0)))
    if db.get("rc"):
        s += " | render_control %s" % rcdesc(db["rc"])
    if db.get("zw") not in (None, DEPTH):
        s += " | z_write %010x" % db["zw"]
    if db.get("sc"):
        s += " | stencil_control %08x" % db["sc"]
    return s


k = [d for d in rows if kept(d)]
print("# %s: %d draw/dispatch lines, %d kept; render_control values: %s" % (
    path.split("/")[-1], len(rows), len(k), sorted({"%x" % (d["db"] or {}).get("rc", 0) for d in rows})))


def code(d):
    # one letter per pass: H the HTILE fill CS 0x11d0288a00, P CS 0x11d0288800, c any other dispatch, D a draw with
    # DB_RENDER_CONTROL 0x60, W the water draw, and with the lake's depth as the depth target: Z a writer (Z on +
    # write), e a depth-tested draw without a write, o a draw with Z off; other draws are left out
    db = d["db"] or {}
    if d["disp"]:
        return {HTILE_FILL: "H", PYRAMID: "P"}.get(d["cs"], "c")
    if db.get("rc", 0) == 0x60:
        return "D"
    if d["ps"] == WATER:
        return "W"
    if db.get("zw") == DEPTH:
        return "Z" if db.get("dc", 0) & 6 == 6 else ("e" if db.get("dc", 0) & 2 else "o")
    return ""


s = "".join(code(d) for d in rows)
print("# the passes in journal order, one letter each, runs folded (H HTILE fill, Z depth writer, e depth-tested, o depth bound with Z off, W water, D decompress, P CS 0x11d0288800, c other dispatch):")
rl = re.sub(r"(.)\1+", lambda m: "%s%d" % (m[1], len(m[0])), s)
for i in range(0, len(rl), 120):
    print("   " + rl[i:i + 120])
# every draw with DB_RENDER_CONTROL 0x60, with the passes around it (the first two of each pixel shader)
seen = {}
for i, d in enumerate(rows):
    if d["disp"] or (d["db"] or {}).get("rc", 0) != 0x60 or seen.get(d["ps"], 0) >= maxf:
        continue
    seen[d["ps"]] = seen.get(d["ps"], 0) + 1
    print("## decompress state at buf %d +%d (PS %010x):" % (d["buf"], d["off"], d["ps"]))
    for x in rows[max(0, i - 14): i + 4]:
        db = x["db"] or {}
        print("   %s buf %d +%d: %s%s" % ("=>" if x is d else "  ", x["buf"], x["off"], desc(x),
                                         " | z %010x htile %010x clear z %s" % (db["zw"], db["htile"], db["clear"]) if db.get("zw") else ""))
