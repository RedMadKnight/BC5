// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0439 (tag gs439): does the shared filter strip CP_SYNC from the dcb's GDS DMA_DATA? A synthetic IB (no
// title bytes) with the two GFX-queue forms the dump session (exp 0440/0441) read in the title's dcb: a GDS-to-memory
// copy 0xa0306000 (CP_SYNC, SRC_SEL 1 GDS, DST_SEL 3) and a fill 0xc6104000 (CP_SYNC, SRC_SEL 2 data, DST_SEL 1 GDS),
// filtered with the options bc5LleAgc.cpp's submit sets (drop_gds false, no GDS shadow). Prints what comes out.
#include "bc5/policy.hpp"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <span>
#include <vector>

int main(int argc, char **argv) {
    // "keep": BC5_0439_KEEP_GDS_SYNC=1 (candidate F, private policy.cpp): both must keep CP_SYNC; otherwise both lose it
    const bool keep = argc > 1 && std::strcmp(argv[1], "keep") == 0;
    if (keep) setenv("BC5_0439_KEEP_GDS_SYNC", "1", 1);
    const std::vector<std::uint32_t> ib = {
        0xC0055000u, 0xa0306000u, 0xd08u, 0u, 0x1000u, 0x20u, 4u, // copy GDS -> memory, CP_SYNC
        0xC0055000u, 0xc6104000u, 0u, 0u, 0xd08u, 0u, 8u,         // fill data -> GDS, CP_SYNC
    };
    std::vector<std::uint32_t> out(ib.size());
    bc5::policy::FilterOptions opt;
    opt.mapped = [](std::uint64_t, std::uint64_t) { return true; };
    opt.clear_int_sel = true;
    opt.drop_gds = false;
    bc5::policy::FilterStats st;
    bc5::policy::filter(bc5::policy::Policy::builtin(), std::span<const std::uint32_t>(ib), out, opt, st);
    std::printf("copy 0x%08x -> 0x%08x, fill 0x%08x -> 0x%08x, gds_rewrites %llu\n", ib[1], out[1], ib[8], out[8],
                static_cast<unsigned long long>(st.gds_rewrites));
    const bool stripped = (out[1] & 0x80000000u) == 0 && (out[8] & 0x80000000u) == 0;
    const bool kept = (out[1] & 0x80000000u) != 0 && (out[8] & 0x80000000u) != 0;
    const bool pass = keep ? kept : stripped;
    std::printf("%s; expected %s: %s\n", stripped ? "STRIPPED: both lose CP_SYNC" : kept ? "KEPT: both keep CP_SYNC" : "mixed",
                keep ? "kept" : "stripped", pass ? "PASS" : "FAIL");
    return pass ? 0 : 1;
}
