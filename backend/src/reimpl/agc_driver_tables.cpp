// SPDX-License-Identifier: GPL-2.0-only
// Own-source data of the libSceAgcDriver re-creation (see
// include/bc5/reimpl/agc_driver_tables.hpp).
//
// The default context state (the description's DRV-CS-1..8) is AMD's public gfx10 clear state:
// amd/clearstate_gfx10.h, copied unchanged from the Linux kernel (MIT, provenance in
// amd/README.md). Its gfx10_SECT_CONTEXT_defs[] ranges are the eight ranges of the description,
// with the same first registers and counts; the file is included below inside a namespace of
// this .cpp only, with the kernel's two small type definitions it needs written here.
#include "bc5/reimpl/agc_driver_tables.hpp"

#include <array>

namespace bc5::reimpl::agc_driver::tables {

namespace amd_clearstate {
// Declarations the kernel's clearstate_defs.h provides to the file (Linux
// drivers/gpu/drm/amd/include/clearstate_defs.h, MIT): an extent is {values, first register,
// count}; a section groups extents. Only the context section is used here.
enum section_id { SECT_NONE, SECT_CONTEXT, SECT_CLEAR, SECT_CTRLCONST };
struct cs_extent_def {
    const unsigned int *extent;
    const unsigned int reg_index;
    const unsigned int reg_count;
};
struct cs_section_def {
    const struct cs_extent_def *section;
    const enum section_id id;
};

#if defined(__clang__)
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wunused-const-variable"
#pragma clang diagnostic ignored "-Wunused-variable"
#elif defined(__GNUC__)
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-variable"
#elif defined(_MSC_VER)
#pragma warning(push)
#pragma warning(disable : 4189)
#endif
#include "amd/clearstate_gfx10.h"
#if defined(__clang__)
#pragma clang diagnostic pop
#elif defined(__GNUC__)
#pragma GCC diagnostic pop
#elif defined(_MSC_VER)
#pragma warning(pop)
#endif
} // namespace amd_clearstate

namespace {

using u32 = std::uint32_t;

constexpr u32 kContextBase = 0xA000; // absolute dword of context register 0

// The image addresses where the original module keeps each range's values (interoperability
// facts of the description), only used to read the module file behind BC5_REIMPL_FW_DATA.
constexpr std::uint64_t kImageAddress[kDefaultRangeCount] = {0x10520, 0x10B20, 0x10880, 0x10890,
                                                             0x10B08, 0x10B10, 0x10F60, 0x11070};

std::array<DefaultRange, kDefaultRangeCount> build_ranges() {
    std::array<DefaultRange, kDefaultRangeCount> r{};
    for (std::size_t i = 0; i < r.size(); ++i) {
        const auto &e = amd_clearstate::gfx10_SECT_CONTEXT_defs[i];
        r[i] = {e.reg_index, e.reg_count, kImageAddress[i]};
    }
    return r;
}

std::array<u32, 0x400> build_defaults() {
    std::array<u32, 0x400> v{};
    for (const auto *e = amd_clearstate::gfx10_SECT_CONTEXT_defs; e->extent != nullptr; ++e) {
        for (u32 i = 0; i < e->reg_count; ++i) {
            v[e->reg_index - kContextBase + i] = e->extent[i];
        }
    }
    return v;
}

// ---- trap handler
// ---------------------------------------------------------------------------------
//
// The original module hands the kernel a 0x2400-byte GPU trap handler (ioctl 0x80888123, see
// install_trap_handler in agc_driver_core.cpp). We send the same ioctl with our own minimal
// handler instead: one instruction that ends the trapped wave.
//
//     s_endpgm
//
// Encoding (RDNA SOPP): bits 31..23 = 0x17F, opcode in bits 22..16, simm16 in bits 15..0;
// s_endpgm is SOPP opcode 1 with simm16 0, so the dword is 0xBF810000.
// Checked 2026-11-20 with Ubuntu LLVM 21.1.8 llvm-mc (gfx1013, wave64): s_endpgm encodes as 0xBF810000.
//
// On BC5 the host only traces this ioctl and never runs the handler on the GPU, so the bytes
// are never executed; they only have to be a well-formed handler of the size the ioctl reports.
// The ioctl therefore reports 0x100 bytes (this one dword, rounded up to 256) where the original
// reports 0x2400; a compare with a capture of the title's own module (run rmplF1bb, 2026-11-21)
// shows that as the only difference in that ioctl, and it is kept: BC5's /dev/gc only traces it.
constexpr u32 kSoppFixedBits = 0x17Fu << 23;
constexpr u32 kSoppOpEndpgm = 1;
constexpr u32 kTrapHandlerDword = kSoppFixedBits | (kSoppOpEndpgm << 16);
static_assert(kTrapHandlerDword == 0xBF810000u);

constexpr std::array<std::uint8_t, 4> kTrapHandler = {
    static_cast<std::uint8_t>(kTrapHandlerDword), static_cast<std::uint8_t>(kTrapHandlerDword >> 8),
    static_cast<std::uint8_t>(kTrapHandlerDword >> 16),
    static_cast<std::uint8_t>(kTrapHandlerDword >> 24)};

} // namespace

std::span<const DefaultRange> default_ranges() {
    static const std::array<DefaultRange, kDefaultRangeCount> ranges = build_ranges();
    return ranges;
}

std::span<const std::uint32_t> default_context_values() {
    static const std::array<u32, 0x400> values = build_defaults();
    return values;
}

std::span<const std::uint32_t> default_range_values(const DefaultRange &r) {
    const std::uint32_t index = r.first - kContextBase;
    if (r.first < kContextBase || index + r.count > 0x400u) {
        return {};
    }
    return default_context_values().subspan(index, r.count);
}

std::span<const std::uint8_t> trap_handler_code() { return kTrapHandler; }

} // namespace bc5::reimpl::agc_driver::tables
