#!/usr/bin/env python3
# BC5 experiment 0282: one burst of back-to-back reads of the night lake's depth image, read-only through
# /proc/<pid>/mem (as exp 0212's mem0212.py; yama ptrace_scope 0 on the box, no ptrace attach). K reads of the depth
# range, started PERIOD ms apart (or back to back when a read and its write take longer; 0 = back to back), then one
# read of the G-buffer range for the size check. Each read is written to <out prefix>.z<k>.bin / <out prefix>.g.bin as
# soon as it is taken, so no burst is held in memory (the box has little free memory while the title runs).
# Prints one line per read: "<name> start <ms> read <ms> write <ms> bytes <n>", the start relative to the burst's first
# read (time.monotonic). A range that cannot be read is reported, not fatal.
# usage: burst0282.py <pid> <out prefix> <K> <period ms> <depth base hex>:<size hex> <G-buffer base hex>:<size hex>
import os, sys, time

pid, out, k_reads, period = int(sys.argv[1]), sys.argv[2], int(sys.argv[3]), float(sys.argv[4]) / 1000
(zb, zs), (gb, gs) = [(int(b, 16), int(s, 16)) for b, s in (a.split(":") for a in sys.argv[5:7])]
fd = os.open("/proc/%d/mem" % pid, os.O_RDONLY)
t00 = time.monotonic()


def take(name, base, size):
    t0 = time.monotonic()
    try:
        data = os.pread(fd, size, base)
    except OSError as e:
        print("%s start %.1f error %s" % (name, (t0 - t00) * 1000, e))
        return
    t1 = time.monotonic()
    with open("%s.%s.bin" % (out, name), "wb") as f:
        f.write(data)
    t2 = time.monotonic()
    print("%s start %.1f read %.1f write %.1f bytes %d" % (name, (t0 - t00) * 1000, (t1 - t0) * 1000, (t2 - t1) * 1000,
                                                          len(data)))


for k in range(k_reads):
    wait = t00 + k * period - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    take("z%d" % k, zb, zs)
take("g", gb, gs)
