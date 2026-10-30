# BC5 experiment 0379, test shortcut: two zero lists compared per heap, in 2 MiB chunks (bc5/zero_skip.hpp's format).
# Both lists hold runs of at least 8 MiB of chunks zero in every scan, as offsets from the heap's start. Prints, per heap:
# the MiB in each list, in both, only in A, only in B, and the runs (offset, MiB) of "only in A" = zero in every scan of A
# but not listed in B (written, or in a run shorter than 8 MiB, during B's session).
# usage: python -I cmp0379t.py <list A> <list B>
import sys
CH = 2 << 20
def load(p):
    heaps, chunks = {}, {}
    for line in open(p):
        f = line.split()
        if not f or f[0].startswith("#"): continue
        if f[0] == "heap": heaps[f[1]] = (int(f[2], 16), int(f[3])); chunks.setdefault(f[1], set())
        elif f[0] == "zero":
            o, n = int(f[2], 16), int(f[3], 16)
            chunks.setdefault(f[1], set()).update(range(o // CH, (o + n) // CH))
    return heaps, chunks
def runs(s):
    out, cur = [], None
    for c in sorted(s):
        if cur and c == cur[1]: cur[1] += 1
        else:
            if cur: out.append(cur)
            cur = [c, c + 1]
    if cur: out.append(cur)
    return [(a * CH, (b - a) * 2) for a, b in out]
ha, ca = load(sys.argv[1]); hb, cb = load(sys.argv[2])
print(f"A {sys.argv[1]}\nB {sys.argv[2]}")
for h in sorted(set(ca) | set(cb)):
    a, b = ca.get(h, set()), cb.get(h, set())
    print(f"{h}: span A {ha.get(h, (0, 0))[0] >> 20} MiB ({ha.get(h, (0, 0))[1]} scans), B {hb.get(h, (0, 0))[0] >> 20} MiB ({hb.get(h, (0, 0))[1]} scans); "
          f"A {2 * len(a)} MiB, B {2 * len(b)} MiB, both {2 * len(a & b)} MiB, only A {2 * len(a - b)} MiB, only B {2 * len(b - a)} MiB")
    ra = runs(a - b)
    print(f"  only in A: {len(ra)} runs; the largest: " + ", ".join(f"+0x{o:x} {m} MiB" for o, m in sorted(ra, key=lambda r: -r[1])[:8]))
