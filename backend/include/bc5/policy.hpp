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
    std::uint64_t unsatisfiable_wait_drops = 0; // WAIT_REG_MEM[64] on a label this IB never writes
    std::uint64_t gds_drops = 0; // DMA_DATA / WRITE_DATA to or from GDS (FilterOptions::drop_gds)
    std::uint64_t gds_rewrites = 0; // GDS accesses redirected to the shadow buffer (gds_shadow_va)
    std::uint64_t offset_drops = 0; // packets dropped through FilterOptions::drop_offsets
    std::uint64_t dispatch_rewrites = 0; // DISPATCH_* initiators given ORDERED_APPEND_ENBL
    std::uint64_t mec_indirect_rewrites = 0; // DISPATCH_INDIRECT, compute-queue form -> GFX form
    std::uint64_t mec_indirect_drops = 0;    // the same, address outside FilterOptions::mec_indirect_base's 4 GiB
    std::uint64_t pfp_syncs = 0; // PFP_SYNC_ME inserted before rewritten DISPATCH_INDIRECT (Device::submit)
    std::uint64_t clear_state_rewrites = 0; // CLEAR_STATE cmd 1/2 -> cmd 0
    std::uint64_t cs_done_rewrites = 0; // RELEASE_MEM CS_DONE/index 6 without data -> BOTTOM_OF_PIPE_TS/5
    std::uint64_t gcr_rewrites = 0;     // ACQUIRE_MEM with FilterOptions::gcr_clear bits cleared
    // IB offsets (dwords) where a SAMPLE_PIPELINESTAT took a dropped marker's place
    // (FilterOptions::stat_sample_va); sample k went to stat_sample_va + k * kStatSampleStride.
    std::vector<std::uint32_t> stat_sample_offsets;
};

inline constexpr std::uint64_t kStatSampleStride = 0x80; // 11 qwords of counters, padded

// Options for the rewrites.
struct FilterOptions {
    std::uint32_t cu_mask = 0xffffffffu; // ANDed into COMPUTE_STATIC_THREAD_MGMT_SE* and RSRC3.CU_EN
    bool clear_int_sel = true;           // RELEASE_MEM / EVENT_WRITE_EOP: the host fires the events
    // Experiment 0044: GCR_CNTL bits (ACQUIRE_MEM dword 7 on gfx10; GL2_WB is bit 15, layout in
    // tools/bc5-agc/regdb/pkt3.json from Mesa) cleared in every ACQUIRE_MEM. 0 = unchanged.
    std::uint32_t gcr_clear = 0;
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
    // Dword offsets of packets to drop, decided by the caller from data the filter cannot see
    // (e.g. an indirect draw whose argument buffer holds an absurd count). Sorted or not.
    std::vector<std::uint32_t> drop_offsets;
    // WAIT_REG_MEM[64] passes only when its label was written earlier in the same IB (by a
    // passing WRITE_DATA/RELEASE_MEM/EVENT_WRITE_EOP/ATOMIC_MEM); other waits are dropped and
    // left to the host. A wait the GPU can never satisfy ends in the kernel's GPU timeout.
    bool self_waits_only = true;
    // Drop CP packets that read or write GDS (DMA_DATA SRC/DST_SEL 1, WRITE_DATA DST_SEL 3): the
    // context has no GDS unless a GDS BO is in its BO lists.
    bool drop_gds = true;
    // When non-zero: the CP's GDS accesses are redirected to this 64 KiB memory buffer instead
    // of being dropped — DMA_DATA GDS→memory / memory→GDS / fill→GDS become memory DMAs against
    // shadow + GDS offset (the offset is what the packet carries in the GDS-side address field),
    // WRITE_DATA to GDS writes the shadow. A real GDS partition makes this game's gfx shaders hang
    // (experiment 0016, runs 49–51); the shadow keeps the counters the game reads back consistent.
    std::uint64_t gds_shadow_va = 0;
    // Set ORDERED_APPEND_ENBL (COMPUTE_DISPATCH_INITIATOR bit 3, Mesa gfx10) on every dispatch:
    // the console's dispatches carry 0x41 (COMPUTE_SHADER_EN | ORDER_MODE) and their shaders use
    // ds_ordered_count; on the BC-250 the counters came back as garbage (experiment 0016, run 55).
    bool ordered_append_enable = false;
    // Packets the submission executes before the IB (copied verbatim into the scratch ahead of
    // it, not filtered): state the console's CP derives itself and the AMD CP needs told, e.g.
    // VGT_PRIMITIVE_TYPE through SET_UCONFIG_REG_INDEX index 1 (experiment 0016, run 62).
    std::vector<std::uint32_t> prologue;
    // Packets executed right after the IB (verbatim, unfiltered), e.g. a pipeline-statistics
    // sample to compare with one taken in the prologue.
    std::vector<std::uint32_t> epilogue;
    // Diagnostics (experiment 0016, run 74): when non-zero, up to stat_sample_max dropped
    // register-destination WRITE_DATA packets (the console driver's pass markers, at least four
    // dwords each) are replaced by EVENT_WRITE SAMPLE_PIPELINESTAT into this address + k * stride,
    // so the pipeline counters can be read per marker-delimited section of one IB.
    std::uint64_t stat_sample_va = 0;
    std::uint32_t stat_sample_max = 0;
    // RELEASE_MEM with EVENT_INDEX 6 and DATA_SEL 0 becomes BOTTOM_OF_PIPE_TS / EVENT_INDEX 5
    // (the GFX ring's ME never completes the former; experiment 0016, run 40).
    bool cs_done_to_bottom_of_pipe = true;
    // Experiment 0038: DISPATCH_INDIRECT comes in two forms. On a compute queue (MEC) it carries
    // the argument address itself (address lo, address hi, initiator; 4 dwords); on the GFX ring
    // it carries an offset from the base set by SET_BASE index 1 (offset, initiator; 3 dwords)
    // (Mesa radv_cmd_buffer.c, radv_emit_dispatch_packets, TODO(verify) the line). The console's
    // compute IBs run on the BC-250's GFX ring, which reads the first form as the second. When
    // non-zero, this is the base the caller has set with SET_BASE index 1 in the prologue (a
    // multiple of 4 GiB): compute-form packets whose address lies in [base, base + 4 GiB) become
    // GFX form (offset = the low address dword, initiator, NOP), the others are dropped.
    std::uint64_t mec_indirect_base = 0;
};

// Draw and dispatch opcodes (the "work" packets), for staging.
bool is_draw_or_dispatch(std::uint8_t opcode);

// The CU-mask registers (HANDOFF F7): COMPUTE_STATIC_THREAD_MGMT_SE0-3 take the mask whole;
// SPI_SHADER_PGM_RSRC3_PS/VS/GS carry CU_EN in bits 15:0, RSRC3_HS in bits 31:16 on gfx10 (Mesa
// sid.h S_00B41C_CU_EN_GFX10; the console's tables load 0xffff0000 there and 0x0000ffff into
// PS/GS, experiment 0016). ANDs cu_mask into `value` when `mm` (register index, mm address / 4)
// is one of them; returns whether it is.
bool mask_cu_register(std::uint32_t mm, std::uint32_t &value, std::uint32_t cu_mask);
// DMA_DATA with a GDS source or destination, WRITE_DATA to GDS.
bool is_gds_access(const std::uint32_t *p, std::uint32_t len);

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
