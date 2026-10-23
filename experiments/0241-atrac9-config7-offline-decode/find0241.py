#!/usr/bin/env python3
# BC5 experiment 0241: list the title's Wwise ATRAC9 streams (codec 0xFFFC) in its mounted package and copy each
# stream's raw ATRAC9 data out to a private directory, for an offline decode. The copies never leave the box and are
# never committed. Usage (read-only on the mount):
#   python3 -I find0241.py <mounted package root> <private output dir> [relative file ...] > index.tsv
# With file names given, only those are scanned (the title keeps its Wwise data in extension-less archives such as
# d/0/wem_0 and d/0/soundbank); without, every file with an audio-like extension.
# Wwise's fmt layout for ATRAC9 (0x24 bytes, extra 0x12: config at +0x18, sample count at +0x1c, encoder delay at
# +0x20) is from vgmstream src/meta/wwise.c (ATRAC9 case); the scan also accepts any fmt whose bytes hold a 0xFE
# config word, and reports where it found it.
import mmap, os, struct, sys

root, out, only = sys.argv[1], sys.argv[2], sys.argv[3:]
os.makedirs(out, mode=0o700, exist_ok=True)
EXT = (".pck", ".bnk", ".wem", ".wsp", ".bin")
print("file\toffset\triff_size\tcodec\tchannels\trate\tconfig\tcfg_at\tsamples\tdelay\tdata_size\tcopy")
n = 0
targets = [os.path.join(root, r) for r in only] if only else [
    os.path.join(dp, fn) for dp, _, fs in os.walk(root) for fn in sorted(fs) if fn.lower().endswith(EXT)]
for p in targets:
        fn = os.path.basename(p)
        size = os.path.getsize(p)
        if size < 64:
            continue
        with open(p, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
            pos = 0
            while True:
                pos = m.find(b"RIFF", pos)
                if pos < 0 or pos + 12 > size:
                    break
                riff = struct.unpack_from("<I", m, pos + 4)[0]
                if m[pos + 8:pos + 12] != b"WAVE" or riff < 16 or pos + 8 + riff > size:
                    pos += 4
                    continue
                # walk the chunks
                q, end = pos + 12, pos + 8 + riff
                fmt = data = None
                while q + 8 <= end:
                    cid, csz = m[q:q + 4], struct.unpack_from("<I", m, q + 4)[0]
                    if cid == b"fmt ":
                        fmt = (q + 8, csz)
                    elif cid == b"data":
                        data = (q + 8, csz)
                    q += 8 + csz + (csz & 1)
                if fmt and data:
                    fo, fsz = fmt
                    codec, ch, rate = struct.unpack_from("<HHI", m, fo)
                    cfg_at = -1
                    if codec == 0xFFFC and fsz >= 0x24 and m[fo + 0x18] == 0xFE:
                        cfg_at = 0x18
                    elif codec == 0xFFFC:
                        k = m.find(b"\xfe", fo, fo + fsz)
                        cfg_at = k - fo if k >= 0 else -1
                    if codec == 0xFFFC:
                        cfg = m[fo + cfg_at:fo + cfg_at + 4].hex() if cfg_at >= 0 else "-"
                        samples = struct.unpack_from("<i", m, fo + 0x1c)[0] if fsz >= 0x20 else -1
                        delay = struct.unpack_from("<i", m, fo + 0x20)[0] if fsz >= 0x24 else -1
                        name = f"{n:04d}_{fn}_{pos:x}.at9raw"
                        with open(os.path.join(out, name), "wb") as w:
                            w.write(m[data[0]:data[0] + data[1]])
                        os.chmod(os.path.join(out, name), 0o600)
                        rel = os.path.relpath(p, root)
                        print(f"{rel}\t{pos:#x}\t{riff}\t{codec:#06x}\t{ch}\t{rate}\t{cfg}\t{cfg_at:#x}\t{samples}\t{delay}\t{data[1]}\t{name}")
                        n += 1
                pos = pos + 8 + riff
print(f"# {n} ATRAC9 streams", file=sys.stderr)
