// SPDX-License-Identifier: GPL-2.0-only
// Context-state stack emulation (ADR 0005 amendment xix, experiment 0016 run 73).
//
// The console's driver brackets its internal draws (clears, resolves) with
//   CONTEXT_CONTROL (context shadowing off), CLEAR_STATE cmd 1, <default state, the draw>,
//   CONTEXT_CONTROL (shadowing on), CLEAR_STATE cmd 2
// and relies on cmd 2 to bring back the context registers the game had before cmd 1 — the CP
// keeps them in shadow memory the console's system set up. amdgpu sets up no such memory on
// gfx10: cmd 1/2 stall the CP there (F27), so the policy rewrites both to cmd 0 (the kernel's
// clear state), which leaves the game without its context state after every internal draw.
// The cmd field (4 bits): 0 clear_state, 1 push_state, 2 pop_state, 3 push_clear_state —
// PFP_CLEAR_STATE_cmd_enum in GPUOpen-Drivers/pal,
// src/core/hw/gfxip/gfx9/chip/gfx9_plus_merged_f32_pfp_pm4_packets.h (dev branch, read
// 2026-10-01); the stream's use matches (experiment 0016, run 73).
//
// The tracker follows the context registers an IB sets (SET_CONTEXT_REG, LOAD_CONTEXT_REG,
// LOAD_CONTEXT_REG_INDEX tables read from memory), snapshots them at a push and replaces an
// unconditional pop by SET_CONTEXT_REG packets that restore the snapshot. No GPU access.
#pragma once

#include <array>
#include <bitset>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <span>
#include <vector>

namespace bc5::state_stack {

inline constexpr std::size_t kContextRegs = 0x400; // offsets from 0xa000 (mm 0x28000)

struct Context {
    std::array<std::uint32_t, kContextRegs> value{};
    std::bitset<kContextRegs> valid;
};

struct Stats {
    std::uint32_t pushes = 0, pops = 0;
    std::uint32_t conditional = 0;       // CLEAR_STATE inside a COND_EXEC range: left to the filter
    std::uint32_t unmatched_pops = 0;    // a pop with an empty stack: left to the filter
    std::uint32_t restored_regs = 0;     // registers written back by the pops
    std::uint32_t inserted_dwords = 0;   // growth of the IB
    std::uint32_t tables = 0;            // LOAD_CONTEXT_REG[_INDEX] followed
    std::uint32_t unreadable_tables = 0; // ... whose memory the caller did not vouch for
};

class Tracker {
  public:
    // (address, bytes) -> may the tracker read that memory of this process? IB addresses are
    // guest addresses; with 1:1 userptr mappings they are valid here exactly when mapped.
    using Readable = std::function<bool(std::uint64_t, std::uint64_t)>;

    // src: the IB as the guest wrote it. filtered: the same IB after policy::filter (same
    // length, dropped packets NOP-ed). Returns the IB to execute.
    std::vector<std::uint32_t> apply(std::span<const std::uint32_t> src,
                                     std::span<const std::uint32_t> filtered,
                                     const Readable &readable, Stats &stats);

    const Context &context() const { return ctx_; }
    std::size_t depth() const { return stack_.size(); }
    void reset() {
        ctx_ = Context{};
        stack_.clear();
    }

  private:
    void set(std::uint32_t reg, std::uint32_t value) {
        if (reg < kContextRegs) {
            ctx_.value[reg] = value;
            ctx_.valid.set(reg);
        }
    }
    Context ctx_;
    std::vector<Context> stack_;
};

} // namespace bc5::state_stack
