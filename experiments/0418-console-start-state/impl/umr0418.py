"""BC5 exp 0418 section 3: read the two umr register reads (idle.txt, play.txt) against what section 2 inferred.

The reads are the maintainer's own (`umr -r "*.gfx1013.^mm<NAME>$"`, one per register, the commands of ../README.md
section 3). umr prints "gfx1013.mm<NAME> => 0x<value>"; GRBM_GFX_CNTL is read first and last as the bank witness.
This prints one table: each register at idle and in play, the expectation and the verdict.

usage: python -I umr0418.py <idle.txt> <play.txt>
"""
import re
import sys

LINE = re.compile(r"\bmm([A-Z0-9_]+)\s*=>\s*(0x[0-9a-fA-F]+|ERROR)")

# name: (expected in play, what it settles)
EXPECT = {
    "CP_COHER_START_DELAY": (0x20, "section 2: the reset value; Mesa and PAL write 0x20"),
    "SPI_SHADER_REQ_CTRL_PS": (0x7, "section 2: Mesa clients on the shared ring write 0x7 (reset 0)"),
    "GE_MIN_VTX_INDX": (0x0, "section 2: 0"),
    "GE_MAX_VTX_INDX": (0xFFFFFFFF, "section 2: ~0 from Mesa clients (reset 0)"),
    "VGT_INSTANCE_BASE_ID": (0x0, "section 2: 0"),
    "VGT_ESGS_RING_SIZE_UMD": (0x0, "no GS ring asked (exp 0189's trace)"),
    "VGT_GSVS_RING_SIZE_UMD": (0x0, "no GS ring asked"),
}
# _UMD copy -> the register the kernel's CAM maps it to (gfx_v10_0.c:7296-7475)
UMD = {
    "VGT_TF_RING_SIZE_UMD": "VGT_TF_RING_SIZE",
    "VGT_HS_OFFCHIP_PARAM_UMD": "VGT_HS_OFFCHIP_PARAM",
    "VGT_TF_MEMORY_BASE_UMD": "VGT_TF_MEMORY_BASE",
    "VGT_TF_MEMORY_BASE_HI_UMD": "VGT_TF_MEMORY_BASE_HI",
    "VGT_ESGS_RING_SIZE_UMD": "VGT_ESGS_RING_SIZE",
    "VGT_GSVS_RING_SIZE_UMD": "VGT_GSVS_RING_SIZE",
}


def read(path):
    order, vals, errors = [], {}, []
    with open(path, "rb") as f:
        for raw in f:
            text = raw.decode("utf-8", "replace").strip()
            m = LINE.search(text)
            if not m:
                if text:
                    errors.append(text)
                continue
            name, v = m.group(1), m.group(2)
            val = None if v == "ERROR" else int(v, 16)
            order.append((name, val))
            vals.setdefault(name, []).append(val)
    return order, vals, errors


def fmt(v):
    return "-" if v is None else f"0x{v:08x}"


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    io, iv, ierr = read(sys.argv[1])
    po, pv, perr = read(sys.argv[2])
    for label, order, errs in (("idle", io, ierr), ("play", po, perr)):
        w = [v for n, v in order if n == "GRBM_GFX_CNTL"]
        first, last = (w[0], w[-1]) if w else (None, None)
        print(f"{label}: {len(order)} values, {len(errs)} other lines; GRBM_GFX_CNTL first {fmt(first)} last {fmt(last)}"
              + ("" if first == 0 and last == 0 else "  <- NOT 0: a kernel select may have overlapped"))
        for e in errs[:6]:
            print(f"  other: {e[:160]}")
    names = []
    for n, _ in io + po:
        if n not in names and n != "GRBM_GFX_CNTL":
            names.append(n)
    print()
    print(f"{'register':30} {'idle':>10} {'play':>10}  verdict")
    for n in names:
        i = iv.get(n, [None])[-1]
        p = pv.get(n, [None])[-1]
        verdict = ""
        if n in EXPECT:
            want, why = EXPECT[n]
            got = p if n in pv else i
            verdict = ("as inferred" if got == want else f"NOT as inferred (expected {fmt(want)})") + f": {why}"
        if n in UMD:
            r = UMD[n]
            for label, vals in (("idle", iv), ("play", pv)):
                if n in vals and r in vals:
                    same = vals[n][-1] == vals[r][-1]
                    verdict += f"{'; ' if verdict else ''}{label}: _UMD {'=' if same else '!='} {r}"
        print(f"{n:30} {fmt(i):>10} {fmt(p):>10}  {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
