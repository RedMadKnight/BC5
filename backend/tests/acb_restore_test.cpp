// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/acb_restore.hpp"

#include <catch2/catch_test_macros.hpp>

#include <cstddef>
#include <cstdint>
#include <initializer_list>
#include <ios>
#include <map>
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
    SECTION("a write in an IB2 under COND_EXEC is unknown, at any depth; a later plain write settles it") {
        // Codex's J4 review: a seeded 0x11, then a skipped IB2 would keep 0x11.
        const std::vector<std::uint32_t> ib2 = set_sh(ud0, {0x11d00860u});
        const std::vector<std::uint32_t> ib1 = {0xC0023F00u, lo(ib2.data()), hi(ib2.data()), static_cast<std::uint32_t>(ib2.size())};
        std::vector<std::uint32_t> ib = set_sh(ud0, {0x11u});
        append(ib, {0xC0032200u, 0x1000, 0, 0, 4}); // COND_EXEC over the 4-dword INDIRECT_BUFFER
        append(ib, {0xC0023F00u, lo(ib1.data()), hi(ib1.data()), static_cast<std::uint32_t>(ib1.size())});
        CHECK(acb_restore::final_value(ib, ud0, kHost, v) == Final::Unknown);
        append(ib, set_sh(ud0, {0x11u}));
        REQUIRE(acb_restore::final_value(ib, ud0, kHost, v) == Final::Known);
        CHECK(v == 0x11u);
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

// PORT-CHAIN (F760). agc_chain_probe.cpp's cases, turned from a reproducer of the defect into
// regressions on the right answers, and the control flow around them. The packets are invented.
namespace {
constexpr std::uint32_t kChainBit = 1u << 20;

// Buffers at made-up addresses, read through a Reader; an address not listed cannot be read.
struct Memory {
    std::map<std::uint64_t, std::vector<std::uint32_t>> at;
    Tracker::Reader reader() const {
        return [this](std::uint64_t a, std::uint64_t bytes) -> const std::uint32_t * {
            const auto it = at.find(a);
            return it != at.end() && it->second.size() * 4 == bytes ? it->second.data() : nullptr;
        };
    }
};
std::vector<std::uint32_t> ib_packet(std::uint64_t a, std::size_t dwords, bool chain) {
    return {0xC0023F00u, static_cast<std::uint32_t>(a), static_cast<std::uint32_t>(a >> 32),
            static_cast<std::uint32_t>(dwords) | (chain ? kChainBit : 0u)};
}
std::vector<std::uint32_t> cond_exec(std::uint32_t skip) { return {0xC0032200u, 0x2000, 0, 0, skip}; }
std::vector<std::uint32_t> ud0(std::uint32_t v) { return set_sh(acb_restore::kUserData0, {v}); }
std::vector<std::uint32_t> cat(std::initializer_list<std::vector<std::uint32_t>> parts) {
    std::vector<std::uint32_t> out;
    for (const auto &p : parts) append(out, p);
    return out;
}
struct Answer {
    acb_restore::Final state;
    std::uint32_t value;
};
Answer run(const std::vector<std::uint32_t> &ib, const Memory &m) {
    std::uint32_t v = 0xdeadbeefu;
    const auto f = acb_restore::final_value(ib, acb_restore::kUserData0, m.reader(), v);
    return {f, v};
}
void known(const Answer &a, std::uint32_t v) {
    CHECK(a.state == acb_restore::Final::Known);
    CHECK(a.value == v);
}
void unknown(const Answer &a) {
    CHECK(a.state == acb_restore::Final::Unknown);
    CHECK(a.value == 0xdeadbeefu); // value is set only for Known
}
void none(const Answer &a) { CHECK(a.state == acb_restore::Final::None); }
} // namespace

TEST_CASE("final_value: a call returns, a CHAIN replaces the tail (the probe's four cases)", "[acb_restore][chain]") {
    Memory m;
    m.at[0x1000] = ud0(0x22);
    SECTION("a call: the tail runs after it") {
        known(run(cat({ib_packet(0x1000, 3, false), ud0(0x33)}), m), 0x33);
    }
    SECTION("a CHAIN: the tail is dead") {
        known(run(cat({ib_packet(0x1000, 3, true), ud0(0x33)}), m), 0x22);
    }
    SECTION("an unreadable CHAIN: the dead tail decides nothing") {
        unknown(run(cat({ib_packet(0x9000, 3, true), ud0(0x33)}), m));
    }
    SECTION("a conditional CHAIN whose ends differ") {
        unknown(run(cat({cond_exec(4), ib_packet(0x1000, 3, true), ud0(0x33)}), m));
    }
}

TEST_CASE("final_value: CHAIN through levels", "[acb_restore][chain]") {
    Memory m;
    SECTION("a CHAIN to a CHAIN") {
        m.at[0x1000] = cat({ib_packet(0x2000, 3, true), ud0(0x44)});
        m.at[0x2000] = ud0(0x22);
        known(run(cat({ib_packet(0x1000, 7, true), ud0(0x33)}), m), 0x22);
    }
    SECTION("a call that holds a CHAIN returns, and the caller's tail runs") {
        m.at[0x1000] = cat({ib_packet(0x2000, 3, true), ud0(0x44)});
        m.at[0x2000] = ud0(0x22);
        known(run(ib_packet(0x1000, 7, false), m), 0x22);
        known(run(cat({ib_packet(0x1000, 7, false), ud0(0x33)}), m), 0x33);
    }
    SECTION("a CHAIN to a buffer with a call: the call returns into the target") {
        m.at[0x1000] = cat({ib_packet(0x2000, 3, false), ud0(0x55)});
        m.at[0x2000] = ud0(0x22);
        known(run(cat({ib_packet(0x1000, 7, true), ud0(0x33)}), m), 0x55);
    }
    SECTION("a child that writes nothing keeps the seed, through a call and a CHAIN") {
        m.at[0x1000] = {0xC0001000u, 0}; // a NOP
        known(run(cat({ud0(0x11), ib_packet(0x1000, 2, false)}), m), 0x11);
        known(run(cat({ud0(0x11), ib_packet(0x1000, 2, true), ud0(0x33)}), m), 0x11);
        none(run(ib_packet(0x1000, 2, true), m));
    }
    SECTION("a malformed tail after a taken CHAIN is never parsed") {
        m.at[0x1000] = ud0(0x22);
        known(run(cat({ib_packet(0x1000, 3, true), {0xC0FF7600u}}), m), 0x22);
    }
}

TEST_CASE("final_value: conditions join every way through", "[acb_restore][chain]") {
    Memory m;
    m.at[0x1000] = ud0(0x22);
    m.at[0x2000] = {0xC0001000u, 0};  // writes nothing
    m.at[0x3000] = ud0(0x11);         // writes the seed's value
    SECTION("a conditional call: skipped keeps the seed") {
        unknown(run(cat({ud0(0x11), cond_exec(4), ib_packet(0x1000, 3, false)}), m));
        known(run(cat({ud0(0x11), cond_exec(4), ib_packet(0x3000, 3, false)}), m), 0x11);
        known(run(cat({ud0(0x11), cond_exec(4), ib_packet(0x2000, 2, false)}), m), 0x11);
        unknown(run(cat({cond_exec(4), ib_packet(0x1000, 3, false)}), m)); // None or 0x22
    }
    SECTION("a conditional CHAIN: both ends agree") {
        known(run(cat({cond_exec(4), ib_packet(0x1000, 3, true), ud0(0x22)}), m), 0x22);
        known(run(cat({ud0(0x11), cond_exec(4), ib_packet(0x2000, 2, true)}), m), 0x11);
    }
    SECTION("a conditional CHAIN: the ends differ") {
        unknown(run(cat({ud0(0x11), cond_exec(4), ib_packet(0x1000, 3, true)}), m));
    }
    SECTION("a conditional CHAIN with a child that writes nothing, and a tail") {
        unknown(run(cat({ud0(0x11), cond_exec(4), ib_packet(0x2000, 2, true), ud0(0x33)}), m));
    }
    SECTION("a write before the condition stands; a write after it settles") {
        known(run(cat({ud0(0x11), cond_exec(4), ib_packet(0x1000, 3, false), ud0(0x77)}), m), 0x77);
        known(run(cat({cond_exec(4), ib_packet(0x1000, 3, true), ud0(0x22), ud0(0x22)}), m), 0x22);
    }
    SECTION("a plain write settles after a way that CHAINed only if it was not the way out") {
        // Taken leaves with 0x22; not taken goes on to 0x33: the ends differ, however late the write.
        unknown(run(cat({cond_exec(4), ib_packet(0x1000, 3, true), ud0(0x33)}), m));
    }
    SECTION("a condition inside a call and inside a CHAIN target") {
        m.at[0x4000] = cat({cond_exec(3), ud0(0x66)});
        unknown(run(cat({ud0(0x11), ib_packet(0x4000, 8, false)}), m));
        unknown(run(cat({ud0(0x11), ib_packet(0x4000, 8, true), ud0(0x33)}), m));
        known(run(cat({ud0(0x11), ib_packet(0x4000, 8, false), ud0(0x33)}), m), 0x33);
    }
    SECTION("two conditions do not explode and still join") {
        std::vector<std::uint32_t> ib = ud0(0x11);
        for (int k = 0; k < 2000; ++k) append(ib, cat({cond_exec(3), ud0(0x11)}));
        known(run(ib, m), 0x11);
    }
}

TEST_CASE("final_value: what cannot be followed is Unknown, never certain", "[acb_restore][chain]") {
    Memory m;
    m.at[0x1000] = ud0(0x22);
    SECTION("an unreadable call is lost until a plain write") {
        unknown(run(ib_packet(0x9000, 3, false), m));
        known(run(cat({ib_packet(0x9000, 3, false), ud0(0x33)}), m), 0x33);
    }
    SECTION("no reader at all") {
        std::uint32_t v = 0xdeadbeefu;
        const auto ib = ib_packet(0x1000, 3, true);
        CHECK(acb_restore::final_value(ib, acb_restore::kUserData0, Tracker::Reader{}, v) == acb_restore::Final::Unknown);
    }
    SECTION("a size that does not match, and a zero size") {
        unknown(run(ib_packet(0x1000, 4, true), m));
        unknown(run(ib_packet(0x1000, 0, true), m));
        unknown(run(ib_packet(0x1000, 0, false), m));
    }
    SECTION("a CHAIN cycle, and a call cycle: a later write cannot rescue them") {
        m.at[0x5000] = ib_packet(0x5000, 4, true);
        m.at[0x6000] = ib_packet(0x6000, 4, false);
        unknown(run(ib_packet(0x5000, 4, true), m));
        unknown(run(cat({ib_packet(0x6000, 4, false), ud0(0x33)}), m));
        m.at[0x7000] = ib_packet(0x8000, 4, true);
        m.at[0x8000] = ib_packet(0x7000, 4, true);
        unknown(run(ib_packet(0x7000, 4, true), m));
    }
    SECTION("the same buffer twice in a row is no cycle") {
        known(run(cat({ib_packet(0x1000, 3, false), ib_packet(0x1000, 3, false)}), m), 0x22);
    }
    SECTION("the depth limit") {
        const auto chain_of = [&m](std::uint64_t n) {
            for (std::uint64_t k = 0; k + 1 < n; ++k)
                m.at[0x10000 + k * 16] = ib_packet(0x10000 + (k + 1) * 16, k + 2 == n ? 3u : 4u, true);
            m.at[0x10000 + (n - 1) * 16] = ud0(0x22);
            return ib_packet(0x10000, n == 1 ? 3u : 4u, true);
        };
        known(run(chain_of(acb_restore::detail::kFinalMaxDepth), m), 0x22);
        unknown(run(chain_of(acb_restore::detail::kFinalMaxDepth + 1), m));
    }
    SECTION("the work limit: a wide tree of calls ends as Unknown, not as an answer") {
        std::vector<std::uint32_t> leaf;
        for (int k = 0; k < 64; ++k) append(leaf, ib_packet(0x1000, 3, false));
        m.at[0x20000] = leaf;
        for (std::uint64_t d = 1; d < 6; ++d) {
            std::vector<std::uint32_t> up;
            for (int k = 0; k < 64; ++k) append(up, ib_packet(0x20000 * d, leaf.size(), false));
            m.at[0x20000 * (d + 1)] = up;
        }
        unknown(run(ib_packet(0x20000 * 6, leaf.size(), false), m));
    }
    SECTION("truncated and malformed packets") {
        unknown(run({0xC0017600u, acb_restore::kUserData0}, m));          // SET_SH_REG cut short
        unknown(run(cat({ud0(0x11), {0xC0027600u, 0x240}}), m));          // after a good write
        unknown(run(cat({ud0(0x11), {0xC0023F00u, 0x1000}}), m));         // an IB cut short
        unknown(run(cat({ud0(0x11), {0xC0013F00u, 0x1000, 0}}), m));      // an IB of the wrong length
        unknown(run(cat({ud0(0x11), {0xC0002200u, 0}}), m));              // a COND_EXEC too short
        unknown(run(cat({ud0(0x11), {0x40000000u}}), m));                 // type 1
        unknown(run(cat({ud0(0x11), cond_exec(9)}), m));                  // past the end
        unknown(run(cat({ud0(0x11), cond_exec(1), ud0(0x22)}), m));       // into a packet
        unknown(run(cat({ud0(0x11), {0xC0005F00u, 0x1000}, ud0(0x33)}), m)); // a LOAD_SH_REG too short
    }
    SECTION("the longer conditional IB is not decoded: Unknown, and a later write does not settle it") {
        // Codex's REVIEW-PORTS-01: opcode 0x3f of another length than 4. The body is made up; only the length matters.
        const std::vector<std::uint32_t> cond_ib = {0xC0083F00u, 0x1000, 0, 0, 0, 0, 0, 0, 0, 3};
        unknown(run(cat({ud0(0x11), cond_ib}), m));
        unknown(run(cat({ud0(0x11), cond_ib, ud0(0x33)}), m));
    }
    SECTION("the one-dword NOP pad and type 2 fillers are not malformed") {
        known(run(cat({ud0(0x11), {0xFFFF1000u, 0x80000000u}}), m), 0x11);
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
