#!/usr/bin/env python3
# BC5 (experiment 0200): find the second title's main cinematic players (exp 0153: the object whose tick slews
# its clip time +0xf8 toward the sync clock; +0xc8 == 1 marks a main player, +0x120 & 3 == 3 one synced to the
# clock, +0x548 & 1 one that plays) in the running emulator, read-only via /proc/<pid>/mem.
# - synced: +0x110 is the clock at 0x90ae007b4 unwrapped, as of the player's last tick (exp 0200 test run), so
#   modulo 10 s it is one of the values the clock took in the last frames. The pool is snapshotted between two
#   clock reads and searched at 16-byte-aligned objects.
# - by vtable: objects whose +0 is one of the vtables given (learned from synced players), +0xc8 == 1 and
#   +0x548 & 1, synced or not (an unsynced player advances by the frame time, not by the clock).
# usage: find_player.py <pid> [vtable ...]   (searches the pool 0x1070000000-0x1076800000 that held them)
import os, struct, sys
CLOCK = 0x90ae007b4
LO, HI = 0x1070000000, 0x1076800000

def find(pid, vts=(), lo=LO, hi=HI):
    fd = os.open("/proc/%d/mem" % pid, os.O_RDONLY)
    try:
        c0 = struct.unpack("<f", os.pread(fd, 4, CLOCK))[0]
        snap = bytearray()
        for a in range(lo, hi, 4 << 20):
            snap += os.pread(fd, min(4 << 20, hi - a), a)
        c1 = struct.unpack("<f", os.pread(fd, 4, CLOCK))[0]
    finally:
        os.close(fd)
    def near(v):  # +0x110 is the clock unwrapped (it counts on past the clock's 10-s wrap): modulo 10 it is
        if v != v or not (0.001 < v < 1e6) or v % 10.0 == 0.0:  # one of the clock's values of the last ~0.3 s
            return False
        return (c0 - v) % 10.0 <= 0.3 or (v - c1) % 10.0 <= 0.05
    def sane(obj):  # the rest of the player as in exp 0153 and the test run: a sync source at +0xb0 in guest
        src = struct.unpack_from("<Q", snap, obj + 0xb0)[0]  # direct memory, a clip time and a small debt
        clip, debt = struct.unpack_from("<f", snap, obj + 0xf8)[0], struct.unpack_from("<f", snap, obj + 0x100)[0]
        return 0x1000000000 <= src < 0x2000000000 and clip == clip and 0.0 <= clip < 1e5 and debt == debt and abs(debt) < 100.0
    synced = []
    marks = bytes(snap[0xc8::16])  # stride scan: the +0xc8 bytes of every 16-byte-aligned object
    i = marks.find(1)
    while i >= 0:
        obj = i * 16
        if obj + 0x5f8 <= len(snap) and (snap[obj + 0x120] & 3) == 3:
            if near(struct.unpack_from("<f", snap, obj + 0x110)[0]) and sane(obj):
                synced.append((lo + obj, struct.unpack_from("<Q", snap, obj)[0]))
        i = marks.find(1, i + 1)
    byvt = []
    for vt in vts:
        pat = struct.pack("<Q", vt)
        i = snap.find(pat)
        while i >= 0:
            if i % 16 == 0 and i + 0x5f8 <= len(snap) and snap[i + 0xc8] == 1 and snap[i + 0x548] & 1 and sane(i):
                byvt.append((lo + i, vt))
            i = snap.find(pat, i + 1)
    return sorted(set(synced))[:16], sorted(set(byvt))[:16], c0, c1

if __name__ == "__main__":
    pid = int(sys.argv[1])
    vts = [int(a, 16) for a in sys.argv[2:]]
    synced, byvt, c0, c1 = find(pid, vts)
    print("clock %.3f..%.3f, main-player candidates: %s; by vtable: %s" % (
        c0, c1, " ".join("0x%x/%x" % o for o in synced) or "none", " ".join("0x%x/%x" % o for o in byvt) or "none"))
