// SPDX-License-Identifier: GPL-2.0-only
// Own-source data of the libSceAgcDriver re-creation: the driver's default context state (the
// "clear state" image, eight ranges of consecutive context registers; AMD's public gfx10 clear
// state, src/reimpl/amd/clearstate_gfx10.h, MIT) and our own GPU trap handler. They replace the
// reads of the original module file, which stay available behind BC5_REIMPL_FW_DATA=1.
#pragma once

#include <cstdint>
#include <span>

namespace bc5::reimpl::agc_driver::tables {

// One range of the default context state: `count` consecutive context registers starting at the
// absolute register dword `first` (context base 0xA000 included).
struct DefaultRange {
    std::uint32_t first;
    std::uint32_t count;
    std::uint64_t image_address; // where the original module stores the values (FW_DATA only)
};
inline constexpr int kDefaultRangeCount = 8;
std::span<const DefaultRange> default_ranges();

// The default value of every context register 0..0x3FF (relative offset); registers outside the
// eight ranges are zero.
std::span<const std::uint32_t> default_context_values();

// The own values of one range (a view into default_context_values()).
std::span<const std::uint32_t> default_range_values(const DefaultRange &range);

// Our own GPU trap handler (replaces the 0x2400-byte handler the original module embeds at image
// address 0x1C000). See agc_driver_tables.cpp.
std::span<const std::uint8_t> trap_handler_code();
inline constexpr std::uint64_t kTrapHandlerImageAddress = 0x1C000;
inline constexpr std::uint64_t kTrapHandlerImageSize = 0x2400;

} // namespace bc5::reimpl::agc_driver::tables
