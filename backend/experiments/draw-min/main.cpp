// SPDX-License-Identifier: GPL-2.0-only
// draw-min: the smallest known-good draw on gfx10 — libdrm's amdgpu_test "memset draw"
// (RectPosTexFast VS + constant PS, one DRAW_INDEX_AUTO of 3 vertices into a 32x32 target) —
// pushed through the very submission path of the track-B direct mode: anonymous CPU memory
// mapped 1:1 as userptr BOs, the policy filter, the scratch IB, the GFX ring fence.
// Phase-3 task 2 ("clear, then one triangle") and the control for experiment 0016 run 63,
// where the game's draws leave no pixel while its clears and compute run.
//
//   draw-min --submit [--render-node PATH] [--raw-filter-off]
//
// Hard rule 5 (CLAUDE.md): --submit runs on the GPU; never in tests or CI.
//
// The shader binaries, the preamble/cached register blocks and the packet sequence are taken
// from libdrm 2.4.120 tests/amdgpu/shader_code_gfx10.h and shader_test_util.c
// (Copyright 2022 Advanced Micro Devices, Inc., MIT licence — see the notice below).
#include "bc5/direct.hpp"
#include "bc5/policy.hpp"

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <string_view>
#include <vector>
#ifdef BC5_WITH_AMDGPU
#include <sys/mman.h>
#endif

namespace {

/* MIT notice for the arrays and the sequence below (libdrm tests/amdgpu):
 * Copyright 2022 Advanced Micro Devices, Inc.
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software
 * and associated documentation files (the "Software"), to deal in the Software without
 * restriction, including without limitation the rights to use, copy, modify, merge, publish,
 * distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the
 * Software is furnished to do so, subject to the following conditions: The above copyright
 * notice and this permission notice shall be included in all copies or substantial portions of
 * the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND. */

const std::uint32_t kPsConst[] = {0x7E000200, 0x7E020201, 0x7E040202, 0x7E060203, 0x5E000300, 0x5E020702,
                                  0xBF800000, 0xBF800000, 0xF8001C0F, 0x00000100, 0xBF810000};
// patch code per export format (10 variants of 6 dwords at dword offset 4 of the shader)
const std::uint32_t kPsConstPatch[10][6] = {
    {0xBF800000, 0xBF800000, 0xBF800000, 0xBF800000, 0xF8001890, 0x00000000},
    {0xBF800000, 0xBF800000, 0xBF800000, 0xBF800000, 0xF8001801, 0x00000000},
    {0xBF800000, 0xBF800000, 0xBF800000, 0xBF800000, 0xF8001803, 0x00000100},
    {0xBF800000, 0xBF800000, 0xBF800000, 0xBF800000, 0xF8001803, 0x00000300},
    {0x5E000300, 0x5E020702, 0xBF800000, 0xBF800000, 0xF8001C0F, 0x00000100},
    {0xD7690000, 0x00020300, 0xD7690001, 0x00020702, 0xF8001C0F, 0x00000100},
    {0xD7680000, 0x00020300, 0xD7680001, 0x00020702, 0xF8001C0F, 0x00000100},
    {0xD76A0000, 0x00020300, 0xD76A0001, 0x00020702, 0xF8001C0F, 0x00000100},
    {0xD76B0000, 0x00020300, 0xD76B0001, 0x00020702, 0xF8001C0F, 0x00000100},
    {0xBF800000, 0xBF800000, 0xBF800000, 0xBF800000, 0xF800180F, 0x03020100}};
const std::uint32_t kVsRectPosTexFast[] = {
    0x7E000B00, 0x060000F3, 0x7E020202, 0x7E040206, 0x7C040080, 0x060000F3, 0xD5010001, 0x01AA0200,
    0x7E060203, 0xD5010002, 0x01AA0404, 0x7E080207, 0x7C040080, 0xD5010000, 0x01A80101, 0xD5010001,
    0x01AA0601, 0x7E060208, 0x7E0A02F2, 0xD5010002, 0x01A80902, 0xD5010004, 0x01AA0805, 0x7E0C0209,
    0xF80008CF, 0x05030100, 0xF800020F, 0x05060402, 0xBF810000};
const std::uint32_t kPreambleCache[] = {
    0xc0026900, 0x81, 0x80000000, 0x40004000, 0xc0026900, 0x8c, 0xaa99aaaa, 0x0,
    0xc0026900, 0x90, 0x80000000, 0x40004000, 0xc0026900, 0x94, 0x80000000, 0x40004000,
    0xc0026900, 0xb4, 0x0, 0x3f800000, 0xc0016900, 0x103, 0x0,
    0xc0016900, 0x208, 0x0, 0xc0016900, 0x290, 0x0,
    0xc0016900, 0x2a1, 0x0, 0xc0026900, 0x2ad, 0x0, 0x0,
    0xc0016900, 0x2d5, 0x10000, 0xc0016900, 0x2dc, 0x0,
    0xc0066900, 0x2de, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0xc0026900, 0x2e5, 0x0, 0x0,
    0xc0056900, 0x2f9, 0x5, 0x3f800000, 0x3f800000, 0x3f800000, 0x3f800000,
    0xc0046900, 0x310, 0, 0x3, 0, 0x100000, 0xc0026900, 0x316, 0xe, 0x20,
    0xc0016900, 0x349, 0x0, 0xc0016900, 0x358, 0x0, 0xc0016900, 0x367, 0x0,
    0xc0016900, 0x376, 0x0, 0xc0016900, 0x385, 0x0, 0xc0016900, 0x6, 0x0,
    0xc0056900, 0xe8, 0x0, 0x0, 0x0, 0x0, 0x0,
    0xc0076900, 0x1e1, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0,
    0xc0026900, 0x204, 0x90000, 0x4, 0xc0046900, 0x20c, 0x0, 0x0, 0x0, 0x0,
    0xc0016900, 0x2b2, 0x0, 0xc0026900, 0x30e, 0xffffffff, 0xffffffff,
    0xc0016900, 0x314, 0x0, 0xc0016900, 0x10a, 0, 0xc0016900, 0x2a6, 0, 0xc0016900, 0x210, 0,
    0xc0016900, 0x2db, 0, 0xc0016900, 0x1d4, 0, 0xc0002f00, 0x1, 0xc0016900, 0x1, 0x1, 0xc0016900, 0xe, 0x2,
    0xc0016900, 0x206, 0x300, 0xc0016900, 0x212, 0x200, 0xc0017900, 0x7b, 0x20, 0xc0017a00, 0x20000243, 0x0,
    0xc0017900, 0x249, 0, 0xc0017900, 0x24a, 0, 0xc0017900, 0x24b, 0, 0xc0017900, 0x259, 0xffffffff,
    0xc0017900, 0x25f, 0, 0xc0017900, 0x260, 0, 0xc0017900, 0x262, 0,
    0xc0017600, 0x45, 0x0, 0xc0017600, 0x6, 0x0,
    0xc0067600, 0x70, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0,
    0xc0067600, 0x30, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0};
const std::uint32_t kCachedCmd[] = {
    0xc0016900, 0x0, 0x0, 0xc0026900, 0x3, 0x2a, 0x0,
    0xc0046900, 0xa, 0x0, 0x0, 0x0, 0x200020,
    0xc0016900, 0x83, 0xffff, 0xc0026900, 0x8e, 0xf, 0xf,
    0xc0056900, 0x105, 0x0, 0x0, 0x0, 0x0, 0x18,
    0xc0026900, 0x10b, 0x0, 0x0, 0xc0016900, 0x1e0, 0x0,
    0xc0036900, 0x200, 0x0, 0x10000, 0xcc0011,
    0xc0026900, 0x292, 0x20, 0x6020000,
    0xc0026900, 0x2b0, 0x0, 0x0, 0xc0016900, 0x2f8, 0x0};

constexpr std::uint32_t pkt3(std::uint32_t op, std::uint32_t count) {
    return 0xC0000000u | ((count & 0x3fffu) << 16) | (op << 8);
}
constexpr std::uint32_t kSetContext = 0x69, kSetSh = 0x76, kSetShIndex = 0x77, kSetUconfig = 0x79,
                        kContextControl = 0x28, kDrawIndexAuto = 0x2d;

struct Ib {
    std::vector<std::uint32_t> w;
    void put(std::uint32_t v) { w.push_back(v); }
    void put(std::initializer_list<std::uint32_t> v) { w.insert(w.end(), v); }
    void zeros(std::size_t n) { w.insert(w.end(), n, 0u); }
    void set_context(std::uint32_t off, std::initializer_list<std::uint32_t> vals) {
        put(pkt3(kSetContext, static_cast<std::uint32_t>(vals.size())));
        put(off);
        put(vals);
    }
    void set_sh(std::uint32_t off, std::initializer_list<std::uint32_t> vals) {
        put(pkt3(kSetSh, static_cast<std::uint32_t>(vals.size())));
        put(off);
        put(vals);
    }
};

// The libdrm gfx10 sequence: context control, preamble cache, surface info, state, VS, PS,
// PS constants, GE_CNTL + primitive type, the draw, NOP padding.
std::vector<std::uint32_t> build_ib(std::uint64_t dst, std::uint64_t vs, std::uint64_t ps) {
    Ib ib;
    ib.put({pkt3(kContextControl, 1), 0x80000000u, 0x80000000u});
    ib.w.insert(ib.w.end(), std::begin(kPreambleCache), std::end(kPreambleCache));
    // surface info (amdgpu_draw_setup_and_write_drawblt_surf_info_gfx10)
    ib.put(pkt3(kSetContext, 14));
    ib.put(0x318);
    ib.put(static_cast<std::uint32_t>(dst >> 8));
    ib.zeros(3);
    ib.put(0x50438); // CB_COLOR0_INFO
    ib.zeros(9);
    ib.set_context(0x390, {static_cast<std::uint32_t>(dst >> 40)});
    ib.set_context(0x398, {0});
    ib.set_context(0x3a0, {0});
    ib.set_context(0x3a8, {0});
    ib.set_context(0x3b0, {0x7c01f});    // CB_COLOR0_ATTRIB2: 32x32
    ib.set_context(0x3b8, {0x9014000});  // CB_COLOR0_ATTRIB3
    ib.set_context(0x32b, {0});
    ib.set_context(0x33a, {0});
    ib.set_context(0x1c5, {9});          // SPI_SHADER_COL_FORMAT
    ib.put({pkt3(kSetContext, 2), 0x10, 0, 0}); // DB_Z_INFO, DB_STENCIL_INFO
    // state (amdgpu_draw_setup_and_write_drawblt_state_gfx10)
    ib.set_context(0xd7, {0});
    ib.put({0xffff1000u, 0xc0021000u}); // a NOP and a 4-dword NOP, as in the test
    ib.zeros(2);
    ib.set_context(0xd7, {0});
    ib.put(pkt3(kSetContext, 16));
    ib.put(0x2fe);
    ib.zeros(16);
    ib.put(pkt3(kSetContext, 2));
    ib.put(0x2f5);
    ib.zeros(2);
    ib.w.insert(ib.w.end(), std::begin(kCachedCmd), std::end(kCachedCmd));
    ib.set_context(0x104, {0x40aa0055});
    ib.set_context(0x1f, {0x2a0055});
    // VS (amdgpu_draw_vs_RectPosTexFast_write2hw_gfx10)
    ib.set_context(0x207, {0});
    ib.put({pkt3(kSetShIndex, 1), 0x30000046u, 0xffffu}); // SPI_SHADER_PGM_RSRC3_VS
    ib.put({pkt3(kSetShIndex, 1), 0x30000041u, 0xffffu}); // SPI_SHADER_PGM_RSRC4_VS
    ib.set_sh(0x48, {static_cast<std::uint32_t>(vs >> 8), static_cast<std::uint32_t>(vs >> 40)});
    ib.set_sh(0x4a, {0xc0041});
    ib.set_sh(0x4b, {0x18});
    ib.set_context(0x1b1, {2});
    ib.set_context(0x1c3, {4});
    ib.put({pkt3(kSetSh, 4), 0x4c, 0, 0, 0x42000000u, 0x42000000u});
    ib.put({pkt3(kSetSh, 4), 0x50, 0, 0, 0, 0});
    ib.put({pkt3(kSetSh, 4), 0x54, 0, 0, 0, 0});
    // PS (amdgpu_draw_ps_write2hw_gfx9_10, gfx10 branch; variant 9 of the patched shader)
    const std::uint64_t ps_addr = ps + 256 * 9;
    ib.set_sh(0x8, {static_cast<std::uint32_t>(ps_addr >> 8), static_cast<std::uint32_t>(ps_addr >> 40)});
    ib.put({pkt3(kSetShIndex, 1), 0x30000007u, 0xffffu}); // SPI_SHADER_PGM_RSRC3_PS
    ib.put({pkt3(kSetShIndex, 1), 0x30000001u, 0xffffu}); // SPI_SHADER_PGM_RSRC4_PS
    ib.set_sh(0x0a, {0x000C0000}); // RSRC1_PS
    ib.set_sh(0x0b, {0x00000008}); // RSRC2_PS
    ib.set_context(0x1b4, {2});    // SPI_PS_INPUT_ADDR
    ib.set_context(0x1b3, {2});    // SPI_PS_INPUT_ENA
    ib.set_context(0x1b6, {0});    // SPI_PS_IN_CONTROL
    ib.set_context(0x08f, {0xf});  // CB_SHADER_MASK
    ib.set_context(0x203, {0x10}); // DB_SHADER_CONTROL
    ib.set_context(0x1c4, {0});    // SPI_SHADER_Z_FORMAT
    ib.set_context(0x1b8, {0});    // SPI_BARYC_CNTL
    // PS constant data: the memset value
    ib.put({pkt3(kSetSh, 4), 0xc, 0x33333333u, 0x33333333u, 0x33333333u, 0x33333333u});
    // draw (amdgpu_draw_draw, gfx10)
    ib.put({pkt3(kSetUconfig, 1), 0x25b, 0xff}); // GE_CNTL
    ib.put({pkt3(kSetUconfig, 1), 0x242, 0x11}); // VGT_PRIMITIVE_TYPE = RECTLIST
    ib.put({pkt3(kDrawIndexAuto, 1), 3, 2});
    while (ib.w.size() & 7) ib.put(0xffff1000u);
    return ib.w;
}

} // namespace

int main(int argc, char **argv) {
    bool submit = false;
    std::string node = "/dev/dri/renderD128";
    for (int i = 1; i < argc; ++i) {
        const std::string_view a = argv[i];
        if (a == "--submit") submit = true;
        else if (a == "--render-node" && i + 1 < argc) node = argv[++i];
        else {
            std::fprintf(stderr, "usage: draw-min --submit [--render-node PATH]\n");
            return 2;
        }
    }
    const auto ib = build_ib(0x1000, 0x2000, 0x3000);
    std::printf("draw-min: %zu dwords of IB (libdrm gfx10 memset-draw sequence)\n", ib.size());
    if (!submit) {
        std::printf("dry run; --submit runs it on the GPU\n");
        return 0;
    }
#ifndef BC5_WITH_AMDGPU
    std::fprintf(stderr, "built without BC5_WITH_AMDGPU\n");
    return 1;
#else
    // Buffers: anonymous CPU memory, resident, mapped 1:1 — the track-B memory model.
    auto alloc = [](std::size_t bytes) {
        void *p = mmap(nullptr, bytes, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        if (p == MAP_FAILED) return static_cast<std::uint8_t *>(nullptr);
        std::memset(p, 0, bytes);
        return static_cast<std::uint8_t *>(p);
    };
    std::uint8_t *dst = alloc(0x10000), *vs = alloc(0x10000), *ps = alloc(0x10000);
    if (!dst || !vs || !ps) { std::perror("mmap"); return 1; }
    std::memcpy(vs, kVsRectPosTexFast, sizeof(kVsRectPosTexFast));
    for (int v = 0; v < 10; ++v) {
        std::memcpy(ps + 256 * v, kPsConst, sizeof(kPsConst));
        std::memcpy(ps + 256 * v + 4 * 4, kPsConstPatch[v], sizeof(kPsConstPatch[v]));
    }
    auto dev = bc5::direct::Device::open(node);
    if (!dev) return 1;
    for (auto *p : {dst, vs, ps}) {
        if (!dev->map_userptr(reinterpret_cast<std::uint64_t>(p), 0x10000)) {
            std::fprintf(stderr, "map_userptr failed\n");
            return 1;
        }
    }
    const auto real = build_ib(reinterpret_cast<std::uint64_t>(dst), reinterpret_cast<std::uint64_t>(vs),
                               reinterpret_cast<std::uint64_t>(ps));
    bc5::policy::FilterOptions opt;
    const auto maps = dev->mappings();
    opt.mapped = [&maps](std::uint64_t a, std::uint64_t bytes) {
        for (const auto &m : maps)
            if (a >= m.va && a + bytes <= m.va + m.size) return true;
        return false;
    };
    const auto r = dev->submit(real, opt, 2'000'000'000ull);
    std::printf("submit: %s rc %d%s %.2f ms; filter: %llu pass %llu rewrite %llu drop\n",
                r.ok ? "OK" : "FAILED", r.rc, r.timed_out ? " TIMEOUT" : "", r.submit_ms,
                static_cast<unsigned long long>(r.filter.passed), static_cast<unsigned long long>(r.filter.rewritten),
                static_cast<unsigned long long>(r.filter.dropped));
    if (!r.ok) return 1;
    // 32x32 x 4 bytes = 4 KiB of 0x33 expected (the test checks bytes 0, size/2, size-16)
    std::size_t bytes33 = 0, nonzero = 0;
    for (std::size_t i = 0; i < 0x4000; ++i) {
        bytes33 += dst[i] == 0x33;
        nonzero += dst[i] != 0;
    }
    std::printf("dst: %zu of 16384 bytes == 0x33, %zu non-zero; first dwords %08x %08x %08x %08x\n", bytes33, nonzero,
                reinterpret_cast<std::uint32_t *>(dst)[0], reinterpret_cast<std::uint32_t *>(dst)[1],
                reinterpret_cast<std::uint32_t *>(dst)[2], reinterpret_cast<std::uint32_t *>(dst)[3]);
    return bytes33 > 0 ? 0 : 3;
#endif
}
