// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/selftest_route.hpp"

#include <catch2/catch_test_macros.hpp>

using bc5::selftest::Args;
using bc5::selftest::Path;
using bc5::selftest::route;

TEST_CASE("direct-selftest routing (experiment 0380, Codex review REVIEW-05)", "[selftest_route]") {
    SECTION("nothing runs without --submit, whatever else is given") {
        CHECK(route(Args{false, true, true, 0}) == Path::nothing);
        CHECK(route(Args{}) == Path::nothing);
    }
    SECTION("--compute-ring takes the MEC ladder, also with --zero-check") {
        CHECK(route(Args{true, false, false, 0}) == Path::compute_ladder);
        CHECK(route(Args{true, true, true, 0}) == Path::compute_ladder); // was the GFX check before the fix
        CHECK(route(Args{true, true, false, 2}) == Path::compute_ladder);
    }
    SECTION("--cp-check / --zero-check alone take the GFX check") {
        CHECK(route(Args{true, true, false, -1}) == Path::gfx_check);
        CHECK(route(Args{true, true, true, -1}) == Path::gfx_check);
    }
    SECTION("neither: the IB submissions") {
        CHECK(route(Args{true, false, false, -1}) == Path::ibs);
    }
}
