// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/direct.hpp"
#include "bc5/draw_args.hpp"
#include "bc5/env_flag.hpp"
#include "bc5/ib_split.hpp"
#include "bc5/indirect_check.hpp"
#include "bc5/shadow_labels.hpp"

#include <amdgpu.h>
#include <amdgpu_drm.h>
#include <fcntl.h>
#include <linux/udmabuf.h>
#include <sys/ioctl.h>
#include <sys/uio.h>
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
#include <shared_mutex>
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
    bool readonly = false; // exp 0412 (tag cv412): mapped readable only (a K1r cover)
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
    // Experiment 0027: the IB is assembled and scanned in this cached buffer and copied into the
    // scratch once; every read of the uncached scratch cost more than the walk itself.
    std::vector<std::uint32_t> image;
    // Experiment 0341: the two experimental switches read from the environment in
    // Device::open (the host's FilterOptions / OpenOptions fields win when set),
    // the shadow-label sums (arm 2) and the summary at close.
    bool env_product = false, env_shadow = false;
    // Experiment 0380: BC5_DIRECT_GPU_CHECK_ZERO — the CP check also skips a dispatch whose x, y or z
    // argument is 0 (indirect_check zero_dims). Unset: off.
    bool env_zero = false;
    std::uint64_t zero_sum = 0;
    // Experiment 0380: BC5_DIRECT_FORCE_START_000 — every indirect dispatch the check pass sees gets
    // FORCE_START_AT_000 in its initiator (indirect_check force_start), as RADV sets it. Unset: off.
    bool env_force_start = false;
    // Experiment 0442 bake 1c (D28): BC5_DIRECT_0442_GC_NOCOPY, on unless "0": a job with no packet the CP check
    // instruments skips indirect_check::apply, which returned a whole copy of the IB for it on every submit.
    bool gc_nocopy = true;
    // Experiment 0380 (F555): BC5_DIRECT_GPU_CHECK_YZ — the CP check's y and z limits for indirect
    // dispatches lowered ("1" = 256:64, or "<y>[:<z>]"). Unset: the host's limits as they are.
    bool env_yz = false;
    // Experiment 0380 (F566): BC5_DIRECT_ARGS_COPY — each checked GFX-form DISPATCH_INDIRECT runs from the
    // CP's own copy of its arguments, the copy the check reads (indirect_check args_copy). Unset: off.
    bool env_args_copy = false;
    std::uint64_t args_copied_sum = 0;
    // Experiment 0380 (F570): BC5_DIRECT_ARGS_WB — "first" (the first DISPATCH_INDIRECT after an INDEX_BASE) or
    // "all": a GL2 write-back (ACQUIRE_MEM GL2_WB) before the check of a checked indirect dispatch. Unset: off.
    indirect_check::ArgsWb env_args_wb = indirect_check::ArgsWb::off;
    std::uint64_t args_wb_sum = 0;
    // Experiment 0380 (F617): BC5_DIRECT_ARGS_FLUSH — "first" (the first DISPATCH_INDIRECT after an INDEX_BASE) or
    // "all": a CS_PARTIAL_FLUSH before the check of a checked indirect dispatch; BC5_DIRECT_ARGS_FLUSH_DRAWS=1: the
    // same before the check of every checked indirect draw. Unset: off.
    indirect_check::ArgsFlush env_args_flush = indirect_check::ArgsFlush::off;
    bool env_flush_draws = false;
    std::uint64_t args_flush_sum = 0;
    indirect_check::YzLimit yz;
    std::uint64_t start_forced_sum = 0, start_seen_sum = 0;
    // exp 0442 (tag nl442): experiment 0346's BC5_DIRECT_HOST_INDIRECT is gone: its window was learned from the title's
    // SET_BASEs or a constant of one title (0x1100000000), and F432 counted 0 rewrites. A dispatch it would have
    // resolved runs as the title wrote it; a fault there is a bug with a record (F416's class), fixed at its cause.
    // Experiment 0349: a job's executed IB longer than this is cut into up to four IBs of one submit
    // (bc5/ib_split.hpp); the kernel refuses an IB over 0xfffff dwords (F421). BC5_DIRECT_IB_MAX_DW lowers it.
    std::size_t ib_max_dw = ib_split::kDefaultMaxDwords;
    std::uint64_t split_jobs = 0, split_pieces = 0, split_fallback = 0, split_failed = 0;
    indirect_check::ProductLimit product;
    std::uint64_t shadow_jobs = 0, shadow_labels_sum = 0, shadow_writes_sum = 0, shadow_waits_sum = 0,
                  shadow_overflow_sum = 0, shadow_failed_sum = 0, product_sum = 0;
    static constexpr std::uint32_t kShadowSlots = 64; // per job: 512 bytes of the scratch
    void summary(const char *when = "at close") { // also every 2000 shadowed jobs: a killed emulator never gets here
        if (env_draw_args && when[0] == 'a') da_summary("close"); // experiment 0381
        if (shadow_jobs != 0 || product_sum != 0 || shadow_failed_sum != 0)
            std::fprintf(stderr,
                         "bc5-direct: experiment 0341 %s: shadow labels in %llu jobs: %llu labels, %llu writes copied, %llu waits redirected, %llu labels without a slot, %llu IBs left alone (COND_EXEC); product staircase on %llu dispatches\n",
                         when, static_cast<unsigned long long>(shadow_jobs), static_cast<unsigned long long>(shadow_labels_sum),
                         static_cast<unsigned long long>(shadow_writes_sum), static_cast<unsigned long long>(shadow_waits_sum),
                         static_cast<unsigned long long>(shadow_overflow_sum), static_cast<unsigned long long>(shadow_failed_sum),
                         static_cast<unsigned long long>(product_sum));
        if (env_product && product.count) // experiment 0442
            std::fprintf(stderr, "bc5-direct: experiment 0442 %s: product staircase count: %llu of %llu completed checked jobs refused at least one dispatch\n",
                         when, static_cast<unsigned long long>(product_jobs_marked), static_cast<unsigned long long>(product_jobs_read));
        if (shadow_count) // experiment 0442
            std::fprintf(stderr, "bc5-direct: experiment 0442 %s: shadow count: labels after completed jobs: %llu equal to their slot, %llu 0 (the title's CPU), %llu a third value, %llu unreadable\n",
                         when, static_cast<unsigned long long>(shadow_cmp_equal), static_cast<unsigned long long>(shadow_cmp_zero),
                         static_cast<unsigned long long>(shadow_cmp_other), static_cast<unsigned long long>(shadow_cmp_unread));
        if (env_zero) // experiment 0380: how many the CP skipped is not seen by the host
            std::fprintf(stderr, "bc5-direct: experiment 0380 %s: zero-dimension guard on %llu checked dispatches\n",
                         when, static_cast<unsigned long long>(zero_sum));
        if (env_args_wb != indirect_check::ArgsWb::off) // experiment 0380 (F570)
            std::fprintf(stderr, "bc5-direct: experiment 0380 %s: GL2 write-back before %llu checked indirect dispatches\n",
                         when, static_cast<unsigned long long>(args_wb_sum));
        if (env_args_flush != indirect_check::ArgsFlush::off || env_flush_draws) // experiment 0380 (F617)
            std::fprintf(stderr, "bc5-direct: experiment 0380 %s: CS_PARTIAL_FLUSH before %llu checked indirect dispatches and draws\n",
                         when, static_cast<unsigned long long>(args_flush_sum));
        if (env_args_copy) // experiment 0380 (F566)
            std::fprintf(stderr, "bc5-direct: experiment 0380 %s: %llu checked indirect dispatches ran from the CP's copy of their arguments\n",
                         when, static_cast<unsigned long long>(args_copied_sum));
        if (env_force_start) // experiment 0380
            std::fprintf(stderr, "bc5-direct: experiment 0380 %s: FORCE_START_AT_000 set on %llu of %llu indirect dispatches (the rest had it)\n",
                         when, static_cast<unsigned long long>(start_forced_sum), static_cast<unsigned long long>(start_seen_sum));
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
    // Experiment 0436 (tag su436): held shared by a job of submit(..., before_call) from before its prepare to the end
    // of its bookkeeping, across the kernel call made without `mutex`; taken exclusively, before `mutex`, by every
    // removal of a mapping or BO (unmap_userptr, unmap_shared, free_shared, the destructor). Order:
    // flight_mu, then mutex. Nobody waits for the host's locks while holding it.
    std::shared_mutex flight_mu;
    // Experiment 0436: the kept BO lists named by a job between its prepare and its kernel call's return; a list
    // replaced meanwhile (another job's new full list) is destroyed by its last user, not at once.
    std::map<amdgpu_bo_list_handle, int> list_users;
    void list_drop(amdgpu_bo_list_handle h) {
        if (h != nullptr && list_users.count(h) == 0) amdgpu_bo_list_destroy(h);
    }
    // Device::sorted_mappings: the sorted list and the list_gen it was built at.
    std::shared_ptr<const MappingIndex> sorted;
    std::uint64_t sorted_gen = ~0ull;
    // exp 0438 (tag a2): BC5_DIRECT_0438_A2=1 keeps `sorted` up to date at each edit of the lists (no rebuild);
    // with BC5_0438_A2_CHECK_BUILD defined, BC5_DIRECT_0438_A2_CHECK=1 compares it with a full rebuild every 64th call
    const bool a2 = [] { const char *e = std::getenv("BC5_DIRECT_0438_A2"); return !(e != nullptr && e[0] == '0' && e[1] == 0); }(); // exp 0438 (bake438b): on unless "0"
#if defined(BC5_0438_A2_CHECK_BUILD) // exp 0438 (bake438b): A2's compare-only check, private diagnosis builds only
    const bool a2_check = [] { const char *e = std::getenv("BC5_DIRECT_0438_A2_CHECK"); return e != nullptr && e[0] == '1' && e[1] == 0; }();
    std::uint64_t a2_calls = 0, a2_mismatches = 0;
    // exp 0438 (tag a2c438): counters, one stderr line per 60 s from sorted_mappings() while A2_CHECK=1 (cumulative)
    std::uint64_t a2_ins = 0, a2_era = 0, a2_skipped = 0, a2_drops = 0, a2_rebuilds = 0, a2_compares = 0;
    std::chrono::steady_clock::time_point a2_t0 = std::chrono::steady_clock::now(), a2_next = a2_t0 + std::chrono::seconds(60);
    void a2_insert(const Mapping &m) { if (a2 && sorted) { sorted = index_insert(sorted, m); a2_ins++; } else if (a2) a2_skipped++; }
    void a2_erase(const Mapping &m) { if (a2 && sorted) { sorted = index_erase(sorted, m); a2_era++; } else if (a2) a2_skipped++; }
    void a2_line() {
        const auto now = std::chrono::steady_clock::now();
        if (now < a2_next) return;
        a2_next = now + std::chrono::seconds(60);
        std::fprintf(stderr, "bc5-direct: exp 0438 (tag a2c438): t %.0f s: index edits insert %llu erase %llu (with no index %llu), drops %llu, rebuilds %llu; "
                     "A2_CHECK sorted_mappings calls %llu, compares %llu, mismatches %llu; entries %zu\n",
                     std::chrono::duration<double>(now - a2_t0).count(), (unsigned long long)a2_ins, (unsigned long long)a2_era,
                     (unsigned long long)a2_skipped, (unsigned long long)a2_drops, (unsigned long long)a2_rebuilds, (unsigned long long)a2_calls,
                     (unsigned long long)a2_compares, (unsigned long long)a2_mismatches, sorted ? sorted->size() : std::size_t{0});
    }
#else
    void a2_insert(const Mapping &m) { if (a2 && sorted) sorted = index_insert(sorted, m); }
    void a2_erase(const Mapping &m) { if (a2 && sorted) sorted = index_erase(sorted, m); }
#endif // BC5_0438_A2_CHECK_BUILD
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
    // can let more than a dozen jobs fly (24 since experiment 0045); a slot grows to the largest
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
    // Experiment 0442 (count while guarding): BC5_DIRECT_GPU_CHECK_PRODUCT=count[:...] marks a job whose staircase refused a dispatch
    // (bc5/indirect_check.hpp kWouldByte); BC5_DIRECT_SHADOW_LABELS=count compares, after each GFX job, every
    // shadowed label of the title with its slot (bc5/shadow_labels.hpp classify). Both guards still guard.
    // The submitting thread fills a slot's record before the job is queued; finish() reads it before the slot
    // is given back (as ts_off and da_pending).
    bool shadow_count = false;
    std::uint32_t would_off[kSlots] = {};              // dword offset of the job's would word, 0 = none
    std::uint32_t shadow_cmp_off[kSlots] = {};         // dword offset of the job's first shadow slot, 0 = none
    std::vector<std::uint64_t> shadow_cmp_vas[kSlots]; // the title's label of each slot
    std::mutex cnt_mu;
    std::uint64_t product_jobs_marked = 0, product_jobs_read = 0;
    std::uint64_t shadow_cmp_equal = 0, shadow_cmp_zero = 0, shadow_cmp_other = 0, shadow_cmp_unread = 0, shadow_cmp_loud = 0;
    void read_counts(std::uint32_t slot, std::uint64_t seq_no) { // experiment 0442, finish(): the job completed
        if (slot >= static_cast<std::uint32_t>(kSlots) || slots[slot].cpu == nullptr) return;
        const auto *base = static_cast<const volatile std::uint32_t *>(slots[slot].cpu);
        if (would_off[slot] != 0) {
            const bool marked = base[would_off[slot]] != 0;
            std::lock_guard<std::mutex> g(cnt_mu);
            product_jobs_read++;
            if (marked) product_jobs_marked++;
        }
        if (shadow_cmp_off[slot] != 0 && !shadow_cmp_vas[slot].empty()) {
            const std::vector<std::uint64_t> &vas = shadow_cmp_vas[slot];
            for (std::size_t i = 0; i < vas.size(); ++i) {
                const std::uint64_t sv = static_cast<std::uint64_t>(base[shadow_cmp_off[slot] + 2 * i]) |
                                         (static_cast<std::uint64_t>(base[shadow_cmp_off[slot] + 2 * i + 1]) << 32);
                std::uint64_t tv = 0;
                iovec l{&tv, sizeof(tv)}, r{reinterpret_cast<void *>(vas[i]), sizeof(tv)};
                const bool read = process_vm_readv(getpid(), &l, 1, &r, 1, 0) == static_cast<ssize_t>(sizeof(tv));
                std::lock_guard<std::mutex> g(cnt_mu);
                if (!read) {
                    shadow_cmp_unread++;
                    continue;
                }
                switch (shadow_labels::classify(tv, sv)) {
                case shadow_labels::Match::Equal: shadow_cmp_equal++; break;
                case shadow_labels::Match::TitleZero: shadow_cmp_zero++; break;
                case shadow_labels::Match::Other:
                    shadow_cmp_other++;
                    if (shadow_cmp_loud++ < 20)
                        std::fprintf(stderr, "bc5-direct: experiment 0442 shadow count: job %llu label 0x%llx holds 0x%llx, its slot 0x%llx (a third value)\n",
                                     static_cast<unsigned long long>(seq_no), static_cast<unsigned long long>(vas[i]),
                                     static_cast<unsigned long long>(tv), static_cast<unsigned long long>(sv));
                    break;
                }
            }
            shadow_cmp_vas[slot].clear();
        }
        would_off[slot] = 0;
        shadow_cmp_off[slot] = 0;
    }
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
    // Experiment 0442 bake 1c (D28, SNAP_GROW): BC5_DIRECT_0442_SNAP_GROW, on unless "0". The ring is sized from use: it
    // starts as one 8 MiB buffer at kSnapRingVa and grows by a buffer as large as the ring so far (8, 8, 16, 32 MiB: 16,
    // 32, 64 MiB), each mapped right after the last, when a copy would otherwise be refused (no room beside the copies of
    // jobs in flight, or larger than any buffer); never past the old 64 MiB. A copy stays inside one buffer (the CPU
    // mappings are separate); the GPU sees one range. Off: the old fixed 64 MiB buffer, allocated at first use.
    static constexpr std::uint64_t kSnapFirstBytes = 8ull << 20;
    bool snap_grow = true;
    struct SnapSpan {
        std::uint64_t start = 0, end = 0;
        int slot = 0;
        std::uint64_t seq = 0;
    };
    std::vector<ScratchBo> snap_ring; // exp 0442 bake 1c: the ring's buffers, in VA order (one with SNAP_GROW=0)
    std::uint64_t snap_size = 0;      // their total, the ring's size
    ScratchBo code; // experiment 0137 (Device::code_area)
    std::uint64_t snap_head = 0;
    std::vector<SnapSpan> snap_spans;                         // committed jobs' copies, oldest first
    std::vector<std::pair<std::uint64_t, std::uint64_t>> snap_job; // this submission's copies

    bool snap_in_flight(const SnapSpan &x) const {
        return x.slot >= 0 && x.slot < kSlots && slot_seq[x.slot].load() == x.seq && x.seq != 0;
    }
    // A copy of [a, a + bytes) in the ring, keeping the low eight address bits (the DMA reads the
    // copy as it would have read the source); 0 when it does not fit now.
    // exp 0442 bake 1c: one more buffer of the ring, mapped at the ring's end; false when it cannot be had
    bool snap_add(std::uint64_t bytes) {
        ScratchBo s;
        amdgpu_bo_alloc_request req{};
        req.alloc_size = bytes;
        req.phys_alignment = 4096;
        req.preferred_heap = AMDGPU_GEM_DOMAIN_GTT;
        // Write-combined for the CPU: the copies are written once, in order, never read back.
        req.flags = AMDGPU_GEM_CREATE_CPU_GTT_USWC;
        if (amdgpu_bo_alloc(dev, &req, &s.bo) != 0) return false;
        s.va = kSnapRingVa + snap_size;
        // The default (cached) GPU mapping, as the title's own staging has: the DMA reads the
        // copy where it would have read the source, after the same cache invalidations.
        const std::uint64_t flags = AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_WRITEABLE;
        if (amdgpu_bo_va_op_raw(dev, s.bo, 0, bytes, s.va, flags, AMDGPU_VA_OP_MAP) != 0) {
            amdgpu_bo_free(s.bo);
            return false;
        }
        if (amdgpu_bo_cpu_map(s.bo, &s.cpu) != 0) {
            amdgpu_bo_va_op_raw(dev, s.bo, 0, bytes, s.va, 0, AMDGPU_VA_OP_UNMAP);
            amdgpu_bo_free(s.bo);
            return false;
        }
        s.size = bytes;
        snap_ring.push_back(s);
        snap_size += bytes;
        list_gen++; // the BO list must name it
        return true;
    }
    // exp 0442 bake 1c: the ring offset where a copy of bytes from a goes, starting at off0, or ~0 when it does not
    // fit now: it stays inside one buffer and overwrites no copy of this submission or of a job in flight
    std::uint64_t snap_place(std::uint64_t off0, std::uint64_t a, std::uint32_t bytes) const {
        std::uint64_t off = off0;
        for (int tries = 0; tries < 2 + static_cast<int>(snap_ring.size()); ++tries) {
            const ScratchBo *in = nullptr;
            for (const ScratchBo &c : snap_ring)
                if (off >= c.va - kSnapRingVa && off < c.va - kSnapRingVa + c.size) in = &c;
            if (in == nullptr) { // past the ring's end: wrap
                off = a & 0xffu;
                continue;
            }
            const std::uint64_t c_end = in->va - kSnapRingVa + in->size;
            if (off + bytes > c_end) { // into the next buffer (or wrap after the last)
                off = c_end + (a & 0xffu);
                continue;
            }
            const std::uint64_t end = off + bytes;
            auto overlaps = [off, end](std::uint64_t x0, std::uint64_t x1) { return x0 < end && off < x1; };
            for (const auto &[x0, x1] : snap_job)
                if (overlaps(x0, x1)) return ~std::uint64_t{0};
            for (const SnapSpan &x : snap_spans)
                if (overlaps(x.start, x.end) && snap_in_flight(x)) return ~std::uint64_t{0};
            return off;
        }
        return ~std::uint64_t{0};
    }
    std::uint64_t snapshot(std::uint64_t a, std::uint32_t bytes, policy::FilterStats &stats) {
        if (snap_ring.empty() && !snap_add(snap_grow ? kSnapFirstBytes : kSnapRingBytes)) return 0;
        if (bytes > kSnapRingBytes / 4) {
            stats.dma_snapshot_overflow++;
            return 0;
        }
        std::uint64_t off = snap_place(((snap_head + 255) & ~std::uint64_t{255}) + (a & 0xffu), a, bytes);
        // exp 0442 bake 1c: no room now: the ring grows (doubles) and the copy goes into the new buffer
        while (off == ~std::uint64_t{0} && snap_grow && snap_size < kSnapRingBytes) {
            const std::uint64_t at = snap_size;
            if (!snap_add(snap_size)) break;
            off = snap_place(at + (a & 0xffu), a, bytes);
        }
        if (off == ~std::uint64_t{0}) {
            stats.dma_snapshot_overflow++;
            return 0;
        }
        const ScratchBo *in = nullptr;
        for (const ScratchBo &c : snap_ring)
            if (off >= c.va - kSnapRingVa && off < c.va - kSnapRingVa + c.size) in = &c;
        const std::uint64_t end = off + bytes;
        std::memcpy(static_cast<std::uint8_t *>(in->cpu) + (off - (in->va - kSnapRingVa)), reinterpret_cast<const void *>(a), bytes);
        snap_head = end;
        snap_job.emplace_back(off, end);
        stats.dma_snapshot_bytes += bytes;
        return kSnapRingVa + off;
    }
    // After the job is on the ring: its copies are kept from being overwritten until it is done.
    // exp 0436: the job's spans and slot are passed in (with the kernel call outside the lock, another ring's job may
    // have been prepared since: `cur` and snap_job are no longer this job's)
    void snap_commit(std::uint64_t seq, int slot, std::vector<std::pair<std::uint64_t, std::uint64_t>> &job) {
        if (job.empty()) return;
        std::erase_if(snap_spans, [this](const SnapSpan &x) { return !snap_in_flight(x); });
        for (const auto &[x0, x1] : job) snap_spans.push_back({x0, x1, slot, seq});
        job.clear();
    }
    void snap_free() {
        for (ScratchBo &s : snap_ring) {
            if (s.cpu) amdgpu_bo_cpu_unmap(s.bo);
            if (s.va && s.bo) amdgpu_bo_va_op_raw(dev, s.bo, 0, s.size, s.va, 0, AMDGPU_VA_OP_UNMAP);
            if (s.bo) amdgpu_bo_free(s.bo);
        }
        snap_ring.clear();
        snap_size = 0;
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

    // Experiment 0381: BC5_DIRECT_DRAW_ARGS_JOURNAL=1 (default off), the GFX jobs' indirect draw
    // arguments read at submit and again at completion or timeout (bc5/draw_args.hpp). CPU reads
    // through process_vm_readv (an unreadable slot is reported, not fatal); no packet is added. The
    // records of a job wait in its slot; the submitting thread fills a slot before the job is
    // queued and the completion thread empties it before the slot is given back.
    bool env_draw_args = false;
    std::vector<draw_args::Rec> da_pending[kSlots];
    draw_args::Limits da_limits;
    draw_args::Counters da;
    std::uint64_t da_loud = 0;
    std::mutex da_mu; // the counters and the line budget: submit and completion run on two threads
    static bool da_read(std::uint64_t a, std::uint32_t (&out)[4]) {
        iovec l{out, sizeof(out)}, r{reinterpret_cast<void *>(a), sizeof(out)};
        return process_vm_readv(getpid(), &l, 1, &r, 1, 0) == static_cast<ssize_t>(sizeof(out));
    }
    void da_submit(const std::vector<draw_args::Rec> &recs, std::uint32_t unbased) {
        std::lock_guard<std::mutex> g(da_mu);
        da.draws += recs.size();
        da.unbased += unbased;
        for (const auto &r : recs)
            if (draw_args::classify(r, da_limits) != 0) da.flagged_submit++;
    }
    // Every record of a timed-out job is printed; otherwise the first 256 flagged ones and then
    // one in 4096, with a summary every 100,000 draws.
    void da_complete(std::uint64_t seq, std::vector<draw_args::Rec> &recs, bool timed_out) {
        if (recs.empty()) return;
        const auto done = draw_args::reread(recs, &Impl::da_read);
        std::lock_guard<std::mutex> g(da_mu);
        if (timed_out) da.timed_out_jobs++;
        for (std::size_t k = 0; k < recs.size(); ++k) {
            const std::uint32_t f0 = draw_args::classify(recs[k], da_limits);
            const std::uint32_t f1 = draw_args::classify(done[k], da_limits);
            if (f1 != 0) da.flagged_done++;
            if (std::memcmp(recs[k].v, done[k].v, sizeof(recs[k].v)) != 0) da.changed++;
            if (timed_out || ((f0 | f1) != 0 && (da_loud++ < 256 || da_loud % 4096 == 0)))
                std::fprintf(stderr, "bc5-direct: exp 0381 %s\n",
                             draw_args::line("submit", seq, recs[k], f0, timed_out ? "timeout" : "done", &done[k], f1).c_str());
        }
        recs.clear();
        if (da.draws >= da_next_summary) {
            da_summary("periodic");
            da_next_summary = da.draws + 100000;
        }
    }
    std::uint64_t da_next_summary = 100000;
    void da_summary(const char *when) { // da_mu held, or at close
        std::fprintf(stderr,
                     "bc5-direct: exp 0381 draw-args %s: %llu draws read (%llu unbased), flagged at submit %llu, at completion %llu, changed %llu, timed-out jobs %llu (limits %u vertices, %u instances)\n",
                     when, static_cast<unsigned long long>(da.draws), static_cast<unsigned long long>(da.unbased),
                     static_cast<unsigned long long>(da.flagged_submit), static_cast<unsigned long long>(da.flagged_done),
                     static_cast<unsigned long long>(da.changed), static_cast<unsigned long long>(da.timed_out_jobs),
                     da_limits.vertices, da_limits.instances);
    }

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
        // exp 0432 (tag s432): the resize by step, and BC5_DIRECT_SLOT_GROW
        static const bool s432_grow = [] {
            const char *e = std::getenv("BC5_DIRECT_SLOT_GROW");
            return !(e != nullptr && e[0] == '0' && e[1] == 0);
        }();
        static std::uint64_t s432_n = 0, s432_bytes = 0;
        static double s432_total = 0, s432_max = 0;
        const std::uint64_t s432_old = scratch.size;
        double s432_t[4] = {now_ms(), 0, 0, 0};
        scratch_free();
        s432_t[1] = now_ms();
        // Exactly the pages needed (dispatch-min's 4 KiB command BO is the configuration known
        // to work; a 1 MiB scratch hung the CP on the second fetch, experiment 0016).
        std::uint64_t size = (bytes + 4095) & ~std::uint64_t{4095};
        if (size == 0) size = 4096;
        if (s432_grow) { // exp 0432 (tag s432): the next power of two, at least 64 KiB
            std::uint64_t p = 65536;
            while (p < size) p <<= 1;
            size = p;
        }
        amdgpu_bo_alloc_request req{};
        req.alloc_size = size;
        req.phys_alignment = 4096;
        req.preferred_heap = AMDGPU_GEM_DOMAIN_GTT;
        if (amdgpu_bo_alloc(dev, &req, &scratch.bo) != 0) return false;
        s432_t[2] = now_ms();
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
        s432_t[3] = now_ms();
        if (amdgpu_bo_cpu_map(scratch.bo, &scratch.cpu) != 0) return false;
        scratch.size = size;
        { // exp 0432 (tag s432)
            const double end = now_ms(), all = end - s432_t[0];
            s432_n++;
            s432_total += all;
            s432_bytes += size;
            if (all > s432_max) s432_max = all;
            if (all > 20.0)
                std::fprintf(stderr, "bc5-direct: exp 0432 (tag s432): slot %d resize %llu -> %llu bytes (asked %llu) took %.1f ms: unmap+free %.1f, alloc %.1f, gpu map %.1f, cpu map %.1f\n",
                             cur, static_cast<unsigned long long>(s432_old), static_cast<unsigned long long>(size), static_cast<unsigned long long>(bytes), all,
                             s432_t[1] - s432_t[0], s432_t[2] - s432_t[1], s432_t[3] - s432_t[2], end - s432_t[3]);
            if (s432_n <= 2 || (s432_n & 63u) == 0)
                std::fprintf(stderr, "bc5-direct: exp 0432 (tag s432): slot grow %s; %llu resizes, %.1f ms in all, longest %.1f ms, %llu KiB allocated in all\n",
                             s432_grow ? "ON" : "off (exact size)", static_cast<unsigned long long>(s432_n), s432_total, s432_max,
                             static_cast<unsigned long long>(s432_bytes >> 10));
        }
        return true;
    }

    // exp 0432 (tag s432): see mkbe432.py, item P
    static bool s432_prealloc() {
        static const bool v = [] {
            const char *e = std::getenv("BC5_DIRECT_SLOT_PREALLOC");
            return !(e != nullptr && e[0] == '0' && e[1] == 0);
        }();
        return v;
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
    if (const char *e = std::getenv("BC5_DIRECT_SHADOW_LABELS"); env_on(e)) { // exp 0442: "=0" is off (was presence only); "count" adds the compare
        d->impl_->env_shadow = true;
        d->impl_->shadow_count = std::strcmp(e, "count") == 0;
    }
    if (const char *e = std::getenv("BC5_DIRECT_DRAW_ARGS_JOURNAL"); e != nullptr && *e != 0 && std::strcmp(e, "0") != 0) {
        d->impl_->env_draw_args = true; // experiment 0381; the limits follow the CP check's (FilterOptions::gpu_check_draw_max)
        std::fprintf(stderr, "bc5-direct: experiment 0381 switch: indirect draw arguments read at submit and at completion or timeout (journal only)\n");
    }
    // "1", or "x_limit[:yz_min]", and since experiment 0442 "count[:...]" (indirect_check::parse_product)
    if (const char *e = std::getenv("BC5_DIRECT_0442_GC_NOCOPY"); e != nullptr && std::strcmp(e, "0") == 0)
        d->impl_->gc_nocopy = false; // experiment 0442 bake 1c (D28)
    if (const char *e = std::getenv("BC5_DIRECT_0442_SNAP_GROW"); e != nullptr && std::strcmp(e, "0") == 0)
        d->impl_->snap_grow = false; // experiment 0442 bake 1c (D28)
    d->impl_->env_product = indirect_check::parse_product(std::getenv("BC5_DIRECT_GPU_CHECK_PRODUCT"), d->impl_->product);
    if (const char *e = std::getenv("BC5_DIRECT_IB_MAX_DW"); e != nullptr && *e != 0) { // experiment 0349
        const std::size_t v = static_cast<std::size_t>(std::strtoull(e, nullptr, 0));
        if (v >= 64 && v <= ib_split::kKernelMaxDwords) d->impl_->ib_max_dw = v;
    }
    std::fprintf(stderr, "bc5-direct: experiment 0349: a job's IB over %zu dwords is cut at aligned packet boundaries outside COND_EXEC ranges into up to %zu IBs of one submit (the kernel takes at most 0xfffff dwords per IB)\n",
                 d->impl_->ib_max_dw, ib_split::kMaxPieces);
    if (d->impl_->env_shadow || d->impl_->env_product)
        std::fprintf(stderr, "bc5-direct: experiment 0341 switches: product staircase %d (x > %u with y or z > %u), shadow labels %d\n",
                     d->impl_->env_product ? 1 : 0, d->impl_->product.x_limit, d->impl_->product.yz_min,
                     d->impl_->env_shadow ? 1 : 0);
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
    if (Impl::s432_prealloc()) { // exp 0432 (tag s432): the large slot buffers, once, before the title maps anything
        const double t0 = now_ms();
        int made = 0, failed = 0;
        std::uint64_t gfx_kib = 256, comp_kib = 256, total_kib = 0; // BC5_DIRECT_SLOT_PREALLOC=<GFX KiB>:<other KiB> sets other sizes
        if (const char *e = std::getenv("BC5_DIRECT_SLOT_PREALLOC"); e != nullptr) {
            unsigned long long a = 0, b = 0;
            if (std::sscanf(e, "%llu:%llu", &a, &b) == 2 && a <= 16384 && b <= 16384) {
                gfx_kib = a;
                comp_kib = b;
            }
        }
        for (int k = 0; k < Impl::kSlots; ++k) {
            d->impl_->cur = k;
            const std::uint64_t want = k < Impl::kGfxSlots ? gfx_kib : comp_kib;
            if (want == 0) continue;
            (d->impl_->scratch_reserve(want << 10) ? made : failed)++;
            total_kib += want;
        }
        d->impl_->cur = Impl::pool_first(kGfxRing);
        std::fprintf(stderr, "bc5-direct: exp 0432 (tag s432): slot prealloc: %d buffers made (%d failed) in %.1f ms: %llu KiB for each of the %d GFX-ring slots, %llu KiB for each of the others, %llu MiB of GTT in all\n", made, failed,
                     now_ms() - t0, static_cast<unsigned long long>(gfx_kib), Impl::kGfxSlots, static_cast<unsigned long long>(comp_kib),
                     static_cast<unsigned long long>(total_kib >> 10));
    }
    return d;
}

Device::~Device() {
    if (!impl_) return;
    std::unique_lock<std::shared_mutex> flight(impl_->flight_mu); // exp 0436: no job of submit() is in its kernel call
    impl_->summary(); // experiment 0341
    impl_->list_drop(impl_->full_list);
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
        // the guest's pages writable instead (sysLinuxVirtual.cpp in the host).
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
    impl_->userptrs.push_back(u);
    impl_->a2_insert({u.va, u.size, u.readonly, false}); // exp 0438 (tag a2)
    impl_->list_gen++;
    return true;
}

bool Device::unmap_userptr(std::uint64_t cpu_va) {
    std::unique_lock<std::shared_mutex> flight(impl_->flight_mu); // exp 0436 (tag su436): after every prepared job's kernel call
    std::lock_guard lock(impl_->mutex);
    for (auto it = impl_->userptrs.begin(); it != impl_->userptrs.end(); ++it) {
        if (it->va == cpu_va) {
            impl_->va_unmap(it->bo, 0, it->size, it->va);
            amdgpu_bo_free(it->bo);
            impl_->a2_erase({it->va, it->size, it->readonly, false}); // exp 0438 (tag a2)
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
    for (const auto &m : impl_->shared_maps) out.push_back({m.va, m.size, m.readonly, true});
    return out;
}

std::shared_ptr<const MappingIndex> Device::sorted_mappings() const {
    std::lock_guard lock(impl_->mutex);
#if defined(BC5_0438_A2_CHECK_BUILD) // exp 0438 (bake438b): A2's compare-only check, private diagnosis builds only
    if (impl_->a2_check) impl_->a2_line(); // exp 0438 (tag a2c438)
#endif // BC5_0438_A2_CHECK_BUILD
    if (impl_->a2 && impl_->sorted != nullptr) { // exp 0438 (tag a2): kept up to date at each edit
#if defined(BC5_0438_A2_CHECK_BUILD) // exp 0438 (bake438b): A2's compare-only check, private diagnosis builds only
        if (impl_->a2_check && (impl_->a2_calls++ & 63u) == 0) {
            impl_->a2_compares++; // exp 0438 (tag a2c438)
            std::vector<Mapping> users;
            for (const auto &u : impl_->userptrs) users.push_back({u.va, u.size, u.readonly, false});
            std::sort(users.begin(), users.end(), [](const Mapping &x, const Mapping &y) { return x.va < y.va; });
            std::vector<Mapping> ref;
            auto u = users.begin();
            for (const auto &m : impl_->shared_maps) {
                while (u != users.end() && u->va < m.va) ref.push_back(*u++);
                ref.push_back({m.va, m.size, m.readonly, true});
            }
            ref.insert(ref.end(), u, users.end());
            bool same = ref.size() == impl_->sorted->size();
            std::size_t at = 0;
            for (const auto &m : *impl_->sorted) {
                if (!same) break;
                const Mapping &r = ref[at];
                if (r.va != m.va || r.size != m.size || r.readonly != m.readonly || r.shared != m.shared) same = false;
                else at++;
            }
            if (!same && impl_->a2_mismatches++ < 20)
                std::fprintf(stderr, "bc5-direct: exp 0438 (tag a2): MISMATCH of the index against a rebuild at element %zu (index %zu, rebuild %zu entries; %llu so far)\n", at,
                             impl_->sorted->size(), ref.size(), static_cast<unsigned long long>(impl_->a2_mismatches));
        }
#endif // BC5_0438_A2_CHECK_BUILD
        return impl_->sorted;
    }
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
            out->push_back({m.va, m.size, m.readonly, true});
        }
        out->insert(out->end(), u, users.end());
        impl_->sorted = std::make_shared<const MappingIndex>(std::move(*out)); // exp 0438 (tag a2): one chunk
#if defined(BC5_0438_A2_CHECK_BUILD) // exp 0438 (bake438b): A2's compare-only check, private diagnosis builds only
        impl_->a2_rebuilds++; // exp 0438 (tag a2c438)
#endif // BC5_0438_A2_CHECK_BUILD
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
    return map_shared(id, bo_offset, size, gpu_va, false); // exp 0412 (tag k1r412)
}

bool Device::map_shared(std::uint32_t id, std::uint64_t bo_offset, std::uint64_t size, std::uint64_t gpu_va, bool readonly) {
    std::lock_guard lock(impl_->mutex);
    if (size == 0 || ((bo_offset | size | gpu_va) & 0xfff) != 0) return false;
    SharedBo *b = impl_->shared_bo_locked(id);
    if (b == nullptr || bo_offset + size > b->size) return false;
    const int rc = impl_->va_map(b->bo, bo_offset, size, gpu_va,
                                 readonly ? AMDGPU_VM_PAGE_READABLE // exp 0412 (tag k1r412)
                                          : AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_WRITEABLE | AMDGPU_VM_PAGE_EXECUTABLE);
    if (rc != 0) {
        std::fprintf(stderr, "bc5-direct: shared map at 0x%llx+0x%llx: %d\n",
                     static_cast<unsigned long long>(gpu_va), static_cast<unsigned long long>(size), rc);
        return false;
    }
    // Experiment 0170: kept sorted by address (after any equal address, as push_back did).
    const auto at = std::upper_bound(impl_->shared_maps.begin(), impl_->shared_maps.end(), gpu_va,
                                     [](std::uint64_t va, const SharedMap &m) { return va < m.va; });
    impl_->shared_maps.insert(at, SharedMap{gpu_va, size, bo_offset, id, b->bo, readonly});
    impl_->a2_insert({gpu_va, size, readonly, true}); // exp 0438 (tag a2)
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
    std::unique_lock<std::shared_mutex> flight(impl_->flight_mu); // exp 0436 (tag su436): after every prepared job's kernel call
    std::lock_guard lock(impl_->mutex);
    // Experiment 0170: binary search in the sorted list (the first mapping at that address, as
    // the old walk found).
    const auto it = std::lower_bound(impl_->shared_maps.begin(), impl_->shared_maps.end(), gpu_va,
                                     [](const SharedMap &m, std::uint64_t va) { return m.va < va; });
    if (it == impl_->shared_maps.end() || it->va != gpu_va) return false;
    impl_->va_unmap(it->bo, it->bo_offset, it->size, it->va);
    if (SharedBo *b = impl_->shared_bo_locked(it->id); b != nullptr && b->maps != 0) b->maps--;
    impl_->a2_erase({it->va, it->size, it->readonly, true}); // exp 0438 (tag a2)
    impl_->shared_maps.erase(it);
    impl_->list_gen++;
    return true;
}

bool Device::free_shared(std::uint32_t id) {
    std::unique_lock<std::shared_mutex> flight(impl_->flight_mu); // exp 0436 (tag su436): after every prepared job's kernel call
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
        impl_->sorted = nullptr; // exp 0438 (tag a2): many maps went at once; the next call rebuilds
#if defined(BC5_0438_A2_CHECK_BUILD) // exp 0438 (bake438b): A2's compare-only check, private diagnosis builds only
        impl_->a2_drops++; // exp 0438 (tag a2c438)
#endif // BC5_0438_A2_CHECK_BUILD
        b->maps = 0;
        // a kept list would hold the BO (and its pages) alive
        if (impl_->full_list) {
            impl_->list_drop(impl_->full_list); // exp 0436: no job can hold it here (flight_mu is ours)
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

// Experiment 0430 (F4): the calling thread's extra CS dependencies for its next submit(), consumed by it.
constexpr std::uint32_t kMaxNextDeps = 8;
static thread_local std::vector<std::pair<int, std::uint64_t>> t_next_deps;
void Device::add_next_submit_dependency(int ring, std::uint64_t seq_no) {
    if (t_next_deps.size() < kMaxNextDeps) t_next_deps.emplace_back(ring, seq_no);
}

SubmitResult Device::submit(std::span<const std::uint32_t> ib, const policy::FilterOptions &opt,
                            std::uint64_t timeout_ns, bool with_gds, int ring) {
    return submit_impl(ib, opt, timeout_ns, with_gds, ring, nullptr);
}

SubmitResult Device::submit(std::span<const std::uint32_t> ib, const policy::FilterOptions &opt,
                            std::uint64_t timeout_ns, bool with_gds, int ring, const std::function<void()> &before_call) {
    return submit_impl(ib, opt, timeout_ns, with_gds, ring, &before_call);
}

SubmitResult Device::submit_impl(std::span<const std::uint32_t> ib, const policy::FilterOptions &opt,
                                 std::uint64_t timeout_ns, bool with_gds, int ring,
                                 const std::function<void()> *before_call) {
    SubmitResult r;
    // Experiment 0436 (tag su436): with before_call in async mode the kernel call runs without `mutex` (see direct.hpp).
    const bool split = before_call != nullptr && async_;
    std::shared_lock<std::shared_mutex> flight;
    if (split) flight = std::shared_lock<std::shared_mutex>(impl_->flight_mu);
    std::unique_lock lock(impl_->mutex);
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
    const int cur = impl_->cur; // exp 0436: this job's slot (impl_->cur moves on with another ring's job once the lock is let go)
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
    std::vector<std::uint64_t> shadow_vas; // experiment 0442: the title's label of each slot (count mode)
    if (impl_->env_shadow && !comp) {
        shadow_labels::Stats sst;
        const bool ok = shadow_labels::apply(main_out, Impl::kShadowSlots, sst, impl_->shadow_count ? &shadow_vas : nullptr);
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
    if (opt.mec_indirect_base != 0 && !opt.gpu_check_indirect && !comp) {
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
    std::vector<draw_args::Rec> da_recs; // experiment 0381: the indirect draws' arguments as the host sees them now
    if (impl_->env_draw_args && !comp) {
        std::uint32_t unbased = 0;
        da_recs = draw_args::scan(main_out, opt.mec_indirect_base, &Impl::da_read, &unbased);
        impl_->da_limits.vertices = opt.gpu_check_draw_max[0];
        impl_->da_limits.instances = opt.gpu_check_draw_max[1];
        impl_->da_submit(da_recs, unbased);
    }
    if (opt.gpu_check_indirect && (!impl_->gc_nocopy || indirect_check::any_checked(main_out, comp))) { // exp 0442 bake 1c
        indirect_check::Stats st;
        std::uint32_t check_max[3] = {opt.gpu_check_max[0], opt.gpu_check_max[1], opt.gpu_check_max[2]};
        if (impl_->env_yz) indirect_check::tighten(check_max, impl_->yz); // experiment 0380
        main_out = indirect_check::apply(main_out, opt.mec_indirect_base, check_max,
                                         opt.gpu_check_draw_max, flag_refs, st, comp,
                                         impl_->env_product && !comp ? &impl_->product : nullptr, // experiment 0341
                                         impl_->env_zero, impl_->env_force_start,
                                         impl_->env_args_copy, impl_->env_args_wb, impl_->args_slot_va, // experiment 0380
                                         impl_->env_args_flush, impl_->env_flush_draws); // experiment 0380 (F617)
        impl_->product_sum += st.product_checked;
        impl_->zero_sum += st.zero_checked;
        impl_->start_forced_sum += st.start_forced;
        impl_->args_copied_sum += st.args_copied;
        impl_->args_wb_sum += st.args_written_back;
        impl_->args_flush_sum += st.args_flushed; // experiment 0380 (F617)
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
    // experiment 0442: this job's count records (0 = none), read by finish() before the slot is given back
    impl_->would_off[cur] = impl_->env_product && impl_->product.count && !comp && !flag_refs.empty()
                                ? static_cast<std::uint32_t>(flag_off + indirect_check::kWouldByte / 4) : 0;
    impl_->shadow_cmp_off[cur] = impl_->shadow_count && shadow_slots != 0 ? static_cast<std::uint32_t>(shadow_off) : 0;
    impl_->shadow_cmp_vas[cur] = impl_->shadow_count && shadow_slots != 0 ? shadow_vas : std::vector<std::uint64_t>{};
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
    for (const ScratchBo &c : impl_->snap_ring) bos.push_back(c.bo); // experiment 0122 (exp 0442 bake 1c: its buffers)
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
            impl_->list_drop(impl_->full_list); // exp 0436: one a job still uses in its kernel call is destroyed by it
            impl_->full_list = list;
            impl_->full_list_gen = impl_->list_gen;
            impl_->full_list_gds = with_gds;
            impl_->full_list_count = r.bo_count;
        }
    }
    r.list_ms = now_ms() - t_list;
    if (r.rc != 0) return r;
    // exp 0436: the kept list this job uses stays alive until its kernel call has returned
    const bool list_held = split && list != nullptr && list == impl_->full_list;
    if (list_held) impl_->list_users[list]++;
    auto list_done = [&]() {
        if (list_held) {
            auto it = impl_->list_users.find(list);
            if (--it->second == 0) {
                impl_->list_users.erase(it);
                if (list != impl_->full_list) amdgpu_bo_list_destroy(list); // replaced meanwhile: its last user
            }
        } else if (list != impl_->full_list) {
            amdgpu_bo_list_destroy(list);
        }
    };

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
    amdgpu_cs_fence deps[kComputeRings + kMaxNextDeps]{};
    std::uint32_t n_deps = 0;
    if ((ring_deps_ & (comp ? 1 : 2)) != 0) { // set_ring_deps
        if (comp) {
            if (const std::uint64_t seq = impl_->last_seq.load(); seq != 0) deps[n_deps++] = impl_->fence_of(kGfxRing, seq);
        } else {
            for (int k = 0; k < kComputeRings; ++k) {
                if (const std::uint64_t seq = impl_->last_seq_comp[k].load(); seq != 0) deps[n_deps++] = impl_->fence_of(k, seq);
            }
        }
    }
    for (const auto &[dring, dseq] : t_next_deps) { // experiment 0430 (F4): add_next_submit_dependency
        if (dseq != 0 && n_deps < kComputeRings + kMaxNextDeps) deps[n_deps++] = impl_->fence_of(dring, dseq);
    }
    t_next_deps.clear();
    if (n_deps != 0) {
        req.number_of_dependencies = n_deps;
        req.dependencies = deps;
    }

    std::vector<std::pair<std::uint64_t, std::uint64_t>> snap_mine; // exp 0436: this job's DMA snapshot spans
    snap_mine.swap(impl_->snap_job);
    if (split) { // exp 0436 (tag su436): the kernel call without the lock; the caller keeps this ring's order
        lock.unlock();
        (*before_call)();
    }
    const double t0 = now_ms();
    r.rc = amdgpu_cs_submit(impl_->ctx, 0, &req, 1);
    if (split) lock.lock();
    if (r.rc != 0) // experiment 0348: amdgpu_cs refuses an IB over 0xfffff dwords (amdgpu_cs.c, amdgpu_cs_p2_ib)
        std::fprintf(stderr, "bc5-direct: cs refused rc %d: the job's IB is %zu dwords (%zu from the title's %zu) in %u IBs, %u BOs; the kernel takes at most 0xfffff dwords per IB\n",
                     r.rc, padded, main_n, ib.size(), n_ibs, r.bo_count);
    r.cs_ms = now_ms() - t0;
    std::uint32_t expired = 0;
    r.seq_no = req.seq_no;
    if (async_) {
        r.slot = static_cast<std::uint32_t>(cur);
        r.pending = r.rc == 0;
        if (r.pending) {
            if (!da_recs.empty()) impl_->da_pending[cur] = std::move(da_recs); // experiment 0381, read in finish()
            impl_->slot_seq[cur] = req.seq_no;
            (comp ? impl_->last_seq_comp[ring] : impl_->last_seq) = req.seq_no;
            impl_->snap_commit(req.seq_no, cur, snap_mine); // experiment 0122
        }
        r.submit_ms = now_ms() - t0;
        list_done();
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
        impl_->da_complete(req.seq_no, da_recs, r.timed_out); // experiment 0381 (empty unless the switch is on)
    }
    r.submit_ms = now_ms() - t0;
    r.fence_ms = r.submit_ms - r.cs_ms;
    list_done();
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
    if ((r.ok || r.timed_out) && slot < static_cast<std::uint32_t>(Impl::kSlots)) // experiment 0381
        impl_->da_complete(seq_no, impl_->da_pending[slot], r.timed_out);
    if (r.ok) impl_->read_job_ts(slot, r); // experiment 0124, before the slot is given back
    if (r.ok) impl_->read_counts(slot, seq_no); // experiment 0442, the same
    if (r.ok && slot < static_cast<std::uint32_t>(Impl::kSlots)) impl_->slot_seq[slot] = 0;
    return r;
}

} // namespace bc5::direct
