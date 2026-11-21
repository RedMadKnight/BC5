// SPDX-License-Identifier: GPL-2.0-only
// The register descriptors that sceAgcCreateShader, sceAgcCreatePrimState and the interpolant
// mappings write into the caller's register lists must resolve from BC5's own defaults tables for
// every SDK version: an unresolved descriptor is all-ones, and a register list with offset
// 0xFFFFFFFF reaches the GPU as an illegal register write (run rmplN01, 2026-11-21).
// The internal GS-override descriptors (pairs 24..29) are not in the internal defaults of SDK
// versions 0..9 at all, so they stay unresolved there; every other descriptor resolves always.
#include "bc5/reimpl/agc.hpp"
#include "bc5/reimpl/agc_internal.hpp"

#include <catch2/catch_test_macros.hpp>

#include <cstdio>

namespace agc = bc5::reimpl::agc;
namespace detail = bc5::reimpl::agc::detail;

TEST_CASE("agc descriptors resolve from the own defaults tables", "[reimpl][agc]") {
    agc::testing::reset();
    for (std::uint32_t v = 0; v <= 16; ++v) {
        detail::reset_descriptors();
        REQUIRE(detail::resolve_descriptors(v) == 0);
        const auto &d = detail::descriptors();
        const auto *p = reinterpret_cast<const agc::RegPair *>(&d);
        const std::size_t n = sizeof(d) / sizeof(agc::RegPair);
        for (std::size_t i = 0; i < n; ++i) {
            if (v <= 9 && i >= 24) {
                continue;
            }
            if (p[i].offset == 0xFFFFFFFFu) {
                std::printf("v%u descriptor pair %zu unresolved\n", v, i);
            }
            CHECK(p[i].offset != 0xFFFFFFFFu);
        }
    }
}
