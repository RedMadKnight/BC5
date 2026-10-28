// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0349: the IB cut (bc5/ib_split.hpp).
#include "bc5/ib_split.hpp"

#include <catch2/catch_test_macros.hpp>

#include <cstdint>
#include <vector>

namespace {

using bc5::ib_split::Piece;
using bc5::ib_split::Stats;

std::uint32_t pkt3(std::uint32_t op, std::uint32_t body_dwords) {
    return (3u << 30) | ((body_dwords - 1) << 16) | (op << 8);
}

// A stream of type-3 packets of `len` dwords each (len >= 2), `count` of them.
std::vector<std::uint32_t> stream(std::size_t count, std::uint32_t len, std::uint32_t op = 0x76) {
    std::vector<std::uint32_t> ib;
    for (std::size_t k = 0; k < count; ++k) {
        ib.push_back(pkt3(op, len - 1));
        for (std::uint32_t b = 1; b < len; ++b) ib.push_back(0x1000u + static_cast<std::uint32_t>(k));
    }
    return ib;
}

std::size_t packet_len(std::uint32_t h) {
    const std::uint32_t count = (h >> 16) & 0x3fff;
    return count == 0x3fff ? 1 : count + 2;
}

// The invariants of a cut set: contiguous cover of [0, end), sizes within max, every start a packet
// boundary aligned to `align` (or `fallback`), none inside a COND_EXEC range.
void check(const std::vector<std::uint32_t> &ib, const std::vector<Piece> &p, std::size_t end, std::size_t max_dw,
           std::size_t align, std::size_t fallback) {
    REQUIRE(!p.empty());
    REQUIRE(p.front().off == 0);
    std::size_t at = 0;
    for (const Piece &x : p) {
        REQUIRE(x.off == at);
        REQUIRE(x.n >= 1);
        REQUIRE(x.n <= max_dw);
        at += x.n;
    }
    REQUIRE(at == end);
    std::vector<bool> boundary(end + 1, false);
    std::vector<std::pair<std::size_t, std::size_t>> ranges;
    for (std::size_t i = 0; i < end;) {
        boundary[i] = true;
        const std::size_t len = packet_len(ib[i]);
        if (((ib[i] >> 8) & 0xff) == 0x22 && len == 5) ranges.emplace_back(i, i + 5 + (ib[i + 4] & 0x3fffu));
        i += len;
    }
    for (std::size_t k = 1; k < p.size(); ++k) {
        const std::size_t b = p[k].off;
        REQUIRE(boundary[b]);
        REQUIRE((b % align == 0 || b % fallback == 0));
        for (const auto &[lo, hi] : ranges) REQUIRE(!(lo < b && b < hi));
    }
}

} // namespace

TEST_CASE("ib_split: an IB within the limit is one piece", "[ib_split]") {
    const auto ib = stream(10, 3);
    Stats st;
    const auto p = bc5::ib_split::split(ib, ib.size(), 64, 4, 64, 8, st);
    REQUIRE(p.size() == 1);
    REQUIRE(p[0].off == 0);
    REQUIRE(p[0].n == ib.size());
    REQUIRE(st.pieces == 1);
    REQUIRE(!st.failed);
}

TEST_CASE("ib_split: a plain stream is cut at aligned packet boundaries", "[ib_split]") {
    const auto ib = stream(100, 3); // 300 dwords, boundaries at multiples of 3
    Stats st;
    const auto p = bc5::ib_split::split(ib, ib.size(), 64, 64, 8, 8, st);
    check(ib, p, ib.size(), 64, 8, 8);
    REQUIRE(p.size() >= 5); // 300 / 64
    REQUIRE(st.pieces == p.size());
    REQUIRE(st.fallback_cuts == 0);
    for (std::size_t k = 1; k < p.size(); ++k) REQUIRE(p[k].off % 24 == 0); // aligned to 8 and on a 3-dword packet
}

TEST_CASE("ib_split: the fallback alignment is used when no 64-aligned boundary exists", "[ib_split]") {
    const auto ib = stream(60, 5); // boundaries at multiples of 5; 320 is the first multiple of 64 and 5
    Stats st;
    const auto p = bc5::ib_split::split(ib, ib.size(), 100, 64, 64, 8, st);
    check(ib, p, ib.size(), 100, 64, 8);
    REQUIRE(st.fallback_cuts >= 1);
    for (std::size_t k = 1; k < p.size(); ++k) REQUIRE(p[k].off % 40 == 0);
}

TEST_CASE("ib_split: a cut never lands inside a COND_EXEC range", "[ib_split]") {
    // 20 packets of 3 (60 dwords), a COND_EXEC skipping the next 30 dwords, 30 more packets of 3.
    auto ib = stream(20, 3);
    const std::size_t cond_at = ib.size();
    ib.insert(ib.end(), {pkt3(0x22, 4), 0x60u, 0x0fu, 0u, 30u});
    const auto tail = stream(30, 3);
    ib.insert(ib.end(), tail.begin(), tail.end());
    Stats st;
    // With max 80 the natural cut (the largest aligned boundary <= 80) would be 72 or 78, inside the
    // range (65, 95); the cut has to move to the COND_EXEC itself (60) or before.
    const auto p = bc5::ib_split::split(ib, ib.size(), 80, 64, 8, 8, st);
    check(ib, p, ib.size(), 80, 8, 8);
    REQUIRE(st.cond_ranges == 1);
    REQUIRE(p.size() >= 2);
    REQUIRE(p[1].off <= cond_at);
    bool at_or_after_range_end = false;
    for (const Piece &x : p) at_or_after_range_end = at_or_after_range_end || x.off >= cond_at + 5 + 30;
    REQUIRE(at_or_after_range_end);
}

TEST_CASE("ib_split: a COND_EXEC range longer than the limit cannot be cut", "[ib_split]") {
    auto ib = stream(4, 3);
    ib.insert(ib.end(), {pkt3(0x22, 4), 0x60u, 0x0fu, 0u, 90u});
    const auto tail = stream(40, 3);
    ib.insert(ib.end(), tail.begin(), tail.end());
    Stats st;
    const auto p = bc5::ib_split::split(ib, ib.size(), 64, 64, 8, 8, st);
    REQUIRE(p.empty());
    REQUIRE(st.failed);
    REQUIRE(!st.too_many_pieces);
}

TEST_CASE("ib_split: more pieces than allowed fails", "[ib_split]") {
    const auto ib = stream(100, 3); // 300 dwords need at least 5 pieces of 64
    Stats st;
    const auto p = bc5::ib_split::split(ib, ib.size(), 64, 4, 8, 8, st);
    REQUIRE(p.empty());
    REQUIRE(st.failed);
    REQUIRE(st.too_many_pieces);
    Stats st2;
    const auto q = bc5::ib_split::split(ib, ib.size(), 64, 6, 8, 8, st2);
    check(ib, q, ib.size(), 64, 8, 8);
    REQUIRE(q.size() <= 6);
}

TEST_CASE("ib_split: the kernel's limits are the defaults", "[ib_split]") {
    REQUIRE(bc5::ib_split::kKernelMaxDwords == 0xfffff);
    REQUIRE(bc5::ib_split::kDefaultMaxDwords < bc5::ib_split::kKernelMaxDwords);
    REQUIRE(bc5::ib_split::kDefaultMaxDwords * 4 >= 0x3c0000); // four pieces hold 3.9 M dwords, any job of the day
    REQUIRE(bc5::ib_split::kMaxPieces == 4);
}
