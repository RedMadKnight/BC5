#!/usr/bin/env bash
# Scan the title executable and its modules for the 170 MHz constant (private input, stdout only).
M=~/bc5-data/mnt/pkg-game
~/bc5-work/bc5-tools-ubuntu/release/bc5-mount mount ~/bc5-data/pkg/game.pkg $M > /tmp/bc5-cs-mount.log 2>&1 &
P=$!
for i in $(seq 1 30); do mountpoint -q $M && break; sleep 1; done
python3 - $M <<"PY"
import os, struct, sys
root = sys.argv[1]
pats = {"u32 170000000": struct.pack("<I", 170000000), "f32 1.7e8": struct.pack("<f", 1.7e8), "f64 1.7e8": struct.pack("<d", 1.7e8),
        "f32 1.7": struct.pack("<f", 1.7), "f64 1.7": struct.pack("<d", 1.7), "u64 170000000": struct.pack("<Q", 170000000),
        "f64 1/1.7e8": struct.pack("<d", 1 / 1.7e8), "f32 1/1.7e8": struct.pack("<f", 1 / 1.7e8)}
for dp, dn, fn in os.walk(root):
    for f in fn:
        if not (f.endswith((".prx", ".sprx", ".bin", ".elf", ".self")) or f == "eboot.bin"): continue
        p = os.path.join(dp, f)
        try: d = open(p, "rb").read()
        except Exception as e: continue
        hits = {k: d.count(v) for k, v in pats.items() if d.count(v)}
        if hits: print(os.path.relpath(p, root), len(d), hits)
PY
fusermount3 -u $M; wait $P 2>/dev/null
