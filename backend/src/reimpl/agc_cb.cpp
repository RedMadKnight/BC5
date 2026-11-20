// SPDX-License-Identifier: GPL-2.0-only
// Clean-room re-creation of libSceAgc (see src/reimpl/PROVENANCE.md): command-buffer reservation
// (the out-of-space protocol) and the queue-agnostic sceAgcCb* builders.
//
// Packet layouts are per the original module's behaviour (clean-room description, see
// src/reimpl/PROVENANCE.md). Opcode names in comments are from Mesa src/amd/common/sid.h
// (commit ab2374a): PKT3_NOP 0x10, PKT3_DISPATCH_DIRECT 0x15, PKT3_INDIRECT_BUFFER 0x3F,
// PKT3_COND_WRITE 0x45, PKT3_RELEASE_MEM 0x49, PKT3_SET_SH_REG 0x76, PKT3_SET_UCONFIG_REG 0x79;
// MEM_SEMAPHORE 0x39 is TODO(verify) (not in sid.h at that commit).
#include "bc5/reimpl/agc_internal.hpp"

#include <algorithm>
#include <limits>

namespace bc5::reimpl::agc {

using namespace detail;

// ---- reservation ------------------------------------------------------------------------------

namespace {
bool default_out_of_space(CommandBuffer *, std::uint32_t, void *) {
    sceAgcDebugRaiseException(1, 0);
    return false;
}

// Shared space check; `honour` = the callback's false result fails the request.
bool make_room(CommandBuffer *cb, std::uint32_t n, bool honour) {
    if (free_dwords(cb) >= n) {
        return true;
    }
    const std::uint64_t total = static_cast<std::uint64_t>(cb->reserved_dwords) + n;
    if (total > std::numeric_limits<std::uint32_t>::max()) {
        return false;
    }
    if (cb->out_of_space == nullptr) {
        // deviation: UB in the original (it calls the callback unconditionally).
        return false;
    }
    const bool ok = cb->out_of_space(cb, static_cast<std::uint32_t>(total), cb->user_data);
    if (honour && !ok) {
        return false;
    }
    return free_dwords(cb) >= n;
}
} // namespace

void init_command_buffer(CommandBuffer *cb, void *buffer, std::uint64_t size_bytes,
                         OutOfSpaceFn callback, void *user_data) {
    auto *begin = static_cast<std::uint32_t *>(buffer);
    cb->begin = begin;
    cb->cursor = begin;
    cb->buffer_end = ptr<std::uint32_t>(addr(buffer) + (size_bytes & ~3ull));
    cb->limit = cb->buffer_end;
    cb->reserved_dwords = 0;
    cb->padding = 0;
    cb->out_of_space = callback != nullptr ? callback : &default_out_of_space;
    cb->user_data = user_data;
}

std::uint32_t free_dwords(const CommandBuffer *cb) {
    const auto diff = static_cast<std::int64_t>(addr(cb->limit) - addr(cb->cursor));
    const std::int64_t f = diff / 4 - static_cast<std::int64_t>(cb->reserved_dwords);
    if (f <= 0) {
        return 0;
    }
    return static_cast<std::uint32_t>(
        std::min<std::int64_t>(f, std::numeric_limits<std::uint32_t>::max()));
}

std::uint32_t *reserve_strict(CommandBuffer *cb, std::uint32_t n) {
    if (cb == nullptr || !make_room(cb, n, true)) {
        return nullptr;
    }
    const std::uint64_t p = (addr(cb->cursor) + 3) & ~3ull;
    if (p == 0) {
        return nullptr;
    }
    cb->cursor = ptr<std::uint32_t>(p + 4ull * n);
    return ptr<std::uint32_t>(p);
}

bool reserve_soft(CommandBuffer *cb, std::uint32_t n) {
    return cb != nullptr && make_room(cb, n, false);
}

bool ensure_space(CommandBuffer *cb, std::uint32_t n) {
    return cb != nullptr && make_room(cb, n, true);
}

// ---- shared helpers -----------------------------------------------------------------------------

namespace detail {

void copy_bytes(void *dst, const void *src, std::size_t n) {
    if (n == 0) {
        return;
    }
    if (g_imports.memcpy != nullptr) {
        g_imports.memcpy(dst, src, n);
    } else {
        std::memcpy(dst, src, n); // libc is always present; the host's copy is equivalent
    }
}

void fill_bytes(void *dst, int value, std::size_t n) {
    if (n == 0) {
        return;
    }
    if (g_imports.memset != nullptr) {
        g_imports.memset(dst, value, n);
    } else {
        std::memset(dst, value, n);
    }
}

std::size_t string_length(const char *s) {
    return g_imports.strlen != nullptr ? g_imports.strlen(s) : std::strlen(s);
}

std::uint32_t *emit_raw(CommandBuffer *cb, const std::uint32_t *dwords, std::uint32_t n) {
    std::uint32_t *p = cb->cursor;
    copy_bytes(p, dwords, 4ull * n);
    cb->cursor = p + n;
    return p;
}

std::uint32_t *emit(CommandBuffer *cb, const std::uint32_t *dwords, std::uint32_t n) {
    std::uint32_t *p = reserve_strict(cb, n);
    if (p != nullptr) {
        copy_bytes(p, dwords, 4ull * n);
    }
    return p;
}

std::uint32_t *write_user_data(CommandBuffer *cb, int is_acb, std::uint32_t id, const void *payload,
                               std::uint32_t payload_bytes) {
    std::uint32_t *p = cb->cursor;
    const std::uint32_t w = g_imports.ud_write_packet(p, is_acb, id, payload, payload_bytes);
    cb->cursor = p + w;
    return p;
}

} // namespace detail

// ---- generic builders -------------------------------------------------------------------------

std::uint32_t *sceAgcCbBranch(CommandBuffer *cb, std::uint32_t mode, std::uint32_t compare_func,
                              std::uint64_t compare_address, std::uint64_t reference,
                              std::uint64_t mask, std::uint8_t then_cache_policy,
                              std::uint64_t then_address, std::uint32_t then_size_dwords,
                              std::uint8_t else_cache_policy, std::uint64_t else_address,
                              std::uint32_t else_size_dwords) {
    const std::uint32_t then_control =
        then_address != 0
            ? ((static_cast<std::uint32_t>(then_cache_policy) & 3u) << 28) |
                  (then_size_dwords & 0xFFFFFu)
            : 0u;
    const std::uint32_t else_control =
        else_address != 0
            ? ((static_cast<std::uint32_t>(else_cache_policy) & 3u) << 28) |
                  (else_size_dwords & 0xFFFFFu)
            : 0u;
    // 14-dword conditional INDIRECT_BUFFER form, per the original module's behaviour.
    const std::uint32_t d[14] = {0xC00C3F00u,
                                 ((compare_func & 7u) << 8) | (mode & 3u),
                                 lo32(compare_address) & ~7u,
                                 hi32(compare_address),
                                 lo32(reference),
                                 hi32(reference),
                                 lo32(mask),
                                 hi32(mask),
                                 lo32(then_address) & ~3u,
                                 hi32(then_address),
                                 then_control,
                                 lo32(else_address) & ~3u,
                                 hi32(else_address),
                                 else_control};
    return emit(cb, d, 14);
}

std::uint32_t *sceAgcCbDispatch(CommandBuffer *cb, std::uint32_t groups_x, std::uint32_t groups_y,
                                std::uint32_t groups_z, std::uint32_t initiator_flags) {
    const std::uint32_t d[5] = {0xC0031500u, groups_x, groups_y, groups_z,
                                (initiator_flags & 0xA038u) | state().trace_initiator[9] | 0x41u};
    return emit(cb, d, 5);
}

std::uint32_t *sceAgcCbCondWrite(CommandBuffer *cb, std::uint32_t compare_func,
                                 std::uint32_t write_space, std::uint64_t write_address,
                                 std::uint32_t write_data, std::uint64_t poll_address,
                                 std::uint32_t reference, std::uint32_t mask) {
    const std::uint32_t d[9] = {0xC0074500u,
                                ((write_space & 3u) << 8) | 0x10u | (compare_func & 7u),
                                lo32(poll_address),
                                hi32(poll_address),
                                reference,
                                mask,
                                lo32(write_address),
                                hi32(write_address),
                                write_data};
    return emit(cb, d, 9);
}

std::uint32_t *sceAgcCbMemSemaphore(CommandBuffer *cb, std::uint64_t address,
                                    std::uint32_t use_mailbox, std::uint32_t signal_type,
                                    std::int32_t sem_sel) {
    const std::uint32_t d[4] = {0xC0023900u, lo32(address) & ~7u, hi32(address),
                                (static_cast<std::uint32_t>(sem_sel) << 29) |
                                    ((signal_type & 1u) << 20) | ((use_mailbox & 1u) << 16)};
    return emit(cb, d, 4);
}

std::uint32_t *sceAgcCbNop(CommandBuffer *cb, std::uint32_t num_dwords) {
    if (num_dwords == 0) {
        return nullptr;
    }
    std::uint32_t *p = reserve_strict(cb, num_dwords);
    if (p != nullptr) {
        // Only the header is written; the body keeps whatever the memory held.
        p[0] = 0xC0001000u | (((num_dwords - 2u) & 0x3FFFu) << 16);
    }
    return p;
}

std::uint32_t *sceAgcCbReleaseMem(CommandBuffer *cb, std::uint8_t event_type,
                                  std::uint32_t gcr_control, std::uint32_t dst_sel,
                                  std::uint8_t cache_policy, std::uint64_t address,
                                  std::uint32_t data_sel, std::uint64_t data,
                                  std::uint16_t gds_offset, std::uint16_t gds_count,
                                  std::uint8_t interrupt_sel, std::uint32_t interrupt_context_id) {
    std::uint32_t g = gcr_control;
    if ((g & 0x300u) == 0x100u) {
        g |= 0x200u;
    }
    if (interrupt_sel == 4) {
        address = 0;
        data = 0;
    } else if (static_cast<std::uint8_t>(data_sel) == 5) {
        data = (static_cast<std::uint64_t>(gds_count) << 16) | gds_offset;
    }
    const std::uint32_t ev = event_type;
    const std::uint32_t d[8] = {
        0xC0064900u,
        (ev & 0x3Fu) | ((ev > 0x2Eu ? 6u : 5u) << 8) | ((g & 0xFFFu) << 12) |
            ((static_cast<std::uint32_t>(cache_policy) & 3u) << 25),
        ((dst_sel & 3u) << 16) | ((static_cast<std::uint32_t>(interrupt_sel) & 7u) << 24) |
            (data_sel << 29),
        lo32(address) & ~3u,
        hi32(address),
        lo32(data),
        hi32(data),
        interrupt_context_id & 0x7FFFFFFu};
    return emit(cb, d, 8);
}

namespace {
std::uint32_t *range_direct(CommandBuffer *cb, std::uint32_t header, std::uint32_t start_offset,
                            const std::uint32_t *values, std::uint32_t count) {
    const std::uint32_t n = count + 2u;
    if (n == 0) {
        return nullptr;
    }
    std::uint32_t *p = reserve_strict(cb, n);
    if (p == nullptr) {
        return nullptr;
    }
    p[0] = header;
    p[1] = start_offset & 0xFFFFu;
    if (values != nullptr) {
        copy_bytes(p + 2, values, 4ull * count);
    }
    return p;
}

// One SET_* packet per run of consecutive offsets, in list order. A run whose reservation fails
// is skipped; the first packet written is returned.
std::uint32_t *registers_direct(CommandBuffer *cb, std::uint32_t opcode_bits, bool mask_count,
                                const RegPair *regs, std::uint32_t count) {
    if (count == 0) {
        return nullptr;
    }
    std::uint32_t *first = nullptr;
    std::uint32_t i = 0;
    while (i < count) {
        const std::uint32_t start = i;
        while (i + 1 < count && regs[i + 1].offset == regs[i].offset + 1u) {
            ++i;
        }
        const std::uint32_t len = i - start + 1u;
        std::uint32_t *p = reserve_strict(cb, len + 2u);
        if (p != nullptr) {
            p[0] = 0xC0000000u | opcode_bits | ((mask_count ? (len & 0x3FFFu) : len) << 16);
            p[1] = regs[start].offset & 0xFFFFu;
            for (std::uint32_t k = 0; k < len; ++k) {
                p[2 + k] = regs[start + k].value;
            }
            if (first == nullptr) {
                first = p;
            }
        }
        ++i;
    }
    return first;
}
} // namespace

std::uint32_t *sceAgcCbSetShRegisterRangeDirect(CommandBuffer *cb, std::uint32_t start_offset,
                                                const std::uint32_t *values, std::uint32_t count) {
    return range_direct(cb, 0xC0007600u | ((count & 0x3FFFu) << 16), start_offset, values, count);
}

std::uint32_t *sceAgcCbSetUcRegisterRangeDirect(CommandBuffer *cb, std::uint32_t start_offset,
                                                const std::uint32_t *values, std::uint32_t count) {
    // The count is not masked to 14 bits here (as in the original).
    return range_direct(cb, 0xC0007900u | (count << 16), start_offset, values, count);
}

std::uint32_t *sceAgcCbSetShRegistersDirect(CommandBuffer *cb, const RegPair *regs,
                                            std::uint32_t count) {
    return registers_direct(cb, 0x7600u, true, regs, count);
}

std::uint32_t *sceAgcCbSetUcRegistersDirect(CommandBuffer *cb, const RegPair *regs,
                                            std::uint32_t count) {
    return registers_direct(cb, 0x7900u, false, regs, count);
}

std::uint32_t *agcCbFillMemory(CommandBuffer *cb, std::uint64_t dst_address,
                               const std::uint64_t *pattern, std::uint64_t size_bytes) {
    const Shader *shader = state().fill_shader;
    if (shader == nullptr) {
        // deviation: UB in the original (it uses the internal shader without a check).
        return nullptr;
    }
    std::uint32_t *r = sceAgcCbSetShRegistersDirect(cb, ptr<const RegPair>(shader->sh_regs),
                                                    shader->num_sh_regs);
    // Nine user-data dwords: buffer descriptor of the destination plus the pattern and the
    // number of 64 KiB blocks (per the original module's behaviour).
    std::uint32_t user[9];
    user[0] = lo32(dst_address);
    user[1] = (hi32(dst_address) & 0xFFFFu) | 0x00100000u;
    user[2] = static_cast<std::uint32_t>(size_bytes >> 4);
    user[3] = 0x0004BFACu;
    copy_bytes(&user[4], pattern, 16);
    user[8] = static_cast<std::uint32_t>((size_bytes + 0xFFFFu) >> 16);

    const auto *extra = ptr<const std::uint8_t>(shader->extra);
    std::uint16_t u = 0;
    std::uint16_t s = 0;
    if (extra != nullptr) {
        std::memcpy(&u, extra + 0x2A, 2);
        std::uint64_t first_field = 0;
        std::memcpy(&first_field, extra, 8);
        if (first_field != 0) {
            std::memcpy(&s, ptr<const std::uint8_t>(first_field) + 2, 2);
        }
    }
    const std::uint32_t un = std::min<std::uint32_t>(u, 9u); // deviation: UB in the original (u > 9)
    if (std::uint32_t *p = reserve_strict(cb, un + 2u); p != nullptr) {
        p[0] = hdr(0x76, un + 2u);
        p[1] = static_cast<std::uint16_t>(s + 0x240u);
        copy_bytes(p + 2, user, 4ull * un);
    }
    const std::uint32_t mask = soc_class() == kSocB ? 0x00FF00FFu : 0x0003FCFFu;
    const std::uint32_t m0[3] = {0xC0017600u, 0x216u, mask};
    const std::uint32_t m1[3] = {0xC0017600u, 0x217u, mask};
    emit(cb, m0, 3);
    emit(cb, m1, 3);
    std::uint32_t initiator = 0;
    if (const auto *info = ptr<const std::uint8_t>(shader->info); info != nullptr) {
        std::memcpy(&initiator, info + 0x10, 4);
    }
    const std::uint32_t disp[5] = {0xC0031500u, 16u, 1u, 1u,
                                   (initiator & 0xA038u) | state().trace_initiator[9] | 0x41u};
    emit(cb, disp, 5);
    const RegPair a = state().restore_a;
    const RegPair b = state().restore_b;
    const std::uint32_t ra[3] = {0xC0017600u, a.offset & 0xFFFFu, a.value};
    const std::uint32_t rb[3] = {0xC0017600u, b.offset & 0xFFFFu, b.value};
    emit(cb, ra, 3);
    emit(cb, rb, 3);
    return r;
}

} // namespace bc5::reimpl::agc
