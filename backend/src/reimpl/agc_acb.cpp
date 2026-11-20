// SPDX-License-Identifier: GPL-2.0-only
// Clean-room re-creation of libSceAgc (see src/reimpl/PROVENANCE.md): the sceAgcAcb* builders
// (compute queues) and the driver-backed builders shared by both queue kinds (markers, flip,
// wait-until-safe, workloads, wait-on-memory, memory semaphores, WRITE_DATA, ATOMIC_GDS).
//
// Packet layouts are per the original module's behaviour (clean-room description, see
// src/reimpl/PROVENANCE.md). Opcode names in comments are from Mesa src/amd/common/sid.h
// (commit ab2374a): PKT3_ATOMIC_GDS 0x1D, PKT3_ATOMIC_MEM 0x1E, PKT3_COND_EXEC 0x22,
// PKT3_WRITE_DATA 0x37, PKT3_WAIT_REG_MEM 0x3C, PKT3_COPY_DATA 0x40, PKT3_EVENT_WRITE 0x46,
// PKT3_DMA_DATA 0x50, PKT3_ACQUIRE_MEM 0x58, PKT3_REWIND 0x59; DISPATCH_INDIRECT 0x16,
// MEM_SEMAPHORE 0x39, PRIME_UTCL2 0x5D and WAIT_REG_MEM64 0x93 are TODO(verify).
#include "bc5/reimpl/agc_internal.hpp"

#include <algorithm>

namespace bc5::reimpl::agc {

using namespace detail;

// ---- shared driver-backed helpers ---------------------------------------------------------------

namespace detail {

std::uint32_t *marker(CommandBuffer *cb, int is_acb, bool push, const char *name,
                      std::uint32_t length, std::uint32_t color) {
    auto *writer = push ? g_imports.ud_write_push_marker : g_imports.ud_write_set_marker;
    if (g_imports.ud_get_packet_size == nullptr || writer == nullptr) {
        return nullptr;
    }
    const std::uint32_t n = g_imports.ud_get_packet_size(length);
    if (!reserve_soft(cb, n)) {
        return nullptr;
    }
    std::uint32_t *s = cb->cursor;
    if (writer(s, is_acb, name, length, color) != n) {
        return nullptr;
    }
    cb->cursor = s + n;
    return s;
}

std::uint32_t *pop_marker(CommandBuffer *cb, int is_acb) {
    if (g_imports.ud_get_packet_size == nullptr || g_imports.ud_write_pop_marker == nullptr) {
        return nullptr;
    }
    const std::uint32_t n = g_imports.ud_get_packet_size(0);
    if (!reserve_soft(cb, n)) {
        return nullptr;
    }
    std::uint32_t *s = cb->cursor;
    if (g_imports.ud_write_pop_marker(s, is_acb) != n) {
        return nullptr;
    }
    cb->cursor = s + n;
    return s;
}

std::uint32_t *set_flip(CommandBuffer *cb, int is_acb, std::uint32_t arg0, std::uint32_t arg1,
                        std::uint32_t arg2, std::uint64_t arg3) {
    if (g_imports.get_set_flip_size == nullptr || g_imports.set_flip == nullptr) {
        return nullptr;
    }
    const std::uint32_t n = g_imports.get_set_flip_size();
    if (!reserve_soft(cb, n)) {
        return nullptr;
    }
    std::uint32_t *s = cb->cursor;
    // The driver writes the packet and advances the cursor itself.
    const int rc = g_imports.set_flip(&cb->cursor, n, is_acb, static_cast<int>(arg0),
                                      static_cast<int>(arg1), arg2, static_cast<std::int64_t>(arg3));
    return rc == 0 ? s : nullptr;
}

std::uint32_t *wait_until_safe(CommandBuffer *cb, int is_acb, std::uint32_t arg0,
                               std::uint32_t arg1) {
    if (g_imports.get_wait_rendering_size == nullptr || g_imports.wait_until_safe == nullptr) {
        return nullptr;
    }
    const std::uint32_t n = g_imports.get_wait_rendering_size();
    if (!reserve_soft(cb, n)) {
        return nullptr;
    }
    std::uint32_t *s = cb->cursor;
    const int rc = g_imports.wait_until_safe(&cb->cursor, n, is_acb, static_cast<int>(arg0),
                                             static_cast<int>(arg1));
    return rc == 0 ? s : nullptr;
}

std::uint32_t *workloads_active(CommandBuffer *cb, int is_acb, std::uint32_t arg0,
                                std::uint64_t arg1, std::uint32_t arg2) {
    if (g_imports.get_workloads_active_size == nullptr ||
        g_imports.set_workloads_active == nullptr) {
        return nullptr;
    }
    const std::uint32_t n = g_imports.get_workloads_active_size();
    if (!reserve_soft(cb, n)) {
        return nullptr;
    }
    std::uint32_t *s = cb->cursor;
    if (g_imports.set_workloads_active(s, is_acb, arg0, ptr<const std::uint32_t>(arg1), arg2) !=
        0) {
        return nullptr;
    }
    cb->cursor = s + n;
    return s;
}

std::uint32_t *workload_complete(CommandBuffer *cb, int is_acb, std::uint32_t arg0,
                                 std::uint32_t arg1) {
    if (g_imports.get_workload_complete_size == nullptr ||
        g_imports.set_workload_complete == nullptr) {
        return nullptr;
    }
    const std::uint32_t n = g_imports.get_workload_complete_size();
    if (!reserve_soft(cb, n)) {
        return nullptr;
    }
    std::uint32_t *s = cb->cursor;
    if (g_imports.set_workload_complete(s, is_acb, arg0, arg1) != 0) {
        return nullptr;
    }
    cb->cursor = s + n;
    return s;
}

std::uint32_t *workload_stream_inactive(CommandBuffer *cb, int is_acb, std::uint32_t arg0) {
    if (g_imports.get_workload_stream_inactive_size == nullptr ||
        g_imports.set_workload_stream_inactive == nullptr) {
        return nullptr;
    }
    const std::uint32_t n = g_imports.get_workload_stream_inactive_size();
    if (!reserve_soft(cb, n)) {
        return nullptr;
    }
    std::uint32_t *s = cb->cursor;
    if (g_imports.set_workload_stream_inactive(s, is_acb, arg0) != 0) {
        return nullptr;
    }
    cb->cursor = s + n;
    return s;
}

std::uint32_t *wait_reg_mem(CommandBuffer *cb, int is_acb, std::int32_t size,
                            std::uint32_t control32, std::uint32_t control64,
                            std::uint64_t address, std::uint64_t reference, std::uint64_t mask,
                            std::uint32_t poll_cycles) {
    if (size != 0 && size != 1) {
        return nullptr;
    }
    if (g_imports.ud_get_packet_size == nullptr || g_imports.ud_write_packet == nullptr) {
        return nullptr;
    }
    const std::uint32_t u = g_imports.ud_get_packet_size(4);
    const std::uint32_t e = g_imports.ud_get_packet_size(0);
    if (!reserve_soft(cb, u + e + (size == 0 ? 7u : 9u))) {
        return nullptr;
    }
    const std::uint32_t poll = std::min<std::uint32_t>(poll_cycles >> 4, 0xFFFFu);
    const std::uint32_t address_lo = lo32(address);
    std::uint32_t *start =
        write_user_data(cb, is_acb, (size == 0 ? 0xC8010000u : 0xC8020000u) | (hi32(address) & 0xFFFFu),
                        &address_lo, 4);
    if (size == 0) {
        const std::uint32_t d[7] = {0xC0053C00u,        control32,       lo32(address) & ~3u,
                                    hi32(address) & 0x3FFFFu, lo32(reference), lo32(mask),
                                    poll};
        emit_raw(cb, d, 7);
    } else {
        const std::uint32_t d[9] = {0xC0079300u,     control64,        lo32(address) & ~7u,
                                    hi32(address) & 0x3FFFFu, lo32(reference), hi32(reference),
                                    lo32(mask),      hi32(mask),       poll};
        emit_raw(cb, d, 9);
    }
    write_user_data(cb, is_acb, 0xC8000000u, nullptr, 0);
    return start;
}

std::uint32_t *mem_semaphore(CommandBuffer *cb, int begin_is_acb, int end_is_acb,
                             std::uint64_t address, std::uint8_t use_mailbox,
                             std::uint8_t signal_type, std::int32_t sem_sel) {
    if (g_imports.ud_get_packet_size == nullptr || g_imports.ud_write_packet == nullptr) {
        return nullptr;
    }
    const std::uint32_t u = g_imports.ud_get_packet_size(4);
    const std::uint32_t e = g_imports.ud_get_packet_size(0);
    if (!reserve_soft(cb, u + 4u + e)) {
        return nullptr;
    }
    const std::uint32_t address_lo = lo32(address);
    std::uint32_t *start = write_user_data(
        cb, begin_is_acb, (sem_sel == 6 ? 0xC9010000u : 0xC9020000u) + (hi32(address) & 0xFFFFu),
        &address_lo, 4);
    if (static_cast<std::uint8_t>(sem_sel) == 6) {
        sceAgcCbNop(cb, e); // padding for a signal; result ignored
    }
    const std::uint32_t d[4] = {0xC0023900u, lo32(address) & ~7u, hi32(address),
                                (static_cast<std::uint32_t>(sem_sel) << 29) |
                                    ((static_cast<std::uint32_t>(signal_type) & 1u) << 20) |
                                    ((static_cast<std::uint32_t>(use_mailbox) & 1u) << 16)};
    emit_raw(cb, d, 4);
    if (static_cast<std::uint8_t>(sem_sel) == 7) {
        write_user_data(cb, end_is_acb, 0xC9000000u, nullptr, 0);
    }
    return start;
}

std::uint32_t *write_data(CommandBuffer *cb, std::uint32_t control, std::uint32_t address_lo,
                          std::uint32_t address_hi, const std::uint32_t *data,
                          std::uint32_t num_dwords) {
    if (data == nullptr) {
        return nullptr; // deviation: UB in the original (data[0] is always read)
    }
    if (!reserve_soft(cb, num_dwords + 4u)) {
        return nullptr;
    }
    const std::uint32_t first = data[0];
    std::uint32_t *p = reserve_strict(cb, 5);
    if (p == nullptr) {
        return nullptr;
    }
    p[0] = 0xC0003700u | ((num_dwords + 2u) << 16);
    p[1] = control;
    p[2] = address_lo;
    p[3] = address_hi;
    p[4] = first;
    if (num_dwords > 1) {
        // A failure here leaves a truncated packet; the header is still returned.
        if (std::uint32_t *q = reserve_strict(cb, num_dwords - 1u); q != nullptr) {
            copy_bytes(q, data + 1, 4ull * (num_dwords - 1u));
        }
    }
    return p;
}

std::uint32_t atomic_gds_control(std::uint32_t op_flags, std::int32_t mode, bool op8) {
    const std::uint32_t low =
        op8 ? ((op_flags & 0xFFu) | ((op_flags & 0x200u) << 7))
            : (((op_flags << 7) | op_flags) & 0x1007Fu);
    return low | ((op_flags & 0x20u) << 13) | ((op_flags & 0x40u) << 14) |
           ((mode == 1 && (op_flags & 0x20u) == 0) ? (1u << 17) : 0u);
}

std::uint32_t *atomic_gds(CommandBuffer *cb, std::uint32_t control, std::uint32_t flag40,
                          std::uint32_t field32, std::uint32_t gds_offset, std::uint16_t gds_size,
                          std::uint32_t field5, std::uint32_t field6, std::uint64_t data0,
                          std::uint64_t data1) {
    const std::uint32_t d[11] = {0xC0091D00u,
                                 control,
                                 (field32 & 0x3Fu) | ((flag40 & 1u) << 8),
                                 gds_offset & 0xFFFFu,
                                 gds_size,
                                 field5 & 0x00FF00FFu,
                                 field6,
                                 lo32(data0),
                                 hi32(data0),
                                 lo32(data1),
                                 hi32(data1)};
    return emit(cb, d, 11);
}

} // namespace detail

// ---- ACB builders -----------------------------------------------------------------------------

std::uint32_t *sceAgcAcbAtomicMem(CommandBuffer *cb, std::uint32_t atomic_op, std::uint32_t command,
                                  std::uint64_t address, std::uint8_t cache_policy,
                                  std::uint64_t src_data, std::uint64_t cmp_data,
                                  std::uint32_t loop_interval) {
    const std::uint32_t d[9] = {0xC0071E00u,
                                ((static_cast<std::uint32_t>(cache_policy) & 3u) << 25) |
                                    ((command & 0xFu) << 8) | (atomic_op & 0x7Fu),
                                lo32(address),
                                hi32(address),
                                lo32(src_data),
                                hi32(src_data),
                                lo32(cmp_data),
                                hi32(cmp_data),
                                std::min<std::uint32_t>(loop_interval >> 6, 0xFFFu)};
    return emit(cb, d, 9);
}

std::uint32_t *sceAgcAcbAcquireMem(CommandBuffer *cb, std::uint32_t gcr_control,
                                   std::uint64_t base_address, std::uint64_t size_bytes,
                                   std::uint32_t poll_cycles) {
    std::uint32_t g = gcr_control;
    if ((g & 0xC000u) == 0x4000u) {
        g |= 0x8000u;
    }
    const std::uint32_t poll = std::min<std::uint32_t>((poll_cycles >> 4) & 0x0FFFFFFFu, 0xFFFFu);
    const std::uint32_t w = state().workaround_mask;
    std::uint32_t *extra = nullptr;
    if ((w & 1u) == 0) {
        if ((w & 2u) != 0 && (g & 0x108u) == 0x108u) {
            g &= ~0xCu;
        }
    } else if ((g & 0x108u) == 0x108u) {
        if ((g & 0x2A0u) == 0) {
            g &= 0xFFFFFD53u;
        } else {
            const std::uint32_t x[8] = {0xC0065800u, 0, 0, 0, 0, 0, poll, 0x00000100u};
            extra = emit(cb, x, 8);
            if (extra == nullptr) {
                return nullptr;
            }
            g &= ~0x100u;
        }
    }
    const std::uint64_t t = (((base_address & 0xFFu) + size_bytes) & 0xFFFFFFFFFFFFull) + 0xFFu;
    const std::uint64_t sz = std::min<std::uint64_t>(t, 0xFFFFFFFFFF00ull - base_address);
    const std::uint32_t d[8] = {0xC0065800u,
                                0u,
                                static_cast<std::uint32_t>(sz >> 8),
                                static_cast<std::uint32_t>(sz >> 40) & 0xFFu,
                                static_cast<std::uint32_t>(base_address >> 8),
                                static_cast<std::uint32_t>(base_address >> 40),
                                poll,
                                g & 0x7FFFFu};
    std::uint32_t *main_packet = emit(cb, d, 8);
    if (main_packet == nullptr) {
        return nullptr;
    }
    return extra != nullptr ? extra : main_packet;
}

std::uint32_t *sceAgcAcbCondExec(CommandBuffer *cb, std::uint64_t condition_address,
                                 std::uint32_t num_dwords) {
    const std::uint32_t d[5] = {0xC0032200u, lo32(condition_address) & ~3u,
                                hi32(condition_address), 0u, num_dwords & 0x3FFFu};
    return emit(cb, d, 5);
}

std::uint32_t *sceAgcAcbCopyData(CommandBuffer *cb, std::uint32_t dst_sel,
                                 std::uint8_t dst_cache_policy, std::uint64_t dst_address,
                                 std::uint32_t src_sel, std::uint32_t src_cache_policy,
                                 std::uint64_t src_address_or_data, std::uint8_t count_sel,
                                 std::uint8_t write_confirm) {
    const std::uint32_t d[6] = {
        0xC0044000u,
        ((static_cast<std::uint32_t>(dst_cache_policy) & 3u) << 25) |
            ((static_cast<std::uint32_t>(write_confirm) & 1u) << 20) |
            ((static_cast<std::uint32_t>(count_sel) & 1u) << 16) |
            ((src_cache_policy & 3u) << 13) | ((dst_sel & 0xFu) << 8) | (src_sel & 0xFu),
        lo32(src_address_or_data),
        hi32(src_address_or_data),
        lo32(dst_address),
        hi32(dst_address)};
    return emit(cb, d, 6);
}

std::uint32_t *sceAgcAcbDispatchIndirect(CommandBuffer *cb, std::uint64_t args_address,
                                         std::uint32_t initiator_flags) {
    const std::uint32_t d[4] = {0xC0021600u, lo32(args_address), hi32(args_address),
                                (initiator_flags & 0xA038u) | state().trace_initiator[10] | 0x41u};
    return emit(cb, d, 4);
}

std::uint32_t *sceAgcAcbDmaData(CommandBuffer *cb, std::uint32_t dst_sel,
                                std::uint8_t dst_cache_policy, std::uint64_t dst_address,
                                std::uint32_t src_sel, std::uint8_t src_cache_policy,
                                std::uint64_t src_address_or_data, std::uint32_t byte_count,
                                std::uint8_t flag30, std::uint8_t flag31) {
    // Special source selectors read fixed register byte addresses (per the original module).
    std::uint64_t src = src_address_or_data;
    if (src_sel == 0x25) {
        src = 0x30184;
    } else if (src_sel == 0x24) {
        src = 0x3017C;
    } else if (src_sel == 0x14) {
        src = 0x30174;
    }
    const std::uint32_t d[7] = {
        0xC0055000u,
        ((src_sel & 3u) << 29) | ((static_cast<std::uint32_t>(dst_cache_policy) & 3u) << 25) |
            ((dst_sel & 3u) << 20) | ((static_cast<std::uint32_t>(src_cache_policy) & 3u) << 13),
        lo32(src),
        hi32(src),
        lo32(dst_address),
        hi32(dst_address),
        (static_cast<std::uint32_t>(flag31) << 31) |
            ((static_cast<std::uint32_t>(flag30) & 1u) << 30) | ((dst_sel & 8u) << 26) |
            ((dst_sel & 4u) << 25) | ((src_sel & 8u) << 25) | ((src_sel & 4u) << 24) |
            (byte_count & 0x3FFFFFFu)};
    return emit(cb, d, 7);
}

std::uint32_t *sceAgcAcbEventWrite(CommandBuffer *cb, std::uint32_t event_type) {
    const std::uint32_t d[2] = {0xC0004600u, (event_type & 0x3Fu) | (event_type == 7 ? 0x400u : 0u)};
    return emit(cb, d, 2);
}

namespace {
std::uint32_t *copy_sh_stream(CommandBuffer *cb, const QueueSlot *slot) {
    if (slot->sh_stream_bytes == 0) {
        return nullptr;
    }
    std::uint32_t *p = reserve_strict(cb, (slot->sh_stream_bytes + 3u) / 4u);
    if (p != nullptr) {
        copy_bytes(p, slot->sh_stream, slot->sh_stream_bytes);
    }
    return p;
}
} // namespace

std::uint32_t *agcAcbCopyActiveShDefaults(CommandBuffer *cb) {
    const QueueSlot *slot = active_slot();
    if (slot == nullptr) {
        return nullptr;
    }
    return copy_sh_stream(cb, slot);
}

namespace detail {
std::uint32_t *acb_reset_queue_body(CommandBuffer *cb, std::uint16_t flags, QueueSlot *slot,
                                    bool trusted) {
    if ((flags & 0x8000u) != 0) {
        slot = active_slot();
    }
    if (slot == nullptr) {
        return nullptr; // deviation: UB in the original (NULL slot dereferenced)
    }
    if (g_imports.ud_get_packet_size == nullptr || g_imports.ud_write_packet == nullptr) {
        return nullptr;
    }
    const std::uint32_t id = 0xCE000000u | ((trusted ? 0u : 1u) << 22) |
                             ((slot->trusted != 0 ? 0u : 1u) << 21) | flags;
    if (!reserve_soft(cb, g_imports.ud_get_packet_size(4))) {
        return nullptr;
    }
    std::uint32_t *start = write_user_data(cb, 1, id, &slot->version, 4);
    if ((flags & 0x80u) != 0) {
        const std::uint32_t d[2] = {0xC0004600u, 0x00000407u};
        if (emit(cb, d, 2) == nullptr) {
            return nullptr;
        }
    }
    if ((flags & 2u) != 0 && copy_sh_stream(cb, slot) == nullptr) {
        return nullptr;
    }
    if ((flags & 0x140u) != 0) {
        const std::uint32_t gcr = (flags & 0x100u) != 0 ? 0xC3A1u : 0xC1u;
        if (sceAgcAcbAcquireMem(cb, gcr, 0, 0, 0) == nullptr) {
            return nullptr;
        }
    }
    if (!reserve_soft(cb, g_imports.ud_get_packet_size(0))) {
        return nullptr;
    }
    write_user_data(cb, 1, (id & 0xCF600000u) | 0xCE800000u, nullptr, 0);
    return start;
}
} // namespace detail

std::uint32_t *sceAgcAcbResetQueue(CommandBuffer *cb, std::uint16_t flags, std::uint32_t queue_slot) {
    const bool trusted = is_trusted_caller(BC5_AGC_RETURN_ADDRESS());
    return acb_reset_queue_body(cb, flags, slot_for_queue(queue_slot), trusted);
}

std::uint32_t *sceAgcAcbJump(CommandBuffer *cb, std::uint8_t cache_policy,
                             std::uint64_t target_address, std::uint32_t size_dwords) {
    const std::uint32_t d[4] = {0xC0023F00u, lo32(target_address) & 0xFFFFFFFCu,
                                hi32(target_address),
                                (size_dwords & 0xFFFFFu) + 0x0F900000u +
                                    (static_cast<std::uint32_t>(cache_policy) & 3u) * 0x10000000u};
    return emit(cb, d, 4);
}

std::uint32_t *sceAgcAcbWriteData(CommandBuffer *cb, std::uint32_t dst_sel, std::uint8_t cache_policy,
                                  std::uint64_t dst_address, const std::uint32_t *data,
                                  std::uint32_t num_dwords, std::uint8_t write_one_address,
                                  std::uint8_t write_confirm) {
    const std::uint32_t confirm =
        static_cast<std::uint8_t>(dst_sel) != 0 ? (static_cast<std::uint32_t>(write_confirm) & 1u)
                                                : 0u;
    const std::uint32_t control = ((static_cast<std::uint32_t>(cache_policy) & 3u) << 25) |
                                  (confirm << 20) |
                                  ((static_cast<std::uint32_t>(write_one_address) & 1u) << 16) |
                                  ((dst_sel & 0xFu) << 8);
    return write_data(cb, control, lo32(dst_address), hi32(dst_address), data, num_dwords);
}

std::uint32_t *sceAgcAcbWaitRegMem(CommandBuffer *cb, std::int32_t size, std::uint8_t compare_func,
                                   std::uint8_t cache_policy, std::uint64_t address,
                                   std::uint64_t reference, std::uint64_t mask,
                                   std::uint32_t poll_cycles) {
    const std::uint32_t control = ((static_cast<std::uint32_t>(cache_policy) & 3u) << 25) | 0x10u |
                                  (static_cast<std::uint32_t>(compare_func) & 7u);
    return wait_reg_mem(cb, 1, size, control, control, address, reference, mask, poll_cycles);
}

std::uint32_t *sceAgcAcbRewind(CommandBuffer *cb, std::uint32_t valid, std::uint8_t offload_enable) {
    const std::uint32_t d[2] = {0xC0005900u, (valid << 31) |
                                                 ((static_cast<std::uint32_t>(offload_enable) & 1u)
                                                  << 24)};
    return emit(cb, d, 2);
}

std::uint32_t *sceAgcAcbPrimeUtcl2(CommandBuffer *cb, std::uint8_t cache_permissions,
                                   std::uint8_t prime_mode, std::uint64_t address,
                                   std::uint32_t num_pages) {
    const std::uint32_t d[5] = {
        0xC0035D00u,
        static_cast<std::uint8_t>(((static_cast<std::uint32_t>(prime_mode) & 1u) << 3) |
                                  (static_cast<std::uint32_t>(cache_permissions) & 7u)),
        lo32(address) & 0xFFFFC000u, hi32(address), num_pages & 0x3FFFu};
    return emit(cb, d, 5);
}

std::uint32_t *sceAgcAcbAtomicGds(CommandBuffer *cb, std::uint32_t op_flags, std::int32_t mode,
                                  std::uint32_t flag40, std::uint32_t field32,
                                  std::uint64_t gds_offset, std::uint16_t gds_size,
                                  std::uint32_t field5, std::uint32_t field6, std::uint64_t data0,
                                  std::uint64_t data1) {
    return atomic_gds(cb, atomic_gds_control(op_flags, mode, false), flag40, field32,
                      lo32(gds_offset), gds_size, field5, field6, data0, data1);
}

std::uint32_t *agcAcbAtomicGdsOp8(CommandBuffer *cb, std::uint32_t op_flags, std::int32_t mode,
                                  std::uint32_t flag40, std::uint32_t field32,
                                  std::uint64_t gds_offset, std::uint16_t gds_size,
                                  std::uint32_t field5, std::uint32_t field6, std::uint64_t data0,
                                  std::uint64_t data1) {
    return atomic_gds(cb, atomic_gds_control(op_flags, mode, true), flag40, field32,
                      lo32(gds_offset), gds_size, field5, field6, data0, data1);
}

std::uint32_t *sceAgcAcbSetMarkerSpan(CommandBuffer *cb, const char *name, std::uint32_t name_length,
                                      std::uint32_t color) {
    return marker(cb, 1, false, name, name_length, color);
}

std::uint32_t *sceAgcAcbSetMarker(CommandBuffer *cb, const char *name, std::uint32_t color) {
    const auto len = name != nullptr ? static_cast<std::uint32_t>(string_length(name)) : 0u;
    return marker(cb, 1, false, name, len, color);
}

std::uint32_t *sceAgcAcbPushMarkerSpan(CommandBuffer *cb, const char *name,
                                       std::uint32_t name_length, std::uint32_t color) {
    return marker(cb, 1, true, name, name_length, color);
}

std::uint32_t *sceAgcAcbPushMarker(CommandBuffer *cb, const char *name, std::uint32_t color) {
    const auto len = name != nullptr ? static_cast<std::uint32_t>(string_length(name)) : 0u;
    return marker(cb, 1, true, name, len, color);
}

std::uint32_t *sceAgcAcbPopMarker(CommandBuffer *cb) { return pop_marker(cb, 1); }

std::uint32_t *sceAgcAcbSetFlip(CommandBuffer *cb, std::uint32_t arg0, std::uint32_t arg1,
                                std::uint32_t arg2, std::uint64_t arg3) {
    return set_flip(cb, 1, arg0, arg1, arg2, arg3);
}

std::uint32_t *sceAgcAcbMemSemaphore(CommandBuffer *cb, std::uint64_t address,
                                     std::uint8_t use_mailbox, std::uint8_t signal_type,
                                     std::int32_t sem_sel) {
    return mem_semaphore(cb, 1, 1, address, use_mailbox, signal_type, sem_sel);
}

std::uint32_t *sceAgcAcbWaitUntilSafeForRendering(CommandBuffer *cb, std::uint32_t arg0,
                                                  std::uint32_t arg1) {
    return wait_until_safe(cb, 1, arg0, arg1);
}

std::uint32_t *sceAgcAcbSetWorkloadsActive(CommandBuffer *cb, std::uint32_t arg0,
                                           std::uint64_t arg1, std::uint32_t arg2) {
    return workloads_active(cb, 1, arg0, arg1, arg2);
}

std::uint32_t *sceAgcAcbSetWorkloadComplete(CommandBuffer *cb, std::uint32_t arg0,
                                            std::uint32_t arg1) {
    return workload_complete(cb, 1, arg0, arg1);
}

std::uint32_t *sceAgcAcbSetWorkloadStreamInactive(CommandBuffer *cb, std::uint32_t arg0) {
    return workload_stream_inactive(cb, 1, arg0);
}

} // namespace bc5::reimpl::agc
