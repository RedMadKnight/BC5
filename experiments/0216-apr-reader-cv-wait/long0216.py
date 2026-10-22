#!/usr/bin/env python3
# BC5 experiment 0216: the "frame profile" lines of frames over <ms> ms from a run's GPU journal (gc/direct.log), read
# with O_DIRECT at a capped rate as exp 0214's ra0214.py does (no page cache, other sessions' runs not disturbed).
# usage: long0216.py <MB/s> <ms> <journal>   (on the box)
import mmap, os, re, sys, time

FR = re.compile(rb'^frame profile: t ([0-9.]+) s, ([0-9.]+) ms since the last flip;')


def lines(path, rate):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECT)
    buf = mmap.mmap(-1, 4 << 20)
    carry = b''
    t0 = time.monotonic()
    done = 0
    try:
        while True:
            n = os.readv(fd, [buf])
            if n <= 0:
                break
            parts = (carry + buf[:n]).split(b'\n')
            carry = parts.pop()
            yield from parts
            done += n
            wait = done / (rate * 1e6) - (time.monotonic() - t0)
            if wait > 0:
                time.sleep(wait)
            if n < len(buf):
                break
    finally:
        os.close(fd)
    if carry:
        yield carry


rate, limit, path = float(sys.argv[1]), float(sys.argv[2]), sys.argv[3]
for ln in lines(path, rate):
    m = FR.match(ln)
    if m and float(m.group(2)) > limit:
        print(ln[:400].decode('latin-1'))
