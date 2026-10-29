// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/indirect_check.hpp"

#include <catch2/catch_test_macros.hpp>

#include <algorithm>
#include <cstdint>
#include <vector>

using namespace bc5;

namespace {
constexpr std::uint32_t kMax[3] = {1u << 20, 1u << 10, 1u << 10};
constexpr std::uint32_t kDrawMax[2] = {1u << 22, 1024};
constexpr std::uint32_t kNop = 0xC0001000u;              // PKT3(NOP, 0, 0) + one dword
constexpr std::uint32_t kDispatchIndirect = 0xC0011600u; // PKT3(DISPATCH_INDIRECT, 1, 0)
} // namespace

TEST_CASE("indirect_check: a dispatch with a known base gets the CP check", "[indirect_check]") {
    // SET_BASE index 1 = 0x12_3456_7000, then DISPATCH_INDIRECT offset 0x40, initiator 0x41.
    const std::vector<std::uint32_t> ib = {0xC0021100u,       1u,    0x34567000u, 0x12u,
                                           kDispatchIndirect, 0x40u, 0x41u};
    std::vector<std::size_t> refs;
    indirect_check::Stats st;
    auto out = indirect_check::apply(ib, 0, kMax, kDrawMax, refs, st);
    REQUIRE(st.checked == 1);
    REQUIRE(out.size() == ib.size() + indirect_check::kCheckDwords);
    CHECK(st.inserted_dwords == indirect_check::kCheckDwords);
    REQUIRE(refs.size() == 6); // flag = 1, three COND_WRITEs, the confirm word, COND_EXEC
    indirect_check::patch(out, refs, 0x1000'0000'2000ull);
    std::size_t i = 4;
    CHECK(out[i] == 0xC0033700u); // WRITE_DATA flag = 1
    CHECK(out[i + 2] == 0x2000u);
    CHECK(out[i + 3] == 0x1000u);
    CHECK(out[i + 4] == 1u);
    i += 5;
    for (std::uint32_t k = 0; k < 3; ++k, i += 9) {
        CHECK(out[i] == 0xC0074500u);               // COND_WRITE
        CHECK(out[i + 1] == (6u | 0x10u | 0x100u)); // greater, memory poll, memory write
        CHECK(out[i + 2] == 0x34567040u + 4 * k);   // the argument dword k
        CHECK(out[i + 3] == 0x12u);
        CHECK(out[i + 4] == kMax[k]);
        CHECK(out[i + 6] == 0x2000u); // writes the flag
        CHECK(out[i + 8] == 0u);
    }
    CHECK(out[i] == 0xC0033700u); // WRITE_DATA with WR_CONFIRM to the word after the flag
    CHECK(out[i + 1] == ((5u << 8) | (1u << 20)));
    CHECK(out[i + 2] == 0x2004u);
    i += 5;
    CHECK(out[i] == 0xC0004200u); // PFP_SYNC_ME
    i += 2;
    CHECK(out[i] == 0xC0032200u); // COND_EXEC flag, 3 dwords
    CHECK(out[i + 1] == 0x2000u);
    CHECK(out[i + 4] == 3u);
    i += 5;
    CHECK(out[i] == kDispatchIndirect);
    CHECK(out[i + 1] == 0x40u);
}

TEST_CASE("indirect_check: the caller's base, no base, and the IB's own COND_EXEC",
          "[indirect_check]") {
    const std::vector<std::uint32_t> ib = {kDispatchIndirect, 0x40u, 0x41u, kNop, 0u};
    {
        std::vector<std::size_t> refs;
        indirect_check::Stats st;
        auto out = indirect_check::apply(ib, 0x2'0000'0000ull, kMax, kDrawMax, refs, st);
        CHECK(st.checked == 1);
        CHECK(out[7] == 0x40u); // the first COND_WRITE (after WRITE_DATA) polls base + offset
        CHECK(out[8] == 0x2u);
    }
    {
        std::vector<std::size_t> refs;
        indirect_check::Stats st;
        auto out = indirect_check::apply(ib, 0, kMax, kDrawMax, refs, st);
        CHECK(st.checked == 0);
        CHECK(st.unbased == 1);
        CHECK(refs.empty());
        REQUIRE(out.size() == ib.size() + 2);
        CHECK(out[0] == 0xC0004200u);
        CHECK(out[2] == kDispatchIndirect);
    }
    {
        // The IB's own COND_EXEC over the dispatch: its count grows by the check.
        std::vector<std::uint32_t> cond = ib;
        cond.insert(cond.begin(), {0xC0032200u, 0x1000u, 0u, 0u, 3u});
        std::vector<std::size_t> refs;
        indirect_check::Stats st;
        auto out = indirect_check::apply(cond, 0x2'0000'0000ull, kMax, kDrawMax, refs, st);
        CHECK(st.checked == 1);
        REQUIRE(out.size() == cond.size() + indirect_check::kCheckDwords);
        CHECK(out[0] == 0xC0032200u);
        CHECK(out[4] == 3u + indirect_check::kCheckDwords);
        CHECK(out[5 + indirect_check::kCheckDwords] == kDispatchIndirect);
        // A COND_EXEC whose range ends before the dispatch keeps its count.
        std::vector<std::uint32_t> before = {0xC0032200u, 0x1000u, 0u, 0u, 2u, kNop, 0u};
        before.insert(before.end(), ib.begin(), ib.end());
        refs.clear();
        out = indirect_check::apply(before, 0x2'0000'0000ull, kMax, kDrawMax, refs, st);
        CHECK(out[4] == 2u);
    }
}

TEST_CASE("indirect_check: a COND_EXEC range whose grown count overflows drops only its own "
          "dispatches (ADR 0010 section A)",
          "[indirect_check]") {
    // A range of 0x3fff - 10 dwords (one long NOP, then a dispatch) grows past 14 bits with the
    // check; the dispatch after the range is checked as usual. The whole IB used to be NOP-ed.
    const std::uint32_t nop_len = 0x3fffu - 10u - 3u; // dwords of the filler NOP packet
    std::vector<std::uint32_t> ib = {0xC0032200u, 0x1000u, 0u, 0u, nop_len + 3u};
    ib.push_back(0xC0001000u | ((nop_len - 2u) << 16)); // PKT3(NOP, nop_len - 2, 0)
    ib.resize(ib.size() + nop_len - 1, 0u);
    const std::size_t inside = ib.size();
    ib.insert(ib.end(), {kDispatchIndirect, 0x40u, 0x41u});
    const std::size_t outside = ib.size();
    ib.insert(ib.end(), {kDispatchIndirect, 0x80u, 0x41u});
    std::vector<std::size_t> refs;
    indirect_check::Stats st;
    auto out = indirect_check::apply(ib, 0x2'0000'0000ull, kMax, kDrawMax, refs, st);
    CHECK(st.conditional == 1);
    CHECK(st.checked == 1);
    REQUIRE(out.size() == ib.size() + indirect_check::kCheckDwords);
    CHECK(out[4] == nop_len + 3u); // the range's count is unchanged: nothing was inserted in it
    CHECK(out[inside] == 0xC0011000u);                                    // NOP-ed, 3 dwords
    CHECK(out[outside + indirect_check::kCheckDwords] == kDispatchIndirect); // checked
    CHECK(out[outside] == 0xC0033700u); // its check starts with WRITE_DATA
    REQUIRE(refs.size() == 6);
}

TEST_CASE("insert_before: packets inserted, COND_EXEC counts grown around them",
          "[indirect_check]") {
    // COND_EXEC over NOP(2 dwords) + dispatch (3 dwords), then a dispatch outside its range.
    std::vector<std::uint32_t> ib = {
        0xC0032200u, 0x1000u,           0u,    0u,   5u, kNop, 0u, kDispatchIndirect, 0x40u,
        0x41u,       kDispatchIndirect, 0x80u, 0x41u};
    const std::vector<std::uint32_t> wait = {0xC0055000u, 0xE0300000u, 0u, 0u, 0u, 0u, 0u};
    REQUIRE(indirect_check::insert_before(ib, {{7, wait}, {10, wait}}));
    REQUIRE(ib.size() == 13 + 14);
    CHECK(ib[4] == 5u + 7u); // only the first wait lies in the range
    CHECK(ib[7] == 0xC0055000u);
    CHECK(ib[14] == kDispatchIndirect);
    CHECK(ib[17] == 0xC0055000u);
    CHECK(ib[24] == kDispatchIndirect);
}

TEST_CASE("indirect_check: indirect draws get the check of their two counts", "[indirect_check]") {
    // SET_BASE index 1, DRAW_INDIRECT (offset 0x20, two SH register offsets, initiator).
    const std::vector<std::uint32_t> ib = {0xC0021100u, 1u,    0x1000u, 0x12u, 0xC0032400u,
                                           0x20u,       0x4cu, 0x4du,   2u};
    std::vector<std::size_t> refs;
    indirect_check::Stats st;
    auto out = indirect_check::apply(ib, 0, kMax, kDrawMax, refs, st);
    REQUIRE(st.checked == 1);
    REQUIRE(out.size() == ib.size() + indirect_check::kDrawCheckDwords);
    CHECK(refs.size() == 5);
    CHECK(out[4 + 5] == 0xC0074500u); // COND_WRITE on the vertex count
    CHECK(out[4 + 5 + 2] == 0x1020u);
    CHECK(out[4 + 5 + 4] == (1u << 22));
    CHECK(out[4 + 14 + 2] == 0x1024u); // and on the instance count
    CHECK(out[4 + 14 + 4] == 1024u);
    const std::size_t cond = 4 + indirect_check::kDrawCheckDwords - 5;
    CHECK(out[cond] == 0xC0032200u);
    CHECK(out[cond + 4] == 5u); // COND_EXEC over the 5-dword draw
    CHECK(out[cond + 5] == 0xC0032400u);
}

TEST_CASE("indirect_check: on a compute ring the MEC form is checked, without PFP_SYNC_ME",
          "[indirect_check]") {
    // DISPATCH_INDIRECT, MEC form: address 0x12_3456_7040, initiator 0x41.
    const std::vector<std::uint32_t> ib = {0xC0021600u, 0x34567040u, 0x12u, 0x41u};
    std::vector<std::size_t> refs;
    indirect_check::Stats st;
    auto out = indirect_check::apply(ib, 0, kMax, kDrawMax, refs, st, true);
    REQUIRE(st.checked == 1);
    REQUIRE(out.size() == ib.size() + indirect_check::kCheckDwords - 2);
    std::size_t i = 5;
    for (std::uint32_t k = 0; k < 3; ++k, i += 9) {
        CHECK(out[i] == 0xC0074500u);
        CHECK(out[i + 2] == 0x34567040u + 4 * k);
        CHECK(out[i + 3] == 0x12u);
    }
    i += 5;                       // the confirming WRITE_DATA
    CHECK(out[i] == 0xC0032200u); // COND_EXEC right after it
    CHECK(out[i + 4] == 4u);      // skips the 4-dword dispatch
    for (const auto w : out) CHECK(w != 0xC0004200u);
    // the GFX form is not a compute-ring dispatch: left alone
    const std::vector<std::uint32_t> gfx = {0xC0021100u, 1u, 0x34567000u, 0x12u, kDispatchIndirect, 0x40u, 0x41u};
    indirect_check::Stats st2;
    std::vector<std::size_t> refs2;
    CHECK(indirect_check::apply(gfx, 0, kMax, kDrawMax, refs2, st2, true) == gfx);
}

TEST_CASE("indirect_check: the product staircase (experiment 0341)", "[indirect_check]") {
    // SET_BASE index 1 = 0x12_3456_7000, then DISPATCH_INDIRECT offset 0x40, initiator 0x41.
    const std::vector<std::uint32_t> ib = {0xC0021100u,       1u,    0x34567000u, 0x12u,
                                           kDispatchIndirect, 0x40u, 0x41u};
    std::vector<std::size_t> refs;
    indirect_check::Stats st;
    const indirect_check::ProductLimit product{1u << 16, 1};
    auto out = indirect_check::apply(ib, 0, kMax, kDrawMax, refs, st, false, &product);
    REQUIRE(st.checked == 1);
    CHECK(st.product_checked == 1);
    REQUIRE(out.size() == ib.size() + indirect_check::kCheckDwords + indirect_check::kProductDwords);
    REQUIRE(refs.size() == 12);
    indirect_check::patch(out, refs, 0x1000'0000'2000ull);
    std::size_t i = 4;
    CHECK(out[i] == 0xC0033700u); // flag = 1
    CHECK(out[i + 2] == 0x2000u);
    CHECK(out[i + 4] == 1u);
    i += 5;
    CHECK(out[i] == 0xC0033700u); // flag2 = 0
    CHECK(out[i + 2] == 0x2008u);
    CHECK(out[i + 3] == 0x1000u);
    CHECK(out[i + 4] == 0u);
    i += 5;
    for (std::uint32_t k = 0; k < 3; ++k, i += 9) { // the per-dimension checks
        CHECK(out[i] == 0xC0074500u);
        CHECK(out[i + 2] == 0x34567040u + 4 * k);
        CHECK(out[i + 4] == kMax[k]);
        CHECK(out[i + 6] == 0x2000u);
        CHECK(out[i + 8] == 0u);
    }
    for (std::uint32_t k = 1; k < 3; ++k, i += 9) { // y, z > 1 ? flag2 = 1
        CHECK(out[i] == 0xC0074500u);
        CHECK(out[i + 1] == (6u | 0x10u | 0x100u));
        CHECK(out[i + 2] == 0x34567040u + 4 * k);
        CHECK(out[i + 3] == 0x12u);
        CHECK(out[i + 4] == 1u);
        CHECK(out[i + 6] == 0x2008u);
        CHECK(out[i + 8] == 1u);
    }
    CHECK(out[i] == 0xC0033700u); // confirm2
    CHECK(out[i + 1] == ((5u << 8) | (1u << 20)));
    CHECK(out[i + 2] == 0x200cu);
    i += 5;
    CHECK(out[i] == 0xC0004200u); // PFP_SYNC_ME
    i += 2;
    CHECK(out[i] == 0xC0032200u); // COND_EXEC flag2 over the x check
    CHECK(out[i + 1] == 0x2008u);
    CHECK(out[i + 4] == 9u);
    i += 5;
    CHECK(out[i] == 0xC0074500u); // x > 2^16 ? flag = 0
    CHECK(out[i + 2] == 0x34567040u);
    CHECK(out[i + 4] == (1u << 16));
    CHECK(out[i + 6] == 0x2000u);
    CHECK(out[i + 8] == 0u);
    i += 9;
    CHECK(out[i] == 0xC0033700u); // the check's confirm
    CHECK(out[i + 2] == 0x2004u);
    i += 5;
    CHECK(out[i] == 0xC0004200u);
    i += 2;
    CHECK(out[i] == 0xC0032200u); // COND_EXEC flag over the dispatch
    CHECK(out[i + 1] == 0x2000u);
    CHECK(out[i + 4] == 3u);
    i += 5;
    CHECK(out[i] == kDispatchIndirect);
    // without the staircase nothing changes
    std::vector<std::size_t> refs2;
    indirect_check::Stats st2;
    auto plain = indirect_check::apply(ib, 0, kMax, kDrawMax, refs2, st2);
    CHECK(plain.size() == ib.size() + indirect_check::kCheckDwords);
    CHECK(st2.product_checked == 0);
    // an indirect draw gets no staircase
    const std::vector<std::uint32_t> draw = {0xC0021100u, 1u, 0x1000u, 0x12u, 0xC0032400u, 0x20u, 0x4cu, 0x4du, 2u};
    std::vector<std::size_t> refs3;
    indirect_check::Stats st3;
    auto d = indirect_check::apply(draw, 0, kMax, kDrawMax, refs3, st3, false, &product);
    CHECK(d.size() == draw.size() + indirect_check::kDrawCheckDwords);
    CHECK(st3.product_checked == 0);
}

TEST_CASE("insert_before: an insert at the IB's end is appended (experiment 0341)", "[indirect_check]") {
    std::vector<std::uint32_t> ib = {0xC0032200u, 0x1000u, 0u, 0u, 2u, kNop, 0u};
    const std::vector<std::uint32_t> tail = {kNop, 0u};
    REQUIRE(indirect_check::insert_before(ib, {{7, tail}}));
    REQUIRE(ib.size() == 9);
    CHECK(ib[4] == 2u); // the range does not grow: the insert lies after it
    CHECK(ib[7] == kNop);
}

TEST_CASE("indirect_check: the zero-dimension guard (experiment 0380)", "[indirect_check]") {
    // SET_BASE index 1 = 0x12_3456_7000, then DISPATCH_INDIRECT offset 0x40, initiator 0x41.
    const std::vector<std::uint32_t> ib = {0xC0021100u,       1u,    0x34567000u, 0x12u,
                                           kDispatchIndirect, 0x40u, 0x41u};
    std::vector<std::size_t> refs;
    indirect_check::Stats st;
    auto out = indirect_check::apply(ib, 0, kMax, kDrawMax, refs, st, false, nullptr, true);
    REQUIRE(st.checked == 1);
    CHECK(st.zero_checked == 1);
    REQUIRE(out.size() == ib.size() + indirect_check::kCheckDwords + indirect_check::kZeroDwords);
    CHECK(st.inserted_dwords == indirect_check::kCheckDwords + indirect_check::kZeroDwords);
    REQUIRE(refs.size() == 9); // flag = 1, six COND_WRITEs, the confirm word, COND_EXEC
    indirect_check::patch(out, refs, 0x1000'0000'2000ull);
    std::size_t i = 4;
    CHECK(out[i] == 0xC0033700u); // flag = 1
    CHECK(out[i + 4] == 1u);
    i += 5;
    for (std::uint32_t k = 0; k < 3; ++k, i += 9) { // the per-dimension limits, unchanged
        CHECK(out[i] == 0xC0074500u);
        CHECK(out[i + 1] == (6u | 0x10u | 0x100u));
        CHECK(out[i + 2] == 0x34567040u + 4 * k);
        CHECK(out[i + 4] == kMax[k]);
    }
    for (std::uint32_t k = 0; k < 3; ++k, i += 9) { // x, y, z == 0 ? flag = 0
        CHECK(out[i] == 0xC0074500u);
        CHECK(out[i + 1] == (3u | 0x10u | 0x100u)); // equal, memory poll, memory write
        CHECK(out[i + 2] == 0x34567040u + 4 * k);
        CHECK(out[i + 3] == 0x12u);
        CHECK(out[i + 4] == 0u);          // reference 0
        CHECK(out[i + 5] == 0xffffffffu); // mask
        CHECK(out[i + 6] == 0x2000u);     // writes the flag
        CHECK(out[i + 7] == 0x1000u);
        CHECK(out[i + 8] == 0u);
    }
    CHECK(out[i] == 0xC0033700u); // the confirm
    CHECK(out[i + 2] == 0x2004u);
    i += 5;
    CHECK(out[i] == 0xC0004200u); // PFP_SYNC_ME
    i += 2;
    CHECK(out[i] == 0xC0032200u); // COND_EXEC flag, 3 dwords
    CHECK(out[i + 1] == 0x2000u);
    CHECK(out[i + 4] == 3u);
    i += 5;
    CHECK(out[i] == kDispatchIndirect);
    CHECK(i + 3 == out.size());

    SECTION("off by default: the IB is the plain check") {
        std::vector<std::size_t> refs2;
        indirect_check::Stats st2;
        auto plain = indirect_check::apply(ib, 0, kMax, kDrawMax, refs2, st2);
        CHECK(plain.size() == ib.size() + indirect_check::kCheckDwords);
        CHECK(st2.zero_checked == 0);
    }
    SECTION("with the staircase: both, the staircase after the guard") {
        std::vector<std::size_t> refs2;
        indirect_check::Stats st2;
        const indirect_check::ProductLimit product{1u << 16, 1};
        auto both = indirect_check::apply(ib, 0, kMax, kDrawMax, refs2, st2, false, &product, true);
        CHECK(both.size() == ib.size() + indirect_check::kCheckDwords +
                                 indirect_check::kProductDwords + indirect_check::kZeroDwords);
        CHECK(st2.zero_checked == 1);
        CHECK(st2.product_checked == 1);
        CHECK(refs2.size() == 15);
        const std::size_t g = 4 + 5 + 5 + 3 * 9; // flag, flag2, the three limits
        CHECK(both[g + 1] == (3u | 0x10u | 0x100u));
        CHECK(both[g + 27 + 1] == (6u | 0x10u | 0x100u)); // then y > yz_min
    }
    SECTION("on a compute ring: the MEC form, its own address") {
        const std::vector<std::uint32_t> mec = {0xC0021600u, 0x34567040u, 0x12u, 0x41u};
        std::vector<std::size_t> refs2;
        indirect_check::Stats st2;
        auto m = indirect_check::apply(mec, 0, kMax, kDrawMax, refs2, st2, true, nullptr, true);
        CHECK(st2.zero_checked == 1);
        CHECK(m.size() == mec.size() + indirect_check::kCheckDwords - 2 + indirect_check::kZeroDwords);
        const std::size_t g = 5 + 3 * 9;
        CHECK(m[g + 1] == (3u | 0x10u | 0x100u));
        CHECK(m[g + 2] == 0x34567040u);
        CHECK(m[g + 9 + 2] == 0x34567044u);
    }
    SECTION("indirect draws get no guard") {
        const std::vector<std::uint32_t> draw = {0xC0021100u, 1u,    0x1000u, 0x12u, 0xC0032400u,
                                                 0x20u,       0x4cu, 0x4du,   2u};
        std::vector<std::size_t> refs2;
        indirect_check::Stats st2;
        auto d = indirect_check::apply(draw, 0, kMax, kDrawMax, refs2, st2, false, nullptr, true);
        CHECK(d.size() == draw.size() + indirect_check::kDrawCheckDwords);
        CHECK(st2.zero_checked == 0);
    }
    SECTION("inside the IB's own COND_EXEC: its count grows by the guard too") {
        // COND_EXEC (addr, 0, 7 dwords) over SET_BASE + DISPATCH_INDIRECT.
        std::vector<std::uint32_t> c = {0xC0032200u, 0x100u, 0x12u, 0u, 7u};
        c.insert(c.end(), ib.begin(), ib.end());
        std::vector<std::size_t> refs2;
        indirect_check::Stats st2;
        auto o = indirect_check::apply(c, 0, kMax, kDrawMax, refs2, st2, false, nullptr, true);
        CHECK(o[4] == 7u + indirect_check::kCheckDwords + indirect_check::kZeroDwords);
    }
}

TEST_CASE("indirect_check: FORCE_START_AT_000 on indirect dispatches (experiment 0380)", "[indirect_check]") {
    // SET_BASE index 1 = 0x12_3456_7000, then DISPATCH_INDIRECT offset 0x40, initiator 0x41.
    const std::vector<std::uint32_t> ib = {0xC0021100u,       1u,    0x34567000u, 0x12u,
                                           kDispatchIndirect, 0x40u, 0x41u};
    std::vector<std::size_t> refs;
    indirect_check::Stats st;
    auto out = indirect_check::apply(ib, 0, kMax, kDrawMax, refs, st, false, nullptr, false, true);
    REQUIRE(out.size() == ib.size() + indirect_check::kCheckDwords); // no packet added
    CHECK(st.start_forced == 1);
    CHECK(out[out.size() - 3] == kDispatchIndirect);
    CHECK(out[out.size() - 2] == 0x40u);
    CHECK(out[out.size() - 1] == 0x45u); // 0x41 | FORCE_START_AT_000
    // the check before it is the plain one, byte for byte
    std::vector<std::size_t> refs0;
    indirect_check::Stats st0;
    auto plain = indirect_check::apply(ib, 0, kMax, kDrawMax, refs0, st0);
    CHECK(st0.start_forced == 0);
    CHECK(plain.back() == 0x41u);
    CHECK(std::vector<std::uint32_t>(out.begin(), out.end() - 1) ==
          std::vector<std::uint32_t>(plain.begin(), plain.end() - 1));

    SECTION("an initiator that has the bit is left alone and not counted") {
        auto has = ib;
        has.back() = 0x8045u;
        std::vector<std::size_t> r;
        indirect_check::Stats s;
        auto o = indirect_check::apply(has, 0, kMax, kDrawMax, r, s, false, nullptr, false, true);
        CHECK(o.back() == 0x8045u);
        CHECK(s.start_forced == 0);
    }
    SECTION("a dispatch without a known base: PFP_SYNC_ME and the bit") {
        const std::vector<std::uint32_t> unbased = {kDispatchIndirect, 0x40u, 0x8041u};
        std::vector<std::size_t> r;
        indirect_check::Stats s;
        auto o = indirect_check::apply(unbased, 0, kMax, kDrawMax, r, s, false, nullptr, false, true);
        CHECK(s.unbased == 1);
        CHECK(s.start_forced == 1);
        CHECK(o == std::vector<std::uint32_t>{0xC0004200u, 0u, kDispatchIndirect, 0x40u, 0x8045u});
    }
    SECTION("the MEC form: its initiator is its fourth dword") {
        const std::vector<std::uint32_t> mec = {0xC0021600u, 0x34567040u, 0x12u, 0x61u};
        std::vector<std::size_t> r;
        indirect_check::Stats s;
        auto o = indirect_check::apply(mec, 0, kMax, kDrawMax, r, s, true, nullptr, false, true);
        CHECK(s.start_forced == 1);
        CHECK(o[o.size() - 4] == 0xC0021600u);
        CHECK(o[o.size() - 3] == 0x34567040u);
        CHECK(o[o.size() - 2] == 0x12u);
        CHECK(o[o.size() - 1] == 0x65u);
    }
    SECTION("direct dispatches and indirect draws are not touched") {
        const std::vector<std::uint32_t> other = {0xC0031500u, 13u,         8u,   1u,   0x41u, // DISPATCH_DIRECT
                                                  0xC0021100u, 1u,          0x1000u, 0x12u,
                                                  0xC0032400u, 0x20u,       0x4cu, 0x4du, 2u}; // DRAW_INDIRECT
        std::vector<std::size_t> r;
        indirect_check::Stats s;
        auto o = indirect_check::apply(other, 0, kMax, kDrawMax, r, s, false, nullptr, false, true);
        CHECK(s.start_forced == 0);
        CHECK(o[4] == 0x41u);
        CHECK(o.back() == 2u);
    }
    SECTION("with the zero guard: both, the check grows by the guard only") {
        std::vector<std::size_t> r;
        indirect_check::Stats s;
        auto o = indirect_check::apply(ib, 0, kMax, kDrawMax, r, s, false, nullptr, true, true);
        CHECK(o.size() == ib.size() + indirect_check::kCheckDwords + indirect_check::kZeroDwords);
        CHECK(o.back() == 0x45u);
        CHECK(s.zero_checked == 1);
        CHECK(s.start_forced == 1);
    }
}

TEST_CASE("indirect_check: tighter y and z limits (experiment 0380, the 12:12 hang)", "[indirect_check]") {
    indirect_check::YzLimit l;
    CHECK_FALSE(indirect_check::parse_yz_limit(nullptr, l));
    CHECK_FALSE(indirect_check::parse_yz_limit("", l));
    CHECK_FALSE(indirect_check::parse_yz_limit("0", l));
    REQUIRE(indirect_check::parse_yz_limit("1", l));
    CHECK(l.y == 256u);
    CHECK(l.z == 64u);
    REQUIRE(indirect_check::parse_yz_limit("180", l));
    CHECK(l.y == 180u);
    CHECK(l.z == 64u);
    REQUIRE(indirect_check::parse_yz_limit("0x100:8", l));
    CHECK(l.y == 256u);
    CHECK(l.z == 8u);
    REQUIRE(indirect_check::parse_yz_limit("junk", l)); // set but unreadable: the defaults
    CHECK(l.y == 256u);
    CHECK(l.z == 64u);

    std::uint32_t max[3] = {kMax[0], kMax[1], kMax[2]};
    indirect_check::tighten(max, indirect_check::YzLimit{180, 8});
    CHECK(max[0] == kMax[0]);
    CHECK(max[1] == 180u);
    CHECK(max[2] == 8u);
    std::uint32_t low[3] = {1u << 20, 16, 2};
    indirect_check::tighten(low, indirect_check::YzLimit{180, 8}); // never raised
    CHECK(low[1] == 16u);
    CHECK(low[2] == 2u);

    // The tightened limits are what the COND_WRITEs compare against.
    const std::vector<std::uint32_t> ib = {0xC0021100u,       1u,    0x34567000u, 0x12u,
                                           kDispatchIndirect, 0x40u, 0x41u};
    std::vector<std::size_t> refs;
    indirect_check::Stats st;
    auto out = indirect_check::apply(ib, 0, max, kDrawMax, refs, st);
    REQUIRE(out.size() == ib.size() + indirect_check::kCheckDwords);
    const std::size_t i = 4 + 5;
    CHECK(out[i + 4] == kMax[0]);
    CHECK(out[i + 9 + 4] == 180u);
    CHECK(out[i + 18 + 4] == 8u);
}

TEST_CASE("indirect_check: the SET_BASE rebase before a checked dispatch (experiment 0380)", "[indirect_check]") {
    // SET_BASE index 1 = 0x12_3456_7000, INDEX_BASE, INDEX_BUFFER_SIZE, then DISPATCH_INDIRECT offset 0x40.
    const std::vector<std::uint32_t> ib = {0xC0021100u, 1u,          0x34567000u, 0x12u,  // SET_BASE 1
                                           0xC0012600u, 0x9db6280u,  0x11u,               // INDEX_BASE
                                           0xC0001300u, 0xffffffffu,                      // INDEX_BUFFER_SIZE
                                           kDispatchIndirect, 0x40u, 0x41u};
    std::vector<std::size_t> refs;
    indirect_check::Stats st;
    auto out = indirect_check::apply(ib, 0, kMax, kDrawMax, refs, st, false, nullptr, false, false, true);
    REQUIRE(st.checked == 1);
    CHECK(st.rebased == 1);
    REQUIRE(out.size() == ib.size() + indirect_check::kCheckDwords + indirect_check::kRebaseDwords);
    CHECK(st.rebased_after_index_base == 1); // the first DISPATCH_INDIRECT after the INDEX_BASE
    CHECK(st.inserted_dwords == indirect_check::kCheckDwords + indirect_check::kRebaseDwords);
    // the title's packets first, unchanged
    CHECK(std::vector<std::uint32_t>(out.begin(), out.begin() + 9) ==
          std::vector<std::uint32_t>(ib.begin(), ib.begin() + 9));
    const std::size_t d = out.size() - 3; // the dispatch
    CHECK(out[d] == kDispatchIndirect);
    CHECK(out[d + 2] == 0x41u);
    // SET_BASE index 1 with the same base right before it
    CHECK(out[d - 4] == 0xC0021100u);
    CHECK(out[d - 3] == 1u);
    CHECK(out[d - 2] == 0x34567000u);
    CHECK(out[d - 1] == 0x12u);
    // the check's COND_EXEC covers both: 4 + 3 dwords
    CHECK(out[d - 9] == 0xC0032200u);
    CHECK(out[d - 9 + 4] == 7u);
    // without the switch: the plain check, the COND_EXEC over 3 dwords
    std::vector<std::size_t> refs0;
    indirect_check::Stats st0;
    auto plain = indirect_check::apply(ib, 0, kMax, kDrawMax, refs0, st0);
    CHECK(st0.rebased == 0);
    CHECK(plain.size() == ib.size() + indirect_check::kCheckDwords);
    CHECK(plain[plain.size() - 3 - 5 + 4] == 3u);

    SECTION("the base in effect is the latest SET_BASE index 1 (index 0 is ignored)") {
        auto two = ib;
        two.insert(two.begin() + 9, {0xC0021100u, 1u, 0x55550000u, 0x13u, 0xC0021100u, 0u, 0x77770000u, 0x14u});
        std::vector<std::size_t> r;
        indirect_check::Stats s;
        auto o = indirect_check::apply(two, 0, kMax, kDrawMax, r, s, false, nullptr, false, false, true);
        const std::size_t e = o.size() - 3;
        CHECK(o[e - 2] == 0x55550000u);
        CHECK(o[e - 1] == 0x13u);
    }
    SECTION("with the zero guard, the staircase and FORCE_START: the rebase stays next to the dispatch") {
        std::vector<std::size_t> r;
        indirect_check::Stats s;
        const indirect_check::ProductLimit product{1u << 16, 1};
        auto o = indirect_check::apply(ib, 0, kMax, kDrawMax, r, s, false, &product, true, true, true);
        CHECK(o.size() == ib.size() + indirect_check::kCheckDwords + indirect_check::kProductDwords +
                               indirect_check::kZeroDwords + indirect_check::kRebaseDwords);
        const std::size_t e = o.size() - 3;
        CHECK(o[e + 2] == 0x45u);
        CHECK(o[e - 4] == 0xC0021100u);
        CHECK(o[e - 9] == 0xC0032200u);
        CHECK(o[e - 9 + 4] == 7u);
    }
    SECTION("an unbased dispatch, the MEC form and draws get no rebase") {
        const std::vector<std::uint32_t> unbased = {kDispatchIndirect, 0x40u, 0x41u};
        std::vector<std::size_t> r;
        indirect_check::Stats s;
        auto o = indirect_check::apply(unbased, 0, kMax, kDrawMax, r, s, false, nullptr, false, false, true);
        CHECK(o == std::vector<std::uint32_t>{0xC0004200u, 0u, kDispatchIndirect, 0x40u, 0x41u});
        const std::vector<std::uint32_t> mec = {0xC0021600u, 0x34567040u, 0x12u, 0x41u};
        auto m = indirect_check::apply(mec, 0, kMax, kDrawMax, r, s, true, nullptr, false, false, true);
        CHECK(m.size() == mec.size() + indirect_check::kCheckDwords - 2);
        const std::vector<std::uint32_t> draw = {0xC0021100u, 1u, 0x1000u, 0x12u, 0xC0032400u, 0x20u, 0x4cu, 0x4du, 2u};
        auto dr = indirect_check::apply(draw, 0, kMax, kDrawMax, r, s, false, nullptr, false, false, true);
        CHECK(dr.size() == draw.size() + indirect_check::kDrawCheckDwords);
        CHECK(s.rebased == 0);
    }
    SECTION("only the first dispatch after an INDEX_BASE counts as after it") {
        auto two = ib;
        two.insert(two.end(), {kDispatchIndirect, 0x80u, 0x41u});
        std::vector<std::size_t> r;
        indirect_check::Stats s;
        indirect_check::apply(two, 0, kMax, kDrawMax, r, s, false, nullptr, false, false, true);
        CHECK(s.rebased == 2);
        CHECK(s.rebased_after_index_base == 1);
    }
    SECTION("inside the IB's own COND_EXEC: its count grows by the rebase too") {
        std::vector<std::uint32_t> c = {0xC0032200u, 0x100u, 0x12u, 0u, static_cast<std::uint32_t>(ib.size())};
        c.insert(c.end(), ib.begin(), ib.end());
        std::vector<std::size_t> r;
        indirect_check::Stats s;
        auto o = indirect_check::apply(c, 0, kMax, kDrawMax, r, s, false, nullptr, false, false, true);
        CHECK(o[4] == ib.size() + indirect_check::kCheckDwords + indirect_check::kRebaseDwords);
    }
}

TEST_CASE("indirect_check: the dispatch runs from the CP's copy of its arguments (experiment 0380)", "[indirect_check]") {
    // SET_BASE index 1 = 0x12_3456_7000, INDEX_BASE, INDEX_BUFFER_SIZE, DISPATCH_INDIRECT offset 0x40, initiator 0x41.
    const std::vector<std::uint32_t> ib = {0xC0021100u, 1u,         0x34567000u, 0x12u,
                                           0xC0012600u, 0x9db6280u, 0x11u,
                                           0xC0001300u, 0xffffffffu,
                                           kDispatchIndirect, 0x40u, 0x41u};
    std::vector<std::size_t> refs;
    indirect_check::Stats st;
    auto out = indirect_check::apply(ib, 0, kMax, kDrawMax, refs, st, false, nullptr, false, false, false, true);
    REQUIRE(st.checked == 1);
    CHECK(st.args_copied == 1);
    REQUIRE(out.size() == ib.size() + indirect_check::kCheckDwords + indirect_check::kArgsCopyDwords);
    CHECK(st.inserted_dwords == indirect_check::kCheckDwords + indirect_check::kArgsCopyDwords);
    indirect_check::patch(out, refs, 0x1000'0000'2000ull);
    std::size_t i = 9;
    for (std::uint32_t k = 0; k < 3; ++k, i += 6) { // COPY_DATA args + 4k -> flag area + 16 + 4k
        CHECK(out[i] == 0xC0044000u);
        CHECK(out[i + 1] == (1u | (5u << 8) | (1u << 20))); // memory to memory, WR_CONFIRM, ME
        CHECK(out[i + 2] == 0x34567040u + 4 * k);         // the title's base + offset
        CHECK(out[i + 3] == 0x12u);
        CHECK(out[i + 4] == 0x2010u + 4 * k);
        CHECK(out[i + 5] == 0x1000u);
    }
    CHECK(out[i] == 0xC0033700u); // flag = 1
    CHECK(out[i + 2] == 0x2000u);
    i += 5;
    for (std::uint32_t k = 0; k < 3; ++k, i += 9) { // the limits, polled on the copy
        CHECK(out[i] == 0xC0074500u);
        CHECK(out[i + 1] == (6u | 0x10u | 0x100u));
        CHECK(out[i + 2] == 0x2010u + 4 * k);
        CHECK(out[i + 3] == 0x1000u);
        CHECK(out[i + 4] == kMax[k]);
        CHECK(out[i + 6] == 0x2000u);
    }
    CHECK(out[i] == 0xC0033700u); // confirm
    i += 5;
    CHECK(out[i] == 0xC0004200u); // PFP_SYNC_ME
    i += 2;
    CHECK(out[i] == 0xC0032200u); // COND_EXEC flag over SET_BASE + the dispatch
    CHECK(out[i + 4] == 7u);
    i += 5;
    CHECK(out[i] == 0xC0021100u); // SET_BASE index 1 = the copy
    CHECK(out[i + 1] == 1u);
    CHECK(out[i + 2] == 0x2010u);
    CHECK(out[i + 3] == 0x1000u);
    i += 4;
    CHECK(out[i] == kDispatchIndirect);
    CHECK(out[i + 1] == 0u); // offset 0 into the copy
    CHECK(out[i + 2] == 0x41u);
    i += 3;
    CHECK(out[i] == 0xC0021100u); // the title's base again
    CHECK(out[i + 1] == 1u);
    CHECK(out[i + 2] == 0x34567000u);
    CHECK(out[i + 3] == 0x12u);
    CHECK(i + 4 == out.size());

    SECTION("with the staircase, the zero guard, FORCE_START and rebase: all poll the copy, the copy wins over rebase") {
        std::vector<std::size_t> r;
        indirect_check::Stats s;
        const indirect_check::ProductLimit product{1u << 16, 1};
        auto o = indirect_check::apply(ib, 0, kMax, kDrawMax, r, s, false, &product, true, true, true, true);
        CHECK(o.size() == ib.size() + indirect_check::kCheckDwords + indirect_check::kProductDwords +
                               indirect_check::kZeroDwords + indirect_check::kArgsCopyDwords);
        CHECK(s.rebased == 0);
        CHECK(s.args_copied == 1);
        indirect_check::patch(o, r, 0x1000'0000'2000ull);
        std::size_t polls = 0, title_polls = 0;
        for (std::size_t j = 0; j + 8 < o.size(); ++j) {
            if (o[j] != 0xC0074500u) continue;
            if (o[j + 2] >= 0x2010u && o[j + 2] <= 0x2018u && o[j + 3] == 0x1000u) polls++;
            if ((o[j + 2] & 0xfffff000u) == 0x34567000u) title_polls++;
        }
        CHECK(polls == 3 + 3 + 2 + 1); // limits, zero guard, staircase y/z, staircase x
        CHECK(title_polls == 0);
        const std::size_t e = o.size() - 4 - 3; // the dispatch, before the restoring SET_BASE
        CHECK(o[e] == kDispatchIndirect);
        CHECK(o[e + 1] == 0u);
        CHECK(o[e + 2] == 0x45u); // FORCE_START on the dispatch's initiator, not on the SET_BASE after it
        CHECK(o.back() == 0x12u);
    }
    SECTION("off by default; unbased, MEC form and draws are untouched") {
        std::vector<std::size_t> r;
        indirect_check::Stats s;
        auto plain = indirect_check::apply(ib, 0, kMax, kDrawMax, r, s);
        CHECK(plain.size() == ib.size() + indirect_check::kCheckDwords);
        CHECK(s.args_copied == 0);
        const std::vector<std::uint32_t> unbased = {kDispatchIndirect, 0x40u, 0x41u};
        auto u = indirect_check::apply(unbased, 0, kMax, kDrawMax, r, s, false, nullptr, false, false, false, true);
        CHECK(u == std::vector<std::uint32_t>{0xC0004200u, 0u, kDispatchIndirect, 0x40u, 0x41u});
        const std::vector<std::uint32_t> mec = {0xC0021600u, 0x34567040u, 0x12u, 0x41u};
        auto m = indirect_check::apply(mec, 0, kMax, kDrawMax, r, s, true, nullptr, false, false, false, true);
        CHECK(m.size() == mec.size() + indirect_check::kCheckDwords - 2);
        const std::vector<std::uint32_t> draw = {0xC0021100u, 1u, 0x1000u, 0x12u, 0xC0032400u, 0x20u, 0x4cu, 0x4du, 2u};
        auto d = indirect_check::apply(draw, 0, kMax, kDrawMax, r, s, false, nullptr, false, false, false, true);
        CHECK(d.size() == draw.size() + indirect_check::kDrawCheckDwords);
        CHECK(s.args_copied == 0);
    }
    SECTION("inside the IB's own COND_EXEC: the restoring SET_BASE is inside the grown range") {
        std::vector<std::uint32_t> c = {0xC0032200u, 0x100u, 0x12u, 0u, static_cast<std::uint32_t>(ib.size())};
        c.insert(c.end(), ib.begin(), ib.end());
        c.push_back(kNop);
        std::vector<std::size_t> r;
        indirect_check::Stats s;
        auto o = indirect_check::apply(c, 0, kMax, kDrawMax, r, s, false, nullptr, false, false, false, true);
        CHECK(o[4] == ib.size() + indirect_check::kCheckDwords + indirect_check::kArgsCopyDwords);
        CHECK(o.back() == kNop);
        CHECK(o[5 + o[4] - 4] == 0xC0021100u); // the range ends with the restore
    }
    SECTION("two copied dispatches: each restores the base in effect for it") {
        auto two = ib;
        two.insert(two.end(), {0xC0021100u, 1u, 0x55550000u, 0x13u, kDispatchIndirect, 0x8u, 0x41u});
        std::vector<std::size_t> r;
        indirect_check::Stats s;
        auto o = indirect_check::apply(two, 0, kMax, kDrawMax, r, s, false, nullptr, false, false, false, true);
        CHECK(s.args_copied == 2);
        CHECK(o[o.size() - 2] == 0x55550000u);
        CHECK(o[o.size() - 1] == 0x13u);
        indirect_check::patch(o, r, 0x1000'0000'2000ull);
        bool second_src = false;
        for (std::size_t j = 0; j + 5 < o.size(); ++j)
            second_src = second_src || (o[j] == 0xC0044000u && o[j + 2] == 0x55550008u && o[j + 3] == 0x13u);
        CHECK(second_src); // its offset 8 is folded into the copy's source
    }
}

TEST_CASE("indirect_check: a GL2 write-back before the check (experiment 0380)", "[indirect_check]") {
    // SET_BASE index 1, INDEX_BASE, INDEX_BUFFER_SIZE, two DISPATCH_INDIRECTs.
    const std::vector<std::uint32_t> ib = {0xC0021100u, 1u,         0x34567000u, 0x12u,
                                           0xC0012600u, 0x9db6280u, 0x11u,
                                           0xC0001300u, 0xffffffffu,
                                           kDispatchIndirect, 0x40u, 0x41u,
                                           kDispatchIndirect, 0x80u, 0x41u};
    const std::vector<std::uint32_t> acquire = {0xC0065800u, 0u, 0xffffffffu, 0xffffffu, 0u, 0u, 0xAu, 1u << 15};
    const auto count = [&acquire](const std::vector<std::uint32_t> &o) {
        std::size_t n = 0;
        for (std::size_t j = 0; j + acquire.size() <= o.size(); ++j)
            n += std::equal(acquire.begin(), acquire.end(), o.begin() + static_cast<std::ptrdiff_t>(j)) ? 1 : 0;
        return n;
    };
    SECTION("first: only the first dispatch after the INDEX_BASE, at the start of its check") {
        std::vector<std::size_t> r;
        indirect_check::Stats s;
        auto o = indirect_check::apply(ib, 0, kMax, kDrawMax, r, s, false, nullptr, false, false, false, false,
                                       indirect_check::ArgsWb::first_after_index_base);
        CHECK(s.args_written_back == 1);
        CHECK(count(o) == 1);
        CHECK(o.size() == ib.size() + 2 * indirect_check::kCheckDwords + indirect_check::kArgsWbDwords);
        CHECK(std::equal(acquire.begin(), acquire.end(), o.begin() + 9)); // before the check's flag = 1
        CHECK(o[9 + 8] == 0xC0033700u);
    }
    SECTION("all: every checked dispatch") {
        std::vector<std::size_t> r;
        indirect_check::Stats s;
        auto o = indirect_check::apply(ib, 0, kMax, kDrawMax, r, s, false, nullptr, false, false, false, false,
                                       indirect_check::ArgsWb::all);
        CHECK(s.args_written_back == 2);
        CHECK(count(o) == 2);
    }
    SECTION("with the copy: after the three COPY_DATA, before flag = 1") {
        std::vector<std::size_t> r;
        indirect_check::Stats s;
        auto o = indirect_check::apply(ib, 0, kMax, kDrawMax, r, s, false, nullptr, false, false, false, true,
                                       indirect_check::ArgsWb::all);
        CHECK(s.args_copied == 2);
        CHECK(s.args_written_back == 2);
        CHECK(o[9] == 0xC0044000u);
        CHECK(std::equal(acquire.begin(), acquire.end(), o.begin() + 9 + 18));
        CHECK(o[9 + 18 + 8] == 0xC0033700u);
    }
    SECTION("off by default; never on the MEC form") {
        std::vector<std::size_t> r;
        indirect_check::Stats s;
        auto o = indirect_check::apply(ib, 0, kMax, kDrawMax, r, s);
        CHECK(count(o) == 0);
        CHECK(s.args_written_back == 0);
        const std::vector<std::uint32_t> mec = {0xC0021600u, 0x34567040u, 0x12u, 0x41u};
        auto m = indirect_check::apply(mec, 0, kMax, kDrawMax, r, s, true, nullptr, false, false, false, false,
                                       indirect_check::ArgsWb::all);
        CHECK(count(m) == 0);
    }
}
