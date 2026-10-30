// SPDX-License-Identifier: GPL-2.0-only
// Which test direct-selftest runs for its command line (experiment 0380, Codex review REVIEW-05): --compute-ring N
// takes the MEC ladder whether or not --cp-check / --zero-check is given (with --zero-check the ladder adds its zero
// rows); --cp-check / --zero-check alone take the GFX check; without --submit nothing runs on the GPU. Before this,
// the GFX check ran first and returned, so `--compute-ring 0 --zero-check` never reached the ladder's zero rows.
// Pure, so the routing is tested on the CPU (tests/selftest_route_test.cpp).
#pragma once

namespace bc5::selftest {

enum class Path { nothing, gfx_check, compute_ladder, ibs };

struct Args {
    bool submit = false;
    bool cp_check = false;   // --cp-check, or --zero-check
    bool zero_check = false; // --zero-check
    int compute_ring = -1;   // --compute-ring N
};

constexpr Path route(const Args &a) {
    if (!a.submit) return Path::nothing;
    if (a.compute_ring >= 0) return Path::compute_ladder;
    if (a.cp_check) return Path::gfx_check;
    return Path::ibs;
}

} // namespace bc5::selftest
