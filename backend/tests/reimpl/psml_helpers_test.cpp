// SPDX-License-Identifier: GPL-2.0-only
// libScePsml re-creation: pure helpers (LZ4 block decoder, tile tables, depth parameters, half
// floats, version map) and the export/import tables. Synthetic data only.
#include <catch2/catch_test_macros.hpp>

#include "bc5/reimpl/psml_internal.hpp"

#include <cmath>
#include <cstring>
#include <set>
#include <string>
#include <utility>
#include <vector>

using namespace bc5::reimpl;
using namespace bc5::reimpl::psml;

namespace {
std::vector<std::uint8_t> bytes(std::initializer_list<int> v) {
    std::vector<std::uint8_t> out;
    for (int b : v) {
        out.push_back(static_cast<std::uint8_t>(b));
    }
    return out;
}
std::int32_t decode(const std::vector<std::uint8_t> &src, std::vector<std::uint8_t> &dst) {
    return lz4_decompress(src.data(), dst.data(), static_cast<std::int32_t>(src.size()),
                          static_cast<std::int32_t>(dst.size()));
}
} // namespace

TEST_CASE("lz4: literal-only, match, overlap and long-length blocks", "[psml]") {
    std::vector<std::uint8_t> out(64, 0xcc);
    // 5 literals.
    REQUIRE(decode(bytes({0x50, 'h', 'e', 'l', 'l', 'o'}), out) == 5);
    REQUIRE(std::string(out.begin(), out.begin() + 5) == "hello");
    // 3 literals, match offset 3 length 9, then a final sequence of one literal.
    REQUIRE(decode(bytes({0x35, 'a', 'b', 'c', 3, 0, 0x10, '!'}), out) == 13);
    REQUIRE(std::string(out.begin(), out.begin() + 13) == "abcabcabcabc!");
    // Overlapping copy: 1 literal, offset 1, length 15 + 0 + 4 = 19; then an empty last sequence.
    REQUIRE(decode(bytes({0x1f, 'x', 1, 0, 0, 0x00}), out) == 20);
    REQUIRE(std::string(out.begin(), out.begin() + 20) == std::string(20, 'x'));
    // 20 literals through the length extension (15 + 5).
    std::vector<std::uint8_t> lit = {0xf0, 5};
    for (int i = 0; i < 20; ++i) {
        lit.push_back(static_cast<std::uint8_t>('A' + i));
    }
    REQUIRE(decode(lit, out) == 20);
    REQUIRE(out[19] == 'A' + 19);
}

TEST_CASE("lz4: malformed input and capacity rules", "[psml]") {
    std::vector<std::uint8_t> out(8);
    REQUIRE(decode(bytes({0x35, 'a', 'b', 'c', 0, 0, 0x10, '!'}), out) < 0); // offset 0
    REQUIRE(decode(bytes({0x15, 'a', 9, 0, 0x10, '!'}), out) < 0);           // offset too far
    REQUIRE(decode(bytes({0x50, 'h', 'e'}), out) < 0);                       // truncated
    REQUIRE(decode(bytes({0x35, 'a', 'b', 'c', 3, 0, 0x10, '!'}), out) < 0); // dst too small
    std::uint8_t z = 0;
    REQUIRE(lz4_decompress(&z, out.data(), 1, 0) == 0); // zero capacity: only {0x00} succeeds
    std::uint8_t one = 0x10;
    REQUIRE(lz4_decompress(&one, out.data(), 1, 0) < 0);
    REQUIRE(lz4_decompress(nullptr, out.data(), 1, 8) < 0);
}

TEST_CASE("tile tables: argument checks", "[psml]") {
    std::uint32_t t[30];
    REQUIRE(tile_table_a(t, 236, 4) == -1);
    REQUIRE(tile_table_a(t, 242, 4) == -1);
    REQUIRE(tile_table_a(t, 3844, 4) == -1);
    REQUIRE(tile_table_a(t, 240, 6) == -2);
    REQUIRE(tile_table_a(t, 240, 0) == -2);
    REQUIRE(tile_table_b(t, 236, 2) == -1);
    REQUIRE(tile_table_b(t, 1928, 2) == -1);
    REQUIRE(tile_table_b(t, 240, 3) == -2);
    REQUIRE(tile_table_c(t, 112, 2) == -1);
    REQUIRE(tile_table_c(t, 120, 1082) == -2);
}

TEST_CASE("tile tables: hand-computed smallest cases (Appendix B)", "[psml]") {
    std::uint32_t t[30];
    // A(240, 4): wr 240, pad 0, col 0, H4 8, R 24; one entry start -20, rows 24, c 0.
    REQUIRE(tile_table_a(t, 240, 4) == 0);
    REQUIRE(t[0] == 0x07d07500u);
    for (int i = 1; i < 30; ++i) {
        REQUIRE(t[i] == 0xffffffffu);
    }
    // B(240, 2): pad 16, col 0, H4 6, R 6; start -4, rows 6, c -16.
    REQUIRE(tile_table_b(t, 240, 2) == 0);
    REQUIRE(t[0] == 0x07807d01u);
    REQUIRE(t[1] == 0xffffffffu);
    // C(120, 2): pad 0, col 0, R 4; start -2, rows 4, c 0.
    REQUIRE(tile_table_c(t, 120, 2) == 0);
    REQUIRE(t[0] == 0x08007e00u);
    REQUIRE(t[1] == 0xffffffffu);
}

TEST_CASE("tile tables: realistic sizes fit in 30 entries", "[psml]") {
    for (auto [w, h] : {std::pair{1920, 1080}, std::pair{960, 540}, std::pair{480, 270}}) {
        std::uint32_t a[30];
        std::uint32_t b[30];
        std::uint32_t c[30];
        REQUIRE(tile_table_a(a, w, h - (h % 4)) == 0);
        REQUIRE(tile_table_b(b, w / 2 - ((w / 2) % 8), (h / 2) & ~1) == 0);
        REQUIRE(tile_table_c(c, w / 2 - ((w / 2) % 8), (h / 2) & ~1) == 0);
        // Entries carry the fixed tags in their high bits; an idle tail, if any, is contiguous.
        REQUIRE(a[0] != 0xffffffffu);
        bool idle = false;
        for (std::uint32_t e : a) {
            if (e == 0xffffffffu) {
                idle = true;
            } else {
                REQUIRE(!idle);
            }
        }
        REQUIRE(b[0] != 0xffffffffu);
        REQUIRE(c[0] != 0xffffffffu);
        // Deterministic.
        std::uint32_t a2[30];
        REQUIRE(tile_table_a(a2, w, h - (h % 4)) == 0);
        REQUIRE(std::memcmp(a, a2, sizeof a) == 0);
    }
}

TEST_CASE("depth parameters (mode 1)", "[psml]") {
    float p[4];
    depth_params(p, 1.0f, 3.0f, false);
    REQUIRE(p[0] == 0.0f);
    REQUIRE(p[1] == -1.5f);
    REQUIRE(p[2] == 1.0f);
    REQUIRE(p[3] == -1.5f);
    depth_params(p, 1.0f, INFINITY, false);
    REQUIRE(p[1] == -1.0f);
    REQUIRE(p[3] == -1.0f);
    depth_params(p, 1.0f, 3.0f, true);
    REQUIRE(p[1] == 1.5f);
    REQUIRE(p[3] == 0.5f);
    depth_params(p, 2.0f, INFINITY, true);
    REQUIRE(p[1] == 2.0f);
    REQUIRE(p[3] == 0.0f);
    REQUIRE(std::signbit(p[3]));
}

TEST_CASE("half floats round to nearest", "[psml]") {
    REQUIRE(float_to_half(1.0f) == 0x3c00);
    REQUIRE(float_to_half(0.25f) == 0x3400);
    REQUIRE(float_to_half(-2.0f) == 0xc000);
    REQUIRE(float_to_half(65504.0f) == 0x7bff);
    REQUIRE(float_to_half(1e6f) == 0x7c00);
    REQUIRE(float_to_half(0.0f) == 0);
    REQUIRE(float_to_half(1.0f + 1.0f / 2048.0f) == 0x3c00); // tie to even
    REQUIRE(detail::half_to_float(0x3c00) == 1.0f);
    REQUIRE(detail::half_to_float(0x0001) == std::ldexp(1.0f, -24));
}

TEST_CASE("mfsrVersion map and SDK defaults (INTEROP TABLE)", "[psml]") {
    REQUIRE(version_index("09.40", 0) == 0);
    REQUIRE(version_index("09.00", 0) == 1);
    REQUIRE(version_index("09.60", 0) == 2);
    REQUIRE(version_index("10.20", 0) == 3);
    REQUIRE(version_index("11.00", 0) == 4);
    REQUIRE(version_index("11.60", 0) == 5);
    REQUIRE(version_index("12.00", 0x10000000) == err::kProfileMismatch);
    REQUIRE(version_index(nullptr, 0x05000000) == 0);
    REQUIRE(version_index("", 0x10123456) == 2);
    REQUIRE(version_index(nullptr, 0x11000000) == 3);
    REQUIRE(version_index(nullptr, 0xfeffffff) == 3);
    REQUIRE(version_index(nullptr, 0x00ffffff) == err::kProfileMismatch);
    REQUIRE(version_index(nullptr, 0xff000000) == err::kProfileMismatch);
}

TEST_CASE("export table: 41 unique NID+library entries, none null", "[psml]") {
    const auto ex = psml::exports();
    REQUIRE(ex.size() == 41);
    std::set<std::pair<std::string, std::string>> seen;
    int per_lib_main = 0;
    int per_lib_mfsr2 = 0;
    int per_lib_nosub = 0;
    for (const ExportEntry &e : ex) {
        REQUIRE(e.nid != nullptr);
        REQUIRE(std::strlen(e.nid) == 11);
        REQUIRE(e.address != nullptr);
        REQUIRE(!e.is_object);
        REQUIRE(seen.insert({e.nid, e.library}).second);
        const std::string lib = e.library;
        per_lib_main += lib == "libScePsml" ? 1 : 0;
        per_lib_mfsr2 += lib == "libScePsml_mfsr2" ? 1 : 0;
        per_lib_nosub += lib == "libScePsml_nosubmission" ? 1 : 0;
    }
    REQUIRE(per_lib_main == 25);
    REQUIRE(per_lib_mfsr2 == 9);
    REQUIRE(per_lib_nosub == 3);
    REQUIRE(seen.count({"3E85qTivV78", "libScePsml_set_mfsrversion"}) == 1);
    REQUIRE(seen.count({"xNZM9Y5lf-M", "libScePsml_specularAA"}) == 1);
    REQUIRE(seen.count({"lcZD9tJraAw", "libScePsml_quality8K"}) == 1);
    REQUIRE(seen.count({"TupVXn-8vU4", "libScePsml_lightweight"}) == 1);
}

TEST_CASE("import table: unique NIDs, every slot addressable", "[psml]") {
    const auto im = psml::imports();
    REQUIRE(im.size() >= 40);
    std::set<std::string> nids;
    for (const ImportSlot &s : im) {
        REQUIRE(s.slot != nullptr);
        REQUIRE(std::strlen(s.nid) == 11);
        REQUIRE(nids.insert(s.nid).second);
    }
    REQUIRE(nids.count("f3dg2CSgRKY") == 1); // sceAgcCreateShader
    REQUIRE(nids.count("tU5e3f9gSiU") == 1); // the Trinity query
    REQUIRE(nids.count("zARR5aCmkoY") == 1);
    REQUIRE(nids.count("mQfUoU5-d1g") == 1);
}
