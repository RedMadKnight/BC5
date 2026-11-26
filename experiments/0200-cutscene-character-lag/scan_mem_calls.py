#!/usr/bin/env python3
# BC5 (experiment 0200): direct calls (e8 rel32) to the given targets in the running title's text, read from
# /proc/<pid>/mem (no attach). Prints addresses only. usage: scan_mem_calls.py <pid> <lo> <hi> <target>...
import os, struct, sys
pid, lo, hi = int(sys.argv[1]), int(sys.argv[2], 16), int(sys.argv[3], 16)
targets = set(int(t, 16) for t in sys.argv[4:])
fd = os.open("/proc/%d/mem" % pid, os.O_RDONLY)
data = bytearray()
for a in range(lo, hi, 1 << 20):
    data += os.pread(fd, min(1 << 20, hi - a), a)
hits = {t: [] for t in targets}
i = data.find(b"\xe8")
while 0 <= i and i + 5 <= len(data):
    t = lo + i + 5 + struct.unpack_from("<i", data, i + 1)[0]
    if t in hits:
        hits[t].append(lo + i)
    i = data.find(b"\xe8", i + 1)
for t in sorted(hits):
    print("calls to 0x%x: %s" % (t, " ".join("0x%x" % a for a in hits[t][:30])))
