// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/policy.hpp"

#include <catch2/catch_test_macros.hpp>

#include <vector>

using namespace bc5;

TEST_CASE("the shipped policy table parses and has the known entries", "[policy]") {
    const auto &p = policy::Policy::builtin();
    REQUIRE(p.op(0x10) == policy::Verdict::Pass);      // NOP
    REQUIRE(p.op(0x8e) == policy::Verdict::Drop);      // GET_LOD_STATS
    REQUIRE(p.op(0xee) == policy::Verdict::Drop);      // unreviewed → default
    REQUIRE(p.op(0x49) == policy::Verdict::Rewrite);   // RELEASE_MEM
    REQUIRE(p.type0() == policy::Verdict::Drop);
    REQUIRE(p.reg(0x2e16) == policy::Verdict::Rewrite); // COMPUTE_STATIC_THREAD_MGMT_SE0
    REQUIRE(p.reg(0xc342) == policy::Verdict::Drop);    // SQ_THREAD_TRACE_USERDATA_2
    REQUIRE(p.reg(0x2e80) == policy::Verdict::Drop);
    REQUIRE(p.reg(0xa000) == policy::Verdict::Pass);
}

TEST_CASE("SET_*_REG packets take the verdict of their registers", "[policy]") {
    const auto &p = policy::Policy::builtin();
    const std::uint32_t user_data[] = {0xC0027600u, 0x240u, 1u, 2u};
    REQUIRE(p.packet(user_data, 4) == policy::Verdict::Pass);
    const std::uint32_t masks[] = {0xC0029B00u, 0x30000216u, 0xffffffffu, 0xffffffffu};
    REQUIRE(p.packet(masks, 4) == policy::Verdict::Rewrite);
    const std::uint32_t mixed[] = {0xC0027600u, 0x27fu, 0u, 0u}; // 0x2e7f pass, 0x2e80 drop
    REQUIRE(p.packet(mixed, 4) == policy::Verdict::Split);
    const std::uint32_t markers[] = {0xC0027900u, 0x342u, 5u, 6u};
    REQUIRE(p.packet(markers, 4) == policy::Verdict::Drop);
}

TEST_CASE("filter NOPs dropped packets in place and rewrites masks and INT_SEL", "[policy]") {
    const auto &p = policy::Policy::builtin();
    const std::vector<std::uint32_t> src = {
        0xffff1000u,                                             // NOP filler: pass
        0xC0038E00u, 0u, 0u, 0u, 0u,                             // GET_LOD_STATS: drop (5 dwords)
        0xC0027900u, 0x342u, 5u, 6u,                             // markers: drop (4 dwords)
        0xC0029B00u, 0x30000216u, 0xffffffffu, 0xffffffffu,      // masks: rewrite
        0xC0064900u, 0x528u, 0x02000000u, 0u, 0u, 7u, 0u, 0x11u, // RELEASE_MEM INT_SEL=2: rewrite
        0xC0017600u, 0x207u, 64u,                                // NUM_THREAD_X: pass
    };
    std::vector<std::uint32_t> out(src.size());
    policy::FilterOptions opt;
    opt.cu_mask = 0x0fffffffu;
    policy::FilterStats st;
    const auto n = policy::filter(p, src, out, opt, st);
    REQUIRE(n == src.size());
    REQUIRE(st.packets == 6);
    REQUIRE(st.passed == 2);
    REQUIRE(st.dropped == 2);
    REQUIRE(st.rewritten == 2);
    REQUIRE(st.dwords_dropped == 9);
    REQUIRE(st.cu_mask_rewrites == 2);
    REQUIRE(st.int_sel_rewrites == 1);
    for (std::size_t i = 1; i < 10; ++i) REQUIRE(out[i] == policy::kNop);
    REQUIRE(out[12] == 0x0fffffffu);
    REQUIRE(out[13] == 0x0fffffffu);
    REQUIRE(out[16] == 0u); // INT_SEL cleared
    REQUIRE(out[21] == 0x11u);
    REQUIRE(out[22] == 0xC0017600u);
    REQUIRE(out[24] == 64u);
}

TEST_CASE("filter NOPs a packet that runs past the end", "[policy]") {
    const auto &p = policy::Policy::builtin();
    const std::vector<std::uint32_t> src = {0xC0027600u, 0x240u, 1u}; // claims 4 dwords, has 3
    std::vector<std::uint32_t> out(src.size());
    policy::FilterOptions opt;
    policy::FilterStats st;
    policy::filter(p, src, out, opt, st);
    REQUIRE(st.truncated == 1);
    for (auto w : out) REQUIRE(w == policy::kNop);
}
