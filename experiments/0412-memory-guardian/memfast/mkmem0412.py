#!/usr/bin/env python3
"""BC5 experiment 0412, tag mf412 (README section 15): the first fix of the host's memory bookkeeping, as one edit of the
e11-based line's src/kernel/memory.cpp (exp 0401 e8's x5-jit, ee24c888...).
VirtualRanges::QuerySpan walked m_ranges from its first element on every call. The table is sorted by start and holds
about 28,000 ranges of 72 bytes while the second title streams, and the title's AMM map and unmap commands call it for
every 16 KiB page: the stack samples of 2026-11-11 found the game thread in it for 16 % of the load phases.
With KYTY_BC5_RANGES_FAST=1 the walk starts at the range that holds `start` (std::upper_bound, as the class's own
Overlapping() does); the loop body is unchanged, so the result is the same. Default off (unset, empty and "0").
The anchor occurs exactly once; the script undoes its edit and asserts that this gives the input back.
CPU test: memfast0412.cpp (the old and the new walk on random tables).
usage: mkmem0412.py [--any-input] <memory.cpp in> <memory.cpp out>"""
import hashlib
import sys

PIN = "ee24c888f976cc125502cf3a31006349"
OLD = (b"\t\tconst auto end     = start + size;\n"
       b"\t\tauto       current = start;\n"
       b"\t\tfor (const auto& range: m_ranges) {\n"
       b"\t\t\tconst auto range_end = End(range.start, range.size);\n"
       b"\t\t\tif (range_end <= current) {\n")
NEW = (b"\t\tconst auto end     = start + size;\n"
       b"\t\tauto       current = start;\n"
       b"\t\t// Experiment 0412 (tag mf412, mkmem0412.py): KYTY_BC5_RANGES_FAST=1 starts the walk at the range that holds `start`\n"
       b"\t\t// instead of at the table's first element (28,000 ranges while the second title streams). The ranges are sorted\n"
       b"\t\t// by start and do not overlap, so every range before that one ends at or before `start` and the loop below skipped it.\n"
       b"\t\tstatic const bool fast412 = [] {\n"
       b"\t\t\tconst char* e = std::getenv(\"KYTY_BC5_RANGES_FAST\");\n"
       b"\t\t\treturn e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);\n"
       b"\t\t}();\n"
       b"\t\tauto first412 = m_ranges.begin();\n"
       b"\t\tif (fast412) {\n"
       b"\t\t\tfirst412 = std::upper_bound(m_ranges.begin(), m_ranges.end(), start, [](uint64_t v, const Range& r) { return v < r.start; });\n"
       b"\t\t\tif (first412 != m_ranges.begin()) --first412;\n"
       b"\t\t}\n"
       b"\t\tfor (auto it412 = first412; it412 != m_ranges.end(); ++it412) {\n"
       b"\t\t\tconst auto& range     = *it412;\n"
       b"\t\t\tconst auto  range_end = End(range.start, range.size);\n"
       b"\t\t\tif (range_end <= current) {\n")


def main():
    args = [a for a in sys.argv[1:] if a != "--any-input"]
    any_input = len(args) != len(sys.argv[1:])
    assert len(args) == 2 and args[0] != args[1], __doc__
    s = open(args[0], "rb").read()
    if not any_input:
        assert hashlib.md5(s).hexdigest() == PIN, ("refused: not the pinned input", hashlib.md5(s).hexdigest())
    assert b"mf412" not in s and b"KYTY_BC5_RANGES_FAST" not in s, "refused: the unit has the edit already"
    assert b"\r" not in s and s.count(OLD) == 1, ("the anchor does not occur exactly once", s.count(OLD))
    bal = lambda b: (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"))
    assert bal(OLD) == bal(NEW), "the edit changes the balance"
    NEW.decode("ascii")
    out = s.replace(OLD, NEW)
    assert out.count(NEW) == 1 and out.replace(NEW, OLD) == s, "undoing the edit does not give the input back"
    assert b"std::getenv" in s, "the unit does not use std::getenv yet (an include would be missing)"
    open(args[1], "wb").write(out)
    print(f"src/kernel/memory.cpp {hashlib.md5(out).hexdigest()}")


if __name__ == "__main__":
    main()
