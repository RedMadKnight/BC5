// SPDX-License-Identifier: GPL-2.0-only
// The phase-2 "memset" dispatch (ADR 0004): a gfx10 compute shader that
// fills a buffer with a 32-bit value, and the PM4 indirect buffer that runs it.
#pragma once

#include <array>
#include <cstdint>
#include <vector>

namespace bc5::dispatch_min {

// Buffer-clear compute shader for gfx10, 9 dwords of RDNA ISA. Taken verbatim from
// IGT lib/amdgpu/amd_shaders.c:295-309 (igt-gpu-tools @ 9d4b6ef), which is
// SPDX-License-Identifier: MIT, Copyright 2014, 2022 Advanced Micro Devices, Inc.
// Disassembly (from the same file):
//   v_lshl_add_u32 v4, s8, 6, v0          ; global index = tgid.x * 64 + tid
//   v_mov_b32 v0..v3, s4..s7              ; the clear value (user data 4..7)
//   buffer_store_format_xyzw v[0:3], v4, s[0:3], 0 idxen   ; V# in user data 0..3
//   s_endpgm
inline constexpr std::array<std::uint32_t, 9> kBufferClearCsGfx10 = {
    0xD7460004u, 0x04010C08u, 0x7E000204u, 0x7E020205u, 0x7E040206u,
    0x7E060207u, 0xE01C2000u, 0x80000004u, 0xBF810000u,
};

// Each thread stores one 16-byte record; each group has 64 threads.
inline constexpr std::uint32_t kBytesPerThread = 16;
inline constexpr std::uint32_t kThreadsPerGroup = 64;
inline constexpr std::uint32_t kBytesPerGroup = kBytesPerThread * kThreadsPerGroup;

struct MemsetParams {
    std::uint64_t shader_va = 0;  // GPU VA of the shader, 256-byte aligned
    std::uint64_t dst_va = 0;     // GPU VA of the destination buffer
    std::uint32_t dst_bytes = 16384; // multiple of kBytesPerGroup
    std::uint32_t value = 0x22222222u;
    bool gfx_ring = true;         // emit CONTEXT_CONTROL (GFX ring); HANDOFF F6
};

// Builds the complete IB (padded to 8 dwords). Throws std::invalid_argument on
// misaligned addresses or sizes.
std::vector<std::uint32_t> build_memset_ib(const MemsetParams &params);

} // namespace bc5::dispatch_min
