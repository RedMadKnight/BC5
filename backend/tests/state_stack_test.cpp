// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/policy.hpp"
#include "bc5/state_stack.hpp"

#include <catch2/catch_test_macros.hpp>

#include <cstdint>
#include <vector>

using namespace bc5;

namespace {

std::vector<std::uint32_t> filtered_of(const std::vector<std::uint32_t> &src) {
    std::vector<std::uint32_t> out(src.size());
    policy::FilterStats st;
    policy::filter(policy::Policy::builtin(), src, out, policy::FilterOptions{}, st);
    return out;
}

const state_stack::Tracker::Readable kAll = [](std::uint64_t, std::uint64_t) { return true; };

} // namespace

TEST_CASE("state stack: a pop restores the context registers of the matching push", "[state_stack]") {
    // the game state, a push, the internal draw with its own state, a pop
    static const std::uint32_t table[] = {0x103, 0xffffffffu, 0x318, 0x05093f00u}; // (offset, value)
    const auto ta = reinterpret_cast<std::uint64_t>(&table[0]);
    const std::vector<std::uint32_t> src = {
        0xC0026900u, 0x200, 0x11111111u, 0x22222222u, // SET_CONTEXT_REG 0x200..0x201
        0xC0039F00u, static_cast<std::uint32_t>(ta), static_cast<std::uint32_t>(ta >> 32), 0x80000000u, 2,
        0xC0001200u, 1,                  // CLEAR_STATE push
        0xC0016900u, 0x103, 0,           // the internal draw: its own state
        0xC0016900u, 0x200, 0x33333333u, //
        0xC0001200u, 2,                  // CLEAR_STATE pop
        0xC0016900u, 0x2a0, 0x44444444u,
    };
    const auto filtered = filtered_of(src);
    REQUIRE(filtered[9] == 0xC0001200u);
    REQUIRE(filtered[10] == 0); // the policy rewrite: cmd 0
    state_stack::Tracker t;
    state_stack::Stats st;
    const auto out = t.apply(src, filtered, kAll, st);
    CHECK(st.pushes == 1);
    CHECK(st.pops == 1);
    CHECK(st.tables == 1);
    CHECK(st.restored_regs == 4);
    for (std::size_t k = 0; k < 17; ++k) CHECK(out[k] == filtered[k]); // up to the pop: unchanged
    // the pop: two NOPs, then one SET_CONTEXT_REG per run (0x103; 0x200..0x201; 0x318)
    const std::vector<std::uint32_t> expect = {
        policy::kNop, policy::kNop,
        0xC0016900u, 0x103, 0xffffffffu,
        0xC0026900u, 0x200, 0x11111111u, 0x22222222u,
        0xC0016900u, 0x318, 0x05093f00u,
        0xC0016900u, 0x2a0, 0x44444444u,
    };
    REQUIRE(out.size() == 17 + expect.size());
    for (std::size_t k = 0; k < expect.size(); ++k) CHECK(out[17 + k] == expect[k]);
    CHECK(st.inserted_dwords == out.size() - src.size());
    CHECK(t.depth() == 0);
    CHECK(t.context().valid.test(0x2a0));
    CHECK(t.context().value[0x103] == 0xffffffffu);
}

TEST_CASE("state stack: conditional and unmatched pops are left to the filter", "[state_stack]") {
    const std::vector<std::uint32_t> src = {
        0xC0016900u, 0x200, 0x11111111u,
        0xC0032200u, 0x1000, 0, 0, 2, // COND_EXEC: the next 2 dwords
        0xC0001200u, 2,               // conditional pop
        0xC0001200u, 2,               // unconditional pop, empty stack
    };
    const auto filtered = filtered_of(src);
    state_stack::Tracker t;
    state_stack::Stats st;
    const auto out = t.apply(src, filtered, kAll, st);
    CHECK(out == filtered);
    CHECK(st.conditional == 1);
    CHECK(st.unmatched_pops == 1);
    CHECK(st.pops == 0);
    CHECK(st.inserted_dwords == 0);
    CHECK(!t.context().valid.test(0x200)); // the unmatched pop ran as the kernel clear state
}

TEST_CASE("state stack: state carries over to the next IB, unreadable tables are counted", "[state_stack]") {
    state_stack::Tracker t;
    state_stack::Stats st;
    const std::vector<std::uint32_t> a = {0xC0016900u, 0x10, 0xaaaaaaaau, 0xC0001200u, 1};
    t.apply(a, filtered_of(a), kAll, st);
    CHECK(t.depth() == 1);
    const std::vector<std::uint32_t> b = {
        0xC0039F00u, 0x4000, 0x1, 0x80000000u, 4, // a table the caller does not vouch for
        0xC0001200u, 2,
    };
    const state_stack::Tracker::Readable none = [](std::uint64_t, std::uint64_t) { return false; };
    const auto out = t.apply(b, filtered_of(b), none, st);
    CHECK(st.unreadable_tables == 1);
    CHECK(st.pops == 1);
    REQUIRE(out.size() == b.size() + 3);
    CHECK(out[7] == 0xC0016900u);
    CHECK(out[8] == 0x10);
    CHECK(out[9] == 0xaaaaaaaau);
}
