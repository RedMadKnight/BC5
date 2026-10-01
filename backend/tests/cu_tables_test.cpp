// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/cu_tables.hpp"
#include "bc5/policy.hpp"

#include <catch2/catch_test_macros.hpp>

#include <cstdint>
#include <vector>

using namespace bc5;

namespace {
const cu_tables::Readable kAll = [](std::uint64_t, std::uint64_t) { return true; };
}

TEST_CASE("mask_cu_register: the CU-mask fields of the SH registers", "[cu_tables]") {
    std::uint32_t v = 0xffffffffu;
    CHECK(policy::mask_cu_register(0x2e16, v, 0x01ff01ffu)); // COMPUTE_STATIC_THREAD_MGMT_SE0
    CHECK(v == 0x01ff01ffu);
    v = 0x1234ffffu;
    CHECK(policy::mask_cu_register(0x2c07, v, 0x01ff01ffu)); // RSRC3_PS: CU_EN bits 15:0
    CHECK(v == 0x123401ffu);
    v = 0xffff0abcu;
    CHECK(policy::mask_cu_register(0x2d07, v, 0x01ff01ffu)); // RSRC3_HS: CU_EN bits 31:16
    CHECK(v == 0x01ff0abcu);
    v = 0x55555555u;
    CHECK(!policy::mask_cu_register(0x2c08, v, 0x01ff01ffu)); // not a CU-mask register
    CHECK(v == 0x55555555u);
}

TEST_CASE("cu tables: a loaded CU mask is overridden right after the load", "[cu_tables]") {
    // (SH offset, value) pairs: a program address, RSRC3_GS, RSRC3_HS, a compute mask
    static const std::uint32_t table[] = {0x88, 0x05007100u, 0x87, 0x0000ffffu,
                                          0x107, 0xffff0000u, 0x216, 0xffffffffu};
    const auto ta = reinterpret_cast<std::uint64_t>(&table[0]);
    const std::vector<std::uint32_t> ib = {
        0xC0036300u, static_cast<std::uint32_t>(ta), static_cast<std::uint32_t>(ta >> 32), 0x80000000u, 4,
        0xC0002F00u, 1, // NUM_INSTANCES
    };
    cu_tables::Stats st;
    const auto out = cu_tables::apply(ib, 0x01ff01ffu, kAll, st);
    const std::vector<std::uint32_t> expect = {
        ib[0], ib[1], ib[2], ib[3], ib[4],
        0xC0017600u, 0x87, 0x000001ffu,
        0xC0017600u, 0x107, 0x01ff0000u,
        0xC0017600u, 0x216, 0x01ff01ffu,
        0xC0002F00u, 1,
    };
    CHECK(out == expect);
    CHECK(st.loads == 1);
    CHECK(st.overrides == 3);
    CHECK(st.inserted_dwords == 9);

    cu_tables::Stats none;
    CHECK(cu_tables::apply(ib, 0xffffffffu, kAll, none) == ib); // the default mask: nothing to do
    CHECK(none.overrides == 0);
}

TEST_CASE("cu tables: the register image, conditional loads, unreadable tables", "[cu_tables]") {
    static std::uint32_t image[0x220] = {};
    image[0x07] = 0x0000ffffu; // RSRC3_PS
    image[0x219] = 0xffffffffu; // COMPUTE_STATIC_THREAD_MGMT_SE2
    const auto ia = reinterpret_cast<std::uint64_t>(&image[0]);
    const std::vector<std::uint32_t> ib = {
        // LOAD_SH_REG: address, then (offset, count) pairs
        0xC0055F00u, static_cast<std::uint32_t>(ia), static_cast<std::uint32_t>(ia >> 32), 0x06, 2, 0x215, 6,
        0xC0032200u, 0x1000, 0, 0, 5, // COND_EXEC over the next 5 dwords
        0xC0036300u, static_cast<std::uint32_t>(ia), static_cast<std::uint32_t>(ia >> 32), 0x07, 1,
    };
    cu_tables::Stats st;
    const auto out = cu_tables::apply(ib, 0x00030003u, kAll, st);
    // RSRC3_PS from the first pair; the second pair spans all four compute masks
    REQUIRE(out.size() == ib.size() + 15);
    const std::vector<std::uint32_t> appended(out.begin() + 7, out.begin() + 22);
    const std::vector<std::uint32_t> expect = {
        0xC0017600u, 0x07,  0x00000003u, 0xC0017600u, 0x216, 0u, 0xC0017600u, 0x217, 0u,
        0xC0017600u, 0x219, 0x00030003u, 0xC0017600u, 0x21a, 0u,
    };
    CHECK(appended == expect);
    CHECK(st.loads == 1);
    CHECK(st.conditional == 1); // the load inside the COND_EXEC range is left alone

    const cu_tables::Readable no = [](std::uint64_t, std::uint64_t) { return false; };
    cu_tables::Stats un;
    CHECK(cu_tables::apply(ib, 0x00030003u, no, un) == ib);
    CHECK(un.unreadable == 3);
}
