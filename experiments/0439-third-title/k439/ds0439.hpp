// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0439 (tag ds439): the insertion points of candidates D, D-label and C (README item 49), as one function
// the backend's Device::submit calls and the det tests check. It is experiment 0050's loop (the zero-byte CP_SYNC
// DMA_DATA before the first dispatch after an unsynced DMA_DATA, GFX ring) with three additions, each behind its own
// switch:
//   d_mec (BC5_0439_DMA_SYNC_MEC=1): the same wait on the compute rings too (candidate D);
//   c_mec (BC5_0439_ARGS_GL2WB=1): on the compute rings, an ACQUIRE_MEM with GL2_WB after it (candidate C);
//   label (BC5_0439_DMA_SYNC_LABEL=1): the wait also before the first label write (RELEASE_MEM, EVENT_WRITE_EOP,
//     WRITE_DATA to memory) after an unsynced DMA_DATA, and at the end of a buffer that ends with one pending, so a
//     label never goes out ahead of a copy another queue reads behind it (queue 24's copies -> the dcb's indirect
//     dispatches, the dump session of exp 0440/0441).
// Why the host supplies this order (the dump session's census): the title's library writes CP_SYNC on every GDS
// DMA_DATA and a PFP_SYNC_ME before every indirect dispatch on the GFX queue (7 of 7), and neither on its compute queues
// (0 of 27), so the console's compute engine keeps DMA_DATA in order by itself and this part's does not.
// Packet forms (Mesa 0866ae7): the wait is si_emit_cp_dma(sctx, cs, 0, 0, 0, CP_DMA_SYNC)'s zero-byte DMA_DATA, CP_SYNC,
// SRC_SEL and DST_SEL "address using L2" (as backend/src/direct.cpp has it since experiment 0050); the ACQUIRE_MEM is
// gfx10 ac_emit_cp_acquire_mem (src/amd/common/ac_cmdbuf_cp.c:412-429): engine 0 off the GFX queue, size 0xffffffff,
// size_hi 0xff, base 0, poll interval 0xA, GCR_CNTL = GL2_WB (bit 15; backend/include/bc5/policy.hpp:93).
// WRITE_DATA's DST_SEL (dword 1 bits 11:8) 1, 2 or 5 is a memory destination, as the probe's label scan reads it.
#pragma once

#include <cstddef>
#include <cstdint>
#include <utility>
#include <vector>

namespace bc5::ds439 {

inline const std::vector<std::uint32_t> &wait_words() {
    static const std::vector<std::uint32_t> w{0xC0055000u, 0xE0300000u, 0u, 0u, 0u, 0u, 0u};
    return w;
}
inline const std::vector<std::uint32_t> &wb_words() {
    static const std::vector<std::uint32_t> w{0xC0065800u, 0u, 0xffffffffu, 0xffu, 0u, 0u, 0x0000000Au, 0x00008000u};
    return w;
}

// (offset, words) pairs, offsets ascending, each a packet start or the buffer's size (an append). gfx: the GFX-ring
// wait of experiment 0050 is on (FilterOptions::dma_sync_before_dispatch); comp: the job goes to a compute ring.
inline std::vector<std::pair<std::size_t, std::vector<std::uint32_t>>> points(const std::vector<std::uint32_t> &ib, bool comp, bool gfx,
                                                                                bool d_mec, bool c_mec, bool label = false) {
    std::vector<std::pair<std::size_t, std::vector<std::uint32_t>>> r;
    const bool on = comp ? (d_mec || c_mec || label) : (gfx || label);
    if (!on) return r;
    const auto words = [&]() {
        std::vector<std::uint32_t> w;
        if (!comp || d_mec || label) w.insert(w.end(), wait_words().begin(), wait_words().end());
#if !defined(BC5_DS439_PLANT_NOWB) // the planted bug: C's write-back never inserted
        if (comp && c_mec) w.insert(w.end(), wb_words().begin(), wb_words().end());
#endif
        return w;
    };
    bool pending = false;
    for (std::size_t i = 0; i < ib.size();) {
        const std::uint32_t h = ib[i];
        const std::uint32_t type = h >> 30;
        std::size_t len = 1;
        if (type == 3 || type == 0) {
            const std::uint32_t count = (h >> 16) & 0x3fff;
            len = count == 0x3fff ? 1 : count + 2;
        }
        if (i + len > ib.size()) len = ib.size() - i;
        const std::uint32_t op = (h >> 8) & 0xff;
        if (type == 3 && op == 0x50 && len >= 2) pending = (ib[i + 1] & 0x80000000u) == 0;
        const bool dispatch = type == 3 && (op == 0x15 || op == 0x16) && (comp ? (d_mec || c_mec) : gfx);
        const bool label_write = type == 3 && label &&
                                 (op == 0x49 || op == 0x47 ||
                                  (op == 0x37 && len >= 2 && (((ib[i + 1] >> 8) & 0xfu) == 1 || ((ib[i + 1] >> 8) & 0xfu) == 2 ||
                                                              ((ib[i + 1] >> 8) & 0xfu) == 5)));
#if defined(BC5_DS439_PLANT_NOLABEL) // the planted bug: the label positions never taken
        if (pending && dispatch) {
#else
        if (pending && (dispatch || label_write)) {
#endif
            auto w = words();
            if (!w.empty()) r.emplace_back(i, std::move(w));
            pending = false;
        }
        i += len;
    }
#if !defined(BC5_DS439_PLANT_NOEND) // the planted bug: nothing at the end of a buffer with a copy pending
    if (pending && label) r.emplace_back(ib.size(), wait_words());
#endif
    return r;
}

} // namespace bc5::ds439
