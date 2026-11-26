#!/usr/bin/env python3
"""BC5 experiment 0412, tag zc412 (README section 33): the zero skip's blind window, counted.
Input: the main unit after mklock, mksect, mkgap, mkbuf, mkret and mkuse. zcat0412.inc goes in before use0412.inc's
block, and in zskip_take_back(): zc412::poll(g_submits.load()) before the walk over the runs that looks for CPU data,
and zc412::found(c) where a chunk with CPU data is taken back.
BC5_GUARD_ZSKIP_STAT unset: both are one test of a constant. No statement is removed or reordered.
Each anchor occurs exactly once; the script undoes its edits and asserts that this gives the input back.
usage: mkzcat0412.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
T = b" // exp 0412 (tag zc412)\n"


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    s = open(sys.argv[1], "rb").read()
    inc = open(os.path.join(HERE, "zcat0412.inc"), "rb").read()
    assert b"namespace us412" in s and b"namespace zc412" not in s, "refused: not the expected input"
    assert b"\r" not in s and b"\r" not in inc
    inc.decode("ascii")
    edits = []
    a = b"// Experiment 0412 (tag us412): BC5_GUARD_USE_STAT, the guest memory that command buffers name.\n"
    edits.append((a, b"// Experiment 0412 (tag zc412): BC5_GUARD_ZSKIP_STAT, the zero skip's blind window.\n#define ZC412_PRINT journal\n#define ZC412_NOW timing_now\n" + inc + a))
    a = b"\tfor (size_t r = 0; r < g_zskip.run_count() && r < g_zleft.size(); r++) {\n\t\tif (g_zleft[r] == 0) continue;\n\t\tconst auto [o, l] = g_zskip.run(static_cast<uint32_t>(r));\n\t\tfor (uint64_t pos = o; pos < o + l;) {\n"
    edits.append((a, b"\tzc412::poll(g_submits.load());" + T + a))
    a = b"\t\t\t\tg_zstat_cpu++;\n\t\t\t\tg_zleft[r] -= kDChunk;\n"
    edits.append((a, a + b"\t\t\t\tzc412::found(c);" + T))
    out = s
    for old, new in edits:
        assert out.count(old) == 1, ("an anchor does not occur exactly once", old[:60], out.count(old))
        out = out.replace(old, new)
    back = out
    for old, new in reversed(edits):
        assert back.count(new) == 1, ("undo", new[:60], back.count(new))
        back = back.replace(new, old)
    assert back == s, "undoing the edits does not give the input back"
    lo = out.index(b"static void zskip_take_back(DState& S, int fd) {\n")
    hi = out.index(b"\n}\n", lo)
    assert out[lo:hi].count(b"zc412::") == 2, "both stamps must lie inside zskip_take_back"
    assert out.index(b"namespace zc412") < lo
    open(sys.argv[2], "wb").write(out)
    print(f"bc5LleAgc.cpp {hashlib.md5(out).hexdigest()}")


if __name__ == "__main__":
    main()
