// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0359: the job-arena fix's pure parts (bc5/job_arena_fix.hpp).
#include "bc5/job_arena_fix.hpp"

#include <catch2/catch_test_macros.hpp>

#include <array>
#include <cstdint>
#include <cstring>

namespace {

using namespace bc5::job_arena_fix;

TEST_CASE("the site encoding reaches the slot through a rip-relative call", "[job_arena_fix]") {
    std::array<std::uint8_t, 7> out {};
    const std::uint64_t         base = 0x900000000ull;
    REQUIRE(encode_site(base + kSiteOffset, base + kSlotOffset, &out));
    CHECK(out[0] == 0xff);
    CHECK(out[1] == 0x15);
    CHECK(out[6] == 0x90);
    std::int32_t disp = 0;
    std::memcpy(&disp, &out[2], 4);
    // rip after the 6-byte call + disp = the slot
    CHECK(static_cast<std::int64_t>(base + kSiteOffset + 6) + disp == static_cast<std::int64_t>(base + kSlotOffset));
    CHECK(disp == static_cast<std::int32_t>(kSlotOffset) - static_cast<std::int32_t>(kSiteOffset + 6));
}

TEST_CASE("the site encoding refuses a slot out of rip-relative reach", "[job_arena_fix]") {
    std::array<std::uint8_t, 7> out {};
    CHECK_FALSE(encode_site(0x900000000ull, 0x900000000ull + (1ull << 31) + 0x1000, &out));
    CHECK_FALSE(encode_site(0x900000000ull + (1ull << 31) + 0x1000, 0x900000000ull, &out));
    CHECK(encode_site(0x1000, 0x1000ull + 6ull + static_cast<std::uint64_t>(INT32_MAX), &out));
}

TEST_CASE("the expected bytes are checked exactly", "[job_arena_fix]") {
    std::array<std::uint8_t, 7> site = kSiteExpected;
    std::array<std::uint8_t, 8> slot = kSlotExpected;
    CHECK(site_matches(site.data()));
    CHECK(slot_matches(slot.data()));
    site[3] ^= 1;
    CHECK_FALSE(site_matches(site.data()));
    slot[7] = 0x90;
    CHECK_FALSE(slot_matches(slot.data()));
}

TEST_CASE("the override arena is laid out as the title builds it", "[job_arena_fix]") {
    OverrideArena             a {};
    std::array<std::uint8_t, 16> consts {};
    for (std::size_t i = 0; i < consts.size(); i++) {
        consts[i] = static_cast<std::uint8_t>(0x10 + i);
    }
    build_arena(&a, 0x1234000, 0x100000, consts.data(), 0x900000000ull + kArenaTailOffset);
    const auto* raw = reinterpret_cast<const std::uint8_t*>(&a);
    std::uint64_t block = 0;
    std::memcpy(&block, raw, 8);
    CHECK(block == 0x1234000);
    std::uint32_t size = 0;
    std::memcpy(&size, raw + 8, 4);
    CHECK(size == 0x100000);
    CHECK(std::memcmp(raw + 0xc, consts.data(), 16) == 0);
    std::uint32_t zero = 1;
    std::memcpy(&zero, raw + 0x1c, 4);
    CHECK(zero == 0);
    for (std::size_t i = 0x20; i < 0x30; i++) {
        CHECK(raw[i] == 0);
    }
    std::uint64_t tail = 0;
    std::memcpy(&tail, raw + 0x30, 8);
    CHECK(tail == 0x900000000ull + kArenaTailOffset);
}

TEST_CASE("only an unregistered thread gets the window", "[job_arena_fix]") {
    CHECK(wrap_needed(-1));
    CHECK_FALSE(wrap_needed(0));
    CHECK_FALSE(wrap_needed(4));
    CHECK_FALSE(wrap_needed(5));
}

} // namespace
