// SPDX-License-Identifier: GPL-2.0-only
// BC5's own fill shader for libSceAgc's CbMemsetExclusive export (nid_6nths4DHNrs): the shader
// header we build in C++ and the machine code of src/reimpl/shaders/fill16.s. Written from the
// export's interface (clean-room, src/reimpl/PROVENANCE.md); it replaces internal shader 0 of the
// original module. Until the code is assembled on the box the code is empty and the fill shader
// stays absent, as without module files before.
#pragma once

#include <cstddef>
#include <cstdint>
#include <span>

namespace bc5::reimpl::agc::fill_shader {

// The interface agcCbFillMemory sets up (agc_cb.cpp).
inline constexpr std::uint32_t kUserDataCount = 9;     // s[0:3] V#, s[4:7] pattern, s8 blocks
inline constexpr std::uint32_t kUserDataStartSlot = 0; // COMPUTE_USER_DATA_0
inline constexpr std::uint32_t kThreadsPerGroup = 256; // 16 groups x 256 x 16 B = 64 KiB
inline constexpr std::uint32_t kVgprCount = 6;         // v0..v5
inline constexpr std::uint32_t kSgprCount = 12;        // s0..s11

// Machine code of shaders/fill16.s (gfx10, wave64). Empty until assembled.
std::span<const std::uint32_t> code();

// Size of the header blob build_header() writes.
std::size_t header_bytes();

// Writes the header blob into `dst` (header_bytes() bytes, 8-byte aligned): the Shader object
// (stage 0, compute) followed by its SH registers, the sub-block with the user-data layout and
// the info block. Pointers are self-relative offsets, as sceAgcCreateShader expects.
void build_header(std::uint8_t *dst, std::uint32_t code_bytes);

} // namespace bc5::reimpl::agc::fill_shader
