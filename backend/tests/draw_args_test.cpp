// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0381: the indirect draw argument journal (bc5/draw_args.hpp). Synthetic IBs and an
// in-test memory; no GPU access.
#include "bc5/draw_args.hpp"

#include <catch2/catch_test_macros.hpp>

#include <array>
#include <cstddef>
#include <map>

using namespace bc5::draw_args;

namespace {

std::uint32_t pkt3(std::uint32_t op, std::uint32_t count) { return 0xC0000000u | (count << 16) | (op << 8); }

void set_base1(std::vector<std::uint32_t> &ib, std::uint64_t va) {
    ib.insert(ib.end(), {pkt3(0x11, 2), 1u, static_cast<std::uint32_t>(va), static_cast<std::uint32_t>(va >> 32)});
}

void draw_indirect(std::vector<std::uint32_t> &ib, std::uint32_t off, std::uint32_t op = 0x24) {
    ib.insert(ib.end(), {pkt3(op, 3), off, 0x0000004cu, 0x0000004du, 2u});
}

struct Mem {
    std::map<std::uint64_t, std::array<std::uint32_t, 4>> at;
    Reader reader() {
        return [this](std::uint64_t a, std::uint32_t (&out)[4]) {
            auto it = at.find(a);
            if (it == at.end())
                return false;
            for (std::size_t k = 0; k < 4; ++k)
                out[k] = it->second[k];
            return true;
        };
    }
};

} // namespace

TEST_CASE("scan finds based indirect draws and counts unbased ones", "[draw_args]") {
    std::vector<std::uint32_t> ib;
    draw_indirect(ib, 0x40); // before any SET_BASE: unbased
    set_base1(ib, 0x1193ad3900ull);
    ib.push_back(0xffff1000u); // a one-dword NOP between
    draw_indirect(ib, 0xc4a0);
    draw_indirect(ib, 0x22940, 0x25);
    Mem m;
    m.at[0x1193ad3900ull + 0xc4a0] = {0x000f0101u, 0x000f0102u, 0x000f0103u, 0x000f0104u};
    std::uint32_t unbased = 0;
    const auto recs = scan(ib, 0, m.reader(), &unbased);
    REQUIRE(unbased == 1);
    REQUIRE(recs.size() == 2);
    CHECK(recs[0].addr == 0x1193ad3900ull + 0xc4a0);
    CHECK(recs[0].op == 0x24);
    CHECK(recs[0].read);
    CHECK(recs[0].v[1] == 0x000f0102u);
    CHECK(recs[1].op == 0x25);
    CHECK_FALSE(recs[1].read); // not in the test memory
}

TEST_CASE("the IB's base at entry is used until a SET_BASE of index 1", "[draw_args]") {
    std::vector<std::uint32_t> ib;
    draw_indirect(ib, 0x10);
    ib.insert(ib.end(), {pkt3(0x11, 2), 0u, 0x5000u, 0u}); // SET_BASE index 0: ignored
    draw_indirect(ib, 0x20);
    const auto recs = scan(ib, 0x1000, Reader{});
    REQUIRE(recs.size() == 2);
    CHECK(recs[0].addr == 0x1010);
    CHECK(recs[1].addr == 0x1020);
    CHECK_FALSE(recs[0].read);
}

TEST_CASE("classify: the 18:08 slots against sane draws", "[draw_args]") {
    const Limits lim; // 2^20 vertices, 64 instances
    Rec r;
    r.read = true;
    const std::uint32_t garbage[][4] = {{0x000f0101u, 0x000f0102u, 0x000f0103u, 0x000f0104u},
                                        {0x00050006u, 0x00050007u, 0x00050008u, 0x00050009u},
                                        {0x000f0119u, 0x000d007au, 0x000d007bu, 0x000d007cu},
                                        {0x000a01a7u, 0x000a01a8u, 0x000a01a9u, 0x000a01aau}};
    for (const auto &g : garbage) {
        for (int k = 0; k < 4; ++k)
            r.v[k] = g[k];
        const std::uint32_t f = classify(r, lim);
        CHECK((f & kIndexLike) != 0);
        CHECK((f & kOverInstances) != 0);
    }
    const std::uint32_t sane[][4] = {{0x35u, 1u, 0u, 0u}, {1u, 1u, 0u, 0u}, {94322u, 1u, 0u, 0u}, {3u, 4u, 5u, 6u}};
    for (const auto &s : sane) {
        for (int k = 0; k < 4; ++k)
            r.v[k] = s[k];
        CHECK(classify(r, lim) == 0);
    }
    // 14127's words: over the instance limit, not a clean run of steps
    r.v[0] = 0x8a64u, r.v[1] = 0xa418u, r.v[2] = 0xa41du, r.v[3] = 0xa48du;
    CHECK(classify(r, lim) == kOverInstances);
    r.read = false;
    CHECK(classify(r, lim) == kUnread);
}

TEST_CASE("line and reread report what changed between submit and completion", "[draw_args]") {
    Mem m;
    const std::uint64_t a = 0x1193aef8e0ull;
    m.at[a] = {0x35u, 1u, 0u, 0u};
    std::vector<std::uint32_t> ib;
    set_base1(ib, 0x1193ad3900ull);
    draw_indirect(ib, static_cast<std::uint32_t>(a - 0x1193ad3900ull));
    const auto sub = scan(ib, 0, m.reader());
    REQUIRE(sub.size() == 1);
    m.at[a] = {0x00050006u, 0x00050007u, 0x00050008u, 0x00050009u};
    const auto done = reread(sub, m.reader());
    const Limits lim;
    const std::string s = line("submit", 127530, sub[0], classify(sub[0], lim), "done", &done[0], classify(done[0], lim));
    CHECK(s == "draw-args submit seq 127530 at 4 op 0x24 base 0x1193ad3900 addr 0x1193aef8e0 v 00000035 00000001 "
               "00000000 00000000 flags - | done v 00050006 00050007 00050008 00050009 flags over-instances,index-like "
               "changed yes");
    const std::string same = line("submit", 1, sub[0], 0, "done", &sub[0], 0);
    CHECK(same.substr(same.size() - 10) == "changed no");
    CHECK(flag_names(kUnread) == "unread");
}
