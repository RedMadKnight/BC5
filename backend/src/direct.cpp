// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/direct.hpp"
#include "bc5/host_indirect.hpp"
#include "bc5/ib_split.hpp"
#include "bc5/indirect_check.hpp"
#include "bc5/shadow_labels.hpp"

#include <amdgpu.h>
#include <amdgpu_drm.h>
#include <fcntl.h>
#include <linux/udmabuf.h>
#include <sys/ioctl.h>
#include <xf86drm.h>
#include <unistd.h>

#include <algorithm>
#include <iterator>
#include <atomic>
#include <cerrno>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <cstdlib>
#include <map>
#include <set>

namespace bc5::direct {

namespace {

double now_ms() {
    return std::chrono::duration<double, std::milli>(
               std::chrono::steady_clock::now().time_since_epoch())
        .count();
}

struct UserptrBo {
    std::uint64_t va = 0;
    std::uint64_t size = 0;
    amdgpu_bo_handle bo = nullptr;
    bool readonly = false;
};

// ADR 0006: an imported memfd range and its mappings.
struct SharedBo {
    std::uint32_t id = 0;
    amdgpu_bo_handle bo = nullptr;
    std::uint64_t size = 0;
    std::uint32_t maps = 0; // experiment 0170: how many shared mappings lie on this BO
};
struct SharedMap {
    std::uint64_t va = 0;
    std::uint64_t size = 0;
    std::uint64_t bo_offset = 0;
    std::uint32_t id = 0;
    amdgpu_bo_handle bo = nullptr;
};

struct ScratchBo {
    amdgpu_bo_handle bo = nullptr;
    amdgpu_va_handle va_handle = nullptr; // only with legacy_scratch_va
    std::uint64_t va = 0;
    std::uint64_t size = 0;
    void *cpu = nullptr;
};

} // namespace

// PKT3(PFP_SYNC_ME, 0, 0) (Mesa sid.h PKT3_PFP_SYNC_ME 0x42).
constexpr std::uint32_t kPfpSyncMe = 0xC0004200u;

struct Device::Impl {
    int fd = -1;
    amdgpu_device_handle dev = nullptr;
    amdgpu_context_handle ctx = nullptr;
    std::vector<UserptrBo> userptrs;
    std::vector<SharedBo> shared;
    std::vector<SharedMap> shared_maps;
    struct Alias {
        std::uint64_t va = 0; // as passed to the kernel (sign-extended from 2^47 up)
        std::uint64_t size = 0;
        std::uint64_t bo_offset = 0;
        amdgpu_bo_handle bo = nullptr;
    };
    std::vector<Alias> aliases; // Device::map_alias (experiment 0056)
    // Experiment 0102: VA windows mapped as PRT (Device::map_prt_window). Inside one, mappings are
    // made with AMDGPU_VA_OP_REPLACE over the PRT pages and undone by replacing them with PRT pages
    // again, as RADV binds and unbinds sparse memory (Mesa src/amd/vulkan/winsys/amdgpu/
    // radv_amdgpu_bo.c, radv_amdgpu_virtual_bo_map/_unmap, 0866ae7).
    std::vector<std::pair<std::uint64_t, std::uint64_t>> prt_windows; // (va, size)
    bool in_prt(std::uint64_t va, std::uint64_t size) const {
        for (const auto &[w, n] : prt_windows)
            if (va >= w && va + size <= w + n) return true;
        return false;
    }
    int va_map(amdgpu_bo_handle bo, std::uint64_t offset, std::uint64_t size, std::uint64_t va, std::uint64_t flags) {
        return amdgpu_bo_va_op_raw(dev, bo, offset, size, va, flags, in_prt(va, size) ? AMDGPU_VA_OP_REPLACE : AMDGPU_VA_OP_MAP);
    }
    int va_unmap(amdgpu_bo_handle bo, std::uint64_t offset, std::uint64_t size, std::uint64_t va) {
        if (in_prt(va, size)) return amdgpu_bo_va_op_raw(dev, nullptr, 0, size, va, AMDGPU_VM_PAGE_PRT, AMDGPU_VA_OP_REPLACE);
        return amdgpu_bo_va_op_raw(dev, bo, offset, size, va, 0, AMDGPU_VA_OP_UNMAP);
    }
    void drop_aliases_of(amdgpu_bo_handle bo) {
        for (auto a = aliases.begin(); a != aliases.end();) {
            if (a->bo == bo) {
                amdgpu_bo_va_op_raw(dev, a->bo, a->bo_offset, a->size, a->va, 0, AMDGPU_VA_OP_UNMAP);
                a = aliases.erase(a);
            } else {
                ++a;
            }
        }
    }
    // Experiment 0027: the IB is assembled and scanned in this cached buffer and copied into the
    // scratch once; every read of the uncached scratch cost more than the walk itself.
    std::vector<std::uint32_t> image;
    // Experiment 0341: the three experimental switches read from the environment in
    // Device::open (the host's FilterOptions / OpenOptions fields win when set), the dispatch
    // argument histogram (arm 1), the shadow-label sums (arm 2) and the summary at close.
    bool env_product = false, env_histogram = false, env_shadow = false, bo_journal = false;
    // Experiment 0380: BC5_DIRECT_GPU_CHECK_ZERO — the CP check also skips a dispatch whose x, y or z
    // argument is 0 (indirect_check zero_dims). Unset: off.
    bool env_zero = false;
    std::uint64_t zero_sum = 0;
    // Experiment 0380: BC5_DIRECT_FORCE_START_000 — every indirect dispatch the check pass sees gets
    // FORCE_START_AT_000 in its initiator (indirect_check force_start), as RADV sets it. Unset: off.
    bool env_force_start = false;
    // Experiment 0380 (F555): BC5_DIRECT_GPU_CHECK_YZ — the CP check's y and z limits for indirect
    // dispatches lowered ("1" = 256:64, or "<y>[:<z>]"). Unset: the host's limits as they are.
    bool env_yz = false;
    // Experiment 0380 (F558-F560): BC5_DIRECT_REBASE_DISPATCH — each checked GFX-form DISPATCH_INDIRECT
    // gets its SET_BASE index 1 again right before it (indirect_check rebase). Unset: off.
    bool env_rebase = false;
    std::uint64_t rebased_sum = 0, rebased_ib_sum = 0;
    // Experiment 0380 (F566): BC5_DIRECT_ARGS_COPY — each checked GFX-form DISPATCH_INDIRECT runs from the
    // CP's own copy of its arguments, the copy the check reads (indirect_check args_copy). Unset: off.
    bool env_args_copy = false;
    std::uint64_t args_copied_sum = 0;
    // Experiment 0380 (F570): BC5_DIRECT_ARGS_WB — "first" (the first DISPATCH_INDIRECT after an INDEX_BASE) or
    // "all": a GL2 write-back (ACQUIRE_MEM GL2_WB) before the check of a checked indirect dispatch. Unset: off.
    indirect_check::ArgsWb env_args_wb = indirect_check::ArgsWb::off;
    std::uint64_t args_wb_sum = 0;
    indirect_check::YzLimit yz;
    std::uint64_t start_forced_sum = 0, start_seen_sum = 0;
    // Experiment 0346: BC5_DIRECT_HOST_INDIRECT — a GFX-form DISPATCH_INDIRECT without a SET_BASE of its type
    // in its own IB is resolved and verified by the host at filter time (bc5/host_indirect.hpp): rewritten
    // to the page the host read, or NOP-ed. "1" or "learn": the window for a base of 0 learned from the
    // title's own SET_BASEs; "learn:<hex>" with that value until one is seen; "<hex>" fixed. Unset: off.
    bool env_host_indirect = false;
    std::uint64_t hi_window_fixed = 0, hi_window_learned = 0;
    host_indirect::Register hi_reg; // the CP's one base-1 register as the GFX ring's jobs leave it (third version)
    host_indirect::Stats hi_sum;
    // Experiment 0349: a job's executed IB longer than this is cut into up to four IBs of one submit
    // (bc5/ib_split.hpp); the kernel refuses an IB over 0xfffff dwords (F421). BC5_DIRECT_IB_MAX_DW lowers it.
    std::size_t ib_max_dw = ib_split::kDefaultMaxDwords;
    std::uint64_t split_jobs = 0, split_pieces = 0, split_fallback = 0, split_failed = 0;
    std::set<std::uint64_t> hi_programs;
    indirect_check::ProductLimit product;
    std::map<std::uint32_t, std::uint64_t> hist; // key: the log2 classes of x, y, z, 8 bits each
    std::uint64_t hist_n = 0, hist_printed = 0, hist_stair = 0, hist_dim = 0;
    std::uint64_t shadow_jobs = 0, shadow_labels_sum = 0, shadow_writes_sum = 0, shadow_waits_sum = 0,
                  shadow_overflow_sum = 0, shadow_failed_sum = 0, product_sum = 0;
    static constexpr std::uint32_t kShadowSlots = 64; // per job: 512 bytes of the scratch
    void bo_line(const char *what, std::uint64_t va, std::uint64_t size) const {
        if (!bo_journal) return;
        std::fprintf(stderr, "bc5-direct: bo %s va 0x%llx size 0x%llx\n", what,
                     static_cast<unsigned long long>(va), static_cast<unsigned long long>(size));
    }
    static std::uint32_t log2_class(std::uint32_t v) {
        if (v == 0) return 0xff;
        std::uint32_t c = 0;
        while (v > 1) { v >>= 1; c++; }
        return c;
    }
    // The counts of every GFX-form DISPATCH_INDIRECT with a known base, read from the mapped
    // argument memory as the host sees it now (stale for arguments the GPU writes later in the
    // frame: a histogram, not a verdict).
    void histogram(const std::vector<std::uint32_t> &ib, std::uint64_t base_in,
                   const std::function<bool(std::uint64_t, std::uint64_t)> &mapped,
                   const policy::FilterOptions &fopt) {
        if (!mapped) return;
        std::uint64_t base = base_in;
        for (std::size_t i = 0; i < ib.size();) {
            const std::uint32_t h = ib[i];
            std::size_t len = 1;
            if (h >> 30 == 3 || h >> 30 == 0) {
                const std::uint32_t count = (h >> 16) & 0x3fff;
                len = count == 0x3fff ? 1 : count + 2;
            }
            if (i + len > ib.size()) break;
            const std::uint32_t op = (h >> 8) & 0xff;
            if (h >> 30 == 3 && op == 0x11 && len >= 4 && (ib[i + 1] & 0xfu) == 1) {
                base = (static_cast<std::uint64_t>(ib[i + 2]) & ~3ull) |
                       (static_cast<std::uint64_t>(ib[i + 3] & 0xffffu) << 32);
            }
            if (h >> 30 == 3 && op == 0x16 && len == 3 && base != 0) {
                const std::uint64_t a = base + ib[i + 1];
                if (mapped(a, 12)) {
                    std::uint32_t v[3];
                    std::memcpy(v, reinterpret_cast<const void *>(a), sizeof(v));
                    const std::uint32_t key = (log2_class(v[0]) << 16) | (log2_class(v[1]) << 8) | log2_class(v[2]);
                    hist[key]++;
                    hist_n++;
                    if ((v[1] > product.yz_min || v[2] > product.yz_min) && v[0] > product.x_limit) hist_stair++;
                    if (v[0] > fopt.gpu_check_max[0] || v[1] > fopt.gpu_check_max[1] || v[2] > fopt.gpu_check_max[2]) hist_dim++;
                }
            }
            i += len;
        }
        if (hist_n - hist_printed >= 500000) hist_print("periodic");
    }
    void hist_print(const char *when) {
        hist_printed = hist_n;
        std::vector<std::pair<std::uint64_t, std::uint32_t>> top;
        for (const auto &[k, n] : hist) top.emplace_back(n, k);
        std::sort(top.begin(), top.end(), [](const auto &a, const auto &b) { return a.first > b.first; });
        std::string line;
        char buf[96];
        for (std::size_t k = 0; k < top.size() && k < 24; ++k) {
            auto cls = [](std::uint32_t c) -> std::string { return c == 0xff ? "0" : "2^" + std::to_string(c); };
            const std::uint32_t key = top[k].second;
            std::snprintf(buf, sizeof(buf), "%s%s.%s.%s:%llu", k ? " " : "", cls(key >> 16).c_str(),
                          cls((key >> 8) & 0xff).c_str(), cls(key & 0xff).c_str(),
                          static_cast<unsigned long long>(top[k].first));
            line += buf;
        }
        std::fprintf(stderr,
                     "bc5-direct: args histogram (%s): %llu sampled, %llu classes; the staircase (y or z > %u with x > %u) would refuse %llu, the per-dimension limits %llu; top x.y.z classes: %s\n",
                     when, static_cast<unsigned long long>(hist_n), static_cast<unsigned long long>(hist.size()),
                     product.yz_min, product.x_limit, static_cast<unsigned long long>(hist_stair),
                     static_cast<unsigned long long>(hist_dim), line.c_str());
    }
    void summary(const char *when = "at close") { // also every 2000 shadowed jobs: a killed emulator never gets here
        if (hist_n != 0 && when[0] == 'a') hist_print("close");
        if (shadow_jobs != 0 || product_sum != 0 || shadow_failed_sum != 0)
            std::fprintf(stderr,
                         "bc5-direct: experiment 0341 %s: shadow labels in %llu jobs: %llu labels, %llu writes copied, %llu waits redirected, %llu labels without a slot, %llu IBs left alone (COND_EXEC); product staircase on %llu dispatches\n",
                         when, static_cast<unsigned long long>(shadow_jobs), static_cast<unsigned long long>(shadow_labels_sum),
                         static_cast<unsigned long long>(shadow_writes_sum), static_cast<unsigned long long>(shadow_waits_sum),
                         static_cast<unsigned long long>(shadow_overflow_sum), static_cast<unsigned long long>(shadow_failed_sum),
                         static_cast<unsigned long long>(product_sum));
        if (env_zero) // experiment 0380: how many the CP skipped is not seen by the host
            std::fprintf(stderr, "bc5-direct: experiment 0380 %s: zero-dimension guard on %llu checked dispatches\n",
                         when, static_cast<unsigned long long>(zero_sum));
        if (env_args_wb != indirect_check::ArgsWb::off) // experiment 0380 (F570)
            std::fprintf(stderr, "bc5-direct: experiment 0380 %s: GL2 write-back before %llu checked indirect dispatches\n",
                         when, static_cast<unsigned long long>(args_wb_sum));
        if (env_args_copy) // experiment 0380 (F566)
            std::fprintf(stderr, "bc5-direct: experiment 0380 %s: %llu checked indirect dispatches ran from the CP's copy of their arguments\n",
                         when, static_cast<unsigned long long>(args_copied_sum));
        if (env_rebase) // experiment 0380
            std::fprintf(stderr, "bc5-direct: experiment 0380 %s: SET_BASE re-emitted before %llu checked indirect dispatches, %llu of them the first after an INDEX_BASE\n",
                         when, static_cast<unsigned long long>(rebased_sum), static_cast<unsigned long long>(rebased_ib_sum));
        if (env_force_start) // experiment 0380
            std::fprintf(stderr, "bc5-direct: experiment 0380 %s: FORCE_START_AT_000 set on %llu of %llu indirect dispatches (the rest had it)\n",
                         when, static_cast<unsigned long long>(start_forced_sum), static_cast<unsigned long long>(start_seen_sum));
        if (env_host_indirect) // experiment 0346
            std::fprintf(stderr,
                         "bc5-direct: experiment 0346 %s: dispatches seen by the host: %u left (the register non-zero) + %u left (never set), after the title's zeroing %u rewritten to a verified page, dropped %u (no candidate) + %u (not a real mapping) + %u (unreadable) + %u (counts), %u NOP-ed on a COND_EXEC overflow; window 0x%llx; %zu programs\n",
                         when, hi_sum.left_nonzero, hi_sum.left_never_set, hi_sum.rewritten, hi_sum.dropped_no_candidate, hi_sum.dropped_unmapped, hi_sum.dropped_unreadable,
                         hi_sum.dropped_insane, hi_sum.nop_on_overflow,
                         static_cast<unsigned long long>(hi_window_learned != 0 ? hi_window_learned : hi_window_fixed), hi_programs.size());
    }
    // Experiment 0064: the filtered main IB, kept between submissions so that its memory is not
    // allocated and zeroed again for every buffer (up to ~470 KB each, four of them a frame).
    std::vector<std::uint32_t> main_buf;
    std::uint32_t next_shared_id = 1;
    int udmabuf_fd = -1;
    // The BO list of a submission with draws names every mapping; it is kept between
    // submissions while the set of mapped BOs stays the same (experiment 0022).
    std::uint64_t list_gen = 0;
    amdgpu_bo_list_handle full_list = nullptr;
    std::uint64_t full_list_gen = 0;
    bool full_list_gds = false;
    std::uint32_t full_list_count = 0;
    amdgpu_bo_handle gds = nullptr; // OpenOptions::gds_kib
    amdgpu_bo_handle oa = nullptr;  // OpenOptions::oa_count
    amdgpu_bo_handle gws = nullptr; // OpenOptions::gws_count
    amdgpu_bo_handle shadow = nullptr; // OpenOptions::gds_shadow, 64 KiB at kShadowVa
    // Experiment 0380 (F574): BC5_DIRECT_ARGS_COPY's slot, 4 KiB at a low GPU VA (libdrm's 32-bit range):
    // the job scratch at 16 TiB is not where an indirect fetch through SET_BASE reads (F572)
    amdgpu_bo_handle args_slot = nullptr;
    amdgpu_va_handle args_slot_vah = nullptr;
    std::uint64_t args_slot_va = 0;
    void *shadow_cpu = nullptr;
    state_stack::Tracker tracker; // Device::set_state_stack
    static constexpr std::uint64_t kShadowVa = 0x1000'0400'0000ull; // 64 MiB above the scratch
    std::mutex mutex;
    // Device::sorted_mappings: the sorted list and the list_gen it was built at.
    std::shared_ptr<const std::vector<Mapping>> sorted;
    std::uint64_t sorted_gen = ~0ull;
    // Experiment 0170: shared_maps is kept sorted by address (map_shared inserts in place,
    // unmap_shared finds by binary search), and the direct mapper never maps two pieces over the
    // same addresses, so the short BO list finds the mappings around an operand by binary search
    // instead of walking all ~17,000 of them for every operand of every submission. Whether the
    // pieces really are disjoint is checked once per change of the list (disjoint_gen); if they
    // are not, the old walk is used.
    std::uint64_t disjoint_gen = ~0ull;
    bool disjoint = false;
    bool shared_disjoint_locked() {
        if (disjoint_gen != list_gen) {
            disjoint = true;
            for (std::size_t i = 1; i < shared_maps.size() && disjoint; ++i)
                disjoint = shared_maps[i - 1].va + shared_maps[i - 1].size <= shared_maps[i].va;
            disjoint_gen = list_gen;
        }
        return disjoint;
    }
    SharedBo *shared_bo_locked(std::uint32_t id) {
        for (auto &x : shared) {
            if (x.id == id) return &x;
        }
        return nullptr;
    }

    // The scratch IB lives at a fixed GPU VA of 16 TiB: inside the 48-bit range the CP can
    // address (an IB address above 2^48 is truncated by the CP — the kernel-half "high VA" range
    // hung the BC-250, experiment 0016), above every guest window a track-B host maps 1:1
    // (< 1 TiB) and away from libdrm's low-range allocator (0x100000000+).
    static constexpr std::uint64_t kScratchVa = 0x1000'0000'0000ull;
    OpenOptions opts;

    // One scratch buffer per job in flight (Device::set_async); synchronous submission uses
    // slot 0 only. Each slot has its own VA, 4 GiB apart. Experiment 0045: 64, so that the host
    // can let more than a dozen jobs fly (BC5_DIRECT_MAX_IN_FLIGHT); a slot grows to the largest
    // IB it carried, a few hundred KiB.
    static constexpr int kSlots = 128;
    // ADR 0009: slots [0, kGfxSlots) carry GFX-ring jobs, then kCompSlots for each compute ring.
    // Each pool is used in turn, so a slot is given back in the order its ring completes jobs; one
    // shared round would wait for a ring that has fallen behind (-EBUSY).
    static constexpr int kGfxSlots = 32;
    static constexpr int kCompSlots = (kSlots - kGfxSlots) / kComputeRings;
    static constexpr int pool_first(int ring) { return ring == kGfxRing ? 0 : kGfxSlots + ring * kCompSlots; }
    static constexpr int pool_size(int ring) { return ring == kGfxRing ? kGfxSlots : kCompSlots; }
    ScratchBo slots[kSlots];
    std::atomic<int> slot_ring[kSlots] = {}; // the ring of the slot's last job (kGfxRing or n)
    std::uint32_t ts_off[kSlots] = {}; // experiment 0124: dword offset of the job's timestamps, 0 = none
    // The two timestamps of the slot's last job (FilterOptions::job_timestamps).
    void read_job_ts(std::uint32_t slot, SubmitResult &r) const {
        if (slot >= static_cast<std::uint32_t>(kSlots) || ts_off[slot] == 0 || slots[slot].cpu == nullptr) return;
        const auto *t = reinterpret_cast<const volatile std::uint64_t *>(static_cast<const std::uint32_t *>(slots[slot].cpu) + ts_off[slot]);
        r.gpu_start = t[0];
        r.gpu_end = t[1];
    }
    // Experiment 0122 (FilterOptions::dma_snapshot_min): one ring of copies of the jobs' DMA_DATA
    // sources, 128 MiB above the scratch, allocated on first use. A copy never overwrites the copies
    // of a job still in flight (snap_spans: each job's ranges with its slot and sequence number);
    // when it would, the source is left in place. One buffer, always on the BO list: a buffer per
    // slot (runs 507-512) put up to 64 more buffers on every submission's list, 1.5 ms of CS ioctl
    // time a frame in the second title's menu.
    static constexpr std::uint64_t kSnapRingBytes = 64ull << 20;
    static constexpr std::uint64_t kSnapRingVa = kScratchVa + (128ull << 20);
    struct SnapSpan {
        std::uint64_t start = 0, end = 0;
        int slot = 0;
        std::uint64_t seq = 0;
    };
    ScratchBo snap_ring;
    ScratchBo code; // experiment 0137 (Device::code_area)
    std::uint64_t snap_head = 0;
    std::vector<SnapSpan> snap_spans;                         // committed jobs' copies, oldest first
    std::vector<std::pair<std::uint64_t, std::uint64_t>> snap_job; // this submission's copies

    bool snap_in_flight(const SnapSpan &x) const {
        return x.slot >= 0 && x.slot < kSlots && slot_seq[x.slot].load() == x.seq && x.seq != 0;
    }
    // A copy of [a, a + bytes) in the ring, keeping the low eight address bits (the DMA reads the
    // copy as it would have read the source); 0 when it does not fit now.
    std::uint64_t snapshot(std::uint64_t a, std::uint32_t bytes, policy::FilterStats &stats) {
        ScratchBo &s = snap_ring;
        if (s.bo == nullptr) {
            amdgpu_bo_alloc_request req{};
            req.alloc_size = kSnapRingBytes;
            req.phys_alignment = 4096;
            req.preferred_heap = AMDGPU_GEM_DOMAIN_GTT;
            // Write-combined for the CPU: the copies are written once, in order, never read back.
            req.flags = AMDGPU_GEM_CREATE_CPU_GTT_USWC;
            if (amdgpu_bo_alloc(dev, &req, &s.bo) != 0) return 0;
            s.va = kSnapRingVa;
            // The default (cached) GPU mapping, as the title's own staging has: the DMA reads the
            // copy where it would have read the source, after the same cache invalidations.
            const std::uint64_t flags = AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_WRITEABLE;
            if (amdgpu_bo_va_op_raw(dev, s.bo, 0, kSnapRingBytes, s.va, flags, AMDGPU_VA_OP_MAP) != 0) {
                amdgpu_bo_free(s.bo);
                s = ScratchBo{};
                return 0;
            }
            if (amdgpu_bo_cpu_map(s.bo, &s.cpu) != 0) {
                amdgpu_bo_va_op_raw(dev, s.bo, 0, kSnapRingBytes, s.va, 0, AMDGPU_VA_OP_UNMAP);
                amdgpu_bo_free(s.bo);
                s = ScratchBo{};
                return 0;
            }
            s.size = kSnapRingBytes;
            bo_line("snapshot ring", s.va, s.size); // experiment 0341
            list_gen++; // the BO list must name it
        }
        if (bytes > kSnapRingBytes / 4) {
            stats.dma_snapshot_overflow++;
            return 0;
        }
        std::uint64_t off = ((snap_head + 255) & ~std::uint64_t{255}) + (a & 0xffu);
        if (off + bytes > s.size) off = a & 0xffu; // wrap
        const std::uint64_t end = off + bytes;
        auto overlaps = [off, end](std::uint64_t x0, std::uint64_t x1) { return x0 < end && off < x1; };
        for (const auto &[x0, x1] : snap_job) {
            if (overlaps(x0, x1)) {
                stats.dma_snapshot_overflow++;
                return 0;
            }
        }
        for (const SnapSpan &x : snap_spans) {
            if (overlaps(x.start, x.end) && snap_in_flight(x)) {
                stats.dma_snapshot_overflow++;
                return 0;
            }
        }
        std::memcpy(static_cast<std::uint8_t *>(s.cpu) + off, reinterpret_cast<const void *>(a), bytes);
        snap_head = end;
        snap_job.emplace_back(off, end);
        stats.dma_snapshot_bytes += bytes;
        return s.va + off;
    }
    // After the job is on the ring: its copies are kept from being overwritten until it is done.
    void snap_commit(std::uint64_t seq) {
        if (snap_job.empty()) return;
        std::erase_if(snap_spans, [this](const SnapSpan &x) { return !snap_in_flight(x); });
        for (const auto &[x0, x1] : snap_job) snap_spans.push_back({x0, x1, cur, seq});
        snap_job.clear();
    }
    void snap_free() {
        ScratchBo &s = snap_ring;
        if (s.cpu) amdgpu_bo_cpu_unmap(s.bo);
        if (s.va && s.bo) amdgpu_bo_va_op_raw(dev, s.bo, 0, s.size, s.va, 0, AMDGPU_VA_OP_UNMAP);
        if (s.bo) amdgpu_bo_free(s.bo);
        s = ScratchBo{};
        snap_spans.clear();
        snap_job.clear();
        snap_head = 0;
    }
    int cur = 0;
    int next_gfx = 0;                                  // the slot each ring takes next
    int next_comp[kComputeRings] = {pool_first(0), pool_first(1), pool_first(2), pool_first(3)};
    std::atomic<std::uint64_t> slot_seq[kSlots] = {}; // sequence number of the job using the slot, 0 = free
    std::atomic<std::uint64_t> last_seq{0};            // the job queued last on the GFX ring (wait_idle)
    std::atomic<std::uint64_t> last_seq_comp[kComputeRings] = {}; // ... on each compute ring

    // A fence of this context on `ring`.
    amdgpu_cs_fence fence_of(int ring, std::uint64_t seq) const {
        amdgpu_cs_fence f{};
        f.context = ctx;
        f.ip_type = ring == kGfxRing ? AMDGPU_HW_IP_GFX : AMDGPU_HW_IP_COMPUTE;
        f.ring = ring == kGfxRing ? 0 : static_cast<std::uint32_t>(ring);
        f.fence = seq;
        return f;
    }

    bool scratch_reserve(std::uint64_t bytes) {
        ScratchBo &scratch = slots[cur];
        if (scratch.bo != nullptr && scratch.size >= bytes) return true;
        scratch_free();
        // Exactly the pages needed (dispatch-min's 4 KiB command BO is the configuration known
        // to work; a 1 MiB scratch hung the CP on the second fetch, experiment 0016).
        std::uint64_t size = (bytes + 4095) & ~std::uint64_t{4095};
        if (size == 0) size = 4096;
        amdgpu_bo_alloc_request req{};
        req.alloc_size = size;
        req.phys_alignment = 4096;
        req.preferred_heap = AMDGPU_GEM_DOMAIN_GTT;
        if (amdgpu_bo_alloc(dev, &req, &scratch.bo) != 0) return false;
        if (opts.legacy_scratch_va) {
            if (amdgpu_va_range_alloc(dev, amdgpu_gpu_va_range_general, size, 4096, 0, &scratch.va,
                                      &scratch.va_handle, 0) != 0)
                return false;
        } else {
            drm_amdgpu_info_device dev_info{};
            const std::uint64_t slot_va = kScratchVa + (static_cast<std::uint64_t>(cur) << 32);
            if (amdgpu_query_info(dev, AMDGPU_INFO_DEV_INFO, sizeof(dev_info), &dev_info) != 0 ||
                slot_va + size > dev_info.virtual_address_max) {
                std::fprintf(stderr, "bc5-direct: scratch VA 0x%llx outside the device's range\n",
                             static_cast<unsigned long long>(kScratchVa));
                return false;
            }
            scratch.va = slot_va;
        }
        // MTYPE_UC: the CP must never read the scratch through a stale GL2 line. A buffer read
        // once by the GPU and then rewritten by the CPU is served from the GPU L2 on the next
        // fetch (CPU-side coherence does not reach it): the first submit cached "8 NOPs + zeros",
        // the next one executed the zeros as type-0 packets and hung (experiment 0016, eight
        // resets to find). Uncached PTEs make every IB fetch go to memory.
        const std::uint64_t flags = AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_WRITEABLE |
                                    AMDGPU_VM_PAGE_EXECUTABLE | AMDGPU_VM_MTYPE_UC;
        if (amdgpu_bo_va_op_raw(dev, scratch.bo, 0, size, scratch.va, flags, AMDGPU_VA_OP_MAP) != 0) {
            std::fprintf(stderr, "bc5-direct: scratch map at 0x%llx failed\n",
                         static_cast<unsigned long long>(scratch.va));
            return false;
        }
        if (amdgpu_bo_cpu_map(scratch.bo, &scratch.cpu) != 0) return false;
        scratch.size = size;
        bo_line("scratch slot", scratch.va, size); // experiment 0341
        return true;
    }

    void scratch_free() {
        ScratchBo &scratch = slots[cur];
        if (scratch.cpu) amdgpu_bo_cpu_unmap(scratch.bo);
        if (scratch.va && scratch.bo) amdgpu_bo_va_op_raw(dev, scratch.bo, 0, scratch.size, scratch.va, 0, AMDGPU_VA_OP_UNMAP);
        if (scratch.va_handle) amdgpu_va_range_free(scratch.va_handle);
        if (scratch.bo) amdgpu_bo_free(scratch.bo);
        scratch = ScratchBo{};
        list_gen++; // a kept BO list names the old scratch BO
    }
};

std::unique_ptr<Device> Device::open(const std::string &node, const OpenOptions &opts) {
    std::unique_ptr<Device> d(new Device());
    d->impl_ = std::make_unique<Impl>();
    d->impl_->opts = opts;
    // Experiment 0341: the experimental switches, read here until the host's option parsing
    // carries them (each default off; the host's fields, when set, are kept).
    d->impl_->bo_journal = std::getenv("BC5_DIRECT_BO_JOURNAL") != nullptr;
    d->impl_->env_histogram = std::getenv("BC5_DIRECT_ARGS_HISTOGRAM") != nullptr;
    d->impl_->env_shadow = std::getenv("BC5_DIRECT_SHADOW_LABELS") != nullptr;
    if (const char *e = std::getenv("BC5_DIRECT_GPU_CHECK_PRODUCT"); e != nullptr && *e != 0) {
        d->impl_->env_product = true; // "1", or "x_limit[:yz_min]"
        char *end = nullptr;
        const unsigned long x = std::strtoul(e, &end, 0);
        if (end != e && x > 1) d->impl_->product.x_limit = static_cast<std::uint32_t>(x);
        if (end != nullptr && *end == ':') d->impl_->product.yz_min = static_cast<std::uint32_t>(std::strtoul(end + 1, nullptr, 0));
    }
    if (const char *e = std::getenv("BC5_DIRECT_GPU_CHECK_ZERO"); e != nullptr && *e != 0 && std::strcmp(e, "0") != 0) {
        d->impl_->env_zero = true; // experiment 0380
        std::fprintf(stderr, "bc5-direct: experiment 0380 switch: the CP check also skips an indirect dispatch whose x, y or z argument is 0\n");
    }
    if (const char *e = std::getenv("BC5_DIRECT_ARGS_WB"); e != nullptr && *e != 0 && std::strcmp(e, "0") != 0) {
        d->impl_->env_args_wb = std::strcmp(e, "all") == 0 ? indirect_check::ArgsWb::all : indirect_check::ArgsWb::first_after_index_base; // experiment 0380 (F570)
        std::fprintf(stderr, "bc5-direct: experiment 0380 switch: a GL2 write-back before the check of %s\n",
                     d->impl_->env_args_wb == indirect_check::ArgsWb::all ? "every checked indirect dispatch" : "the first indirect dispatch after an INDEX_BASE");
    }
    if (const char *e = std::getenv("BC5_DIRECT_ARGS_COPY"); e != nullptr && *e != 0 && std::strcmp(e, "0") != 0) {
        d->impl_->env_args_copy = true; // experiment 0380 (F566)
        std::fprintf(stderr, "bc5-direct: experiment 0380 switch: every checked GFX-form indirect dispatch runs from the CP's copy of its arguments, the copy the check reads\n");
    }
    if (const char *e = std::getenv("BC5_DIRECT_REBASE_DISPATCH"); e != nullptr && *e != 0 && std::strcmp(e, "0") != 0) {
        d->impl_->env_rebase = true; // experiment 0380
        std::fprintf(stderr, "bc5-direct: experiment 0380 switch: every checked GFX-form indirect dispatch gets its SET_BASE index 1 again right before it\n");
    }
    if (indirect_check::parse_yz_limit(std::getenv("BC5_DIRECT_GPU_CHECK_YZ"), d->impl_->yz)) { // experiment 0380
        d->impl_->env_yz = true;
        std::fprintf(stderr, "bc5-direct: experiment 0380 switch: the CP check refuses an indirect dispatch with y > %u or z > %u (never above the host's limits)\n",
                     d->impl_->yz.y, d->impl_->yz.z);
    }
    if (const char *e = std::getenv("BC5_DIRECT_FORCE_START_000"); e != nullptr && *e != 0 && std::strcmp(e, "0") != 0) {
        d->impl_->env_force_start = true; // experiment 0380
        std::fprintf(stderr, "bc5-direct: experiment 0380 switch: every indirect dispatch the GPU check pass sees gets FORCE_START_AT_000 in its initiator\n");
    }
    if (const char *e = std::getenv("BC5_DIRECT_HOST_INDIRECT"); e != nullptr && *e != 0) { // experiment 0346
        d->impl_->env_host_indirect = true;
        if (std::strncmp(e, "learn", 5) == 0) {
            if (e[5] == ':') d->impl_->hi_window_fixed = std::strtoull(e + 6, nullptr, 16);
        } else if (std::strcmp(e, "1") != 0) {
            d->impl_->hi_window_fixed = std::strtoull(e, nullptr, 16);
        }
        std::fprintf(stderr, "bc5-direct: experiment 0346 switch: a GFX-form dispatch without a SET_BASE of its type in its IB is resolved by the host (the carried base, or the window 0x%llx%s) and rewritten only to a page the host read, else NOP-ed; no CP read at an inferred address\n",
                     static_cast<unsigned long long>(d->impl_->hi_window_fixed), d->impl_->hi_window_fixed == 0 ? " learned from the title's SET_BASEs" : " until one is learned");
    }
    if (const char *e = std::getenv("BC5_DIRECT_IB_MAX_DW"); e != nullptr && *e != 0) { // experiment 0349
        const std::size_t v = static_cast<std::size_t>(std::strtoull(e, nullptr, 0));
        if (v >= 64 && v <= ib_split::kKernelMaxDwords) d->impl_->ib_max_dw = v;
    }
    std::fprintf(stderr, "bc5-direct: experiment 0349: a job's IB over %zu dwords is cut at aligned packet boundaries outside COND_EXEC ranges into up to %zu IBs of one submit (the kernel takes at most 0xfffff dwords per IB)\n",
                 d->impl_->ib_max_dw, ib_split::kMaxPieces);
    if (d->impl_->bo_journal || d->impl_->env_histogram || d->impl_->env_shadow || d->impl_->env_product)
        std::fprintf(stderr, "bc5-direct: experiment 0341 switches: product staircase %d (x > %u with y or z > %u), args histogram %d, shadow labels %d, bo journal %d\n",
                     d->impl_->env_product ? 1 : 0, d->impl_->product.x_limit, d->impl_->product.yz_min,
                     d->impl_->env_histogram ? 1 : 0, d->impl_->env_shadow ? 1 : 0, d->impl_->bo_journal ? 1 : 0);
    d->impl_->fd = ::open(node.c_str(), O_RDWR | O_CLOEXEC);
    if (d->impl_->fd < 0) {
        std::perror(node.c_str());
        return nullptr;
    }
    std::uint32_t major = 0, minor = 0;
    // deduplicate_device = false: libdrm otherwise returns the amdgpu_device (and therefore the
    // VM, VA allocator and fd) already opened by another client of the same node in this process
    // — RADV, in a track-B host — and every 1:1 mapping and scratch IB of ours lands in that VM.
    // A private device means a private VM. (Diagnostic: OpenOptions::deduplicate_device.)
    const int rc = opts.deduplicate_device
                       ? amdgpu_device_initialize(d->impl_->fd, &major, &minor, &d->impl_->dev)
                       : amdgpu_device_initialize2(d->impl_->fd, false, &major, &minor, &d->impl_->dev);
    if (rc != 0) {
        std::fprintf(stderr, "bc5-direct: amdgpu_device_initialize%s failed on %s\n",
                     opts.deduplicate_device ? "" : "2", node.c_str());
        return nullptr;
    }
    if (amdgpu_cs_ctx_create(d->impl_->dev, &d->impl_->ctx) != 0) {
        std::fprintf(stderr, "bc5-direct: amdgpu_cs_ctx_create failed\n");
        return nullptr;
    }
    if (opts.gds_kib != 0) {
        amdgpu_bo_alloc_request req{};
        req.alloc_size = static_cast<std::uint64_t>(opts.gds_kib) * 1024;
        req.preferred_heap = AMDGPU_GEM_DOMAIN_GDS;
        const int grc = amdgpu_bo_alloc(d->impl_->dev, &req, &d->impl_->gds);
        std::fprintf(stderr, "bc5-direct: GDS BO %u KiB: %s (%d)\n", opts.gds_kib, grc == 0 ? "ok" : "FAILED", grc);
        if (grc != 0) d->impl_->gds = nullptr;
    }
    if (opts.oa_count != 0) {
        amdgpu_bo_alloc_request req{};
        req.alloc_size = opts.oa_count;
        req.preferred_heap = AMDGPU_GEM_DOMAIN_OA;
        const int orc = amdgpu_bo_alloc(d->impl_->dev, &req, &d->impl_->oa);
        std::fprintf(stderr, "bc5-direct: OA BO %u: %s (%d)\n", opts.oa_count, orc == 0 ? "ok" : "FAILED", orc);
        if (orc != 0) d->impl_->oa = nullptr;
    }
    if (d->impl_->env_args_copy) { // experiment 0380 (F574): the copy's slot below 4 GiB
        amdgpu_bo_alloc_request req{};
        req.alloc_size = 4096;
        req.phys_alignment = 4096;
        req.preferred_heap = AMDGPU_GEM_DOMAIN_GTT;
        int arc = amdgpu_bo_alloc(d->impl_->dev, &req, &d->impl_->args_slot);
        if (arc == 0) {
            void *cpu = nullptr;
            if (amdgpu_bo_cpu_map(d->impl_->args_slot, &cpu) == 0) {
                std::memset(cpu, 0, 4096);
                amdgpu_bo_cpu_unmap(d->impl_->args_slot);
            }
            arc = amdgpu_va_range_alloc(d->impl_->dev, amdgpu_gpu_va_range_general, 4096, 4096, 0,
                                        &d->impl_->args_slot_va, &d->impl_->args_slot_vah, AMDGPU_VA_RANGE_32_BIT);
            if (arc == 0)
                arc = amdgpu_bo_va_op_raw(d->impl_->dev, d->impl_->args_slot, 0, 4096, d->impl_->args_slot_va,
                                          AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_WRITEABLE, AMDGPU_VA_OP_MAP);
        }
        std::fprintf(stderr, "bc5-direct: experiment 0380 args copy slot 4 KiB at 0x%llx: %s (%d)\n",
                     static_cast<unsigned long long>(d->impl_->args_slot_va), arc == 0 ? "ok" : "FAILED, the copy is off", arc);
        if (arc != 0) {
            if (d->impl_->args_slot_vah) amdgpu_va_range_free(d->impl_->args_slot_vah);
            if (d->impl_->args_slot) amdgpu_bo_free(d->impl_->args_slot);
            d->impl_->args_slot = nullptr;
            d->impl_->args_slot_vah = nullptr;
            d->impl_->args_slot_va = 0;
            d->impl_->env_args_copy = false;
        }
    }
    if (opts.gds_shadow) {
        amdgpu_bo_alloc_request req{};
        req.alloc_size = 65536;
        req.phys_alignment = 4096;
        req.preferred_heap = AMDGPU_GEM_DOMAIN_GTT;
        int src = amdgpu_bo_alloc(d->impl_->dev, &req, &d->impl_->shadow);
        if (src == 0) {
            void *cpu = nullptr;
            if (amdgpu_bo_cpu_map(d->impl_->shadow, &cpu) == 0) {
                std::memset(cpu, 0, 65536);
                d->impl_->shadow_cpu = cpu; // kept mapped: snapshots are read through it
            }
            src = amdgpu_bo_va_op_raw(d->impl_->dev, d->impl_->shadow, 0, 65536, Impl::kShadowVa,
                                      AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_WRITEABLE, AMDGPU_VA_OP_MAP);
        }
        std::fprintf(stderr, "bc5-direct: GDS shadow 64 KiB at 0x%llx: %s (%d)\n",
                     static_cast<unsigned long long>(Impl::kShadowVa), src == 0 ? "ok" : "FAILED", src);
        if (src != 0 && d->impl_->shadow) { amdgpu_bo_free(d->impl_->shadow); d->impl_->shadow = nullptr; }
    }
    if (opts.gws_count != 0) {
        amdgpu_bo_alloc_request req{};
        req.alloc_size = opts.gws_count;
        req.preferred_heap = AMDGPU_GEM_DOMAIN_GWS;
        const int wrc = amdgpu_bo_alloc(d->impl_->dev, &req, &d->impl_->gws);
        std::fprintf(stderr, "bc5-direct: GWS BO %u: %s (%d)\n", opts.gws_count, wrc == 0 ? "ok" : "FAILED", wrc);
        if (wrc != 0) d->impl_->gws = nullptr;
    }
    return d;
}

Device::~Device() {
    if (!impl_) return;
    impl_->summary(); // experiment 0341
    if (impl_->full_list) amdgpu_bo_list_destroy(impl_->full_list);
    for (auto &u : impl_->userptrs) {
        amdgpu_bo_va_op(u.bo, 0, u.size, u.va, 0, AMDGPU_VA_OP_UNMAP);
        amdgpu_bo_free(u.bo);
    }
    for (auto &m : impl_->shared_maps)
        amdgpu_bo_va_op_raw(impl_->dev, m.bo, m.bo_offset, m.size, m.va, 0, AMDGPU_VA_OP_UNMAP);
    for (auto &b : impl_->shared) amdgpu_bo_free(b.bo);
    for (const auto &[w, n] : impl_->prt_windows) amdgpu_bo_va_op_raw(impl_->dev, nullptr, 0, n, w, 0, AMDGPU_VA_OP_CLEAR);
    if (impl_->udmabuf_fd >= 0) close(impl_->udmabuf_fd);
    for (int k = 0; k < Impl::kSlots; ++k) {
        impl_->cur = k;
        impl_->scratch_free();
    }
    impl_->snap_free();
    if (ScratchBo &c = impl_->code; c.bo != nullptr) { // experiment 0137
        if (c.cpu) amdgpu_bo_cpu_unmap(c.bo);
        amdgpu_bo_va_op_raw(impl_->dev, c.bo, 0, c.size, c.va, 0, AMDGPU_VA_OP_UNMAP);
        amdgpu_bo_free(c.bo);
        c = ScratchBo{};
    }
    if (impl_->gds) amdgpu_bo_free(impl_->gds);
    if (impl_->oa) amdgpu_bo_free(impl_->oa);
    if (impl_->shadow) {
        if (impl_->shadow_cpu) amdgpu_bo_cpu_unmap(impl_->shadow);
        amdgpu_bo_va_op_raw(impl_->dev, impl_->shadow, 0, 65536, Impl::kShadowVa, 0, AMDGPU_VA_OP_UNMAP);
        amdgpu_bo_free(impl_->shadow);
    }
    if (impl_->gws) amdgpu_bo_free(impl_->gws);
    if (impl_->args_slot) { // experiment 0380 (F574)
        amdgpu_bo_va_op_raw(impl_->dev, impl_->args_slot, 0, 4096, impl_->args_slot_va, 0, AMDGPU_VA_OP_UNMAP);
        amdgpu_bo_free(impl_->args_slot);
        if (impl_->args_slot_vah) amdgpu_va_range_free(impl_->args_slot_vah);
    }
    if (impl_->ctx) amdgpu_cs_ctx_free(impl_->ctx);
    if (impl_->dev) amdgpu_device_deinitialize(impl_->dev);
    if (impl_->fd >= 0) close(impl_->fd);
}

bool Device::map_userptr(std::uint64_t cpu_va, std::uint64_t size) {
    return map_userptr(cpu_va, size, false);
}

bool Device::map_userptr(std::uint64_t cpu_va, std::uint64_t size, bool readonly) {
    std::lock_guard lock(impl_->mutex);
    if (size == 0 || (cpu_va & 0xfff) != 0 || (size & 0xfff) != 0) return false;
    for (const auto &u : impl_->userptrs) {
        if (cpu_va < u.va + u.size && u.va < cpu_va + size) {
            std::fprintf(stderr, "bc5-direct: mapping 0x%llx+0x%llx overlaps 0x%llx+0x%llx\n",
                         static_cast<unsigned long long>(cpu_va), static_cast<unsigned long long>(size),
                         static_cast<unsigned long long>(u.va), static_cast<unsigned long long>(u.size));
            return false;
        }
    }
    UserptrBo u;
    u.va = cpu_va;
    u.size = size;
    u.readonly = readonly;
    int rc = 0;
    if (readonly) {
        // Same flags as libdrm's helper plus READONLY (amdgpu_drm.h): the kernel accepts them
        // over r-- anonymous pages (probed on the BC-250, experiment 0016). NOT USABLE YET: the
        // raw ioctl hands back a GEM handle and libdrm's amdgpu_bo_import refuses KMS handles
        // (-EPERM), so the BO cannot enter an amdgpu_bo_list; a raw-handle BO list
        // (amdgpu_bo_list_create_raw) and a raw VA map are needed. Until then the host keeps
        // the guest's pages writable instead (KYTY_BC5_ALL_RW).
        drm_amdgpu_gem_userptr args{};
        args.addr = cpu_va;
        args.size = size;
        args.flags = AMDGPU_GEM_USERPTR_READONLY | AMDGPU_GEM_USERPTR_ANONONLY |
                     AMDGPU_GEM_USERPTR_REGISTER | AMDGPU_GEM_USERPTR_VALIDATE;
        rc = drmCommandWriteRead(impl_->fd, DRM_AMDGPU_GEM_USERPTR, &args, sizeof(args));
        if (rc == 0) {
            amdgpu_bo_import_result res{};
            rc = amdgpu_bo_import(impl_->dev, amdgpu_bo_handle_type_kms, args.handle, &res);
            u.bo = res.buf_handle;
        }
    } else {
        rc = amdgpu_create_bo_from_user_mem(impl_->dev, reinterpret_cast<void *>(cpu_va), size, &u.bo);
    }
    if (rc != 0) {
        std::fprintf(stderr, "bc5-direct: userptr%s 0x%llx+0x%llx failed: %d\n", readonly ? " (ro)" : "",
                     static_cast<unsigned long long>(cpu_va), static_cast<unsigned long long>(size), rc);
        return false;
    }
    if (readonly) {
        rc = impl_->va_map(u.bo, 0, size, cpu_va, AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_EXECUTABLE);
    } else {
        // amdgpu_bo_va_op's own flags (libdrm amdgpu_bo.c): readable, writeable, executable
        rc = impl_->va_map(u.bo, 0, size, cpu_va,
                           AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_WRITEABLE | AMDGPU_VM_PAGE_EXECUTABLE);
    }
    if (rc != 0) {
        std::fprintf(stderr, "bc5-direct: va map 0x%llx+0x%llx failed: %d\n",
                     static_cast<unsigned long long>(cpu_va), static_cast<unsigned long long>(size), rc);
        amdgpu_bo_free(u.bo);
        return false;
    }
    impl_->bo_line(readonly ? "userptr map (ro)" : "userptr map", cpu_va, size); // experiment 0341
    impl_->userptrs.push_back(u);
    impl_->list_gen++;
    return true;
}

bool Device::unmap_userptr(std::uint64_t cpu_va) {
    std::lock_guard lock(impl_->mutex);
    for (auto it = impl_->userptrs.begin(); it != impl_->userptrs.end(); ++it) {
        if (it->va == cpu_va) {
            impl_->drop_aliases_of(it->bo);
            impl_->bo_line("userptr unmap", it->va, it->size); // experiment 0341
            impl_->va_unmap(it->bo, 0, it->size, it->va);
            amdgpu_bo_free(it->bo);
            impl_->userptrs.erase(it);
            impl_->list_gen++;
            return true;
        }
    }
    return false;
}

std::uint64_t Device::gds_shadow_va() const { return impl_->shadow ? Impl::kShadowVa : 0; }
volatile std::uint32_t *Device::gds_shadow_cpu() const {
    return static_cast<volatile std::uint32_t *>(impl_->shadow_cpu);
}

std::vector<Mapping> Device::mappings() const {
    std::lock_guard lock(impl_->mutex);
    std::vector<Mapping> out;
    for (const auto &u : impl_->userptrs) out.push_back({u.va, u.size, u.readonly, false});
    for (const auto &m : impl_->shared_maps) out.push_back({m.va, m.size, false, true});
    return out;
}

std::shared_ptr<const std::vector<Mapping>> Device::sorted_mappings() const {
    std::lock_guard lock(impl_->mutex);
    if (impl_->sorted == nullptr || impl_->sorted_gen != impl_->list_gen) {
        // Experiment 0170: shared_maps is already sorted; only the few userptrs are sorted here
        // and merged in (a full sort of ~17,000 entries at every change of the list cost the
        // submitting thread a millisecond or more each time).
        std::vector<Mapping> users;
        users.reserve(impl_->userptrs.size());
        for (const auto &u : impl_->userptrs) users.push_back({u.va, u.size, u.readonly, false});
        const auto by_va = [](const Mapping &x, const Mapping &y) { return x.va < y.va; };
        std::sort(users.begin(), users.end(), by_va);
        auto out = std::make_shared<std::vector<Mapping>>();
        out->reserve(users.size() + impl_->shared_maps.size());
        auto u = users.begin();
        for (const auto &m : impl_->shared_maps) {
            while (u != users.end() && u->va < m.va) out->push_back(*u++);
            out->push_back({m.va, m.size, false, true});
        }
        out->insert(out->end(), u, users.end());
        impl_->sorted = std::move(out);
        impl_->sorted_gen = impl_->list_gen;
    }
    return impl_->sorted;
}

std::uint32_t Device::import_memfd(int memfd, std::uint64_t offset, std::uint64_t size) {
    std::lock_guard lock(impl_->mutex);
    if (size == 0 || (offset & 0xfff) != 0 || (size & 0xfff) != 0) return 0;
    if (impl_->udmabuf_fd < 0) {
        impl_->udmabuf_fd = ::open("/dev/udmabuf", O_RDWR | O_CLOEXEC);
        if (impl_->udmabuf_fd < 0) {
            std::fprintf(stderr, "bc5-direct: /dev/udmabuf: %s\n", std::strerror(errno));
            return 0;
        }
    }
    udmabuf_create c{};
    c.memfd = static_cast<std::uint32_t>(memfd);
    c.flags = UDMABUF_FLAGS_CLOEXEC;
    c.offset = offset;
    c.size = size;
    const int buf = ioctl(impl_->udmabuf_fd, UDMABUF_CREATE, &c);
    if (buf < 0) {
        std::fprintf(stderr, "bc5-direct: UDMABUF_CREATE 0x%llx+0x%llx: %s\n",
                     static_cast<unsigned long long>(offset), static_cast<unsigned long long>(size),
                     std::strerror(errno));
        return 0;
    }
    amdgpu_bo_import_result res{};
    const int rc = amdgpu_bo_import(impl_->dev, amdgpu_bo_handle_type_dma_buf_fd,
                                    static_cast<std::uint32_t>(buf), &res);
    close(buf); // the BO keeps the dma-buf
    if (rc != 0) {
        std::fprintf(stderr, "bc5-direct: dma-buf import 0x%llx+0x%llx: %d\n",
                     static_cast<unsigned long long>(offset), static_cast<unsigned long long>(size), rc);
        return 0;
    }
    SharedBo b;
    b.id = impl_->next_shared_id++;
    b.bo = res.buf_handle;
    b.size = size;
    impl_->shared.push_back(b);
    return b.id;
}

bool Device::map_shared(std::uint32_t id, std::uint64_t bo_offset, std::uint64_t size, std::uint64_t gpu_va) {
    std::lock_guard lock(impl_->mutex);
    if (size == 0 || ((bo_offset | size | gpu_va) & 0xfff) != 0) return false;
    SharedBo *b = impl_->shared_bo_locked(id);
    if (b == nullptr || bo_offset + size > b->size) return false;
    const int rc = impl_->va_map(b->bo, bo_offset, size, gpu_va,
                                 AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_WRITEABLE | AMDGPU_VM_PAGE_EXECUTABLE);
    if (rc != 0) {
        std::fprintf(stderr, "bc5-direct: shared map at 0x%llx+0x%llx: %d\n",
                     static_cast<unsigned long long>(gpu_va), static_cast<unsigned long long>(size), rc);
        return false;
    }
    // Experiment 0170: kept sorted by address (after any equal address, as push_back did).
    const auto at = std::upper_bound(impl_->shared_maps.begin(), impl_->shared_maps.end(), gpu_va,
                                     [](std::uint64_t va, const SharedMap &m) { return va < m.va; });
    impl_->shared_maps.insert(at, SharedMap{gpu_va, size, bo_offset, id, b->bo});
    if (impl_->bo_journal) // experiment 0341
        std::fprintf(stderr, "bc5-direct: bo shared map va 0x%llx size 0x%llx id %u offset 0x%llx\n",
                     static_cast<unsigned long long>(gpu_va), static_cast<unsigned long long>(size), id,
                     static_cast<unsigned long long>(bo_offset));
    b->maps++;
    impl_->list_gen++;
    return true;
}

bool Device::map_prt_window(std::uint64_t va, std::uint64_t size) {
    std::lock_guard lock(impl_->mutex);
    if (size == 0 || ((va | size) & 0xffff) != 0) return false;
    const int rc = amdgpu_bo_va_op_raw(impl_->dev, nullptr, 0, size, va, AMDGPU_VM_PAGE_PRT, AMDGPU_VA_OP_MAP);
    std::fprintf(stderr, "bc5-direct: PRT window 0x%llx+0x%llx: %d\n", static_cast<unsigned long long>(va),
                 static_cast<unsigned long long>(size), rc);
    if (rc != 0) return false;
    impl_->prt_windows.emplace_back(va, size);
    return true;
}

bool Device::unmap_shared(std::uint64_t gpu_va) {
    std::lock_guard lock(impl_->mutex);
    // Experiment 0170: binary search in the sorted list (the first mapping at that address, as
    // the old walk found).
    const auto it = std::lower_bound(impl_->shared_maps.begin(), impl_->shared_maps.end(), gpu_va,
                                     [](const SharedMap &m, std::uint64_t va) { return m.va < va; });
    if (it == impl_->shared_maps.end() || it->va != gpu_va) return false;
    impl_->va_unmap(it->bo, it->bo_offset, it->size, it->va);
    if (SharedBo *b = impl_->shared_bo_locked(it->id); b != nullptr && b->maps != 0) b->maps--;
    impl_->bo_line("shared unmap", it->va, it->size); // experiment 0341
    impl_->shared_maps.erase(it);
    impl_->list_gen++;
    return true;
}

std::uint64_t Device::map_alias(std::uint64_t src_va, std::uint64_t size, std::uint64_t alias_va) {
    std::lock_guard lock(impl_->mutex);
    if (size == 0 || ((src_va | size | alias_va) & 0xfff) != 0) return 0;
    const std::uint64_t end = src_va + size;
    std::uint64_t mapped = 0;
    auto one = [&](amdgpu_bo_handle bo, std::uint64_t va, std::uint64_t len, std::uint64_t bo_offset,
                   bool readonly) {
        const std::uint64_t s = std::max(va, src_va), e = std::min(va + len, end);
        if (s >= e) return;
        std::uint64_t to = alias_va + (s - src_va);
        if (to >= (1ull << 47)) to |= 0xffff000000000000ull; // the kernel's VA hole (amdgpu_vm_ioctl)
        const std::uint64_t flags = AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_EXECUTABLE |
                                    (readonly ? 0 : AMDGPU_VM_PAGE_WRITEABLE);
        const std::uint64_t off = bo_offset + (s - va);
        if (amdgpu_bo_va_op_raw(impl_->dev, bo, off, e - s, to, flags, AMDGPU_VA_OP_MAP) != 0) {
            std::fprintf(stderr, "bc5-direct: alias map at 0x%llx+0x%llx failed\n",
                         static_cast<unsigned long long>(to), static_cast<unsigned long long>(e - s));
            return;
        }
        impl_->aliases.push_back({to, e - s, off, bo});
        impl_->bo_line("alias map", to, e - s); // experiment 0341
        mapped += e - s;
    };
    for (const auto &u : impl_->userptrs) one(u.bo, u.va, u.size, 0, u.readonly);
    for (const auto &m : impl_->shared_maps) one(m.bo, m.va, m.size, m.bo_offset, false);
    return mapped;
}

void Device::unmap_aliases() {
    std::lock_guard lock(impl_->mutex);
    for (const auto &a : impl_->aliases)
        amdgpu_bo_va_op_raw(impl_->dev, a.bo, a.bo_offset, a.size, a.va, 0, AMDGPU_VA_OP_UNMAP);
    impl_->aliases.clear();
}

bool Device::free_shared(std::uint32_t id) {
    std::lock_guard lock(impl_->mutex);
    for (auto b = impl_->shared.begin(); b != impl_->shared.end(); ++b) {
        if (b->id != id) continue;
        // Experiment 0170: one pass that keeps the list's order (erasing one by one was quadratic).
        std::size_t w = 0;
        for (std::size_t r = 0; r < impl_->shared_maps.size(); ++r) {
            auto &m = impl_->shared_maps[r];
            if (m.id == id) {
                impl_->va_unmap(m.bo, m.bo_offset, m.size, m.va);
                continue;
            }
            if (w != r) impl_->shared_maps[w] = m;
            ++w;
        }
        impl_->shared_maps.resize(w);
        b->maps = 0;
        impl_->drop_aliases_of(b->bo);
        // a kept list would hold the BO (and its pages) alive
        if (impl_->full_list) {
            amdgpu_bo_list_destroy(impl_->full_list);
            impl_->full_list = nullptr;
        }
        amdgpu_bo_free(b->bo);
        impl_->shared.erase(b);
        impl_->list_gen++;
        return true;
    }
    return false;
}

namespace {

// Which type-3 packets of `src` survived the filter into `dst` (the filter NOPs in place).
void executed_offsets_of(std::span<const std::uint32_t> src, const std::uint32_t *dst,
                         std::vector<std::uint32_t> &out) {
    for (std::size_t i = 0; i < src.size();) {
        const std::uint32_t h = src[i];
        const std::uint32_t type = h >> 30;
        std::size_t len = 1;
        if (type == 3) {
            const std::uint32_t count = (h >> 16) & 0x3fff;
            len = count == 0x3fff ? 1 : count + 2;
            const std::uint32_t op_in = (h >> 8) & 0xff;
            const std::uint32_t op_out = (dst[i] >> 8) & 0xff;
            if (op_in != 0x10 && (dst[i] >> 30) == 3 && op_out != 0x10)
                out.push_back(static_cast<std::uint32_t>(i));
        } else if (type == 0) {
            len = ((h >> 16) & 0x3fff) + 2;
        } else if (type == 2) {
            len = 1;
        } else {
            break;
        }
        i += len;
    }
}

// Does a filtered IB still hold a draw or a dispatch?
bool has_draw_or_dispatch(const std::uint32_t *d, std::size_t n) {
    for (std::size_t i = 0; i < n;) {
        const std::uint32_t h = d[i];
        const std::uint32_t type = h >> 30;
        const std::uint32_t count = (h >> 16) & 0x3fff;
        std::size_t len = 1;
        if (type == 3 || type == 0) len = count == 0x3fff ? 1 : count + 2;
        if (type == 3 && count != 0x3fff &&
            policy::is_draw_or_dispatch(static_cast<std::uint8_t>((h >> 8) & 0xff)))
            return true;
        i += len;
    }
    return false;
}

struct Piece {
    const std::uint32_t *src = nullptr;
    std::size_t n = 0;      // dwords
    std::size_t off = 0;    // dword offset in the scratch
    std::size_t padded = 0; // n rounded up to 8
    int depth = 0;
};

// INDIRECT_BUFFER / INDIRECT_BUFFER_CNST targets of an IB that lie inside the mapped ranges.
void nested_targets(std::span<const std::uint32_t> ib, const policy::FilterOptions &opt,
                    std::vector<std::pair<const std::uint32_t *, std::size_t>> &out) {
    for (std::size_t i = 0; i < ib.size();) {
        const std::uint32_t h = ib[i];
        const std::uint32_t type = h >> 30;
        std::size_t len = 1;
        if (type == 3 || type == 0) {
            const std::uint32_t count = (h >> 16) & 0x3fff;
            len = count == 0x3fff ? 1 : count + 2;
        }
        if (i + len > ib.size()) break;
        const std::uint32_t op = (h >> 8) & 0xff;
        if (type == 3 && (op == 0x3f || op == 0x33) && len >= 4) {
            const std::uint64_t a = (static_cast<std::uint64_t>(ib[i + 1]) & ~3ull) |
                                    (static_cast<std::uint64_t>(ib[i + 2] & 0xffu) << 32);
            const std::size_t n = ib[i + 3] & 0xfffffu;
            if (a != 0 && n != 0 && (!opt.mapped || opt.mapped(a, n * 4)))
                out.emplace_back(reinterpret_cast<const std::uint32_t *>(a), n);
        }
        i += len;
    }
}

} // namespace

SubmitResult Device::submit(std::span<const std::uint32_t> ib, const policy::FilterOptions &opt,
                            std::uint64_t timeout_ns, bool with_gds, int ring) {
    SubmitResult r;
    std::lock_guard lock(impl_->mutex);
    const bool comp = ring != kGfxRing;
    if (comp && (ring < 0 || ring >= kComputeRings)) { // ADR 0009
        r.rc = -EINVAL;
        return r;
    }
    r.ring = ring;
    if (async_) {
        int &next = comp ? impl_->next_comp[ring] : impl_->next_gfx;
        impl_->cur = next;
        next = next + 1 < Impl::pool_first(ring) + Impl::pool_size(ring) ? next + 1 : Impl::pool_first(ring);
        if (impl_->slot_seq[impl_->cur].load() != 0) { // the host lets fewer jobs fly than there are slots
            r.rc = -EBUSY;
            return r;
        }
    } else {
        impl_->cur = Impl::pool_first(ring);
    }
    impl_->slot_ring[impl_->cur] = ring;
    const double t_enter = now_ms();
    if (wedged_) {
        r.rc = -1;
        return r;
    }
    if (ib.empty()) {
        r.rc = -2;
        return r;
    }
    // Layout: the IB first, then every INDIRECT_BUFFER target it (transitively) reaches, each
    // padded to 8 dwords with NOPs — the CP fetches IBs in 32-byte chunks and must never run
    // into what lies past a buffer (experiment 0016). The nested copies let the filter see the
    // console's compute rings, which are rings of INDIRECT_BUFFER packets (step e).
    std::vector<Piece> pieces;
    // Experiment 0124: the job's own timestamps, at the end of the prologue and of the epilogue; their
    // address is filled in once the slot is known.
    std::vector<std::uint32_t> pro_v = opt.prologue;
    std::vector<std::uint32_t> epi_v = opt.epilogue;
    std::size_t ts_at_pro = 0, ts_at_epi = 0;
    if (opt.job_timestamps) {
        ts_at_pro = pro_v.size();
        pro_v.insert(pro_v.end(), {0xC0044000u, 9u | (5u << 8) | (1u << 16) | (1u << 20), 0u, 0u, 0u, 0u});
        ts_at_epi = epi_v.size();
        epi_v.insert(epi_v.end(), {0xC0064900u, 0x28u | (5u << 8), 3u << 29, 0u, 0u, 0u, 0u, 0u});
    }
    const std::size_t pro = pro_v.size();
    const std::size_t pro_padded = (pro + 7) & ~std::size_t{7};
    const std::size_t epi = epi_v.size();
    // The IB itself is filtered into a vector first: the state-stack emulation may grow it
    // (a CLEAR_STATE pop becomes the SET_CONTEXT_REG packets of the saved context), and the
    // nested copies are laid out behind what will actually be executed.
    // Short lists: the operands the filter accepts are recorded, for the BO list of an IB
    // without draws and dispatches.
    const bool short_possible = short_lists_ && include_mappings_ && static_cast<bool>(opt.mapped);
    std::vector<std::pair<std::uint64_t, std::uint64_t>> touched;
    policy::FilterOptions fopt = opt;
    fopt.compute_ring = comp;
    if (short_possible) {
        fopt.mapped = [&opt, &touched](std::uint64_t a, std::uint64_t bytes) {
            const bool ok = opt.mapped(a, bytes);
            if (ok) touched.emplace_back(a, bytes);
            return ok;
        };
    }
    impl_->snap_job.clear();
    if (opt.dma_snapshot_min != 0 && !impl_->opts.legacy_scratch_va) { // experiment 0122
        fopt.dma_source_min = opt.dma_snapshot_min;
        fopt.dma_source = [this, &r](std::uint64_t a, std::uint32_t bytes) -> std::uint64_t {
            return impl_->snapshot(a, bytes, r.filter);
        };
    }
    std::vector<std::uint32_t> &main_out = impl_->main_buf; // every dword is written by the filter
    main_out.resize(ib.size());
    double t_phase = now_ms();
    policy::filter(policy::Policy::builtin(), ib, main_out, fopt, r.filter);
    executed_offsets_of(ib, main_out.data(), r.executed_offsets);
    // Experiment 0346: the host-side resolution of GFX-form dispatches without a SET_BASE of their type in
    // this IB (bc5/host_indirect.hpp). The real mappings are the device's userptr and shared mappings (the
    // sorted table: no PRT window, guard or zero buffer is in it); the reader is the host's `mapped` test
    // and a CPU read of the arguments (GPU VA == guest VA, as the 0341 histogram read them).
    // Experiment 0348: the register the pass carries is committed only once the job is on the ring. A job
    // the kernel refuses (rc -22: the ~250,000-dword dcbs of 12:52, 18:55 and 19:22) changes nothing on the
    // GPU, so its SET_BASEs must not move the host's copy either (F421).
    host_indirect::Register hi_next = impl_->hi_reg;
    if (impl_->env_host_indirect && !comp) {
        const host_indirect::Reader read = [&opt](std::uint64_t va, std::uint32_t (&cnt)[3]) {
            if (opt.mapped && !opt.mapped(va, 12)) return false;
            const auto *p = reinterpret_cast<const volatile std::uint32_t *>(va);
            cnt[0] = p[0];
            cnt[1] = p[1];
            cnt[2] = p[2];
            return true;
        };
        host_indirect::Stats hs;
        const std::uint64_t window = impl_->hi_window_learned != 0 ? impl_->hi_window_learned : impl_->hi_window_fixed;
        // The mapping table (~19,000 userptr and shared mappings) is copied and sorted only when a dispatch is
        // a candidate (the register 0 after the title's zeroing): the first walk runs against no region, and
        // a candidate then shows as "not a real mapping"; R1 of the third version (RT off) paid ~15 % of its
        // flips for the sort on every GFX-ring job with no candidate at all.
        static const std::vector<host_indirect::Region> kNoRegion;
        auto decisions = host_indirect::resolve_indirect(main_out, impl_->hi_reg, window, kNoRegion, read,
                                                         host_indirect::Limits{}, hs);
        if (hs.dropped_unmapped != 0) {
            std::vector<host_indirect::Region> regions; // the device lock is held: the lists, not sorted_mappings()
            regions.reserve(impl_->shared_maps.size() + impl_->userptrs.size());
            for (const auto &m : impl_->shared_maps) regions.push_back({m.va, m.size});
            for (const auto &u : impl_->userptrs) regions.push_back({u.va, u.size});
            std::sort(regions.begin(), regions.end(), [](const host_indirect::Region &a, const host_indirect::Region &b) { return a.va < b.va; });
            hs = host_indirect::Stats{};
            decisions = host_indirect::resolve_indirect(main_out, impl_->hi_reg, window, regions, read,
                                                        host_indirect::Limits{}, hs);
        }
        if (!decisions.empty()) host_indirect::rewrite_verified(main_out, decisions, hs);
        hi_next = hs.register_out;
        if (hs.window_seen != 0) impl_->hi_window_learned = hs.window_seen;
        impl_->hi_sum.left_nonzero += hs.left_nonzero;
        impl_->hi_sum.left_never_set += hs.left_never_set;
        impl_->hi_sum.rewritten += hs.rewritten;
        impl_->hi_sum.dropped_no_candidate += hs.dropped_no_candidate;
        impl_->hi_sum.dropped_unmapped += hs.dropped_unmapped;
        impl_->hi_sum.dropped_unreadable += hs.dropped_unreadable;
        impl_->hi_sum.dropped_insane += hs.dropped_insane;
        impl_->hi_sum.nop_on_overflow += hs.nop_on_overflow;
        for (const auto &x : decisions) { // one line per program, the first time it is rewritten or dropped
            if (x.decision == host_indirect::Decision::Leave) continue;
            if (!impl_->hi_programs.insert(x.program).second) continue;
            static const char *const why[] = {"left: the register is non-zero", "left: the register was never set", "verified: SET_BASE to the page, the dispatch, SET_BASE 0",
                                              "no candidate (register 0, no window): NOP", "not a real mapping: NOP", "unreadable: NOP", "counts fail the limits: NOP"};
            std::fprintf(stderr, "bc5-direct: experiment 0346 %s: dispatch at %zu of program 0x%llx (%s type), register 0 after the title's zeroing, window 0x%llx + offset 0x%llx -> 0x%llx (page 0x%llx), counts %u %u %u: %s\n",
                         x.decision == host_indirect::Decision::Rewrite ? "rewrite" : "drop", x.at, static_cast<unsigned long long>(x.program),
                         x.shader_type != 0 ? "compute" : "graphics", static_cast<unsigned long long>(x.window), static_cast<unsigned long long>(x.address - x.window),
                         static_cast<unsigned long long>(x.address), static_cast<unsigned long long>(x.page), x.counts[0], x.counts[1], x.counts[2],
                         why[static_cast<std::size_t>(x.why)]);
        }
    }
    r.prep_filter_ms = now_ms() - t_phase;
    t_phase = now_ms();
    if (state_stack_ && opt.mapped && !comp) { // the context registers are the GFX ring's
        impl_->tracker.apply_in_place(ib, main_out, opt.mapped, r.state_stack);
    }
    r.prep_tracker_ms = now_ms() - t_phase;
    t_phase = now_ms();
    // The CU mask for registers loaded from memory (phase 3 step f): a SET_SH_REG after the load.
    if (opt.cu_mask != 0xffffffffu && opt.mapped) {
        main_out = cu_tables::apply(main_out, opt.cu_mask, opt.mapped, r.cu_tables);
    }
    // Experiment 0341 (arm 2): host-owned shadow labels for the main IB's own syncs on the GFX
    // ring; the slots lie after the flag area of the job's scratch and are patched in below.
    std::uint32_t shadow_slots = 0;
    if (impl_->env_shadow && !comp) {
        shadow_labels::Stats sst;
        const bool ok = shadow_labels::apply(main_out, Impl::kShadowSlots, sst);
        shadow_slots = ok ? sst.labels : 0;
        if (sst.labels != 0 && (++impl_->shadow_jobs % 2000) == 0) impl_->summary("periodic");
        impl_->shadow_labels_sum += sst.labels;
        impl_->shadow_writes_sum += sst.writes;
        impl_->shadow_waits_sum += sst.waits;
        impl_->shadow_overflow_sum += sst.overflow;
        if (!ok) impl_->shadow_failed_sum++;
    }
    r.prep_cu_ms = now_ms() - t_phase;
    t_phase = now_ms();
    // Experiment 0038: a compute IB's DISPATCH_INDIRECT, rewritten for the GFX ring
    // (FilterOptions::mec_indirect_base), gets a PFP_SYNC_ME in front: on the GFX ring the
    // prefetch parser reads the arguments ahead of the ME, so the CS_PARTIAL_FLUSH and
    // ACQUIRE_MEM the console puts between the dispatch that writes them and this one did not
    // hold it back, and it read stale values (+inf as a group count). RADV and radeonsi do the
    // same before an indirect draw or dispatch whose arguments the GPU wrote (Mesa
    // PKT3_PFP_SYNC_ME, TODO(verify) the lines). Inserting dwords moves every offset after it:
    // the IB's own COND_EXEC counts are grown around the insertions (ADR 0010 section A, as the
    // CP DMA waits below since experiment 0052); an IB used to be left alone when it held one.
    if ((opt.mec_indirect_base != 0 || opt.pfp_sync_indirect) && !opt.gpu_check_indirect && !comp) {
        std::vector<indirect_check::Insert> syncs;
        for (std::size_t i = 0; i < main_out.size();) {
            const std::uint32_t h = main_out[i];
            const std::uint32_t type = h >> 30;
            std::size_t len = 1;
            if (type == 3 || type == 0) {
                const std::uint32_t count = (h >> 16) & 0x3fff;
                len = count == 0x3fff ? 1 : count + 2;
            }
            if (type == 3 && ((h >> 8) & 0xff) == 0x16 && len == 3) {
                syncs.push_back({i, {kPfpSyncMe, 0u}});
            }
            i += len;
        }
        if (!syncs.empty() && indirect_check::insert_before(main_out, syncs)) {
            r.filter.pfp_syncs += syncs.size();
        }
    }
    // Experiment 0050: CP DMA runs beside the CP, and a DMA_DATA without CP_SYNC is not waited for
    // by the dispatches after it. The second title's compute IB copies BVH headers with such
    // DMA_DATAs, then dispatches the tree refit that reads them; on the GFX ring the refit read
    // the 0xBAADF00D the header held before the copy and looped (journal: header at submit
    // f00d4abd 0000baad, after the timeout the copied "PSR_BVHL"). Before the first dispatch after
    // an unsynced DMA_DATA goes the zero-byte DMA_DATA with CP_SYNC of the IB's end (dma_idle_).
    // Experiment 0052: an IB with its own COND_EXEC gets them too, the counts grown around them.
    if (opt.dma_sync_before_dispatch && !comp) { // the MEC waits for its DMA itself
        std::vector<indirect_check::Insert> waits;
        bool pending = false;
        for (std::size_t i = 0; i < main_out.size();) {
            const std::uint32_t h = main_out[i];
            const std::uint32_t type = h >> 30;
            std::size_t len = 1;
            if (type == 3 || type == 0) {
                const std::uint32_t count = (h >> 16) & 0x3fff;
                len = count == 0x3fff ? 1 : count + 2;
            }
            if (i + len > main_out.size()) len = main_out.size() - i;
            const std::uint32_t op = (h >> 8) & 0xff;
            if (type == 3 && op == 0x50 && len >= 2) pending = (main_out[i + 1] & 0x80000000u) == 0;
            if (type == 3 && (op == 0x15 || op == 0x16) && pending) {
                waits.push_back({i, {0xC0055000u, 0xE0300000u, 0u, 0u, 0u, 0u, 0u}});
                pending = false;
            }
            i += len;
        }
        if (indirect_check::insert_before(main_out, waits)) r.filter.dma_syncs += waits.size();
    }
    // Experiment 0052: the group counts checked by the CP when it runs the dispatch (after the
    // DMA waits above: a COND_EXEC must skip exactly the dispatch). The flag lives in this job's
    // scratch, after the last piece; its address is filled in once the slot is known.
    std::vector<std::size_t> flag_refs;
    if (impl_->env_histogram && !comp) impl_->histogram(main_out, opt.mec_indirect_base, opt.mapped, fopt); // experiment 0341
    if (opt.gpu_check_indirect) {
        indirect_check::Stats st;
        std::uint32_t check_max[3] = {opt.gpu_check_max[0], opt.gpu_check_max[1], opt.gpu_check_max[2]};
        if (impl_->env_yz) indirect_check::tighten(check_max, impl_->yz); // experiment 0380
        main_out = indirect_check::apply(main_out, opt.mec_indirect_base, check_max,
                                         opt.gpu_check_draw_max, flag_refs, st, comp,
                                         impl_->env_product && !comp ? &impl_->product : nullptr, // experiment 0341
                                         impl_->env_zero, impl_->env_force_start, impl_->env_rebase,
                                         impl_->env_args_copy, impl_->env_args_wb, impl_->args_slot_va); // experiment 0380
        impl_->product_sum += st.product_checked;
        impl_->zero_sum += st.zero_checked;
        impl_->start_forced_sum += st.start_forced;
        impl_->rebased_sum += st.rebased;
        impl_->rebased_ib_sum += st.rebased_after_index_base;
        impl_->args_copied_sum += st.args_copied;
        impl_->args_wb_sum += st.args_written_back;
        if (impl_->env_force_start) impl_->start_seen_sum += st.checked + st.unbased;
        r.filter.gpu_checks += st.checked;
        r.filter.gpu_check_unbased += st.unbased;
        r.filter.gpu_check_skipped += st.conditional;
    }
    if (dma_idle_ && !comp) {
        // PKT3(DMA_DATA, 5, 0); CP_SYNC | SRC_SEL and DST_SEL "address using L2"; no addresses;
        // zero bytes — as si_emit_cp_dma(sctx, cs, 0, 0, 0, CP_DMA_SYNC) emits it (Mesa 0866ae7).
        main_out.insert(main_out.end(), {0xC0055000u, 0xE0300000u, 0u, 0u, 0u, 0u, 0u});
    }
    const std::size_t main_n = main_out.size();
    pieces.push_back({ib.data(), ib.size(), pro_padded, (main_n + epi + 7) & ~std::size_t{7}, 0});
    for (std::size_t k = 0; k < pieces.size() && pieces.size() < 64; ++k) {
        if (pieces[k].depth >= 3) continue;
        std::vector<std::pair<const std::uint32_t *, std::size_t>> targets;
        nested_targets(std::span<const std::uint32_t>(pieces[k].src, pieces[k].n), opt, targets);
        for (const auto &[src, n] : targets) {
            bool seen = false;
            for (const auto &q : pieces) seen = seen || (q.src == src && q.n == n);
            if (seen) continue;
            const Piece &last = pieces.back();
            pieces.push_back({src, n, last.off + last.padded, (n + 7) & ~std::size_t{7}, pieces[k].depth + 1});
        }
    }
    const Piece &last = pieces.back();
    const std::size_t flag_off = last.off + last.padded; // experiment 0052: 8 dwords
    std::size_t end_off = flag_off + (flag_refs.empty() ? 0 : 8);
    const std::size_t shadow_off = end_off; // experiment 0341: two dwords per shadow slot
    end_off += static_cast<std::size_t>(shadow_slots) * 2;
    std::size_t ts_dw = 0;
    if (opt.job_timestamps) { // experiment 0124: start and end, 8-byte aligned
        ts_dw = (end_off + 1) & ~std::size_t{1};
        end_off = ts_dw + 4;
    }
    const std::uint64_t bytes = end_off * sizeof(std::uint32_t);
    r.prep_nested_ms = now_ms() - t_phase; // the survey; the nested filters are added below
    t_phase = now_ms();
    if (!impl_->scratch_reserve(bytes)) {
        r.rc = -2;
        return r;
    }
    if (impl_->image.size() < bytes / sizeof(std::uint32_t)) impl_->image.resize(bytes / sizeof(std::uint32_t));
    auto *dst = impl_->image.data();
    if (!flag_refs.empty()) {
        indirect_check::patch(main_out, flag_refs, impl_->slots[impl_->cur].va + flag_off * 4);
        for (std::size_t i = 0; i < 8; ++i) dst[flag_off + i] = 0;
    }
    if (shadow_slots != 0) { // experiment 0341: the slots start as 0, as the title's labels do
        shadow_labels::patch(main_out, impl_->slots[impl_->cur].va + shadow_off * 4);
        for (std::size_t i = 0; i < static_cast<std::size_t>(shadow_slots) * 2; ++i) dst[shadow_off + i] = 0;
    }
    impl_->ts_off[impl_->cur] = static_cast<std::uint32_t>(ts_dw);
    if (opt.job_timestamps) {
        const std::uint64_t ts_va = impl_->slots[impl_->cur].va + ts_dw * 4;
        pro_v[ts_at_pro + 4] = static_cast<std::uint32_t>(ts_va);
        pro_v[ts_at_pro + 5] = static_cast<std::uint32_t>(ts_va >> 32);
        epi_v[ts_at_epi + 3] = static_cast<std::uint32_t>(ts_va + 8);
        epi_v[ts_at_epi + 4] = static_cast<std::uint32_t>((ts_va + 8) >> 32);
        for (std::size_t i = 0; i < 4; ++i) dst[ts_dw + i] = 0;
    }
    for (std::size_t i = 0; i < pro; ++i) dst[i] = pro_v[i];
    for (std::size_t i = pro; i < pro_padded; ++i) dst[i] = policy::kNop;
    for (std::size_t k = 0; k < pieces.size(); ++k) {
        const Piece &pc = pieces[k];
        if (k == 1) { // the main copy is done; what follows are the nested filters
            r.prep_copy_ms += now_ms() - t_phase;
            t_phase = now_ms();
        }
        if (k == 0) { // filtered above; the epilogue sits between the IB and its padding
            for (std::size_t i = 0; i < main_n; ++i) dst[pc.off + i] = main_out[i];
            for (std::size_t i = main_n; i < pc.padded; ++i) dst[pc.off + i] = policy::kNop;
            for (std::size_t i = 0; i < epi; ++i) dst[pc.off + main_n + i] = epi_v[i];
            continue;
        }
        // nested IBs: no statistics samples (their slots belong to the main IB)
        policy::FilterStats st;
        policy::FilterOptions nested_opt = fopt;
        nested_opt.stat_sample_va = 0;
        policy::filter(policy::Policy::builtin(), std::span<const std::uint32_t>(pc.src, pc.n),
                       std::span<std::uint32_t>(dst + pc.off, pc.n), nested_opt, st);
        for (std::size_t i = pc.n; i < pc.padded; ++i) dst[pc.off + i] = policy::kNop;
        std::vector<std::uint32_t> ex;
        executed_offsets_of(std::span<const std::uint32_t>(pc.src, pc.n), dst + pc.off, ex);
        r.nested.push_back({reinterpret_cast<std::uint64_t>(pc.src),
                            static_cast<std::uint32_t>(pc.n), std::move(ex)});
    }
    if (pieces.size() > 1) {
        r.prep_nested_ms += now_ms() - t_phase;
    } else {
        r.prep_copy_ms += now_ms() - t_phase;
    }
    t_phase = now_ms();
    // Point the surviving INDIRECT_BUFFER packets at the scratch copies.
    for (std::size_t k = 0; k < pieces.size(); ++k) {
        const Piece &pc = pieces[k];
        std::uint32_t *d = dst + pc.off;
        const std::size_t pc_n = k == 0 ? main_n : pc.n;
        for (std::size_t i = 0; i < pc_n;) {
            const std::uint32_t h = d[i];
            const std::uint32_t type = h >> 30;
            std::size_t len = 1;
            if (type == 3 || type == 0) {
                const std::uint32_t count = (h >> 16) & 0x3fff;
                len = count == 0x3fff ? 1 : count + 2;
            }
            if (i + len > pc_n) break;
            const std::uint32_t op = (h >> 8) & 0xff;
            if (type == 3 && (op == 0x3f || op == 0x33) && len >= 4) {
                const std::uint64_t a = (static_cast<std::uint64_t>(d[i + 1]) & ~3ull) |
                                        (static_cast<std::uint64_t>(d[i + 2] & 0xffu) << 32);
                const std::size_t n = d[i + 3] & 0xfffffu;
                bool found = false;
                for (const Piece &q : pieces) {
                    if (reinterpret_cast<std::uint64_t>(q.src) == a && q.n == n) {
                        const std::uint64_t va = impl_->slots[impl_->cur].va + q.off * 4;
                        d[i + 1] = static_cast<std::uint32_t>(va & 0xffffffffu);
                        d[i + 2] = static_cast<std::uint32_t>((va >> 32) & 0xffffu);
                        found = true;
                        break;
                    }
                }
                if (!found) { // an unmapped or over-deep target: never let the CP follow it
                    for (std::size_t q = 0; q < len; ++q) d[i + q] = policy::kNop;
                }
            }
            i += len;
        }
    }
    const std::size_t padded = pro_padded + pieces[0].padded; // the CP runs prologue then IB
    // Experiment 0349: the executed IB [0, padded) cut into up to four IBs when it is over the limit; the
    // cuts are packet boundaries 256 bytes aligned (else 32, the CP's fetch chunk) outside every COND_EXEC
    // range, no dword moves. A job that cannot be cut is refused here as the kernel would refuse it.
    std::vector<ib_split::Piece> ib_pieces;
    if (padded > impl_->ib_max_dw) {
        ib_split::Stats ss;
        ib_pieces = ib_split::split(std::span<const std::uint32_t>(impl_->image.data(), padded), padded, impl_->ib_max_dw,
                                    ib_split::kMaxPieces, 64, 8, ss);
        if (ib_pieces.empty()) {
            impl_->split_failed++;
            std::fprintf(stderr, "bc5-direct: experiment 0349: job of %zu dwords (%zu from the title's %zu) cannot be cut into %zu IBs of %zu: %s (%u COND_EXEC ranges, at %zu); refused\n",
                         padded, main_n, ib.size(), ib_split::kMaxPieces, impl_->ib_max_dw,
                         ss.too_many_pieces ? "more pieces would be needed" : "no aligned packet boundary outside a COND_EXEC range", ss.cond_ranges, ss.failed_at);
            r.rc = -EINVAL;
            return r;
        }
        impl_->split_jobs++;
        impl_->split_pieces += ib_pieces.size();
        impl_->split_fallback += ss.fallback_cuts;
        if (impl_->split_jobs <= 8 || impl_->split_jobs % 500 == 0) {
            std::fprintf(stderr, "bc5-direct: experiment 0349 split #%llu: job of %zu dwords (%zu from the title's %zu) into %zu IBs:",
                         static_cast<unsigned long long>(impl_->split_jobs), padded, main_n, ib.size(), ib_pieces.size());
            for (const auto &pc : ib_pieces) std::fprintf(stderr, " [%zu +%zu]", pc.off, pc.n);
            std::fprintf(stderr, "; %u COND_EXEC ranges, %u fallback cuts; so far %llu jobs cut into %llu IBs, %llu fallback cuts, %llu refused\n", ss.cond_ranges, ss.fallback_cuts,
                         static_cast<unsigned long long>(impl_->split_jobs), static_cast<unsigned long long>(impl_->split_pieces),
                         static_cast<unsigned long long>(impl_->split_fallback), static_cast<unsigned long long>(impl_->split_failed));
        }
    }
    // One sequential copy into the uncached scratch (MTYPE_UC, F25); nothing reads it back.
    std::memcpy(impl_->slots[impl_->cur].cpu, impl_->image.data(), bytes);
    r.prep_copy_ms += now_ms() - t_phase;

    std::vector<amdgpu_bo_handle> bos;
    bos.reserve(impl_->userptrs.size() + 1);
    for (const auto &sl : impl_->slots) {
        if (sl.bo != nullptr) bos.push_back(sl.bo);
    }
    if (impl_->snap_ring.bo != nullptr) bos.push_back(impl_->snap_ring.bo); // experiment 0122
    if (impl_->code.bo != nullptr) bos.push_back(impl_->code.bo);           // experiment 0137
    if (with_gds && impl_->gds) bos.push_back(impl_->gds);
    if (with_gds && impl_->oa) bos.push_back(impl_->oa);
    if (with_gds && impl_->gws) bos.push_back(impl_->gws);
    if (impl_->shadow) bos.push_back(impl_->shadow);
    if (impl_->args_slot) bos.push_back(impl_->args_slot); // experiment 0380 (F574)
    bool draws = !short_possible;
    if (short_possible) {
        draws = has_draw_or_dispatch(dst + pieces[0].off, main_n);
        for (std::size_t k = 1; k < pieces.size() && !draws; ++k)
            draws = has_draw_or_dispatch(dst + pieces[k].off, pieces[k].n);
    }
    // Imported memfd ranges (ADR 0006): each BO once, however many addresses it is mapped at.
    auto add_shared = [&](amdgpu_bo_handle bo) {
        if (std::find(bos.begin(), bos.end(), bo) == bos.end()) bos.push_back(bo);
    };
    const bool full = include_mappings_ && draws;
    const bool kept = full && impl_->full_list != nullptr && impl_->full_list_gen == impl_->list_gen &&
                      impl_->full_list_gds == with_gds;
    if (kept) {
        // the list of the last submission with draws still names every mapping
    } else if (full) {
        for (const auto &u : impl_->userptrs) bos.push_back(u.bo);
        bos.reserve(bos.size() + impl_->shared.size());
        // every imported BO that is mapped somewhere (experiment 0170: from the per-BO count,
        // not a walk of every mapping)
        for (const auto &b : impl_->shared) {
            if (b.maps != 0) bos.push_back(b.bo);
        }
    } else if (include_mappings_) {
        // Table operands are declared with a nominal size; the margins cover their real extent.
        constexpr std::uint64_t kBefore = 0x10000, kAfter = 0x20000;
        for (const auto &u : impl_->userptrs) {
            for (const auto &[a, span_bytes] : touched) {
                const std::uint64_t lo = a > kBefore ? a - kBefore : 0;
                const std::uint64_t hi = a + 2 * span_bytes + kAfter;
                if (u.va < hi && u.va + u.size > lo) {
                    bos.push_back(u.bo);
                    break;
                }
            }
        }
        if (impl_->shared_disjoint_locked()) {
            // Experiment 0170: the mappings are sorted and disjoint, so those overlapping
            // [lo, hi) are the one holding lo (if any) and the ones starting before hi.
            const auto &maps = impl_->shared_maps;
            for (const auto &[a, span_bytes] : touched) {
                const std::uint64_t lo = a > kBefore ? a - kBefore : 0;
                const std::uint64_t hi = a + 2 * span_bytes + kAfter;
                auto it = std::upper_bound(maps.begin(), maps.end(), lo,
                                           [](std::uint64_t va, const SharedMap &m) { return va < m.va; });
                if (it != maps.begin() && std::prev(it)->va + std::prev(it)->size > lo) --it;
                for (; it != maps.end() && it->va < hi; ++it) {
                    if (it->va + it->size > lo) add_shared(it->bo);
                }
            }
        } else {
            for (const auto &m : impl_->shared_maps) {
                for (const auto &[a, span_bytes] : touched) {
                    const std::uint64_t lo = a > kBefore ? a - kBefore : 0;
                    const std::uint64_t hi = a + 2 * span_bytes + kAfter;
                    if (m.va < hi && m.va + m.size > lo) {
                        add_shared(m.bo);
                        break;
                    }
                }
            }
        }
        r.short_list = true;
    }
    r.bo_count = kept ? impl_->full_list_count : static_cast<std::uint32_t>(bos.size());
    amdgpu_bo_list_handle list = nullptr;
    const double t_list = now_ms();
    r.prepare_ms = t_list - t_enter;
    if (kept) {
        list = impl_->full_list;
    } else {
        r.rc = amdgpu_bo_list_create(impl_->dev, static_cast<std::uint32_t>(bos.size()), bos.data(),
                                     nullptr, &list);
        if (r.rc == 0 && full) {
            if (impl_->full_list) amdgpu_bo_list_destroy(impl_->full_list);
            impl_->full_list = list;
            impl_->full_list_gen = impl_->list_gen;
            impl_->full_list_gds = with_gds;
            impl_->full_list_count = r.bo_count;
        }
    }
    r.list_ms = now_ms() - t_list;
    if (r.rc != 0) return r;

    amdgpu_cs_ib_info ib_info[ib_split::kMaxPieces]{};
    std::uint32_t n_ibs = 0;
    if (ib_pieces.empty()) {
        ib_info[0].ib_mc_address = impl_->slots[impl_->cur].va;
        ib_info[0].size = static_cast<std::uint32_t>(padded);
        n_ibs = 1;
    } else {
        for (const auto &pc : ib_pieces) { // experiment 0349: the pieces run back to back, each an IB1
            ib_info[n_ibs].ib_mc_address = impl_->slots[impl_->cur].va + pc.off * 4;
            ib_info[n_ibs].size = static_cast<std::uint32_t>(pc.n);
            n_ibs++;
        }
    }
    amdgpu_cs_request req{};
    req.ip_type = comp ? AMDGPU_HW_IP_COMPUTE : AMDGPU_HW_IP_GFX;
    req.ring = comp ? static_cast<std::uint32_t>(ring) : 0;
    req.resources = list;
    req.number_of_ibs = n_ibs;
    req.ibs = ib_info;
    amdgpu_cs_fence deps[kComputeRings]{};
    if ((ring_deps_ & (comp ? 1 : 2)) != 0) { // set_ring_deps
        std::uint32_t n = 0;
        if (comp) {
            if (const std::uint64_t seq = impl_->last_seq.load(); seq != 0) deps[n++] = impl_->fence_of(kGfxRing, seq);
        } else {
            for (int k = 0; k < kComputeRings; ++k) {
                if (const std::uint64_t seq = impl_->last_seq_comp[k].load(); seq != 0) deps[n++] = impl_->fence_of(k, seq);
            }
        }
        req.number_of_dependencies = n;
        req.dependencies = n != 0 ? deps : nullptr;
    }

    const double t0 = now_ms();
    r.rc = amdgpu_cs_submit(impl_->ctx, 0, &req, 1);
    if (r.rc == 0) impl_->hi_reg = hi_next; // experiment 0348: the CP's base-1 register as this job leaves it
    if (r.rc != 0) // experiment 0348: amdgpu_cs refuses an IB over 0xfffff dwords (amdgpu_cs.c, amdgpu_cs_p2_ib)
        std::fprintf(stderr, "bc5-direct: cs refused rc %d: the job's IB is %zu dwords (%zu from the title's %zu) in %u IBs, %u BOs; the kernel takes at most 0xfffff dwords per IB\n",
                     r.rc, padded, main_n, ib.size(), n_ibs, r.bo_count);
    r.cs_ms = now_ms() - t0;
    std::uint32_t expired = 0;
    r.seq_no = req.seq_no;
    if (async_) {
        r.slot = static_cast<std::uint32_t>(impl_->cur);
        r.pending = r.rc == 0;
        if (r.pending) {
            impl_->slot_seq[impl_->cur] = req.seq_no;
            (comp ? impl_->last_seq_comp[ring] : impl_->last_seq) = req.seq_no;
            impl_->snap_commit(req.seq_no); // experiment 0122
        }
        r.submit_ms = now_ms() - t0;
        if (list != impl_->full_list) amdgpu_bo_list_destroy(list);
        submits_++;
        r.ok = r.rc == 0;
        return r;
    }
    if (r.rc == 0) {
        amdgpu_cs_fence fence = impl_->fence_of(ring, req.seq_no);
        r.rc = amdgpu_cs_query_fence_status(&fence, timeout_ns, 0, &expired);
        if (r.rc == 0 && !expired) {
            r.timed_out = true;
            wedged_ = true;
#ifdef AMDGPU_INFO_GPUVM_FAULT
            // A shader-side fault is what usually sits behind a timeout (experiment 0016, step
            // d): the kernel keeps the last VM fault per process; it names the page to map.
            drm_amdgpu_info_gpuvm_fault fault{};
            if (amdgpu_query_info(impl_->dev, AMDGPU_INFO_GPUVM_FAULT, sizeof(fault), &fault) == 0) {
                r.fault_addr = fault.addr;
                r.fault_status = fault.status;
            }
#endif
        }
    }
    r.submit_ms = now_ms() - t0;
    r.fence_ms = r.submit_ms - r.cs_ms;
    if (list != impl_->full_list) amdgpu_bo_list_destroy(list);
    submits_++;
    r.ok = r.rc == 0 && expired != 0;
    return r;
}

void *Device::code_area() {
    std::lock_guard lock(impl_->mutex);
    ScratchBo &c = impl_->code;
    if (c.bo != nullptr) return c.cpu;
    amdgpu_bo_alloc_request req{};
    req.alloc_size = kCodeBytes;
    req.phys_alignment = 65536;
    req.preferred_heap = AMDGPU_GEM_DOMAIN_GTT;
    req.flags = AMDGPU_GEM_CREATE_CPU_GTT_USWC;
    if (amdgpu_bo_alloc(impl_->dev, &req, &c.bo) != 0) return nullptr;
    const std::uint64_t flags = AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_WRITEABLE | AMDGPU_VM_PAGE_EXECUTABLE | AMDGPU_VM_MTYPE_UC;
    if (amdgpu_bo_va_op_raw(impl_->dev, c.bo, 0, kCodeBytes, kCodeVa, flags, AMDGPU_VA_OP_MAP) != 0) {
        amdgpu_bo_free(c.bo);
        c = ScratchBo{};
        return nullptr;
    }
    if (amdgpu_bo_cpu_map(c.bo, &c.cpu) != 0) {
        amdgpu_bo_va_op_raw(impl_->dev, c.bo, 0, kCodeBytes, kCodeVa, 0, AMDGPU_VA_OP_UNMAP);
        amdgpu_bo_free(c.bo);
        c = ScratchBo{};
        return nullptr;
    }
    c.va = kCodeVa;
    c.size = kCodeBytes;
    impl_->bo_line("code area", c.va, c.size); // experiment 0341
    impl_->list_gen++; // the BO lists must name it
    return c.cpu;
}

bool Device::wait_idle(std::uint64_t timeout_ns) {
    auto idle = [this, timeout_ns](int ring, std::uint64_t seq) {
        if (seq == 0) return true;
        amdgpu_cs_fence fence = impl_->fence_of(ring, seq);
        std::uint32_t expired = 0;
        return amdgpu_cs_query_fence_status(&fence, timeout_ns, 0, &expired) == 0 && expired != 0;
    };
    bool all = idle(kGfxRing, impl_->last_seq.load());
    for (int k = 0; k < kComputeRings; ++k) all = idle(k, impl_->last_seq_comp[k].load()) && all;
    return all;
}

SubmitResult Device::finish(std::uint64_t seq_no, std::uint32_t slot, std::uint64_t timeout_ns) {
    // No device lock: the submitting thread may be preparing the next IB.
    SubmitResult r;
    r.seq_no = seq_no;
    r.slot = slot;
    r.ring = slot < static_cast<std::uint32_t>(Impl::kSlots) ? impl_->slot_ring[slot].load() : kGfxRing;
    const double t0 = now_ms();
    amdgpu_cs_fence fence = impl_->fence_of(r.ring, seq_no);
    std::uint32_t expired = 0;
    r.rc = amdgpu_cs_query_fence_status(&fence, timeout_ns, 0, &expired);
    if (r.rc == 0 && !expired) {
        r.timed_out = true;
        wedged_ = true;
#ifdef AMDGPU_INFO_GPUVM_FAULT
        drm_amdgpu_info_gpuvm_fault fault{};
        if (amdgpu_query_info(impl_->dev, AMDGPU_INFO_GPUVM_FAULT, sizeof(fault), &fault) == 0) {
            r.fault_addr = fault.addr;
            r.fault_status = fault.status;
        }
#endif
    }
    r.fence_ms = now_ms() - t0;
    r.ok = r.rc == 0 && expired != 0;
    if (r.ok) impl_->read_job_ts(slot, r); // experiment 0124, before the slot is given back
    if (r.ok && slot < static_cast<std::uint32_t>(Impl::kSlots)) impl_->slot_seq[slot] = 0;
    return r;
}

} // namespace bc5::direct
