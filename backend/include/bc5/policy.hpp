// SPDX-License-Identifier: GPL-2.0-only
// The submission policy of ADR 0005: which packets of a console-format command buffer go to the
// AMD CP verbatim, which are NOP-ed, which are rewritten. The table is backend/policy/pm4-policy.tsv,
// embedded at build time; tools/bc5-agc reads the same file (`bc5-agc check`).
#pragma once

#include <cstddef>
#include <cstdint>
#include <functional>
#include <span>
#include <string_view>
#include <vector>

namespace bc5::policy {

enum class Verdict : std::uint8_t { Pass, Rewrite, Split, Drop };

const char *verdict_name(Verdict v);

class Policy {
public:
    // Parses a table; throws std::invalid_argument naming the first bad line.
    static Policy parse(std::string_view tsv);
    // The table shipped with the repository.
    static const Policy &builtin();

    Verdict op(std::uint8_t opcode) const;
    Verdict reg(std::uint32_t mm) const;
    Verdict type0() const { return type0_; }

    // Verdict for one packet at `p` (header first), `len` dwords including the header.
    Verdict packet(const std::uint32_t *p, std::uint32_t len) const;

private:
    struct Range {
        std::uint32_t first, last;
        Verdict verdict;
    };
    Verdict ops_[256];
    bool op_set_[256] = {};
    std::vector<Range> regs_;
    Verdict default_op_ = Verdict::Drop;
    Verdict default_reg_ = Verdict::Pass;
    Verdict type0_ = Verdict::Drop;
};

struct FilterStats {
    std::uint64_t packets = 0, passed = 0, rewritten = 0, split = 0, dropped = 0;
    std::uint64_t dwords = 0, dwords_dropped = 0;
    std::uint64_t cu_mask_rewrites = 0, int_sel_rewrites = 0, context_control_rewrites = 0;
    std::uint64_t truncated = 0;      // packets running past the end (the rest is NOP-ed)
    std::uint64_t unmapped_drops = 0; // packets referencing memory outside the mapped ranges
    std::uint64_t extra_drops = 0;    // packets dropped by FilterOptions::extra_drop
    std::uint64_t reg_write_drops = 0; // WRITE_DATA with a register destination (DST_SEL 0)
};

// Options for the rewrites.
struct FilterOptions {
    std::uint32_t cu_mask = 0xffffffffu; // ANDed into COMPUTE_STATIC_THREAD_MGMT_SE* and RSRC3.CU_EN
    bool clear_int_sel = true;           // RELEASE_MEM / EVENT_WRITE_EOP: the host fires the events
    bool drop_draws = false;             // staging (ADR 0005 §5c): NOP every draw and dispatch
    // CONTEXT_CONTROL as RADV/radeonsi emit it (0x80000000 0x80000000: update the enables, load
    // and shadow nothing). The console's 0x91018003/0x80018003 asks the CP to load and shadow
    // register state through areas amdgpu never set up on gfx10 (experiment 0016).
    bool safe_context_control = true;
    // When set, every packet whose memory operand lies outside the mapped ranges is dropped
    // instead of faulting the GPU. Called with (address, bytes).
    std::function<bool(std::uint64_t, std::uint64_t)> mapped;
    // Opcodes to drop in addition to the table (experiments).
    std::vector<std::uint8_t> extra_drop;
};

// Draw and dispatch opcodes (the "work" packets), for staging.
bool is_draw_or_dispatch(std::uint8_t opcode);

// Memory operands (address, bytes) of one packet, for the mapped-range check.
std::vector<std::pair<std::uint64_t, std::uint64_t>> memory_operands(const std::uint32_t *p,
                                                                     std::uint32_t len);

// Copies `src` to `out` (same length, `out.size() >= src.size()`) applying the policy: dropped
// packets become one-dword NOPs (0xffff1000) so every offset, and therefore every COND_EXEC skip
// count, stays valid; rewrites are applied in place. Returns the number of dwords written.
std::size_t filter(const Policy &policy, std::span<const std::uint32_t> src,
                   std::span<std::uint32_t> out, const FilterOptions &opt, FilterStats &stats);

// PM4 constants shared with the filter and the tests.
inline constexpr std::uint32_t kNop = 0xffff1000u;
inline constexpr std::uint8_t kOpContextControl = 0x28;
inline constexpr std::uint8_t kOpWriteData = 0x37;
inline constexpr std::uint8_t kOpEventWriteEop = 0x47;
inline constexpr std::uint8_t kOpReleaseMem = 0x49;

} // namespace bc5::policy
