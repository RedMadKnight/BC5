#!/usr/bin/env python3
# Experiment 0201, run X3: who touches the water's textures (raw/X1-X2.txt). (1) Dispatches in the dispatch journal
# (BC5_DIRECT_DISPATCH_JOURNAL=1, user data 0-15 per dispatch) whose user data hold one of the textures' descriptor
# dword0 (base >> 8): counted per program, kind and texture. (2) AMM trace lines (KYTY_BC5_AMM_TRACE=1, the emulator's
# log) with an address inside a texture's window (base .. base + 64 MiB).
# usage: python3 x3scan.py <direct.log> <emulator log>
import collections, re, sys

TEX = {"8492504000": 0x8492504000, "80907c4000": 0x80907c4000, "8001810000": 0x8001810000, "8001010000": 0x8001010000}
DW0 = {format((v >> 8) & 0xffffffff, "08x"): k for k, v in TEX.items()}
DISP = re.compile(r"^\s+(\S+) dispatch op (\S+) at (\d+): pgm (0x[0-9a-f]+) (.*)$")
hits = collections.Counter()
for line in open(sys.argv[1], errors="replace"):
    m = DISP.match(line)
    if not m:
        continue
    words = re.findall(r"\b[0-9a-f]{8}\b", m[5])
    for w in words:
        if w in DW0:
            hits[(m[4], m[1], DW0[w])] += 1
print("dispatches whose user data hold a water texture's descriptor dword0:")
for (pgm, kind, tex), n in sorted(hits.items(), key=lambda x: -x[1]):
    print(f"  pgm {pgm} {kind}: texture 0x{tex}, {n} dispatches")
amm = collections.Counter()
examples = {}
for line in open(sys.argv[2], errors="replace"):
    if "amm" not in line.lower():
        continue
    for h in re.findall(r"0x([0-9a-fA-F]{6,16})", line):
        v = int(h, 16)
        for k, b in TEX.items():
            if b <= v < b + (64 << 20):
                kind = re.sub(r"0x[0-9a-fA-F]+|\d+", "N", line.strip())[:90]
                amm[(k, kind)] += 1
                examples.setdefault((k, kind), line.strip()[:200])
print("AMM trace lines inside a texture window:")
for (k, kind), n in sorted(amm.items(), key=lambda x: -x[1])[:30]:
    print(f"  0x{k}: {n} x {examples[(k, kind)]}")
