#!/usr/bin/env python3
"""BC5 experiment 0412 (README section 68): the two defaults for the shared build, as the top ordered after the
tests of 2026-11-13: K1r ON and the fault record ON unless the variable says 0. Everything else stays as it is
(rl412 off, the replace form off, the probe and the watch compiled in and off).
  BC5_GUARD_K1R      unset or anything but "0": on;  "0": off
  BC5_FAULT_RECORD   unset or anything but "0": on;  "0": off
Input: the main unit after the whole chain (nl, rl, k1r, fr, wa, pr, ff). Two edits, each anchor exactly once.
usage: mkdef0412.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import sys


def flip(s, name):
    old = (b'\t\tconst char* e = std::getenv("' + name + b'");\n'
           b"\t\treturn e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);\n")
    new = (b'\t\tconst char* e = std::getenv("' + name + b'");\n'
           b"\t\treturn e == nullptr || !(e[0] == '0' && e[1] == 0); // exp 0412 (mkdef0412.py): on by default, \"0\" turns it off\n")
    assert s.count(old) == 1, ("the switch does not occur exactly once", name, s.count(old))
    return s.replace(old, new)


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    s = open(sys.argv[1], "rb").read()
    assert b"\r" not in s and b"tag k1r412" in s and b"tag fr412" in s and b"mkdef0412.py" not in s
    s = flip(s, b"BC5_GUARD_K1R")
    s = flip(s, b"BC5_FAULT_RECORD")
    open(sys.argv[2], "wb").write(s)
    print(f"bc5LleAgc.cpp {hashlib.md5(s).hexdigest()}")


if __name__ == "__main__":
    main()
