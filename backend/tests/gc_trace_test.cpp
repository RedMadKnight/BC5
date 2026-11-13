// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0418 section 3b: the pure parts of the /dev/gc caller trace.
#include "bc5/gc_trace.hpp"

#include <catch2/catch_test_macros.hpp>

#include <cstdint>
#include <cstring>
#include <map>
#include <vector>

namespace gt = bc5::gc_trace;

namespace {

// A sparse fake stack: quadwords by address; a read of an absent address fails.
struct FakeStack {
    std::map<std::uint64_t, std::uint64_t> q;
    void frame(std::uint64_t fp, std::uint64_t next, std::uint64_t ret) {
        q[fp] = next;
        q[fp + 8] = ret;
    }
    bool operator()(std::uint64_t addr, std::uint64_t *two) const {
        const auto a = q.find(addr), b = q.find(addr + 8);
        if (a == q.end() || b == q.end()) return false;
        two[0] = a->second;
        two[1] = b->second;
        return true;
    }
};

} // namespace

TEST_CASE("gc trace: a frame chain is walked to its end", "[gc_trace]") {
    FakeStack s;
    s.frame(0x7000, 0x7040, 0xA001);
    s.frame(0x7040, 0x70c0, 0xA002);
    s.frame(0x70c0, 0x0, 0xA003);
    std::uint64_t ret[8] = {};
    REQUIRE(gt::walk_frames(0x7000, s, ret, 8) == 3);
    CHECK(ret[0] == 0xA001);
    CHECK(ret[1] == 0xA002);
    CHECK(ret[2] == 0xA003);
}

TEST_CASE("gc trace: the walk stops on a bad frame and keeps what it had", "[gc_trace]") {
    std::uint64_t ret[8] = {};
    SECTION("non-increasing frame: a caller without frame pointers") {
        FakeStack s;
        s.frame(0x7000, 0x6ff0, 0xA001);
        s.frame(0x6ff0, 0x7100, 0xA002);
        CHECK(gt::walk_frames(0x7000, s, ret, 8) == 1);
    }
    SECTION("misaligned frame") {
        FakeStack s;
        s.frame(0x7000, 0x7043, 0xA001);
        CHECK(gt::walk_frames(0x7000, s, ret, 8) == 1);
    }
    SECTION("a frame beyond the span") {
        FakeStack s;
        s.frame(0x7000, 0x7000 + gt::kMaxSpan + 8, 0xA001);
        s.frame(0x7000 + gt::kMaxSpan + 8, 0, 0xA002);
        CHECK(gt::walk_frames(0x7000, s, ret, 8) == 1);
    }
    SECTION("unreadable frame") {
        FakeStack s;
        s.frame(0x7000, 0x8000, 0xA001);
        CHECK(gt::walk_frames(0x7000, s, ret, 8) == 1);
    }
    SECTION("zero return address") {
        FakeStack s;
        s.frame(0x7000, 0x7040, 0);
        CHECK(gt::walk_frames(0x7000, s, ret, 8) == 0);
    }
    SECTION("null or misaligned start") {
        FakeStack s;
        CHECK(gt::walk_frames(0, s, ret, 8) == 0);
        CHECK(gt::walk_frames(0x7004, s, ret, 8) == 0);
    }
}

TEST_CASE("gc trace: the walk keeps to its maximum", "[gc_trace]") {
    FakeStack s;
    for (std::uint64_t i = 0; i < 20; ++i) s.frame(0x7000 + i * 0x40, 0x7000 + (i + 1) * 0x40, 0xA000 + i);
    std::uint64_t ret[gt::kMaxFrames] = {};
    CHECK(gt::walk_frames(0x7000, s, ret, gt::kMaxFrames) == gt::kMaxFrames);
    CHECK(ret[gt::kMaxFrames - 1] == 0xA000 + gt::kMaxFrames - 1);
}

TEST_CASE("gc trace: the stack scan keeps code addresses in order", "[gc_trace]") {
    const std::uint64_t words[] = {0, 0x1234, 0xA0010, 0x55, 0xA0FF0, 0xB0000, 0xA0020};
    const auto is_code = [](std::uint64_t w) { return w >= 0xA0000 && w < 0xA1000; };
    std::uint64_t out[8] = {};
    REQUIRE(gt::scan_words(words, 7, is_code, out, 8) == 3);
    CHECK(out[0] == 0xA0010);
    CHECK(out[1] == 0xA0FF0);
    CHECK(out[2] == 0xA0020);
    CHECK(gt::scan_words(words, 7, is_code, out, 2) == 2);
}

TEST_CASE("gc trace: the nearest export at or below an address", "[gc_trace]") {
    const gt::Export ex[] = {{0x2000, "B#A#A"}, {0x1000, "A#A#A"}, {0x3000, "C#A#A"}};
    CHECK(gt::nearest_export(ex, 3, 0x0fff) == nullptr);
    CHECK(gt::nearest_export(ex, 3, 0x1000)->name == "A#A#A");
    CHECK(gt::nearest_export(ex, 3, 0x2fff)->name == "B#A#A");
    CHECK(gt::nearest_export(ex, 3, 0x9000)->name == "C#A#A");
    CHECK(gt::nearest_export(ex, 0, 0x9000) == nullptr);
}

TEST_CASE("gc trace: the NID of a dynamic symbol name", "[gc_trace]") {
    CHECK(gt::nid_of("XlNp7jzGiPo#A#B") == "XlNp7jzGiPo");
    CHECK(gt::nid_of("XlNp7jzGiPo") == "XlNp7jzGiPo");
    CHECK(gt::nid_of("") == "");
    CHECK(gt::nid_of("#A#B") == "");
}

TEST_CASE("gc trace: the switch reads like bc5::env_on", "[gc_trace]") {
    CHECK_FALSE(gt::switch_on(nullptr));
    CHECK_FALSE(gt::switch_on(""));
    CHECK_FALSE(gt::switch_on("0"));
    CHECK(gt::switch_on("1"));
    CHECK(gt::switch_on("00"));
}
