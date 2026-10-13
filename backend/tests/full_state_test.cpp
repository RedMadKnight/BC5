// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/full_state.hpp"
#include "bc5/policy.hpp"

#include <catch2/catch_test_macros.hpp>

#include <cstdint>
#include <vector>

using namespace bc5;
using full_state::Tracker;

namespace {

const Tracker::Reader kHost = [](std::uint64_t a, std::uint64_t) {
    return reinterpret_cast<const std::uint32_t *>(a);
};
const Tracker::Reader kNone = [](std::uint64_t, std::uint64_t) -> const std::uint32_t * { return nullptr; };

std::uint32_t lo(const void *p) { return static_cast<std::uint32_t>(reinterpret_cast<std::uint64_t>(p)); }
std::uint32_t hi(const void *p) { return static_cast<std::uint32_t>(reinterpret_cast<std::uint64_t>(p) >> 32); }

std::uint32_t value(const Tracker &t, full_state::Space s, std::uint32_t off) {
    std::uint32_t v = 0xdeadbeefu;
    REQUIRE(t.get(s, off, v));
    return v;
}

} // namespace

TEST_CASE("full state: registers accumulate across buffers, later sets win", "[full_state]") {
    Tracker t;
    full_state::Stats st;
    const std::vector<std::uint32_t> a = {
        0xC0026900u, 0x200, 1, 2,      // SET_CONTEXT_REG 0x200..0x201
        0xC0017600u, 0x4c, 3,          // SET_SH_REG 0x4c
        0xC0017900u, 0x242, 4,         // SET_UCONFIG_REG 0x242
        0xC0017A00u, 0x10000243u, 5,   // SET_UCONFIG_REG_INDEX, index bits above the offset
        0xC0016800u, 0x10, 6,          // SET_CONFIG_REG
    };
    const std::vector<std::uint32_t> b = {0xC0016900u, 0x201, 7, 0xC0019B00u, 0x2000004cu, 8};
    t.apply(a, kNone, st);
    t.apply(b, kNone, st);
    CHECK(value(t, full_state::Context, 0x200) == 1);
    CHECK(value(t, full_state::Context, 0x201) == 7);
    CHECK(value(t, full_state::Sh, 0x4c) == 8);
    CHECK(value(t, full_state::Uconfig, 0x242) == 4);
    CHECK(value(t, full_state::Uconfig, 0x243) == 5);
    CHECK(value(t, full_state::Config, 0x10) == 6);
    CHECK(st.packets == 7);
    CHECK(st.registers_set == 8);
}

TEST_CASE("full state: LOAD_*_REG tables are read through the reader", "[full_state]") {
    // LOAD_SH_REG: values at base + offset * 4 for each (offset, count) pair
    std::vector<std::uint32_t> table(0x60, 0);
    table[0x4c] = 0x11;
    table[0x4d] = 0x12;
    table[0x50] = 0x13;
    const std::vector<std::uint32_t> ib = {0xC0055F00u, lo(table.data()), hi(table.data()), 0x4c, 2, 0x50, 1};
    Tracker t;
    full_state::Stats st;
    t.apply(ib, kHost, st);
    CHECK(value(t, full_state::Sh, 0x4c) == 0x11);
    CHECK(value(t, full_state::Sh, 0x4d) == 0x12);
    CHECK(value(t, full_state::Sh, 0x50) == 0x13);
    CHECK(st.tables == 2);
    CHECK(st.unreadable_tables == 0);

    Tracker u;
    full_state::Stats su;
    u.apply(ib, kNone, su);
    CHECK(u.count(full_state::Sh) == 0);
    CHECK(su.unreadable_tables == 2);
}

TEST_CASE("full state: LOAD_*_REG_INDEX in pairs and in consecutive form", "[full_state]") {
    static const std::uint32_t pairs[] = {0x103, 0xaa, 0x318, 0xbb};
    static const std::uint32_t values[] = {0xcc, 0xdd, 0xee};
    const std::vector<std::uint32_t> ib = {
        0xC0039F00u, lo(pairs), hi(pairs), 0x80000000u, 2,   // context, (offset, value) pairs
        0xC0036400u, lo(values), hi(values), 0x250, 3,       // uconfig, consecutive from 0x250
    };
    Tracker t;
    full_state::Stats st;
    t.apply(ib, kHost, st);
    CHECK(value(t, full_state::Context, 0x103) == 0xaa);
    CHECK(value(t, full_state::Context, 0x318) == 0xbb);
    CHECK(value(t, full_state::Uconfig, 0x250) == 0xcc);
    CHECK(value(t, full_state::Uconfig, 0x252) == 0xee);
    CHECK(st.tables == 2);
}

TEST_CASE("full state: CLEAR_STATE clears, pushes and pops the context registers", "[full_state]") {
    const std::vector<std::uint32_t> ib = {
        0xC0016900u, 0x200, 1,  // game state
        0xC0017600u, 0x4c, 2,   // SH: not touched by CLEAR_STATE
        0xC0001200u, 1,         // push
        0xC0016900u, 0x300, 3,  // internal draw state
        0xC0001200u, 2,         // pop
    };
    Tracker t;
    full_state::Stats st;
    t.apply(ib, kNone, st);
    CHECK(value(t, full_state::Context, 0x200) == 1);
    std::uint32_t v = 0;
    CHECK_FALSE(t.get(full_state::Context, 0x300, v));
    CHECK(value(t, full_state::Sh, 0x4c) == 2);
    CHECK(st.pushes == 1);
    CHECK(st.pops == 1);

    t.apply(std::vector<std::uint32_t>{0xC0001200u, 0}, kNone, st);
    CHECK(t.count(full_state::Context) == 0);
    CHECK(t.count(full_state::Sh) == 1);
    CHECK(st.clears == 1);
}

TEST_CASE("full state: the prefix reproduces the tracked state on a fresh tracker", "[full_state]") {
    static const std::uint32_t pairs[] = {0x103, 0xaa, 0x318, 0xbb};
    const std::vector<std::uint32_t> a = {
        0xC0036900u, 0x200, 1, 2, 3,                 // run of 3
        0xC0016900u, 0x205, 4,                       // gap: a second run
        0xC0039F00u, lo(pairs), hi(pairs), 0x80000000u, 2,
        0xC0027600u, 0x4c, 5, 6,
        0xC0017900u, 0x242, 7,
        0xC0016800u, 0x10, 8,
        0xC0021100u, 0, 0x1000, 0,                   // SET_BASE index 0
        0xC0021100u, 1, 0x2000, 0,                   // SET_BASE index 1
        0xC0012600u, 0x3000, 0,                      // INDEX_BASE
        0xC0001300u, 64,                             // INDEX_BUFFER_SIZE
        0xC0002A00u, 1,                              // INDEX_TYPE
        0xC0002F00u, 2,                              // NUM_INSTANCES
        0xC0012800u, 0x91018003u, 0x80018003u,       // CONTEXT_CONTROL: not replayed
    };
    Tracker t;
    full_state::Stats st;
    t.apply(a, kHost, st);
    const auto prefix = t.emit_prefix();

    Tracker fresh;
    full_state::Stats sf;
    fresh.apply(prefix, kNone, sf); // the prefix reads no memory
    CHECK(fresh == t);
    CHECK(sf.unreadable_tables == 0);
    CHECK(sf.clears == 1);

    // The prefix applied over unrelated state (another process's) gives the same result.
    Tracker dirty;
    dirty.apply(std::vector<std::uint32_t>{0xC0016900u, 0x2a0, 9, 0xC0017600u, 0x4c, 10}, kNone, sf);
    dirty.apply(prefix, kNone, sf);
    CHECK(value(dirty, full_state::Sh, 0x4c) == 5);
    std::uint32_t v = 0;
    CHECK_FALSE(dirty.get(full_state::Context, 0x2a0, v));

    // The policy filter keeps the prefix's state.
    std::vector<std::uint32_t> filtered(prefix.size());
    policy::FilterStats fs;
    policy::filter(policy::Policy::builtin(), prefix, filtered, policy::FilterOptions{}, fs);
    Tracker after_filter;
    after_filter.apply(filtered, kNone, sf);
    CHECK(after_filter == t);
}

TEST_CASE("full state: long register runs split into packets", "[full_state]") {
    // 0x3ffe + 0x100 consecutive context registers: more than one packet can carry
    std::vector<std::uint32_t> ib = {0xC0006900u | (0x3ffeu << 16), 0};
    for (std::uint32_t k = 0; k < 0x3ffe; ++k) ib.push_back(k);
    ib.insert(ib.end(), {0xC0006900u | (0x100u << 16), 0x3ffe});
    for (std::uint32_t k = 0; k < 0x100; ++k) ib.push_back(0x10000u + k);
    Tracker t;
    full_state::Stats st;
    t.apply(ib, kNone, st);
    REQUIRE(t.count(full_state::Context) == 0x3ffe + 0x100);
    Tracker fresh;
    fresh.apply(t.emit_prefix(), kNone, st);
    CHECK(fresh == t);
}

TEST_CASE("full state: nested INDIRECT_BUFFERs are followed through the reader", "[full_state]") {
    static const std::uint32_t nested[] = {0xC0016900u, 0x210, 0x77};
    const std::vector<std::uint32_t> ib = {0xC0023F00u, lo(nested), hi(nested), 3};
    Tracker t;
    full_state::Stats st;
    t.apply(ib, kHost, st);
    CHECK(value(t, full_state::Context, 0x210) == 0x77);
    CHECK(st.nested == 1);
    Tracker u;
    u.apply(ib, kNone, st);
    CHECK(u.count(full_state::Context) == 0);
    CHECK(st.unreadable_nested == 1);
}

TEST_CASE("full state: a split checked against the unsplit buffer", "[full_state]") {
    Tracker before; // the frame's earlier buffers
    full_state::Stats st;
    before.apply(std::vector<std::uint32_t>{0xC0016900u, 0x200, 1, 0xC0017600u, 0x4c, 2}, kNone, st);
    const std::vector<std::uint32_t> ib = {
        0xC0016900u, 0x201, 3,                         // head
        0xC0053C00u, 0x13, 0x1000, 0, 1, 1, 4,         // WAIT_REG_MEM on memory: the split (offset 3)
        0xC0016900u, 0x202, 4,
        0xC0012D00u, 3, 2,                             // DRAW_INDEX_AUTO
        0xC0017600u, 0x4d, 5,
        0xC0031500u, 1, 1, 1, 0,                       // DISPATCH_DIRECT
    };
    const auto c = full_state::check_split(before, ib, 3, kNone);
    CHECK(c.draws == 2);
    CHECK(c.mismatched_draws == 0);
    CHECK(c.stack_depth == 0);
    CHECK(c.prefix_dwords > 0);

    // A push open at the split: the saved context is the device's state stack's (adopted), so
    // the pop restores the same registers in the piece.
    const std::vector<std::uint32_t> pushed = {
        0xC0001200u, 1,                                // push (offset 0)
        0xC0016900u, 0x300, 9,
        0xC0053C00u, 0x13, 0x1000, 0, 1, 1, 4,         // split at 5
        0xC0001200u, 2,                                // pop: 0x200 back
        0xC0012D00u, 3, 2,
    };
    const auto d = full_state::check_split(before, pushed, 5, kNone);
    CHECK(d.stack_depth == 1);
    CHECK(d.draws == 1);
    CHECK(d.mismatched_draws == 0);
}
