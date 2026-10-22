#!/usr/bin/env python3
# BC5 experiment 0214: the regression check of KYTY_BC5_APR_READAHEAD from the runs' GPU journals (gc/direct.log).
# Each journal is read with O_DIRECT (no page cache) at a capped rate, so runs of other sessions are not disturbed.
# Per run: flips, flips a second, the mean time between flips, frames over 100/250/1000 ms, GPU-busy frames over 1 s,
# and counts of TIMEOUT, fault, reopen and given-up-wait lines; the same for t >= SKIP s (after the load).
# usage: ra0214.py <MB/s> <skip s> <tag>=<journal> ...   (on the box)
import mmap, os, re, sys, time

FR = re.compile(rb'^frame profile: t ([0-9.]+) s, ([0-9.]+) ms since the last flip;.*?GPU busy ([0-9.]+) ms')
KINDS = [('TIMEOUT', rb'TIMEOUT'), ('fault', rb'[Ff]ault'), ('reopen', rb'reopen'), ('given up', rb'GIVEN UP')]


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
            if n < len(buf):  # end of file; an unaligned offset cannot be read again with O_DIRECT
                break
    finally:
        os.close(fd)
    if carry:
        yield carry


def stats(fr):
    if len(fr) < 2:
        return 'no frames'
    dur = fr[-1][0] - fr[0][0]
    ms = [f[1] for f in fr]
    return ('%6d flips in %6.1f s = %5.1f/s, mean %5.1f ms, >100 ms %4d, >250 ms %3d, >1 s %2d, max %7.1f ms, '
            'GPU busy >1 s %2d' % (len(fr), dur, len(fr) / dur, sum(ms) / len(ms), sum(m > 100 for m in ms),
                                   sum(m > 250 for m in ms), sum(m > 1000 for m in ms), max(ms),
                                   sum(f[2] > 1000 for f in fr)))


def main():
    rate = float(sys.argv[1])
    skip = float(sys.argv[2])
    for arg in sys.argv[3:]:
        tag, path = arg.split('=', 1)
        fr = []
        cnt = {k: 0 for k, _ in KINDS}
        first = {}
        for ln in lines(path, rate):
            m = FR.match(ln)
            if m:
                fr.append((float(m.group(1)), float(m.group(2)), float(m.group(3))))
                continue
            for k, pat in KINDS:
                if re.search(pat, ln):
                    cnt[k] += 1
                    first.setdefault(k, ln[:160].decode('latin-1'))
        late = [f for f in fr if f[0] >= skip]
        print('%-4s %s' % (tag, path))
        print('     all      : ' + stats(fr))
        print('     t >= %3.0f : ' % skip + stats(late))
        print('     lines    : ' + ', '.join('%s %d' % (k, cnt[k]) for k, _ in KINDS))
        for k in first:
            print('       first %s: %s' % (k, first[k]))
        sys.stdout.flush()


main()
