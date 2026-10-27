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
    // span_listed: does any register of [first, first + count) fall in a listed range? A span
    // that touches none has the default verdict throughout: one test per range instead of one
    // per register (experiment 0061: SET_SH_REG packets of ~30 registers are 85% of a
    // second-level frame's 355,000 dwords). span_has: may a register of the span have verdict
    // `v`? Never a false "no"; "yes" for the default verdict.
    bool span_listed(std::uint32_t first, std::uint32_t count) const;
    bool span_has(std::uint32_t first, std::uint32_t count, Verdict v) const;

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
    std::uint64_t ring_ordered_waits = 0; // ... kept for the GPU (FilterOptions::keep_wait_offsets)
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
    std::uint64_t dma_sources = 0;      // DMA_DATA sources replaced (FilterOptions::dma_source)
    std::uint64_t dma_snapshot_bytes = 0;    // bytes copied by Device::submit (dma_snapshot_min)
    std::uint64_t dma_snapshot_overflow = 0; // sources left in place: the slot's snapshot buffer was full
    std::uint64_t dma_syncs = 0;        // CP DMA waits inserted before dispatches (Device::submit)
    std::uint64_t gpu_checks = 0;       // DISPATCH_INDIRECT checked by the CP (gpu_check_indirect)
    std::uint64_t gpu_check_unbased = 0; // the same without a known base: PFP_SYNC_ME only
    std::uint64_t gpu_check_skipped = 0; // NOP-ed instead: a COND_EXEC range grew past its count
    std::uint64_t gfx_only_drops = 0; // graphics-only packets NOP-ed on a compute ring (FilterOptions::compute_ring)
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
    // Experiment 0050: before the first dispatch that follows a DMA_DATA without CP_SYNC, a
    // zero-byte DMA_DATA with CP_SYNC (the CP waits for its DMA to finish). Device::submit; the
    // IB's own COND_EXEC counts grow around them (experiment 0052).
    bool dma_sync_before_dispatch = false;
    // Experiment 0050: a PFP_SYNC_ME before every DISPATCH_INDIRECT of any IB (as for the rebuilt
    // compute IBs of experiment 0039): the prefetch parser must not read arguments the GPU is
    // still writing. Device::submit; the IB's own COND_EXEC counts grow around them (ADR 0010
    // section A; an IB with one used to be left alone).
    bool pfp_sync_indirect = false;
    // Experiment 0052: the CP checks every DISPATCH_INDIRECT's group counts when it runs it
    // (bc5/indirect_check.hpp) and skips the dispatch if one exceeds gpu_check_max; a PFP_SYNC_ME
    // goes before each, as with pfp_sync_indirect. Device::submit; the IB's own COND_EXEC counts
    // grow by what is inserted in their ranges. The base of a rebuilt compute IB is mec_indirect_base.
    bool gpu_check_indirect = false;
    std::uint32_t gpu_check_max[3] = {1u << 20, 1u << 10, 1u << 10};
    std::uint32_t gpu_check_draw_max[2] = {1u << 22, 1024}; // experiment 0054: indirect draws
    // Experiment 0341: the product staircase (bc5/indirect_check.hpp ProductLimit), the argument
    // histogram and the shadow labels (bc5/shadow_labels.hpp) are switched on by the environment
    // in Device::open (BC5_DIRECT_GPU_CHECK_PRODUCT, BC5_DIRECT_ARGS_HISTOGRAM,
    // BC5_DIRECT_SHADOW_LABELS), not by fields here: this struct's layout is the host's ABI, and
    // the experiment's emulator keeps the host's objects as they were compiled.
    bool drop_draws = false;             // staging (ADR 0005 §5c): NOP every draw and dispatch
    // CONTEXT_CONTROL as RADV/radeonsi emit it (0x80000000 0x80000000: update the enables, load
    // and shadow nothing). The console's 0x91018003/0x80018003 asks the CP to load and shadow
    // register state through areas amdgpu never set up on gfx10 (experiment 0016).
    bool safe_context_control = true;
    // When set, every packet whose memory operand lies outside the mapped ranges is dropped
    // instead of faulting the GPU. Called with (address, bytes).
    std::function<bool(std::uint64_t, std::uint64_t)> mapped;
    // Experiment 0087: called for every passing DMA_DATA that reads memory (SRC_SEL 0 or 3, SAS 0)
    // of at least dma_source_min bytes, with (source address, bytes); a non-zero result replaces
    // the source in the filtered copy (the caller has copied the data there, e.g. at submission,
    // so that the title may rewrite its staging before the job runs). The returned range must be
    // mapped. Field layout: RPCSX rpcsx/gpu/Pipe.cpp ComputePipe::dmaData (e8ae148): control
    // dword 1 (SRC_SEL 30:29), source 2-3, destination 4-5, command dword 6 (BYTE_COUNT 20:0,
    // SAS 26).
    std::function<std::uint64_t(std::uint64_t, std::uint32_t)> dma_source;
    std::uint32_t dma_source_min = 4096;
    // Experiment 0122: when non-zero, Device::submit itself copies the source of every DMA_DATA
    // that reads at least this many bytes of memory into a snapshot buffer of the job's own slot
    // at submission and points the packet at the copy (dma_source above is then the device's).
    // The second title rewrites its rotating CPU staging before our jobs run (F146); the copy
    // keeps what it held when the title submitted. 0 = off.
    std::uint32_t dma_snapshot_min = 0;
    // Experiment 0124: Device::submit puts a GPU timestamp in front of the job (COPY_DATA from the
    // GPU clock, as the CP reaches it) and behind it (RELEASE_MEM BOTTOM_OF_PIPE_TS with DATA_SEL 3,
    // once all its work is done), in the job's scratch; SubmitResult::gpu_start / gpu_end carry them
    // once the job is finished. Mesa src/amd/common/sid.h (0866ae7): PKT3_COPY_DATA 0x40,
    // COPY_DATA_TIMESTAMP 9, COPY_DATA_DST_MEM 5, COPY_DATA_COUNT_SEL bit 16, COPY_DATA_WR_CONFIRM
    // bit 20; PKT3_RELEASE_MEM 0x49, EOP_DATA_SEL_TIMESTAMP 3 at bit 29; radv_query.c writes its
    // timestamps with the same COPY_DATA.
    bool job_timestamps = false;
    // Opcodes to drop in addition to the table (experiments).
    std::vector<std::uint8_t> extra_drop;
    // Dword offsets of packets to drop, decided by the caller from data the filter cannot see
    // (e.g. an indirect draw whose argument buffer holds an absurd count). Sorted or not.
    std::vector<std::uint32_t> drop_offsets;
    // WAIT_REG_MEM[64] passes only when its label was written earlier in the same IB (by a
    // passing WRITE_DATA/RELEASE_MEM/EVENT_WRITE_EOP/ATOMIC_MEM); other waits are dropped and
    // left to the host. A wait the GPU can never satisfy ends in the kernel's GPU timeout.
    bool self_waits_only = true;
    // Experiment 0055: dword offsets of WAIT_REG_MEM[64] packets that pass although no earlier packet
    // of the IB writes their label: the caller knows a job already on the ring ahead of this one
    // will write a value that satisfies them.
    std::vector<std::uint32_t> keep_wait_offsets;
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
    // ADR 0009: the job goes to a kernel compute ring (the MEC). The packets of
    // compute_ring_refusal() are NOP-ed (FilterStats::gfx_only_drops; a caller sends IBs holding
    // them to the GFX ring instead), and RELEASE_MEM keeps CS_DONE (cs_done_to_bottom_of_pipe is
    // a GFX-ring workaround). Device::submit sets it for its compute-ring jobs.
    bool compute_ring = false;
};

// ADR 0009: a packet that has no place on a compute ring: CONTEXT_CONTROL (run 43 hung the MEC
// with it, experiment 0127; IGT lib/amdgpu/compute_utils/amd_dispatch_helpers.c emits it for
// AMDGPU_HW_IP_GFX only), CLEAR_STATE, SET_CONTEXT_REG, LOAD_CONTEXT_REG[_INDEX], the draws,
// INDEX_BASE / INDEX_BUFFER_SIZE / INDEX_TYPE, NUM_INSTANCES, PFP_SYNC_ME (there is no PFP), and
// DISPATCH_INDIRECT in its GFX form (3 dwords; the MEC's form carries the address, 4 dwords).
// TODO(verify): beyond CONTEXT_CONTROL the set is what RADV's compute queue never emits, refused
// rather than tried.
bool is_graphics_only(std::uint8_t opcode, std::uint32_t len);
// ADR 0009: why `ib` should not go to a compute ring, nullptr when it may: a graphics-only packet
// (is_graphics_only), or a dispatch with PARTIAL_TG_EN set and USE_THREAD_DIMENSIONS clear, which
// the gfx1013 MEC runs with workgroups missing (mesa#16054; COMPUTE_DISPATCH_INITIATOR bits 1 and
// 5, Mesa src/amd/registers/gfx10.json, 0866ae7). INDIRECT_BUFFER targets are followed (up to
// three levels) when `mapped` accepts their range; an unmapped target is not refused (the filter
// NOPs the packet). Experiment 0290: a DISPATCH_INDIRECT of either form is refused as well until
// the CP's argument check (indirect_check) is verified on the MEC — on the GFX ring the check skips
// a garbage triple, on a compute ring it ran unchecked and never ended (F332).
const char *compute_ring_refusal(std::span<const std::uint32_t> ib,
                                 const std::function<bool(std::uint64_t, std::uint64_t)> &mapped = {});

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
