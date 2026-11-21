# BC5 exp 0439 (problem 3): every registered guest queue's ring read through /proc/<pid>/mem at the stall: its
# doorbell (the title's write pointer, a dword offset into the ring, modulo its size, as queue_consumer_thread reads it),
# the INDIRECT_BUFFER packets in the ring, and in each IB every packet that writes [lo, hi): WRITE_DATA 0x37 to
# memory, RELEASE_MEM 0x49 / EVENT_WRITE_EOP 0x47 with data, ATOMIC_MEM 0x1e, DMA_DATA 0x50, MEM_SEMAPHORE 0x39 (any).
# Queues come from the play log's "queue reg:" lines. Private output only.
#   python3 -I ringscan.py <pid> <play-last.log> [lo-hi]
import re
import sys

pid, logf = int(sys.argv[1]), sys.argv[2]
lo, hi = (int(x, 16) for x in (sys.argv[3] if len(sys.argv) > 3 else "2000000000-2000000100").split("-"))
qs = []
for line in open(logf, errors="replace"):
    m = re.search(r"queue reg: (\d+) (\d+) (\d+) 0x([0-9a-f]+) ring 0x([0-9a-f]+)-0x([0-9a-f]+) doorbell 0x([0-9a-f]+)\+0x([0-9a-f]+)", line)
    if m:
        qs.append(tuple(int(m.group(k), 16 if k >= 4 else 10) for k in range(1, 9)))
mem = open(f"/proc/{pid}/mem", "rb")


def rd(a, n):
    mem.seek(a)
    b = mem.read(4 * n)
    return [int.from_bytes(b[4 * i:4 * i + 4], "little") for i in range(len(b) // 4)]


def a64(l, h):
    return (l & ~3) | ((h & 0xffff) << 32)


def writes(base, n, depth=0):
    out = []
    try:
        w = rd(base, n)
    except OSError:
        return [("unreadable", 0, 0)]
    i = 0
    while i < len(w):
        h = w[i]
        t, c = h >> 30, (h >> 16) & 0x3fff
        ln = (c + 2) if t in (0, 3) and c != 0x3fff else 1
        if t == 3 and c != 0x3fff and i + ln <= len(w):
            op, p = (h >> 8) & 0xff, w[i:i + ln]
            a = None
            if op == 0x37 and ln >= 4 and ((p[1] >> 8) & 0xf) in (1, 2, 5):
                a = a64(p[2], p[3])
            elif op == 0x49 and ln >= 7 and ((p[2] >> 29) & 7) != 0:
                a = a64(p[3], p[4])
            elif op == 0x47 and ln >= 6 and ((p[3] >> 29) & 7) != 0:
                a = a64(p[2], p[3])
            elif op == 0x1e and ln >= 4:
                a = a64(p[2], p[3])
            elif op == 0x50 and ln >= 6:
                a = a64(p[4], p[5])
            elif op in (0x3f, 0x33) and ln >= 4 and depth == 0:
                na, nn = a64(p[1], p[2]), p[3] & 0xfffff
                out.append((f"nested IB 0x{na:x}+{nn}", i, 0))
                for (wh, at2, ad) in writes(na, nn, 1):
                    out.append((f"  in nested 0x{na:x}: {wh}", at2, ad))
            elif op == 0x39 and ln >= 3:
                a = (p[1] & ~7) | ((p[2] & 0xffff) << 32)
                out.append(("MEM_SEMAPHORE", i, a))
                a = None
            if a is not None and lo <= a < hi:
                out.append((f"op 0x{op:02x}", i, a))
        i += ln
    return out


db_pages = {}
print(f"{len(qs)} queues; watching 0x{lo:x}-0x{hi:x}")
for (qa, qb, qc, qd, rb, re_, dbp, dbs) in qs:
    n = (re_ - rb) // 4
    if dbp not in db_pages:
        db_pages[dbp] = rd(dbp, 2 * 64)
    dbw = db_pages[dbp]
    wraw = dbw[2 * (qd - 1)] | (dbw[2 * (qd - 1) + 1] << 32) if qd >= 1 else 0
    wp = wraw % n if n else 0
    ring = rd(rb, n)
    ibs = []
    i = 0
    while i < n:
        h = ring[i]
        t, c = h >> 30, (h >> 16) & 0x3fff
        ln = (c + 2) if t in (0, 3) and c != 0x3fff else 1
        if t == 3 and ((h >> 8) & 0xff) in (0x3f, 0x33) and ln >= 4 and i + 3 < n:
            ibs.append((i, a64(ring[i + 1], ring[i + 2]), ring[i + 3] & 0xfffff))
        i += ln
    hits = []
    for (off, a, sz) in ibs:
        if a == 0 or sz == 0:
            continue
        for (what, at, addr) in writes(a, sz):
            if what.startswith("nested IB") and not (qa == 1 and qb == 0 and qc == 0):
                continue
            hits.append(f"ring@{off} IB 0x{a:x}+{sz} @{at} {what} 0x{addr:x}")
    if ibs or wraw:
        print(f"queue {qa}/{qb}/{qc}/0x{qd:x}: doorbell {wraw} (ring offset {wp} of {n}); IBs in ring {len(ibs)}"
              + (f" (last at {ibs[-1][0]})" if ibs else ""))
        for h in hits[:12]:
            print("   " + h)
