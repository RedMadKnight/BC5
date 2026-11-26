// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0439 (tag fa439): a testable copy of patch 0001's flat_aperture_fix scan (experiment 0190, F249), for
// the third title's cloth traversal (README items 46-47). The scan and the rewrite are the patch's, unchanged; only the
// code-area access and the journal are left out, so the det test can feed it synthetic programs.
//
// A BVH traversal pushes its per-lane stack with FLAT stores whose address high dword is
// v_med3_u32 vD, sN, 0x70000000, <packed stack pointer>, sN made by s_brev_b32 sN, 1 (0x80000000): the console's LDS and
// private apertures. amdgpu's graphics VMIDs use 0x2000'... (LDS) and 0x1000'... (private) (Linux gmc_v10_0.c
// gmc_v10_0_early_init; exp 0190 read src_shared_base / src_private_base on the box), so a push leaves both apertures.
// The rewrite: the literal 0x70000000 becomes 0x10000000 and the brev operand 1 becomes 4 (0x20000000).
// Encodings (llvm-mc -triple=amdgcn -mcpu=gfx1013 -show-encoding): v_med3_u32 VOP3 0xD559xxxx with src1 = literal (0xff);
// s_brev_b32 sN, 1 = 0xBE800B81 | N << 16, with 4 = 0xBE800B84 | N << 16; s_endpgm 0xBF810000.
#pragma once

#include <cstdint>

namespace bc5::fa439 {

struct Result {
    std::uint32_t sites = 0; // med3 literals rewritten
    std::uint32_t brevs = 0; // s_brev_b32 operands rewritten
};

// w: the program's dwords, n: how many are readable. Rewrites in place up to the first s_endpgm.
inline Result rewrite(std::uint32_t *w, std::uint32_t n) {
    Result r;
    std::uint32_t end = 0;
    while (end < n && w[end] != 0xBF810000u) end++;
    for (std::uint32_t k = 0; k + 2 < end; k++) {
        const std::uint32_t d0 = w[k], d1 = w[k + 1], s = d1 & 0x1ffu;
        if ((d0 & 0xffffff00u) != 0xD5590000u || ((d1 >> 9u) & 0x1ffu) != 0xffu || w[k + 2] != 0x70000000u || s > 105u) continue;
        std::uint32_t at = 0;
        for (std::uint32_t j = k; j-- > 0 && k - j <= 1024u;) {
            if (w[j] == (0xBE800B81u | (s << 16u)) || w[j] == (0xBE800B84u | (s << 16u))) {
                at = j + 1;
                break;
            }
        }
        if (at == 0) continue;
#if !defined(BC5_FA439_PLANT_BREV) // the planted bug: the brev left at 0x80000000 (LDS pushes still lost)
        if (w[at - 1] != (0xBE800B84u | (s << 16u))) {
            w[at - 1] = 0xBE800B84u | (s << 16u);
            r.brevs++;
        }
#endif
        w[k + 2] = 0x10000000u;
        r.sites++;
#if !defined(BC5_FA439_PLANT_SKIP) // the planted bug: every second push missed
        k += 2;
#else
        k += 5;
#endif
    }
    return r;
}

} // namespace bc5::fa439
