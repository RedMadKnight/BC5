// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0379: the zero list and the skip set (bc5/zero_skip.hpp).
#include "bc5/zero_skip.hpp"

#include <catch2/catch_test_macros.hpp>

#include <cstdint>
#include <string>
#include <vector>

namespace {

using namespace bc5::zero_skip;
constexpr std::uint64_t M = 1ull << 20u;

TEST_CASE("the list round-trips through its text form", "[zero_skip]") {
    std::vector<Heap> in {{"RenderGpuWcLarge", 2758 * M, 5, {{0, 8 * M}, {2450 * M, 256 * M}}}, {"CommitIABufferAllocator", 2736 * M, 5, {{748 * M, 116 * M}}}};
    std::uint32_t     bad = 99;
    const auto        out = parse_list(format_list(in), &bad);
    CHECK(bad == 0);
    REQUIRE(out.size() == 2);
    CHECK(out[0].name == "RenderGpuWcLarge");
    CHECK(out[0].size == 2758 * M);
    CHECK(out[0].scans == 5);
    REQUIRE(out[0].runs.size() == 2);
    CHECK(out[0].runs[1] == std::pair<std::uint64_t, std::uint64_t>(2450 * M, 256 * M));
    CHECK(out[1].runs.size() == 1);
}

TEST_CASE("the parser drops bad, unaligned, out-of-heap, overlapping and orphan runs", "[zero_skip]") {
    const std::string text = "# c\n"
                             "heap H 0x10000000 3\r\n" // 256 MiB, CRLF
                             "zero H 0x0 0x400000\n"
                             "zero H 0x200000 0x200000\n"   // overlaps the run before
                             "zero H 0x500000 0x200000\n"   // not chunk aligned
                             "zero H 0xff00000 0x400000\n"  // past the heap's end
                             "zero X 0x0 0x200000\n"        // no such heap
                             "zero H 0x800000 0x0\n"        // empty
                             "garbage\n"
                             "heap H 0x10 1\n"              // a second H
                             "zero H 0x1000000 0x600000\n";
    std::uint32_t bad = 0;
    const auto    h   = parse_list(text, &bad);
    REQUIRE(h.size() == 1);
    CHECK(h[0].size == 0x10000000ull);
    CHECK(h[0].scans == 3);
    REQUIRE(h[0].runs.size() == 2);
    CHECK(h[0].runs[0].first == 0);
    CHECK(h[0].runs[1] == std::pair<std::uint64_t, std::uint64_t>(0x1000000, 0x600000));
    CHECK(bad == 7); // overlap, unaligned, past the end, orphan, empty, garbage, a second H
}

TEST_CASE("the mask keeps only chunks zero in every scan, and runs respect the minimum", "[zero_skip]") {
    const std::uint64_t size = 20 * M + 1 * M; // 10 whole chunks and a partial one
    ZeroMask            m(size);
    REQUIRE(m.chunks() == 11);
    CHECK(m.runs(size, 0).empty()); // no scan yet: nothing is known to be zero
    m.intersect({1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1});
    m.intersect({1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1}); // chunk 6 held data in the second scan
    CHECK(m.scans() == 2);
    CHECK(m.zero_bytes() == 9 * kChunk);
    const auto all = m.runs(size, 0);
    REQUIRE(all.size() == 3);
    CHECK(all[0] == std::pair<std::uint64_t, std::uint64_t>(0, 8 * M));
    CHECK(all[1] == std::pair<std::uint64_t, std::uint64_t>(10 * M, 2 * M));
    CHECK(all[2] == std::pair<std::uint64_t, std::uint64_t>(14 * M, 6 * M)); // the partial chunk 10 is not listed
    const auto big = m.runs(size, 8 * M);
    REQUIRE(big.size() == 1);
    CHECK(big[0].first == 0);
    m.intersect({1}); // a short scan (the heap shrank?) clears the chunks it did not cover
    CHECK(m.runs(size, 0).size() == 1);
    CHECK(m.zero_bytes() == kChunk);
}

TEST_CASE("all_zero finds a single set byte anywhere", "[zero_skip]") {
    std::vector<unsigned char> b(kChunk + 3, 0);
    CHECK(all_zero(b.data(), b.size()));
    for (const std::size_t at: {std::size_t {0}, std::size_t {7}, std::size_t {4096}, b.size() - 1}) {
        b[at] = 0x40;
        CHECK_FALSE(all_zero(b.data(), b.size()));
        b[at] = 0;
    }
}

TEST_CASE("the skip set places runs, gives chunks and runs back, and keeps run indices", "[zero_skip]") {
    Heap    h {"H", 64 * M, 4, {{0, 8 * M}, {16 * M, 4 * M}}};
    SkipSet s;
    const std::uint64_t base = 0x40000000ull;
    CHECK(place(h, base, &s) == 12 * M);
    CHECK(s.run_count() == 2);
    CHECK(s.contains(base));
    CHECK(s.contains(base + 6 * M));
    CHECK_FALSE(s.contains(base + 8 * M));
    CHECK(s.run_of(base + 16 * M) == 1);
    CHECK(s.run_of(base + 8 * M) == -1);
    CHECK(s.chunks_in(base + 1 * M, base + 18 * M) == std::vector<std::uint64_t> {base, base + 2 * M, base + 4 * M, base + 6 * M, base + 16 * M});
    // a CPU write in chunk 1 of run 0
    CHECK(s.erase_chunk(base + 2 * M));
    CHECK_FALSE(s.erase_chunk(base + 2 * M));
    CHECK(s.run_left(0) == 6 * M);
    CHECK(s.bytes() == 10 * M);
    // a canary hit in run 0 takes the rest of it back
    CHECK(s.erase_run(0) == 6 * M);
    CHECK(s.erase_run(0) == 0);
    CHECK(s.run_left(0) == 0);
    CHECK(s.bytes() == 4 * M);
    CHECK(s.run_of(base + 16 * M) == 1); // run 1 keeps its index (its canary slice)
    // a later run never takes a chunk that is already skipped
    CHECK(s.add_run(base + 16 * M, 4 * M) == 2);
    CHECK(s.bytes() == 4 * M);
    CHECK(s.run_of(base + 16 * M) == 1);
    s.clear();
    CHECK(s.empty());
    CHECK(s.bytes() == 0);
}

} // namespace
