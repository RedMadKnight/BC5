#!/usr/bin/env python3
# BC5 experiment 0244: the structure of one of the title's shader programs from its private disassembly listing
# (~/bc5-data/priv/<address>.dis, llvm-mc -mcpu=gfx1013 text from earlier experiments; the title's code, never copied
# off the box). Prints only mnemonics, counts, register origins and immediate offsets; no instruction text.
# Scalar registers are followed from the program start: user SGPRs hold SPI_SHADER_USER_DATA (from s0 for a pixel
# program; from s8 for a merged ES/GS program, after its 8 system SGPRs, as Mesa's ac_shader_args lays them out
# (src/amd/common/ac_shader_args.h) TODO(verify) for the title's compiler); s_load_dword* from a user-data pair
# gives "udK+0xOFF", from a register loaded that way "udK+0xOFF>+0xOFF2"; s_buffer_load_dword* gives "cbuf(<V#>)+OFF";
# s_mov copies the origin; other scalar writes give "alu". For each image/buffer/global memory instruction the origin
# of its resource descriptor (and sampler) is reported; exec-mask writes (v_cmpx_*, s_*_b32/b64 exec, s_wqm),
# s_cbranch_execz/execnz, exports (exp mrt*, mrtz, null) and s_endpgm are listed as the program's discard skeleton.
# usage: python3 -I code0244.py <listing> [user SGPR base, 0 for PS, 8 for ES/GS]
import collections, re, sys

path = sys.argv[1]
UBASE = int(sys.argv[2]) if len(sys.argv) > 2 else 0
SREG = re.compile(r"\bs\[(\d+):(\d+)\]|\bs(\d+)\b")


def sregs(op):
    m = re.fullmatch(r"s\[(\d+):(\d+)\]", op.strip())
    if m:
        return list(range(int(m[1]), int(m[2]) + 1))
    m = re.fullmatch(r"s(\d+)", op.strip())
    return [int(m[1])] if m else []


def imm(op):
    op = op.strip()
    try:
        return int(op, 0)
    except ValueError:
        return None


lines = []
for l in open(path, errors="replace"):
    l = l.split("//")[0].split(";")[0].strip()
    if not l or l.startswith(".") or l.endswith(":"):
        continue
    parts = l.split(None, 1)
    mn = parts[0]
    ops = [o.strip() for o in re.split(r",(?![^\[]*\])", parts[1])] if len(parts) > 1 else []
    lines.append((mn, ops))
    if mn == "s_code_end":
        break
origin = {k: "ud%d" % (k - UBASE) for k in range(UBASE, UBASE + 32)}
res = collections.Counter()
skel = []
counts = collections.Counter()
for i, (mn, ops) in enumerate(lines):
    counts["instructions"] += 1
    if mn.startswith("s_load_dword") and len(ops) >= 3:
        dst, base, off = sregs(ops[0]), sregs(ops[1]), imm(ops[2])
        b = origin.get(base[0], "alu") if base else "alu"
        tag = "%s+0x%x" % (b if b.startswith("ud") and "+" not in b else "<%s>" % b, off) if off is not None else "%s+?" % b
        for k, r in enumerate(dst):
            origin[r] = "%s[%d]" % (tag, k) if k else tag
        skel.append("%s %s" % (mn, tag))
        continue
    if mn.startswith("s_buffer_load_dword") and len(ops) >= 3:
        dst, desc, off = sregs(ops[0]), sregs(ops[1]), imm(ops[2])
        tag = "cbuf(%s)+%s" % (origin.get(desc[0], "alu") if desc else "?", "0x%x" % off if off is not None else "?")
        for r in dst:
            origin[r] = tag
        counts["s_buffer_load"] += 1
        continue
    if mn in ("s_mov_b32", "s_mov_b64") and len(ops) >= 2:
        d, s = sregs(ops[0]), sregs(ops[1])
        for k, r in enumerate(d):
            origin[r] = origin.get(s[k], "alu") if k < len(s) else "alu"
        if ops[0].startswith("exec"):
            skel.append("%s exec" % mn)
        continue
    if re.match(r"(image|buffer|tbuffer|global|flat)_", mn):
        rs = [list(range(int(a), int(b) + 1)) for a, b in re.findall(r"\bs\[(\d+):(\d+)\]", " ".join(ops))]
        rdesc = origin.get(rs[0][0], "alu") if rs else "-"
        samp = origin.get(rs[1][0], "alu") if len(rs) > 1 else "-"
        res[(mn, rdesc, samp)] += 1
        skel.append("%s T#/V# %s%s" % (mn, rdesc, " samp %s" % samp if samp != "-" else ""))
        continue
    if mn.startswith("v_cmpx") or (mn.startswith("s_") and ops and ops[0].startswith("exec")) or mn.startswith("s_wqm"):
        counts["exec writes"] += 1
        skel.append(mn)
        continue
    if mn.startswith("s_cbranch_exec") or mn == "s_endpgm" or mn.startswith("s_branch") or mn.startswith("s_cbranch_scc") or mn.startswith("s_cbranch_vcc"):
        counts[mn] += 1
        skel.append(mn)
        continue
    if mn == "exp" and ops:
        tgt = ops[0].split()[0]  # the export target only (mrtN, posN, prim, null): no register operands leave the box
        counts["exp " + tgt] += 1
        skel.append("exp %s%s" % (tgt, " done" if "done" in " ".join(ops) else ""))
        continue
    if mn.startswith("s_") and ops:
        for r in sregs(ops[0]):
            origin[r] = "alu"
print("# %s: user SGPRs from s%d" % (path, UBASE))
print("(1) counts: " + ", ".join("%s %d" % kv for kv in sorted(counts.items())))
print("(2) memory reads by resource origin (udK+0xOFF: the descriptor loaded from the table the user-data pair K points at):")
for (mn, rd, sp), n in sorted(res.items(), key=lambda kv: -kv[1]):
    print("  %3d x %-34s %-34s %s" % (n, mn, rd, "samp " + sp if sp != "-" else ""))
print("(3) skeleton (descriptor loads, memory reads, exec writes, branches, exports), repeats folded:")
out = []
for s in skel:
    if out and out[-1][0] == s:
        out[-1][1] += 1
    else:
        out.append([s, 1])
for s, n in out:
    print("  %s%s" % (s, " x%d" % n if n > 1 else ""))
