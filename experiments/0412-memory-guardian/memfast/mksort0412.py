#!/usr/bin/env python3
"""BC5 experiment 0412, tag ps412 (README section 18): PhysicalMemory's mapping table searched by address.
Input: the e11-based line's src/kernel/memory.cpp after mkmem0412.py and mkphys0412.py (72bcd493...). Six places:
  1. before `class PhysicalMemory`: physmap0412.inc (namespace pm412, the text physmap0412.cpp tests) and the switch;
  2. Map(): the new block goes to its place by address (pm412::insert); a block that overlaps another, is empty or
     wraps ends the sorted mode for the rest of the run (one line on stderr) and is appended as before;
  3. Unmap(): the block is found by binary search and edited by the old statements (pm412::unmap); "is the host
     mapping still used" looks only at the blocks inside that host range. An empty range, and in verify mode a call
     where the old search finds another block, take the old walk; the table is sorted again afterwards;
  4. Find(vaddr): binary search;
  5. SetVirtualRangeName(), 6. SetVirtualRangeMemoryType(): only the blocks around the range, the same overlap test.
ProtectMapping() rebuilds the table in order and needs no change.
KYTY_BC5_PHYSMAP_SORTED=1 turns it on, =verify also runs the old search in Unmap and counts differences; unset, empty
and "0" are off, and then the six places run the old statements. The sorted table is the old behaviour exactly while
no two blocks overlap (README section 17: none in 32,768 inserts on the maintainer's save; insert() enforces it).
Every anchor occurs exactly once; the script undoes its edits and asserts that this gives the input back.
usage: mksort0412.py [--any-input] <memory.cpp in> <memory.cpp out>"""
import hashlib
import os
import sys

PIN = "72bcd493cc28ec602fe12c9ca638c365"
HERE = os.path.dirname(os.path.abspath(__file__))

SWITCH = b'''
// Experiment 0412 (tag ps412): KYTY_BC5_PHYSMAP_SORTED. 0 off, 1 on, 2 verify. g_pm412_ok: no overlapping block was ever added.
static int Pm412Mode() {
	static const int mode = [] {
		const char* e = std::getenv("KYTY_BC5_PHYSMAP_SORTED");
		if (e == nullptr || e[0] == 0 || (e[0] == '0' && e[1] == 0)) return 0;
		const int m = std::strcmp(e, "verify") == 0 ? 2 : std::strcmp(e, "1") == 0 ? 1 : 0;
		std::fprintf(stderr, "[bc5] exp 0412 physmap sorted: %s (tag ps412)\\n", m == 2 ? "verify" : m == 1 ? "on" : "value not understood, off");
		return m;
	}();
	return mode;
}
static bool     g_pm412_ok       = true;
static uint64_t g_pm412_mismatch = 0;

'''

A_CLASS = b"class PhysicalMemory {\n"
A_MAP = b"\tm_mappings.push_back(mapping);\n"
N_MAP = (b"\tif (Pm412Mode() != 0 && g_pm412_ok) { // exp 0412 (tag ps412): the table stays sorted by guest address\n"
         b"\t\tif (!pm412::insert(m_mappings, mapping)) {\n"
         b"\t\t\tg_pm412_ok = false;\n"
         b"\t\t\tstd::fprintf(stderr, \"[bc5] exp 0412 physmap sorted: block 0x%\" PRIx64 \"+0x%\" PRIx64 \" overlaps another, is empty or wraps: the old table code from here on (tag ps412)\\n\",\n"
         b"\t\t\t             mapping.map_vaddr, mapping.map_size);\n"
         b"\t\t\tm_mappings.push_back(mapping);\n"
         b"\t\t}\n"
         b"\t} else {\n"
         b"\t\tm_mappings.push_back(mapping);\n"
         b"\t}\n")
A_UNMAP = b"\tsize_t index = 0;\n\tfor (auto& b: m_mappings) {\n\t\tif (b.map_vaddr == vaddr && b.map_size == size) {\n"
N_UNMAP = (b"\t// Experiment 0412 (tag ps412): the old walk below can append the right half of a split block; when it runs in the\n"
           b"\t// sorted mode (an empty range, or a verify difference) the table is sorted again on the way out.\n"
           b"\tstruct Pm412Resort {\n"
           b"\t\tstd::vector<AllocatedBlock>* v = nullptr;\n"
           b"\t\t~Pm412Resort() {\n"
           b"\t\t\tif (v != nullptr) {\n"
           b"\t\t\t\tstd::stable_sort(v->begin(), v->end(), [](const AllocatedBlock& x, const AllocatedBlock& y) { return x.map_vaddr < y.map_vaddr; });\n"
           b"\t\t\t}\n"
           b"\t\t}\n"
           b"\t} resort412;\n"
           b"\tif (Pm412Mode() != 0 && g_pm412_ok) {\n"
           b"\t\tbool fast412 = size != 0;\n"
           b"\t\tif (fast412 && Pm412Mode() == 2 && pm412::linear_first(m_mappings, vaddr, size) != pm412::candidate(m_mappings, vaddr, size)) {\n"
           b"\t\t\tfast412 = false;\n"
           b"\t\t\tif (g_pm412_mismatch++ < 8) {\n"
           b"\t\t\t\tstd::fprintf(stderr, \"[bc5] exp 0412 physmap sorted: verify: Unmap 0x%\" PRIx64 \"+0x%\" PRIx64 \": the old search finds another block (tag ps412)\\n\", vaddr, size);\n"
           b"\t\t\t}\n"
           b"\t\t}\n"
           b"\t\tif (fast412) {\n"
           b"\t\t\tuint64_t         hv412 = 0, hs412 = 0;\n"
           b"\t\t\tconst pm412::Hit hit412 = pm412::unmap(m_mappings, vaddr, size, gpu_mode, &hv412, &hs412);\n"
           b"\t\t\tif (hit412 == pm412::Whole && host_vaddr_to_release != nullptr && hv412 != 0 && hs412 != 0 && !pm412::host_still_mapped(m_mappings, hv412, hs412)) {\n"
           b"\t\t\t\t*host_vaddr_to_release = hv412;\n"
           b"\t\t\t}\n"
           b"\t\t\treturn hit412 != pm412::None;\n"
           b"\t\t}\n"
           b"\t\tresort412.v = &m_mappings;\n"
           b"\t}\n")
A_FIND = (b"\treturn std::any_of(m_mappings.begin(), m_mappings.end(),\n"
          b"\t                   [vaddr, base_addr, len, prot, mode, gpu_mode](auto& b) {\n")
N_FIND = (b"\tif (Pm412Mode() != 0 && g_pm412_ok) { // exp 0412 (tag ps412): the block that holds vaddr, by binary search\n"
          b"\t\tconst auto it412 = pm412::containing(m_mappings, vaddr);\n"
          b"\t\tif (it412 == m_mappings.end()) {\n"
          b"\t\t\treturn false;\n"
          b"\t\t}\n"
          b"\t\tif (base_addr != nullptr) *base_addr = it412->map_vaddr;\n"
          b"\t\tif (len != nullptr) *len = it412->map_size;\n"
          b"\t\tif (prot != nullptr) *prot = it412->prot;\n"
          b"\t\tif (mode != nullptr) *mode = it412->mode;\n"
          b"\t\tif (gpu_mode != nullptr) *gpu_mode = it412->gpu_mode;\n"
          b"\t\treturn true;\n"
          b"\t}\n")
A_NAME = b"void PhysicalMemory::SetVirtualRangeName(uint64_t vaddr, uint64_t len, const char* name) {\n\tCommon::LockGuard lock(m_mutex);\n\n"
A_TYPE = b"void PhysicalMemory::SetVirtualRangeMemoryType(uint64_t vaddr, uint64_t len, int memory_type) {\n\tCommon::LockGuard lock(m_mutex);\n\n"


def walk(stmt):
    return (b"\tif (Pm412Mode() != 0 && g_pm412_ok) { // exp 0412 (tag ps412): only the blocks around the range, the same overlap test\n"
            b"\t\tfor (auto it412 = pm412::walk_from(m_mappings, vaddr); it412 != m_mappings.end(); ++it412) {\n"
            b"\t\t\tif (it412->map_vaddr > vaddr && it412->map_vaddr - vaddr >= len) break;\n"
            b"\t\t\tif (VirtualRangesOverlap(vaddr, len, it412->map_vaddr, it412->map_size)) " + stmt + b"\n"
            b"\t\t}\n"
            b"\t\treturn;\n"
            b"\t}\n")


def main():
    args = [a for a in sys.argv[1:] if a != "--any-input"]
    any_input = len(args) != len(sys.argv[1:])
    assert len(args) == 2 and args[0] != args[1], __doc__
    s = open(args[0], "rb").read()
    inc = open(os.path.join(HERE, "physmap0412.inc"), "rb").read()
    if not any_input:
        assert hashlib.md5(s).hexdigest() == PIN, ("refused: not the pinned input", hashlib.md5(s).hexdigest())
    assert b"tag ps412" not in s and b"KYTY_BC5_PHYSMAP_SORTED" not in s and b"Pm412Mode" not in s, "refused: the unit has the edit already"
    assert b"\r" not in s and b"\r" not in inc
    inc.decode("ascii")
    edits = [("the helpers", A_CLASS, inc + SWITCH + A_CLASS),
             ("Map", A_MAP, N_MAP),
             ("Unmap", A_UNMAP, N_UNMAP + A_UNMAP),
             ("Find", A_FIND, N_FIND + A_FIND),
             ("SetVirtualRangeName", A_NAME, A_NAME + walk(b"CopyVirtualRangeName(it412->name, name);")),
             ("SetVirtualRangeMemoryType", A_TYPE, A_TYPE + walk(b"it412->memory_type = memory_type;"))]
    bal = lambda b: (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"))
    out, at, done = s, -1, []
    for name, old, new in edits:
        assert out.count(old) == 1, ("an anchor does not occur exactly once", name, out.count(old))
        if name != "the helpers":  # physmap0412.inc has half-open ranges in its comments; physmap0412.cpp's compile checks its syntax
            assert bal(old) == bal(new), ("the edit changes the balance", name)
        new.decode("ascii")
        pos = out.index(old)
        assert pos > at, ("the edits are not in file order", name)
        at = pos + len(new) - len(old)
        out = out.replace(old, new)
        done.append((name, old, new))
    back = out
    for name, old, new in reversed(done):
        assert back.count(new) == 1, ("undo", name)
        back = back.replace(new, old)
    assert back == s, "undoing the edits does not give the input back"
    for need in (b"std::stable_sort", b"<algorithm>", b"<cstring>"):
        assert need in out
    open(args[1], "wb").write(out)
    print(f"src/kernel/memory.cpp {hashlib.md5(out).hexdigest()}")


if __name__ == "__main__":
    main()
