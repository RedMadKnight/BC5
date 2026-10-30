// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/acb_restore.hpp"

#include <catch2/catch_test_macros.hpp>

#include <cstddef>
#include <cstdint>
#include <ios>
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

std::uint32_t sh(const Tracker &t, std::uint32_t off) {
    std::uint32_t v = 0xdeadbeefu;
    REQUIRE(t.get(full_state::Sh, off, v));
    return v;
}

// SET_SH_REG of n values from off.
std::vector<std::uint32_t> set_sh(std::uint32_t off, const std::vector<std::uint32_t> &v) {
    std::vector<std::uint32_t> p = {0xC0007600u | (static_cast<std::uint32_t>(v.size()) << 16), off};
    p.insert(p.end(), v.begin(), v.end());
    return p;
}

void append(std::vector<std::uint32_t> &a, const std::vector<std::uint32_t> &b) { a.insert(a.end(), b.begin(), b.end()); }

const std::vector<std::uint32_t> kDispatchIndirect = {0xC0011600u, 0x80, 0x61}; // DISPATCH_INDIRECT

// The F679 shape: a dcb that sets the program, resources, threads and all 16 user data (part of
// them through a LOAD_SH_REG_INDEX pairs table), and a later dcb that dispatches with them.
struct Scene {
    std::vector<std::uint32_t> table; // pairs: COMPUTE_PGM_LO, USER_DATA_3
    std::vector<std::uint32_t> dcb1, acb, dcb2;
    Scene() {
        table = {0x20c, 0x09977100u >> 8, 0x243, 0x8c652a00u};
        append(dcb1, set_sh(0x207, {64, 1, 1}));                  // COMPUTE_NUM_THREAD_X..Z
        append(dcb1, set_sh(0x20d, {0x9}));                       // COMPUTE_PGM_HI
        append(dcb1, set_sh(0x212, {0x002c0041u, 0x00000098u}));  // RSRC1, RSRC2
        append(dcb1, set_sh(0x228, {0x0}));                       // RSRC3
        std::vector<std::uint32_t> ud;
        for (std::uint32_t k = 0; k < 16; ++k) ud.push_back(k == 0 ? 0x11u : 0x1000u + k);
        append(dcb1, set_sh(0x240, ud));                          // USER_DATA_0..15
        append(dcb1, {0xC0036300u, lo(table.data()), hi(table.data()), 0x80000000u, 2}); // LOAD_SH_REG_INDEX pairs
        append(dcb1, kDispatchIndirect);
        // The acb: its own program, resources, threads and user data 0..3.
        append(acb, set_sh(0x207, {256, 1, 1}));
        append(acb, set_sh(0x20c, {0x11d03a35u, 0x0}));
        append(acb, set_sh(0x212, {0x00ac0081u, 0x0000098cu}));
        append(acb, set_sh(0x240, {0x11d00860u, 0xc3800000u, 0x0000c000u, 0x90500facu}));
        append(acb, set_sh(0x2a0, {0x5}));                        // an SH register the dcbs never set
        append(acb, {0xC0031500u, 4, 1, 1, 0x1});                 // DISPATCH_DIRECT
        // The dcb that inherits everything: it dispatches at once.
        dcb2 = kDispatchIndirect;
    }
};

} // namespace

TEST_CASE("acb restore: wants only buffers that dispatch or call an IB2", "[acb_restore]") {
    CHECK(acb_restore::wants(kDispatchIndirect));
    CHECK(acb_restore::wants(std::vector<std::uint32_t>{0xC0031500u, 1, 1, 1, 1}));
    CHECK(acb_restore::wants(std::vector<std::uint32_t>{0xC0023F00u, 0x1000, 0x10, 4}));
    CHECK_FALSE(acb_restore::wants(std::vector<std::uint32_t>{0xC0017600u, 0x4c, 3, 0xC0012D00u, 3, 2}));
    // A dispatch opcode inside another packet's body is not a packet.
    CHECK_FALSE(acb_restore::wants(std::vector<std::uint32_t>{0xC0017600u, 0x240, 0xC0011600u}));
}

TEST_CASE("acb restore: the F679 carry, and the restore that undoes it", "[acb_restore]") {
    const Scene s;
    full_state::Stats st;
    Tracker dcb_state; // the host's tracker: dcbs only, CPU view of the tables
    dcb_state.apply(s.dcb1, kHost, st);
    REQUIRE(sh(dcb_state, acb_restore::kUserData0) == 0x11u);
    REQUIRE(sh(dcb_state, 0x20c) == 0x09977100u >> 8);
    REQUIRE(sh(dcb_state, 0x243) == 0x8c652a00u); // the table's value over the SET_SH_REG

    SECTION("without the restore the dcb dispatches with the acb's registers") {
        Tracker gpu; // the one GFX ring: dcb1, the merged acb, dcb2
        gpu.apply(s.dcb1, kHost, st);
        gpu.apply(s.acb, kHost, st);
        gpu.apply(s.dcb2, kHost, st);
        CHECK(sh(gpu, acb_restore::kUserData0) == 0x11d00860u);
        CHECK((sh(gpu, acb_restore::kUserData0) & 0xffffu) == 0x0860u); // F679's fault high half
        CHECK(sh(gpu, 0x20c) == 0x11d03a35u);
    }
    SECTION("with the restore every register the dcbs set is back") {
        std::size_t regs = 0;
        const auto pre = acb_restore::runs(dcb_state, &regs);
        Tracker gpu;
        gpu.apply(s.dcb1, kHost, st);
        gpu.apply(s.acb, kHost, st);
        std::vector<std::uint32_t> segment = pre; // the restore and dcb2 in one chain segment
        append(segment, s.dcb2);
        gpu.apply(segment, kHost, st);
        // NUM_THREAD 3 + PGM_LO/HI 2 + RSRC1/2 2 + RSRC3 1 + USER_DATA 16 = 24
        CHECK(regs == 24);
        for (std::uint32_t o = acb_restore::kFirst; o < acb_restore::kEnd; ++o) {
            std::uint32_t want = 0;
            if (!acb_restore::replayable(o) || !dcb_state.get(full_state::Sh, o, want)) continue;
            INFO("SH 0x" << std::hex << o);
            CHECK(sh(gpu, o) == want);
        }
        CHECK(sh(gpu, acb_restore::kUserData0) == 0x11u);
        CHECK(sh(gpu, 0x207) == 64u);
        CHECK(sh(gpu, 0x212) == 0x002c0041u);
        // The acb's register the dcbs never set stays: the restore cannot know its value.
        CHECK(sh(gpu, 0x2a0) == 0x5u);
    }
}

TEST_CASE("acb restore: runs skip untracked offsets, COMPUTE_VMID and the dispatch registers", "[acb_restore]") {
    Tracker t;
    full_state::Stats st;
    std::vector<std::uint32_t> ib;
    append(ib, set_sh(0x200, {1, 2, 3, 4}));   // DISPATCH_INITIATOR, DIM_X..Z: never replayed
    append(ib, set_sh(0x204, {7}));            // START_X
    append(ib, set_sh(0x214, {9}));            // COMPUTE_VMID: never replayed
    append(ib, set_sh(0x240, {0xa, 0xb}));     // USER_DATA_0..1
    t.apply(ib, kNone, st);
    std::size_t regs = 0;
    const auto p = acb_restore::runs(t, &regs);
    const std::vector<std::uint32_t> want = {0xC0017600u, 0x204, 7, 0xC0027600u, 0x240, 0xa, 0xb};
    CHECK(p == want);
    CHECK(regs == 3);
    CHECK(acb_restore::runs(Tracker{}).empty());
}

TEST_CASE("acb restore: chain offsets map back to the title's buffer", "[acb_restore]") {
    struct S {
        std::uint32_t off, prefix, n;
    };
    // Two title buffers in one chain, the second behind a 58-dword restore (REVIEW-06-J2's 13 + 58).
    const std::vector<S> segs = {{0, 0, 100}, {100, 58, 15083}};
    const auto at = [&](std::uint32_t q) { return acb_restore::locate(std::span<const S>(segs), q); };
    CHECK(at(13).seg == 0);
    CHECK(at(13).orig == 13);
    const auto opener = at(100 + 58 + 13);
    CHECK(opener.seg == 1);
    CHECK(opener.orig == 13);
    CHECK_FALSE(opener.in_prefix);
    const auto in_pre = at(120);
    CHECK(in_pre.seg == 1);
    CHECK(in_pre.in_prefix);
    CHECK(at(100 + 58 + 15083).seg == -1);
    // A job alone behind its restore: the same opener at 71, which a fixed limit on the offset missed.
    const std::vector<S> head = {{0, 58, 15083}};
    const auto alone = acb_restore::locate(std::span<const S>(head), 71);
    CHECK(alone.seg == 0);
    CHECK(alone.orig == 13);
    CHECK(acb_restore::locate(std::span<const S>(), 5).seg == -1);
}

TEST_CASE("acb restore: sh_value reads what a prefix emitted", "[acb_restore]") {
    const Scene s;
    Tracker t;
    full_state::Stats st;
    t.apply(s.dcb1, kHost, st);
    const auto pre = acb_restore::runs(t);
    std::uint32_t v = 0;
    REQUIRE(acb_restore::sh_value(pre, acb_restore::kUserData0, v));
    CHECK(v == 0x11u);
    REQUIRE(acb_restore::sh_value(pre, 0x20c, v));
    CHECK(v == 0x09977100u >> 8);
    CHECK_FALSE(acb_restore::sh_value(pre, 0x2a0, v));
    CHECK_FALSE(acb_restore::sh_value({}, acb_restore::kUserData0, v));
    const std::vector<std::uint32_t> twice = {0xC0017600u, 0x240, 1, 0xC0017600u, 0x240, 2};
    REQUIRE(acb_restore::sh_value(twice, acb_restore::kUserData0, v));
    CHECK(v == 2u);
}

TEST_CASE("acb restore: final_value is the state after all writes, or unknown", "[acb_restore]") {
    using acb_restore::Final;
    const std::uint32_t ud0 = acb_restore::kUserData0;
    std::uint32_t v = 0;
    const auto dispatch = std::vector<std::uint32_t>{0xC0031500u, 4, 1, 1, 1};
    SECTION("nothing writes it") {
        CHECK(acb_restore::final_value(dispatch, ud0, kNone, v) == Final::None);
    }
    SECTION("a write after the last dispatch counts") {
        std::vector<std::uint32_t> ib = set_sh(ud0, {0x11d00860u});
        append(ib, dispatch);
        append(ib, set_sh(ud0, {0x22u}));
        REQUIRE(acb_restore::final_value(ib, ud0, kNone, v) == Final::Known);
        CHECK(v == 0x22u);
    }
    SECTION("tables: pairs, flat, and LOAD_SH_REG") {
        const std::vector<std::uint32_t> pairs = {0x241, 1, ud0, 0x33};
        std::vector<std::uint32_t> ib = {0xC0036300u, lo(pairs.data()), hi(pairs.data()), 0x80000000u, 2};
        REQUIRE(acb_restore::final_value(ib, ud0, kHost, v) == Final::Known);
        CHECK(v == 0x33u);
        const std::vector<std::uint32_t> flat = {0x44, 0x55};
        ib = {0xC0036300u, lo(flat.data()), hi(flat.data()), ud0 - 1, 2};
        REQUIRE(acb_restore::final_value(ib, ud0, kHost, v) == Final::Known);
        CHECK(v == 0x55u);
        std::vector<std::uint32_t> mem(0x242, 0);
        mem[0x240] = 0x66;
        ib = {0xC0035F00u, lo(mem.data()), hi(mem.data()), 0x23f, 3};
        REQUIRE(acb_restore::final_value(ib, ud0, kHost, v) == Final::Known);
        CHECK(v == 0x66u);
    }
    SECTION("an unreadable table or IB2 is unknown, a later plain write settles it") {
        std::vector<std::uint32_t> ib = {0xC0036300u, 0x1000, 0, 0x80000000u, 2};
        CHECK(acb_restore::final_value(ib, ud0, kNone, v) == Final::Unknown);
        append(ib, set_sh(ud0, {0x77u}));
        REQUIRE(acb_restore::final_value(ib, ud0, kNone, v) == Final::Known);
        CHECK(v == 0x77u);
        CHECK(acb_restore::final_value(std::vector<std::uint32_t>{0xC0023F00u, 0x1000, 0, 4}, ud0, kNone, v) == Final::Unknown);
    }
    SECTION("an IB2 is followed") {
        const std::vector<std::uint32_t> ib2 = set_sh(ud0, {0x88u});
        const std::vector<std::uint32_t> ib = {0xC0023F00u, lo(ib2.data()), hi(ib2.data()), static_cast<std::uint32_t>(ib2.size())};
        REQUIRE(acb_restore::final_value(ib, ud0, kHost, v) == Final::Known);
        CHECK(v == 0x88u);
    }
    SECTION("a write under COND_EXEC is unknown") {
        std::vector<std::uint32_t> ib = {0xC0032200u, 0x1000, 0, 0, 3}; // COND_EXEC over the next 3 dwords
        append(ib, set_sh(ud0, {0x99u}));
        CHECK(acb_restore::final_value(ib, ud0, kNone, v) == Final::Unknown);
        append(ib, set_sh(ud0, {0xaau}));
        REQUIRE(acb_restore::final_value(ib, ud0, kNone, v) == Final::Known);
        CHECK(v == 0xaau);
    }
}

TEST_CASE("acb restore: Touched lists what acbs write and the dcb state lacks", "[acb_restore]") {
    const Scene s;
    acb_restore::Touched touched;
    touched.scan(s.acb, kHost);
    // NUM_THREAD 3, PGM_LO/HI 2, RSRC1/2 2, USER_DATA_0..3 4, 0x2a0 1
    CHECK(touched.count() == 12);
    CHECK(touched.has(0x240));
    CHECK(touched.has(0x2a0));
    CHECK_FALSE(touched.has(0x244));
    Tracker dcb_state;
    full_state::Stats st;
    dcb_state.apply(s.dcb1, kHost, st);
    CHECK(touched.missing(dcb_state) == std::vector<std::uint32_t>{0x2a0});

    SECTION("tables, LOAD_SH_REG ranges and IB2s count; unreadable ones are counted") {
        const std::vector<std::uint32_t> pairs = {0x24e, 1, 0x24f, 2};
        const std::vector<std::uint32_t> ib2 = set_sh(0x2b0, {1});
        std::vector<std::uint32_t> acb;
        append(acb, {0xC0036300u, lo(pairs.data()), hi(pairs.data()), 0x80000000u, 2}); // pairs table
        append(acb, {0xC0036300u, 0x1000, 0, 0x00000230u, 2});                             // flat: 0x230..0x231
        append(acb, {0xC0035F00u, 0x2000, 0, 0x250, 3});                                   // LOAD_SH_REG 0x250..0x252
        append(acb, {0xC0023F00u, lo(ib2.data()), hi(ib2.data()), static_cast<std::uint32_t>(ib2.size())});
        acb_restore::Touched t;
        t.scan(acb, kHost);
        for (std::uint32_t o : {0x24eu, 0x24fu, 0x230u, 0x231u, 0x250u, 0x251u, 0x252u, 0x2b0u}) CHECK(t.has(o));
        CHECK(t.count() == 8);
        acb_restore::Touched u;
        u.scan(acb, kNone);
        CHECK(u.unreadable() == 2); // the pairs table and the IB2
        CHECK(u.count() == 5);
    }
}
