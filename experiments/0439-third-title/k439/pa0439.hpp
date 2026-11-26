// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0439 (tag pa439): the indirect-argument probe (README item 49; the top session's GO of 11-22 ~07:30).
// Diagnostics only, behind BC5_0439_ARGS_PROBE=1 in the private normal build: at the submit of a job that holds a
// compute-form DISPATCH_INDIRECT or a DMA_DATA, the host's view of the argument dwords (guest memory, which the GPU maps
// through the same pages) and every DMA_DATA packet are kept in a ring of the last kRing such jobs; the timeout probe
// prints the timed-out job's entry beside the same reads at the timeout. Nothing changes what is submitted.
//
// Packet fields (Mesa 0866ae7):
//   DISPATCH_INDIRECT 0x16, compute-queue form: address lo, address hi, initiator (4 dwords with the header). The
//     probe's existing reading of it: bc5LleAgc.cpp's timeout_probe ("the compute-queue form (4 dwords: the address)").
//   DMA_DATA 0x50 (src/amd/registers/pkt3.json DMA_DATA_WORD0_cik; src/amd/common/sid.h:177-184): dword 1
//     CP_SYNC [31] | SRC_SEL [30:29] | DST_CACHE_POLICY [26:25] | DST_SEL [21:20] | SRC_CACHE_POLICY [14:13] | ENGINE [0];
//     2/3 source (or data) lo/hi; 4/5 destination lo/hi; 6 command, BYTE_COUNT [20:0] per sid.h's comment
//     (TODO(verify) for gfx10: the raw command dword is printed too).
#pragma once

#include <cstdint>
#include <vector>

namespace bc5::pa439 {

struct Ind {
    std::uint32_t q = 0;     // dword offset of the packet in the job
    std::uint64_t addr = 0;  // the arguments' address
    bool have = false;       // readable by the host at this moment
    std::uint32_t v[3] = {}; // the three group counts
    std::uint64_t table = 0; // COMPUTE_USER_DATA_0/1 (SH 0x240/0x241) as last set before it: the program's table
    std::uint64_t table2 = 0; // COMPUTE_USER_DATA_2/3 (SH 0x242/0x243): the second table
    std::uint64_t pgm = 0;    // COMPUTE_PGM_LO/HI (SH 0x20c/0x20d) as last set before it, << 8 (the program's address)
    std::uint32_t limits = ~0u; // COMPUTE_RESOURCE_LIMITS (SH 0x215) as last set before it in this job; ~0 = not set here
};
struct Dma {
    std::uint32_t q = 0;
    std::uint32_t w[6] = {}; // dwords 1..6 of the packet
    bool cp_sync() const { return (w[0] >> 31u) != 0; }
    std::uint32_t src_sel() const { return (w[0] >> 29u) & 3u; }
#if defined(BC5_PA439_PLANT_DMA) // the planted bug: DST_SEL read one bit off
    std::uint32_t dst_sel() const { return (w[0] >> 21u) & 3u; }
#else
    std::uint32_t dst_sel() const { return (w[0] >> 20u) & 3u; }
#endif
    std::uint64_t src() const { return w[1] | (static_cast<std::uint64_t>(w[2]) << 32u); }
    std::uint64_t dst() const { return w[3] | (static_cast<std::uint64_t>(w[4]) << 32u); }
    std::uint32_t bytes() const { return w[5] & 0x1fffffu; }
};
struct Snap {
    std::uint64_t n = ~0ull; // the submit number (g_submits)
    double t = 0;
    std::vector<Ind> ind;
    std::vector<Dma> dma;
};

// Walks the job's type-3 packets (top level). readable(a, bytes) says whether the host may read [a, a + bytes).
template <typename F> Snap scan(const std::uint32_t *ib, std::uint32_t n, F readable) {
    Snap s;
    std::uint32_t ud0 = 0, ud1 = 0, ud2 = 0, ud3 = 0, pl = 0, ph = 0, lim = ~0u;
    for (std::uint32_t q = 0; q < n;) {
        const std::uint32_t h = ib[q], type = h >> 30u;
        std::uint32_t len = 1;
        if (type == 3 || type == 0) {
            const std::uint32_t c = (h >> 16u) & 0x3fffu;
            len = c == 0x3fffu ? 1 : c + 2;
        }
        if (q + len > n) break;
        if (type == 3) {
            const std::uint32_t op = (h >> 8u) & 0xffu;
            if (op == 0x76 && len >= 3) { // SET_SH_REG: track COMPUTE_USER_DATA_0/1
                const std::uint32_t off = ib[q + 1] & 0xffffu;
                for (std::uint32_t k = 0; k + 2 < len; k++) {
                    if (off + k == 0x240u) ud0 = ib[q + 2 + k];
                    if (off + k == 0x241u) ud1 = ib[q + 2 + k];
                    if (off + k == 0x242u) ud2 = ib[q + 2 + k];
                    if (off + k == 0x243u) ud3 = ib[q + 2 + k];
                    if (off + k == 0x20cu) pl = ib[q + 2 + k];
                    if (off + k == 0x20du) ph = ib[q + 2 + k];
                    if (off + k == 0x215u) lim = ib[q + 2 + k];
                }
            }
            if (op == 0x16 && len >= 4) {
                Ind d;
                d.q = q;
                d.addr = (ib[q + 1] & ~3u) | (static_cast<std::uint64_t>(ib[q + 2] & 0xffffu) << 32u);
                d.table = ud0 | (static_cast<std::uint64_t>(ud1 & 0xffffu) << 32u);
                d.table2 = ud2 | (static_cast<std::uint64_t>(ud3 & 0xffffu) << 32u);
                d.pgm = (static_cast<std::uint64_t>(pl) | (static_cast<std::uint64_t>(ph & 0xffu) << 32u)) << 8u;
                d.limits = lim;
#if defined(BC5_PA439_PLANT_READ) // the planted bug: the arguments never read
                if (false) {
#else
                if (d.addr != 0 && readable(d.addr, 12)) {
#endif
                    const auto *t = reinterpret_cast<const volatile std::uint32_t *>(d.addr);
                    d.v[0] = t[0], d.v[1] = t[1], d.v[2] = t[2], d.have = true;
                }
                s.ind.push_back(d);
            } else if (op == 0x50 && len >= 7) {
                Dma d;
                d.q = q;
                for (int k = 0; k < 6; k++) d.w[k] = ib[q + 1 + k];
                s.dma.push_back(d);
            }
        }
        q += len;
    }
    return s;
}

} // namespace bc5::pa439
