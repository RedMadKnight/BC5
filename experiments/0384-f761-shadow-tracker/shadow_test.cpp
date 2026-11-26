// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0384: the shadow against the real Tracker and against the oracle. Synthetic packets only.
#include "oracle.hpp"
#include "shadow_state.hpp"

#include <catch2/catch_test_macros.hpp>

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <initializer_list>
#include <random>
#include <vector>

using namespace bc5;
using oracle::kReg0;
using oracle::Memory;
using Buf = std::vector<std::uint32_t>;
using Stream = std::vector<Buf>;

namespace {

constexpr std::uint32_t kChain = 1u << 20;

Buf set(std::uint32_t reg, std::uint32_t v) { return {0xC0017600u, reg, v}; }
Buf ud0(std::uint32_t v) { return set(kReg0, v); }
Buf ib(std::uint64_t a, std::size_t n, bool chain) {
    return {0xC0023F00u, static_cast<std::uint32_t>(a), static_cast<std::uint32_t>(a >> 32), static_cast<std::uint32_t>(n) | (chain ? kChain : 0u)};
}
Buf cond(std::uint32_t dwords) { return {0xC0032200u, 0x2000, 0, 0, dwords}; }
Buf pairs_table(std::uint64_t a, std::uint32_t n) {
    return {0xC0036300u, static_cast<std::uint32_t>(a), static_cast<std::uint32_t>(a >> 32), 0x80000000u, n};
}
Buf flat_table(std::uint64_t a, std::uint32_t off, std::uint32_t n) {
    return {0xC0036300u, static_cast<std::uint32_t>(a), static_cast<std::uint32_t>(a >> 32), off, n};
}
Buf load_range(std::uint64_t base, std::uint32_t off, std::uint32_t n) {
    return {0xC0035F00u, static_cast<std::uint32_t>(base), static_cast<std::uint32_t>(base >> 32), off, n};
}
Buf cat(std::initializer_list<Buf> parts) {
    Buf out;
    for (const auto &p : parts) out.insert(out.end(), p.begin(), p.end());
    return out;
}
full_state::Tracker::Reader reader(const Memory &m) {
    return [&m](std::uint64_t a, std::uint64_t bytes) -> const std::uint32_t * {
        const auto it = m.find(a);
        return it != m.end() && it->second.size() * 4 == bytes ? it->second.data() : nullptr;
    };
}
shadow::ShadowState walk(const Stream &s, const Memory &m, shadow::ShadowState::Options o = {}) {
    shadow::ShadowState st(o);
    const auto r = reader(m);
    for (const Buf &b : s) st.apply(b, r);
    return st;
}
shadow::State state_of(const shadow::ShadowState &s, std::uint32_t reg, std::uint32_t &v) { return s.get(full_state::Sh, reg, v); }

// Certain must hold at every end, under both readings of a count past the end. 0 sound, 1 unsound, 2 too big to check.
int verdict(const Stream &s, const Memory &m, const shadow::ShadowState &st) {
    for (const bool carry : {false, true}) {
        oracle::Oracle o(m, carry);
        const auto ways = o.run(s);
        if (o.overflowed()) return 2;
        for (std::size_t k = 0; k < oracle::kRegs; ++k) {
            std::uint32_t v = 0;
            if (state_of(st, kReg0 + static_cast<std::uint32_t>(k), v) != shadow::State::Certain) continue;
            for (const auto &w : ways)
                if (w.r[k] != static_cast<std::int64_t>(v)) return 1;
        }
    }
    return 0;
}

constexpr std::uint64_t kA[] = {0x1000, 0x2000, 0x3000}, kTable = 0x4000, kFlat = 0x5000, kRange = 0x7000, kGone = 0x9000;

Buf gen_buffer(std::mt19937 &g, const Memory &m, int max_packets) {
    const auto pick = [&g](std::uint32_t n) { return static_cast<std::uint32_t>(g() % n); };
    Buf b;
    const std::uint32_t packets = 1 + pick(static_cast<std::uint32_t>(max_packets));
    for (std::uint32_t k = 0; k < packets; ++k) {
        const std::uint32_t x = pick(100);
        if (x < 45) {
            const Buf p = set(kReg0 + pick(3), pick(3));
            b.insert(b.end(), p.begin(), p.end());
        } else if (x < 65) {
            const Buf p = cond(1 + pick(9));
            b.insert(b.end(), p.begin(), p.end());
        } else if (x < 68) {
            const Buf p = pairs_table(pick(4) == 0 ? kGone : kTable, 2);
            b.insert(b.end(), p.begin(), p.end());
        } else if (x < 71) {
            const Buf p = flat_table(pick(4) == 0 ? kGone : kFlat, kReg0, 2);
            b.insert(b.end(), p.begin(), p.end());
        } else if (x < 74) {
            const Buf p = load_range(pick(4) == 0 ? kGone : kRange, kReg0 + 1, 2);
            b.insert(b.end(), p.begin(), p.end());
        } else if (x < 79) { // short forms of known packets
            static const std::uint32_t heads[] = {0xC0007600u, 0xC0003F00u, 0xC0013F00u, 0xC0002200u, 0xC0005F00u, 0xC0016300u};
            const std::uint32_t h = heads[pick(6)];
            const std::uint32_t body = ((h >> 16) & 0x3fffu) + 1;
            b.push_back(h);
            for (std::uint32_t q = 0; q < body; ++q) b.push_back(pick(3));
        } else {
            const std::uint64_t a = pick(5) == 0 ? kGone : kA[pick(3)];
            const auto it = m.find(a);
            const Buf p = ib(a, it == m.end() ? 3 : it->second.size(), pick(2) == 0);
            b.insert(b.end(), p.begin(), p.end());
        }
    }
    return b;
}
struct Case {
    Memory m;
    Stream s;
};
Case gen_case(std::mt19937 &g) {
    Case c;
    c.m[kTable] = {kReg0 + 1, 2, kReg0, 1};
    c.m[kFlat] = {2, 1};
    c.m[kRange + (kReg0 + 1) * 4ull] = {1, 2};
    // Sizes first, so that buffers can point at each other with the right size.
    for (const auto a : kA) c.m[a] = {0xC0001000u, 0};
    for (const auto a : kA) {
        Buf b = gen_buffer(g, c.m, 3);
        c.m[a] = std::move(b);
    }
    // A target's size may have changed after a pointer to it was made: such a pointer reads as unreadable, which is a
    // case too, in both the shadow and the oracle.
    const std::size_t buffers = 1 + g() % 3;
    for (std::size_t k = 0; k < buffers; ++k) c.s.push_back(gen_buffer(g, c.m, 5));
    return c;
}

} // namespace

TEST_CASE("Codex's case 1: a CHAIN makes old and shadow differ, and the old bytes stay", "[shadow]") {
    Memory m;
    m[0x1000] = ud0(0x22);
    const Buf b = cat({ib(0x1000, 3, true), ud0(0x33)});
    const auto r = reader(m);
    full_state::Tracker alone;
    full_state::Stats st;
    alone.apply(b, r, st);
    shadow::Pair pair;
    pair.apply(b, r);
    std::uint32_t old = 0, sh = 0;
    REQUIRE(pair.old.get(full_state::Sh, kReg0, old));
    CHECK(old == 0x33u); // the defect, still there in the real tracker: this prototype does not touch it
    REQUIRE(pair.shadow.get(full_state::Sh, kReg0, sh) == shadow::State::Certain);
    CHECK(sh == 0x22u);
    CHECK(pair.old.emit_prefix() == alone.emit_prefix());
    CHECK(verdict({b}, m, pair.shadow) == 0);
    CHECK(pair.shadow.stats().chains == 1);
}

TEST_CASE("Codex's case 2: a count past the end of a buffer carries no false certainty", "[shadow]") {
    const Stream s = {cat({ud0(0x11), cond(3)}), ud0(0x22)};
    const Memory m;
    oracle::Oracle stops(m, false), carries(m, true);
    const auto a = stops.run(s), b = carries.run(s);
    REQUIRE(a.size() == 1); // stopping at the end: 0x22
    CHECK(a[0].r[0] == 0x22);
    REQUIRE(b.size() == 2); // carrying on: 0x11 or 0x22
    const auto st = walk(s, m);
    std::uint32_t v = 0;
    CHECK(state_of(st, kReg0, v) == shadow::State::Uncertain);
    CHECK(verdict(s, m, st) == 0);
    auto no_carry = shadow::ShadowState::Options{};
    no_carry.carry = false;
    const auto bad = walk(s, m, no_carry);
    CHECK(state_of(bad, kReg0, v) == shadow::State::Certain);
    CHECK(verdict(s, m, bad) == 1); // the gap Codex found, if the carry is taken out
}

TEST_CASE("the contract on named streams", "[shadow]") {
    Memory m;
    m[0x1000] = ud0(0x22);
    m[0x2000] = {0xC0001000u, 0}; // a NOP
    m[0x5000] = ib(0x5000, 4, true);
    const auto one = [&m](const Buf &b, shadow::State want, std::uint32_t value = 0) {
        const auto st = walk({b}, m);
        std::uint32_t v = 0;
        const auto got = state_of(st, kReg0, v);
        CHECK(got == want);
        if (want == shadow::State::Certain) CHECK(v == value);
        CHECK(verdict({b}, m, st) == 0);
    };
    using shadow::State;
    one(cat({ib(0x1000, 3, false), ud0(0x33)}), State::Certain, 0x33);                        // a call
    one(cat({ud0(0x11), ib(0x9000, 3, true), ud0(0x33)}), State::Uncertain);                  // unreadable CHAIN, seed
    one(cat({ud0(0x11), ib(0x9000, 3, false)}), State::Uncertain);                            // unreadable call, seed
    one(cat({ud0(0x11), ib(0x9000, 3, false), ud0(0x33)}), State::Certain, 0x33);             // a later plain write
    one(cat({cond(4), ib(0x1000, 3, true), ud0(0x33)}), State::Uncertain);                    // both ways of a conditional CHAIN
    one(cat({ud0(0x11), cond(4), ib(0x2000, 2, true)}), State::Certain, 0x11);                // silent target, seed
    one(cat({ud0(0x11), cond(4), ib(0x1000, 3, false)}), State::Uncertain);                   // conditional call
    one(cat({ud0(0x11), cond(3), ud0(0x11)}), State::Certain, 0x11);                          // the same value
    one(cat({ud0(0x11), cond(3), ud0(0x22)}), State::Uncertain);
    one(cat({ud0(0x11), cond(4), ib(0x1000, 3, false), ud0(0x33)}), State::Certain, 0x33);    // after the condition
    one(cat({ud0(0x11), ib(0x5000, 4, true)}), State::Uncertain);                             // a cycle
    one(cat({ud0(0x11), cond(1), ud0(0x22)}), State::Uncertain);                              // a count inside a packet
    one(cat({ud0(0x11), {0xC0017600u, kReg0}}), State::Uncertain);                            // truncated
    one(cat({ud0(0x11), {0xC0083F00u, 0, 0, 0, 0, 0, 0, 0, 0, 3}}), State::Uncertain);        // the longer conditional IB
    one(cat({ud0(0x11), pairs_table(0x9000, 2)}), State::Uncertain);                          // an unreadable table
    // A count running past the end of a call's target carries back into the caller.
    m[0x6000] = cat({ud0(0x44), cond(3)});
    one(cat({ib(0x6000, 8, false), ud0(0x33)}), State::Uncertain);
    // CLEAR_STATE: context only, and the shadow keeps its stack apart from the old tracker's.
    const Buf ctx = cat({{0xC0016900u, 0x200, 7}, {0xC0001200u, 0}});
    auto st = walk({ctx}, m);
    std::uint32_t v = 0;
    CHECK(st.get(full_state::Context, 0x200, v) == shadow::State::Absent);
    st = walk({cat({{0xC0016900u, 0x200, 7}, cond(2), {0xC0001200u, 0}})}, m);
    CHECK(st.get(full_state::Context, 0x200, v) == shadow::State::Uncertain);
}

TEST_CASE("counts past a buffer's end: the oracle's two findings, kept as regressions", "[shadow]") {
    using shadow::State;
    Memory m;
    m[0x2000] = set(kReg0 + 2, 1);
    SECTION("different ways leave different counts: the smaller one lands inside a packet of the next buffer") {
        const Stream s = {set(kReg0 + 1, 2), cat({cond(6), cond(9)}), ib(0x2000, 3, false)};
        const auto st = walk(s, m);
        std::uint32_t v = 0;
        CHECK(state_of(st, kReg0 + 1, v) == State::Uncertain);
        CHECK(verdict(s, m, st) == 0);
    }
    SECTION("a count left by a CHAIN's target runs on after the buffer, not in the tail") {
        m[0x3000] = cond(9);
        const Stream s = {cat({cond(4), ib(0x3000, 5, true), ud0(1)}), ud0(2)};
        const auto st = walk(s, m);
        std::uint32_t v = 0;
        CHECK(state_of(st, kReg0, v) == State::Uncertain);
        CHECK(verdict(s, m, st) == 0);
    }
}

TEST_CASE("Codex's table counterexample: no cap, at the boundaries, in every form", "[shadow][tables]") {
    using shadow::State;
    constexpr std::uint32_t kHigh = 0x1100; // past 4,096 entries from offset 0x100
    const auto value = [](const shadow::ShadowState &st, std::uint32_t reg, State want, std::uint32_t v) {
        std::uint32_t got = 0;
        CHECK(st.get(full_state::Sh, reg, got) == want);
        if (want == State::Certain) CHECK(got == v);
    };
    shadow::ShadowState::Options capped;
    capped.table_cap = true;
    SECTION("pairs: the last entry writes the seeded register, n 4095, 4096, 4097") {
        for (const std::uint32_t n : {4095u, 4096u, 4097u}) {
            Memory m;
            Buf t;
            for (std::uint32_t k = 0; k + 1 < n; ++k) {
                t.push_back(kReg0 + 1);
                t.push_back(7);
            }
            t.push_back(kReg0);
            t.push_back(0x22);
            m[kTable] = t;
            const Stream s = {cat({ud0(0x11), pairs_table(kTable, n)})};
            const auto st = walk(s, m);
            value(st, kReg0, State::Certain, 0x22);
            CHECK(verdict(s, m, st) == 0);
            // The cap as Codex's probe met it: a reader that allows a shorter read of the same table.
            const full_state::Tracker::Reader prefix = [&m](std::uint64_t a, std::uint64_t bytes) -> const std::uint32_t * {
                const auto it = m.find(a);
                return it != m.end() && bytes <= it->second.size() * 4 ? it->second.data() : nullptr;
            };
            shadow::ShadowState old(capped);
            old.apply(s[0], prefix);
            value(old, kReg0, State::Certain, n > 4096 ? 0x11 : 0x22);
            CHECK(verdict(s, m, old) == (n > 4096 ? 1 : 0)); // fails with the cap, passes without it
            shadow::ShadowState fixed;
            fixed.apply(s[0], prefix);
            value(fixed, kReg0, State::Certain, 0x22);
            const Stream under = {cat({ud0(0x11), cond(5), pairs_table(kTable, n)})};
            const auto c = walk(under, m);
            value(c, kReg0, State::Uncertain, 0);
            CHECK(verdict(under, m, c) == 0);
            const Stream gone = {cat({ud0(0x11), pairs_table(kGone, n), ud0(0x11)})};
            CHECK(verdict(gone, m, walk(gone, m)) == 0);
            const Stream gone2 = {cat({ud0(0x11), pairs_table(kGone, n)})};
            value(walk(gone2, m), kReg0, State::Uncertain, 0);
        }
    }
    SECTION("flat, and LOAD_SH_REG: entry 4096 is the seeded register") {
        for (const std::uint32_t n : {4095u, 4096u, 4097u}) {
            for (const bool ranged : {false, true}) {
                Memory m;
                Buf t(n, 7);
                t[n - 1] = 0x22;
                const std::uint32_t off = 0x100;
                const std::uint64_t key = ranged ? kRange + off * 4ull : kFlat;
                m[key] = t;
                const Buf load = ranged ? load_range(kRange, off, n) : flat_table(kFlat, off, n);
                const Buf gone = ranged ? load_range(kGone, off, n) : flat_table(kGone, off, n);
                const std::uint32_t last = off + n - 1; // the table's last register
                const Buf seed = set(last, 0x11);
                value(walk({cat({seed, load})}, m), last, State::Certain, 0x22);
                value(walk({cat({seed, load})}, m, capped), last, State::Certain, n > 4096 ? 0x11 : 0x22); // fails old
                value(walk({cat({seed, cond(5), load})}, m), last, State::Uncertain, 0);
                value(walk({cat({seed, gone})}, m), last, State::Uncertain, 0);
                value(walk({cat({seed, gone, seed})}, m), last, State::Certain, 0x11);
            }
        }
        (void)kHigh;
    }
    SECTION("an unreadable pairs table names any register: a seed past its count is not safe either") {
        Memory m;
        const Stream s = {cat({set(kHigh, 0x11), pairs_table(kGone, 2)})};
        value(walk(s, m), kHigh, State::Uncertain, 0);
    }
    SECTION("the old tracker has the same cap: not fixed here, recorded") {
        Memory m;
        Buf t;
        for (std::uint32_t k = 0; k < 4096; ++k) {
            t.push_back(kReg0 + 1);
            t.push_back(7);
        }
        t.push_back(kReg0);
        t.push_back(0x22);
        m[kTable] = t;
        const auto r = reader(m);
        shadow::Pair pair;
        pair.apply(cat({ud0(0x11), pairs_table(kTable, 4097)}), r);
        std::uint32_t v = 0;
        REQUIRE(pair.old.get(full_state::Sh, kReg0, v));
        CHECK(v == 0x11u); // F764: the real tracker stops at 4,096 entries
    }
}

TEST_CASE("short forms of known packets, with no read past the packet", "[shadow][malformed]") {
    using shadow::State;
    Memory m;
    m[0x1000] = ud0(0x22);
    const std::vector<Buf> shorts = {
        {0xC0003F00u, 0x1000},             // IB of 2 dwords
        {0xC0013F00u, 0x1000, 0},          // IB of 3
        {0xC0027F00u, 0, 0, 0},            // an unknown opcode: not malformed
        {0xC0007600u, kReg0},              // SET_SH_REG with no value
        {0xC0002200u, 0},                  // COND_EXEC of 2
        {0xC0022200u, 0, 0, 0},            // COND_EXEC of 4
        {0xC0005F00u, 0},                  // LOAD_SH_REG of 2
        {0xC0025F00u, 0, 0, 0},            // of 4
        {0xC0045F00u, 0, 0, 0, 0, 0},      // of 6: an offset with no count
        {0xC0006300u, 0},                  // LOAD_SH_REG_INDEX of 2
    };
    for (const Buf &p : shorts) {
        const bool known = ((p[0] >> 8) & 0xffu) != 0x7fu;
        for (const Stream &s : {Stream{cat({ud0(0x11), p})}, Stream{cat({ud0(0x11), p, ud0(0x33)})}, Stream{p}}) {
            const auto st = walk(s, m);
            CHECK(verdict(s, m, st) == 0);
        }
        std::uint32_t v = 0;
        const auto st = walk({cat({ud0(0x11), p})}, m);
        CHECK(state_of(st, kReg0, v) == (known ? State::Uncertain : State::Certain));
    }
}

TEST_CASE("oracle against shadow on random streams, and the mutants are caught", "[shadow][oracle]") {
    const auto sweep = [](std::size_t n, shadow::ShadowState::Options o, std::uint32_t seed = 384) {
        std::mt19937 g(seed);
        std::size_t bad = 0, big = 0, certain = 0;
        for (std::size_t k = 0; k < n; ++k) {
            const Case c = gen_case(g);
            const auto st = walk(c.s, c.m, o);
            const int v = verdict(c.s, c.m, st);
            bad += v == 1;
            big += v == 2;
            std::uint32_t x = 0;
            for (std::uint32_t r = 0; r < oracle::kRegs; ++r) certain += state_of(st, kReg0 + r, x) == shadow::State::Certain;
        }
        return std::array<std::size_t, 3>{bad, big, certain};
    };
    const auto good = sweep(40000, {});
    std::printf("shadow: 40000 streams, unsound %zu, too big to check %zu, certain registers %zu\n", good[0], good[1], good[2]);
    CHECK(good[0] == 0);
    CHECK(good[1] < 400);
    CHECK(good[2] > 1000); // it must not get there by claiming nothing
    for (const std::uint32_t seed : {1384u, 2384u, 3384u}) {
        const auto more = sweep(100000, {}, seed);
        std::printf("shadow: seed %u, 100000 streams, unsound %zu, too big to check %zu\n", seed, more[0], more[1]);
        CHECK(more[0] == 0);
    }
    const auto mutant = [&sweep](const char *name, shadow::ShadowState::Options o) {
        const auto r = sweep(6000, o);
        std::printf("mutant %s: unsound in %zu of 6000\n", name, r[0]);
        CHECK(r[0] > 0);
    };
    using O = shadow::ShadowState::Options;
    { O o; o.chain_ends_level = false; mutant("CHAIN as a call", o); }
    { O o; o.carry = false; mutant("no carry past a buffer's end", o); }
    { O o; o.conditional_writes = false; mutant("conditional writes count as plain", o); }
    { O o; o.cannot_follow_clobbers = false; mutant("what cannot be followed is only counted", o); }
    { O o; o.conditional_chain_tail = false; mutant("the tail of a conditional CHAIN counts as plain", o); }
    { O o; o.inside_packet = false; mutant("a count inside a packet is ignored", o); }
}

TEST_CASE("the old tracker's emitted bytes are untouched, with and without CHAIN", "[shadow][bytes]") {
    std::mt19937 g(385);
    std::size_t with_chain = 0, differ = 0;
    for (std::size_t k = 0; k < 40000; ++k) {
        const Case c = gen_case(g);
        const auto r = reader(c.m);
        full_state::Tracker alone;
        full_state::Stats st;
        shadow::Pair pair;
        for (const Buf &b : c.s) {
            alone.apply(b, r, st);
            pair.apply(b, r);
        }
        REQUIRE(pair.old.emit_prefix() == alone.emit_prefix());
        with_chain += pair.shadow.stats().chains != 0;
        for (std::uint32_t reg = kReg0; reg < kReg0 + oracle::kRegs; ++reg) {
            std::uint32_t a = 0, b = 0;
            if (pair.shadow.get(full_state::Sh, reg, b) == shadow::State::Certain && pair.old.get(full_state::Sh, reg, a) && a != b) ++differ;
        }
    }
    std::printf("bytes: 40000 streams identical, %zu with a CHAIN; old value differs from a certain shadow value on %zu registers\n", with_chain, differ);
    CHECK(with_chain > 1000);
    CHECK(differ > 0); // the defect is visible through the pair, without touching the tracker
}

TEST_CASE("on plain streams the shadow and the old tracker agree exactly", "[shadow]") {
    std::mt19937 g(386);
    for (std::size_t k = 0; k < 5000; ++k) {
        Buf b;
        for (int n = 0; n < 6; ++n) {
            const Buf p = set(kReg0 + g() % 3, static_cast<std::uint32_t>(g() % 5));
            b.insert(b.end(), p.begin(), p.end());
        }
        const Memory m;
        shadow::Pair pair;
        pair.apply(b, reader(m));
        for (std::uint32_t reg = kReg0; reg < kReg0 + 3; ++reg) {
            std::uint32_t a = 0, s = 0;
            const bool has = pair.old.get(full_state::Sh, reg, a);
            const auto st = pair.shadow.get(full_state::Sh, reg, s);
            REQUIRE(has == (st == shadow::State::Certain));
            if (has) REQUIRE(a == s);
        }
    }
}
