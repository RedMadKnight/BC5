#!/usr/bin/env python3
"""BC5 experiment 0412, tag cv412 (README section 69): K1r's covers are INVISIBLE to the host's "is it mapped?".
The defect (2026-11-13 11:32, ASTRO BOT's start on candidate 26ef195c with K1r on by default: a GPU fault at 3.8 s,
the ring reset failed, the box rebooted): the fault was a WRITE by the command processor (status 0x00640c41: client 6
of the kernel's gfxhub table, CPG; bit 18 set) at 0x3082f6000, under a read-only zero cover in the lazy view
"orbis_user_malloc". The unit asks one question, covered_sorted() over the device's mapping list, in 49 places: the
packet filter's operand check (a packet whose operand is unmapped is dropped), the soft CP, the probes. A cover is in
that list, so every one of them took never-written memory for the title's mapped memory: the filter let a packet
through that it used to drop, and the command processor wrote into a read-only page.
The rule: a cover exists for the GPU's own reads (shaders); for every decision of the host it is a hole, as that
memory was before K1r. So with K1r on the host behaves exactly as without it, and only the GPU's page tables differ.
  backend  SharedMap keeps `readonly`; Device::mappings() and sorted_mappings() report it (Mapping::readonly with
           Mapping::shared; before, a shared mapping was always reported writable)
  unit     covered_sorted(): a mapping that is shared and read-only (only K1r's covers are) does not cover
What this does not settle: that the filter drops a packet which writes into never-imported lazy memory was true
before K1r and is true again. It is a defect of its own (the title's write is lost), not a fault; registered in
FAULTS.md as open.
usage: mkcv0412.py unit <bc5LleAgc.cpp in (after mkk1r0412.py)> <out>
       mkcv0412.py backend <backend dir in (after mkk1r0412.py backend)> <backend dir out (may be the same)>"""
import hashlib
import os
import sys


def once(s, old, new, n=1):
    assert s.count(old) == n, ("an anchor does not occur the expected number of times", old[:70], s.count(old), n)
    return s.replace(old, new)


def unit(src, out):
    assert src != out
    s = open(src, "rb").read()
    assert b"\r" not in s and b"tag k1r412" in s and b"tag cv412" not in s
    a = (b"static bool covered_sorted(const std::vector<bc5::direct::Mapping>& maps, uint64_t a, uint64_t bytes) {\n"
         b"\tconst uint64_t end = a + bytes;\n\tuint64_t       pos = a;\n\tfor (int guard = 0; pos < end && guard < 64; guard++) {\n"
         b"\t\tauto it = std::upper_bound(maps.begin(), maps.end(), pos, [](uint64_t v, const bc5::direct::Mapping& m) { return v < m.va; });\n"
         b"\t\tif (it == maps.begin()) return false;\n\t\t--it;\n")
    s = once(s, a, a + b"\t\tif (it->shared && it->readonly) return false; // exp 0412 (tag cv412): a K1r cover is for the GPU's reads; for the host it is a hole, as before K1r\n")
    a = b"\t\t\tif (pos >= m.va && pos < m.va + m.size) { pos = m.va + m.size; hit = true; break; }\n"  # covered(), the unsorted form
    s = once(s, a, b"\t\t\tif (m.shared && m.readonly) continue; // exp 0412 (tag cv412): as in covered_sorted\n" + a)
    open(out, "wb").write(s)
    print(f"bc5LleAgc.cpp {hashlib.md5(s).hexdigest()}")


def backend(src, out):
    p = os.path.join(src, "src/direct.cpp")
    s = open(p, "rb").read()
    assert b"\r" not in s and b"map_shared_over" in s and b"tag cv412" not in s
    s = once(s, b"    std::uint32_t id = 0;\n    amdgpu_bo_handle bo = nullptr;\n};\n",
             b"    std::uint32_t id = 0;\n    amdgpu_bo_handle bo = nullptr;\n    bool readonly = false; // exp 0412 (tag cv412): mapped readable only (a K1r cover)\n};\n")
    s = once(s, b"SharedMap{gpu_va, size, bo_offset, id, b->bo}", b"SharedMap{gpu_va, size, bo_offset, id, b->bo, readonly}", 2)
    s = once(s, b"out.push_back({m.va, m.size, false, true});", b"out.push_back({m.va, m.size, m.readonly, true});")
    s = once(s, b"out->push_back({m.va, m.size, false, true});", b"out->push_back({m.va, m.size, m.readonly, true});")
    open(os.path.join(out, "src/direct.cpp"), "wb").write(s)
    print(f"src/direct.cpp {hashlib.md5(s).hexdigest()}")


def main():
    assert len(sys.argv) == 4 and sys.argv[1] in ("unit", "backend"), __doc__
    (unit if sys.argv[1] == "unit" else backend)(sys.argv[2], sys.argv[3])


if __name__ == "__main__":
    main()
