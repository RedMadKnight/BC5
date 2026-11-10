# BC5 hang1954-0401.md, A3: branch targets in an llvm-mc (-mcpu=gfx1013) text listing that has no offsets. Each
# instruction's size is estimated from its encoding class (RDNA 1 encodings: SOPP/SOP1/SOP2/SOPC/SOPK and VOP1/VOP2/
# VOPC 4 bytes; SMEM, VOP3, VOP3P, SDWA, DPP, DS, MUBUF/MTBUF, FLAT/GLOBAL, EXP and MIMG 8 bytes; plus 4 for a literal
# constant, i.e. an operand outside the inline range -16..64 and the inline floats), and each branch's target line is
# resolved (target = next instruction + 4 * simm16).
# It prints line numbers, mnemonics and offsets only: never operands, so no title code leaves the listing.
# The listing is the title's code: it stays on the box or in a private scratch, never in git.
# usage: python -I isa1954.py <listing> [line ...]   (line numbers to report the branch targets of; default all branches)
import re
import sys

INLINE_F = {"0.5", "-0.5", "1.0", "-1.0", "2.0", "-2.0", "4.0", "-4.0", "0.15915494"}
SOPP = re.compile(r"^s_(nop|endpgm|branch|cbranch_\w+|waitcnt|barrier|sendmsg\w*|trap|inst_prefetch|setprio|sleep|icache_inv|"
                  r"clause|code_end|ttracedata|setkill|wakeup|incperflevel|decperflevel|round_mode|denorm_mode|setvskip|"
                  r"waitcnt_depctr|endpgm_saved)\b")
SMEM = re.compile(r"^s_(load|buffer_load|store|buffer_store|dcache|memtime|memrealtime|atc_probe|scratch)\w*")
VMEM = re.compile(r"^(buffer|tbuffer|image|flat|global|scratch|ds|exp)\b|^(buffer|tbuffer|image|flat|global|scratch|ds)_")


def literal(ops):
    for o in re.split(r"[,\s]+", ops):
        o = o.strip()
        if not o or o.startswith(("s", "v", "vcc", "exec", "m0", "null", "off", "done", "idxen", "offen", "offset",
                                  "src", "dst", "sext", "neg", "abs", "lgkmcnt", "vmcnt", "expcnt", "sendmsg",
                                  "clamp", "glc", "slc", "dlc", "row", "bank", "quad", "dpp", "op_sel", "mul", "div",
                                  "scc", "pos", "param", "prim", "mrt")):
            continue
        if o in INLINE_F:
            continue
        try:
            v = int(o, 0)
        except ValueError:
            if re.fullmatch(r"-?\d+\.\d+(e-?\d+)?", o):
                return True
            continue
        if not (-16 <= v <= 64):
            return True
    return False


def size(line):
    parts = line.split(None, 1)
    m = parts[0]
    ops = parts[1] if len(parts) > 1 else ""
    if SOPP.match(m):
        return 4
    if SMEM.match(m):
        return 8
    if VMEM.match(m) or m == "exp":
        return 8
    lit = 4 if literal(ops.split(" src0_sel")[0].split(" dst_sel")[0]) else 0
    if m.startswith("s_"):
        return 4 + lit
    if m.endswith(("_sdwa", "_dpp", "_dpp8")):
        return 8
    if m.endswith("_e32") or m in ("v_readfirstlane_b32", "v_nop", "v_mov_b32", "v_movreld_b32", "v_movrels_b32"):
        return 4 + lit
    return 8 + lit  # VOP3, VOP3P, _e64 and the VOP3-only opcodes


def main(path, want):
    rows = [l.strip() for l in open(path, errors="replace") if l.strip() and not l.strip().startswith((".", ";", "//"))]
    off, offs = 0, []
    for r in rows:
        offs.append(off)
        off += size(r)
    at = {o: k for k, o in enumerate(offs)}
    print("%s: %d instructions, %d bytes (estimated)" % (path, len(rows), off))
    for k, r in enumerate(rows):
        m = r.split()[0]
        if not (m.startswith("s_cbranch") or m == "s_branch"):
            continue
        if want and (k + 1) not in want:
            continue
        simm = int(r.split()[1], 0)
        if simm >= 0x8000:
            simm -= 0x10000
        tgt = offs[k] + 4 + 4 * simm
        t = at.get(tgt)
        print("line %4d %-20s %6d -> byte 0x%x: %s" % (k + 1, m, simm, tgt, ("line %d (%s)" % (t + 1, rows[t].split()[0])) if t is not None
              else ("past the end" if tgt >= off else "between instructions: the size estimate is off before here")))


if __name__ == "__main__":
    main(sys.argv[1], {int(x) for x in sys.argv[2:]})
