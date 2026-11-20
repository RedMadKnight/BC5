// SPDX-License-Identifier: GPL-2.0-only
// FwImage on synthetic containers built here (no console data): plain ELF and SELF, round trip,
// zero-filled bss, refusal of compressed entries, and every truncation of a valid file.
#include <catch2/catch_test_macros.hpp>

#include "bc5/reimpl/fw_image.hpp"

#include <cstdint>
#include <cstring>
#include <vector>

using bc5::reimpl::FwImage;

namespace {

template <typename T> void put(std::vector<std::uint8_t> &b, std::size_t off, T v) {
    if (b.size() < off + sizeof(T)) {
        b.resize(off + sizeof(T));
    }
    std::memcpy(b.data() + off, &v, sizeof(T));
}

struct Seg {
    std::uint64_t vaddr;
    std::vector<std::uint8_t> bytes;
    std::uint64_t memsz;
};

// ELF64 header + program headers at `base` in `out`; segment data at the given file offsets.
void write_elf(std::vector<std::uint8_t> &out, std::size_t base, const std::vector<Seg> &segs,
               const std::vector<std::uint64_t> &data_offsets) {
    put<std::uint32_t>(out, base, 0x464c457fu);
    put<std::uint64_t>(out, base + 0x20, 0x40);                                // phoff
    put<std::uint16_t>(out, base + 0x36, 0x38);                                // phentsize
    put<std::uint16_t>(out, base + 0x38, static_cast<std::uint16_t>(segs.size())); // phnum
    for (std::size_t i = 0; i < segs.size(); ++i) {
        const std::size_t p = base + 0x40 + 0x38 * i;
        put<std::uint32_t>(out, p, 1); // PT_LOAD
        put<std::uint64_t>(out, p + 8, data_offsets[i]);
        put<std::uint64_t>(out, p + 16, segs[i].vaddr);
        put<std::uint64_t>(out, p + 32, segs[i].bytes.size());
        put<std::uint64_t>(out, p + 40, segs[i].memsz);
    }
}

std::vector<Seg> sample_segments() {
    std::vector<std::uint8_t> a(0x30), b(0x10);
    for (std::size_t i = 0; i < a.size(); ++i) {
        a[i] = static_cast<std::uint8_t>(i + 1);
    }
    for (std::size_t i = 0; i < b.size(); ++i) {
        b[i] = static_cast<std::uint8_t>(0xa0 + i);
    }
    return {{0x0, a, 0x30}, {0x4000, b, 0x40}};
}

std::vector<std::uint8_t> make_elf() {
    auto segs = sample_segments();
    std::vector<std::uint8_t> out;
    const std::vector<std::uint64_t> offs{0x200, 0x300};
    write_elf(out, 0, segs, offs);
    for (std::size_t i = 0; i < segs.size(); ++i) {
        out.resize(std::max<std::size_t>(out.size(), offs[i] + segs[i].bytes.size()));
        std::memcpy(out.data() + offs[i], segs[i].bytes.data(), segs[i].bytes.size());
    }
    return out;
}

std::vector<std::uint8_t> make_self(std::uint64_t extra_props = 0) {
    auto segs = sample_segments();
    std::vector<std::uint8_t> out;
    const std::uint16_t n = 2;
    put<std::uint32_t>(out, 0, 0xeef51454u); // bytes 54 14 f5 ee
    put<std::uint16_t>(out, 0x18, n);
    const std::size_t ehdr = 0x20 + 0x20 * n;
    // ELF offsets inside a SELF are not used for the data; the entries carry it.
    write_elf(out, ehdr, segs, {0, 0});
    const std::vector<std::uint64_t> data{0x400, 0x500};
    for (std::uint16_t i = 0; i < n; ++i) {
        const std::size_t e = 0x20 + 0x20u * i;
        put<std::uint64_t>(out, e, 0x800u | (std::uint64_t{i} << 20) | extra_props);
        put<std::uint64_t>(out, e + 8, data[i]);
        put<std::uint64_t>(out, e + 16, segs[i].bytes.size());
        put<std::uint64_t>(out, e + 24, segs[i].bytes.size());
        out.resize(std::max<std::size_t>(out.size(), data[i] + segs[i].bytes.size()));
        std::memcpy(out.data() + data[i], segs[i].bytes.data(), segs[i].bytes.size());
    }
    return out;
}

void check_image(const FwImage &img) {
    REQUIRE(img.image_size() == 0x4040);
    const auto *a = img.at(0, 0x30);
    REQUIRE(a != nullptr);
    CHECK(a[0] == 1);
    CHECK(a[0x2f] == 0x30);
    const auto *b = img.at(0x4000, 0x40);
    REQUIRE(b != nullptr);
    CHECK(b[0] == 0xa0);
    CHECK(b[0xf] == 0xaf);
    CHECK(b[0x10] == 0); // memsz > filesz: zero-filled
    CHECK(b[0x3f] == 0);
    CHECK(img.at(0x30, 0x10) != nullptr); // gap between segments reads as zeros
    CHECK(img.at(0x4040, 1) == nullptr);
    CHECK(img.at(0x403f, 2) == nullptr);
    CHECK(img.at(~0ull, 1) == nullptr);
}

} // namespace

TEST_CASE("FwImage loads a synthetic plain ELF", "[reimpl][fw_image]") {
    FwImage img;
    REQUIRE(img.parse(make_elf()));
    check_image(img);
}

TEST_CASE("FwImage loads a synthetic SELF through its entries", "[reimpl][fw_image]") {
    FwImage img;
    REQUIRE(img.parse(make_self()));
    check_image(img);
}

TEST_CASE("FwImage refuses compressed or encrypted SELF entries", "[reimpl][fw_image]") {
    FwImage img;
    REQUIRE_FALSE(img.parse(make_self(0x8)));
    CHECK_FALSE(img.error().empty());
    CHECK(img.at(0, 1) == nullptr);
}

TEST_CASE("FwImage fails cleanly on every truncation", "[reimpl][fw_image]") {
    for (const auto &whole : {make_elf(), make_self()}) {
        for (std::size_t n = 0; n < whole.size(); ++n) {
            std::vector<std::uint8_t> cut(whole.begin(),
                                          whole.begin() + static_cast<std::ptrdiff_t>(n));
            FwImage img;
            CHECK_FALSE(img.parse(cut));
        }
    }
}

TEST_CASE("FwImage refuses an absurd segment size", "[reimpl][fw_image]") {
    auto elf = make_elf();
    put<std::uint64_t>(elf, 0x40 + 40, 1ull << 40); // memsz of the first PT_LOAD
    FwImage img;
    CHECK_FALSE(img.parse(elf));
}
