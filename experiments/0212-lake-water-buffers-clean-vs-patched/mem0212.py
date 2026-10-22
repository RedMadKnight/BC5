#!/usr/bin/env python3
# BC5 experiment 0212: read-only memory of the running emulator through /proc/<pid>/mem (yama ptrace_scope 0 on the
# box, as exps 0200 and 0205; no ptrace attach). Two modes:
#   dump <pid> <out prefix> <base hex>:<size hex> ...
#       one pread per range into <out prefix>.<base>.bin (what the bench takes at each frozen-view shot)
#   hash <pid> <out file> <step s> <base hex>:<size hex> ...
#       every <step> s a CRC-32 per 4-KiB page of each range; one line per range and sample:
#       "h <mono> <wall> <base> pages <n> changed <n> [first changed page indexes]", until the process exits
# A range that cannot be read (unmapped) is reported, not fatal.
import os, sys, time, zlib


def ranges(args):
    return [(int(b, 16), int(s, 16)) for b, s in (a.split(":") for a in args)]


def read(fd, base, size):
    try:
        return os.pread(fd, size, base)
    except OSError as e:
        return e


mode, pid = sys.argv[1], int(sys.argv[2])
fd = os.open("/proc/%d/mem" % pid, os.O_RDONLY)
if mode == "dump":
    for base, size in ranges(sys.argv[4:]):
        data = read(fd, base, size)
        if isinstance(data, OSError):
            print("0x%x: %s" % (base, data))
            continue
        with open("%s.%x.bin" % (sys.argv[3], base), "wb") as f:
            f.write(data)
    sys.exit(0)
out, step, rs = open(sys.argv[3], "a", buffering=1), float(sys.argv[4]), ranges(sys.argv[5:])
prev = {}
while os.path.exists("/proc/%d" % pid):
    t = time.monotonic()
    for base, size in rs:
        data = read(fd, base, size)
        if isinstance(data, OSError):
            out.write("h %.3f %s 0x%x error %s\n" % (t, time.strftime("%H:%M:%S"), base, data))
            continue
        crcs = [zlib.crc32(data[i:i + 4096]) for i in range(0, len(data), 4096)]
        old = prev.get(base)
        changed = [i for i, c in enumerate(crcs) if old is not None and old[i] != c]
        prev[base] = crcs
        out.write("h %.3f %s 0x%x pages %d changed %d %s\n" % (
            t, time.strftime("%H:%M:%S"), base, len(crcs), len(changed), " ".join(map(str, changed[:40]))))
    time.sleep(max(0.0, step - (time.monotonic() - t)))
