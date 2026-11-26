// SPDX-License-Identifier: GPL-2.0-only
// The CU mask for registers the stream loads from memory (phase 3 step f, experiment 0016).
//
// The policy filter ANDs FilterOptions::cu_mask into the CU-mask registers a SET_SH_REG writes.
// The console's driver also loads them from memory — LOAD_SH_REG (its register image) and
// LOAD_SH_REG_INDEX tables of (offset, value) pairs carry SPI_SHADER_PGM_RSRC3_PS/GS/HS and
// COMPUTE_STATIC_THREAD_MGMT_SE0-3 (experiment 0016, run 82 survey: 0x0000ffff, 0xffff0000 for
// HS, 0xffffffff) — and a load cannot be rewritten in place. This pass appends, after every such
// load, a SET_SH_REG with the loaded value ANDed with the mask. No GPU access.
#pragma once

#include <cstddef>
#include <cstdint>
#include <functional>
#include <span>
#include <vector>

namespace bc5::cu_tables {

struct Stats {
    std::uint32_t loads = 0;           // LOAD_SH_REG[_INDEX] packets that carried a CU-mask register
    std::uint32_t overrides = 0;       // SET_SH_REG packets appended
    std::uint32_t inserted_dwords = 0; // growth of the IB
    std::uint32_t conditional = 0;     // such loads inside a COND_EXEC range: left alone
    std::uint32_t unreadable = 0;      // tables whose memory the caller did not vouch for
};

// (address, bytes) -> may this process read that memory? (As in bc5::state_stack.)
using Readable = std::function<bool(std::uint64_t, std::uint64_t)>;

// ib: a filtered IB (dropped packets NOP-ed). Returns it with the overrides appended; identical
// to the input when cu_mask is 0xffffffff.
std::vector<std::uint32_t> apply(std::span<const std::uint32_t> ib, std::uint32_t cu_mask,
                                 const Readable &readable, Stats &stats);

} // namespace bc5::cu_tables
