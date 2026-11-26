#!/usr/bin/env python3
# BC5 exp 0381: drawcheck0381.py against synthetic host IBs: the check as indirect_check.cpp emits it for a draw
# (verified), and Codex review (REVIEW-04)'s counterexample (audit/test_review04_guard_heuristic.py: a COND_WRITE on an
# unrelated address and a zero-dword COND_EXEC, which the first version counted as a check), plus two more mismatches.
# usage: python test_drawcheck0381.py
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def pkt(op, *w):
    return [0xC0000000 | ((len(w) - 1) << 16) | (op << 8), *w]


def check(base, off, flag, lv=1 << 20, li=64, poll_shift=0, ce_count=5, ce_flag=None):
    a = base + off
    w = pkt(0x37, 5 << 8, flag & 0xffffffff, flag >> 32, 1)
    for k, lim in ((0, lv), (4, li)):
        p = a + k + poll_shift
        w += pkt(0x45, 6 | (1 << 4) | (1 << 8), p & 0xffffffff, p >> 32, lim, 0xffffffff, flag & 0xffffffff, flag >> 32, 0)
    w += pkt(0x37, (5 << 8) | (1 << 20), (flag + 4) & 0xffffffff, (flag + 4) >> 32, 0)
    w += pkt(0x42, 0)
    cf = flag if ce_flag is None else ce_flag
    w += pkt(0x22, cf & 0xffffffff, cf >> 32, 0, ce_count)
    return w


def run(words):
    with tempfile.TemporaryDirectory(prefix="bc5-0381-") as d:
        f = Path(d) / "devcd.txt"
        f.write_text("header\nIB #0 of %d dwords\n" % len(words) + "".join("%08x\n" % x for x in words))
        p = subprocess.run([sys.executable, str(HERE / "drawcheck0381.py"), str(f)], capture_output=True, text=True)
        assert p.returncode == 0, p.stderr
        return p.stdout


base, off, flag = 0x1193AD3900, 0xC4A0, 0x100A0001000
sb = pkt(0x11, 1, base & 0xffffffff, base >> 32)
draw = pkt(0x24, off, 0x4C, 0x4D, 2)

out = run(sb + check(base, off, flag) + draw)
assert "| ok (limits 1048576 vertices, 64 instances)" in out and "verified packet for packet: 1" in out, out

# Codex REVIEW-04: unrelated poll, zero-dword COND_EXEC
codex = pkt(0x11, 1, 0x1000, 0x11)
codex += pkt(0x45, 6 | (1 << 4) | (1 << 8), 0x2000, 0x11, 64, 0xFFFFFFFF, 0x3000, 0x11, 0)
codex += pkt(0x22, 0x3000, 0x11, 0, 0)
codex += pkt(0x24, 0, 0, 0, 0)
out = run(codex)
assert "verified packet for packet: 0" in out, out

out = run(sb + check(base, off, flag, poll_shift=0x20) + draw)
assert "polls 0x1193ae0000" not in out and "polls" in out and "verified packet for packet: 0" in out, out
out = run(sb + check(base, off, flag, ce_count=0) + draw)
assert "COND_EXEC covers 0 dwords" in out, out
out = run(sb + check(base, off, flag, ce_flag=flag + 8) + draw)
assert "COND_EXEC tests" in out, out
out = run(check(base, off, flag) + draw)
assert "no SET_BASE 1 known" in out, out
print("drawcheck0381: 6 cases pass")
