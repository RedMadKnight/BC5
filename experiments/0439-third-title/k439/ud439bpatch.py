# BC5 exp 0439 (tag ud439b): after ud439patch.py on the private backend copy new/be/direct.cpp (run on the box, in k439/).
# ud439 named dropped register loads only; the one packet per frame dropped as "unmapped" in a late piece (the
# maintainer's session, top's question of 11-22 ~18:10) stayed unnamed. Now any packet the filter replaced whose memory
# operand is unmapped prints its opcode, the operand (address, bytes) and its first dwords, once per (piece size, dword)
# for the first 64 and then every 4096th, so a whole session names it without flooding. With BC5_0439_COPY_LAYOUT=1.
import sys

p = sys.argv[1] if len(sys.argv) > 1 else 'new/be/direct.cpp'
s = open(p, encoding='utf-8', newline='').read()
assert 'ud439b' not in s and 'tag ud439' in s
a = '''                    q += len;
                }
            }
        }
'''
assert s.count(a) == 1, s.count(a)
b = '''                    if (!load && ty == 3 && len >= 2 && dst[pc.off + q] != h && opt.mapped) { // exp 0439 (tag ud439b)
                        for (const auto &[oa, ob] : bc5::policy::memory_operands(&pc.src[q], static_cast<std::uint32_t>(len))) {
                            if (opt.mapped(oa, ob == 0 ? 4 : ob)) continue;
                            static std::atomic<std::uint64_t> n_ub {0};
                            const std::uint64_t kub = ++n_ub;
                            if (kub <= 64 || (kub & 0xfffu) == 0)
                                std::fprintf(stderr, "[bc5] exp 0439 (tag ud439b): slot %d piece %zu (%zu dwords) dword %zu: op 0x%x (%zu dwords) operand 0x%llx +%llu UNMAPPED, dropped (%llu so far): %08x %08x %08x %08x %08x %08x\\n", cur,
                                             static_cast<std::size_t>(&pc - &pieces[0]), pc.n, q, (h >> 8) & 0xffu, len, static_cast<unsigned long long>(oa), static_cast<unsigned long long>(ob),
                                             static_cast<unsigned long long>(kub), h, pc.src[q + 1], len > 2 ? pc.src[q + 2] : 0u, len > 3 ? pc.src[q + 3] : 0u, len > 4 ? pc.src[q + 4] : 0u, len > 5 ? pc.src[q + 5] : 0u);
                            break;
                        }
                    }
''' + a
s = s.replace(a, b)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('ud439b: patched', p)
