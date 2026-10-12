// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/indirect_check.hpp"

#include <catch2/catch_test_macros.hpp>

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
