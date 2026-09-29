// SPDX-License-Identifier: GPL-2.0-only
#include <catch2/catch_test_macros.hpp>

#include "bc5/dispatch_min.hpp"
#include "bc5/pm4.hpp"

#include <algorithm>
#include <stdexcept>

using namespace bc5;

TEST_CASE("type-3 headers match the PM4 encoding", "[pm4]") {
    // HANDOFF F2: SET_CONTEXT_REG with 2 payload dwords is 0xC0016900.
    REQUIRE(pm4::header3(pm4::Op::SetContextReg, 2) == 0xC0016900u);
    // IGT PACKET3_COMPUTE(PKT3_SET_SH_REG, 4) = 5 payload dwords, shader-type bit set.
    REQUIRE(pm4::header3(pm4::Op::SetShReg, 5, true) == 0xC0047602u);
    REQUIRE(pm4::header3(pm4::Op::DispatchDirect, 4, true) == 0xC0031502u);
}

TEST_CASE("builder packets, SET_SH_REG and padding", "[pm4]") {
    pm4::Builder b;
    b.set_sh_reg(0x204, {1, 2, 3});
    REQUIRE(b.dwords() == std::vector<std::uint32_t>{0xC0037602u, 0x204, 1, 2, 3});
    b.pad_to_multiple(8);
    REQUIRE(b.size() == 8);
    REQUIRE(b.dwords()[5] == pm4::kNopFiller);
    REQUIRE_THROWS_AS(b.packet(pm4::Op::Nop, {}), std::invalid_argument);
    REQUIRE_THROWS_AS(b.pad_to_multiple(0), std::invalid_argument);
}

TEST_CASE("memset IB reproduces the IGT gfx10 sequence", "[dispatch-min]") {
    dispatch_min::MemsetParams p;
    p.shader_va = 0x0000'0001'0000'0000ull;
    p.dst_va = 0x0000'0002'0000'1000ull;
    const auto ib = dispatch_min::build_memset_ib(p);

    REQUIRE(ib.size() % 8 == 0);
    // Starts with CONTEXT_CONTROL on the GFX ring.
    REQUIRE(ib[0] == 0xC0012800u);
    REQUIRE(ib[1] == 0x80000000u);

    auto find = [&](std::uint32_t header, std::uint32_t first) {
        for (std::size_t i = 0; i + 1 < ib.size(); ++i) {
            if (ib[i] == header && ib[i + 1] == first) return i;
        }
        return ib.size();
    };
    // COMPUTE_PGM_LO/HI = VA >> 8, VA >> 40.
    const auto pgm = find(0xC0027602u, 0x20c);
    REQUIRE(pgm < ib.size());
    REQUIRE(ib[pgm + 2] == 0x01000000u);
    REQUIRE(ib[pgm + 3] == 0u);
    // User data: V# words and value.
    const auto ud = find(0xC0047602u, 0x240);
    REQUIRE(ud < ib.size());
    REQUIRE(ib[ud + 2] == 0x00001000u);
    REQUIRE(ib[ud + 3] == (0x2u | 0x100000u));
    REQUIRE(ib[ud + 4] == 16384u / 16u);
    REQUIRE(ib[ud + 5] == 0x1104bfacu);
    // DISPATCH_DIRECT with 16 groups for 16 KiB.
    const auto disp = find(0xC0031502u, 0x10);
    REQUIRE(disp < ib.size());
    REQUIRE(ib[disp + 2] == 16u);
    REQUIRE(ib[disp + 3] == 1u);
    // CU masks: every SE fully enabled.
    REQUIRE(find(0xC0029B02u, 0x30000216u) < ib.size());
    REQUIRE(find(0xC0029B02u, 0x219u) < ib.size());
    // Only NOP fillers after the dispatch.
    REQUIRE(std::all_of(ib.begin() + static_cast<std::ptrdiff_t>(disp + 5), ib.end(),
                        [](std::uint32_t d) { return d == pm4::kNopFiller; }));
}

TEST_CASE("memset IB rejects bad parameters", "[dispatch-min]") {
    dispatch_min::MemsetParams p;
    p.shader_va = 0x100;
    p.dst_va = 0x1000;
    p.shader_va = 0x180;
    REQUIRE_THROWS_AS(dispatch_min::build_memset_ib(p), std::invalid_argument);
    p.shader_va = 0x100;
    p.dst_va = 0x1008;
    REQUIRE_THROWS_AS(dispatch_min::build_memset_ib(p), std::invalid_argument);
    p.dst_va = 0x1000;
    p.dst_bytes = 1000;
    REQUIRE_THROWS_AS(dispatch_min::build_memset_ib(p), std::invalid_argument);
    p.dst_bytes = 2048;
    p.gfx_ring = false;
    const auto ib = dispatch_min::build_memset_ib(p);
    REQUIRE(ib[0] != 0xC0012800u); // no CONTEXT_CONTROL outside the GFX ring
}

TEST_CASE("the shader is the IGT gfx10 buffer-clear program", "[dispatch-min]") {
    REQUIRE(dispatch_min::kBufferClearCsGfx10.front() == 0xD7460004u);
    REQUIRE(dispatch_min::kBufferClearCsGfx10.back() == 0xBF810000u); // s_endpgm
}
