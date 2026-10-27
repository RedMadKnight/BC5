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
    std::uint32_t product_checked = 0; // ... with the product staircase as well (experiment 0341)
    std::uint32_t unbased = 0;         // dispatches without a known base: PFP_SYNC_ME only
    std::uint32_t conditional = 0;     // dispatches NOP-ed: a COND_EXEC range grew too long
    std::uint32_t inserted_dwords = 0; // growth of the IB
};

// Dwords inserted before a checked dispatch (three counts) and a checked draw (two).
inline constexpr std::size_t kCheckDwords = 5 + 3 * 9 + 5 + 2 + 5;
// Experiment 0341 (arm 1): the product staircase. The CP compares one dword per COND_WRITE and
// cannot multiply, so the product of the three counts is bounded as a staircase: a dispatch with
// y > yz_min or z > yz_min (a grid that is not one-dimensional) is refused when x > x_limit as
// well. F403's runaway grids (818 x 820 x 819 = 549 M groups) pass the per-dimension limits
// (2^20, 2^10, 2^10) and fail this; a one-dimensional builder of 2^20 groups passes both. Packets,
// after the per-dimension COND_WRITEs:
//
//   WRITE_DATA   flag2 = 0                       (flag2 = the flag word + 8)
//   COND_WRITE   y > yz_min ? flag2 = 1
//   COND_WRITE   z > yz_min ? flag2 = 1
//   WRITE_DATA   flag + 12 = 0, WR_CONFIRM
//   PFP_SYNC_ME
//   COND_EXEC    flag2, 9 dwords                 (the next packet runs only if flag2 is not 0)
//   COND_WRITE   x > x_limit ? flag = 0
//
// and then the check's own confirm, PFP_SYNC_ME and COND_EXEC over the dispatch. GFX form only.
struct ProductLimit {
    std::uint32_t x_limit = 1u << 16;
    std::uint32_t yz_min = 1;
};
inline constexpr std::size_t kProductDwords = 5 + 9 + 9 + 5 + 2 + 5 + 9;
inline constexpr std::size_t kDrawCheckDwords = 5 + 2 * 9 + 5 + 2 + 5;

// ib: a filtered IB. base: the SET_BASE index-1 base in effect at its start (0 = unknown).
// max: the largest group count accepted per dimension; draw_max: the largest vertex (index) count
// and instance count of a DRAW_INDIRECT / DRAW_INDEX_INDIRECT, checked the same way (0054).
// flag_refs receives the positions (in the returned IB) of the flag address pairs (lo, hi); patch()
// fills them in once the flag's GPU address is known (two dwords: the flag and the confirm word
// after it).
// compute_ring (ADR 0009): the IB runs on a compute ring. The checked dispatches are then the
// MEC form of DISPATCH_INDIRECT (address lo, hi, initiator), whose address is its own, and no
// PFP_SYNC_ME is inserted (the MEC has no prefetch parser). TODO(verify): COND_WRITE and
// COND_EXEC on the BC-250's MEC (ADR 0009, ladder step 5).
// product (experiment 0341): when given, every checked GFX-form dispatch gets the staircase too;
// the flag area then holds four dwords (flag, confirm, flag2, confirm2).
std::vector<std::uint32_t> apply(std::span<const std::uint32_t> ib, std::uint64_t base,
                                 const std::uint32_t (&max)[3], const std::uint32_t (&draw_max)[2],
                                 std::vector<std::size_t> &flag_refs, Stats &stats,
                                 bool compute_ring = false, const ProductLimit *product = nullptr);

void patch(std::span<std::uint32_t> ib, const std::vector<std::size_t> &flag_refs,
           std::uint64_t flag_va);

// Packets to insert before the packet at dword offset `at` of an IB.
struct Insert {
    std::size_t at = 0;
    std::vector<std::uint32_t> words;
};

// Inserts them (offsets ascending, each a packet start; an offset equal to the IB's size appends
// after its last packet, experiment 0341) and grows the IB's own COND_EXEC counts by what lands
// inside their ranges (experiment 0052: Device::submit's CP DMA waits). Returns false and leaves
// the IB unchanged if a count would no longer fit its 14 bits.
bool insert_before(std::vector<std::uint32_t> &ib, const std::vector<Insert> &inserts);

} // namespace bc5::indirect_check
