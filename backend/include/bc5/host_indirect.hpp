// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0346 (third version): a GFX-form DISPATCH_INDIRECT that the CP would run with a base-1
// register of 0 is resolved and verified by the host, at filter time, and rewritten only to a page the
// host has read itself — or dropped. Nothing else is touched. Never a GPU read at an address the host
// has not verified (D16).
//
// Why. The second title's BVH refit issues GFX-form DISPATCH_INDIRECTs whose data offsets are the low
// dwords of addresses in its 4-GiB window, right after it set SET_BASE index 1 to 0 (its zeroing pair,
// compute type then graphics type); the console resolves that within the process's window, the BC-250
// read the bare offset: a CPF permission fault, a failed ring reset, the machine down (exp 0344, hang 2
// of 2026-10-27 12:52, F416). Three builds that inferred a base for other dispatches as well (exp 0345
// v1, v2; 0346's first build) took the box down with RT off: the CP keeps ONE base-1 register, set by a
// SET_BASE index 1 of either shader type and read by a DISPATCH_INDIRECT of either type (the host's own
// conversions pair a compute-type SET_BASE with a graphics-type dispatch and have run since experiment
// 0038), carried across jobs in ring order; a dispatch without a SET_BASE in its own IB runs on what the
// register holds, and that is right whenever the title set it in an earlier buffer. Replacing it with a
// window (v1), a per-type register (v2, 0346's first build) or a NOP dropped the title's and the host's
// compute work by the thousand (then a CP wait nothing satisfies) or polled guard pages (then a CP fault).
//
// So this pass tracks that one register as the caller carries it from the jobs before, updated by the
// IB's own SET_BASE index-1 packets (the host's conversions included: they are in the IB), and for every
// GFX-form DISPATCH_INDIRECT (3 dwords: offset, initiator):
//   - register non-zero, or never set since the device opened: LEFT ALONE (the CP's read is the title's
//     or the conversion's own);
//   - register 0 by an explicit SET_BASE 0 (the title's zeroing, seen by this pass in this or an earlier
//     IB): the candidate is window + offset — the title's window being the high 32 bits of its own
//     non-zero SET_BASE values — and the candidate must lie in a real mapping (a userptr or shared
//     mapping of title memory, not a PRT window, a guard page or a zero buffer), be readable from the CPU
//     through the caller's reader, and hold counts within the host's sanity limits (stale values accepted,
//     experiment 0038); verified: the dispatch becomes SET_BASE (its own type) = the page holding the
//     arguments, the dispatch with offset = address - page, SET_BASE (its own type) = 0 — the CP reads the
//     page the host read and the register is 0 again, as the title left it; otherwise: that one dispatch
//     is a NOP, counted with its reason.
// DRAW_INDIRECTs are left as they are. The IB's own COND_EXEC counts grow around the inserted packets
// (indirect_check::insert_before); if one cannot, the rewritten dispatches are NOP-ed instead.
// No GPU access; pure functions over an IB and a mapping table, unit-tested.
#pragma once

#include <cstddef>
#include <cstdint>
#include <functional>
#include <span>
#include <vector>

namespace bc5::host_indirect {

// A mapping the GPU can read: title memory mapped as a userptr or shared BO. Sorted by va, disjoint.
struct Region {
    std::uint64_t va = 0;
    std::uint64_t size = 0;
};

// The host's sanity limits for the three counts (as the host's own check, experiment 0038).
struct Limits {
    std::uint32_t per_dim = 65536u * 64u;
    std::uint64_t product = 65536ull * 64ull;
};

// Reads the three counts at va from the CPU side; false when it cannot (the page is not readable there).
using Reader = std::function<bool(std::uint64_t va, std::uint32_t (&counts)[3])>;

// The CP's base-1 register as the caller carries it between jobs: its value, and whether an explicit
// SET_BASE index 1 = 0 made it 0 (a register that was never set is 0 too, and is left alone).
struct Register {
    std::uint64_t base = 0;
    bool zeroed = false;
};

enum class Decision : std::uint8_t { Leave, Rewrite, Drop };
enum class Why : std::uint8_t {
    NonZero,        // the register is non-zero (set in this IB or carried): the CP's own read
    NeverSet,       // the register is 0 but no SET_BASE 0 was ever seen: left alone
    Verified,       // rewritten to the verified page
    NoCandidate,    // register 0 and no window known
    NotRealMapping, // the candidate is outside every real mapping
    Unreadable,     // the reader could not read it
    Insane          // the counts fail the limits
};

struct Resolution {
    std::size_t at = 0;            // the dispatch's offset in the IB
    std::uint32_t shader_type = 0; // the header's bit 1: 0 graphics, 1 compute (the type the SET_BASEs emitted carry)
    std::uint64_t program = 0;     // COMPUTE_PGM_LO/HI as SET_SH_REG set them earlier in the IB (0: not there)
    std::uint64_t base = 0;        // the register at the dispatch (0 for a candidate)
    std::uint64_t window = 0;      // the window used for the candidate
    std::uint64_t address = 0;     // window + offset (a candidate), or base + offset (left)
    std::uint64_t page = 0;        // the 4-KiB page of the address (the SET_BASE emitted)
    std::uint32_t counts[3] = {0, 0, 0};
    Decision decision = Decision::Leave;
    Why why = Why::NonZero;
};

struct Stats {
    std::uint32_t left_nonzero = 0;
    std::uint32_t left_never_set = 0;
    std::uint32_t rewritten = 0;
    std::uint32_t dropped_no_candidate = 0;
    std::uint32_t dropped_unmapped = 0;
    std::uint32_t dropped_unreadable = 0;
    std::uint32_t dropped_insane = 0;
    std::uint32_t nop_on_overflow = 0; // rewrites turned into NOPs: a COND_EXEC count would not fit
    Register register_out;             // the register as the IB leaves it (its own SET_BASEs applied; a rewrite leaves 0)
    std::uint64_t window_seen = 0;     // the window the IB's own non-zero SET_BASEs name, 0 if none
};

inline constexpr std::uint32_t kSetBaseGfx = 0xC0021100u;     // PKT3(SET_BASE, 2, 0), graphics type
inline constexpr std::uint32_t kSetBaseCompute = 0xC0021102u; // ... | the shader-type bit (compute)
inline constexpr std::size_t kRewriteDwords = 8;              // two SET_BASEs around the dispatch

// carried: the register at the IB's start; window: the title's window for a register of 0 (0 = none
// known). Returns one record per GFX-form DISPATCH_INDIRECT.
std::vector<Resolution> resolve_indirect(std::span<const std::uint32_t> ib, const Register &carried,
                                         std::uint64_t window, const std::vector<Region> &regions,
                                         const Reader &read, const Limits &limits, Stats &stats);

// Applies the decisions to ib in place: the rewrites' packets inserted (the IB's own COND_EXEC counts
// grown), the drops NOP-ed. Returns false when a COND_EXEC count would overflow: the IB then holds the
// drops and the rewritten dispatches NOP-ed too (stats.nop_on_overflow), nothing inserted.
bool rewrite_verified(std::vector<std::uint32_t> &ib, const std::vector<Resolution> &decisions, Stats &stats);

// The region holding [va, va + bytes), or nullptr.
const Region *region_of(const std::vector<Region> &regions, std::uint64_t va, std::uint64_t bytes);

} // namespace bc5::host_indirect
