// SPDX-License-Identifier: GPL-2.0-only
// Full register state of a GFX context across command buffers (ADR 0008, experiment 0072).
//
// A graphics buffer split at a cross-queue wait needs, before each later piece, the state the
// frame's earlier buffers set: experiment 0072 found 921 context, 86-177 SH and 57 UCONFIG
// registers set only by earlier buffers at the main buffer's waits. This tracker follows every
// buffer of a context in submission order:
//   - SET_CONFIG/CONTEXT/SH/UCONFIG_REG and their _INDEX forms;
//   - LOAD_CONTEXT/SH/UCONFIG_REG (register ranges read from memory) and LOAD_*_REG_INDEX
//     (consecutive registers or (offset, value) pairs in memory), through a caller-supplied
//     reader; a table it may not read is counted, and the state is then incomplete;
//   - INDIRECT_BUFFER (Mesa sid.h PKT3_INDIRECT_BUFFER 0x3F): the nested buffer is followed
//     through the reader, four levels deep at most;
//   - SET_BASE, INDEX_BASE, INDEX_BUFFER_SIZE, INDEX_TYPE, NUM_INSTANCES, CONTEXT_CONTROL;
//   - CLEAR_STATE: cmd 0 forgets the context registers (the CP's clear state), cmd 1/2 push and
//     pop them (as bc5::state_stack).
// emit_prefix() writes packets that set the tracked state on a context of unknown state: a
// CONTEXT_CONTROL with the load bits set, a CLEAR_STATE cmd 0, the registers in runs, the packet
// state. The tracked CONTEXT_CONTROL is not replayed (the policy forces RADV's form, see
// pm4-policy.tsv) and does not take part in operator==. The prefix goes through the policy filter
// like the game's packets. Packet layouts: Mesa src/amd/common/sid.h and PAL's pm4 headers (see policy.cpp and
// state_stack.hpp for the same packets); LOAD_*_REG_INDEX DATA_FORMAT as in state_stack.cpp.
// TODO(verify): on hardware, that the emitted prefix reproduces a piece's state (ADR 0008 step 3).
// No GPU access.
#pragma once

#include <cstdint>
#include <functional>
#include <map>
#include <span>
#include <vector>

namespace bc5::full_state {

enum Space : int { Config = 0, Context = 1, Sh = 2, Uconfig = 3, Spaces = 4 };

struct Stats {
    std::uint64_t packets = 0;
    std::uint64_t registers_set = 0;
    std::uint64_t tables = 0;             // LOAD_* tables read
    std::uint64_t unreadable_tables = 0;  // LOAD_* tables the reader refused: state incomplete
    std::uint64_t clears = 0, pushes = 0, pops = 0;
    std::uint64_t nested = 0, unreadable_nested = 0; // INDIRECT_BUFFERs followed / not readable
};

// check_split(): a graphics buffer split at `wait` (a packet offset), the later piece run after
// the prefix of the state up to there instead of after the frame's earlier buffers and the head.
struct SplitCheck {
    std::size_t prefix_dwords = 0;
    std::size_t draws = 0;            // draws and dispatches in the later piece
    std::size_t mismatched_draws = 0; // whose tracked state differs between the two
    int first_space = -1;             // the first difference: space, register offset
    std::uint32_t first_offset = 0;
    std::size_t stack_depth = 0;      // CLEAR_STATE pushes open at the split
};

class Tracker {
public:
    // (address, bytes) -> pointer to readable memory holding them, or nullptr.
    using Reader = std::function<const std::uint32_t *(std::uint64_t, std::uint64_t)>;

    // Follows one buffer, as the CP would execute it (COND_EXEC ranges are followed as if taken).
    void apply(std::span<const std::uint32_t> ib, const Reader &read, Stats &stats);

    // Packets that set the tracked state on a context of unknown state.
    std::vector<std::uint32_t> emit_prefix() const;

    // Register value, if tracked. space: Context (offset from 0xa000), Sh (0x2c00), Uconfig
    // (0xc000), Config (0x2000).
    bool get(Space space, std::uint32_t offset, std::uint32_t &value) const;
    std::size_t count(Space space) const { return regs_[space].n; }
    bool operator==(const Tracker &o) const;
    // The first register that differs from o (space, offset); false if the registers are equal.
    bool first_difference(const Tracker &o, int &space, std::uint32_t &offset) const;
    std::size_t stack_depth() const { return context_stack_.size(); }
    // The saved contexts of o's open pushes. A piece needs no prefix for them: the device's
    // state-stack emulation (bc5::state_stack, direct.cpp) keeps its stack across submissions
    // and restores a pop from it.
    void adopt_stack(const Tracker &o) { context_stack_ = o.context_stack_; }

private:
    void apply_level(std::span<const std::uint32_t> ib, const Reader &read, Stats &stats, int depth);
    struct PacketState {
        std::map<std::uint32_t, std::vector<std::uint32_t>> set_base; // index -> body after header
        std::vector<std::uint32_t> index_base, index_buffer_size, index_type, num_instances,
            context_control;
    };
    void set(Space space, std::uint32_t offset, std::uint32_t value);
    // One register space: flat arrays over the space's range (experiment 0074: a std::map per
    // register cost 16-33 % of a core in the host), offsets past it in a map.
    struct RegFile {
        explicit RegFile(std::size_t size) : value(size, 0), has(size, 0) {}
        std::vector<std::uint32_t> value;
        std::vector<std::uint8_t> has;
        std::map<std::uint32_t, std::uint32_t> overflow;
        std::size_t n = 0;
        void set(std::uint32_t off, std::uint32_t v);
        bool get(std::uint32_t off, std::uint32_t &v) const;
        void clear();
        bool operator==(const RegFile &o) const;
        bool first_difference(const RegFile &o, std::uint32_t &off) const;
        template <class F> void for_each(F f) const {
            for (std::size_t k = 0; k < has.size(); ++k)
                if (has[k] != 0) f(static_cast<std::uint32_t>(k), value[k]);
            for (const auto &[k, v] : overflow) f(k, v);
        }
    };
    // Sizes from Mesa src/amd/common/sid.h (sparse clone at 0866ae7): config 0x8000-0xB000,
    // SH 0xB000-0xC000, context 0x28000-0x30000, UCONFIG 0x30000-0x40000 (byte addresses).
    RegFile regs_[Spaces] = {RegFile(0xc00), RegFile(0x2000), RegFile(0x400), RegFile(0x4000)};
    std::vector<RegFile> context_stack_;
    PacketState packets_;
};

// `before`: the state after the frame's earlier buffers. Draws and dispatches: Mesa sid.h
// (DISPATCH_DIRECT 0x15, DISPATCH_INDIRECT 0x16, DRAW_INDIRECT 0x24, DRAW_INDEX_INDIRECT 0x25,
// DRAW_INDEX_2 0x27, DRAW_INDIRECT_MULTI 0x2C, DRAW_INDEX_AUTO 0x2D, DRAW_INDEX_OFFSET_2 0x35,
// DRAW_INDEX_INDIRECT_MULTI 0x38).
SplitCheck check_split(const Tracker &before, std::span<const std::uint32_t> ib, std::size_t wait,
                       const Tracker::Reader &read);

// Experiment 0089: calls f for every draw and dispatch of ib (not of its nested buffers) with the
// packet's offset, its dwords and the tracked state just before it (`before` + the buffer up to
// there). For a per-draw journal of a frame; no GPU access.
void for_each_draw(const Tracker &before, std::span<const std::uint32_t> ib, const Tracker::Reader &read,
                   const std::function<void(std::size_t, std::span<const std::uint32_t>, const Tracker &)> &f);

} // namespace bc5::full_state
