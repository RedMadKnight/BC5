#!/usr/bin/env python3
# BC5 experiment 0235: the night lake water's images in clean and patched frames.
#  dump <pid> <direct.log> <out prefix> [wait s]: before a frozen-view shot, take the water draw's (PS 0x11d01ff900)
#      latest image descriptors from the tail of the live draw journal ("bake ud ps|gs" lines; slots 0, 2, 4 are T#s at
#      user-data dwords 0-7, 8-15, 16-23, exps 0201/0212) and read through /proc/<pid>/mem (read-only, as exps 0200/0205):
#        ps0  the pixel stage's 2048x2048 BC4 texture (streamed; its address moves per run)
#        ps2  the pixel stage's 512x512 16_FLOAT texture (streamed)
#        ps4  the pixel stage's 4x4 image at 0x11d0078000
#        gs4  the vertex stage's slot-4 image at 0x113cb40000 (16_FLOAT at the render resolution, written by the GPU
#             every frame); read at the largest of its descriptor's size and 3328x1872, the largest size the journals
#             showed (exps 0232/0233), so shots at other render sizes still cover the same bytes
#      Surface sizes from exp 0205's res0205.py layout() (Mesa addrlib @ ab2374a; see there). Writes <prefix>.<name>.bin
#      and <prefix>.desc.txt (the descriptors and the journal time of the draw they came from). With no water draw in
#      the journal yet (the journal starts at t = 150 s, about the first shot), it polls for up to [wait] s (default 20).
#  sum <run dir> <bench.txt>: per shot (class from the bench's patch share: clean < 5 %, patched >= 8 %, else mid) and
#      image, summary statistics only: an md5 prefix; for 16_FLOAT the share of zeros, non-finite and negative values
#      and the min / median / max / mean of the finite ones, and the 64-KiB (gs4) or 4-KiB (ps2) blocks holding a single
#      value; for BC4 the share of flat blocks (both endpoints equal) and of all-zero blocks, over the surface and over
#      mip 0; per image across shots the 4-KiB pages that changed from the previous shot and the pages that separate
#      clean from patched (no page content shared between the classes, one class with a single content).
# Runs on the box; the dumps are the title's rendered and texture data and stay there.
# usage: python3 -I img0235.py dump <pid> <direct.log> <out prefix> [wait s]
#        python3 -I img0235.py sum <run dir> <bench.txt>
import collections, glob, hashlib, os, re, struct, sys, time

# gfx10 IMG_FORMAT -> (bytes per element, element width, height): 13 16_FLOAT, 71 16_16_16_16_FLOAT, 175 BC4_UNORM
# (exps 0201/0212), 56 8_8_8_8_UNORM TODO(verify) (a 4x4 one-level image is one 4-KiB block whatever its element size)
FMT = {13: (2, 1, 1), 71: (8, 1, 1), 175: (8, 4, 4), 56: (4, 1, 1)}
GS4_MIN = (3328, 1872)


def layout(width, height, levels, sw, bpe, ew, eh):  # exp 0205 res0205.py, unchanged
    blk = 4096 if 4 <= sw <= 7 or sw == 23 else 65536
    lb = blk.bit_length() - 1
    n = lb - (bpe.bit_length() - 1)
    bw = 1 << ((n + 1) // 2)
    bh = 1 << (n - (n + 1) // 2)
    tw, th = bw >> 1, bh
    maxtail = (1 + (1 << (lb - 9))) if lb <= 11 else lb - 4
    w0, h0 = -(-width // ew), -(-height // eh)  # mip 0 in elements
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
    return {"block": blk, "bw": bw, "bh": bh, "mips": mips, "first_tail": first_tail, "size": off}


def tsharp(d):
    d0, d1, d2, d3 = d[0:4]
    return {"base": (d0 | (d1 & 0xff) << 32) << 8, "fmt": (d1 >> 20) & 0x1ff,
            "w": ((d2 & 0xfff) << 2 | d1 >> 30) + 1, "h": ((d2 >> 14) & 0x3fff) + 1,
            "levels": ((d3 >> 16) & 0xf) - ((d3 >> 12) & 0xf) + 1, "sw": (d3 >> 20) & 0x1f, "type": d3 >> 28}


DRAW = re.compile(r"^draw journal buf (\d+) \(\d+ dwords\) at (\d+):.*\| ps (\S+) ")
UD = re.compile(r"^bake ud (ps|gs) buf (\d+) at (\d+): (.*)$")
T = re.compile(r"\bt (\d+\.\d+)")


def latest_water(path, tail=8 << 20):
    with open(path, "rb") as f:
        f.seek(max(0, os.path.getsize(path) - tail))
        lines = f.read().decode("utf-8", "replace").splitlines()
    t, cur, ud, found = None, None, {}, None
    for line in lines:
        if line.startswith("timing: t ") or line.startswith("frame profile: t "):
            m = T.search(line)
            if m:
                t = float(m[1])
            continue
        m = DRAW.match(line)
        if m:
            cur = (m[1], m[2]) if m[3].lower() == "11d01ff900" else None
            ud = {}
            continue
        m = UD.match(line)
        if m and cur == (m[2], m[3]):
            ud[m[1]] = [int(x, 16) for x in re.findall(r"\b[0-9a-f]{8}\b", m[4])]
            if "ps" in ud and "gs" in ud:
                found = (t, dict(ud))
    return found


def dump(pid, journal, prefix, wait):
    t0 = time.time()
    found = None
    while found is None:
        found = latest_water(journal) if os.path.exists(journal) else None
        if found is None:
            if time.time() - t0 > wait:
                print("%s: no water draw in the journal after %d s" % (prefix, wait))
                return
            time.sleep(1)
    jt, ud = found
    imgs = {"ps0": tsharp(ud["ps"][0:8]), "ps2": tsharp(ud["ps"][8:16]), "ps4": tsharp(ud["ps"][16:24]),
            "gs4": tsharp(ud["gs"][16:24])}
    fd = os.open("/proc/%d/mem" % pid, os.O_RDONLY)
    out = ["# journal t %s, polled %.1f s" % (jt, time.time() - t0)]
    try:
        for name, d in imgs.items():
            if d["fmt"] not in FMT or not (8 <= d["type"] <= 13):
                out.append("%s: base 0x%x fmt %d type %d: not dumped (unknown format)" % (name, d["base"], d["fmt"], d["type"]))
                continue
            bpe, ew, eh = FMT[d["fmt"]]
            w, h = d["w"], d["h"]
            if name == "gs4":
                w, h = max(w, GS4_MIN[0]), max(h, GS4_MIN[1])
            size = layout(w, h, d["levels"], d["sw"], bpe, ew, eh)["size"]
            try:
                data = os.pread(fd, size, d["base"])
                with open("%s.%s.bin" % (prefix, name), "wb") as f:
                    f.write(data)
                note = "read %d bytes" % len(data)
            except OSError as e:
                note = "read failed: %s" % e
            out.append("%s: base 0x%x %dx%d fmt %d levels %d sw %d; extent %dx%d = %d bytes; %s" % (
                name, d["base"], d["w"], d["h"], d["fmt"], d["levels"], d["sw"], w, h, size, note))
    finally:
        os.close(fd)
    with open(prefix + ".desc.txt", "w") as f:
        f.write("\n".join(out) + "\n")


def f16stats(data, blk):
    n = len(data) // 2
    v = struct.unpack("<%de" % n, data[:n * 2])
    raw = struct.unpack("<%dH" % n, data[:n * 2])
    zero = sum(1 for x in raw if x & 0x7fff == 0)
    nonfin = sum(1 for x in raw if x & 0x7c00 == 0x7c00)
    fin = [x for x, r in zip(v, raw) if r & 0x7c00 != 0x7c00]
    neg = sum(1 for x in fin if x < 0)
    s = sorted(fin[::16]) or [0.0]
    flat = sum(1 for i in range(0, len(data) - blk + 1, blk) if data[i:i + blk] == data[i:i + 2] * (blk // 2))
    return "zero %.3f nonfinite %.4f negative %.3f | min %.4g med %.4g max %.4g mean %.4g | single-value %d-KiB blocks %d of %d" % (
        zero / n, nonfin / n, neg / n, min(fin or [0]), s[len(s) // 2], max(fin or [0]), sum(fin) / max(1, len(fin)),
        blk >> 10, flat, len(data) // blk)


def bc4stats(data, mip0):
    def part(b):
        nb = len(b) // 8
        flat = sum(1 for i in range(0, nb * 8, 8) if b[i] == b[i + 1])
        zero = sum(1 for i in range(0, nb * 8, 8) if b[i:i + 8] == bytes(8))
        return "flat %.3f zero %.3f" % (flat / max(1, nb), zero / max(1, nb))
    return "all: %s | mip 0: %s" % (part(data), part(data[mip0[0]:mip0[0] + mip0[1]]))


def summary(rd, bench):
    share = {}
    for l in open(bench):
        m = re.match(r"\s*(\d{6})-(ts\d\d)\.png: patch\s+([\d.]+) %", l)
        if m:
            share[m[2]] = float(m[3])
    cls = {ts: ("clean" if p < 5 else "patched" if p >= 8 else "mid") for ts, p in share.items()}
    pages = collections.defaultdict(dict)  # image -> ts -> list of page hashes
    print("# %s: %d shots (%s)" % (rd, len(cls), ", ".join("%s %d" % kv for kv in sorted(collections.Counter(cls.values()).items()))))
    for ts in sorted(cls):
        desc = os.path.join(rd, "dumps", ts + ".img.desc.txt")
        dl = open(desc).read().splitlines() if os.path.exists(desc) else []
        print("%s %-7s %5.1f %%  %s" % (ts, cls[ts], share[ts], dl[0] if dl else "(no image dump)"))
        for name in ("ps0", "ps2", "ps4", "gs4"):
            p = os.path.join(rd, "dumps", "%s.img.%s.bin" % (ts, name))
            if not os.path.exists(p):
                continue
            data = open(p, "rb").read()
            dline = next((l for l in dl if l.startswith(name + ":")), "")
            m = re.search(r"base 0x([0-9a-f]+) (\d+)x(\d+) fmt (\d+) levels (\d+) sw (\d+)", dline)
            fmt = int(m[4]) if m else 0
            if fmt == 13:
                st = f16stats(data, 65536 if name == "gs4" else 4096)
            elif fmt == 175:
                L = layout(int(m[2]), int(m[3]), int(m[5]), int(m[6]), 8, 4, 4)
                m0 = next(x for x in L["mips"] if x["mip"] == 0)
                st = bc4stats(data, (m0["offset"], m0["size"]))
            else:
                st = "distinct 4-byte values %d" % len(set(struct.unpack("<%dI" % (len(data) // 4), data)))
            size = re.search(r"base 0x([0-9a-f]+) (\d+x\d+)", dline)
            print("   %s %s %s md5 %s | %s" % (name, size[1] if size else "?", size[2] if size else "?",
                                             hashlib.md5(data).hexdigest()[:8], st))
            pages[name][ts] = [hashlib.md5(data[i:i + 4096]).digest() for i in range(0, len(data), 4096)]
    print("# per image across shots: pages changed from the previous shot; pages separating clean from patched")
    for name, byts in pages.items():
        order = sorted(byts)
        ch = []
        for a, b in zip(order, order[1:]):
            n = min(len(byts[a]), len(byts[b]))
            ch.append("%s:%d" % (b, sum(1 for i in range(n) if byts[a][i] != byts[b][i])))
        n = min(len(x) for x in byts.values())
        sep = []
        for i in range(n):
            vc = {byts[ts][i] for ts in order if cls[ts] == "clean"}
            vp = {byts[ts][i] for ts in order if cls[ts] == "patched"}
            if vc and vp and not (vc & vp) and (len(vc) == 1 or len(vp) == 1):
                sep.append(i)
        print("  %s: %d pages; changed %s" % (name, n, " ".join(ch)))
        print("  %s: separating pages %d%s" % (name, len(sep), (": " + " ".join(map(str, sep[:40])) + (" ..." if len(sep) > 40 else "")) if sep else ""))


if __name__ == "__main__":
    if sys.argv[1] == "dump":
        dump(int(sys.argv[2]), sys.argv[3], sys.argv[4], float(sys.argv[5]) if len(sys.argv) > 5 else 20)
    else:
        summary(sys.argv[2], sys.argv[3])
