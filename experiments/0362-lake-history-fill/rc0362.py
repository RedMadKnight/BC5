#!/usr/bin/env python3
# BC5 experiment 0362, after run H1: exp 0357's late-culling test (cyp0357.py) on its clear full reads only. H1 showed
# that a depth read taken before the frame's last D burst holds no per-pixel depth at the frame's width (fz0362.py,
# sx0362.py), yet exp 0357 labelled every journal-sized read; 30 of its 49 hole reads were unclear. From exp 0357's
# committed raw files: b01.times.txt rebuilt from P1.rd.json (cyp0357.py reads only the name, wall, mono, start and read
# fields), P1.labels2.json kept for the clear reads only, P1.events.txt.gz unpacked. Then run, from exp 0357's directory:
#   python3 -I cyp0357.py <out dir>/events.txt <out dir>/b01.times.txt <out dir>/labels-clear.json 2000
# usage: python3 -I rc0362.py <exp 0357 raw dir> <out dir>
import gzip, json, os, shutil, sys

raw, out = sys.argv[1:3]
os.makedirs(out, exist_ok=True)
rd = json.load(open(os.path.join(raw, "P1.rd.json")))["reads"]
lab = json.load(open(os.path.join(raw, "P1.labels2.json")))
clear = {r["name"]: bool(r.get("clear")) for r in rd if r["kind"] == "z"}
with open(os.path.join(out, "b01.times.txt"), "w") as f:
    for r in rd:
        if r["kind"] == "z":
            f.write("%s wall %.4f mono %.4f start %.1f read %.1f write 0.0 bytes 25559040\n" % (
                r["name"].split(".")[1], r["wall"], r["mono"], r["start_ms"], r["read_ms"]))
kept = dict(lab)
kept["labels"] = {k: v for k, v in lab["labels"].items() if clear.get(k)}
json.dump(kept, open(os.path.join(out, "labels-clear.json"), "w"))
with gzip.open(os.path.join(raw, "P1.events.txt.gz"), "rb") as a, open(os.path.join(out, "events.txt"), "wb") as b:
    shutil.copyfileobj(a, b)
n = {}
for k, v in lab["labels"].items():
    key = "%s %s" % (v, "clear" if clear.get(k) else "unclear")
    n[key] = n.get(key, 0) + 1
print("# exp 0357's labels: %d, of them clear %d; by state and clarity: %s" % (len(lab["labels"]), len(kept["labels"]), dict(sorted(n.items()))))
