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
// The same nine dwords are what Sony's libSceAgc dispatches for buffer fills on the console
// (experiment 0013: 1,503 dispatches of ASTRO BOT's most-used compute program).
inline constexpr std::array<std::uint32_t, 9> kBufferClearCsGfx10 = {
    0xD7460004u, 0x04010C08u, 0x7E000204u, 0x7E020205u, 0x7E040206u,
    0x7E060207u, 0xE01C2000u, 0x80000004u, 0xBF810000u,
};

// Each thread stores one 16-byte record; each group has 64 threads.
inline constexpr std::uint32_t kBytesPerThread = 16;
inline constexpr std::uint32_t kThreadsPerGroup = 64;
inline constexpr std::uint32_t kBytesPerGroup = kBytesPerThread * kThreadsPerGroup;

// Values IGT uses (amd_dispatch_helpers.c:103-185, amd_dispatch.c:142-167).
inline constexpr std::uint32_t kIgtRsrc1 = 0x000C0041u;
inline constexpr std::uint32_t kIgtRsrc2 = 0x00000090u; // 8 user SGPRs, TGID_X enabled
inline constexpr std::uint32_t kIgtVsharpWord3 = 0x1104bfacu;

// Values Sony's libSceAgc uses for the same program on the console (experiment 0013,
// dispatch records): RSRC1 additionally sets bit 30 (WGP_MODE on gfx10) and bits 21-23;
// V# word 3 has RESOURCE_LEVEL (bit 24) and bit 28 clear.
inline constexpr std::uint32_t kConsoleRsrc1 = 0x402C0041u;
inline constexpr std::uint32_t kConsoleRsrc2 = 0x00000090u;
inline constexpr std::uint32_t kConsoleVsharpWord3 = 0x0004bfacu;

struct MemsetParams {
    std::uint64_t shader_va = 0;  // GPU VA of the shader, 256-byte aligned
    std::uint64_t dst_va = 0;     // GPU VA of the destination buffer
    std::uint32_t dst_bytes = 16384; // multiple of kBytesPerGroup
    std::uint32_t value = 0x22222222u;
    bool gfx_ring = true;         // emit CONTEXT_CONTROL (GFX ring); HANDOFF F6
    std::uint32_t rsrc1 = kIgtRsrc1;
    std::uint32_t rsrc2 = kIgtRsrc2;
    std::uint32_t vsharp_word3 = kIgtVsharpWord3;
    // COMPUTE_STATIC_THREAD_MGMT_SE0..3 (IGT writes all ones). Experiment 0019 probes which
    // bits carry execution units on the BC-250.
    std::uint32_t cu_mask = 0xffffffffu;
};

// Builds the complete IB (padded to 8 dwords). Throws std::invalid_argument on
// misaligned addresses or sizes.
std::vector<std::uint32_t> build_memset_ib(const MemsetParams &params);

} // namespace bc5::dispatch_min
