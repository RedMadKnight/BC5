#!/usr/bin/env python3
"""BC5 experiment 0399: does anything the water's draws were given point into the table of /dev/gc request 0x80888123 (F787)?
Reads one <zpass.dat.inputs> from exp 0392 or 0397, read-only, on the box, and walks its entries (lake_probe::inputs_of's layout). For each
part of an entry (user data of HS, GS, PS, and the constants behind their dwords 28-29) it looks for an address inside a table range, as a
plain 64-bit pair of dwords, as a shifted (>> 8) value, or as a V#'s base (dword 0 low, dword 1 bits 0-15 high).
Prints the range, the part and the dword, and how many entries had it. Addresses are the only values printed.
Absence shows little: exp 0392 did not record SPI_SHADER_USER_DATA_ADDR, and a ring's descriptor can sit behind that pointer (docs/ports/related-projects-review.md section 7).
usage: rings0399.py <zpass.dat.inputs>"""
import struct
import sys

MAGIC, REGS, PROGRAMS, USER_DATA = 0x57415452, 11, 4, 32
RANGES = (("0xf00000000+0x2400", 0xf00000000, 0x2400), ("0xf00004000+0x4000", 0xf00004000, 0x4000), ("0xf00144000+0x1000000", 0xf00144000, 0x1000000),
          ("0xc80008000+0x3bb00", 0xc80008000, 0x3bb00), ("0xf00008000+0xfc000", 0xf00008000, 0xfc000), ("0xc80043d00+0xd00", 0xc80043d00, 0xd00))


def parts(w):
    """{name: dwords} of one entry; None if it doesn't parse."""
    if len(w) < 3 or w[0] != MAGIC or w[1] != len(w):
        return None
    at = 3 + w[2] + REGS + PROGRAMS
    out = {}
    for s in ("hs", "gs", "ps"):
        out["ud_" + s] = w[at:at + USER_DATA]
        at += USER_DATA
    for s in ("hs", "gs", "ps"):
        if at >= len(w):
            return None
        n = w[at]
        out["c_" + s] = w[at + 1:at + 1 + n]
        at += 1 + n
    return out if at == len(w) else None


def hit(addr):
    for name, base, size in RANGES:
        if base <= addr < base + size:
            return name
    return None


def scan(words):
    """[(range, form, dword)] in one part."""
    found = []
    for k in range(len(words)):
        lo = words[k]
        hi = words[k + 1] if k + 1 < len(words) else 0
        for form, addr in (("pair", lo | ((hi & 0xffff) << 32)), ("shifted", lo << 8)):
            name = hit(addr)
            if name:
                found.append((name, form, k))
    return found


def run(raw):
    counts, entries, at, bad = {}, 0, 0, 0
    while at + 8 <= len(raw):
        magic, n = struct.unpack_from("<II", raw, at)
        if magic != MAGIC or n < 3 or at + n * 4 > len(raw):
            bad += 1
            break
        p = parts(list(struct.unpack_from(f"<{n}I", raw, at)))
        at += n * 4
        if p is None:
            bad += 1
            continue
        entries += 1
        for part, words in p.items():
            for name, form, k in scan(words):
                key = (name, part, form, k)
                counts[key] = counts.get(key, 0) + 1
    out = [f"# {entries} entries, {bad} unreadable"]
    for (name, part, form, k), c in sorted(counts.items(), key=lambda x: (x[0][0], -x[1])):
        out.append(f"{name}: {part} dword {k} as {form}: {c} entries")
    if not counts:
        out.append("# no entry points into any range")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--selftest":
        w = [0] * 4 + [0] * (REGS + PROGRAMS) + [0] * USER_DATA * 3 + [0, 0, 0]
        w[0], w[2] = MAGIC, 1
        w[1] = len(w)
        at = 4 + REGS + PROGRAMS
        w[at + 6], w[at + 7] = 0x00150000, 0xf | (16 << 16)   # a V# into the 16 MiB, stride 16, in HS user data
        w[at + USER_DATA + 2] = 0x0f001450                    # a shifted address in GS user data
        got = run(struct.pack(f"<{len(w)}I", *w))
        assert "0xf00144000+0x1000000: ud_hs dword 6 as pair: 1 entries" in got, got
        assert "0xf00144000+0x1000000: ud_gs dword 2 as shifted: 1 entries" in got, got
        assert run(struct.pack("<3I", MAGIC, 3, 0)).count("unreadable") == 1
        print("selftest ok")
        sys.exit(0)
    with open(sys.argv[1], "rb") as f:
        sys.stdout.write(run(f.read()))
