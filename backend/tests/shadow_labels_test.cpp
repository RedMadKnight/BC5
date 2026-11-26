// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/shadow_labels.hpp"

#include <catch2/catch_test_macros.hpp>

#include <cstdint>
#include <vector>

using namespace bc5;

namespace {
constexpr std::uint32_t kNop = 0xC0001000u;
// The title's end-of-pipe sync on label 0x11e0b975e0 (F360): WRITE_DATA 0, RELEASE_MEM EOP with a
// 32-bit value 1 (EOP_DATA_SEL 1 in dword 2 bits 31:29), WAIT_REG_MEM == 1 in memory space.
const std::vector<std::uint32_t> kWrite = {0xC0033700u, 5u << 8, 0xe0b975e0u, 0x11u, 0u};
const std::vector<std::uint32_t> kRelease = {0xC0064900u, 0x528u, 1u << 29, 0xe0b975e0u, 0x11u, 1u, 0u, 0u};
const std::vector<std::uint32_t> kWait = {0xC0053C00u, 0x13u, 0xe0b975e0u, 0x11u, 1u, 0xffffffffu, 4u};

std::vector<std::uint32_t> cat(std::initializer_list<const std::vector<std::uint32_t> *> parts) {
    std::vector<std::uint32_t> out;
    for (const auto *p : parts) out.insert(out.end(), p->begin(), p->end());
    return out;
}
} // namespace

TEST_CASE("shadow_labels: a label written and waited on gets a shadow slot", "[shadow_labels]") {
    std::vector<std::uint32_t> ib = kWrite;
    ib.insert(ib.end(), {kNop, 0u});
    ib.insert(ib.end(), kRelease.begin(), kRelease.end());
    ib.insert(ib.end(), kWait.begin(), kWait.end());
    shadow_labels::Stats st;
    REQUIRE(shadow_labels::apply(ib, 64, st));
    CHECK(st.labels == 1);
    CHECK(st.writes == 2);
    CHECK(st.waits == 1);
    CHECK(st.overflow == 0);
    // the copy of the WRITE_DATA, the WRITE_DATA, NOP, the copy of the RELEASE_MEM, the RELEASE_MEM, the wait
    REQUIRE(ib.size() == 5 + 5 + 2 + 8 + 8 + 7);
    CHECK(ib[0] == 0xC0033700u);          // the copy of the WRITE_DATA, before it
    CHECK(ib[2] == 0u);                   // slot 0 marker
    CHECK(ib[3] == shadow_labels::kMarkerHi);
    CHECK(ib[4] == 0u);                   // the same data
    CHECK(ib[5 + 2] == 0xe0b975e0u);      // the title's label kept in the original
    CHECK(ib[12] == 0xC0064900u);         // the copy of the RELEASE_MEM
    CHECK(ib[12 + 3] == 0u);
    CHECK(ib[12 + 4] == shadow_labels::kMarkerHi);
    CHECK(ib[12 + 5] == 1u);              // the same value
    CHECK(ib[20] == 0xC0064900u);         // the RELEASE_MEM
    CHECK(ib[20 + 3] == 0xe0b975e0u);     // the title's label kept
    CHECK(ib[28] == 0xC0053C00u);         // the wait, redirected
    CHECK(ib[28 + 2] == 0u);
    CHECK(ib[28 + 3] == shadow_labels::kMarkerHi);
    CHECK(ib[28 + 4] == 1u);
    // patch: the slot's address
    CHECK(shadow_labels::patch(ib, 0x1000'0000'4000ull) == 1);
    CHECK(ib[2] == 0x4000u);
    CHECK(ib[3] == 0x1000u);
    CHECK(ib[12 + 3] == 0x4000u);
    CHECK(ib[12 + 4] == 0x1000u);
    CHECK(ib[28 + 2] == 0x4000u);
    CHECK(ib[28 + 3] == 0x1000u);
    CHECK(shadow_labels::patch(ib, 0x1000'0000'4000ull) == 0); // nothing left to patch
}

TEST_CASE("shadow_labels: waits on labels nobody writes first, register polls and a second label",
          "[shadow_labels]") {
    // a wait before its writer: not shadowed; a register poll: never; a second label gets slot 1
    std::vector<std::uint32_t> other_rel = kRelease;
    other_rel[3] = 0xe0b97600u; // label 0x11e0b97600
    std::vector<std::uint32_t> other_wait = kWait;
    other_wait[2] = 0xe0b97600u;
    std::vector<std::uint32_t> reg_poll = kWait;
    reg_poll[1] = 0x3u; // function 3, register space
    std::vector<std::uint32_t> ib = cat({&kWait, &kRelease, &kWait, &other_rel, &other_wait, &reg_poll});
    shadow_labels::Stats st;
    REQUIRE(shadow_labels::apply(ib, 64, st));
    CHECK(st.labels == 2);
    CHECK(st.writes == 2);
    CHECK(st.waits == 2); // the first wait (before the writer) and the register poll untouched
    CHECK(ib[2] == 0xe0b975e0u);
    CHECK(ib[3] == 0x11u);
    const std::size_t second_wait = 7 + 8 + 8; // wait, the copy, RELEASE_MEM
    CHECK(ib[second_wait] == 0xC0053C00u);
    CHECK(ib[second_wait + 3] == shadow_labels::kMarkerHi);
    CHECK(ib[second_wait + 2] == 0u);
    const std::size_t other = second_wait + 7 + 8 + 8;
    CHECK(ib[other + 2] == 8u); // slot 1
    CHECK(ib[other + 3] == shadow_labels::kMarkerHi);
    CHECK(ib[other + 7 + 2] == 0xe0b975e0u); // the register poll's dwords untouched
    CHECK(shadow_labels::patch(ib, 0x1000'0000'4000ull) == 2);
    CHECK(ib[other + 2] == 0x4008u);
}

TEST_CASE("shadow_labels: the slot limit, an IB without waits, the COND_EXEC growth",
          "[shadow_labels]") {
    {
        std::vector<std::uint32_t> other_rel = kRelease;
        other_rel[3] = 0xe0b97600u;
        std::vector<std::uint32_t> other_wait = kWait;
        other_wait[2] = 0xe0b97600u;
        std::vector<std::uint32_t> ib = cat({&kRelease, &kWait, &other_rel, &other_wait});
        shadow_labels::Stats st;
        REQUIRE(shadow_labels::apply(ib, 1, st));
        CHECK(st.labels == 1);
        CHECK(st.overflow == 1);
        CHECK(ib.size() == 8 + 8 + 7 + 8 + 7);
    }
    {
        std::vector<std::uint32_t> ib = cat({&kWrite, &kRelease});
        shadow_labels::Stats st;
        REQUIRE(shadow_labels::apply(ib, 64, st));
        CHECK(st.labels == 0);
        CHECK(ib.size() == 13);
    }
    {
        // the writer inside the IB's own COND_EXEC range: the count grows by the copy
        std::vector<std::uint32_t> ib = {0xC0032200u, 0x1000u, 0u, 0u, 8u};
        ib.insert(ib.end(), kRelease.begin(), kRelease.end());
        ib.insert(ib.end(), kWait.begin(), kWait.end());
        shadow_labels::Stats st;
        REQUIRE(shadow_labels::apply(ib, 64, st));
        CHECK(ib[4] == 16u);
        CHECK(ib.size() == 5 + 8 + 8 + 7);
    }
}
