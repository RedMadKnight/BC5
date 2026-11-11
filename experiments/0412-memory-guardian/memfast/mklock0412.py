#!/usr/bin/env python3
"""BC5 experiment 0412, tag lk412 (README section 20): the device mutex counts who holds it.
Input: build g412d's main unit bc5LleAgc.cpp (5361c8ba...). One place: the declaration of g_dev_mutex becomes
lock0412.inc's lk412::Mutex (the text lock0412.cpp tests), printing through journal(). The unit's three lock sites
(std::lock_guard with class template argument deduction) need no change. BC5_GUARD_LOCK_STAT=1 turns the counting on;
unset, empty and "0" leave a std::mutex behind one test of a constant.
The anchor occurs exactly once; the script undoes its edit and asserts that this gives the input back.
usage: mklock0412.py [--any-input] <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import os
import sys

PIN = "5361c8baac7690e5167e89a27cc7b4c7"
HERE = os.path.dirname(os.path.abspath(__file__))
A = b"static std::mutex                           g_dev_mutex;\n"
HEAD = b"// Experiment 0412 (tag lk412): BC5_GUARD_LOCK_STAT, the device mutex with per-thread hold and wait counters.\n#define LK412_PRINT journal\n#define LK412_NOW timing_now\n"
TAIL = b"static lk412::Mutex                         g_dev_mutex;\n"


def main():
    args = [a for a in sys.argv[1:] if a != "--any-input"]
    any_input = len(args) != len(sys.argv[1:])
    assert len(args) == 2 and args[0] != args[1], __doc__
    s = open(args[0], "rb").read()
    inc = open(os.path.join(HERE, "lock0412.inc"), "rb").read()
    if not any_input:
        assert hashlib.md5(s).hexdigest() == PIN, ("refused: not the pinned input", hashlib.md5(s).hexdigest())
    assert b"lk412" not in s and b"BC5_GUARD_LOCK_STAT" not in s, "refused: the unit has the edit already"
    assert b"\r" not in s and b"\r" not in inc
    inc.decode("ascii")
    assert s.count(A) == 1, ("the anchor does not occur exactly once", s.count(A))
    assert s.count(b"g_dev_mutex)") == 3 and s.count(b"std::lock_guard lock(g_dev_mutex);") == 3, "the lock sites are not the three known ones"
    assert s.index(b"static void journal(const char* fmt, ...) __attribute__") < s.index(A), "journal() is not declared before the mutex"
    assert s.index(b"static double timing_now();") < s.index(A), "timing_now() is not declared before the mutex"
    new = HEAD + inc + TAIL
    out = s.replace(A, new)
    assert out.count(new) == 1 and out.replace(new, A) == s, "undoing the edit does not give the input back"
    open(args[1], "wb").write(out)
    print(f"bc5LleAgc.cpp {hashlib.md5(out).hexdigest()}")


if __name__ == "__main__":
    main()
