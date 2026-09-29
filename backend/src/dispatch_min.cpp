// SPDX-License-Identifier: GPL-2.0-only
// Packet sequence reproduced from IGT (igt-gpu-tools @ 9d4b6ef, MIT):
//   lib/amdgpu/compute_utils/amd_dispatch_helpers.c:16-185 (version == 10)
//   lib/amdgpu/compute_utils/amd_dispatch.c:142-181 (memset user data and dispatch)
// Deviations are listed in docs/decisions/0004-dispatch-min.md.
#include "bc5/dispatch_min.hpp"

#include "bc5/pm4.hpp"

#include <stdexcept>

namespace bc5::dispatch_min {

namespace {
using pm4::Op;

std::uint32_t lo32(std::uint64_t v) { return static_cast<std::uint32_t>(v & 0xffffffffu); }
std::uint32_t hi32(std::uint64_t v) { return static_cast<std::uint32_t>(v >> 32); }
} // namespace

std::vector<std::uint32_t> build_memset_ib(const MemsetParams &p) {
    if (p.shader_va % 256 != 0) {
        throw std::invalid_argument("shader VA must be 256-byte aligned (COMPUTE_PGM_LO is VA >> 8)");
    }
    if (p.dst_va % 16 != 0) {
        throw std::invalid_argument("destination VA must be 16-byte aligned");
    }
    if (p.dst_bytes == 0 || p.dst_bytes % kBytesPerGroup != 0) {
        throw std::invalid_argument("destination size must be a positive multiple of 1024 bytes");
    }

    pm4::Builder b;

    // amdgpu_dispatch_init (helpers.c:16-72)
    if (p.gfx_ring) {
        b.packet(Op::ContextControl, {0x80000000u, 0x80000000u});
    }
    b.set_sh_reg(0x204, {0, 0, 0}); // COMPUTE_START_X/Y/Z
    b.set_sh_reg(0x218, {0});       // COMPUTE_TMPRING_SIZE
    b.set_sh_reg(0x22a, {0});       // COMPUTE_SHADER_CHKSUM
    // COMPUTE_REQ_CTRL and the five following registers, written with 0x222 as
    // IGT does (helpers.c:45-52). TODO(verify): the values look accidental in IGT;
    // kept verbatim because that sequence is exercised on real gfx10 hardware.
    b.set_sh_reg(0x222, {0x222, 0x222, 0x222, 0x222, 0x222, 0x222});
    b.packet(Op::SetUconfigReg, {0x7b, 0x20}); // CP_COHER_START_DELAY = 0x20

    // amdgpu_dispatch_write_cumask (helpers.c:75-100): all CUs of every SE.
    b.packet(Op::SetShRegIndex, {0x30000216u, 0xffffffffu, 0xffffffffu}, true); // SE0, SE1
    b.packet(Op::SetShRegIndex, {0x219u, 0xffffffffu, 0xffffffffu}, true);      // SE2, SE3

    // amdgpu_dispatch_write2hw (helpers.c:103-185)
    b.set_sh_reg(0x20c, {lo32(p.shader_va >> 8), lo32(p.shader_va >> 40)}); // COMPUTE_PGM_LO/HI
    b.set_sh_reg(0x2e12 - pm4::kShRegBase, {0x000C0041u}); // COMPUTE_PGM_RSRC1
    b.set_sh_reg(0x2e13 - pm4::kShRegBase, {0x00000090u}); // COMPUTE_PGM_RSRC2: 8 user SGPRs, TGID_X
    b.set_sh_reg(0x2e07 - pm4::kShRegBase, {kThreadsPerGroup}); // COMPUTE_NUM_THREAD_X
    b.set_sh_reg(0x2e08 - pm4::kShRegBase, {1});                // COMPUTE_NUM_THREAD_Y
    b.set_sh_reg(0x2e09 - pm4::kShRegBase, {1});                // COMPUTE_NUM_THREAD_Z
    b.set_sh_reg(0x228, {0});                                   // COMPUTE_PGM_RSRC3

    // User data (dispatch.c:142-167): V# of the destination, then the value.
    const std::uint32_t records = p.dst_bytes / kBytesPerThread;
    b.set_sh_reg(0x240, {lo32(p.dst_va), hi32(p.dst_va) | 0x100000u /* stride 16 */, records,
                         0x1104bfacu /* gfx10 word 3 */});
    b.set_sh_reg(0x244, {p.value, p.value, p.value, p.value});
    b.set_sh_reg(0x215, {0}); // COMPUTE_RESOURCE_LIMITS

    // DISPATCH_DIRECT (dispatch.c:174-179), one group per 1 KiB (ADR 0004 deviation).
    const std::uint32_t groups = p.dst_bytes / kBytesPerGroup;
    b.packet(Op::DispatchDirect, {0x10u, groups, 1u, 1u}, true);

    b.pad_to_multiple(8); // emit_aligned(7, GFX_COMPUTE_NOP)
    return b.dwords();
}

} // namespace bc5::dispatch_min
