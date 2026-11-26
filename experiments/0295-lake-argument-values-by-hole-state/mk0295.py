#!/usr/bin/env python3
# BC5 experiment 0295: a synthetic capture for pl0295.py's reading path (the part that needs numpy and the files of a
# real capture), checked on the box before the run. Writes <dir>/direct.log (12 "draw journal args" lines), <dir>/cap
# (3 bursts of 8 argument and depth reads in capa0287.py's layout; depth reads of 16384 float words, one plateau per frame
# of 3, 3 and 2 reads; the last word 0.0 for an X frame, which the de-swizzle spreads over the whole lake window, 0.5
# for a Y frame; record 0x1000 follows the hole state, the others change every frame) and <dir>/reads.json (rd0287.py's
# fields that pl0295.py uses). Expected from pl0295.py: plateaus z0-2, z3-5, z6-7 per burst; record 1000 on top, equal in
# every same-family pair. No title data.
# usage: python3 -I mk0295.py <dir>
import json, os, struct, sys

d = sys.argv[1]
os.makedirs(os.path.join(d, "cap"), exist_ok=True)
recs = [0x1000 + 0x20 * i for i in range(12)]
with open(os.path.join(d, "direct.log"), "w") as f:
    for i, r in enumerate(recs):
        f.write("draw journal args buf 1 at %d: op 2c base1 1000 +0x%x\n" % (i, r - 0x1000))
length = recs[-1] + 32 - 0x1000
states = {"b01": "XXXYYYXX", "b02": "YYYXXXYY", "b03": "XXXXXXYY"}
reads, fams = [], {"X": [], "Y": []}
for bn, (b, st) in enumerate(sorted(states.items())):
    rows = []
    for k in range(8):
        frame = k // 3
        state = st[k]
        rec = bytearray(length)
        for i, r in enumerate(recs):
            v = (300 if state == "X" else 500) if i == 0 else 10 * bn + frame + i
            struct.pack_into("<4I", rec, r - 0x1000, v, 1, 0, 0)
        open(os.path.join(d, "cap", "%s.a%d.bin" % (b, k)), "wb").write(rec)
        z = [0.25] * 16384
        z[0] = 0.001 * (10 * bn + frame + 1)
        z[-1] = 0.0 if state == "X" else 0.5
        open(os.path.join(d, "cap", "%s.z%d.bin" % (b, k)), "wb").write(struct.pack("<16384f", *z))
        w = 1000.0 + 11 * bn + 0.03 * k
        rows.append("a%d wall %.4f mono %.4f start %.1f read 0.1 write 0.0 bytes %d ranges 1000:%x" % (k, w - 0.002, w, 30.0 * k, length, length))
        rows.append("z%d wall %.4f mono %.4f start %.1f read 8.0 write 0.0 bytes 65536" % (k, w, w, 30.0 * k))
        name = "%s.z%d" % (b, k)
        reads.append({"name": name, "burst": b, "kind": "z", "wall": w, "clear": True, "best": 2048,
                      "sizes": {"2048": {"share": 1.0 if state == "X" else 0.0}}})
        fams[state].append(name)
    open(os.path.join(d, "cap", "%s.times.txt" % b), "w").write("\n".join(rows) + "\n")
json.dump({"capture": d, "families": [{"name": n, "reads": v} for n, v in fams.items()], "reads": reads},
          open(os.path.join(d, "reads.json"), "w"))
print("# synthetic capture in %s: 3 bursts, %d records" % (d, len(recs)))
