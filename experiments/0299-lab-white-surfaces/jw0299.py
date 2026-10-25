#!/usr/bin/env python3
# BC5 experiment 0299: the lab frame's passes from a run's draw journal (BC5_DIRECT_DRAW_JOURNAL=<t0>:<buffers>, exp
# 0089: every draw and dispatch of the graphics buffers submitted from t0 on, with colour target 0, CB_TARGET_MASK, the
# viewport and the PS/ES/GS/CS programs). Prints:
#  - per buffer, the events in order, consecutive repeats folded ("x n"): the packet (PM4 opcode from the header, names
#    as tools/bc5-agc/regdb/pm4-opcodes.tsv), the program (PS for a draw, CS for a dispatch; a dispatch's groups from
#    DISPATCH_DIRECT's X Y Z), colour target 0 (base, size, CB_COLOR0_INFO's FORMAT bits 6:2 and NUMBER_TYPE bits
#    10:8, names from tools/bc5-agc/regdb/gfx10.json's ColorFormat and SurfaceNumber enums, at 123cfd9), the target
#    mask and the viewport;
#  - per program, its count, packets, target formats and sizes, over the whole journal.
# Descriptors and counts only. Stdlib only.
# usage: python3 -I jw0299.py <direct.log> [max rows]
import collections, re, sys

FMT = {0: 'INVALID', 1: '8', 2: '16', 3: '8_8', 4: '32', 5: '16_16', 6: '10_11_11', 7: '11_11_10', 8: '10_10_10_2',
       9: '2_10_10_10', 10: '8_8_8_8', 11: '32_32', 12: '16_16_16_16', 13: 'RESERVED_13', 14: '32_32_32_32',
       15: 'RESERVED_15', 16: '5_6_5', 17: '1_5_5_5', 18: '5_5_5_1', 19: '4_4_4_4', 20: '8_24', 21: '24_8',
       22: 'X24_8_32_FLOAT', 31: '2_10_10_10_6E4'}
NUM = {0: 'UNORM', 1: 'SNORM', 2: 'USCALED', 3: 'SSCALED', 4: 'UINT', 5: 'SINT', 6: 'SRGB', 7: 'FLOAT'}
OPS = {0x15: 'DISPATCH_DIRECT', 0x16: 'DISPATCH_INDIRECT', 0x24: 'DRAW_INDIRECT', 0x25: 'DRAW_INDEX_INDIRECT',
       0x27: 'DRAW_INDEX_2', 0x2c: 'DRAW_INDIRECT_MULTI', 0x2d: 'DRAW_INDEX_AUTO', 0x2e: 'DRAW_INDEX_IMMD',
       0x30: 'DRAW_INDEX_MULTI_AUTO', 0x35: 'DRAW_INDEX_OFFSET_2', 0x38: 'DRAW_INDEX_INDIRECT_MULTI'}
RE = re.compile(r"^draw journal buf (\d+) \((\d+) dwords\) at (\d+):((?: [0-9a-f]{8})*) \| rt0 ([0-9a-f]+) (\d+)x(\d+) info ([0-9a-f]+) mask ([0-9a-f]+)"
                r" \| vp (\S+) at (\S+) \| ps ([0-9a-f]+) es ([0-9a-f]+) gs ([0-9a-f]+) cs ([0-9a-f]+)")
log = sys.argv[1]
cap = int(sys.argv[2]) if len(sys.argv) > 2 else 900
events, windows = [], []
for l in open(log, errors="replace"):
    if l.startswith("draw journal window"):
        windows.append(l.strip()[:160])
        continue
    if not l.startswith("draw journal buf"):
        continue
    m = RE.match(l)
    if not m:
        continue
    words = m[4].split()
    hdr = int(words[0], 16) if words else 0
    op = (hdr >> 8) & 0xff if hdr >> 30 == 3 else -1
    disp = op in (0x15, 0x16)
    groups = ""
    if op == 0x15 and len(words) >= 4:
        groups = " %dx%dx%d" % tuple(int(w, 16) for w in words[1:4])
    info = int(m[8], 16)
    fmt = "%s_%s" % (FMT.get((info >> 2) & 0x1f, "?%d" % ((info >> 2) & 0x1f)), NUM.get((info >> 8) & 7, "?"))
    events.append({"buf": int(m[1]), "dwords": int(m[2]), "op": OPS.get(op, "op%02x" % op if op >= 0 else "?"), "disp": disp,
                   "prog": m[15] if disp else m[12], "groups": groups, "rt": m[5], "size": "%sx%s" % (m[6], m[7]), "fmt": fmt,
                   "mask": m[9], "vp": "%s at %s" % (m[10], m[11])})
print("# %s: %d journalled events in %d buffers; %d window lines" % (log, len(events), len({e["buf"] for e in events}), len(windows)))
for w in windows[:5]:
    print("  " + w)
print("# events in order per buffer, repeats folded (dispatch: cs and groups; draw: ps, colour target 0, mask, viewport)")
rows, last, n, buf = 0, None, 0, None


def flush():
    global rows
    if last is None:
        return
    e = last
    if e["disp"]:
        print("    %-18s cs %s%s%s" % (e["op"], e["prog"], e["groups"], " x%d" % n if n > 1 else ""))
    else:
        print("    %-18s ps %s | rt0 %s %s %s mask %s | vp %s%s" % (e["op"], e["prog"], e["rt"], e["size"], e["fmt"], e["mask"], e["vp"],
                                                           " x%d" % n if n > 1 else ""))
    rows += 1


for e in events:
    if rows >= cap:
        break
    if e["buf"] != buf:
        flush()
        last, n = None, 0
        buf = e["buf"]
        print("  buf %d (%d dwords)" % (buf, e["dwords"]))
    key = (e["op"], e["prog"], e["groups"], e["rt"], e["size"], e["fmt"], e["mask"], e["vp"])
    if last is not None and key == (last["op"], last["prog"], last["groups"], last["rt"], last["size"], last["fmt"], last["mask"], last["vp"]):
        n += 1
        continue
    flush()
    last, n = e, 1
flush()
print("# per program over the journal: count, packets, colour-target formats and sizes (draws) or groups (dispatches)")
per = collections.defaultdict(list)
for e in events:
    per[("cs" if e["disp"] else "ps", e["prog"])].append(e)
for (k, p), es in sorted(per.items(), key=lambda kv: -len(kv[1])):
    ops = collections.Counter(e["op"] for e in es)
    if k == "cs":
        detail = ", ".join("%s %d" % kv for kv in collections.Counter(e["groups"].strip() or "-" for e in es).most_common(4))
    else:
        detail = ", ".join("%s %s %d" % (s, f, c) for (s, f), c in collections.Counter((e["size"], e["fmt"]) for e in es).most_common(4))
    print("  %s %s: %d (%s) | %s" % (k, p, len(es), ", ".join("%s %d" % kv for kv in ops.most_common(3)), detail))
