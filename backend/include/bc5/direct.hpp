// SPDX-License-Identifier: GPL-2.0-only
// Direct submission (ADR 0005): the game's memory mapped 1:1 as userptr BOs, its command buffers
// copied through the policy filter into a scratch IB and submitted on the GFX ring with a fence.
// Only built with BC5_WITH_AMDGPU. Nothing here submits unless the host calls submit(); hosts
// keep that behind an explicit switch (hard rule 5).
#pragma once

#include "bc5/cu_tables.hpp"
#include "bc5/policy.hpp"
#include "bc5/state_stack.hpp"

#include <cstdint>
#include <memory>
#include <span>
#include <string>
#include <vector>

namespace bc5::direct {

struct SubmitResult {
    bool ok = false;
    int rc = 0;            // libdrm / ioctl return code when not ok
    bool timed_out = false; // fence did not signal within the timeout
    double submit_ms = 0;   // submit + fence wall clock
    // The parts of a submission (experiment 0016, run 80: a constant ~17 ms whatever the IB):
    // filtering and scratch layout, BO list creation, the CS ioctl, the fence wait.
    double prepare_ms = 0, list_ms = 0, cs_ms = 0, fence_ms = 0;
    // BOs on this submission's list, and whether it was the short list (Device::set_short_lists).
    std::uint32_t bo_count = 0;
    bool short_list = false;
    std::uint64_t seq_no = 0; // sequence number the kernel assigned (0 = none)
    // Device::set_async: the job was queued and not waited for; `ok` then only says the kernel
    // took it. Device::finish(seq_no, slot) waits and completes the result.
    bool pending = false;
    std::uint32_t slot = 0;
    // After a timeout: the last GPU VM fault of this process (AMDGPU_INFO_GPUVM_FAULT; page
    // address, GCVM_L2_PROTECTION_FAULT_STATUS), 0 when the kernel has none to report.
    std::uint64_t fault_addr = 0;
    std::uint32_t fault_status = 0;
    policy::FilterStats filter;
    // Context-state stack emulation (Device::set_state_stack): pushes, pops and the registers
    // the pops restored in this IB.
    state_stack::Stats state_stack;
    // CU-mask overrides appended after register loads (FilterOptions::cu_mask != 0xffffffff).
    cu_tables::Stats cu_tables;
    // Dword offsets (in the caller's IB) of the type-3 packets that reached the GPU as
    // themselves, i.e. passed or rewritten, not NOP-ed by the filter. A host that also emulates
    // the stream (a soft CP) uses this to skip the memory side effects the GPU already produced.
    std::vector<std::uint32_t> executed_offsets;
    // INDIRECT_BUFFER targets reached from the IB (the console's compute rings are rings of
    // INDIRECT_BUFFER packets): each was copied into the scratch behind the IB, filtered like
    // it, and the packet's address rewritten to the copy — so the filter sees every packet the
    // CP will execute. Per target: the guest address, its length and its executed offsets.
    struct Nested {
        std::uint64_t cpu_addr = 0;
        std::uint32_t num_dwords = 0;
        std::vector<std::uint32_t> executed_offsets;
    };
    std::vector<Nested> nested;
};

struct Mapping {
    std::uint64_t va = 0;
    std::uint64_t size = 0;
    bool readonly = false; // GPU read/execute only (r-- / r-x guest pages: shader code, rodata)
    bool shared = false;   // a mapping of an imported memfd range (map_shared), not a userptr BO
};

// Diagnostic knobs (experiment 0016 bisection); the defaults are the intended configuration.
struct OpenOptions {
    bool deduplicate_device = false; // true: plain amdgpu_device_initialize (shares a device already open in the process)
    bool legacy_scratch_va = false;
    // GDS bytes to allocate (AMDGPU_GEM_DOMAIN_GDS) and put on every BO list: the kernel then
    // programs the VMID's GDS base/size for the submission, so the console's GDS counters
    // (DMA_DATA/WRITE_DATA and shader ds_* instructions) have somewhere to live. 0 = none.
    std::uint32_t gds_kib = 0;
    // Ordered-append counters (AMDGPU_GEM_DOMAIN_OA, 16 per compute partition on the BC-250) and
    // global wave sync resources (AMDGPU_GEM_DOMAIN_GWS, 64): the shaders' ds_ordered_count and
    // GWS instructions need a partition too; with GDS alone the gfx queue's shaders hung
    // (experiment 0016, runs 49–50). 0 = none.
    std::uint32_t oa_count = 0;
    std::uint32_t gws_count = 0;
    // 64 KiB GDS shadow in GTT at a fixed GPU VA (on every BO list); see
    // policy::FilterOptions::gds_shadow_va. false = none.
    bool gds_shadow = false;  // true: scratch VA from libdrm's allocator instead of the fixed 16 TiB
};

class Device {
public:
    // Opens a render node; nullptr on failure (message on stderr).
    static std::unique_ptr<Device> open(const std::string &node, const OpenOptions &opts = {});
    ~Device();
    Device(const Device &) = delete;
    Device &operator=(const Device &) = delete;

    // Maps [cpu_va, cpu_va + size) — page-aligned host memory of this process — into the GPU at
    // the same address. Overlapping or duplicate ranges are rejected.
    bool map_userptr(std::uint64_t cpu_va, std::uint64_t size);
    bool unmap_userptr(std::uint64_t cpu_va);
    // readonly: AMDGPU_GEM_USERPTR_READONLY (raw ioctl; libdrm's helper has no flag) and a VA
    // mapping without WRITEABLE — the only way to give the GPU the game's r-x/r-- pages.
    bool map_userptr(std::uint64_t cpu_va, std::uint64_t size, bool readonly);
    // ADR 0006: a range of a sealed memfd (F_SEAL_SHRINK) as GPU memory without userptr —
    // udmabuf turns [offset, offset + size) into a dma-buf, amdgpu imports it. The pages are
    // pinned from here on, and a CS that lists the BO walks nothing. Returns an id (> 0), 0 on
    // failure. size is limited by the udmabuf module (size_limit_mb, 64 by default).
    std::uint32_t import_memfd(int memfd, std::uint64_t offset, std::uint64_t size);
    // Maps [bo_offset, bo_offset + size) of an imported range at gpu_va (all page aligned). One
    // range may be mapped at several addresses (the guest's aliases of one physical range).
    bool map_shared(std::uint32_t id, std::uint64_t bo_offset, std::uint64_t size, std::uint64_t gpu_va);
    bool unmap_shared(std::uint64_t gpu_va);
    // Unmaps an imported range everywhere and frees its BO (experiment 0022: small imports are
    // replaced by one merged import).
    bool free_shared(std::uint32_t id);
    // GPU VA of the GDS shadow buffer, 0 when none was requested or allocated.
    std::uint64_t gds_shadow_va() const;
    // CPU view of the GDS shadow (64 KiB), nullptr when none. Also the landing buffer for a GDS
    // snapshot (a host-built DMA_DATA GDS -> shadow, experiment 0016).
    volatile std::uint32_t *gds_shadow_cpu() const;
    std::vector<Mapping> mappings() const;

    // Filters `ib` into a scratch IB and submits it on the GFX ring with every mapping in the BO
    // list; waits for the fence up to `timeout_ns`. After a timeout the device refuses further
    // submits (a wedged ring is not retried; ADR 0005 §3).
    // with_gds: put the GDS/OA/GWS allocations (OpenOptions) on this submission's BO list — the
    // kernel programs the VMID's partitions per job, so a compute IB can have them while a gfx
    // DCB, whose shaders hang with any partition present, does not (experiment 0016, runs 49–52).
    SubmitResult submit(std::span<const std::uint32_t> ib, const policy::FilterOptions &opt,
                        std::uint64_t timeout_ns, bool with_gds = true);

    bool wedged() const { return wedged_; }
    // Experiment 0024: submit() returns once the kernel has queued the job, so that the host
    // can prepare the next IB while the GPU runs this one. Each job in flight keeps its own
    // scratch buffer (16 of them, used in turn); the host calls finish() for every pending
    // result, in order, and keeps fewer than 16 in flight.
    void set_async(bool v) { async_ = v; }
    bool async() const { return async_; }
    SubmitResult finish(std::uint64_t seq_no, std::uint32_t slot, std::uint64_t timeout_ns);
    std::uint64_t submits() const { return submits_; }

    // Staging knob: when false, submits carry only the scratch IB in their BO list (the userptr
    // mappings stay mapped but are not validated per submit). Default true.
    void set_include_mappings(bool v) { include_mappings_ = v; }
    // Emulate the console CP's context-state stack (CLEAR_STATE cmd 1 / cmd 2 around the
    // driver's internal draws; bc5/state_stack.hpp) for the IBs given to submit(): a pop becomes
    // SET_CONTEXT_REG packets restoring what the IBs set before the push. Needs
    // FilterOptions::mapped (the register tables are read from this process's memory). Off by
    // default.
    void set_state_stack(bool v) { state_stack_ = v; }
    // An IB (with its nested IBs) that holds no draw and no dispatch reaches guest memory only
    // through the operands of its packets. With short lists on, such a submission lists only the
    // userptr BOs those operands lie in, not every mapping: the kernel revalidates each listed
    // userptr BO's pages on every CS, which is what a submission costs (experiment 0016, run
    // 80: 28 ms with 5.8 GB listed). The other mappings stay in the VM; they are revalidated by
    // the next submission that draws. Needs FilterOptions::mapped. Off by default.
    void set_short_lists(bool v) { short_lists_ = v; }
    // Every IB ends with a zero-byte DMA_DATA carrying CP_SYNC: the CP then waits for all CP DMA
    // operations to finish before the IB ends. amdgpu does not wait for them, a fence signals
    // with a copy still running (Mesa ends its IBs the same way: radeonsi
    // si_cp_dma_wait_for_idle / si_gfx_cs.c, RADV radv_cp_dma_wait_for_idle, "because the kernel
    // doesn't wait for it"). The console stream leaves 12 MB copies without CP_SYNC behind
    // (experiment 0017: video frames; the machine went down with the next IB). On by default.
    void set_dma_idle(bool v) { dma_idle_ = v; }

private:
    Device() = default;
    struct Impl;
    std::unique_ptr<Impl> impl_;
    bool wedged_ = false;
    bool async_ = false;
    bool include_mappings_ = true;
    bool state_stack_ = false;
    bool short_lists_ = false;
    bool dma_idle_ = true;
    std::uint64_t submits_ = 0;
};

} // namespace bc5::direct
