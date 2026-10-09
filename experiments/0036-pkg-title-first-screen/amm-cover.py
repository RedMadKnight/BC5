import re, sys
log = sys.argv[1]
targets = [int(x, 16) for x in sys.argv[2:]]
rx = re.compile(r"map auto va 0x([0-9a-f]+) size 0x([0-9a-f]+) dmem 0x([0-9a-f]+) type (\d+) prot 0x([0-9a-f]+)")
rd = re.compile(r"read file (0x[0-9a-f]+) \+0x([0-9a-f]+) size 0x([0-9a-f]+) -> 0x([0-9a-f]+)")
maps = []
overl = 0
with open(log, errors="replace") as f:
    for n, line in enumerate(f, 1):
        m = rx.search(line)
        if m:
            va, sz, dm = int(m[1], 16), int(m[2], 16), int(m[3], 16)
            for (n2, va2, sz2, dm2) in maps:
                if va < va2 + sz2 and va2 < va + sz and overl < 15:
                    overl += 1
                    print(f"overlap: line {n} va {va:#x}+{sz:#x} dmem {dm:#x} over line {n2} va {va2:#x}+{sz2:#x} dmem {dm2:#x}")
            maps.append((n, va, sz, dm))
            for t in targets:
                if va <= t < va + sz:
                    print(f"map covers {t:#x}: line {n}: {line.strip()}")
        m = rd.search(line)
        if m:
            dst, sz = int(m[4], 16), int(m[3], 16)
            for t in targets:
                if dst <= t < dst + sz:
                    print(f"read covers {t:#x}: line {n}: {line.strip()}")
print("maps", len(maps), "overlaps", overl)
# dmem aliasing: same dmem range used by two VAs
d = {}
al = 0
for (n, va, sz, dm) in maps:
    for (n2, va2, sz2, dm2) in maps:
        if n2 < n and dm < dm2 + sz2 and dm2 < dm + sz and va != va2:
            al += 1
            if al <= 10:
                print(f"dmem alias: line {n} va {va:#x} dmem {dm:#x}+{sz:#x} with line {n2} va {va2:#x} dmem {dm2:#x}+{sz2:#x}")
print("aliases", al)
