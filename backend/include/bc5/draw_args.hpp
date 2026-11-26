// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0381: the arguments of a GFX IB's indirect draws, read by the host at submit and again
// when the job completes or times out (BC5_DIRECT_DRAW_ARGS_JOURNAL=1, default off; CPU reads only,
// no packet is added).
//
// At the 18:08 hang of 2026-10-29 (exp 0381, F662) the host's timeout probe read index-like words
// (ascending 16-bit pairs, 000f0101 000f0102 ...) in 13 of 15 DRAW_INDIRECT argument slots of the
// stuck job, while the CP check of experiment 0057 (at most 2^20 vertices and 64 instances,
// indirect_check.hpp) would have skipped such a draw had its polls read them. Whether those words
// were there when the CP polled and fetched, or arrived after, the timeout read cannot say. This
// journal reads the same slots at two more moments: at submit (before the GPU runs the job; the
// title writes many arguments on the GPU later in the frame, so a stale value is expected there)
// and when the job's fence signals (the values the draws consumed, unless something wrote them
// again since). A healthy job whose slots hold index-like words at completion would make the
// timeout read worthless as evidence; healthy jobs with sane words at completion would make it
// specific.
//
// Packet layouts: DRAW_INDIRECT (0x24) and DRAW_INDEX_INDIRECT (0x25), 5 dwords: data offset from
// SET_BASE index 1, then base-vertex / start-instance (and draw-index) register locations, and the
// draw initiator; the arguments as VkDrawIndirectCommand (vertex count, instance count, first
// vertex, first instance) / VkDrawIndexedIndirectCommand (index count, instance count, first index,
// vertex offset, first instance). Mesa src/amd/vulkan/radv_cmd_buffer.c
// radv_cs_emit_indirect_draw_packet (0866ae7), as indirect_check.cpp uses them. No GPU access.
#pragma once

#include <cstddef>
#include <cstdint>
#include <functional>
#include <span>
#include <string>
#include <vector>

namespace bc5::draw_args {

struct Rec {
    std::uint32_t at = 0;    // dword offset of the packet in the IB scanned
    std::uint32_t op = 0;    // 0x24 or 0x25
    std::uint64_t base = 0;  // SET_BASE index 1 in effect
    std::uint64_t addr = 0;  // base + data offset
    bool read = false;       // the four argument dwords could be read
    std::uint32_t v[4] = {}; // count, instance count, first vertex / index, first instance / vertex offset
};

struct Limits {
    std::uint32_t vertices = 1u << 20; // the CP check's defaults (experiment 0057)
    std::uint32_t instances = 64;
};

enum Flag : std::uint32_t {
    kOverVertices = 1u << 0,  // count above Limits::vertices
    kOverInstances = 1u << 1, // instance count above Limits::instances
    kIndexLike = 1u << 2,     // see index_like()
    kUnread = 1u << 3,        // the slot could not be read
};

// Reads 16 bytes at a CPU-visible guest address; false if it cannot.
using Reader = std::function<bool(std::uint64_t addr, std::uint32_t (&out)[4])>;

// Every DRAW_INDIRECT / DRAW_INDEX_INDIRECT of a GFX IB whose SET_BASE index 1 is known (base_in:
// the base in effect at the IB's start, 0 = unknown; the IB's own SET_BASE packets update it). The
// unbased ones are counted in *unbased when given.
std::vector<Rec> scan(std::span<const std::uint32_t> ib, std::uint64_t base_in, const Reader &read,
                      std::uint32_t *unbased = nullptr);

// The words look like 16-bit index pairs rather than draw arguments: at least two of the three
// neighbouring dwords step by exactly one, and the count or the instance count is above 0xffff.
bool index_like(const std::uint32_t (&v)[4]);

std::uint32_t classify(const Rec &r, const Limits &lim);

// Flags as "over-vertices,index-like" ("-" for none).
std::string flag_names(std::uint32_t flags);

// One journal line (no newline): "draw-args <phase> seq <n> at <dw> op 0x24 base 0x.. addr 0x..
// v <4 words> flags <...>", and, when `then` is given, " | <then_phase> v <4 words> flags <...>
// changed <yes|no>".
std::string line(const char *phase, std::uint64_t seq, const Rec &r, std::uint32_t flags,
                 const char *then_phase = nullptr, const Rec *then = nullptr,
                 std::uint32_t then_flags = 0);

// Re-reads the slots of recs (at completion or timeout) into a copy.
std::vector<Rec> reread(const std::vector<Rec> &recs, const Reader &read);

struct Counters {
    std::uint64_t draws = 0;           // records scanned at submit
    std::uint64_t unbased = 0;         // draws without a known base
    std::uint64_t flagged_submit = 0;  // flagged at submit
    std::uint64_t flagged_done = 0;    // flagged when the job completed
    std::uint64_t changed = 0;         // words different between submit and completion
    std::uint64_t timed_out_jobs = 0;  // jobs whose records were printed at a timeout
};

} // namespace bc5::draw_args
