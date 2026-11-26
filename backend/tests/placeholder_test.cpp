// SPDX-License-Identifier: GPL-2.0-only
#include <catch2/catch_test_macros.hpp>

#include "bc5/version.hpp"

TEST_CASE("version string is set", "[placeholder]") { REQUIRE_FALSE(bc5::version().empty()); }

TEST_CASE("default build has no amdgpu path", "[placeholder]") {
#ifndef BC5_WITH_AMDGPU
    REQUIRE_FALSE(bc5::has_amdgpu());
#endif
}
