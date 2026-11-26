// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0439 (tag pa439): det test of pa0439.hpp on a synthetic job (no title bytes): a SET_SH_REG, a GDS-to-memory
// DMA_DATA (CP_SYNC 0), a compute-form DISPATCH_INDIRECT whose arguments the host can read, one whose arguments it may not,
// a GFX-form (3-dword) DISPATCH_INDIRECT that must be skipped, and a NOP with the 0x3fff count. Planted bugs
// BC5_PA439_PLANT_READ (arguments never read) and BC5_PA439_PLANT_DMA (DST_SEL one bit off) must FAIL.
#include "bc5/pa0439.hpp"

#include <cstdint>
#include <cstdio>
#include <vector>

static int g_fail = 0;
#define CHECK(x) do { if (!(x)) { std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #x); g_fail++; } } while (0)

static std::uint32_t pkt3(std::uint32_t op, std::uint32_t n_dw) { return 0xC0000000u | ((n_dw - 2) << 16) | (op << 8); }

int main() {
    alignas(16) static std::uint32_t args[3] = {13104, 1, 1};
    alignas(16) static std::uint32_t hidden[3] = {7, 7, 7};
    const auto a = reinterpret_cast<std::uintptr_t>(args), h = reinterpret_cast<std::uintptr_t>(hidden);
    std::vector<std::uint32_t> w;
    w.push_back(pkt3(0x76, 3)); w.push_back(0x212); w.push_back(0x402c0308);                       // SET_SH_REG
    w.push_back(pkt3(0x76, 4)); w.push_back(0x240); w.push_back(0x10326180); w.push_back(0x20);     // USER_DATA_0/1
    w.push_back(pkt3(0x50, 7));                                                                    // DMA_DATA GDS -> memory (TC_L2)
    w.push_back((1u << 29) | (3u << 20)); w.push_back(0x40); w.push_back(0);                       // SRC_SEL 1 (GDS), DST_SEL 3
    w.push_back(static_cast<std::uint32_t>(a)); w.push_back(static_cast<std::uint32_t>(a >> 32)); w.push_back(4);
    w.push_back(pkt3(0x16, 4)); w.push_back(static_cast<std::uint32_t>(a)); w.push_back(static_cast<std::uint32_t>(a >> 32) & 0xffff); w.push_back(0x41);
    w.push_back(pkt3(0x16, 4)); w.push_back(static_cast<std::uint32_t>(h)); w.push_back(static_cast<std::uint32_t>(h >> 32) & 0xffff); w.push_back(0x41);
    w.push_back(pkt3(0x16, 3)); w.push_back(0x100); w.push_back(0x41);                            // GFX form: skipped
    w.push_back(0xC0001000u | (0x3fffu << 16));                                                    // NOP, count 0x3fff: 1 dword
    const auto readable = [a](std::uint64_t x, std::uint64_t b) { return x >= a && x + b <= a + sizeof(args); };
    const auto s = bc5::pa439::scan(w.data(), static_cast<std::uint32_t>(w.size()), readable);
    CHECK(s.ind.size() == 2);
    CHECK(s.dma.size() == 1);
    if (s.ind.size() == 2) {
        CHECK(s.ind[0].q == 14 && s.ind[0].addr == a && s.ind[0].have && s.ind[0].v[0] == 13104 && s.ind[0].v[1] == 1);
        CHECK(s.ind[0].table == 0x2010326180ull); // from the SET_SH_REG 0x240 in front
        CHECK(s.ind[1].q == 18 && s.ind[1].addr == h && !s.ind[1].have);
    }
    if (s.dma.size() == 1) {
        const auto &d = s.dma[0];
        CHECK(d.q == 7 && !d.cp_sync() && d.src_sel() == 1 && d.dst_sel() == 3 && d.src() == 0x40 && d.dst() == a && d.bytes() == 4);
    }
    std::printf("%s (%d failures)\n", g_fail == 0 ? "PASS" : "FAIL", g_fail);
    return g_fail == 0 ? 0 : 1;
}
