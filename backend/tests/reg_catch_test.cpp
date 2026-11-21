// SPDX-License-Identifier: GPL-2.0-only
// The register catcher (bc5/reg_catch.hpp) on synthetic packets.
#include "bc5/policy.hpp"
#include "bc5/reg_catch.hpp"

#include <catch2/catch_test_macros.hpp>

#include <cstdint>
#include <vector>

namespace rc = bc5::reg_catch;
using u32 = std::uint32_t;

namespace {
u32 pkt3(u32 op, u32 count) { return 0xC0000000u | ((count - 1u) << 16) | (op << 8); }
const std::function<bool(std::uint64_t, std::uint64_t)> kAllMapped = [](std::uint64_t, std::uint64_t) { return true; };
} // namespace

TEST_CASE("reg catch: mode switch", "[reg_catch]") {
    CHECK(rc::parse_mode(nullptr) == rc::Mode::Off);
    CHECK(rc::parse_mode("") == rc::Mode::Off);
    CHECK(rc::parse_mode("0") == rc::Mode::Off);
    CHECK(rc::parse_mode("1") == rc::Mode::Log);
    CHECK(rc::parse_mode("fatal") == rc::Mode::Fatal);
}

TEST_CASE("reg catch: SET_* ranges", "[reg_catch]") {
    const u32 ok_sh[] = {pkt3(0x76, 3), 0x20C, 1, 2};
    CHECK(rc::check(ok_sh, 4, {}).reason == nullptr);
    const u32 last_sh[] = {pkt3(0x76, 2), 0x3FF, 1};
    CHECK(rc::check(last_sh, 3, {}).reason == nullptr);
    const u32 over_sh[] = {pkt3(0x76, 3), 0x3FF, 1, 2};
    CHECK(rc::check(over_sh, 4, {}).reason != nullptr);
    const u32 bad_cx[] = {pkt3(0x69, 2), 0xFFFF, 0};
    const rc::Finding f = rc::check(bad_cx, 3, {});
    REQUIRE(f.reason != nullptr);
    CHECK(f.reg == 0xFFFF);
    const u32 ok_uc[] = {pkt3(0x79, 2), 0x242, 4};
    CHECK(rc::check(ok_uc, 3, {}).reason == nullptr);
    const u32 nop[] = {pkt3(0x10, 2), 0, 0};
    CHECK(rc::check(nop, 3, {}).reason == nullptr);
}

TEST_CASE("reg catch: LOAD_*_REG_INDEX lists", "[reg_catch]") {
    std::vector<u32> pairs = {0x20C, 1, 0x20D, 2, 0x3FF, 3};
    const auto a = reinterpret_cast<std::uintptr_t>(pairs.data());
    const u32 load[] = {pkt3(0x63, 4), static_cast<u32>(a), static_cast<u32>(static_cast<std::uint64_t>(a) >> 32),
                        0x80000000u, 3};
    CHECK(rc::check(load, 5, kAllMapped).reason == nullptr);
    pairs[2] = 0xFFFFFFFFu; // an unresolved descriptor
    const rc::Finding f = rc::check(load, 5, kAllMapped);
    REQUIRE(f.reason != nullptr);
    CHECK(f.index == 1);
    CHECK(rc::check(load, 5, {}).reason == nullptr); // not mapped: not checked
    pairs[2] = 0x400;                                // one past the context/SH space
    const u32 cx[] = {pkt3(0x9f, 4), load[1], load[2], 0x80000000u, 3};
    CHECK(rc::check(cx, 5, kAllMapped).reason != nullptr);
    const u32 uc[] = {pkt3(0x64, 4), load[1], load[2], 0x80000000u, 3};
    CHECK(rc::check(uc, 5, kAllMapped).reason == nullptr); // 0x400 is inside the uconfig space
}
