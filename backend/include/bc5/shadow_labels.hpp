// SPDX-License-Identifier: GPL-2.0-only
// Host-owned shadow labels for an IB's own end-of-pipe syncs (experiment 0341, arm 2).
//
// The second title's command buffers synchronise with themselves through labels in the title's
// memory: WRITE_DATA 0, RELEASE_MEM end-of-pipe 1, WAIT_REG_MEM == 1. A stray store of the RT work
// (F360, F406: a sync label overwritten with two floats) lands on such a label, the CP waits for
// a value that never comes, and the ring times out; the reset then took the machine down twice.
// This pass gives every label the IB both writes and waits on a shadow word in memory the host
// owns (the job's scratch, far from the title's buffers): each write of the label is preceded by
// a copy of the packet writing the shadow (inside the same COND_EXEC range, so a skipped writer
// skips its copy too), and each wait on the label polls the shadow instead.
// The title's own label is still written (its CPU polls it); only the CP's wait no longer depends
// on memory a shader can reach through a garbage pointer.
//
// Packet layouts: RELEASE_MEM (8 dwords: header, event, EOP_DATA_SEL bits 31:29 of dword 2,
// address lo/hi in dwords 3/4, data lo/hi), WRITE_DATA (DST_SEL bits 11:8 of dword 1, address
// lo/hi in dwords 2/3, data), WAIT_REG_MEM / WAIT_REG_MEM64 (mem_space bit 4 of dword 1, address
// lo/hi in dwords 2/3): Mesa src/amd/common/sid.h (0866ae7); the same fields policy.cpp's
// label_of reads. The IB's own COND_EXEC counts grow around the copies (indirect_check's
// insert_before). No GPU access.
#pragma once

#include <cstddef>
#include <cstdint>
#include <span>
#include <vector>

namespace bc5::shadow_labels {

struct Stats {
    std::uint32_t labels = 0;   // labels given a shadow slot in this IB
    std::uint32_t writes = 0;   // writer packets copied to the shadow
    std::uint32_t waits = 0;    // waits redirected to the shadow
    std::uint32_t overflow = 0; // labels left alone: no slot left (max_slots)
    bool failed = false;        // the IB was left unchanged: a COND_EXEC count would overflow
};

// Each slot is 8 bytes at shadow_va + 8 * slot. Before patch() the slot's address is a marker:
// address lo = 8 * slot, address hi = kMarkerHi (the title's addresses never carry it).
inline constexpr std::uint32_t kMarkerHi = 0x5a5au;
inline constexpr std::size_t kSlotBytes = 8;

// Rewrites ib in place (returns false and leaves it unchanged on a COND_EXEC overflow). A label
// qualifies when a RELEASE_MEM with a data value or a WRITE_DATA to memory writes it earlier in
// the IB than a memory-space WAIT_REG_MEM[64] on it; slots are given in order of first wait, at
// most max_slots of them.
bool apply(std::vector<std::uint32_t> &ib, std::uint32_t max_slots, Stats &stats);

// Replaces the markers with shadow_va + 8 * slot. Returns the number of slots referenced
// (the highest slot + 1), 0 when there are none.
std::uint32_t patch(std::span<std::uint32_t> ib, std::uint64_t shadow_va);

} // namespace bc5::shadow_labels
