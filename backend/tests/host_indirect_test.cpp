// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/host_indirect.hpp"

#include <catch2/catch_test_macros.hpp>

#include <cstdint>
#include <map>
#include <vector>

using namespace bc5;

namespace {
constexpr std::uint32_t kNop = 0xC0001000u;
constexpr std::uint32_t kDispatch = 0xC0011600u;        // DISPATCH_INDIRECT, GFX form, graphics type
constexpr std::uint32_t kDispatchCompute = 0xC0011602u; // ... compute type
constexpr std::uint32_t kSetBase = 0xC0021100u;         // SET_BASE, graphics type
constexpr std::uint32_t kSetBaseCompute = 0xC0021102u;

// A fake title memory: the counts at given addresses.
struct Memory {
    std::map<std::uint64_t, std::uint32_t> words;
    host_indirect::Reader reader() const {
        return [this](std::uint64_t va, std::uint32_t (&c)[3]) {
            for (std::size_t k = 0; k < 3; ++k) {
                const auto it = words.find(va + 4 * k);
                if (it == words.end()) return false;
                c[k] = it->second;
            }
            return true;
        };
    }
};
const std::vector<host_indirect::Region> kRegions = {{0x11'9600'0000ull, 0x600'0000ull}, {0x12'3456'0000ull, 0x1'0000ull}};
const host_indirect::Register kNever;                      // never set since the device opened
const host_indirect::Register kZeroed{0, true};            // the title's zeroing seen
const host_indirect::Register kCarried{0x12'3456'7000ull}; // a non-zero register from an earlier job
} // namespace

TEST_CASE("host_indirect: the refit's dispatch after the title's zeroing is verified and rewritten", "[host_indirect]") {
    // SET_SH_REG COMPUTE_PGM_LO/HI = 0x90997a500, then DISPATCH_INDIRECT offset 0x9bce4d80 (exp 0344, hang 2), the
    // register 0 by the zeroing pair of the previous buffer.
    std::vector<std::uint32_t> ib = {0xC0027600u, 0x20cu, 0x0909'97a5u, 0u, kDispatch, 0x9bce4d80u, 0x61u, kNop, 0u};
    Memory mem;
    mem.words[0x11'9bce'4d80ull] = 64;
    mem.words[0x11'9bce'4d84ull] = 1;
    mem.words[0x11'9bce'4d88ull] = 1;
    host_indirect::Stats st;
    auto d = host_indirect::resolve_indirect(ib, kZeroed, 0x11'0000'0000ull, kRegions, mem.reader(), host_indirect::Limits{}, st);
    REQUIRE(d.size() == 1);
    CHECK(d[0].at == 4);
    CHECK(d[0].shader_type == 0);
    CHECK(d[0].program == 0x9'0997'a500ull);
    CHECK(d[0].base == 0);
    CHECK(d[0].window == 0x11'0000'0000ull);
    CHECK(d[0].address == 0x11'9bce'4d80ull);
    CHECK(d[0].page == 0x11'9bce'4000ull);
    CHECK(d[0].decision == host_indirect::Decision::Rewrite);
    CHECK(d[0].counts[0] == 64);
    CHECK(st.rewritten == 1);
    CHECK(st.register_out.base == 0);
    CHECK(st.register_out.zeroed);
    CHECK(host_indirect::rewrite_verified(ib, d, st));
    // SET_BASE (graphics) = the page, the dispatch with offset 0xd80, SET_BASE 0, then the NOP as it was.
    REQUIRE(ib.size() == 9 + host_indirect::kRewriteDwords);
    std::size_t i = 4;
    CHECK(ib[i] == kSetBase);
    CHECK(ib[i + 1] == 1u);
    CHECK(ib[i + 2] == 0x9bce4000u);
    CHECK(ib[i + 3] == 0x11u);
    i += 4;
    CHECK(ib[i] == kDispatch);
    CHECK(ib[i + 1] == 0xd80u);
    CHECK(ib[i + 2] == 0x61u);
    i += 3;
    CHECK(ib[i] == kSetBase);
    CHECK(ib[i + 2] == 0u);
    CHECK(ib[i + 3] == 0u);
    CHECK(ib[i + 4] == kNop);
    // The same zeroing seen in this IB (the title's pair, compute type then graphics type) has the same effect.
    std::vector<std::uint32_t> pair = {kSetBaseCompute, 1u, 0u, 0u, kSetBase, 1u, 0u, 0u, kDispatch, 0x9bce4d80u, 0x61u};
    host_indirect::Stats s2;
    auto d2 = host_indirect::resolve_indirect(pair, kCarried, 0x11'0000'0000ull, kRegions, mem.reader(), host_indirect::Limits{}, s2);
    REQUIRE(d2.size() == 1);
    CHECK(d2[0].decision == host_indirect::Decision::Rewrite);
    CHECK(s2.register_out.base == 0);
    CHECK(s2.register_out.zeroed);
    CHECK(s2.window_seen == 0);
}

TEST_CASE("host_indirect: a non-zero register, set here or carried, and a register never set leave the dispatch alone",
          "[host_indirect]") {
    Memory mem;
    mem.words[0x12'3456'7040ull] = 8;
    mem.words[0x12'3456'7044ull] = 1;
    mem.words[0x12'3456'7048ull] = 1;
    {
        // The host's own conversion: a compute-type SET_BASE then a graphics-type dispatch (one register: served).
        const std::vector<std::uint32_t> ib = {kSetBaseCompute, 1u, 0x34567000u, 0x12u, kDispatch, 0x40u, 0x61u,
                                               kDispatchCompute, 0x80u, 0x61u};
        host_indirect::Stats st;
        auto d = host_indirect::resolve_indirect(ib, kNever, 0x11'0000'0000ull, kRegions, mem.reader(), host_indirect::Limits{}, st);
        REQUIRE(d.size() == 2);
        CHECK(d[0].decision == host_indirect::Decision::Leave);
        CHECK(d[0].why == host_indirect::Why::NonZero);
        CHECK(d[0].address == 0x12'3456'7040ull);
        CHECK(d[1].decision == host_indirect::Decision::Leave);
        CHECK(st.left_nonzero == 2);
        CHECK(st.register_out.base == 0x12'3456'7000ull);
        CHECK(!st.register_out.zeroed);
        CHECK(st.window_seen == 0x12'0000'0000ull);
        std::vector<std::uint32_t> copy = ib;
        CHECK(host_indirect::rewrite_verified(copy, d, st));
        CHECK(copy == ib); // nothing changed
    }
    {
        // A dispatch before any SET_BASE in its IB, the register carried non-zero from an earlier job: left.
        const std::vector<std::uint32_t> ib = {kDispatch, 0x40u, 0x61u};
        host_indirect::Stats st;
        auto d = host_indirect::resolve_indirect(ib, kCarried, 0x11'0000'0000ull, kRegions, mem.reader(), host_indirect::Limits{}, st);
        REQUIRE(d.size() == 1);
        CHECK(d[0].why == host_indirect::Why::NonZero);
        CHECK(d[0].address == 0x12'3456'7040ull);
        CHECK(st.register_out.base == 0x12'3456'7000ull);
    }
    {
        // The register never set since the device opened: left, counted apart.
        const std::vector<std::uint32_t> ib = {kDispatch, 0x9bce4d80u, 0x61u};
        host_indirect::Stats st;
        auto d = host_indirect::resolve_indirect(ib, kNever, 0x11'0000'0000ull, kRegions, mem.reader(), host_indirect::Limits{}, st);
        REQUIRE(d.size() == 1);
        CHECK(d[0].decision == host_indirect::Decision::Leave);
        CHECK(d[0].why == host_indirect::Why::NeverSet);
        CHECK(st.left_never_set == 1);
        CHECK(!st.register_out.zeroed);
    }
}

TEST_CASE("host_indirect: after the zeroing, an unverified candidate is NOP-ed, each for its reason", "[host_indirect]") {
    Memory mem;
    mem.words[0x11'9bce'4d80ull] = 1u << 20;
    mem.words[0x11'9bce'4d84ull] = 1;
    mem.words[0x11'9bce'4d88ull] = 1;
    std::vector<std::uint32_t> ib = {kDispatch, 0x9bce4d80u, 0x61u};
    {
        host_indirect::Stats st; // no window known
        auto d = host_indirect::resolve_indirect(ib, kZeroed, 0, kRegions, mem.reader(), host_indirect::Limits{}, st);
        REQUIRE(d.size() == 1);
        CHECK(d[0].decision == host_indirect::Decision::Drop);
        CHECK(d[0].why == host_indirect::Why::NoCandidate);
        CHECK(st.dropped_no_candidate == 1);
    }
    {
        host_indirect::Stats st; // outside every real mapping
        const std::vector<host_indirect::Region> none;
        auto d = host_indirect::resolve_indirect(ib, kZeroed, 0x11'0000'0000ull, none, mem.reader(), host_indirect::Limits{}, st);
        CHECK(d[0].why == host_indirect::Why::NotRealMapping);
        CHECK(st.dropped_unmapped == 1);
    }
    {
        host_indirect::Stats st; // in a mapping, but the CPU cannot read it
        const Memory empty;
        auto d = host_indirect::resolve_indirect(ib, kZeroed, 0x11'0000'0000ull, kRegions, empty.reader(), host_indirect::Limits{}, st);
        CHECK(d[0].why == host_indirect::Why::Unreadable);
        CHECK(st.dropped_unreadable == 1);
    }
    {
        host_indirect::Stats st; // readable, but the counts fail the limits
        Memory bad = mem;
        bad.words[0x11'9bce'4d84ull] = 4294962046u;
        auto d = host_indirect::resolve_indirect(ib, kZeroed, 0x11'0000'0000ull, kRegions, bad.reader(), host_indirect::Limits{}, st);
        CHECK(d[0].why == host_indirect::Why::Insane);
        CHECK(st.dropped_insane == 1);
        std::vector<std::uint32_t> copy = ib;
        CHECK(host_indirect::rewrite_verified(copy, d, st));
        REQUIRE(copy.size() == ib.size());
        CHECK(copy[0] == (kNop | (1u << 16))); // a NOP of the dispatch's three dwords
        CHECK(copy[1] == 0x9bce4d80u);
    }
}

TEST_CASE("host_indirect: a COND_EXEC count that cannot grow turns the rewrites into NOPs", "[host_indirect]") {
    Memory mem;
    mem.words[0x11'9bce'4d80ull] = 1;
    mem.words[0x11'9bce'4d84ull] = 1;
    mem.words[0x11'9bce'4d88ull] = 1;
    // A COND_EXEC whose range (0x3ff8 dwords: the dispatch and a long NOP) ends within 8 of the 14-bit limit
    // (insert_before clamps a range past the IB's end, so the range has to end at a real packet).
    constexpr std::uint32_t kRange = 0x3ff8u;
    std::vector<std::uint32_t> ib = {0xC0032200u, 0x1000u, 0u, 0u, kRange, kDispatch, 0x9bce4d80u, 0x61u};
    ib.push_back(0xC0001000u | ((kRange - 3u - 2u) << 16)); // a NOP of kRange - 3 dwords
    ib.resize(5 + kRange, 0u);
    host_indirect::Stats st;
    auto d = host_indirect::resolve_indirect(ib, kZeroed, 0x11'0000'0000ull, kRegions, mem.reader(), host_indirect::Limits{}, st);
    REQUIRE(d.size() == 1);
    CHECK(d[0].decision == host_indirect::Decision::Rewrite);
    CHECK(!host_indirect::rewrite_verified(ib, d, st));
    REQUIRE(ib.size() == 5 + kRange);
    CHECK(ib[5] == (kNop | (1u << 16)));
    CHECK(ib[6] == 0x9bce4d80u); // the offset as it was
    CHECK(st.nop_on_overflow == 1);
}
