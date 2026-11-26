#!/usr/bin/env python3
# Experiment 0195: offline replica of the host's cs_inherit_at() (bc5LleAgc.cpp, BC5_DIRECT_CS_PREFIX) over captured
# graphics buffers: the offset of the first DISPATCH_DIRECT/INDIRECT that comes before anything that may set
# COMPUTE_PGM_LO (SH 0x20c), or -1. LOAD_SH_REG_INDEX pair tables are not readable offline (guest memory), so a
# non-empty one counts as "may set it", as an unreadable table does in the host.
# Usage: inherit_check.py <file>...   (raw little-endian dword dumps)
import struct
import sys

PGM_LO = 0x20C


def inherit_at(d):
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
        if t == 3:
            op = (h >> 8) & 0xFF
            p = d[i:i + n]
            if op in (0x15, 0x16):
                return i
            if op == 0x3F:
                return -1
            if op in (0x76, 0x9B) and n >= 3 and 0 <= PGM_LO - (p[1] & 0xFFFF) < n - 2:
                return -1
            if op == 0x5F and n >= 5:
                for k in range(3, n - 1, 2):
                    if 0 <= PGM_LO - (p[k] & 0xFFFF) < (p[k + 1] & 0x3FFF):
                        return -1
            if op == 0x63 and n >= 5 and (p[4] & 0x3FFF) != 0:
                if (p[3] >> 31) == 0:
                    if 0 <= PGM_LO - (p[3] & 0xFFFF) < (p[4] & 0x3FFF):
                        return -1
                else:
                    return -1  # a pair table: unreadable offline
        i += n
    return -1


def main():
    hits = 0
    for path in sys.argv[1:]:
        raw = open(path, "rb").read()
        d = struct.unpack("<%dI" % (len(raw) // 4), raw[: len(raw) // 4 * 4])
        at = inherit_at(d)
        if at >= 0:
            hits += 1
            print("%s: %d dwords, first dispatch at %d before any program write" % (path, len(d), at))
    print("%d of %d buffers would get the compute prefix" % (hits, len(sys.argv) - 1))


if __name__ == "__main__":
    main()
