// SPDX-License-Identifier: GPL-2.0-only
// BC5's own fill shader for CbMemsetExclusive (see include/bc5/reimpl/agc_fill_shader.hpp and
// src/reimpl/shaders/fill16.s).
//
// The header layout is the Shader object of agc.hpp (from the clean-room description of
// sceAgcCreateShader and agcCbFillMemory); the blob around it is our own arrangement. Register
// names and fields: Mesa's gfx10 register database (tools/bc5-agc/regdb/gfx10.json, MIT) through
// agc_regdb.hpp; the RSRC1 VGPR granularity (4 per block in wave64) and the absent SGPR count on
// gfx10 follow Mesa src/amd/vulkan/radv_shader.c @ ab2374a (config->rsrc1).
#include "bc5/reimpl/agc_fill_shader.hpp"

#include "bc5/reimpl/agc.hpp"
#include "bc5/reimpl/agc_regdb.hpp"

#include <cstring>

namespace bc5::reimpl::agc::fill_shader {

namespace {

using namespace bc5::reimpl::regdb;
using u32 = std::uint32_t;

// TODO(assemble-on-box): the dwords of shaders/fill16.s, assembled for gfx1013 wave64. Until then
// the array stays empty and create_internal_shaders() leaves the fill shader absent.
constexpr std::span<const u32> kFillShaderCode{};

// Blob layout (offsets in bytes from the start of the header).
constexpr std::size_t kShRegsAt = sizeof(Shader); // 0x60
constexpr std::size_t kShRegCount = 8;
constexpr std::size_t kExtraAt = kShRegsAt + 8 * kShRegCount; // 0xA0: 5 qwords + counts
constexpr std::size_t kExtraBytes = 0x30;
constexpr std::size_t kSlotAt = kExtraAt + kExtraBytes; // 0xD0: user-data slot record
constexpr std::size_t kSlotBytes = 8;
constexpr std::size_t kInfoAt = kSlotAt + kSlotBytes; // 0xD8: info block
constexpr std::size_t kInfoBytes = 0x30;
constexpr std::size_t kBlobBytes = kInfoAt + kInfoBytes; // 0x108

// Offsets inside the blocks that the module reads (agcCbFillMemory, sceAgcCreateShader).
constexpr std::size_t kExtraUserDataCount = 0x2A; // u16
constexpr std::size_t kSlotStart = 0x02;          // u16
constexpr std::size_t kInfoInitiator = 0x10;      // u32, masked with 0xA038 at dispatch

constexpr u32 kShaderMagic = 0x34333231u; // "1234"
constexpr u32 kShaderVersion = 0x18u;
constexpr std::uint8_t kStageCompute = 0;
// TODO(verify): the meaning of the target ids is not described; 0 is accepted by every target
// check of sceAgcCreateShader (t <= 9 passes on every console).
constexpr u32 kTarget = 0;

// Wave64 (CS_W32_EN clear), so no initiator bit is needed from the header.
constexpr u32 kInitiatorBits = 0;

constexpr u32 kRsrc1 = fld(f::COMPUTE_PGM_RSRC1::VGPRS, (kVgprCount - 1) / 4) |
                       fld(f::COMPUTE_PGM_RSRC1::MEM_ORDERED, 1);
constexpr u32 kRsrc2 = fld(f::COMPUTE_PGM_RSRC2::USER_SGPR, kUserDataCount) |
                       fld(f::COMPUTE_PGM_RSRC2::TGID_X_EN, 1) |
                       fld(f::COMPUTE_PGM_RSRC2::TIDIG_COMP_CNT, 0);
static_assert(kUserDataCount + 1 <= kSgprCount); // the group id lands right after the user data

void put_u16(std::uint8_t *p, std::uint16_t v) { std::memcpy(p, &v, 2); }
void put_u32(std::uint8_t *p, u32 v) { std::memcpy(p, &v, 4); }
void put_u64(std::uint8_t *p, std::uint64_t v) { std::memcpy(p, &v, 8); }

} // namespace

std::span<const std::uint32_t> code() { return kFillShaderCode; }

std::size_t header_bytes() { return kBlobBytes; }

void build_header(std::uint8_t *dst, std::uint32_t code_bytes) {
    std::memset(dst, 0, kBlobBytes);
    Shader h{};
    h.magic = kShaderMagic;
    h.version = kShaderVersion;
    // Self-relative offsets: target address minus the field's own address.
    h.extra = kExtraAt - offsetof(Shader, extra);
    h.code_address = 0; // must be 0 before sceAgcCreateShader
    h.sh_regs = kShRegsAt - offsetof(Shader, sh_regs);
    h.info = kInfoAt - offsetof(Shader, info);
    h.header_bytes = static_cast<u32>(kBlobBytes);
    h.code_bytes = code_bytes;
    h.target = kTarget;
    h.stage = kStageCompute;
    h.num_sh_regs = static_cast<std::uint8_t>(kShRegCount);
    std::memcpy(dst, &h, sizeof h);

    // SH registers. COMPUTE_PGM_LO holds the code offset in 256-byte units (0: the code starts at
    // the code address); sceAgcCreateShader turns LO/HI into the program address.
    const RegPair regs[kShRegCount] = {
        {sh::COMPUTE_PGM_LO, 0},
        {sh::COMPUTE_PGM_HI, 0},
        {sh::COMPUTE_PGM_RSRC1, kRsrc1},
        {sh::COMPUTE_PGM_RSRC2, kRsrc2},
        {sh::COMPUTE_PGM_RSRC3, 0},
        {sh::COMPUTE_NUM_THREAD_X, fld(f::COMPUTE_NUM_THREAD_X::NUM_THREAD_FULL, kThreadsPerGroup)},
        {sh::COMPUTE_NUM_THREAD_Y, fld(f::COMPUTE_NUM_THREAD_Y::NUM_THREAD_FULL, 1)},
        {sh::COMPUTE_NUM_THREAD_Z, fld(f::COMPUTE_NUM_THREAD_Z::NUM_THREAD_FULL, 1)},
    };
    std::memcpy(dst + kShRegsAt, regs, sizeof regs);

    // Sub-block: five self-relative qwords; the first points at the user-data slot record (the
    // other four are unused here, 0 = none), then the user-data count.
    put_u64(dst + kExtraAt, kSlotAt - kExtraAt);
    put_u16(dst + kExtraAt + kExtraUserDataCount, static_cast<std::uint16_t>(kUserDataCount));
    put_u16(dst + kSlotAt + kSlotStart, static_cast<std::uint16_t>(kUserDataStartSlot));

    // Info block: only the dispatch-initiator bits are read for a compute shader.
    put_u32(dst + kInfoAt + kInfoInitiator, kInitiatorBits);
}

} // namespace bc5::reimpl::agc::fill_shader
