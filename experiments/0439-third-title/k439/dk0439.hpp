// SPDX-License-Identifier: GPL-2.0-only
// BC5 exp 0439 (tag dk439 arm; the top session's order of 11-23): the decisive test for the 8-px grid, one switch,
// BC5_0439_DCC_UNCOMPRESSED=1 (off unless "1"). The title's G-buffer ID targets are written with DCC (CB_COLORn_INFO
// DCC_ENABLE, 128-byte independent blocks) and read by compute through their metadata (V# COMPRESSION_EN, metadata =
// DCC_BASE; README, the 8-px grid). Under the switch the job copy of every GFX job has DCC_ENABLE cleared in each
// SET_CONTEXT_REG write of CB_COLORn_INFO, so the colour block writes plain bytes and leaves the keys alone, and each
// such target's keys (one byte per 256-byte block at DCC_BASE) are set to 0xff before the job: the code our own DCC
// decompress pass leaves (README item 39: 94.3 % 0xff after it). The reader keeps COMPRESSION_EN and finds every block
// uncompressed, which is the state a decompress would leave. If the grid goes, the texture path's decode of the
// compressed blocks is the cause; the faithful fix is chosen after (Mesa's GFX10 rule, the kernel's settings).
// Register offsets (context registers, dword index from 0xA000): CB_COLOR0_INFO 0x31c, ATTRIB2 0x3b0 + n, DCC_BASE 0x325
// + n*0xf, DCC_BASE_EXT 0x3a8 + n; INFO DCC_ENABLE bit 28, FORMAT [6:2] (tools/bc5-agc/regdb/gfx10.json).
// SET_CONTEXT_REG is PM4 type-3 opcode 0x69: dword 1 the first register's offset, then one value per register.
#pragma once

#include <cstddef>
#include <cstdint>
#include <span>

namespace bc5::dk439 {

struct Target {
    std::uint32_t info = 0, attrib2 = 0, dcc_lo = 0, dcc_ext = 0;
    bool attrib2_set = false, dcc_set = false;
    bool stripped = false; // DCC_ENABLE cleared in this job (the keys are to be set)
};

inline std::uint32_t bytes_per_element(std::uint32_t info) {
    switch ((info >> 2) & 0x1fu) { // CB ColorFormat
    case 1: return 1;                       // 8
    case 2: case 3: return 2;               // 16, 8_8
    case 4: case 5: case 6: case 7: case 8: case 9: case 10: return 4; // 32, 16_16, 10_11_11, 11_11_10, 10_10_10_2, 2_10_10_10, 8_8_8_8
    case 11: case 12: return 8;             // 32_32, 16_16_16_16
    case 14: return 16;                     // 32_32_32_32
    default: return 0;
    }
}

// The number of key bytes (one per 256-byte block) of a target, 0 when its size or format is unknown.
inline std::uint64_t key_bytes(const Target &t) {
    if (!t.attrib2_set) return 0;
    const std::uint64_t w = ((t.attrib2 >> 14) & 0x3fffu) + 1, h = (t.attrib2 & 0x3fffu) + 1;
    const std::uint32_t bpe = bytes_per_element(t.info);
    return bpe == 0 ? 0 : (w * h * bpe + 255) / 256;
}

inline std::uint64_t dcc_base(const Target &t) {
    return t.dcc_set ? ((static_cast<std::uint64_t>(t.dcc_lo) << 8) | (static_cast<std::uint64_t>(t.dcc_ext & 0xffu) << 40)) : 0;
}

// Walks one buffer (packets from its start): clears DCC_ENABLE in every SET_CONTEXT_REG value for CB_COLORn_INFO, and
// keeps the targets' ATTRIB2 and DCC_BASE as they are set. Returns the number of INFO values changed.
inline std::uint32_t strip(std::span<std::uint32_t> b, Target (&t)[8]) {
    std::uint32_t changed = 0;
    for (std::size_t i = 0; i < b.size();) {
        const std::uint32_t h = b[i], ty = h >> 30;
        std::size_t len = 1;
        if (ty == 3 || ty == 0) {
            const std::uint32_t c = (h >> 16) & 0x3fffu;
            len = c == 0x3fffu ? 1 : c + 2;
        }
        if (i + len > b.size()) break;
        if (ty == 3 && ((h >> 8) & 0xffu) == 0x69 && len >= 3) {
            const std::uint32_t first = b[i + 1] & 0xffffu;
            for (std::size_t k = 2; k < len; k++) {
                const std::uint32_t r = first + static_cast<std::uint32_t>(k - 2);
                std::uint32_t &v = b[i + k];
                if (r >= 0x318 && r < 0x318 + 8 * 0xf) {
                    const std::uint32_t n = (r - 0x318) / 0xf, o = (r - 0x318) % 0xf;
                    if (o == 4) { // INFO
                        if ((v >> 28) & 1u) {
                            v &= ~(1u << 28);
                            changed++;
                            t[n].stripped = true;
                        }
                        t[n].info = v;
                    } else if (o == 0xd) {
                        t[n].dcc_lo = v, t[n].dcc_set = true;
                    }
                } else if (r >= 0x3a8 && r < 0x3b0) {
                    t[r - 0x3a8].dcc_ext = v;
                } else if (r >= 0x3b0 && r < 0x3b8) {
                    t[r - 0x3b0].attrib2 = v, t[r - 0x3b0].attrib2_set = true;
                }
            }
        }
        i += len;
    }
    return changed;
}

} // namespace bc5::dk439
