// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/env_flag.hpp"

#include <catch2/catch_test_macros.hpp>

TEST_CASE("env_on: unset, empty and 0 are off, anything else is on", "[env_flag]") {
    CHECK_FALSE(bc5::env_on(nullptr));
    CHECK_FALSE(bc5::env_on(""));
    CHECK_FALSE(bc5::env_on("0"));
    CHECK(bc5::env_on("1"));
    CHECK(bc5::env_on("00"));
    CHECK(bc5::env_on("0x0"));
    CHECK(bc5::env_on("junk"));
    CHECK(bc5::env_on("learn:1100000000")); // BC5_DIRECT_HOST_INDIRECT, F433
    CHECK(bc5::env_on("65536:2"));          // BC5_DIRECT_GPU_CHECK_PRODUCT
}
