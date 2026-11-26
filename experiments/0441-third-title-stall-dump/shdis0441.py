#!/usr/bin/env python3
"""Experiment 0441 follow-up: disassemble one compute program from a dump's program bytes (private output).

  shdis0441.py <view-file> <view-base> <program-address> <out.s> [first-dword last-dword ...]

Reads the program's dwords up to its first s_endpgm from the dumped view file, runs LLVM's disassembler in the
ubuntu container (llvm-mc --disassemble -triple=amdgcn -mcpu=gfx1013 -show-encoding), maps every decoded
instruction back to its dword index by its encoding bytes, writes the listing (dword index, address, text) to
<out.s>, and prints the dword windows asked for. The listing is title code: private, never in git.
"""
import re
import struct
import subprocess
import sys


def main():
    view, base, pgm, out = sys.argv[1], int(sys.argv[2], 0), int(sys.argv[3], 0), sys.argv[4]
    wins = [int(x, 0) for x in sys.argv[5:]]
    with open(view, "rb") as f:
        f.seek(pgm - base)
        raw = f.read(0x40000)
    dw = struct.unpack("<%dI" % (len(raw) // 4), raw)
    end = next((i for i, w in enumerate(dw) if w == 0xBF810000), None)
    if end is None:
        print("no s_endpgm word found")
        return 1
    data = raw[:(end + 1) * 4]
    hexfile = out + ".hex"
    with open(hexfile, "w") as f:
        f.write(" ".join("0x%02x" % b for b in data) + "\n")
    r = subprocess.run(["distrobox", "enter", "ubuntu", "--", "llvm-mc", "--disassemble", "-triple=amdgcn", "-mcpu=gfx1013",
                        "-show-encoding", hexfile], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300)
    pos = 0
    rows = []
    bad = 0
    for line in r.stdout.splitlines():
        m = re.search(r"^\s*(\S.*?)\s*[;#@]\s*encoding:\s*\[([^\]]*)\]", line)
        if not m:
            continue
        enc = bytes(int(x, 16) for x in m.group(2).split(","))
        at = data.find(enc, pos)
        while at >= 0 and at % 4:
            at = data.find(enc, at + 1)
        if at < 0:
            bad += 1
            continue
        if at != pos:
            rows.append((pos // 4, "(%d dwords not decoded)" % ((at - pos) // 4)))
        rows.append((at // 4, m.group(1)))
        pos = at + len(enc)
    with open(out, "w") as f:
        for i, t in rows:
            f.write("%6d  %#x  %s\n" % (i, pgm + 4 * i, t))
    print("program %#x: %d dwords, %d instructions decoded, %d not placed, %d stderr lines; listing %s" % (
        pgm, end + 1, len(rows), bad, len(r.stderr.splitlines()), out))
    for k in range(0, len(wins) - 1, 2):
        lo, hi = wins[k], wins[k + 1]
        print("== dwords %d..%d" % (lo, hi))
        for i, t in rows:
            if lo <= i <= hi:
                print("%6d  %s" % (i, t))
    return 0


if __name__ == "__main__":
    sys.exit(main())
