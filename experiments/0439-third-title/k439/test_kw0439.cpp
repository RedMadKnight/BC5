// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0439 (tag kw439): det test of candidate G's decision (kw0439.hpp) over every combination of its inputs.
// BC5_KW439_PLANT_GFX (GFX-ring buffers kept too) must FAIL.
#include "bc5/kw0439.hpp"

#include <cstdio>

static int g_fail = 0;
#define CHECK(x) do { if (!(x)) { std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #x); g_fail++; } } while (0)

int main() {
    using bc5::kw439::keep_satisfied;
    int kept = 0;
    for (int m = 0; m < 32; m++) {
        const bool on = m & 1, acb = m & 2, compute = m & 4, self = m & 8, sat = m & 16;
        const bool k = keep_satisfied(on, acb, compute, self, sat);
        kept += k ? 1 : 0;
        CHECK(k == (on && acb && compute && !self && sat));
    }
    CHECK(kept == 1);                                          // exactly the one case
    CHECK(!keep_satisfied(false, true, true, false, true));    // switch off: as today
    CHECK(!keep_satisfied(true, true, false, false, true));    // GFX ring: as today
    CHECK(!keep_satisfied(true, true, true, true, true));      // self-written label: the filter's rule
    CHECK(!keep_satisfied(true, true, true, false, false));    // not satisfied: the existing rule decides
    CHECK(keep_satisfied(true, true, true, false, true));      // the case of acb 3452's waits at 62, 235, 2749
    std::printf("%s (%d failures)\n", g_fail == 0 ? "PASS" : "FAIL", g_fail);
    return g_fail == 0 ? 0 : 1;
}
