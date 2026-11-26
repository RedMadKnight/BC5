# BC5 exp 0439 (tag ud439): patch the private backend copy new/be/direct.cpp after pw439patch.py and cl439patch.py (run
# on the box, in k439/). With BC5_0439_COPY_LAYOUT=1, a piece of a job of 30 or more pieces whose filter dropped
# packets for an unmapped operand, by a root offset, or as a register-destination WRITE_DATA prints one line: the job's
# slot, the piece's index, guest address and dwords, and the counts. A LOAD_SH_REG(_INDEX) whose table is unmapped at the
# submission is dropped with every register in it (exp 0441's question: can a title's 0x218 write be lost in a piece).
import sys

p = sys.argv[1] if len(sys.argv) > 1 else 'new/be/direct.cpp'
s = open(p, encoding='utf-8', newline='').read()
a = '''        { // exp 0439 (tag pw439): piece waits dropped as unsatisfiable, root-list hits in pieces
'''
b = '''        { // exp 0439 (tag ud439)
            static const bool ud439 = [] {
                const char *e = std::getenv("BC5_0439_COPY_LAYOUT");
                return e != nullptr && e[0] == '1' && e[1] == 0;
            }();
            if (ud439 && pieces.size() >= 30 && (st.unmapped_drops != 0 || st.offset_drops != 0 || st.reg_write_drops != 0))
                std::fprintf(stderr, "[bc5] exp 0439 (tag ud439): slot %d piece %zu of %zu (0x%llx, %zu dwords): dropped %llu unmapped, %llu by a root offset, %llu register writes\\n",
                             cur, static_cast<std::size_t>(&pc - &pieces[0]), pieces.size(), static_cast<unsigned long long>(reinterpret_cast<std::uint64_t>(pc.src)), pc.n,
                             static_cast<unsigned long long>(st.unmapped_drops), static_cast<unsigned long long>(st.offset_drops), static_cast<unsigned long long>(st.reg_write_drops));
            // each dropped register load: its dword, table address and count (the filter's reason for an unmapped
            // operand: "dropped instead of faulting the GPU", policy.hpp FilterOptions::mapped; LOAD_SH/CONTEXT/
            // UCONFIG_REG's operand is checked as 4096 bytes from the base, the _INDEX forms as count * 4 + 4)
            if (ud439 && pieces.size() >= 30 && st.unmapped_drops + st.offset_drops != 0) {
                for (std::size_t q = 0; q < pc.n;) {
                    const std::uint32_t h = pc.src[q], ty = h >> 30;
                    std::size_t len = 1;
                    if (ty == 3 || ty == 0) {
                        const std::uint32_t c = (h >> 16) & 0x3fffu;
                        len = c == 0x3fffu ? 1 : c + 2;
                    }
                    if (q + len > pc.n) break;
                    const std::uint32_t op = (h >> 8) & 0xffu;
                    const bool load = ty == 3 && (op == 0x5e || op == 0x5f || op == 0x61 || op == 0x63 || op == 0x64 || op == 0x9f);
                    if (load && len >= 3 && dst[pc.off + q] != h) { // the filter replaced it (a drop is NOP-ed)
                        const std::uint64_t ta = (pc.src[q + 1] & ~3ull) | (static_cast<std::uint64_t>(pc.src[q + 2] & 0xffffu) << 32);
                        const std::uint32_t cnt = len >= 5 ? (pc.src[q + 4] & 0x3fffu) : 0;
                        std::fprintf(stderr, "[bc5] exp 0439 (tag ud439): slot %d piece %zu dword %zu: LOAD op 0x%x table 0x%llx count %u (%zu dwords) DROPPED (%s)\\n", cur,
                                     static_cast<std::size_t>(&pc - &pieces[0]), q, op, static_cast<unsigned long long>(ta), cnt, len,
                                     opt.mapped && !opt.mapped(ta, (op == 0x63 || op == 0x64 || op == 0x9f) ? cnt * 4ull + 4 : 4096) ? "operand unmapped" : "root offset or other");
                    }
                    q += len;
                }
            }
        }
''' + a
assert s.count(a) == 1, s.count(a)
s = s.replace(a, b)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('ud439: patched', p)
