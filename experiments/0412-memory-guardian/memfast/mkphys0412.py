#!/usr/bin/env python3
"""BC5 experiment 0412, tag pm412 (README section 17): a check before PhysicalMemory's table is made searchable.
PhysicalMemory::m_mappings is an unsorted vector; Unmap takes the FIRST block, in insertion order, that matches one of
four cases. That is "the block that contains the range" only if no two blocks overlap in guest addresses, and nothing
in the class enforces it. A sorted table with a binary search is therefore the same behaviour only where that holds.
KYTY_BC5_PHYSMAP_CHECK=1 measures it on a real run: every block Map() adds is compared with the whole table (a linear
walk, so this switch is slow and for one diagnostic run only), overlapping ones are counted, the first eight are printed
on stderr, and a line with the counts comes at every power of two and every 100,000 inserts. Default off; with it off the
added block costs one static bool test. No behaviour changes either way.
Input: the unit mkmem0412.py made (KYTY_BC5_RANGES_FAST, 68c90f4b...). The anchor occurs exactly once; the script undoes
its edit and asserts that this gives the input back.
usage: mkphys0412.py [--any-input] <memory.cpp in> <memory.cpp out>"""
import hashlib
import sys

PIN = "68c90f4b7746cec114300e82fd0bc93a"
OLD = (b"\tmapping.gpu_mode       = gpu_mode;\n"
       b"\tm_mappings.push_back(mapping);\n")
NEW = (b"\tmapping.gpu_mode       = gpu_mode;\n"
       b"\t{ // Experiment 0412 (tag pm412, mkphys0412.py): KYTY_BC5_PHYSMAP_CHECK=1 counts the blocks that overlap one already in the table\n"
       b"\t\tstatic const bool check412 = [] {\n"
       b"\t\t\tconst char* e = std::getenv(\"KYTY_BC5_PHYSMAP_CHECK\");\n"
       b"\t\t\treturn e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);\n"
       b"\t\t}();\n"
       b"\t\tif (check412) {\n"
       b"\t\t\tstatic uint64_t inserts412 = 0, overlaps412 = 0;\n"
       b"\t\t\tinserts412++;\n"
       b"\t\t\tfor (const auto& b412: m_mappings) {\n"
       b"\t\t\t\tif (VirtualRangesOverlap(mapping.map_vaddr, mapping.map_size, b412.map_vaddr, b412.map_size)) {\n"
       b"\t\t\t\t\tif (overlaps412++ < 8) {\n"
       b"\t\t\t\t\t\tstd::fprintf(stderr, \"[bc5] exp 0412 physmap check: new block 0x%\" PRIx64 \"+0x%\" PRIx64 \" overlaps 0x%\" PRIx64 \"+0x%\" PRIx64 \"\\n\",\n"
       b"\t\t\t\t\t\t             mapping.map_vaddr, mapping.map_size, b412.map_vaddr, b412.map_size);\n"
       b"\t\t\t\t\t}\n"
       b"\t\t\t\t\tbreak;\n"
       b"\t\t\t\t}\n"
       b"\t\t\t}\n"
       b"\t\t\tif ((inserts412 & (inserts412 - 1)) == 0 || inserts412 % 100000 == 0) {\n"
       b"\t\t\t\tstd::fprintf(stderr, \"[bc5] exp 0412 physmap check: %\" PRIu64 \" blocks added, %\" PRIu64 \" overlapped an existing one, table %zu (tag pm412)\\n\",\n"
       b"\t\t\t\t             inserts412, overlaps412, m_mappings.size());\n"
       b"\t\t\t}\n"
       b"\t\t}\n"
       b"\t}\n"
       b"\tm_mappings.push_back(mapping);\n")


def main():
    args = [a for a in sys.argv[1:] if a != "--any-input"]
    any_input = len(args) != len(sys.argv[1:])
    assert len(args) == 2 and args[0] != args[1], __doc__
    s = open(args[0], "rb").read()
    if not any_input:
        assert hashlib.md5(s).hexdigest() == PIN, ("refused: not the pinned input", hashlib.md5(s).hexdigest())
    assert b"pm412" not in s and b"KYTY_BC5_PHYSMAP_CHECK" not in s, "refused: the unit has the edit already"
    assert b"\r" not in s and s.count(OLD) == 1, ("the anchor does not occur exactly once", s.count(OLD))
    bal = lambda b: (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"))
    assert bal(OLD) == bal(NEW), "the edit changes the balance"
    NEW.decode("ascii")
    for need in (b"PRIx64", b"std::fprintf", b"std::getenv", b"VirtualRangesOverlap("):
        assert need in s, ("the unit does not use this yet", need)
    out = s.replace(OLD, NEW)
    assert out.count(NEW) == 1 and out.replace(NEW, OLD) == s, "undoing the edit does not give the input back"
    open(args[1], "wb").write(out)
    print(f"src/kernel/memory.cpp {hashlib.md5(out).hexdigest()}")


if __name__ == "__main__":
    main()
