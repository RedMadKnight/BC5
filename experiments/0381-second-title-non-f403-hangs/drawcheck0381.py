#!/usr/bin/env python3
# BC5 exp 0381: in a devcoredump's hung IB (IB #0, the host's filtered IB), verify for every DRAW_INDIRECT /
# DRAW_INDEX_INDIRECT that the host's CP check (experiment 0057, bc5/indirect_check.cpp apply(), dims = 2, no
# staircase) stands right before it, packet for packet, and is about that draw:
#   WRITE_DATA   flag = 1                          (DST_SEL memory)
#   COND_WRITE   [A] > Lv ? flag = 0               (function 6 "greater", poll memory, write memory, mask ~0)
#   COND_WRITE   [A + 4] > Li ? flag = 0
#   WRITE_DATA   flag + 4 = 0, WR_CONFIRM
#   PFP_SYNC_ME
#   COND_EXEC    flag, count = the draw's length
#   DRAW_*INDIRECT
# with A = the SET_BASE 1 in effect + the draw's data offset. Codex review (REVIEW-04) showed that the first version,
# which counted any COND_WRITE and COND_EXEC among the 8 packets before a draw, called a check on an unrelated address
# with a zero-dword COND_EXEC "checked"; this version names the first mismatch per draw instead. Prints offsets,
# addresses, limits and verdicts only; no payload.
# usage: python3 drawcheck0381.py <devcoredump.txt>
import sys

W_DATA, W_MEM, WR_CONFIRM = 0x37, 5 << 8, 1 << 20
COND_WRITE_CTL = 6 | (1 << 4) | (1 << 8)


def packets(ib):
    out, i = [], 0
    while i < len(ib):
        h = ib[i]
        t = h >> 30
        ln = 1
        if t in (0, 3):
            c = (h >> 16) & 0x3fff
            ln = 1 if c == 0x3fff else c + 2
        out.append((i, t, (h >> 8) & 0xff, ib[i:i + ln]))
        i += ln
    return out


def addr(lo, hi):
    return (lo & ~3) | ((hi & 0xffff) << 32)


def verify(pk, k, a):
    """Returns (verdict, limits); verdict 'ok' or the first mismatch."""
    if k < 6:
        return "no room for a check", None
    wd, cw1, cw2, conf, sync, ce = pk[k - 6:k]
    if not all(q[1] == 3 for q in (wd, cw1, cw2, conf, sync, ce)):
        return "a non-type-3 packet in the check", None
    if wd[2] != W_DATA or len(wd[3]) != 5 or (wd[3][1] & 0xf00) != W_MEM or wd[3][4] != 1:
        return "no flag = 1 WRITE_DATA", None
    flag = addr(wd[3][2], wd[3][3])
    lims = []
    for q, off in ((cw1, 0), (cw2, 4)):
        p = q[3]
        if q[2] != 0x45 or len(p) != 9:
            return "no COND_WRITE at %d" % q[0], None
        if p[1] != COND_WRITE_CTL:
            return "COND_WRITE %d control 0x%x" % (q[0], p[1]), None
        if addr(p[2], p[3]) != a + off:
            return "COND_WRITE %d polls 0x%x, not 0x%x" % (q[0], addr(p[2], p[3]), a + off), None
        if p[5] != 0xffffffff or addr(p[6], p[7]) != flag or p[8] != 0:
            return "COND_WRITE %d writes 0x%x = %d (mask 0x%x), not flag 0x%x = 0" % (
                q[0], addr(p[6], p[7]), p[8], p[5], flag), None
        lims.append(p[4])
    p = conf[3]
    if conf[2] != W_DATA or len(p) != 5 or (p[1] & 0xf00) != W_MEM or not p[1] & WR_CONFIRM or addr(p[2], p[3]) != flag + 4:
        return "no confirm WRITE_DATA at flag + 4", None
    if sync[2] != 0x42:
        return "no PFP_SYNC_ME", None
    p = ce[3]
    if ce[2] != 0x22 or len(p) != 5:
        return "no COND_EXEC", None
    if addr(p[1], p[2]) != flag:
        return "COND_EXEC tests 0x%x, not the flag 0x%x" % (addr(p[1], p[2]), flag), None
    if (p[4] & 0x3fff) != len(pk[k][3]):
        return "COND_EXEC covers %d dwords, the draw is %d" % (p[4] & 0x3fff, len(pk[k][3])), None
    return "ok", lims


def main(path):
    lines = open(path, errors="replace").read().split("\n")
    start = next(i for i, l in enumerate(lines) if l.startswith("IB #0 "))
    n = int(lines[start].split()[3])
    ib = [int(x, 16) for x in lines[start + 1:start + 1 + n]]
    pk = packets(ib)
    base1 = 0
    draws = ok = 0
    for k, (at, t, op, p) in enumerate(pk):
        if t != 3:
            continue
        if op == 0x11 and len(p) >= 4 and (p[1] & 0xf) == 1:
            base1 = addr(p[2], p[3])
        if op in (0x24, 0x25) and len(p) == 5:
            draws += 1
            a = base1 + p[1]
            verdict, lims = verify(pk, k, a) if base1 else ("no SET_BASE 1 known", None)
            ok += verdict == "ok"
            print("%6d op 0x%02x data_offset 0x%x base1 0x%x args 0x%x | %s%s" % (
                at, op, p[1], base1, a, verdict, " (limits %d vertices, %d instances)" % tuple(lims) if lims else ""))
    print("draws %d, with exp 0057's check verified packet for packet: %d" % (draws, ok))


if __name__ == "__main__":
    main(sys.argv[1])
