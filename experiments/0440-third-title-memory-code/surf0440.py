#!/usr/bin/env python3
"""Experiment 0440: does a dumped display surface hold a picture? Statistics only (private input, no image written).

  surf0440.py surface <file> [bytes]      zero share, share of the most common 32-bit value, number of distinct
                                          32-bit values in a sample, and a 16-step profile along the buffer (share
                                          of non-zero bytes per sixteenth), over the first <bytes> (default all)
  surf0440.py dcc <file> [offset] [bytes] histogram of the DCC key bytes: 0x00 = clear to zero, 0xff = uncompressed
                                          (Mesa 0866ae7085c1 src/amd/common/ac_descriptors.h:29-30), others = compressed

The surface is read as stored (tiled, possibly DCC-compressed): the numbers say whether content is there, not what
it shows. Works on any host (plain reads), also on a sparse dump file.
"""
import sys


def surface(path, limit):
    data = open(path, "rb").read() if limit is None else open(path, "rb").read(limit)
    n = len(data)
    zero = data.count(0)
    print("%d bytes; zero bytes %.2f %%" % (n, 100.0 * zero / max(n, 1)))
    step = max(4, (n // 4 // 200000) * 4)
    vals = {}
    for i in range(0, n - 3, step):
        v = data[i:i + 4]
        vals[v] = vals.get(v, 0) + 1
    top = sorted(vals.items(), key=lambda x: -x[1])[:5]
    tot = sum(vals.values())
    print("sample of %d 32-bit values: %d distinct; most common: %s" % (
        tot, len(vals), ", ".join("%s %.1f %%" % (v[::-1].hex(), 100.0 * c / tot) for v, c in top)))
    part = n // 16
    prof = []
    for k in range(16):
        seg = data[k * part:(k + 1) * part]
        prof.append("%3.0f" % (100.0 * (len(seg) - seg.count(0)) / max(len(seg), 1)))
    print("non-zero bytes per sixteenth of the buffer, %: " + " ".join(prof))


def dcc(path, off, limit):
    with open(path, "rb") as f:
        f.seek(off)
        data = f.read() if limit is None else f.read(limit)
    hist = {}
    for b in set(data):
        hist[b] = data.count(b)
    top = sorted(hist.items(), key=lambda x: -x[1])[:8]
    print("%d key bytes from offset %#x: %s" % (len(data), off, ", ".join("0x%02x x%d (%.1f %%)" % (k, c, 100.0 * c / max(len(data), 1)) for k, c in top)))


def main():
    cmd, path = sys.argv[1], sys.argv[2]
    if cmd == "surface":
        surface(path, int(sys.argv[3], 0) if len(sys.argv) > 3 else None)
    else:
        dcc(path, int(sys.argv[3], 0) if len(sys.argv) > 3 else 0, int(sys.argv[4], 0) if len(sys.argv) > 4 else None)


if __name__ == "__main__":
    main()
