// SPDX-License-Identifier: GPL-2.0-only
// libSceAgcDriver re-creation: queues and command-buffer submission.
//
// Graphics command buffers go to the kernel through ioctls (the kernel owns the graphics ring;
// the first submit after a ring reset is preceded by a "prologue" that loads the default state).
// Compute command buffers are written as two INDIRECT_BUFFER packets straight into the queue's
// user-mapped ring, after which the new write pointer is stored to the queue's doorbell slot.
// Suspend-point buffers are not run at once: they are queued and sent at the head of the next
// graphics submission.
//
// PM4: INDIRECT_BUFFER is opcode 0x3F and NOP 0x10 (Mesa src/amd/common/sid.h @ ab2374a,
// PKT3_INDIRECT_BUFFER / PKT3_NOP; header = type 3, count in bits 16..29, opcode in bits 8..15,
// PKT3() in the same file). The 0x00800000 bit of an INDIRECT_BUFFER's size dword in the compute
// rings and CONTEXT_CONTROL (0x28, sid.h PKT3_CONTEXT_CONTROL) payloads are per the original
// module's behaviour (clean-room description, see src/reimpl/PROVENANCE.md); TODO(verify) the
// meaning of that bit (a "valid" flag).
#include "bc5/reimpl/agc_driver_internal.hpp"

#include <array>
#include <cstdio>
#include <cstring>
#include <thread>

#if defined(_MSC_VER) && (defined(_M_X64) || defined(_M_IX86))
#include <intrin.h>
#endif

namespace bc5::reimpl::agc_driver {
namespace detail {
namespace {

constexpr std::uint32_t kIbHeader = 0xC0023F00u; // INDIRECT_BUFFER, 3 body dwords
constexpr std::uint32_t kComputeIbValid = 0x00800000u;
constexpr std::uint32_t kMagicMe1 = 0x0769C766u, kMagicPipe1 = 0x72E8E3C1u,
                        kMagicQueue1 = 0xDB72AF28u, kMagicVqid1 = 0xD245ED58u;
constexpr std::uint32_t kMagicMe2 = 0xAF1E80B7u, kMagicPipe2 = 0x8B4CDD90u,
                        kMagicQueue2 = 0x99F68D6Cu, kMagicVqid2 = 0xE5FCC174u;
constexpr std::uint32_t kSpecialQueueId = 0x5D;
constexpr std::uint32_t kSpecialQueueIndex = 5; // in the system table

void cpu_relax() {
#if defined(_MSC_VER) && (defined(_M_X64) || defined(_M_IX86))
    _mm_pause();
#elif (defined(__GNUC__) || defined(__clang__)) && (defined(__x86_64__) || defined(__i386__))
    __builtin_ia32_pause();
#else
    std::this_thread::yield();
#endif
}

std::uint32_t queue_me(std::uint32_t id) { return (id >> 5) & 3u; }
std::uint32_t queue_pipe(std::uint32_t id) { return (id >> 3) & 3u; }
std::uint32_t queue_index(std::uint32_t id) { return id & 7u; }

// Per-vqid record in the GPU-info area.
std::uint64_t queue_record(std::uint32_t vqid) {
    return g_state.gpu_info + 0xB6450u + static_cast<std::uint64_t>(vqid - 1u) * 0x20u;
}

// Maps a compute queue through the kernel (ioctl 0xC0408121) and returns its doorbell slot.
bool map_compute_queue(std::uint32_t me, std::uint32_t pipe, std::uint32_t queue,
                       std::uint64_t ring, std::uint32_t ring_log2, std::uint32_t vqid,
                       std::uint64_t rptr, std::uint64_t *doorbell_out, std::uint32_t extra,
                       int *rc_out) {
    const bool magic1 = me == kMagicMe1 && pipe == kMagicPipe1 && queue == kMagicQueue1;
    const bool magic2 = me == kMagicMe2 && pipe == kMagicPipe2 && queue == kMagicQueue2;
    const std::uint32_t eop_offset =
        magic1 ? 0x38000u
        : magic2
            ? 0x39000u
            : (pipe + me * 4u) * 0x8000u - 0x20000u + queue * 0x1000u; // u32 arithmetic
    MapQueueArgs a{};
    a.me = me;
    a.pipe = pipe;
    a.queue = queue;
    a.vqid = vqid;
    a.ring_base = ring;
    a.rptr_report = rptr;
    a.doorbell_page = g_state.doorbell_page;
    a.ring_size_log2 = ring_log2;
    a.extra = extra;
    a.eop_address = g_state.umd.eop_fifo + eop_offset;
    a.eop_size = 0x1000;
    const int rc = gc_ioctl(kIoctlMapComputeQueue, &a);
    *rc_out = rc;
    if (rc != 0) {
        return false;
    }
    const std::uint32_t d = magic1   ? 0x1E0u
                            : magic2 ? 0x1E8u
                                     : ((queue - 0x20u) + (pipe + me * 4u) * 8u) * 8u;
    *doorbell_out = g_state.doorbell_page + d;
    const bool skip_record = (magic1 && vqid == kMagicVqid1) || (magic2 && vqid == kMagicVqid2);
    // deviation: UB in the original for vqid 0 or >= 256 (out-of-bounds record / array writes).
    if (!skip_record && vqid >= 1 && vqid < 256) {
        if (g_state.gpu_info != 0) {
            const std::uint64_t r = queue_record(vqid);
            put_u32(r + 0x00, 1);
            put_u32(r + 0x04, vqid);
            put_u32(r + 0x08, me * 4u + pipe - 4u);
            put_u32(r + 0x0C, queue);
            put_u32(r + 0x10, ring_log2);
            put_u32(r + 0x14, extra);
            put_u64(r + 0x18, ring);
        }
        g_state.last_wptr[vqid] = 0;
    }
    return true;
}

std::uint32_t entry_vqid(const ComputeQueueEntry *e) {
    if (e >= g_state.compute_game && e < g_state.compute_game + kGameQueues) {
        return static_cast<std::uint32_t>(e - g_state.compute_game) + 1u;
    }
    return static_cast<std::uint32_t>(e - g_state.compute_sys) + 1u;
}

// Appends {seq, vqid, previous wptr, new wptr} to the GPU-info compute submit log.
void log_compute_submit(std::uint32_t vqid, std::uint32_t new_wptr, std::uint64_t seq) {
    if (vqid >= 0x100 || g_state.gpu_info == 0) {
        return;
    }
    const std::uint64_t g = g_state.gpu_info;
    std::uint32_t index = 0;
    std::uint32_t count = 0;
    std::memcpy(&index, at<void>(g + 0xB6444), 4);
    std::memcpy(&count, at<void>(g + 0xB6448), 4);
    index %= 64u;
    const std::uint64_t e = g + 0xB6C50u + static_cast<std::uint64_t>(index) * 0x18u;
    put_u64(e + 0x00, seq);
    put_u32(e + 0x08, vqid);
    put_u32(e + 0x0C, g_state.last_wptr[vqid]);
    put_u32(e + 0x10, new_wptr);
    put_u32(g + 0xB6444, (index + 1u) % 64u);
    put_u32(g + 0xB6448, count < 64u ? count + 1u : 64u);
    g_state.last_wptr[vqid] = new_wptr;
}

// Appends {seq, counter, ib count, flags} to the ring-0 or other-ring graphics submit log.
void log_gfx_submit(bool ring0, std::uint64_t seq, std::uint64_t counter, std::uint32_t ib_count,
                    std::uint32_t flags) {
    const std::uint64_t g = g_state.gpu_info;
    if (g == 0) {
        return;
    }
    const std::uint64_t cap_at = ring0 ? 0xB72ECu : 0xBF2FCu;
    const std::uint64_t index_at = ring0 ? 0xB72F0u : 0xBF300u;
    const std::uint64_t entries_at = ring0 ? 0xB72F8u : 0xBF308u;
    std::uint32_t cap = 0;
    std::uint32_t index = 0;
    std::memcpy(&cap, at<void>(g + cap_at), 4);
    std::memcpy(&index, at<void>(g + index_at), 4);
    if (cap == 0 || cap > (ring0 ? 0x400u : 0x200u)) {
        return; // the log header was overwritten; keep inside the area
    }
    index %= cap;
    const std::uint64_t e = g + entries_at + static_cast<std::uint64_t>(index) * 0x20u;
    put_u64(e + 0x00, seq);
    put_u64(e + 0x08, counter);
    put_u32(e + 0x10, ib_count);
    put_u32(e + 0x14, flags);
    put_u32(g + index_at, (index + 1u) % cap);
}

// Counts a graphics submit and appends it to the matching ring log.
// TODO(verify): which values fill the log entry's {seq, counter, ib count, flags} is our choice.
void count_submit(bool ring0, const QueueHandle &h, std::uint32_t ib_count) {
    const std::uint64_t counter = ring0 ? ++g_state.gfx_ring0_submits : ++g_state.gfx_other_submits;
    log_gfx_submit(ring0, h.seq, counter, ib_count, h.flags);
}

// --- compute rings --------------------------------------------------------------------------

std::int32_t compute_write(QueueHandle *h, const SubmitPair *pairs, std::uint32_t n) {
    auto *e = at<ComputeQueueEntry>(h->entry);
    // deviation: UB in the original when the queue was never mapped (null ring / report / slot).
    if (e == nullptr || e->ring_base == 0 || e->rptr_report == 0 || e->doorbell_slot == 0 ||
        e->ring_size < 4u * 8u * (n + 1u)) {
        return kErrInvalid;
    }
    const std::uint32_t ring_dw = e->ring_size / 4u;
    const std::uint32_t w0 = e->wptr_dw % ring_dw;
    const std::uint32_t need = n * 8u;
    // Busy-wait for room; r == w means empty. There is no timeout.
    for (;;) {
        const std::uint32_t r = *static_cast<volatile const std::uint32_t *>(
            at<const std::uint32_t>(e->rptr_report));
        const std::uint32_t free_dw = (r - w0) + ((r >= w0 && r != w0) ? 0u : ring_dw);
        if (free_dw > need) {
            break;
        }
        cpu_relax();
    }
    auto *ring = at<std::uint32_t>(e->ring_base);
    const std::uint64_t empty_ib = region_addr(3);
    std::uint32_t w = w0;
    for (std::uint32_t i = 0; i < n; ++i) {
        const SubmitPair &p = pairs[i];
        std::uint64_t a_addr = p.a.address;
        std::uint32_t a_size = p.a.size_dw & 0xFFFFFu;
        if (a_addr == 0) {
            a_addr = empty_ib;
            a_size = 2;
        }
        const std::uint64_t b_addr = p.b.address;
        const std::uint32_t b_size = b_addr != 0 ? (p.b.size_dw & 0xFFFFFu) : 0u;
        const std::uint32_t dws[8] = {kIbHeader, lo32(a_addr), hi16(a_addr), a_size | kComputeIbValid,
                                      kIbHeader, lo32(b_addr), hi16(b_addr), b_size | kComputeIbValid};
        for (std::uint32_t k = 0; k < 8; ++k) {
            ring[(w + k) % ring_dw] = dws[k];
        }
        w = (w + 8u) % ring_dw;
    }
    e->wptr_dw = w;
    log_compute_submit(h->queue_id - 0x1Fu, w, h->seq);
    *static_cast<volatile std::uint32_t *>(at<std::uint32_t>(e->doorbell_slot)) = w;
    return kOk;
}

// --- graphics, compositor process: direct IB packets -----------------------------------------

DirectIbPacket direct_packet(const CommandBufferDesc &d) {
    return DirectIbPacket{{kIbHeader, lo32(d.address), hi16(d.address), d.size_dw & 0xFFFFFu}};
}

std::int32_t compositor_submit(QueueHandle *h, const SubmitPair *pairs, std::uint32_t n) {
    RingSelectArgs sel{3, 0};
    (void)gc_ioctl(kIoctlRingSelect, &sel);
    std::array<DirectIbPacket, 256> packets{};
    std::uint32_t count = 0;
    for (std::uint32_t i = 0; i < n && count + 2 <= packets.size(); ++i) {
        if (pairs[i].a.address != 0) {
            packets[count++] = direct_packet(pairs[i].a);
        }
        packets[count++] = direct_packet(pairs[i].b);
    }
    int rc = 0;
    if (h->direct_tag == 0) {
        DirectSubmitArgs a{3, count, addr_of(packets.data())};
        rc = gc_ioctl(kIoctlDirectSubmit, &a);
    } else {
        DirectSubmitTaggedArgs a{h->direct_tag, 3, count, 0, addr_of(packets.data())};
        rc = gc_ioctl(kIoctlDirectSubmitTagged, &a);
    }
    return rc == 0 ? kOk : kErrDirectSubmit;
}

// --- graphics, game process: kernel graphics ring --------------------------------------------

bool send_prologue(std::uint32_t ring_id, std::uint32_t k) {
    const DefaultStateCb &d = k == 0 ? g_state.defstate_gfx : g_state.defstate_agr;
    GfxPrologueArgs a{};
    a.ring = ring_id;
    std::uint32_t *p = a.pm4;
    *p++ = 0xC0012800u; // CONTEXT_CONTROL {0, 0}
    *p++ = 0;
    *p++ = 0;
    *p++ = kIbHeader; // the ring's default-state CB
    *p++ = lo32(d.address);
    *p++ = hi16(d.address);
    *p++ = d.size_dw | (static_cast<std::uint32_t>(d.policy & 3u) << 28);
    *p++ = 0; // optional extra IB slot, never used
    *p++ = 0;
    *p++ = 0;
    *p++ = 0;
    const std::uint64_t empty_ib = region_addr(3);
    if (empty_ib != 0) {
        *p++ = kIbHeader;
        *p++ = lo32(empty_ib);
        *p++ = hi16(empty_ib);
        *p++ = 2;
    } else {
        *p++ = 0xC0021000u; // NOP over the slot
        *p++ = 0;
        *p++ = 0;
        *p++ = 0;
    }
    a.result = 1;
    a.extra_ib_used = 0;
    const int rc = gc_ioctl(kIoctlGfxPrologue, &a);
    g_state.gfx_last_result = a.result;
    if (rc != 0 || a.result != 0) {
        return false;
    }
    ++g_state.prologue_sent[k];
    g_state.gfx_ib_total = 0;
    return true;
}

void to_ib_entry(const CommandBufferDesc &d, std::uint32_t flag_bit, GraphicsIbEntry &out) {
    out = {};
    if (d.address != 0) {
        out.addr_lo = lo32(d.address);
        out.addr_hi = hi16(d.address);
        out.size_dw = d.size_dw & 0xFFFFFu;
    }
    out.flags = flag_bit;
}

std::uint32_t five_c(std::uint32_t last) { return last == 0x5Cu ? 1u : 0u; }

// pairs == nullptr: flush the pending suspend-point pair only.
std::int32_t gfx_submit(QueueHandle *h, const SubmitPair *pairs, std::uint32_t n) {
    const std::uint32_t k = h->queue_id == 4 ? 1u : 0u;
    const bool flush = pairs == nullptr;
    std::array<SubmitPair, 130> list{};
    std::uint32_t count = 0;
    if (g_state.prologue_sent[k] == 0) {
        if (!send_prologue(h->queue_id, k)) {
            return static_cast<std::int32_t>(static_cast<std::uint32_t>(kErrGfxPrologue) |
                                             five_c(g_state.gfx_last_result));
        }
        list[count++] = g_state.pending_suspend[k];
        g_state.pending_suspend[k] = {};
    } else if (flush) {
        list[count++] = g_state.pending_suspend[k];
        g_state.pending_suspend[k] = {};
    }
    if (!flush) {
        for (std::uint32_t i = 0; i < n && count < list.size(); ++i) {
            list[count++] = pairs[i];
        }
    }
    std::array<GraphicsIbEntry, 260> entries{};
    const std::uint32_t b_flag = (h->flags >> 17) & 1u;
    for (std::uint32_t i = 0; i < count; ++i) {
        to_ib_entry(list[i].a, 0, entries[2 * i]);
        to_ib_entry(list[i].b, b_flag, entries[2 * i + 1]);
    }
    const std::uint32_t ib_count = count * 2;
    count_submit(h->queue_id == 0, *h, ib_count);
    GfxSubmitArgs a{h->queue_id, ib_count, addr_of(entries.data()), 1, 0};
    const int rc = gc_ioctl(kIoctlGfxSubmit, &a);
    g_state.gfx_ib_total += ib_count;
    g_state.gfx_last_result = a.result;
    if (rc == 0 && a.result == 0) {
        return kOk;
    }
    if (flush) {
        return kErrDirectSubmit;
    }
    return static_cast<std::int32_t>(static_cast<std::uint32_t>(kErrGfxSubmit) |
                                     five_c(g_state.gfx_last_result));
}

std::int32_t suspend_point_impl(QueueHandle *h, const SubmitPair *pair, std::uint32_t *status_out) {
    const std::uint32_t k = h->queue_id == 4 ? 1u : 0u;
    if (g_state.pending_suspend[k].b.address != 0) {
        (void)gfx_submit(h, nullptr, 0);
    }
    g_state.pending_suspend[k] = *pair;
    if (g_state.prologue_sent[k] != 0) {
        GfxSuspendArgs s{h->queue_id, 1};
        (void)gc_ioctl(kIoctlGfxSuspend, &s);
        ++g_state.gfx_reset_count;
        g_state.gfx_last_result = s.result;
        g_state.prologue_sent[k] = 0;
    }
    if (h->queue_id != 4) {
        SuspendCheckArgs c{0, h->suspend_arg, 0};
        const int rc = gc_ioctl(kIoctlSuspendCheck, &c);
        if (rc != 0) {
            drv_log("suspend check failed = 0x%08x", static_cast<unsigned>(rc));
            return kErrSuspendCheck;
        }
        if (status_out != nullptr) { // deviation: the original writes without a null check
            *status_out = c.status;
        }
        g_state.suspend_status = c.out;
        record_event_time();
    }
    return kOk;
}

SubmitPair pair_from(const CommandBufferDesc *desc) {
    SubmitPair p{};
    p.b.address = desc->address;
    p.b.size_dw = desc->size_dw;
    p.b.flags = static_cast<std::uint8_t>(desc->flags & 3u);
    return p;
}

// Common front end of the single submits: lock, sequence, pre-submit hooks (only a no-op one can
// exist), implementation, unlock.
std::int32_t submit_front(QueueHandle *h, const CommandBufferDesc *desc, std::uint32_t tag_bits,
                          std::uint64_t tag) {
    // deviation: UB in the original for a null handle or descriptor.
    if (h == nullptr || desc == nullptr) {
        return kErrInvalid;
    }
    const std::int32_t lr = mutex_lock(h);
    if (lr < 0) {
        drv_log("submit failed: unable to lock (%d)", lr);
        return kErrQueueLock;
    }
    if (lr > 0) {
        return kErrQueueLock;
    }
    const SubmitPair pair = pair_from(desc);
    h->seq = g_submit_seq.fetch_add(1);
    ++h->submit_count;
    h->batch_first = 0;
    h->batch_left = 0;
    if (tag_bits == 0) {
        h->flags &= ~3u;
    } else {
        h->flags |= tag_bits;
    }
    h->tag = tag;
    const std::int32_t result = submit_single_impl(h, &pair);
    if (mutex_unlock(h) < 0) {
        drv_log("submit failed: unlock error");
    }
    return result;
}

std::int32_t multi_submit(QueueHandle *h, const std::uint64_t *addrs, const std::uint32_t *sizes,
                          std::uint32_t count) {
    if (count == 0) {
        return kErrMultiZero;
    }
    // deviation: UB in the original for null pointers.
    if (h == nullptr || addrs == nullptr || sizes == nullptr) {
        return kErrInvalid;
    }
    const std::int32_t lr = mutex_lock(h);
    if (lr < 0) {
        drv_log("submit failed: unable to lock (%d)", lr);
        return kErrQueueLock;
    }
    if (lr > 0) {
        return kErrQueueLock;
    }
    h->seq = g_submit_seq.fetch_add(1);
    ++h->submit_count;
    h->flags &= ~3u;
    h->tag = 0;
    h->batch_first = 0;
    h->batch_left = count;
    std::int32_t result = kOk;
    std::uint32_t done = 0;
    while (done < count) {
        const std::uint32_t n = count - done < 128u ? count - done : 128u;
        std::array<SubmitPair, 128> batch{};
        for (std::uint32_t i = 0; i < n; ++i) {
            batch[i].b.address = addrs[done + i];
            batch[i].b.size_dw = sizes[done + i];
        }
        result = submit_multi_impl(h, batch.data(), n);
        if (result != kOk) {
            break;
        }
        h->batch_first += 128;
        h->batch_left -= n;
        done += n;
    }
    if (mutex_unlock(h) < 0) {
        drv_log("submit failed: unlock error");
    }
    return result;
}

void mutex_destroy(QueueHandle *h) {
    if (g_imports.mutex_destroy != nullptr) {
        g_imports.mutex_destroy(&h->mutex);
    }
}

} // namespace

std::int32_t mutex_lock(QueueHandle *handle) {
    return g_imports.mutex_lock != nullptr ? g_imports.mutex_lock(&handle->mutex) : -1;
}

std::int32_t mutex_unlock(QueueHandle *handle) {
    return g_imports.mutex_unlock != nullptr ? g_imports.mutex_unlock(&handle->mutex) : -1;
}

void mutex_init_if_needed(QueueHandle *handle) {
    if (handle->mutex_ready != 0 || g_imports.mutex_init == nullptr) {
        return;
    }
    char name[32];
    std::snprintf(name, sizeof name, "SceAgcSubmitMtx%02d\n", static_cast<int>(handle->queue_id));
    g_imports.mutex_init(&handle->mutex, nullptr, name);
    handle->mutex_ready = 1;
}

ComputeQueueEntry *compute_entry_for_id(std::uint32_t queue_id) {
    if (queue_id < 0x20) {
        return nullptr;
    }
    if (queue_id < 0x58) {
        return &g_state.compute_game[queue_id - 0x20];
    }
    if (queue_id - 0x58 < kSysQueues) {
        return &g_state.compute_sys[queue_id - 0x58];
    }
    return nullptr;
}

std::int32_t submit_single_impl(QueueHandle *handle, const SubmitPair *pair) {
    return submit_multi_impl(handle, pair, 1);
}

std::int32_t submit_multi_impl(QueueHandle *handle, const SubmitPair *pairs, std::uint32_t count) {
    if (handle->queue_id >= 0x20) {
        return compute_write(handle, pairs, count);
    }
    if (g_state.client_type == 1) {
        return compositor_submit(handle, pairs, count);
    }
    return gfx_submit(handle, pairs, count);
}

std::int32_t create_queue(std::uint32_t queue_id, QueueHandle **handle_out, const void *config,
                          char force) {
    if (handle_out == nullptr) {
        return kErrInvalid;
    }
    const std::uint32_t me = queue_me(queue_id);
    if (me == 3) {
        return kErrInvalid;
    }
    if (me == 0) {
        if (g_state.client_type == 1 && g_state.gc_closed_for_reset != 0) {
            if (!gc_reopen()) {
                drv_log("cannot initialise the GPU for the compositor (%i)", g_state.gc_fd);
                return kErrGeneric;
            }
            g_state.gc_closed_for_reset = 0;
            drv_log("gc re-opened, handle=%d", g_state.gc_fd);
        }
        QueueHandle *h = queue_id == 4 ? &g_state.gfx_agr : &g_state.gfx_main;
        h->flags = 0;
        h->suspend_arg = 0;
        h->queue_id = queue_id;
        h->struct_size = 0x38;
        h->direct_tag = 0;
        h->entry = 0;
        if (config == nullptr) {
            h->flags = kQueueKernelFlag;
        } else {
            std::memcpy(static_cast<void *>(h), config, 0x38);
        }
        mutex_init_if_needed(h);
        *handle_out = h;
        return kOk;
    }
    ComputeQueueEntry *table = g_state.active_table;
    // deviation: UB in the original when no table was chosen (a process that is neither a game
    // nor a compositor).
    if (table == nullptr) {
        drv_log("invalid queue index for queue %u", queue_id);
        return kErrInvalid;
    }
    const bool game_table = table == g_state.compute_game;
    const std::uint32_t index = game_table ? queue_id - 0x20u : queue_id - 0x58u;
    const std::uint32_t limit = game_table ? kGameQueues : kSysQueues;
    if (index >= limit) {
        drv_log("invalid queue index %u", index);
        return kErrInvalid;
    }
    ComputeQueueEntry &e = table[index];
    if (force == 0 && e.created != 0) {
        drv_log("queue %u already created", queue_id);
        return kOk;
    }
    UmdMemoryInfo u{};
    if (!get_umd_memory_info(&u)) {
        drv_log("cannot get the gc umd memory");
        return kErrUmdMemoryOrUnmap;
    }
    e.ring_base = u.acqrb + static_cast<std::uint64_t>(index) * 0x8000u;
    e.rptr_report = e.ring_base + 0x4000u;
    put_u32(e.rptr_report, 0);
    e.eop_area = u.eop_fifo + static_cast<std::uint64_t>(index) * 0x1000u;
    e.ring_size = 0x4000;
    e.eop_size = 0x1000;
    e.ring_size2 = 0x4000;
    e.wptr_dw = 0;
    int rc = 0;
    if (!map_compute_queue(me, queue_pipe(queue_id), queue_index(queue_id), e.ring_base, 12,
                           index + 1u, e.rptr_report, &e.doorbell_slot, 0, &rc)) {
        drv_log("cannot map queue (%u), ret = %d", queue_id, rc);
        return kErrMapOrClose;
    }
    e.queue_id = queue_id;
    e.created = 1;
    e.wptr_dw = 0;
    QueueHandle &h = e.handle;
    if (config == nullptr) {
        h.struct_size = 0x38;
        h.suspend_arg = 0;
        h.direct_tag = 0;
    } else {
        std::memcpy(static_cast<void *>(&h), config, 0x38);
    }
    h.entry = addr_of(&e);
    h.queue_id = queue_id;
    mutex_init_if_needed(&h);
    *handle_out = &h;
    return kOk;
}

} // namespace detail

using namespace detail;

std::int32_t sceAgcDriverCreateQueue(std::uint32_t queue_id, QueueHandle **handle_out,
                                     const void *config, char force) {
    return create_queue(queue_id, handle_out, config, force);
}

std::int32_t sceAgcDriverDestroyQueue(QueueHandle *handle) {
    if (handle == nullptr) {
        return kErrInvalid;
    }
    if (g_state.client_type == 1 && handle->queue_id < 0x20) {
        const int rc = g_imports.close != nullptr ? g_imports.close(g_state.gc_fd) : -1;
        if (rc != 0) {
            return kErrMapOrClose;
        }
        drv_log("closing gc on purpose for a reset");
        g_state.gc_closed_for_reset = 1;
        return kOk;
    }
    auto *e = at<ComputeQueueEntry>(handle->entry);
    if (e == nullptr) {
        return kErrInvalid;
    }
    if (handle->queue_id < 0x20) {
        drv_log("a graphics queue needs no destroy");
        return kOk;
    }
    UnmapQueueArgs u{queue_me(handle->queue_id), queue_pipe(handle->queue_id),
                     queue_index(handle->queue_id)};
    if (gc_ioctl(kIoctlUnmapComputeQueue, &u) != 0) {
        return kErrUmdMemoryOrUnmap;
    }
    if (g_state.gpu_info != 0) {
        put_u32(queue_record(entry_vqid(e)), 0);
    }
    mutex_destroy(handle);
    // deviation (recommended by the description): forget the destroyed mutex so a later
    // CreateQueue initialises a fresh one.
    handle->mutex_ready = 0;
    e->created = 0;
    return kOk;
}

std::int32_t sceAgcDriverSubmitDcb(const CommandBufferDesc *desc) {
    return submit_front(&g_state.gfx_main, desc, 0, 0);
}

std::int32_t sceAgcDriverAgrSubmitDcb(const CommandBufferDesc *desc) {
    if (g_state.agr_enabled == 0) {
        drv_log("async graphics queue not enabled");
        return kErrInvalid;
    }
    g_state.agr_used = 1;
    return submit_front(&g_state.gfx_agr, desc, 0, 0);
}

std::int32_t sceAgcDriverSubmitAcb(std::uint32_t queue_id, const CommandBufferDesc *desc) {
    ComputeQueueEntry *e = compute_entry_for_id(queue_id);
    if (e == nullptr) {
        return kErrInvalid; // deviation: UB in the original (index before/after the tables)
    }
    return submit_front(&e->handle, desc, 0, 0);
}

std::int32_t sceAgcDriverSubmitCommandBuffer(QueueHandle *handle, const CommandBufferDesc *desc) {
    return submit_front(handle, desc, 0, 0);
}

std::int32_t nid_F5ZTyyVUHTs(std::uint32_t queue_id, const CommandBufferDesc *desc,
                             std::uint64_t tag) {
    ComputeQueueEntry *e = compute_entry_for_id(queue_id);
    if (e == nullptr) {
        return kErrInvalid; // deviation: null dereference in the original
    }
    return submit_front(&e->handle, desc, 1u, tag);
}

std::int32_t nid_Hb3p8BJm2PI(std::uint32_t queue_id, const CommandBufferDesc *desc,
                             std::uint64_t tag) {
    ComputeQueueEntry *e = compute_entry_for_id(queue_id);
    if (e == nullptr) {
        return kErrInvalid; // deviation: null dereference in the original
    }
    return submit_front(&e->handle, desc, 2u, tag);
}

std::int32_t sceAgcDriverSubmitMultiCommandBuffers(QueueHandle *handle, const std::uint64_t *addrs,
                                                   const std::uint32_t *sizes_dw,
                                                   std::uint32_t count) {
    return multi_submit(handle, addrs, sizes_dw, count);
}

std::int32_t sceAgcDriverSubmitMultiDcbs(const std::uint64_t *addrs, const std::uint32_t *sizes_dw,
                                         std::uint32_t count) {
    return multi_submit(&g_state.gfx_main, addrs, sizes_dw, count);
}

std::int32_t sceAgcDriverAgrSubmitMultiDcbs(const std::uint64_t *addrs,
                                            const std::uint32_t *sizes_dw, std::uint32_t count) {
    if (g_state.agr_enabled == 0) {
        drv_log("async graphics queue not enabled");
        return kErrInvalid;
    }
    g_state.agr_used = 1;
    return multi_submit(&g_state.gfx_agr, addrs, sizes_dw, count);
}

std::int32_t sceAgcDriverSubmitMultiAcbs(std::uint32_t queue_id, const std::uint64_t *addrs,
                                         const std::uint32_t *sizes_dw, std::uint32_t count) {
    ComputeQueueEntry *e = compute_entry_for_id(queue_id);
    if (e == nullptr) {
        return count == 0 ? kErrMultiZero : kErrInvalid; // deviation: UB in the original
    }
    return multi_submit(&e->handle, addrs, sizes_dw, count);
}

std::int32_t nid_kAPt2J4U3v8(const CommandBufferDesc *desc, std::uint32_t *status_out,
                             std::uint32_t suspend_arg) {
    if (desc == nullptr) {
        return kErrInvalid; // deviation: UB in the original
    }
    std::int32_t result = kErrQueueLock;
    auto step = [&](QueueHandle *h) -> bool {
        const std::int32_t lr = mutex_lock(h);
        if (lr != 0) {
            if (lr < 0) {
                drv_log("suspend point: unable to lock (%d)", lr);
            }
            return false;
        }
        const SubmitPair pair = pair_from(desc);
        h->seq = g_submit_seq.fetch_add(1);
        ++h->submit_count;
        h->batch_first = 0;
        h->batch_left = 0;
        h->flags &= ~3u;
        h->tag = 0;
        h->suspend_arg = suspend_arg;
        // pre-suspend hooks: none can be installed
        result = suspend_point_impl(h, &pair, status_out);
        if (mutex_unlock(h) < 0) {
            drv_log("suspend point: unlock error");
        }
        return true;
    };
    if (g_state.agr_enabled != 0 &&
        (g_state.pending_suspend[1].b.address == 0 || g_state.agr_used != 0)) {
        (void)step(&g_state.gfx_agr);
    }
    (void)step(&g_state.gfx_main);
    return result;
}

std::int32_t sceAgcDriverSuspendPointSubmit(const CommandBufferDesc *desc,
                                            std::uint32_t *status_out) {
    return nid_kAPt2J4U3v8(desc, status_out, 0);
}

std::int32_t sceAgcDriverIsSuspendPointInFlight() { return kErrNotPermitted; }

std::int32_t nid_dwoD_LJDQy8() {
    if (g_state.client_type != 0) {
        drv_log("user special queue: called from a non-game process, failing on purpose");
        return kErrProcessOrMemory;
    }
    ComputeQueueEntry &e = g_state.compute_sys[kSpecialQueueIndex];
    if (e.created != 0) {
        drv_log("queue 93 already created");
        return kOk;
    }
    UmdMemoryInfo u{};
    if (!get_umd_memory_info(&u)) {
        drv_log("cannot get the gc umd memory");
        return kErrUmdMemoryOrUnmap;
    }
    e.ring_base = u.acqrb + 0x1C8000u;
    e.rptr_report = u.acqrb + 0x1CC000u; // not zeroed
    e.eop_area = u.eop_fifo + 0x39000u;
    e.ring_size = 0x4000;
    e.eop_size = 0x1000;
    e.ring_size2 = 0x4000;
    int rc = 0;
    if (!map_compute_queue(kMagicMe2, kMagicPipe2, kMagicQueue2, e.ring_base, 12, kMagicVqid2,
                           e.rptr_report, &e.doorbell_slot, 0, &rc)) {
        const int err = g_imports.error_location != nullptr ? *g_imports.error_location() : 0;
        drv_log("cannot map queue (93), ret = %d, errno = %d", rc, err);
        return kErrMapOrClose;
    }
    e.queue_id = kSpecialQueueId;
    e.created = 1;
    e.wptr_dw = 0;
    QueueHandle &h = e.handle;
    h.struct_size = 0x38;
    h.queue_id = kSpecialQueueId;
    h.flags = 0;
    h.direct_tag = 0;
    h.entry = addr_of(&e);
    mutex_init_if_needed(&h);
    return kOk;
}

std::int32_t nid_NRO47jBXLiI() {
    if (g_state.client_type != 0) {
        drv_log("user special queue: called from a non-game process, failing on purpose");
        return kErrProcessOrMemory;
    }
    UnmapQueueArgs u{kMagicMe2, kMagicPipe2, kMagicQueue2};
    if (gc_ioctl(kIoctlUnmapComputeQueue, &u) != 0) {
        return kErrMapOrClose;
    }
    ComputeQueueEntry &e = g_state.compute_sys[kSpecialQueueIndex];
    mutex_destroy(&e.handle);
    e.handle.mutex_ready = 0; // deviation: as DestroyQueue, so a re-create gets a fresh mutex
    e.created = 0;
    return kOk;
}

std::int32_t sceAgcDriverSubmitToHDRScopesACQ(const CommandBufferDesc *desc) {
    ComputeQueueEntry &e = g_state.compute_sys[kSpecialQueueIndex];
    if (e.created == 0) {
        drv_log("acquire the user special queue first");
        return kErrInvalid;
    }
    if (desc == nullptr) {
        return kErrInvalid; // deviation: UB in the original
    }
    const SubmitPair pair = pair_from(desc);
    // No lock, no hooks, no sequence update: the caller serialises.
    return submit_single_impl(&e.handle, &pair);
}

std::int32_t sceAgcDriverIDHSSubmit(const CommandBufferDesc *desc) {
    if (desc == nullptr) {
        return kErrInvalid; // deviation: UB in the original
    }
    const std::uint32_t ring = g_state.client_type != 0 ? 3u : 0u;
    RingSelectArgs sel{ring, 1};
    (void)gc_ioctl(kIoctlRingSelect, &sel);
    DirectIbPacket packet = direct_packet(*desc);
    if (g_state.client_type == 0) {
        ++g_state.gfx_ring0_submits;
    } else {
        ++g_state.gfx_other_submits;
    }
    DirectSubmitArgs a{ring, 1, addr_of(&packet)};
    const int rc = gc_ioctl(kIoctlDirectSubmit, &a);
    // The original tests the submit result the wrong way round: success reports an error code.
    return rc == 0 ? kErrIdhsSubmitted : kOk;
}

std::int32_t sceAgcDriverCwsrSuspendAcq(std::uint32_t *result_out) {
    U32PairArgs a{0, 0};
    if (gc_ioctl(kIoctlCwsr, &a) != 0) {
        return kErrMapOrClose;
    }
    if (result_out != nullptr) {
        *result_out = a.second;
    }
    return kOk;
}

std::int32_t sceAgcDriverCwsrResumeAcq() {
    U32PairArgs a{1, 0};
    return gc_ioctl(kIoctlCwsr, &a) == 0 ? kOk : kErrMapOrClose;
}

std::int32_t nid_oFb2hMcoJa4(std::int32_t enable) {
    if (g_state.client_type != 0) {
        return kErrProcessOrMemory;
    }
    // Retries until the lock is taken. deviation: without the lock import the original would spin
    // forever; we proceed unlocked.
    auto lock_retry = [](QueueHandle *h) {
        while (g_imports.mutex_lock != nullptr) {
            const std::int32_t r = mutex_lock(h);
            if (r == 0) {
                return;
            }
            if (r < 0) {
                drv_log("kernel flag: unable to lock (%d), retrying", r);
            }
        }
    };
    lock_retry(&g_state.gfx_main);
    lock_retry(&g_state.gfx_agr);
    if (enable != 0) {
        g_state.gfx_main.flags |= kQueueKernelFlag;
        g_state.gfx_agr.flags |= kQueueKernelFlag;
    } else {
        g_state.gfx_main.flags &= ~kQueueKernelFlag;
        g_state.gfx_agr.flags &= ~kQueueKernelFlag;
    }
    if (mutex_unlock(&g_state.gfx_agr) < 0) {
        drv_log("kernel flag: unlock error");
    }
    if (mutex_unlock(&g_state.gfx_main) < 0) {
        drv_log("kernel flag: unlock error");
    }
    return kOk;
}

std::uint8_t nid_SFB48L57OKQ() { return static_cast<std::uint8_t>(g_state.client_flags & 1u); }

} // namespace bc5::reimpl::agc_driver
