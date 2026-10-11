#!/usr/bin/env python3
# BC5 experiment 0049: look for the ray tracing instructions in dumped shader programs (gfx1013).
# image_bvh_intersect_ray / image_bvh64_intersect_ray assemble to a first dword 0xF1989F01 /
# 0xF19C9F01 (llvm-mc -mcpu=gfx1013 -show-encoding); the scan takes every dword with
# (w & 0xFFF80000) == 0xF1980000 inside the program (up to the first s_endpgm followed by padding)
# and disassembles a window around it to confirm. Usage: rtscan.py DIR
import glob
import os
import struct
import subprocess
import sys

ENDPGM, CODE_END = 0xBF810000, 0xBF9F0000
d = sys.argv[1]
files = sorted(glob.glob(os.path.join(d, "*.bin")))
progs_with_rt, total_hits, code_dwords = [], 0, 0
for path in files:
    raw = open(path, "rb").read()
    words = struct.unpack("<%dI" % (len(raw) // 4), raw[: len(raw) // 4 * 4])
    end = len(words)
    for i, w in enumerate(words):
        if w == ENDPGM:
            tail = words[i + 1 : i + 9]
            if not tail or all(t in (CODE_END, 0) for t in tail):
                end = i + 1
                break
    code_dwords += end
    hits = [i for i in range(end) if (words[i] & 0xFFF80000) == 0xF1980000]
    confirmed = []
    for i in hits:
        window = raw[i * 4 : i * 4 + 8]
        text = " ".join("0x%02x" % b for b in window)
        r = subprocess.run(["llvm-mc", "-arch=amdgcn", "-mcpu=gfx1013", "--disassemble"], input=text,
                           capture_output=True, text=True)
        line = next((l.strip() for l in r.stdout.splitlines() if "bvh" in l), None)
        if line:
            confirmed.append((i, line))
    if confirmed:
        progs_with_rt.append((os.path.basename(path), end, confirmed))
        total_hits += len(confirmed)

print(f"{len(files)} programs, {code_dwords} dwords of code")
print(f"programs with ray tracing instructions: {len(progs_with_rt)}, instructions: {total_hits}")
for name, end, confirmed in progs_with_rt:
    print(f"  {name}: {end} dwords, {len(confirmed)} x, e.g. dword {confirmed[0][0]}: {confirmed[0][1]}")
