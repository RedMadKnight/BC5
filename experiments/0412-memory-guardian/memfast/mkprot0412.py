#!/usr/bin/env python3
"""BC5 experiment 0412, tag pr412 (README section 35): the title's protection bits reach the direct views.
Input: the main unit after mklock, mksect, mkgap, mkbuf, mkret, mkuse and mkzcat. Two places:
  - struct DView gets a last member `int prot = 0;` (every existing initialiser leaves it at 0);
  - direct_views_build(), direct memory: the callback's protection argument, ignored until now (an unnamed `int`),
    is named and stored in the view.
Nothing reads DView::prot except the use catcher's table (use0412.inc, BC5_GUARD_USE_STAT): no behaviour changes.
Each anchor occurs exactly once; the script undoes its edits and asserts that this gives the input back.
usage: mkprot0412.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import sys


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    s = open(sys.argv[1], "rb").read()
    assert b"namespace zc412" in s and b"tag pr412" not in s, "refused: not the expected input"
    edits = []
    a = b"\tbool        lazy;\n\tbool        eager;\n};\nstruct DBo {"
    edits.append((a, b"\tbool        lazy;\n\tbool        eager;\n\tint         prot = 0; // exp 0412 (tag pr412): the title's protection bits of the range (0x10 GPU read, 0x20 GPU write)\n};\nstruct DBo {"))
    a = (b"[](uint64_t start, uint64_t size, uint64_t offset, int type, int, const char* name, void* p) {\n"
         b"\t\t\tif (type == 0 && size != 0) static_cast<std::vector<DView>*>(p)->push_back({start, size, offset, name != nullptr ? name : \"\", direct_lazy_name(name), direct_eager_name(name)});\n")
    edits.append((a, (b"[](uint64_t start, uint64_t size, uint64_t offset, int type, int prot, const char* name, void* p) { // exp 0412 (tag pr412)\n"
                      b"\t\t\tif (type == 0 && size != 0) static_cast<std::vector<DView>*>(p)->push_back({start, size, offset, name != nullptr ? name : \"\", direct_lazy_name(name), direct_eager_name(name), prot});\n")))
    out = s
    for old, new in edits:
        assert out.count(old) == 1, ("an anchor does not occur exactly once", old[:60], out.count(old))
        out = out.replace(old, new)
    back = out
    for old, new in reversed(edits):
        assert back.count(new) == 1, ("undo", new[:60], back.count(new))
        back = back.replace(new, old)
    assert back == s, "undoing the edits does not give the input back"
    assert b"const int pr = v.prot;" in out and b"protection bits" in out, "use0412.inc of build g412r is not in the unit"
    open(sys.argv[2], "wb").write(out)
    print(f"bc5LleAgc.cpp {hashlib.md5(out).hexdigest()}")


if __name__ == "__main__":
    main()
