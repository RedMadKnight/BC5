#!/usr/bin/env python3
# BC5 experiment 0245: read build0245's draw journal ("draw journal buf N (D dwords) at P: ... | rt0 ... | ps ..." and
# the "bake db buf N at P: ..." line patch0245.py adds) for the night lake water's full-screen draw (PS 0x11d01d7100).
# Register fields are decoded from Mesa's gfx10 register JSON (tools/bc5-agc/regdb/gfx10.json). Prints:
#  (1) the full-screen draw's depth/stencil state and buffers, per distinct state;
#  (2) the passes of the journal window in order (runs of draws with the same colour target, shaders and depth/stencil
#      state): colour target, pixel shader, depth test/write/function, stencil test/function/ops/reference/masks, and
#      the depth/stencil read and write bases;
#  (3) the draws before each full-screen draw in its window that write depth or stencil into the buffer it tests
#      (Z_WRITE_ENABLE, or stencil enabled with a non-zero write mask and an op other than KEEP).
# usage: python3 -I jr0245.py <direct.log> <gfx10.json> [pixel shader hex, default 11d01d7100]
import collections, json, re, sys

path, regdb = sys.argv[1], sys.argv[2]
TARGET = (sys.argv[3] if len(sys.argv) > 3 else "11d01d7100").lower()
d = json.load(open(regdb))
types = d["register_types"]
fields = {}
for r in d["register_mappings"]:
    t = types.get(r.get("type_ref", ""), {})
    fields[r["name"]] = [(f["name"], f["bits"][0], f["bits"][1]) for f in t.get("fields", [])]


def dec(name, v):
    return {n: (v >> lo) & ((1 << (hi - lo + 1)) - 1) for n, lo, hi in fields.get(name, [])}


FUNC = ["NEVER", "LESS", "EQUAL", "LEQUAL", "GREATER", "NOTEQUAL", "GEQUAL", "ALWAYS"]  # CompareFrag, Mesa sid.h V_028800_FRAG_*
DRAW = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+):.*\| rt0 (\S+) (\S+) info \S+ mask (\S+) .*\| ps (\S+) es (\S+) gs (\S+)")
DB = re.compile(r"^bake db buf (\d+) at (\d+): depth_control (\S+) stencil_control (\S+) refmask (\S+) refmask_bf (\S+) shader_control (\S+)"
                r" render_control (\S+) render_override (\S+) \| z_info (\S+) stencil_info (\S+) view (\S+) size_xy (\S+) \| z_read (\S+)"
                r" stencil_read (\S+) z_write (\S+) stencil_write (\S+) htile (\S+) \| bounds (\S+)\.\.(\S+) clear z (\S+) s (\S+)")
T = re.compile(r"\bt (\d+\.\d+)")
rows, t, pend = [], 0.0, {}
for line in open(path, errors="replace"):
    if line.startswith("timing: t ") or line.startswith("frame profile: t "):
        m = T.search(line)
        if m:
            t = float(m[1])
        continue
    m = DRAW.match(line)
    if m:
        pend[(m[1], m[3])] = {"t": t, "buf": int(m[1]), "at": int(m[3]), "rt": m[4], "size": m[5], "mask": m[6], "ps": m[7].lower(),
                              "es": m[8], "gs": m[9]}
        continue
    m = DB.match(line)
    if m and (m[1], m[2]) in pend:
        r = pend.pop((m[1], m[2]))
        dc, sc, rm = int(m[3], 16), int(m[4], 16), int(m[5], 16)
        r.update(dc=dec("DB_DEPTH_CONTROL", dc), sc=dec("DB_STENCIL_CONTROL", sc), rm=dec("DB_STENCILREFMASK", rm),
                 shc=dec("DB_SHADER_CONTROL", int(m[7], 16)), zi=dec("DB_Z_INFO", int(m[10], 16)), si=dec("DB_STENCIL_INFO", int(m[11], 16)),
                 zr=m[14], sr=m[15], zw=m[16], sw=m[17], ht=m[18], raw=(m[3], m[4], m[5], m[7], m[8]))
        rows.append(r)


def ds(r):
    dc, sc, rm = r["dc"], r["sc"], r["rm"]
    z = "Z %s%s %s" % ("on" if dc.get("Z_ENABLE") else "off", "+write" if dc.get("Z_WRITE_ENABLE") else "", FUNC[dc.get("ZFUNC", 0)])
    s = "stencil %s" % ("off" if not dc.get("STENCIL_ENABLE") else "%s ref %d mask %02x wmask %02x fail/zpass/zfail %d/%d/%d" % (
        FUNC[dc.get("STENCILFUNC", 0)], rm.get("STENCILTESTVAL", 0), rm.get("STENCILMASK", 0), rm.get("STENCILWRITEMASK", 0),
        sc.get("STENCILFAIL", 0), sc.get("STENCILZPASS", 0), sc.get("STENCILZFAIL", 0)))
    return "%s, %s, kill %d z_export %d" % (z, s, r["shc"].get("KILL_ENABLE", 0), r["shc"].get("Z_EXPORT_ENABLE", 0))


def bufs(r):
    return "z %s/%s fmt %d sw %d, stencil %s/%s fmt %d sw %d" % (r["zr"], r["zw"], r["zi"].get("FORMAT", 0), r["zi"].get("SW_MODE", 0),
                                                              r["sr"], r["sw"], r["si"].get("FORMAT", 0), r["si"].get("SW_MODE", 0))


print("# %s: %d draws with depth/stencil lines; target pixel shader %s" % (path, len(rows), TARGET))
print("(1) the target's depth/stencil state:")
for k, n in collections.Counter((ds(r), bufs(r), r["raw"]) for r in rows if r["ps"] == TARGET).most_common():
    print("  %3d x %s | %s | raw depth_control/stencil_control/refmask/shader_control/render_control %s" % (n, k[0], k[1], "/".join(k[2])))
print("(2) passes in journal order:")
runs = []
for r in rows:
    key = (r["rt"], r["size"], r["mask"], r["ps"], ds(r), bufs(r))
    if runs and runs[-1][0] == key and runs[-1][1]["buf"] == r["buf"]:
        runs[-1][2] += 1
    else:
        runs.append([key, r, 1])
for k, (key, r, n) in enumerate(runs):
    print("  #%-4d t %.3f buf %-3d at %-6d %3d x rt0 %s %s mask %s ps %s | %s | %s%s" % (
        k, r["t"], r["buf"], r["at"], n, key[0], key[1], key[2], key[3], key[4], key[5], " <== TARGET" if key[3] == TARGET else ""))
print("(3) depth/stencil writers before each target draw, into the buffers the target tests:")
for i, r in enumerate(rows):
    if r["ps"] != TARGET:
        continue
    zbuf, sbuf = r["zr"], r["sr"]
    w = collections.Counter()
    for q in rows[max(0, i - 400):i]:
        if q["t"] < r["t"] - 0.05:
            continue
        zw = q["dc"].get("Z_ENABLE") and q["dc"].get("Z_WRITE_ENABLE") and q["zw"] == zbuf
        sw = (q["dc"].get("STENCIL_ENABLE") and q["rm"].get("STENCILWRITEMASK", 0) and q["sw"] == sbuf and
              (q["sc"].get("STENCILZPASS", 0) or q["sc"].get("STENCILFAIL", 0) or q["sc"].get("STENCILZFAIL", 0)))
        if zw or sw:
            w[(q["ps"], q["rt"], "depth" if zw else "", "stencil" if sw else "")] += 1
    print("  target at t %.3f buf %d at %d (z %s, stencil %s): %s" % (r["t"], r["buf"], r["at"], zbuf, sbuf,
          "; ".join("%d x ps %s rt0 %s %s %s" % (n, *k) for k, n in w.most_common(12)) or "no depth/stencil writer in the 50 ms before"))
