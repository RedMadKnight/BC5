#!/usr/bin/env python3
# BC5 experiment 0380 (F580): resolve guest VAs to the direct-memory map, allocation, memory type and name from the
# "bc5-0380 mem:" lines of a play log (memlog0380.py's build). Prints, per target VA, the newest map covering it and
# the allocation covering its physical address, and a summary of the types and names seen. Type names: the PS4
# numbering in shadPS4 src/core/libraries/kernel/memory.h:24-28 (60c42b9); TODO(verify) the PS5's.
# usage: python3 resolve0380m.py <play log> <hex VA>...
import re
import sys
from collections import Counter

TYPES = {0: "WB_ONION", 3: "WC_GARLIC", 10: "WB_GARLIC"}
log, targets = sys.argv[1], [int(v, 16) for v in sys.argv[2:]]
num = r"0x([0-9a-f]+)"
allocs, maps, map2, names, ranges, mtp = [], [], [], [], [], []
for line in open(log, errors="replace"):
    if "bc5-0380 mem: " not in line:
        continue
    body = line.split("bc5-0380 mem: ", 1)[1]
    if m := re.match(rf"alloc phys {num} len {num} type (-?\d+)", body):
        allocs.append((int(m[1], 16), int(m[2], 16), int(m[3])))
    elif m := re.match(rf"map va {num} len {num} phys {num} prot {num} flags {num} type (-?\d+)", body):
        maps.append((int(m[1], 16), int(m[2], 16), int(m[3], 16), int(m[4], 16), int(m[6])))
    elif m := re.match(rf"map2 va {num} len {num} type (-?\d+)", body):
        map2.append((int(m[1], 16), int(m[2], 16), int(m[3])))
    elif m := re.match(rf"name va {num} len {num} name (\S*)", body):
        names.append((int(m[1], 16), int(m[2], 16), m[3]))
    elif m := re.match(rf"rangename va {num} len {num} name (\S*)", body):
        ranges.append((int(m[1], 16), int(m[2], 16), m[3]))
    elif m := re.match(rf"mtypeprotect va {num} len {num} type (-?\d+) prot {num}", body):
        mtp.append((int(m[1], 16), int(m[2], 16), int(m[3]), int(m[4], 16)))


def tname(t):
    return f"{t} ({TYPES.get(t, '?')})"


def cover(lst, a):
    return [x for x in lst if x[0] <= a < x[0] + x[1]]


print(f"lines: alloc {len(allocs)}, map {len(maps)}, map2 {len(map2)}, name {len(names)}, rangename {len(ranges)}, mtypeprotect {len(mtp)}")
print("alloc types:", ", ".join(f"{tname(t)} x{n} ({sum(l for _, l, tt in allocs if tt == t) >> 20} MiB)" for t, n in Counter(t for _, _, t in allocs).most_common()))
print("map2 types:", ", ".join(f"{tname(t)} x{n}" for t, n in Counter(t for *_, t in map2).most_common()) or "-")
print("mtypeprotect types:", ", ".join(f"{tname(t)} x{n}" for t, n in Counter(t for _, _, t, _ in mtp).most_common()) or "-")
for a in targets:
    print(f"== VA 0x{a:x}")
    ms = cover(maps, a)
    if not ms:
        print("   no direct map covers it")
        continue
    va, ln, phys, prot, btype = ms[-1]
    pa = phys + (a - va)
    print(f"   map  va 0x{va:x} len 0x{ln:x} phys 0x{phys:x} prot 0x{prot:x} block type {tname(btype)} ({len(ms)} maps cover it)")
    for x in cover(allocs, pa)[-1:]:
        print(f"   alloc phys 0x{x[0]:x} len 0x{x[1]:x} type {tname(x[2])}")
    for x in cover(map2, a)[-1:]:
        print(f"   map2 type {tname(x[2])}")
    for x in cover(mtp, a)[-1:]:
        print(f"   mtypeprotect type {tname(x[2])} prot 0x{x[3]:x}")
    for x in (cover(names, a) + cover(ranges, a))[-2:]:
        print(f"   name 0x{x[0]:x}+0x{x[1]:x} {x[2]}")
