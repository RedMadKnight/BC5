// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0439 (tag ds439): det test of ds0439.hpp's insertion points (candidates D and C) on a synthetic IB (no
// title bytes): an unsynced DMA_DATA (the title's copy form 0x20306000), a DISPATCH_INDIRECT, a CP_SYNC DMA_DATA, a
// DISPATCH_DIRECT, a SET_SH_REG and a second DISPATCH_DIRECT. BC5_DS439_PLANT_NOWB (C's write-back never inserted) must FAIL.
#include "bc5/ds0439.hpp"

#include <cstdio>
#include <vector>

static int g_fail = 0;
#define CHECK(x) do { if (!(x)) { std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #x); g_fail++; } } while (0)

int main() {
    const std::vector<std::uint32_t> ib = {
        0xC0055000u, 0x20306000u, 0xd08u, 0u, 0x0085d0c0u, 0x50u, 4u,   // 0: DMA_DATA, CP_SYNC clear
        0xC0021600u, 0x0085d0c0u, 0x50u, 0x41u,                         // 7: DISPATCH_INDIRECT
        0xC0055000u, 0xA0306000u, 0xd08u, 0u, 0x0085d0c0u, 0x50u, 4u,   // 11: DMA_DATA, CP_SYNC set
        0xC0031500u, 1u, 1u, 1u, 0x41u,                                 // 18: DISPATCH_DIRECT
        0xC0017600u, 0x212u, 0u,                                        // 23: SET_SH_REG
        0xC0031500u, 1u, 1u, 1u, 0x41u,                                 // 26: DISPATCH_DIRECT
    };
    using bc5::ds439::points;
    const auto &W = bc5::ds439::wait_words();
    const auto &B = bc5::ds439::wb_words();
    { // compute ring, all off: nothing (the shared behaviour)
        CHECK(points(ib, true, true, false, false).empty());
    }
    { // compute ring, D: one wait before 7 only
        const auto r = points(ib, true, false, true, false);
        CHECK(r.size() == 1 && r[0].first == 7 && r[0].second == W);
    }
    { // compute ring, C: one write-back before 7 only
        const auto r = points(ib, true, false, false, true);
        CHECK(r.size() == 1 && r[0].first == 7 && r[0].second == B);
    }
    { // compute ring, D + C: the wait, then the write-back, before 7
        const auto r = points(ib, true, false, true, true);
        std::vector<std::uint32_t> both(W);
        both.insert(both.end(), B.begin(), B.end());
        CHECK(r.size() == 1 && r[0].first == 7 && r[0].second == both);
    }
    { // GFX ring: experiment 0050's wait when on, whatever D and C say; nothing when off
        const auto r = points(ib, false, true, true, true);
        CHECK(r.size() == 1 && r[0].first == 7 && r[0].second == W);
        CHECK(points(ib, false, false, true, true).empty());
    }
    { // D-label, the three positions (queue 24's shape: copies, then a label release, then nothing or a dispatch)
        const std::vector<std::uint32_t> q = {
            0xC0055000u, 0x20306000u, 0xd08u, 0u, 0x1000u, 0x20u, 4u,      // 0: DMA_DATA, CP_SYNC clear
            0xC0064900u, 0x00000528u, 0x40010000u, 0x2000u, 0x20u, 1u, 0u, 0u, // 7: RELEASE_MEM of a label
            0xC0055000u, 0x20306000u, 0xd0cu, 0u, 0x1010u, 0x20u, 4u,      // 15: DMA_DATA, CP_SYNC clear
            0xC0033700u, 0x00000500u, 0x3000u, 0x20u, 1u,                  // 22: WRITE_DATA to memory (DST_SEL 5)
            0xC0055000u, 0x20306000u, 0xd10u, 0u, 0x1020u, 0x20u, 4u,      // 27: DMA_DATA, CP_SYNC clear, then the end
        };
        const auto r = points(q, true, false, false, false, true);
        CHECK(r.size() == 3);
        if (r.size() == 3) {
            CHECK(r[0].first == 7 && r[0].second == W);           // before the release
            CHECK(r[1].first == 22 && r[1].second == W);          // before the label WRITE_DATA
            CHECK(r[2].first == q.size() && r[2].second == W);    // at the end
        }
        // with D and label on, a dispatch after a copy still takes the wait (before the dispatch only, once)
        const auto rd = points(ib, true, false, true, false, true);
        CHECK(rd.size() == 1 && rd[0].first == 7);
        // label off: the shape gets nothing (D only covers dispatches)
        CHECK(points(q, true, false, true, false, false).empty());
        // the GFX ring with label on and the exp 0050 wait off: the label positions only
        CHECK(points(q, false, false, false, false, true).size() == 3);
        // top's check: a title WAIT_REG_MEM, a copy, then the release the wait guards: the sync lands after the wait and
        // before the release, so the label's order against the wait is unchanged (only the release is held back)
        const std::vector<std::uint32_t> w2 = {
            0xC0053C00u, 0x13u, 0x2000u, 0x20u, 1u, 0xffffffffu, 0x19u,         // 0: WAIT_REG_MEM
            0xC0055000u, 0x20306000u, 0xd08u, 0u, 0x1000u, 0x20u, 4u,          // 7: DMA_DATA, CP_SYNC clear
            0xC0064900u, 0x00000528u, 0x40010000u, 0x2010u, 0x20u, 1u, 0u, 0u, // 14: RELEASE_MEM
        };
        const auto rw = points(w2, true, false, false, false, true);
        CHECK(rw.size() == 1 && rw[0].first == 14);
    }
    std::printf("%s (%d failures)\n", g_fail == 0 ? "PASS" : "FAIL", g_fail);
    return g_fail == 0 ? 0 : 1;
}
