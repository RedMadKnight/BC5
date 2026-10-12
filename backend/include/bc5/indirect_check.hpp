// SPDX-License-Identifier: GPL-2.0-only
// Indirect dispatch arguments checked by the CP when it runs the dispatch (experiment 0052).
//
// The host reads a DISPATCH_INDIRECT's arguments when the IB is submitted; the second title writes
// most of them on the GPU earlier in the same frame, so the host saw stale values (+/-inf as group
// counts) and dropped the dispatches, among them the ones that build the leaf lists its BVH refit
// walks (experiment 0050). This pass puts the check where the arguments are final: before every
// GFX-form DISPATCH_INDIRECT whose argument address is known (SET_BASE index 1, or the caller's
// base for a rebuilt compute IB),
//
//   WRITE_DATA   flag = 1
//   COND_WRITE   x > max_x ? flag = 0      (and the same for y, z)
//   WRITE_DATA   flag + 4 = 0, WR_CONFIRM  (the ME waits until its writes have landed)
//   PFP_SYNC_ME                            (the PFP reads the flag and the arguments after that)
//   COND_EXEC    flag, 3 dwords            (the dispatch runs only if the flag is not 0)
//   DISPATCH_INDIRECT
//
// Packet layouts: COND_WRITE (function bits 2:0, poll space bit 4, write space bit 8, poll address,
// reference, mask, write address, data) from RPCSX rpcsx/gpu/Pipe.cpp GraphicsPipe::condWrite
// (e8ae148), function 6 = "greater" (ibid., compare()); COND_EXEC from Mesa
// src/amd/common/ac_cmdbuf_cp.c ac_emit_cp_cond_exec (0866ae7); WRITE_DATA DST_SEL / WR_CONFIRM and
// PFP_SYNC_ME from Mesa src/amd/common/sid.h. On the BC-250's GFX ring the sequence skips exactly
// the dispatches with a count over the limit (experiment 0052, direct-selftest --cp-check).
// Every other DISPATCH_INDIRECT gets the PFP_SYNC_ME alone. The IB's own COND_EXEC counts grow by
// what is inserted in their ranges; if one would no longer fit its 14 bits, the IB's
// DISPATCH_INDIRECTs are NOP-ed instead (none runs unchecked). No GPU access.
#pragma once

#include <cstddef>
#include <cstdint>
#include <span>
#include <vector>

namespace bc5::indirect_check {

struct Stats {
    std::uint32_t checked = 0;         // dispatches given the check
    std::uint32_t unbased = 0;         // dispatches without a known base: PFP_SYNC_ME only
    std::uint32_t conditional = 0;     // dispatches NOP-ed: a COND_EXEC range grew too long
    std::uint32_t inserted_dwords = 0; // growth of the IB
};

// Dwords inserted before a checked dispatch.
inline constexpr std::size_t kCheckDwords = 5 + 3 * 9 + 5 + 2 + 5;

// ib: a filtered IB. base: the SET_BASE index-1 base in effect at its start (0 = unknown).
// max: the largest group count accepted per dimension. flag_refs receives the positions (in the
// returned IB) of the flag address pairs (lo, hi); patch() fills them in once the flag's GPU
// address is known (two dwords: the flag and the confirm word after it).
std::vector<std::uint32_t> apply(std::span<const std::uint32_t> ib, std::uint64_t base,
                                 const std::uint32_t (&max)[3], std::vector<std::size_t> &flag_refs,
                                 Stats &stats);

void patch(std::span<std::uint32_t> ib, const std::vector<std::size_t> &flag_refs,
           std::uint64_t flag_va);

} // namespace bc5::indirect_check
