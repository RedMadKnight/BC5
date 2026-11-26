#!/usr/bin/env python3
"""Experiment 0441 follow-up: which shader programs of a dump use the flat apertures (private input, counts out).

  shscan0441.py <view-file> <view-base> [--all] [--check ADDR]

The dumped program area begins with the title's shader objects; each holds its register pairs (register offset in
the low dword, value in the high dword). A program's start and stage are taken from the pair that sets a
*_PGM_LO register (SH register offsets: compute 0x20c, PS 0x08, VS 0x48, GS 0x88, ES 0xc8, HS 0x108, LS 0x148;
names as in Mesa 0866ae7085c1 src/amd/registers/gfx10.json, R_00B830 COMPUTE_PGM_LO, R_00B020, R_00B120,
R_00B220, R_00B320, R_00B420, R_00B520) followed by the matching *_PGM_HI pair with value 0.

Each program is then walked instruction by instruction (lengths by encoding class, gfx10: FLAT = top six bits
0x37, opcode bits 18-24, segment bits 14-15 with 0 flat, 1 scratch, 2 global; a source field of 255 means a 32-bit
literal follows; the multiply-add-with-constant opcodes always carry one; SDWA and DPP sources carry a modifier
dword; an image instruction carries the extra address dwords its first dword counts). Source of the classes: LLVM's
llvm/lib/Target/AMDGPU/SIInstrFormats.td, VOP2Instructions.td, VOP3Instructions.td, FLATInstructions.td
(TODO(verify): the commit of the container's LLVM was not recorded), checked here against llvm-mc's own listing of
two programs (shdis0441.py: the same 18 flat stores, 6 scratch loads and 6 intersections each). A program ends at
its last s_endpgm: an earlier one has a branch target behind it. A walk that meets an unknown class or runs into
the next program is reported as "WALK LOST"; on the first dump all 595 named programs walk cleanly.

Programs that no object names are found from the s_endpgm words outside every walk: the start is the first
0x100-aligned address after the previous program from which a walk ends exactly there; their stage is unknown.

Per program: flat stores and loads (segment 0), scratch stores and loads, global stores and loads, ray/BVH
intersection instructions (image opcodes 0xe6 and 0xe7), the literals 0x70000000 and 0x80000000, and for every flat access the instruction that last wrote the high half of its
address register before it (linear search backwards, control flow ignored): "clamp" = a three-operand instruction
with the literal 0x70000000 (the traversal stack push of the cloth programs), "literal" = any other instruction
with a literal (printed), "load" = read from memory, "other" = computed.

Output is counts by program address: no title code. The view file is private.
"""
import collections
import struct
import sys

PGM_LO = {0x20C: "compute", 0x08: "pixel", 0x48: "vertex", 0x88: "geometry", 0xC8: "es/merged", 0x108: "hull", 0x148: "ls"}
ENDPGM = 0xBF810000


def length(dw, i):
    """(number of dwords, class, literal or None) of the instruction at dw[i]"""
    w = dw[i]
    if w >> 31 == 0:
        src0 = w & 0x1FF
        if src0 in (0xF9, 0xFA, 0xE9, 0xEA):        # SDWA, DPP16, DPP8: one modifier dword follows
            return 2, "vop", None
        if (w >> 25) in (0x20, 0x21, 0x2B, 0x2D, 0x37, 0x38):   # v_madmk/madak/fmamk/fmaak: a constant always follows
            return 2, "vop", dw[i + 1]
        return (2, "vop", dw[i + 1]) if src0 == 255 else (1, "vop", None)
    if w >> 30 == 2:
        t = w >> 23
        if t == 0x17F:
            return 1, "sopp", None
        if t == 0x17D:
            lit = (w & 0xFF) == 255
            return (2, "sop", dw[i + 1]) if lit else (1, "sop", None)
        if t != 0x17E and w >> 28 == 0xB:
            op = (w >> 23) & 0x1F
            return (2, "sopk", dw[i + 1]) if op == 21 else (1, "sopk", None)
        lit = (w & 0xFF) == 255 or ((w >> 8) & 0xFF) == 255
        return (2, "sop", dw[i + 1]) if lit else (1, "sop", None)
    e = w >> 26
    if e == 0x32:
        return 1, "vintrp", None
    if e in (0x33, 0x34, 0x35):
        x = dw[i + 1]
        lit = (x & 0x1FF) == 255 or ((x >> 9) & 0x1FF) == 255 or ((x >> 18) & 0x1FF) == 255
        return (3, "vop3", dw[i + 2]) if lit else (2, "vop3", None)
    if e == 0x3C:
        return 2 + ((w >> 1) & 3), "mimg", None
    if e in (0x3D, 0x36, 0x37, 0x38, 0x3A, 0x3E):
        return 2, {0x3D: "smem", 0x36: "ds", 0x37: "flat", 0x38: "mubuf", 0x3A: "mtbuf", 0x3E: "exp"}[e], None
    return 1, "bad", None


def vdst(dw, i, cls):
    """the vector register an instruction writes, or None"""
    w = dw[i]
    if cls == "vop":
        if (w >> 25) == 0x3E:                       # VOPC writes vcc
            return None
        return (w >> 17) & 0xFF
    if cls == "vop3":
        return w & 0xFF
    if cls in ("ds", "flat"):
        return dw[i + 1] >> 24
    if cls in ("mubuf", "mtbuf", "mimg"):
        return (dw[i + 1] >> 8) & 0xFF
    return None


def walk(dw, s, limit):
    """instructions from dw[s] to the program's last s_endpgm: an early exit has a branch target behind it, the
    last one has none (SOPP opcodes 2 and 4-9, s_branch and s_cbranch_*, target = next dword + signed 16 bits)"""
    out = []
    i = s
    far = s
    while i < limit:
        n, cls, lit = length(dw, i)
        out.append((i, n, cls, lit))
        w = dw[i]
        if cls == "sopp" and (w >> 16) & 0x7F in (2, 4, 5, 6, 7, 8, 9):
            d = w & 0xFFFF
            far = max(far, i + 1 + (d - 0x10000 if d & 0x8000 else d))
        if w == ENDPGM and far <= i:
            return out, True
        if cls == "bad":
            return out, False
        i += n
    return out, False


def scan(dw, s, limit):
    ins, ok = walk(dw, s, limit)
    c = collections.Counter()
    src = collections.Counter()
    lits = collections.Counter()
    for k, (i, n, cls, lit) in enumerate(ins):
        w = dw[i]
        if lit is not None and lit in (0x70000000, 0x80000000):
            lits[lit] += 1
        if cls == "mimg" and (w >> 18) & 0x7F in (0x66, 0x67) and w & 1:   # image_bvh(64)_intersect_ray, opcodes 0xe6/0xe7
            c["bvh"] += 1
        if cls == "exp":
            c["exp"] += 1
        if cls != "flat":
            continue
        op, seg = (w >> 18) & 0x7F, (w >> 14) & 3
        kind = ("flat", "scratch", "global", "seg3")[seg] + ("-store" if op >= 24 else "-load")
        c[kind] += 1
        if seg != 0:
            continue
        hi = (dw[i + 1] & 0xFF) + 1                 # the high half of the 64-bit address register pair
        how = "not found"
        for j in range(k - 1, max(k - 400, -1), -1):
            pi, pn, pcls, plit = ins[j]
            if vdst(dw, pi, pcls) != hi:
                continue
            if pcls in ("ds", "flat", "mubuf", "mtbuf", "mimg"):
                how = "load"
            elif plit == 0x70000000 and pcls == "vop3":
                how = "clamp"
            elif plit is not None:
                how = "literal %#x" % plit
            else:
                how = "other"
            break
        src[kind + " high half by " + how] += 1
    return ins, ok, c, src, lits


def main():
    view, base = sys.argv[1], int(sys.argv[2], 0)
    show_all = "--all" in sys.argv
    with open(view, "rb") as f:
        raw = f.read()
    dw = struct.unpack("<%dI" % (len(raw) // 4), raw)
    end = base + len(raw)
    progs = {}
    for i in range(0, len(dw) - 3, 2):
        reg, val = dw[i], dw[i + 1]
        if reg in PGM_LO and dw[i + 2] == reg + 1 and dw[i + 3] == 0 and val:
            a = val << 8
            if base <= a < end:
                progs.setdefault(a, collections.Counter())[PGM_LO[reg]] += 1
    starts = sorted(progs)
    if "--check" in sys.argv:
        a = int(sys.argv[sys.argv.index("--check") + 1], 0)
        ins, ok = walk(dw, (a - base) // 4, len(dw))
        print("check %#x: %d instructions, ends on its last s_endpgm: %s" % (a, len(ins), ok))
    print("programs named by a *_PGM_LO pair: %d; by stage: %s" % (
        len(starts), dict(collections.Counter(s for a in starts for s in progs[a]))))
    tot = collections.Counter()
    lost = 0
    rows = []
    for k, a in enumerate(starts):
        s = (a - base) // 4
        limit = (starts[k + 1] - base) // 4 if k + 1 < len(starts) else len(dw)
        ins, ok, c, src, lits = scan(dw, s, limit)
        stage = "+".join(sorted(progs[a]))
        if not ok:
            lost += 1
        tot[stage] += 1
        flat = c["flat-store"] + c["flat-load"]
        if flat or show_all or not ok:
            rows.append((a, stage, len(ins), ok, c, src, lits))
    print("walks that did not end on s_endpgm: %d of %d" % (lost, len(starts)))
    # programs that no object names: s_endpgm words outside every walk; the start is the first 0x100-aligned
    # address after the previous program from which the walk ends exactly there
    spans = sorted(((a - base) // 4, (a - base) // 4 + sum(x[1] for x in walk(dw, (a - base) // 4, len(dw))[0])) for a in starts)
    unnamed = 0
    orphan = 0
    for e in (i for i in range(len(dw)) if dw[i] == ENDPGM):
        prev = [sp for sp in spans if sp[0] <= e]
        if prev and e < prev[-1][1]:
            continue
        c = ((prev[-1][1] if prev else 0) * 4 + 0xFF) // 0x100 * 0x100 // 4
        found = None
        while c < e:
            ins, ok = walk(dw, c, e + 1)
            if ok and ins[-1][0] == e and len(ins) > 4:
                found = c
                break
            c += 0x40
        if found is None:
            orphan += 1
            continue
        unnamed += 1
        spans.append((found, e + 1))
        spans.sort()
        ins, ok, c2, src, lits = scan(dw, found, e + 1)
        if c2["flat-store"] + c2["flat-load"] or show_all:
            rows.append((base + 4 * found, "unnamed", len(ins), ok, c2, src, lits))
    print("programs that no object names: %d found by their end (%d more s_endpgm words with no start found)" % (unnamed, orphan))
    print("programs with a flat-segment access: %d" % sum(1 for r in rows if r[4]["flat-store"] + r[4]["flat-load"]))
    for a, stage, n, ok, c, src, lits in rows:
        print("%#x %-9s %6d ins%s  flat st/ld %d/%d  scratch st/ld %d/%d  global st/ld %d/%d  bvh %d  lit70/80 %d/%d  | %s" % (
            a, stage, n, "" if ok else " WALK LOST", c["flat-store"], c["flat-load"], c["scratch-store"], c["scratch-load"],
            c["global-store"], c["global-load"], c["bvh"], lits[0x70000000], lits[0x80000000],
            "; ".join("%s x%d" % kv for kv in sorted(src.items()))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
