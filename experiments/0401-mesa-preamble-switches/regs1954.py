# BC5 hang1954-0401.md: decodes the CP/GRBM status registers of amdgpu devcoredumps bit by bit and prints the bits
# that differ between them. Register values only; no buffer contents are read (the IB section is skipped).
# Field names: GRBM_STATUS*, CP_CPF_*: tools/bc5-agc/regdb/gfx10.json (Mesa, MIT); CP_STALLED_STAT1/2, CP_BUSY_STAT:
# Linux v7.2 drivers/gpu/drm/amd/include/asic_reg/gc/gc_10_1_0_sh_mask.h (the *_MASK defines), as exp 0404 cites them.
# usage: python -I regs1954.py <gfx10.json> <gc_10_1_0_sh_mask.h> name=<devcoredump.txt> [name=<devcoredump.txt> ...]
#        a value may also be given directly: name=GRBM_STATUS:0xa2712028,CP_STALLED_STAT2:0x230000
import json
import re
import sys

JSON_REGS = ["GRBM_STATUS", "GRBM_STATUS2", "GRBM_STATUS3", "GRBM_STATUS_SE0", "CP_CPF_STATUS", "CP_CPF_BUSY_STAT",
             "CP_CPF_STALLED_STAT1"]
MASK_REGS = ["CP_STALLED_STAT1", "CP_STALLED_STAT2", "CP_BUSY_STAT"]
PLAIN = ["GRBM_STATUS_SE1", "GRBM_STATUS_SE2", "GRBM_STATUS_SE3", "CP_ME_INSTR_PNTR", "CP_PFP_INSTR_PNTR",
         "CP_IB1_CMD_BUFSZ", "CP_IB1_BUFSZ", "CP_IB2_CMD_BUFSZ", "CP_IB2_BUFSZ", "GCVM_L2_PROTECTION_FAULT_STATUS"]


def json_fields(path):
    d = json.load(open(path))
    out = {}
    for n in JSON_REGS:
        out[n] = [(f["name"], f["bits"][0], f["bits"][1]) for f in d["register_types"][n]["fields"]]
    return out


def mask_fields(path):
    out = {n: [] for n in MASK_REGS}
    pat = re.compile(r"#define (\w+?)__(\w+)_MASK\s+0x([0-9A-Fa-f]+)L")
    for line in open(path, errors="replace"):
        m = pat.match(line)
        if m and m.group(1) in out:
            mask = int(m.group(3), 16)
            lo = (mask & -mask).bit_length() - 1
            out[m.group(1)].append((m.group(2), lo, mask.bit_length() - 1))
    return out


def read_dump(path):
    """The first value of each register in the GC list (stops at the first 'IB #' line)."""
    vals = {}
    for line in open(path, errors="replace"):
        if line.startswith("IB #"):
            break
        m = re.match(r"mm(\w+)\s+0x([0-9a-fA-F]+)", line)
        if m and m.group(1) not in vals:
            vals[m.group(1)] = int(m.group(2), 16)
    return vals


def decode(fields, v):
    out = []
    for name, lo, hi in fields:
        f = (v >> lo) & ((1 << (hi - lo + 1)) - 1)
        if f:
            out.append(name if hi == lo else "%s=%d" % (name, f))
    return out


def main(argv):
    fj, fm = json_fields(argv[1]), mask_fields(argv[2])
    fields = dict(fj, **fm)
    dumps = []
    for a in argv[3:]:
        name, src = a.split("=", 1)
        if ":" in src and not src.endswith(".txt"):
            vals = {k: int(v, 16) for k, v in (kv.split(":") for kv in src.split(","))}
        else:
            vals = read_dump(src)
        dumps.append((name, vals))
    for reg in JSON_REGS + MASK_REGS + PLAIN:
        print(reg)
        sets = []
        for name, vals in dumps:
            if reg not in vals:
                print("  %-8s -" % name)
                sets.append(None)
                continue
            v = vals[reg]
            dec = decode(fields[reg], v) if reg in fields else []
            sets.append(set(dec))
            print("  %-8s 0x%08x %s" % (name, v, " ".join(dec)))
        if reg in fields and len(sets) > 1 and sets[0] is not None:
            for (name, _), s in list(zip(dumps, sets))[1:]:
                if s is None:
                    continue
                only0, only1 = sorted(sets[0] - s), sorted(s - sets[0])
                if only0 or only1:
                    print("    %s vs %s: only in %s: %s; only in %s: %s" % (dumps[0][0], name, dumps[0][0],
                          " ".join(only0) or "-", name, " ".join(only1) or "-"))


if __name__ == "__main__":
    main(sys.argv)
