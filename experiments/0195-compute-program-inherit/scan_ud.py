#!/usr/bin/env python3
# Experiment 0195: find captured command buffers that carry the user-data layout of program
# 0x11d039cd00 (COMPUTE_USER_DATA_0..3 = aef90000 00300011 00069000 00005204) and print, for each,
# the packets before the first such dispatch and every COMPUTE_PGM_LO/HI write in the buffer.
# Usage: scan_ud.py <file>...   (raw little-endian dword dumps, e.g. ib-*.bin)
import struct
import sys

PAT = (0x00000240, 0xAEF90000, 0x00300011, 0x00069000, 0x00005204)
NAMES = {0x58: "ACQUIRE_MEM", 0x9F: "LOAD_CONTEXT_REG_INDEX", 0x63: "LOAD_SH_REG_INDEX",
         0x64: "LOAD_UCONFIG_REG_INDEX", 0x76: "SET_SH_REG", 0x15: "DISPATCH_DIRECT",
         0x16: "DISPATCH_INDIRECT", 0x79: "SET_UCONFIG_REG", 0x49: "RELEASE_MEM",
         0x12: "CLEAR_STATE", 0x69: "SET_CONTEXT_REG", 0x10: "NOP", 0x28: "CONTEXT_CONTROL"}


def packets(d):
    i = 0
    while i < len(d):
        h = d[i]
        t = h >> 30
        n = 1
        if t in (0, 3):
            c = (h >> 16) & 0x3FFF
            n = 1 if c == 0x3FFF else c + 2
        if i + n > len(d):
            break
        yield i, t, (h >> 8) & 0xFF, d[i:i + n]
        i += n


def main():
    for path in sys.argv[1:]:
        with open(path, "rb") as f:
            raw = f.read()
        d = struct.unpack("<%dI" % (len(raw) // 4), raw[: len(raw) // 4 * 4])
        hits = [i for i in range(len(d) - 5) if tuple(d[i:i + 5]) == PAT]
        if not hits:
            continue
        print("== %s: %d dwords, layout at %s" % (path, len(d), hits[:8]))
        first = hits[0] - 1
        pgm = []
        for off, t, op, p in packets(d):
            if t != 3:
                continue
            if op == 0x76 and len(p) >= 3:
                base = p[1] & 0xFFFF
                for k, v in enumerate(p[2:]):
                    if base + k in (0x20C, 0x20D):
                        pgm.append((off, base + k, v))
            if first - 120 <= off <= first + 70:
                body = " ".join("%08x" % x for x in p[1:9])
                print("  %5d: %-24s %s%s" % (off, NAMES.get(op, "op %02x" % op), body, " ..." if len(p) > 9 else ""))
        near = [w for w in pgm if w[0] < first]
        print("  COMPUTE_PGM writes (SET_SH_REG) before the first dispatch of the layout (last 4):", ["%d:%x=%08x" % w for w in near[-4:]], "; in all", len(pgm))


if __name__ == "__main__":
    main()
