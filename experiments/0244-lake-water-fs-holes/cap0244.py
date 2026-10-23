#!/usr/bin/env python3
# BC5 experiment 0244: during a frozen view, capture the inputs that code0244.py/match0244.py name for the water's
# full-screen draw (PS 0x11d01d7100), plus the G-buffer target 0x113f230000, read-only through /proc/<pid>/mem (as
# exps 0200/0205/0235). From the latest journalled draw of the program in the live draw journal it takes the address of
# each named table ("bake table ps udK <address>"), reads 4 KiB of it now, checks its first 128 bytes against the
# journalled head (a per-frame table that was reused since shows a mismatch), decodes the descriptor at the named
# offset (T# or V#, as match0244.py) and reads the resource: an image over its full extent (res0205.py's layout()),
# a buffer over records x stride (capped at 32 MiB). Writes <prefix>.<name>.bin and <prefix>.desc.txt; the title's
# data stays on the box (~/bc5-data/priv).
# usage: python3 -I cap0244.py <pid> <direct.log> <out prefix> <udK+0xOFF:image|buffer> [...]
import os, re, struct, sys, time

# gfx10 IMG_FORMAT -> (bytes per element, element width, height), the formats checked against Mesa's GFX10_FORMAT
# (src/amd/registers/gfx10-rsrc.json @ 0866ae7): 13 16_FLOAT, 22 32_FLOAT, 29 16_16_FLOAT, 56 8_8_8_8_UNORM,
# 71 16_16_16_16_FLOAT, 175 BC4_UNORM; other formats are recorded, not read
FMT = {13: (2, 1, 1), 22: (4, 1, 1), 29: (4, 1, 1), 56: (4, 1, 1), 71: (8, 1, 1), 175: (8, 4, 4)}
PROG = "11d01d7100"
GBUF = (0x113f230000, 3328, 1872, 22, 27)


def layout(width, height, levels, sw, bpe, ew, eh):  # exp 0205 res0205.py, unchanged
    blk = 4096 if 4 <= sw <= 7 or sw == 23 else 65536
    lb = blk.bit_length() - 1
    n = lb - (bpe.bit_length() - 1)
    bw = 1 << ((n + 1) // 2)
    bh = 1 << (n - (n + 1) // 2)
    tw, th = bw >> 1, bh
    maxtail = (1 + (1 << (lb - 9))) if lb <= 11 else lb - 4
    w0, h0 = -(-width // ew), -(-height // eh)
    mips, first_tail = [], levels
    for i in range(levels):
        w, h = max(1, w0 >> i), max(1, h0 >> i)
        if w <= tw and h <= th and levels - i <= maxtail:
            first_tail = i
            break
        p, q = -(-w // bw) * bw, -(-h // bh) * bh
        mips.append({"mip": i, "w": w, "h": h, "pitch": p, "height": q, "size": p * q * bpe})
    off = blk if first_tail < levels else 0
    for m in reversed(mips):
        m["offset"] = off
        off += m["size"]
    return {"block": blk, "size": off}


def latest(path, tail=8 << 20):
    with open(path, "rb") as f:
        f.seek(max(0, os.path.getsize(path) - tail))
        lines = f.read().decode("utf-8", "replace").splitlines()
    found, cur = None, None
    for line in lines:
        m = re.match(r"^draw journal buf (\d+) \(\d+ dwords\) at (\d+):.*\| ps (\S+) ", line)
        if m:
            cur = {"tabs": {}} if m[3].lower() == PROG else None
            if cur is not None:
                found = cur
            continue
        m = re.match(r"^bake table ps ud(\d+) ([0-9a-f]+): (.*)$", line)
        if m and cur is not None:
            cur["tabs"][int(m[1])] = (int(m[2], 16), [int(x, 16) for x in re.findall(r"\b[0-9a-f]{8}\b", m[3])])
    return found


def main():
    pid, log, prefix = int(sys.argv[1]), sys.argv[2], sys.argv[3]
    targets = [a.split(":") for a in sys.argv[4:]]
    t0 = time.time()
    d = None
    while d is None and time.time() - t0 < 20:
        d = latest(log) if os.path.exists(log) else None
        if d is None:
            time.sleep(1)
    fd = os.open("/proc/%d/mem" % pid, os.O_RDONLY)
    out = ["# capture at %s" % time.strftime("%H:%M:%S")]

    def save(name, addr, size):
        try:
            data = os.pread(fd, size, addr)
            open("%s.%s.bin" % (prefix, name), "wb").write(data)
            return "read %d bytes" % len(data)
        except OSError as e:
            return "read failed: %s" % e

    try:
        for tg, kind in targets:
            k, off = re.match(r"ud(\d+)\+0x([0-9a-f]+)", tg).groups()
            k, off = int(k), int(off, 16)
            name = "%s_%x" % ("ud%d" % k, off)
            if d is None or k not in d["tabs"]:
                out.append("%s: no journalled table" % tg)
                continue
            addr, head = d["tabs"][k]
            try:
                tab = os.pread(fd, 4096, addr)
            except OSError as e:
                out.append("%s: table 0x%x read failed: %s" % (tg, addr, e))
                continue
            now = list(struct.unpack_from("<%dI" % len(head), tab))
            same = "head matches the journal" if now == head else "head differs from the journal (%d of %d dwords)" % (
                sum(1 for a, b in zip(now, head) if a != b), len(head))
            dw = struct.unpack_from("<8I", tab, off)
            if kind == "image":
                base = (dw[0] | (dw[1] & 0xff) << 32) << 8
                w, h = ((dw[2] & 0xfff) << 2 | dw[1] >> 30) + 1, ((dw[2] >> 14) & 0x3fff) + 1
                fmt, sw = (dw[1] >> 20) & 0x1ff, (dw[3] >> 20) & 0x1f
                lv = ((dw[3] >> 16) & 0xf) - ((dw[3] >> 12) & 0xf) + 1
                desc = "T# base 0x%x %dx%d fmt %d levels %d sw %d type %d" % (base, w, h, fmt, lv, sw, dw[3] >> 28)
                if fmt in FMT and 8 <= dw[3] >> 28 <= 13:
                    size = min(layout(w, h, lv, sw, *FMT[fmt])["size"], 64 << 20)
                    note = save(name, base, size)
                else:
                    note = "not read (format %d, type %d)" % (fmt, dw[3] >> 28)
            else:
                base = dw[0] | (dw[1] & 0xffff) << 32
                stride, rec = (dw[1] >> 16) & 0x3fff, dw[2]
                desc = "V# base 0x%x stride %d records %d" % (base, stride, rec)
                note = save(name, base, min(max(stride, 1) * rec, 32 << 20))
            out.append("%s: table 0x%x (%s): %s; %s" % (tg, addr, same, desc, note))
        b, w, h, fmt, sw = GBUF
        out.append("gbuffer: T# base 0x%x %dx%d fmt %d levels 1 sw %d; %s" % (
            b, w, h, fmt, sw, save("gbuffer", b, layout(w, h, 1, sw, 4, 1, 1)["size"])))
    finally:
        os.close(fd)
    open(prefix + ".desc.txt", "w").write("\n".join(out) + "\n")
    print("\n".join(out))


main()
