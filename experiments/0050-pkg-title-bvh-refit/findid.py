#!/usr/bin/env python3
# Find the package file whose guest path hashes (FNV-1a, 31 bits, as libAmpr's ComputeFileId)
# to a given APR file id; then show what the file holds at an offset. Private: prints a path.
# Usage: findid.py ID OFFSET LEN   (run where the package is mounted at ~/bc5-data/mnt/pkg-game)
import os
import struct
import sys

want, off, n = int(sys.argv[1], 16), int(sys.argv[2], 16), int(sys.argv[3], 16)
root = os.path.expanduser("~/bc5-data/mnt/pkg-game")


def fnv(s):
    h = 2166136261
    for b in s.encode():
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return h & 0x7FFFFFFF


hit = None
for dp, dn, fn in os.walk(root):
    for f in fn:
        rel = os.path.relpath(os.path.join(dp, f), root)
        for cand in ("/app0/" + rel, "/app0//" + rel, rel, "/" + rel):
            if fnv(cand) == want:
                hit = (os.path.join(dp, f), cand)
if not hit:
    print("no file hashes to", hex(want))
    sys.exit(1)
print("file:", hit[1])
with open(hit[0], "rb") as fh:
    fh.seek(off)
    data = fh.read(n)
words = struct.unpack("<%dI" % (len(data) // 4), data)
print("first dwords:", " ".join("%08x" % w for w in words[:8]))
nz = sum(1 for w in words[0xf80 // 4:0x1268 // 4] if w)
print("dwords 0xf80..0x1268 not zero in the file:", nz, "of", (0x1268 - 0xf80) // 4)
print("at 0xf80:", " ".join("%08x" % w for w in words[0xf80 // 4:0xf80 // 4 + 16]))
