#!/usr/bin/env python3
"""BC5 experiment 0412, tag ra412 (README section 28): the return-aware orphan release in the main unit.
Input: the main unit after mklock0412.py, mksect0412.py, mkgap0412.py and mkbuf0412.py. ret0412.inc (the text
ret0412.cpp tests) goes in before buf0412.inc, and in the lazy release (exp 0401 e7's block, which this private build
carries inside the unit; lzr0401.inc and its own CPU test are not touched):
  - the two places where a released chunk is noted as back under a view also tell ra412::table().back(chunk, now);
  - plan(): `if (ready && allowed) drop.push_back(c);` asks ra412::table().exempt(c, now) first;
  - the pass prints ra412's line (at most every 10 s) before its own 60 s report.
BC5_GUARD_RETURN_EXEMPT unset: exempt() is false after one test, back() and report() return at once: the release
decides exactly as before. Each anchor occurs exactly once; the script undoes its edits and asserts the input back.
usage: mkret0412.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
T = b" // exp 0412 (tag ra412)\n"


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    s = open(sys.argv[1], "rb").read()
    inc = open(os.path.join(HERE, "ret0412.inc"), "rb").read()
    assert b"namespace bf412" in s and b"namespace ra412" not in s, "refused: not the expected input"
    assert b"\r" not in s and b"\r" not in inc
    inc.decode("ascii")
    edits = []
    a = b"// Experiment 0412 (tag bf412): BC5_GUARD_BUF_STAT, the per-buffer time line.\n"
    edits.append((a, b"// Experiment 0412 (tag ra412): BC5_GUARD_RETURN_EXEMPT, the return-aware orphan release.\n#define RA412_PRINT journal\n" + inc + a))
    a = b"\t\t\t\tif (ready && allowed) drop.push_back(c);\n"
    edits.append((a, b"\t\t\t\tif (ready && allowed && !ra412::table().exempt(c, now)) drop.push_back(c);" + T))
    a = b"\t\t\t\tLzr0401::note_back(g_lzr, c); // the eager or data path imported it in this sync\n"
    edits.append((a, a + b"\t\t\t\tra412::table().back(c, now);" + T))
    a = b"\t\t\tfor (uint64_t c = r.lo; c < r.hi; c += Lzr0401::kChunk) Lzr0401::note_back(g_lzr, c);\n"
    edits.append((a, a + b"\t\t\tfor (uint64_t c = r.lo; c < r.hi; c += Lzr0401::kChunk) ra412::table().back(c, now);" + T))
    a = b"\tif (g_lzr.last_report == 0 || now - g_lzr.last_report >= 60 * Lzr0401::kSecond) {\n"
    edits.append((a, b"\tra412::report(now, static_cast<double>(g_lzr.cut_bytes) / 1048576.0, static_cast<double>(g_lzr.back_bytes) / 1048576.0);" + T + a))
    out = s
    for old, new in edits:
        assert out.count(old) == 1, ("an anchor does not occur exactly once", old[:60], out.count(old))
        out = out.replace(old, new)
    back = out
    for old, new in reversed(edits):
        assert back.count(new) == 1, ("undo", new[:60], back.count(new))
        back = back.replace(new, old)
    assert back == s, "undoing the edits does not give the input back"
    assert out.index(b"namespace ra412") < out.index(b"namespace Lzr0401"), "ra412 must be defined before the lazy release's block"
    open(sys.argv[2], "wb").write(out)
    print(f"bc5LleAgc.cpp {hashlib.md5(out).hexdigest()}")


if __name__ == "__main__":
    main()
