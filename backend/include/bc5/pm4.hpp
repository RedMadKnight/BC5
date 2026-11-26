// SPDX-License-Identifier: GPL-2.0-only
// PM4 type-3 packet builder. Encoding per docs/formats/agc.md §2 and
// IGT lib/amdgpu/amd_PM4.h:48-52 (igt-gpu-tools @ 9d4b6ef).
#pragma once

#include <cstddef>
#include <cstdint>
#include <initializer_list>
#include <span>
#include <vector>

namespace bc5::pm4 {

// Opcodes used by the backend (Mesa src/amd/common/sid.h, tools/bc5-agc/regdb/pm4-opcodes.tsv).
enum class Op : std::uint8_t {
    Nop = 0x10,
    DispatchDirect = 0x15,
    ContextControl = 0x28,
    SetConfigReg = 0x68,
    SetContextReg = 0x69,
    SetShReg = 0x76,
    SetUconfigReg = 0x79,
    SetShRegIndex = 0x9B,
};

// Header bit 1: the packet targets the compute pipeline (IGT PACKET3_COMPUTE).
inline constexpr std::uint32_t kShaderTypeCompute = 1u << 1;
// Type-3 NOP with count field 0x3fff: a one-dword filler (IGT GFX_COMPUTE_NOP).
inline constexpr std::uint32_t kNopFiller = 0xffff1000u;
// Register block bases (MMIO dword index), docs/formats/agc.md §2.
inline constexpr std::uint32_t kShRegBase = 0x2c00;
inline constexpr std::uint32_t kUconfigRegBase = 0xc000;

// Type-3 header for a packet with `payload` dwords after the header (payload >= 1).
constexpr std::uint32_t header3(Op op, std::uint32_t payload, bool compute = false) {
    return (3u << 30) | (((payload - 1u) & 0x3fffu) << 16) |
           (static_cast<std::uint32_t>(op) << 8) | (compute ? kShaderTypeCompute : 0u);
}

class Builder {
public:
    // Appends a type-3 packet; `payload` must not be empty.
    Builder &packet(Op op, std::span<const std::uint32_t> payload, bool compute = false);
    Builder &packet(Op op, std::initializer_list<std::uint32_t> payload, bool compute = false);

    // SET_SH_REG for consecutive registers starting at `offset` (relative to kShRegBase).
    Builder &set_sh_reg(std::uint32_t offset, std::initializer_list<std::uint32_t> values,
                        bool compute = true);

    // Pads with kNopFiller until the size is a multiple of `align` dwords.
    Builder &pad_to_multiple(std::size_t align);

    const std::vector<std::uint32_t> &dwords() const noexcept { return dwords_; }
    std::size_t size() const noexcept { return dwords_.size(); }

private:
    std::vector<std::uint32_t> dwords_;
};

} // namespace bc5::pm4
