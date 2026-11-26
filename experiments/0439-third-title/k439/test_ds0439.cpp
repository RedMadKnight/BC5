// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0439 (tag ds439): det test of candidate B in the private policy.cpp on a synthetic IB (no title bytes):
// the title's two DMA_DATA forms as the dump session (exp 0440/0441) read them (a GDS fill 0x46104000: SRC_SEL 2 data, DST_SEL 1 GDS; a
// GDS-to-memory copy 0x20306000: SRC_SEL 1 GDS, DST_SEL 3 address through L2), then a compute-form DISPATCH_INDIRECT.
// With BC5_0439_DMA_DST_BYPASS=1 the copy's DST_CACHE_POLICY (bits 26:25) becomes 3 and nothing else changes; without
// it the IB passes as it was. Run twice: "on" and "off" (the control).
#include "bc5/policy.hpp"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <span>
#include <vector>

static int g_fail = 0;
#define CHECK(x) do { if (!(x)) { std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #x); g_fail++; } } while (0)

int main(int argc, char **argv) {
    const bool on = argc > 1 && std::strcmp(argv[1], "on") == 0;
    if (on) setenv("BC5_0439_DMA_DST_BYPASS", "1", 1), setenv("BC5_0439_WAVES_UNLIMITED", "1", 1);
    const std::vector<std::uint32_t> ib = {
        0xC0055000u, 0x46104000u, 0u, 0u, 0xd08u, 0u, 8u,                // DMA_DATA fill: data 0 -> GDS 0xd08, 8 bytes
        0xC0055000u, 0x20306000u, 0xd08u, 0u, 0x0085d0c0u, 0x50u, 4u,   // DMA_DATA copy: GDS 0xd08 -> 0x500085d0c0, 4 bytes
        0xC0021600u, 0x0085d0c0u, 0x50u, 0x41u,                         // DISPATCH_INDIRECT, compute form
        0xC0027600u, 0x214u, 0x0u, 0x7du,                               // SET_SH_REG 0x214, 0x215 (COMPUTE_RESOURCE_LIMITS 0x7d)
    };
    std::vector<std::uint32_t> out(ib.size());
    bc5::policy::FilterOptions opt;
    opt.mapped = [](std::uint64_t, std::uint64_t) { return true; };
    opt.clear_int_sel = true; // as bc5LleAgc.cpp's submit sets them
    opt.drop_gds = false;
    bc5::policy::FilterStats st;
    bc5::policy::filter(bc5::policy::Policy::builtin(), std::span<const std::uint32_t>(ib), out, opt, st);
    std::printf("words: fill 0x%08x copy 0x%08x dispatch %08x %08x %08x %08x\n", out[1], out[8], out[14], out[15], out[16], out[17]);
    CHECK(out[1] == 0x46104000u);                              // the fill's destination is GDS: untouched
    CHECK(out[8] == (on ? 0x26306000u : 0x20306000u));         // the copy: bypass on, as it was off
    CHECK(out[21] == (on ? 0x0u : 0x7du));                     // E: WAVES_PER_SH cleared on, as it was off
    std::printf("limits 0x%08x\n", out[21]);
    for (std::size_t k = 0; k < ib.size(); k++)
        if (k != 8 && k != 21) CHECK(out[k] == ib[k]);
    std::printf("%s %s (%d failures)\n", on ? "on" : "off", g_fail == 0 ? "PASS" : "FAIL", g_fail);
    return g_fail == 0 ? 0 : 1;
}
