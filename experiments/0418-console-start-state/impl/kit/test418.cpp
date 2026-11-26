// SPDX-License-Identifier: GPL-2.0-only
// BC5 exp 0418, the box's CPU test of the two headers as the private tree has them (src/bc5/start_state.hpp,
// src/bc5/gc_trace.hpp; identical copies of backend/include/bc5's, whose Catch2 tests ran on the laptop). Built with the
// box's compiler, warnings as errors: g++ -std=c++20 -O1 -Wall -Wextra -Werror -I <tree>/src test418.cpp
// Prints "test418: <passed> of <checks>; end" and exits 0 when all pass.
#include "bc5/gc_trace.hpp"
#include "bc5/start_state.hpp"

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <map>
#include <string>
#include <vector>

namespace ss = bc5::start_state;
namespace gt = bc5::gc_trace;

static int g_checks = 0, g_passed = 0;
static void check(bool ok, const char *what) {
    ++g_checks;
    if (ok) ++g_passed;
    else std::printf("FAIL %s\n", what);
}

struct Env {
    std::map<std::string, std::string> v;
    const char *operator()(const char *n) const {
        const auto it = v.find(n);
        return it == v.end() ? nullptr : it->second.c_str();
    }
};

int main() {
    {
        const Env none; // the table is always on: every row, with nothing set
        const auto s = ss::select(none);
        const std::vector<std::uint32_t> want = {0xC0017900u, 0x07bu, 0x20u, 0xC0017600u, 0x030u, 0x7u, 0xC0017900u, 0x249u, 0x0u,
                                                 0xC0017900u, 0x259u, 0xffffffffu, 0xC0017900u, 0x25au, 0x0u};
        check(s.on == (1u << ss::kRowCount) - 1u && s.skipped == 0, "nothing set: every row");
        check(ss::constant_packets(s) == want, "the five constant packets");
        check(s.row_on("VGT_TF_RING") && s.row_on("VGT_HS_OFFCHIP_PARAM") && s.row_on("VGT_GS_RINGS"), "the ring rows");
    }
    {
        Env e; // the deleted switches change nothing, at 0 or 1
        for (const char *w : {"BC5_DIRECT_START_STATE", "BC5_DIRECT_CP_COHER_START_DELAY", "BC5_DIRECT_SPI_REQ_CTRL_PS",
                              "BC5_DIRECT_GC_TF_RING", "BC5_DIRECT_GC_HS_OFFCHIP", "BC5_DIRECT_GC_GS_RINGS"})
            e.v[w] = "0";
        check(ss::select(e).on == (1u << ss::kRowCount) - 1u, "deleted switches at 0: every row");
        e.v["BC5_DIRECT_START_STATE_SKIP"] = "VGT_HS_OFFCHIP_PARAM,GE_MAX_VTX_INDX";
        const auto s = ss::select(e);
        check(!s.row_on("VGT_HS_OFFCHIP_PARAM") && !s.row_on("GE_MAX_VTX_INDX") && s.row_on("VGT_TF_RING"), "SKIP drops its rows");
        check(ss::constant_packets(s).size() == 12, "SKIP: four constant packets left");
        check(gt::switch_on("1") && !gt::switch_on("0") && !gt::switch_on(nullptr), "the trace switch");
    }
    {
        const std::vector<std::uint32_t> prefix = {0xC0012800u, 0x80000000u, 0x80000000u, 0xC0001200u, 0u};
        check(ss::insert_at(prefix) == 5, "after CONTEXT_CONTROL and CLEAR_STATE");
        check(ss::insert_at(std::vector<std::uint32_t>{0xC0016900u, 1u, 2u}) == 0, "at 0 without them");
    }
    {
        ss::GsRings r;
        const std::uint32_t a[3] = {0x400000u, 0x800000u, 0u}, odd[3] = {0x400010u, 0x800000u, 0u};
        check(ss::gs_rings_from_request(a, r) && r.esgs == 0x4000u && r.gsvs == 0x8000u, "GS rings: bytes >> 8");
        check(!ss::gs_rings_from_request(odd, r), "GS rings: not a multiple of 256");
        std::vector<std::uint32_t> p;
        ss::gs_rings_packets(p, {0x4000u, 0x8000u}, true);
        check(p == std::vector<std::uint32_t>{0xC0004600u, 0x40fu, 0xC0004600u, 0x24u, 0xC0027900u, 0x240u, 0x4000u, 0x8000u}, "GS rings: packets");
    }
    {
        std::map<std::uint64_t, std::uint64_t> q = {{0x7000, 0x7040}, {0x7008, 0xA1}, {0x7040, 0x7030}, {0x7048, 0xA2}};
        const auto read = [&q](std::uint64_t a, std::uint64_t *two) {
            const auto x = q.find(a), y = q.find(a + 8);
            if (x == q.end() || y == q.end()) return false;
            two[0] = x->second;
            two[1] = y->second;
            return true;
        };
        std::uint64_t ret[8] = {};
        check(gt::walk_frames(0x7000, read, ret, 8) == 2 && ret[0] == 0xA1 && ret[1] == 0xA2, "walk: stops at a non-increasing frame");
        const gt::Export ex[] = {{0x2000, "B#A#A"}, {0x1000, "A#A#A"}};
        check(gt::nearest_export(ex, 2, 0x1fff) != nullptr && gt::nearest_export(ex, 2, 0x1fff)->name == "A#A#A", "nearest export");
        check(gt::nid_of("XlNp7jzGiPo#A#B") == "XlNp7jzGiPo", "NID");
    }
    std::printf("test418: %d of %d; end\n", g_passed, g_checks);
    return g_passed == g_checks ? 0 : 1;
}
