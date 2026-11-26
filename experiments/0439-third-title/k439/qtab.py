# BC5 exp 0439 (problem 3): the queue table at a moment of the run, through /proc/<pid>/mem. For every registered queue
# (the play log's "queue reg:" lines): the doorbell (the guest's write pointer, dword offset, as queue_consumer_thread
# reads it: page qword [d - 1] modulo the ring size), the host's consumed pointer (the consumer writes it to the queue's
# rptr address and to the dword right behind the ring: bc5LleAgc.cpp queue_consumer_thread), whether they differ, and
# any non-zero ring dwords past the doorbell (work written whose doorbell was not rung). Also the semaphore labels
# 0..15 and the tail write of each queue's last IB (opcode, address, data). Private output only.
#   python3 -I qtab.py <pid> <play-last.log> <tag>
import re
import sys

pid, logf, tag = int(sys.argv[1]), sys.argv[2], sys.argv[3]
mem = open(f"/proc/{pid}/mem", "rb")


def rd(a, n):
    mem.seek(a)
    b = mem.read(4 * n)
    return [int.from_bytes(b[4 * i:4 * i + 4], "little") for i in range(len(b) // 4)]


def a64(l, h):
    return (l & ~3) | ((h & 0xffff) << 32)


qs = []
for line in open(logf, errors="replace"):
    m = re.search(r"queue reg: (\d+) (\d+) (\d+) 0x([0-9a-f]+) ring 0x([0-9a-f]+)-0x([0-9a-f]+) doorbell 0x([0-9a-f]+)\+0x([0-9a-f]+) rptr 0x([0-9a-f]+)", line)
    if m:
        qs.append((int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4), 16), int(m.group(5), 16), int(m.group(6), 16), int(m.group(7), 16), int(m.group(9), 16)))
print(f"== {tag}: {len(qs)} queues")
pages = {}
for (a, b, c, d, rb, re_, dbp, rp) in qs:
    n = (re_ - rb) // 4
    if dbp not in pages:
        pages[dbp] = rd(dbp, 2 * 64)
    w = pages[dbp][2 * (d - 1)] | (pages[dbp][2 * (d - 1) + 1] << 32)
    wp = w % n
    rpv = rd(rp, 1)[0]
    endv = rd(re_, 1)[0]
    ring = rd(rb, n)
    past = [i for i in range(wp, n) if ring[i] != 0]
    tail = ""
    i, last = 0, None
    while i < wp:
        h = ring[i]
        ln = ((h >> 16) & 0x3fff) + 2 if (h >> 30) == 3 else 1
        if (h >> 30) == 3 and ((h >> 8) & 0xff) in (0x3f, 0x33):
            last = (a64(ring[i + 1], ring[i + 2]), ring[i + 3] & 0xfffff)
        i += ln
    if last:
        ib = rd(last[0], last[1])
        j, tw = 0, None
        while j < len(ib):
            h = ib[j]
            ln = ((h >> 16) & 0x3fff) + 2 if (h >> 30) == 3 and ((h >> 16) & 0x3fff) != 0x3fff else 1
            op = (h >> 8) & 0xff
            if (h >> 30) == 3 and op == 0x37 and ((ib[j + 1] >> 8) & 0xf) in (1, 2, 5) and j + 5 < len(ib):
                tw = f"WRITE_DATA 0x{a64(ib[j + 2], ib[j + 3]):x} = 0x{ib[j + 5]:x}{ib[j + 4]:08x}"
            elif (h >> 30) == 3 and op == 0x49 and j + 7 < len(ib) and ((ib[j + 2] >> 29) & 7) != 0:
                tw = f"RELEASE_MEM 0x{a64(ib[j + 3], ib[j + 4]):x} = 0x{ib[j + 6]:x}{ib[j + 5]:08x}"
            j += ln
        tail = f" last IB 0x{last[0]:x}+{last[1]} tail {tw}"
    flag = "" if (rpv == wp and endv == wp) else "  <== DIFFER"
    if w or past or rpv or endv:
        print(f"q {a}/{b}/{c}/0x{d:x}: doorbell {wp} consumed(rptr) {rpv} consumed(ring end) {endv}; non-zero dwords past doorbell {len(past)}{flag}{tail}")
lab = rd(0x2000000000, 16 * 8)
print("labels 0..15: " + " ".join(f"{k}={lab[8 * k] | (lab[8 * k + 1] << 32):x}" for k in range(16)))
