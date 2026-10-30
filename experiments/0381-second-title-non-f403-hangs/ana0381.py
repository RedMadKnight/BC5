#!/usr/bin/env python3
# BC5 exp 0381: the second title's non-F403 hangs against exp 0378's 40 healthy forced samples and the F403 class.
# Fields are decoded from the public header gc_10_1_0_sh_mask.h (Linux v7.2, blob 9b7d219e, as ana0378.py).
# The hang values are copied from the committed extracts (exp 0380 raw/hang-1808/extract.txt and raw/wbplay/extract.txt,
# exp 0376 raw/sampler-event, exp 0374 raw/decode.txt); nothing private is read.
# usage: python -I ana0381.py <dir>/gc_10_1_0_sh_mask.h ../0378-second-title-healthy-baseline/raw/B1-samples \
#            ../0376-f403-first-live-capture/raw
import importlib.util
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ana0378", here.parent / "0378-second-title-healthy-baseline" / "ana0378.py")
a78 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a78)

# devcoredump / sampler values (gfx_0.0.0)
EVENTS = {
    "1808 graphics stall (devcd 20261029-180813-devcd3)": dict(
        GRBM_STATUS=0xa2712028, GRBM_STATUS2=0x50000008, GRBM_STATUS3=0x00002000, GRBM_STATUS_SE0=0x0d000004,
        GRBM_STATUS_SE1=0x0d000004, CP_STALLED_STAT1=0x00000c00, CP_STALLED_STAT2=0x00218000,
        CP_BUSY_STAT=0x00448400, CP_STAT=0x94078600),
    "T1 0634 ASTRO BOT graphics stop (F519)": dict(
        GRBM_STATUS=0xe5f100ac, GRBM_STATUS2=0x50000008, GRBM_STATUS3=0x00002000, GRBM_STATUS_SE0=0x08000000,
        GRBM_STATUS_SE1=0xec400000, CP_STALLED_STAT1=0x01000c00, CP_STALLED_STAT2=0x00031000,
        CP_BUSY_STAT=0x00428100, CP_STAT=0x94839600),
    "1625 start 1, sample at 16:25:41 (TCP fault class)": dict(GRBM_STATUS=0xa04030ac),
    "1625 start 1, sample at 16:25:43 (after the first reset)": dict(GRBM_STATUS=0xa0003028),
}


def main():
    header = Path(sys.argv[1]).read_text()
    regs = a78.STATUS
    hf = {r: a78.fields(header, r) for r in regs}
    healthy = []
    for p in sorted(Path(sys.argv[2]).glob("forced-*/regs-*.txt")):
        d = a78.regs_file(p)
        d["name"] = p.parent.name
        healthy.append(d)
    r76 = Path(sys.argv[3])
    f403 = a78.regs_file(sorted((r76 / "sampler-event").glob("regs-*.txt"))[0])
    events = dict(EVENTS)
    events["F403 0948 sampler sample 1 (F525)"] = {k: f403[k] for k in regs if k in f403}

    def b(reg, name):
        return a78.bit(hf, reg, name)

    print("== decoded states")
    for name, ev in events.items():
        print("\n# " + name)
        for reg in regs:
            if reg in ev:
                print("  %-18s 0x%08x  %s" % (reg, ev[reg], " ".join(a78.decode(hf[reg], ev[reg]))))

    # which GRBM_STATUS fields of 18:08 ever occur in a healthy sample, and together
    ev = events["1808 graphics stall (devcd 20261029-180813-devcd3)"]
    print("\n== 18:08 against the 40 healthy samples, field by field")
    for reg in ("GRBM_STATUS", "GRBM_STATUS2", "GRBM_STATUS_SE0", "GRBM_STATUS_SE1", "CP_STALLED_STAT2", "CP_BUSY_STAT"):
        on = set(a78.decode(hf[reg], ev[reg]))
        hs = [set(a78.decode(hf[reg], d[reg])) for d in healthy if reg in d]
        exact = sum(1 for d in healthy if d.get(reg) == ev[reg])
        print("  %s 0x%08x: exactly equal in %d/%d healthy" % (reg, ev[reg], exact, len(hs)))
        for f in sorted(on):
            print("    %-34s set in %2d/%d healthy" % (f, sum(1 for h in hs if f in h), len(hs)))
        for f in sorted(set().union(*hs) - on):
            n = sum(1 for h in hs if f in h)
            if n >= 20:
                print("    %-34s CLEAR here, set in %2d/%d healthy" % (f, n, len(hs)))

    print("\n== nearest healthy samples to 18:08 (number of differing status bits over the six registers)")
    keys = ("GRBM_STATUS", "GRBM_STATUS2", "GRBM_STATUS_SE0", "GRBM_STATUS_SE1", "CP_STALLED_STAT2", "CP_BUSY_STAT")
    dist = sorted((sum(bin(d[k] ^ ev[k]).count("1") for k in keys), d["name"]) for d in healthy if all(k in d for k in keys))
    for n, nm in dist[:5]:
        d = next(x for x in healthy if x["name"] == nm)
        diff = []
        for k in keys:
            x = d[k] ^ ev[k]
            if x:
                diff.append("%s:+[%s] -[%s]" % (k, " ".join(a78.decode(hf[k], ev[k] & x)), " ".join(a78.decode(hf[k], d[k] & x))))
        print("  %2d bits  %s  (hang has +, healthy has -) %s" % (n, nm[7:], "; ".join(diff)))

    # the rules: F535 (C and E), F589's refinement, and a graphics-stall rule
    def has(d, reg, name):
        return bool(d.get(reg, 0) & b(reg, name))

    R = {
        "F535 C&E: ME_WAITING_ON_PARTIAL_FLUSH, EA_LINK_BUSY clear":
            lambda d: has(d, "CP_STALLED_STAT2", "ME_WAITING_ON_PARTIAL_FLUSH") and not has(d, "GRBM_STATUS2", "EA_LINK_BUSY"),
        "F589 compute: C&E, TA_BUSY, GE_BUSY clear, no EOPD wait":
            lambda d: R["F535 C&E: ME_WAITING_ON_PARTIAL_FLUSH, EA_LINK_BUSY clear"](d) and has(d, "GRBM_STATUS", "TA_BUSY")
            and not has(d, "GRBM_STATUS", "GE_BUSY") and not has(d, "CP_STALLED_STAT2", "EOPD_FIFO_NEEDS_SC_EOP_DONE"),
        "G graphics: C&E, GE_BUSY, TA_BUSY clear, EOPD wait":
            lambda d: R["F535 C&E: ME_WAITING_ON_PARTIAL_FLUSH, EA_LINK_BUSY clear"](d) and has(d, "GRBM_STATUS", "GE_BUSY")
            and not has(d, "GRBM_STATUS", "TA_BUSY") and has(d, "CP_STALLED_STAT2", "EOPD_FIFO_NEEDS_SC_EOP_DONE"),
        "G2 graphics, no EA term: ME_WAITING_ON_PARTIAL_FLUSH, GE_BUSY, TA_BUSY clear, EOPD wait":
            lambda d: has(d, "CP_STALLED_STAT2", "ME_WAITING_ON_PARTIAL_FLUSH") and has(d, "GRBM_STATUS", "GE_BUSY")
            and not has(d, "GRBM_STATUS", "TA_BUSY") and has(d, "CP_STALLED_STAT2", "EOPD_FIFO_NEEDS_SC_EOP_DONE"),
    }
    full = {k: v for k, v in events.items() if "CP_STALLED_STAT2" in v}
    print("\n== single-sample rules (fires = looks like that stall)")
    print("  rule | healthy | " + " | ".join(k.split(" (")[0] for k in full))
    for name, f in R.items():
        hs = [d for d in healthy if "CP_STALLED_STAT2" in d]
        print("  %s | %d/%d | %s" % (name, sum(1 for d in hs if f(d)), len(hs),
                                    " | ".join("yes" if f(v) else "no" for v in full.values())))
    c = R["F535 C&E: ME_WAITING_ON_PARTIAL_FLUSH, EA_LINK_BUSY clear"]
    print("  healthy samples with ME_WAITING_ON_PARTIAL_FLUSH: %d; of them GE_BUSY %d, EOPD wait %d, both %d"
          % tuple([sum(1 for d in healthy if has(d, "CP_STALLED_STAT2", "ME_WAITING_ON_PARTIAL_FLUSH") and g(d)) for g in (
              lambda d: True, lambda d: has(d, "GRBM_STATUS", "GE_BUSY"),
              lambda d: has(d, "CP_STALLED_STAT2", "EOPD_FIFO_NEEDS_SC_EOP_DONE"),
              lambda d: has(d, "GRBM_STATUS", "GE_BUSY") and has(d, "CP_STALLED_STAT2", "EOPD_FIFO_NEEDS_SC_EOP_DONE"))]))
    del c


if __name__ == "__main__":
    main()
