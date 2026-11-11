#!/usr/bin/env python3
"""BC5 experiment 0412, tag us412 (README section 32): the use catcher's stamps in the main unit.
Input: the main unit after mklock, mksect, mkgap, mkbuf and mkret. use0412.inc goes in before ret0412.inc's block, and:
  - submit_now: us412::begin() where the submission's options are prepared, and us412::touch(a, bytes) as the first
    statement of the `opt.mapped` callback (the filter asks it about every memory operand);
  - direct_sync_one: us412::report(S.label, views) once the views are known.
BC5_GUARD_USE_STAT unset: each is one test of a constant; the callback returns exactly what it returned before.
Each anchor occurs exactly once; the script undoes its edits and asserts that this gives the input back.
usage: mkuse0412.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
T = b" // exp 0412 (tag us412)\n"


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    s = open(sys.argv[1], "rb").read()
    inc = open(os.path.join(HERE, "use0412.inc"), "rb").read()
    assert b"namespace ra412" in s and b"namespace us412" not in s, "refused: not the expected input"
    assert b"\r" not in s and b"\r" not in inc
    inc.decode("ascii")
    edits = []
    a = b"// Experiment 0412 (tag ra412): BC5_GUARD_RETURN_EXEMPT, the return-aware orphan release.\n"
    edits.append((a, b"// Experiment 0412 (tag us412): BC5_GUARD_USE_STAT, the guest memory that command buffers name.\n#define US412_PRINT journal\n#define US412_NOW timing_now\n" + inc + a))
    a = b"\topt.mapped = [&maps_p, fl_area](uint64_t a, uint64_t bytes) {\n"
    edits.append((a, b"\tus412::begin();" + T + a + b"\t\tus412::touch(a, bytes);" + T))
    a = b"\tconst std::vector<DView>& views  = views_p->v;\n"
    edits.append((a, a + b"\tus412::report(S.label, views);" + T))
    out = s
    for old, new in edits:
        assert out.count(old) == 1, ("an anchor does not occur exactly once", old[:60], out.count(old))
        out = out.replace(old, new)
    back = out
    for old, new in reversed(edits):
        assert back.count(new) == 1, ("undo", new[:60], back.count(new))
        back = back.replace(new, old)
    assert back == s, "undoing the edits does not give the input back"
    for need in (b"<unordered_map>", b"<algorithm>", b"<map>"):
        assert need in out
    open(sys.argv[2], "wb").write(out)
    print(f"bc5LleAgc.cpp {hashlib.md5(out).hexdigest()}")


if __name__ == "__main__":
    main()
