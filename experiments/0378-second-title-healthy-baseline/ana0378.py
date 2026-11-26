#!/usr/bin/env python3
# BC5 exp 0378: the second title's healthy forced register samples (stall sampler 0377, RT on, S6N route) against the
# F403 class: the 09:48:26 sampler event (exp 0376 raw/sampler-event, 5 samples) and the class's devcoredumps
# (exp 0376 raw/class-dumps-cp-regs.txt, 7). Fields are decoded from the public header gc_10_1_0_sh_mask.h (Linux
# v7.2, blob 9b7d219e7954f2bab5a69a8d7eecb67d1f0a547b, as decode0376.py). Prints register names, values, field names
# and the decoded compute dispatch (program address, grid) only.
# usage: python -I ana0378.py <dir>/gc_10_1_0_sh_mask.h raw/B1-samples ../0376-f403-first-live-capture/raw
import re
import sys
from pathlib import Path

STATUS = ["GRBM_STATUS", "GRBM_STATUS2", "GRBM_STATUS3", "GRBM_STATUS_SE0", "GRBM_STATUS_SE1", "CP_STAT",
          "CP_STALLED_STAT1", "CP_STALLED_STAT2", "CP_STALLED_STAT3", "CP_BUSY_STAT", "CP_CPF_STATUS",
          "CP_CPF_BUSY_STAT", "CP_CPF_STALLED_STAT1"]


def fields(header, reg):
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
        m = re.match(r"#\s+program address = .* = (0x[0-9a-f]+)", line)
        if m:
            d["program"] = int(m.group(1), 16)
    return d


def parked(d):
    return d.get("CP_PFP_INSTR_PNTR") in (0xea0, 0xea1) and d.get("CP_ME_INSTR_PNTR") in (0x779, 0x77a, 0x77b)


def bit(header_fields, reg, name):
    for n, s, m in header_fields[reg]:
        if n == name:
            return m
    raise KeyError("%s.%s" % (reg, name))


def main():
    header = Path(sys.argv[1]).read_text()
    hf = {r: fields(header, r) for r in STATUS}
    healthy = []
    for p in sorted(Path(sys.argv[2]).glob("forced-*/regs-*.txt")):
        d = regs_file(p)
        d["name"] = p.parent.name
        healthy.append(d)
    r76 = Path(sys.argv[3])
    hang = [regs_file(p) for p in sorted((r76 / "sampler-event").glob("regs-*.txt"))]
    dumps = []
    for line in (r76 / "class-dumps-cp-regs.txt").read_text().splitlines():
        kv = re.findall(r"(\w+)=(0x[0-9a-f]+)", line)
        if kv:
            d = {}
            for k, v in kv:  # the dump lists GRBM_STATUS2 again later (0x0 there); keep the first, F525's value
                d.setdefault(k, int(v, 16))
            d["name"] = line.split()[0]
            dumps.append(d)

    pk = [d for d in healthy if parked(d)]
    print("healthy forced samples %d; parked at PFP 0xea0-0xea1 / ME 0x779-0x77b: %d; hang samples %d; class dumps %d"
          % (len(healthy), len(pk), len(hang), len(dumps)))

    print("\n== every healthy sample")
    print("dir PFP ME GRBM GRBM2 SE0 SE1 STALL1 STALL2 STALL3 BUSY CP_STAT | program dim threads initiator | GFX_CNTL")
    for d in healthy:
        print("%s %#x %#x %08x %08x %08x %08x %05x %05x %05x %08x %08x | %#x [%d %d %d] [%d %d %d] %#x | %x/%x%s" % (
            d["name"][7:], d.get("CP_PFP_INSTR_PNTR", -1), d.get("CP_ME_INSTR_PNTR", -1), d.get("GRBM_STATUS", 0),
            d.get("GRBM_STATUS2", 0), d.get("GRBM_STATUS_SE0", 0), d.get("GRBM_STATUS_SE1", 0),
            d.get("CP_STALLED_STAT1", 0), d.get("CP_STALLED_STAT2", 0), d.get("CP_STALLED_STAT3", 0),
            d.get("CP_BUSY_STAT", 0), d.get("CP_STAT", 0), d.get("program", 0), d.get("COMPUTE_DIM_X", 0),
            d.get("COMPUTE_DIM_Y", 0), d.get("COMPUTE_DIM_Z", 0), d.get("COMPUTE_NUM_THREAD_X", 0),
            d.get("COMPUTE_NUM_THREAD_Y", 0), d.get("COMPUTE_NUM_THREAD_Z", 0),
            d.get("COMPUTE_DISPATCH_INITIATOR", 0), d.get("GRBM_GFX_CNTL[0]", 0), d.get("GRBM_GFX_CNTL[1]", 0),
            "  PARKED" if parked(d) else ""))

    print("\n== pointer pairs")
    pairs = {}
    for d in healthy:
        k = (d.get("CP_PFP_INSTR_PNTR"), d.get("CP_ME_INSTR_PNTR"))
        pairs[k] = pairs.get(k, 0) + 1
    for (p, m), n in sorted(pairs.items(), key=lambda x: -x[1]):
        print("  PFP %#x ME %#x: %d" % (p, m, n))

    for reg in STATUS:
        fl = hf[reg]
        hv = sorted({h[reg] for h in hang if reg in h})
        ok = sorted({h[reg] for h in pk if reg in h})
        print("\n== %s" % reg)
        for v in hv:
            print("  hang    0x%08x: %s" % (v, " ".join(decode(fl, v))))
        for v in ok:
            n = sum(1 for h in pk if h.get(reg) == v)
            print("  parked  0x%08x (x%d): %s" % (v, n, " ".join(decode(fl, v))))
        if hv and ok:
            a = set().union(*(decode(fl, v) for v in hv))
            b = set.intersection(*(set(decode(fl, v)) for v in ok))
            print("  only in the hang: %s" % (" ".join(sorted(a - set().union(*(decode(fl, v) for v in ok)))) or "-"))
            print("  in every parked sample, not in the hang: %s" % (" ".join(sorted(b - a)) or "-"))

    print("\n== compute dispatch registers (gfx_0.0.0), healthy samples")
    progs = {}
    for d in healthy:
        k = (d.get("program", 0), d.get("COMPUTE_DIM_X", 0), d.get("COMPUTE_DIM_Y", 0), d.get("COMPUTE_DIM_Z", 0),
             d.get("COMPUTE_NUM_THREAD_X", 0), d.get("COMPUTE_NUM_THREAD_Y", 0), d.get("COMPUTE_NUM_THREAD_Z", 0),
             d.get("COMPUTE_DISPATCH_INITIATOR", 0))
        progs.setdefault(k, []).append(d)
    for k, ds in sorted(progs.items(), key=lambda x: -len(x[1])):
        print("  program %#x dim [%d %d %d] threads [%d %d %d] initiator %#x: %d samples (%d parked)" % (
            k + (len(ds), sum(1 for d in ds if parked(d)))))

    # candidate single-sample rules: True = "looks like the F403 hang"
    R = {
        "A: GRBM2 EA_BUSY clear": lambda d: not d["GRBM_STATUS2"] & bit(hf, "GRBM_STATUS2", "EA_BUSY"),
        "B: BUSY_STAT EOP_DONE_BUSY clear": lambda d: not d["CP_BUSY_STAT"] & bit(hf, "CP_BUSY_STAT", "EOP_DONE_BUSY"),
        "C: STALLED2 ME_WAITING_ON_PARTIAL_FLUSH set": lambda d: bool(d["CP_STALLED_STAT2"] & bit(hf, "CP_STALLED_STAT2", "ME_WAITING_ON_PARTIAL_FLUSH")),
        "D: GRBM CB_CLEAN and DB_CLEAN, GE_BUSY clear": lambda d: bool(d["GRBM_STATUS"] & bit(hf, "GRBM_STATUS", "CB_CLEAN")) and bool(d["GRBM_STATUS"] & bit(hf, "GRBM_STATUS", "DB_CLEAN")) and not d["GRBM_STATUS"] & bit(hf, "GRBM_STATUS", "GE_BUSY"),
        "C and A and B": lambda d: R["C: STALLED2 ME_WAITING_ON_PARTIAL_FLUSH set"](d) and R["A: GRBM2 EA_BUSY clear"](d) and R["B: BUSY_STAT EOP_DONE_BUSY clear"](d),
        "C and A and B and D": lambda d: R["C and A and B"](d) and R["D: GRBM CB_CLEAN and DB_CLEAN, GE_BUSY clear"](d),
        "E: GRBM2 EA_LINK_BUSY clear": lambda d: not d["GRBM_STATUS2"] & bit(hf, "GRBM_STATUS2", "EA_LINK_BUSY"),
        "C and E": lambda d: R["C: STALLED2 ME_WAITING_ON_PARTIAL_FLUSH set"](d) and R["E: GRBM2 EA_LINK_BUSY clear"](d),
        "C and A and B and D and E": lambda d: R["C and A and B and D"](d) and R["E: GRBM2 EA_LINK_BUSY clear"](d),
    }
    print("\n== candidate single-sample rules (fires = looks like the hang)")
    print("  rule | healthy all | healthy parked | hang samples | class dumps")
    for name, f in R.items():
        def cnt(ds):
            ok = [d for d in ds if all(k in d for k in ("GRBM_STATUS", "GRBM_STATUS2", "CP_BUSY_STAT", "CP_STALLED_STAT2"))]
            return "%d/%d" % (sum(1 for d in ok if f(d)), len(ok))
        print("  %s | %s | %s | %s | %s" % (name, cnt(healthy), cnt(pk), cnt(hang), cnt(dumps)))
        miss = [d["name"] for d in dumps if all(k in d for k in ("GRBM_STATUS", "GRBM_STATUS2", "CP_BUSY_STAT", "CP_STALLED_STAT2")) and not f(d)]
        if miss:
            print("    class dumps it misses: %s" % " ".join(miss))


if __name__ == "__main__":
    main()
