#!/usr/bin/env python3
# BC5 exp 0376: decode the CP/GRBM status registers of the 09:48:26 hang (the resident sampler's five samples) against
# healthy frames at the same CP pointers (exp 0375's ASTRO BOT samples) and F490's SE value, field by field, from the
# public register header gc_10_1_0_sh_mask.h (Linux v7.2, github.com/torvalds/linux 8d3ae59288f1e7d58d76558a6ee96d533bc5019f,
# blob 9b7d219e7954f2bab5a69a8d7eecb67d1f0a547b; fetched from git.kernel.org .../plain/...?h=v7.2).
# Prints only register names, values and field names.
# usage: python -I decode0376.py gc_10_1_0_sh_mask.h raw/sampler-event raw/healthy-astro-0375-cp-regs.txt
import re
import sys
from pathlib import Path

REGS = ["GRBM_STATUS", "GRBM_STATUS2", "GRBM_STATUS3", "GRBM_STATUS_SE0", "GRBM_STATUS_SE1", "CP_STAT",
        "CP_STALLED_STAT1", "CP_STALLED_STAT2", "CP_STALLED_STAT3", "CP_BUSY_STAT", "CP_CPF_STATUS",
        "CP_CPF_BUSY_STAT", "CP_CPF_STALLED_STAT1"]


def fields(header, reg):
    """(name, shift, mask) of each field of reg, from the __SHIFT / _MASK defines."""
    sh, mk = {}, {}
    for m in re.finditer(r"^#define %s__(\w+?)__SHIFT\s+(0x[0-9a-fA-F]+)" % reg, header, re.M):
        sh[m.group(1)] = int(m.group(2), 16)
    for m in re.finditer(r"^#define %s__(\w+?)_MASK\s+(0x[0-9a-fA-F]+)L?" % reg, header, re.M):
        mk[m.group(1)] = int(m.group(2), 16)
    return sorted(((n, sh[n], mk[n]) for n in sh if n in mk), key=lambda f: f[1])


def decode(fl, v):
    out = []
    for n, s, m in fl:
        x = (v & m) >> s
        if x:
            out.append(n if m >> s == 1 else "%s=%d" % (n, x))
    return out


def regs_file(p):
    d = {}
    for line in p.read_text().splitlines():
        m = re.match(r"gfx1013\.mm(\w+) => (0x[0-9a-f]+)", line)
        if m:
            d[m.group(1)] = int(m.group(2), 16)
    return d


def main():
    header = Path(sys.argv[1]).read_text()
    hang = [regs_file(p) for p in sorted(Path(sys.argv[2]).glob("regs-*.txt"))]
    healthy = []
    for line in Path(sys.argv[3]).read_text().splitlines():
        d = {k: int(v, 16) for k, v in re.findall(r"(\w+)=(0x[0-9a-f]+)", line)}
        if d.get("CP_PFP_INSTR_PNTR") in (0xea0, 0xea1) and d.get("CP_ME_INSTR_PNTR") == 0x77b:
            healthy.append(d)
    print("hang samples %d; healthy ASTRO BOT samples at PFP 0xea0-0xea1 / ME 0x77b: %d" % (len(hang), len(healthy)))
    for reg in REGS:
        fl = fields(header, reg)
        hv = sorted({h[reg] for h in hang if reg in h})
        ok = sorted({h[reg] for h in healthy if reg in h})
        print("\n== %s (%d fields in the header)" % (reg, len(fl)))
        for v in hv:
            print("  hang    0x%08x: %s" % (v, " ".join(decode(fl, v))))
        for v in ok:
            n = sum(1 for h in healthy if h.get(reg) == v)
            print("  healthy 0x%08x (x%d): %s" % (v, n, " ".join(decode(fl, v))))
        if hv and ok:
            a = set().union(*(decode(fl, v) for v in hv))
            b = set.intersection(*(set(decode(fl, v)) for v in ok))
            print("  only in the hang: %s" % (" ".join(sorted(a - set().union(*(decode(fl, v) for v in ok)))) or "-"))
            print("  in every healthy sample, not in the hang: %s" % (" ".join(sorted(b - a)) or "-"))
    fl = fields(header, "GRBM_STATUS_SE0")
    print("\n== GRBM_STATUS_SE0/SE1 against F490 (0x0a000016) and the healthy 0xee600030")
    for v in (0x0a000036, 0x0a000016, 0xee600030):
        print("  0x%08x: %s" % (v, " ".join(decode(fl, v))))
    print("  0x0a000036 ^ 0x0a000016 = 0x%08x: %s" % (0x20, " ".join(decode(fl, 0x20))))


if __name__ == "__main__":
    main()
