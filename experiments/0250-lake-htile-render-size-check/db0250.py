#!/usr/bin/env python3
# BC5 experiment 0250: the night lake's depth buffer as the DB was told to see it, per journalled draw, from exp 0245's
# "bake db" lines (patch0245.py; private binary ~/bc5-work/exp0245/kyty_emulator). jr0245.py parsed but did not print
# these fields. Decoded with Mesa's gfx10 register JSON (tools/bc5-agc/regdb/gfx10.json):
#  - DB_Z_INFO: FORMAT, NUM_SAMPLES, SW_MODE, MAXMIP, DECOMPRESS_ON_N_ZPLANES, ALLOW_EXPCLEAR, READ_SIZE,
#    TILE_SURFACE_ENABLE (HTILE in use), ZRANGE_PRECISION;
#  - DB_DEPTH_SIZE_XY X_MAX/Y_MAX (+1 = the surface's size), DB_DEPTH_VIEW, DB_HTILE_DATA_BASE (40-bit, as patch0245
#    prints it), DB_RENDER_CONTROL and DB_RENDER_OVERRIDE (non-zero fields), DB_DEPTH_CLEAR.
# For the entries whose depth buffer is <z base> (default 0x1129ec0000, F305) it prints:
#  (A) each distinct surface description with its count, the colour target's size and pixel shaders;
#  (B) the descriptions in journal order as runs (a change of size or HTILE base between frames shows as a new run);
#  (C) in an unfiltered window: the entries just before each first depth write into the buffer after a full-screen water
#      draw (PS 0x11d01d7100) or at the window's start: draws, dispatches (op 0x15/0x16, by CS address) and passes with
#      DB_RENDER_CONTROL set; and every non-"bake db" journal line that holds the HTILE base (as a 40-bit address or
#      shifted by 8, as a register stores it): a compute or table reference to it.
# The journal holds draws and dispatches only; DMA_DATA and other CP writes are not in it.
# usage: python3 -I db0250.py <direct.log> <gfx10.json> [z base hex]
import collections, json, re, sys

path, regdb = sys.argv[1], sys.argv[2]
ZB = (sys.argv[3] if len(sys.argv) > 3 else "1129ec0000").lower()
WATER_FS = "11d01d7100"
d = json.load(open(regdb))
types = d["register_types"]
fields = {}
for r in d["register_mappings"]:
    t = types.get(r.get("type_ref", ""), {})
    fields[r["name"]] = [(f["name"], f["bits"][0], f["bits"][1]) for f in t.get("fields", [])]


def dec(name, v):
    return {n: (v >> lo) & ((1 << (hi - lo + 1)) - 1) for n, lo, hi in fields.get(name, [])}


def nonzero(name, v):
    return ",".join("%s=%d" % (k, x) for k, x in dec(name, v).items() if x) or "0"


ZI = ["FORMAT", "NUM_SAMPLES", "SW_MODE", "MAXMIP", "DECOMPRESS_ON_N_ZPLANES", "ALLOW_EXPCLEAR", "READ_SIZE",
      "TILE_SURFACE_ENABLE", "ZRANGE_PRECISION"]
DRAW = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+):((?: [0-9a-f]{8})*) \| rt0 (\S+) (\S+) info \S+ mask (\S+) .*\| ps (\S+) es (\S+) gs (\S+) cs (\S+)")
DB = re.compile(r"^bake db buf (\d+) at (\d+): depth_control (\S+) stencil_control (\S+) refmask (\S+) refmask_bf (\S+) shader_control (\S+)"
                r" render_control (\S+) render_override (\S+) \| z_info (\S+) stencil_info (\S+) view (\S+) size_xy (\S+) \| z_read (\S+)"
                r" stencil_read (\S+) z_write (\S+) stencil_write (\S+) htile (\S+) \| bounds (\S+)\.\.(\S+) clear z (\S+) s (\S+)")
T = re.compile(r"\bt (\d+\.\d+)")
rows, t, pend, raw_lines = [], 0.0, {}, []
for line in open(path, errors="replace"):
    if line.startswith("timing: t ") or line.startswith("frame profile: t "):
        m = T.search(line)
        if m:
            t = float(m[1])
        continue
    m = DRAW.match(line)
    if m:
        words = m[4].split()
        op = (int(words[0], 16) >> 8) & 0xff if words else -1
        pend[(m[1], m[3])] = {"t": t, "buf": int(m[1]), "at": int(m[3]), "op": op, "rt": m[5], "size": m[6], "mask": m[7],
                              "ps": m[8].lower(), "cs": m[11].lower()}
        continue
    m = DB.match(line)
    if m and (m[1], m[2]) in pend:
        r = pend.pop((m[1], m[2]))
        zi, sxy = int(m[10], 16), int(m[13], 16)
        sx = dec("DB_DEPTH_SIZE_XY", sxy)
        dc = dec("DB_DEPTH_CONTROL", int(m[3], 16))
        r.update(zr=m[14], zw=m[16], ht=m[18].lower(), zinfo=" ".join("%s %d" % (k, dec("DB_Z_INFO", zi).get(k, 0)) for k in ZI),
                 dsize="%dx%d" % (sx.get("X_MAX", 0) + 1, sx.get("Y_MAX", 0) + 1), view=nonzero("DB_DEPTH_VIEW", int(m[12], 16)),
                 rc=nonzero("DB_RENDER_CONTROL", int(m[8], 16)), ro=nonzero("DB_RENDER_OVERRIDE", int(m[9], 16)), clear=m[21],
                 zwrite=bool(dc.get("Z_ENABLE") and dc.get("Z_WRITE_ENABLE")))
        rows.append(r)
        continue
    if not line.startswith("bake db"):
        raw_lines.append(line.rstrip("\n"))

mine = [r for r in rows if r["zr"].lower() == ZB or r["zw"].lower() == ZB]
print("# %s: %d journalled entries with a bake-db line, %d on depth buffer %s; %d dispatches" % (
    path, len(rows), len(mine), ZB, sum(1 for r in rows if r["op"] in (0x15, 0x16))))


def surf(r):
    return "depth %s | htile %s | %s | view %s | render_control %s | override %s | clear z %s" % (
        r["dsize"], r["ht"], r["zinfo"], r["view"], r["rc"], r["ro"], r["clear"])


print("(A) distinct descriptions of the depth buffer:")
agg = collections.OrderedDict()
for r in mine:
    a = agg.setdefault(surf(r), {"n": 0, "rt": collections.Counter(), "ps": collections.Counter(), "t": [r["t"], r["t"]]})
    a["n"] += 1
    a["rt"]["%s %s" % (r["rt"], r["size"])] += 1
    a["ps"][r["ps"]] += 1
    a["t"][1] = r["t"]
for k, a in agg.items():
    print("  %4d x %s" % (a["n"], k))
    print("         t %.3f..%.3f; rt0 %s; ps %s" % (a["t"][0], a["t"][1], ", ".join("%s (%d)" % x for x in a["rt"].most_common(4)),
                                                  ", ".join("%s (%d)" % x for x in a["ps"].most_common(6))))
print("(B) in journal order (runs of one description and colour-target size):")
runs = []
for r in mine:
    key = (surf(r), r["size"])
    if runs and runs[-1][0] == key:
        runs[-1][2] += 1
        runs[-1][3] = r["t"]
    else:
        runs.append([key, r["t"], 1, r["t"]])
for key, t0, n, t1 in runs:
    print("  t %.3f..%.3f %4d x rt0 %s | depth %s htile %s" % (t0, t1, n, key[1], key[0].split(" | ")[0][6:], key[0].split(" | ")[1][6:]))
print("(C) before each first depth write into the buffer (window start, or after a full-screen water draw):")
ht_bases = {r["ht"] for r in mine if r["ht"] != "0000000000"}
armed, last = True, collections.deque(maxlen=10)
for r in rows:
    if r["ps"] == WATER_FS:
        armed = True
    if armed and r["zwrite"] and (r["zw"].lower() == ZB):
        print("  first depth write at t %.3f buf %d at %d (ps %s, rt0 %s); the entries before it:" % (r["t"], r["buf"], r["at"], r["ps"], r["size"]))
        for q in last:
            kind = "dispatch cs %s" % q["cs"] if q["op"] in (0x15, 0x16) else "draw op %02x ps %s rt0 %s %s" % (q["op"], q["ps"], q["rt"], q["size"])
            print("    t %.3f buf %d at %d: %s | z %s%s | render_control %s" % (q["t"], q["buf"], q["at"], kind, q["zw"],
                                                                         " write" if q["zwrite"] else "", q["rc"]))
        armed = False
    last.append(r)
for h in sorted(ht_bases):
    keys = [h, "%08x" % (int(h, 16) >> 8)]
    hits = [l for l in raw_lines if any(k in l.lower() for k in keys)]
    print("  HTILE base %s (register form %s): %d non-bake journal lines hold it" % (h, keys[1], len(hits)))
    for l in hits[:5]:
        print("    %s" % l[:150])
