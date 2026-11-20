// SPDX-License-Identifier: GPL-2.0-only
// libSceAgcDriver re-creation: PM4 writers into callers' command buffers (thread-trace user data,
// debug markers, workload tracking, flip and wait-for-flip) and into the module's own memory
// (register-shadow restore and default-state command buffers), plus the clear-state exports.
//
// Packet names and opcodes cited from Mesa src/amd/common/sid.h @ ab2374a: PKT3_NOP 0x10,
// PKT3_ATOMIC_MEM 0x1E, PKT3_COND_EXEC 0x22, PKT3_CONTEXT_CONTROL 0x28, PKT3_WRITE_DATA 0x37,
// PKT3_INDIRECT_BUFFER 0x3F, PKT3_RELEASE_MEM 0x49, PKT3_LOAD_UCONFIG_REG 0x5E, PKT3_LOAD_SH_REG
// 0x5F, PKT3_LOAD_CONTEXT_REG 0x61, PKT3_SET_UCONFIG_REG 0x79; type-3 header layout from PKT3()
// in the same file. The user-data register is R_030D08_SQ_THREAD_TRACE_USERDATA_2 (Mesa
// src/amd/vulkan/tools/radv_sqtt.c @ ab2374a; uconfig offset 0x342); the next one, written by
// absolute dword address 0xC343, we call SQ_THREAD_TRACE_USERDATA_3 (TODO(verify) name).
// Opcode 0x4A (name unknown: not CLEAR_STATE, which Mesa sid.h @ ab2374a line 41 gives as 0x12) and 0x93 ("WAIT_REG_MEM64") and every control-word value
// below are per the original module's behaviour (clean-room description, see
// src/reimpl/PROVENANCE.md); TODO(verify) those two names, Mesa does not list the opcodes.
#include "bc5/reimpl/agc_driver_internal.hpp"

#include <cstdlib>
#include <cstring>

namespace bc5::reimpl::agc_driver {
namespace detail {

namespace {
std::uint32_t pipe_bit(std::int32_t pipe_flag) { return pipe_flag == 0 ? 4u : 0u; }
std::uint32_t ceil4(std::uint32_t n) { return static_cast<std::uint32_t>((std::uint64_t{n} + 3) / 4); }
} // namespace

std::uint32_t user_data_size(std::uint32_t payload_bytes) {
    if (payload_bytes == 0) {
        return 3;
    }
    const std::uint32_t d = ceil4(payload_bytes);
    return d == 1 ? 4u : d + 7u;
}

std::uint32_t write_user_data(std::uint32_t *dst, std::int32_t pipe_flag, std::uint32_t header_word,
                              const void *payload, std::uint32_t payload_bytes) {
    const std::uint32_t bit = pipe_bit(pipe_flag);
    const bool has_payload = payload != nullptr && payload_bytes > 0;
    std::uint32_t w = 0;
    if (has_payload) {
        dst[0] = 0xC0027900u | bit; // SET_UCONFIG_REG, 3 body dwords
        dst[1] = 0x342;
        dst[2] = header_word;
        std::uint32_t first = 0;
        std::memcpy(&first, payload, payload_bytes < 4 ? payload_bytes : 4);
        dst[3] = first;
        w = 4;
    } else {
        dst[0] = 0xC0017900u | bit; // SET_UCONFIG_REG, 2 body dwords
        dst[1] = 0x342;
        dst[2] = header_word;
        w = 3;
    }
    if (has_payload && payload_bytes > 4) {
        const std::uint32_t rest = payload_bytes - 4;
        const std::uint32_t d = ceil4(rest);
        dst[w + 0] = 0xC0000000u | bit | 0x3700u | ((d + 2u) << 16); // WRITE_DATA to a register
        dst[w + 1] = 0x06010000u;
        dst[w + 2] = 0xC343u;
        dst[w + 3] = 0;
        dst[w + 3 + d] = 0; // zero-pad the last data dword
        std::memcpy(dst + w + 4, static_cast<const std::uint8_t *>(payload) + 4, rest);
        w += 4 + d;
    }
    return w;
}

void write_shadow_restore_cb(std::uint32_t *dst, std::uint64_t shadow_base, bool enabled) {
    const std::uint64_t a = enabled ? shadow_base : 0xFDEAD0000u;
    const std::uint64_t parts[3] = {a, a + 0x8000u, a + 0x9000u};
    const std::uint32_t headers[3] = {0xC0036100u, 0xC0035F00u, 0xC0035E00u};
    std::uint32_t *p = dst;
    for (int i = 0; i < 3; ++i) {
        *p++ = headers[i];
        *p++ = lo32(parts[i]) & ~3u;
        *p++ = hi32(parts[i]);
        *p++ = 0;
        *p++ = 0;
    }
    *p++ = 0xC0012800u;
    *p++ = 0x91018003u;
    *p++ = enabled ? 0x80018003u : 0x80000000u;
}

namespace {

// Pads the r dwords left in a caller reservation with one NOP (or the 1-dword NOP form).
void pad_to_reserved(std::uint32_t *cursor, std::uint32_t r) {
    if (r == 0) {
        return; // deviation: the original writes a stray header past the reservation
    }
    if (r == 1) {
        *cursor = 0xFFFD1000u;
    } else {
        *cursor = 0xC0001000u | ((r - 2u) << 16);
    }
}

std::uint32_t write_data_mem(std::uint32_t *dst, std::uint64_t address, std::uint32_t value) {
    dst[0] = 0xC0000000u | ((1u + 2u) << 16) | 0x3700u;
    dst[1] = 0x40000200u;
    dst[2] = lo32(address) & ~3u;
    dst[3] = hi32(address);
    dst[4] = value;
    return 5;
}

struct Range {
    std::uint32_t start;
    std::uint32_t end;
};

// Collapses an ascending list of {offset, ignored} pairs into inclusive ranges.
std::uint32_t collapse(const std::uint32_t *regs, std::uint32_t n, Range *out) {
    if (regs == nullptr || n == 0) {
        return 0; // deviation: the original reads element 0 even when n == 0
    }
    std::uint32_t count = 0;
    out[0] = {regs[0], regs[0]};
    count = 1;
    for (std::uint32_t i = 1; i < n; ++i) {
        const std::uint32_t off = regs[2 * i];
        if (off == 0xFFFFFFFFu) {
            break;
        }
        Range &cur = out[count - 1];
        if (off > cur.end + 1u) {
            out[count++] = {off, off};
        } else if (off > cur.end) {
            cur.end = off;
        }
    }
    return count;
}

std::uint32_t write_load(std::uint32_t *p, std::uint32_t opcode, std::uint64_t base,
                         const Range *ranges, std::uint32_t r, std::uint32_t default_count) {
    if (r == 0) {
        p[0] = 0xC0030000u | (opcode << 8);
        p[1] = lo32(base) & ~3u;
        p[2] = hi32(base);
        p[3] = 0;
        p[4] = default_count;
        return 5;
    }
    p[0] = 0xC0000000u | ((2u * r + 1u) << 16) | (opcode << 8);
    p[1] = lo32(base);
    p[2] = hi32(base);
    for (std::uint32_t i = 0; i < r; ++i) {
        p[3 + 2 * i] = ranges[i].start;
        p[4 + 2 * i] = ranges[i].end - ranges[i].start + 1u;
    }
    return 3 + 2 * r;
}

std::uint32_t write_zero_loads(std::uint32_t *p, std::uint64_t a) {
    const std::uint64_t parts[3] = {a, a + 0x8000u, a + 0x9000u};
    const std::uint32_t headers[3] = {0xC0036100u, 0xC0035F00u, 0xC0035E00u};
    for (int i = 0; i < 3; ++i) {
        p[5 * i + 0] = headers[i];
        p[5 * i + 1] = lo32(parts[i]);
        p[5 * i + 2] = hi32(parts[i]);
        p[5 * i + 3] = 0;
        p[5 * i + 4] = 0;
    }
    return 15;
}

struct RangeLists {
    const Range *ctx;
    std::uint32_t n_ctx;
    const Range *sh;
    std::uint32_t n_sh;
    const Range *uc;
    std::uint32_t n_uc;
};

// Builds one ring's default-state CB; returns its size in dwords.
std::uint32_t build_default_state_cb(std::uint32_t *dst, std::uint64_t shadow, std::uint64_t label,
                                     const RangeLists &rl, bool is_gfx, bool esvm,
                                     std::uint64_t other_label) {
    std::uint32_t *p = dst;
    *p++ = 0xC0004A00u; // opcode 0x4A, TODO(verify) name
    *p++ = 0;
    std::uint32_t *cond = p;
    p += 5; // COND_EXEC, filled below
    std::uint32_t *cond_body = p;
    *p++ = 0xC0012800u;
    *p++ = 0x91018003u;
    *p++ = 0x80000000u;
    p += write_load(p, 0x61, shadow, rl.ctx, rl.n_ctx, 0x3C0);
    p += write_load(p, 0x5F, shadow + 0x8000u, rl.sh, rl.n_sh, 0x282);
    p += write_load(p, 0x5E, shadow + 0x9000u, rl.uc, rl.n_uc, 0x444);
    const std::uint64_t a = (is_gfx && esvm) ? 0xDEAD0000u : shadow;
    p += write_zero_loads(p, a);
    p += write_data_mem(p, label, 0); // end of the conditional block
    const auto n_cond = static_cast<std::uint32_t>(p - cond_body);
    cond[0] = 0xC0032200u;
    cond[1] = lo32(label);
    cond[2] = hi32(label);
    cond[3] = 0;
    cond[4] = n_cond;
    p += write_zero_loads(p, a);
    *p++ = 0xC0012800u;
    *p++ = 0x91018003u;
    *p++ = (is_gfx && esvm) ? 0x80000000u : 0x80018003u;
    *p++ = 0xC0004A00u;
    *p++ = 1;
    if (!esvm) {
        p += write_data_mem(p, other_label, 1);
    }
    return static_cast<std::uint32_t>(p - dst);
}

// INTEROP TABLE: the default context-register ranges {first absolute register, count} and where
// their u32 values sit in the original module's read-only data (fetched at run time).
struct DefaultRange {
    std::uint32_t first;
    std::uint32_t count;
    std::uint64_t values_at;
};
constexpr DefaultRange kDefaultRanges[] = {
    {0xA000, 0xD7, 0x10520}, {0xA0D8, 0x110, 0x10B20}, {0xA1F5, 4, 0x10880},
    {0xA1FF, 0x9E, 0x10890}, {0xA2A0, 2, 0x10B08},     {0xA2A3, 1, 0x10B10},
    {0xA2A5, 0x42, 0x10F60}, {0xA2F5, 0xCB, 0x11070},
};

const std::uint8_t *default_values(const DefaultRange &r) {
    FirmwareData *fw = bc5::reimpl::firmware_data();
    const std::uint8_t *p =
        fw != nullptr ? fw->get(kModule, r.values_at, std::uint64_t{r.count} * 4u) : nullptr;
    if (p == nullptr) {
        static std::atomic<bool> logged{false};
        if (!logged.exchange(true)) {
            drv_log("default register values not available (firmware data missing)");
        }
    }
    return p;
}

std::uint32_t read_u32(const std::uint8_t *p, std::uint32_t i) {
    std::uint32_t v = 0;
    std::memcpy(&v, p + 4u * i, 4);
    return v;
}

bool stream_ok(std::uint32_t stream_id) { return stream_id >= 1 && stream_id <= 31; }

} // namespace
} // namespace detail

using namespace detail;

// ---------------------------------------------------------------------------------------------
// User data and markers.

std::uint32_t sceAgcDriverUserDataGetPacketSize(std::uint32_t payload_bytes) {
    return user_data_size(payload_bytes);
}

std::uint32_t sceAgcDriverUserDataWritePacket(std::uint32_t *dst, std::int32_t pipe_flag,
                                              std::uint32_t header_word, const void *payload,
                                              std::uint32_t payload_bytes) {
    return write_user_data(dst, pipe_flag, header_word, payload, payload_bytes);
}

namespace {
std::uint32_t marker_header(std::uint32_t base, std::uint32_t text_bytes, std::uint32_t color) {
    const std::uint32_t colour15 =
        ((color >> 1) & 0x7C00u) | ((color >> 14) & 0x3E0u) | (color >> 27);
    return base + ((text_bytes * 0x2000u + 0x6000u) & 0x7F8000u) + colour15;
}
} // namespace

std::uint32_t sceAgcDriverUserDataWriteSetMarker(std::uint32_t *dst, std::int32_t pipe_flag,
                                                 const char *text, std::uint32_t text_bytes,
                                                 std::uint32_t color) {
    return write_user_data(dst, pipe_flag, marker_header(0xC0000000u, text_bytes, color), text,
                           text_bytes);
}

std::uint32_t sceAgcDriverUserDataWritePushMarker(std::uint32_t *dst, std::int32_t pipe_flag,
                                                  const char *text, std::uint32_t text_bytes,
                                                  std::uint32_t color) {
    return write_user_data(dst, pipe_flag, marker_header(0xC1000000u, text_bytes, color), text,
                           text_bytes);
}

std::uint32_t sceAgcDriverUserDataWritePopMarker(std::uint32_t *dst, std::int32_t pipe_flag) {
    dst[0] = 0xC0017900u | pipe_bit(pipe_flag);
    dst[1] = 0x342;
    dst[2] = 0xC2000000u;
    return 3;
}

std::int32_t sceAgcDriverUserDataImmediateWrite() { return kOk; }
std::int32_t sceAgcDriverUserDataImmediateWritePacket() { return kOk; }

std::uint32_t nid_gtvWv7DEKD4(std::uint32_t payload_bytes) {
    return static_cast<std::uint32_t>((std::uint64_t{payload_bytes} + 3) / 4 + 2);
}

std::uint32_t nid_mQfUoU5_d1g(std::uint32_t *dst, std::uint32_t tag, const void *payload,
                              std::uint32_t payload_bytes) {
    const std::uint32_t padded = (payload_bytes + 3u) & ~3u;
    const std::uint32_t total = padded / 4u + 2u;
    std::memset(dst, 0, std::size_t{padded} + 8u);
    dst[0] = 0xC0001000u | ((total - 2u) << 16); // NOP covering the whole blob
    dst[1] = tag;
    if (payload != nullptr && payload_bytes != 0) {
        std::memcpy(dst + 2, payload, payload_bytes);
        return total;
    }
    return 2;
}

// ---------------------------------------------------------------------------------------------
// Workloads.

std::uint32_t sceAgcDriverGetSetWorkloadsActivePacketSize() { return user_data_size(8) + 9u; }
std::uint32_t sceAgcDriverGetSetWorkloadCompletePacketSize() { return user_data_size(0) + 9u; }
std::uint32_t sceAgcDriverGetSetWorkloadStreamInactivePacketSize() { return user_data_size(8); }

std::int32_t sceAgcDriverSetWorkloadsActive(std::uint32_t *dst, std::int32_t pipe_flag,
                                            std::uint32_t stream_id,
                                            const std::uint32_t *workload_indices,
                                            std::uint32_t count) {
    if (dst == nullptr) {
        return kErrNullCommandBuffer;
    }
    if (!stream_ok(stream_id)) {
        return kErrStreamId;
    }
    if ((g_state.workload_mask & (1u << stream_id)) == 0) {
        return kErrStreamNotRegistered;
    }
    if (count < 1 || count > 64 || workload_indices == nullptr) {
        return kErrWorkloadList;
    }
    std::uint64_t mask = 0;
    for (std::uint32_t i = 0; i < count; ++i) {
        const std::uint32_t idx = workload_indices[i];
        if (idx >= 64 || (mask & (std::uint64_t{1} << idx)) != 0) {
            return kErrWorkloadList;
        }
        mask |= std::uint64_t{1} << idx;
    }
    std::uint32_t w = write_user_data(dst, pipe_flag, 0xCC000000u | stream_id, &mask, 8);
    const std::uint64_t target = g_state.workload_status + std::uint64_t{stream_id} * 8u;
    dst[w++] = 0xC0071E00u; // ATOMIC_MEM: 64-bit OR
    dst[w++] = 0x267u | (pipe_flag == 0 ? 0x40000000u : 0u);
    dst[w++] = lo32(target);
    dst[w++] = hi32(target);
    dst[w++] = lo32(mask);
    dst[w++] = hi32(mask);
    dst[w++] = 0;
    dst[w++] = 0;
    dst[w++] = 0;
    return kOk;
}

std::int32_t sceAgcDriverSetWorkloadComplete(std::uint32_t *dst, std::int32_t pipe_flag,
                                             std::uint32_t stream_id,
                                             std::uint32_t workload_index) {
    if (dst == nullptr) {
        return kErrNullCommandBuffer;
    }
    if (!stream_ok(stream_id)) {
        return kErrStreamId;
    }
    if ((g_state.workload_mask & (1u << stream_id)) == 0) {
        return kErrStreamNotRegistered;
    }
    if (workload_index >= 64) {
        return kErrWorkloadList;
    }
    std::uint32_t w =
        write_user_data(dst, pipe_flag, 0xCD000000u + workload_index * 0x20u + stream_id, nullptr, 0);
    const std::uint64_t target = g_state.workload_status + std::uint64_t{stream_id} * 8u;
    const std::uint64_t keep = ~(std::uint64_t{1} << workload_index);
    dst[w++] = 0xC0071E00u; // ATOMIC_MEM: 64-bit AND
    dst[w++] = 0x275u | (pipe_flag == 0 ? 0x40000000u : 0u);
    dst[w++] = lo32(target);
    dst[w++] = hi32(target);
    dst[w++] = lo32(keep);
    dst[w++] = hi32(keep);
    dst[w++] = 0;
    dst[w++] = 0;
    dst[w++] = 0;
    return kOk;
}

std::int32_t sceAgcDriverSetWorkloadStreamInactive(std::uint32_t *dst, std::int32_t pipe_flag,
                                                   std::uint32_t stream_id) {
    if (dst == nullptr) {
        return kErrNullCommandBuffer;
    }
    if (!stream_ok(stream_id)) {
        return kErrStreamId;
    }
    if ((g_state.workload_mask & (1u << stream_id)) == 0) {
        return kErrStreamNotRegistered;
    }
    const std::uint64_t zero = 0;
    (void)write_user_data(dst, pipe_flag, 0xCC000000u | stream_id, &zero, 8);
    return kOk;
}

namespace {
void workload_lock() {
    if (g_imports.mutex_lock != nullptr) {
        (void)g_imports.mutex_lock(&g_state.workload_mutex);
    }
}
void workload_unlock() {
    if (g_imports.mutex_unlock != nullptr) {
        (void)g_imports.mutex_unlock(&g_state.workload_mutex);
    }
}
std::size_t bounded_copy(char *dst, const char *src, std::size_t cap) {
    // strlcpy semantics: copy at most cap-1 bytes, always terminate when cap > 0.
    const std::size_t len = std::strlen(src);
    if (cap != 0) {
        const std::size_t n = len < cap - 1 ? len : cap - 1;
        std::memcpy(dst, src, n);
        dst[n] = '\0';
    }
    return len;
}
} // namespace

std::int32_t sceAgcDriverRegisterWorkloadStream(std::uint32_t stream_id, const char *name) {
    if (!stream_ok(stream_id) || (g_state.workload_mask & (1u << stream_id)) != 0) {
        return kErrStreamId;
    }
    if (name == nullptr) {
        return kErrStreamName;
    }
    workload_lock();
    std::int32_t rc = kOk;
    if ((g_state.workload_mask & (1u << stream_id)) != 0) {
        rc = kErrStreamId;
    } else {
        std::memset(g_state.workload_names[stream_id], 0, 32);
        (void)bounded_copy(g_state.workload_names[stream_id], name, 32);
        g_state.workload_mask |= 1u << stream_id;
    }
    workload_unlock();
    return rc;
}

std::int32_t sceAgcDriverUnregisterWorkloadStream(std::uint32_t stream_id) {
    if (!stream_ok(stream_id)) {
        return kErrStreamId;
    }
    workload_lock();
    std::int32_t rc = kOk;
    if ((g_state.workload_mask & (1u << stream_id)) == 0) {
        rc = kErrStreamNotRegistered;
    } else {
        g_state.workload_mask &= ~(1u << stream_id);
        std::memset(g_state.workload_names[stream_id], 0, 32);
    }
    workload_unlock();
    return rc;
}

std::int32_t sceAgcDriverGetWorkloadStreamInfo(std::uint32_t stream_id, char *name_out,
                                               std::size_t name_cap,
                                               std::uint64_t *active_mask_out) {
    if (!stream_ok(stream_id)) {
        return kErrStreamId;
    }
    workload_lock();
    std::int32_t rc = kOk;
    if ((g_state.workload_mask & (1u << stream_id)) == 0) {
        rc = kErrStreamNotRegistered;
    } else {
        if (name_out != nullptr) {
            (void)bounded_copy(name_out, g_state.workload_names[stream_id],
                               name_cap < 32 ? name_cap : 32);
        }
        if (active_mask_out != nullptr) {
            // deviation: UB in the original when the status array was never set up.
            *active_mask_out =
                g_state.workload_status != 0
                    ? *at<volatile std::uint64_t>(g_state.workload_status + stream_id * 8u)
                    : 0;
        }
    }
    workload_unlock();
    return rc;
}

// ---------------------------------------------------------------------------------------------
// Flip.

std::uint32_t sceAgcDriverGetSetFlipPacketSizeInDwords() { return 0x40; }
std::uint32_t sceAgcDriverGetWaitRenderingPacketSizeInDwords() { return 0x20; }

std::int32_t sceAgcDriverSetFlip(std::uint32_t **cursor, std::uint32_t reserved_dwords,
                                 std::int32_t pipe_flag, std::int32_t videoout_handle,
                                 std::int32_t buffer_index, std::uint32_t flip_mode,
                                 std::int64_t flip_arg) {
    if (buffer_index < -2 || buffer_index > 15) {
        drv_log("display buffer index is invalid (%d)", buffer_index);
        return kErrDisplayBufferIndex;
    }
    constexpr std::uint32_t kUsed = 18;
    // deviation: the original overruns the caller's buffer when the reservation is too small.
    if (cursor == nullptr || *cursor == nullptr || reserved_dwords < kUsed) {
        return kErrInvalid;
    }
    std::uint64_t e = 0;
    std::int32_t r = g_imports.video_out_submit_eop_flip != nullptr
                         ? g_imports.video_out_submit_eop_flip(videoout_handle, buffer_index,
                                                               flip_mode, flip_arg, &e)
                         : kErrGeneric;
    if (r < 0) {
        drv_log("VideoOut EOP flip submit failed (0x%08x)", static_cast<unsigned>(r));
        return r;
    }
    std::uint64_t label = 0;
    if (buffer_index >= 0) {
        std::uint64_t base = 0;
        r = g_imports.video_out_get_buffer_label_address != nullptr
                ? g_imports.video_out_get_buffer_label_address(videoout_handle, &base)
                : kErrGeneric;
        if (r < 0) {
            drv_log("VideoOut label address query failed (0x%08x)", static_cast<unsigned>(r));
            return r;
        }
        label = base + static_cast<std::uint64_t>(buffer_index) * 8u;
    }
    const std::uint32_t bus = g_imports.video_out_sys_get_bus != nullptr
                                  ? g_imports.video_out_sys_get_bus(videoout_handle)
                                  : 0u;
    const auto e32 = static_cast<std::uint32_t>(e);
    std::uint32_t p = 0;
    std::uint32_t low3 = 7;
    if ((e32 & 0x0BFFC000u) == 0x08000000u) {
        p = (e32 >> 12) & 3u;
        if (p == 0) {
            low3 = (e32 & 0xF00u) <= 0x600u ? (e32 >> 8) & 7u : 7u;
        }
    }
    const auto index_bits = static_cast<std::uint32_t>(buffer_index) & 0x1Fu;
    const std::uint32_t header =
        (0xC7010000u + (p << 12) + ((flip_mode & 0xFu) << 8) + (index_bits << 3)) | low3;
    const auto arg = static_cast<std::uint64_t>(flip_arg);
    const std::uint32_t payload[3] = {bus, lo32(arg), hi32(arg)};
    std::uint32_t *start = *cursor;
    std::uint32_t w = write_user_data(start, pipe_flag, header, payload, 12);
    std::uint32_t *rm = start + w;
    rm[0] = 0xC0064900u; // RELEASE_MEM
    rm[1] = pipe_flag == 1 ? 0x0620062Fu : 0x06200504u;
    rm[2] = 0x02010000u | (buffer_index >= 0 ? 0x40000000u : 0u);
    rm[3] = lo32(label) & ~3u;
    rm[4] = hi32(label);
    rm[5] = buffer_index >= 0 ? 1u : 0u;
    rm[6] = 0;
    rm[7] = e32 & 0x0FFFFFFFu;
    w += 8;
    pad_to_reserved(start + w, reserved_dwords - w);
    *cursor = start + reserved_dwords;
    return kOk;
}

std::int32_t sceAgcDriverWaitUntilSafeForRendering(std::uint32_t **cursor,
                                                   std::uint32_t reserved_dwords,
                                                   std::int32_t pipe_flag,
                                                   std::int32_t videoout_handle,
                                                   std::int32_t buffer_index) {
    if (buffer_index < -2 || buffer_index > 15) {
        drv_log("display buffer index is invalid (%d)", buffer_index);
        return kErrDisplayBufferIndex;
    }
    constexpr std::uint32_t kUsed = 15;
    // deviation: the original overruns the caller's buffer when the reservation is too small.
    if (cursor == nullptr || *cursor == nullptr || reserved_dwords < kUsed) {
        return kErrInvalid;
    }
    std::uint64_t label = 0;
    if (buffer_index >= 0) {
        std::uint64_t base = 0;
        const std::int32_t r = g_imports.video_out_get_buffer_label_address != nullptr
                                   ? g_imports.video_out_get_buffer_label_address(videoout_handle,
                                                                                  &base)
                                   : kErrGeneric;
        if (r < 0) {
            drv_log("VideoOut label address query failed (0x%08x)", static_cast<unsigned>(r));
            return r;
        }
        label = base + static_cast<std::uint64_t>(buffer_index) * 8u;
    }
    const auto index_bits = static_cast<std::uint32_t>(buffer_index) & 0x1Fu;
    std::uint32_t *start = *cursor;
    std::uint32_t w = write_user_data(start, pipe_flag, 0xCB000000u + index_bits, nullptr, 0);
    std::uint32_t *q = start + w;
    if (buffer_index < 0) {
        q[0] = 0xC0071000u; // NOP over the 9-dword slot, body untouched
    } else {
        q[0] = 0xC0079300u; // WAIT_REG_MEM64 until the 64-bit label is 0
        q[1] = 0x06000113u;
        q[2] = lo32(label) & ~7u;
        q[3] = hi32(label) & 0x3FFFFu;
        q[4] = 0;
        q[5] = 0;
        q[6] = 0xFFFFFFFFu;
        q[7] = 0xFFFFFFFFu;
        q[8] = 0x40;
    }
    w += 9;
    w += write_user_data(start + w, pipe_flag, 0xCB000020u | index_bits, nullptr, 0);
    pad_to_reserved(start + w, reserved_dwords - w);
    *cursor = start + reserved_dwords;
    return kOk;
}

// ---------------------------------------------------------------------------------------------
// Clear state, default state, register shadow.

std::int32_t sceAgcDriverTmpInitIdhs(std::uint32_t *pairs) {
    if (pairs == nullptr) {
        return kErrInvalid; // deviation: UB in the original
    }
    for (const DefaultRange &r : kDefaultRanges) {
        const std::uint8_t *values = default_values(r);
        if (values == nullptr) {
            continue;
        }
        for (std::uint32_t i = 0; i < r.count; ++i) {
            const std::uint32_t index = r.first + i - 0xA000u;
            pairs[2 * index] = index;
            pairs[2 * index + 1] = read_u32(values, i);
        }
    }
    return kOk;
}

std::int32_t sceAgcDriverPatchClearState(const std::uint32_t *pairs, std::uint32_t count) {
    if (count == 0) {
        return kOk;
    }
    if (count > 0x400) {
        return kErrInvalid;
    }
    if (pairs == nullptr) {
        return kErrInvalid; // deviation: UB in the original
    }
    // Defaults by register index; registers outside the table (or without firmware data) read 0.
    std::uint32_t defaults[0x400] = {};
    for (const DefaultRange &r : kDefaultRanges) {
        const std::uint8_t *values = default_values(r);
        if (values == nullptr) {
            continue;
        }
        for (std::uint32_t i = 0; i < r.count; ++i) {
            defaults[r.first + i - 0xA000u] = read_u32(values, i);
        }
    }
    std::uint32_t changed[2 * 0x400];
    std::uint32_t n = 0;
    for (std::uint32_t i = 0; i < count; ++i) {
        const std::uint32_t reg = pairs[2 * i];
        const std::uint32_t value = pairs[2 * i + 1];
        if (reg < 0x400 && value != defaults[reg]) {
            changed[2 * n] = reg;
            changed[2 * n + 1] = value;
            ++n;
        }
    }
    PatchClearStateArgs a{addr_of(changed), n, 0};
    const bool ok = gc_ioctl(kIoctlPatchClearState, &a) == 0;
    if (g_state.client_type == 0) {
        if (g_state.shadow_gfx.base != 0) {
            std::memset(at<void>(g_state.shadow_gfx.base), 0, g_state.shadow_gfx.size);
        }
        RingSelectArgs sel{0, 1};
        (void)gc_ioctl(kIoctlRingSelect, &sel);
        std::uint64_t sb = 0;
        (void)subblock(2, &sb, nullptr);
        DirectIbPacket packet{{0xC0023F00u, lo32(sb), hi16(sb), 0x12}};
        DirectSubmitArgs d{0, 1, addr_of(&packet)};
        (void)gc_ioctl(kIoctlDirectSubmit, &d);
        ++g_state.gfx_ring0_submits;
    }
    return ok ? kOk : kErrInvalid;
}

std::int32_t sceAgcDriverNotifyDefaultStates(const std::uint32_t *ctx_regs,
                                             const std::uint32_t *sh_regs,
                                             const std::uint32_t *uc_regs, std::uint32_t n_ctx,
                                             std::uint32_t n_sh, std::uint32_t n_uc) {
    // deviation: the original writes the labels at a null base when no driver memory exists.
    if (g_state.dmem_base == 0) {
        return kErrProcessOrMemory;
    }
    auto *ctx = static_cast<Range *>(std::malloc(sizeof(Range) * (std::size_t{n_ctx} + 1)));
    auto *sh = static_cast<Range *>(std::malloc(sizeof(Range) * (std::size_t{n_sh} + 2)));
    auto *uc = static_cast<Range *>(std::malloc(sizeof(Range) * (std::size_t{n_uc} + 2)));
    if (ctx == nullptr || sh == nullptr || uc == nullptr) {
        std::free(ctx);
        std::free(sh);
        std::free(uc);
        drv_log("cannot allocate memory for register segments");
        return kErrProcessOrMemory;
    }
    RangeLists rl{};
    rl.ctx = ctx;
    rl.n_ctx = collapse(ctx_regs, n_ctx, ctx);
    std::uint32_t nsh = collapse(sh_regs, n_sh, sh);
    sh[nsh++] = {0x207, 0x209};
    rl.sh = sh;
    rl.n_sh = nsh;
    std::uint32_t nuc = collapse(uc_regs, n_uc, uc);
    uc[nuc++] = {0x24D, 0x24D};
    rl.uc = uc;
    rl.n_uc = nuc;

    std::uint64_t block_gfx = 0, size_gfx = 0, block_agr = 0, size_agr = 0;
    (void)subblock(0, &block_gfx, &size_gfx);
    (void)subblock(1, &block_agr, &size_agr);
    const std::uint64_t label_gfx = block_gfx + (size_gfx & ~std::uint64_t{3}) - 0x20u;
    const std::uint64_t label_agr = block_agr + (size_agr & ~std::uint64_t{3}) - 0x20u;
    put_u32(label_gfx, 0);
    put_u32(label_agr, 0);
    g_state.label_gfx = label_gfx;
    g_state.label_agr = label_agr;
    const bool esvm = (g_state.client_flags & 1u) != 0;

    const std::uint32_t n_gfx = build_default_state_cb(at<std::uint32_t>(block_gfx),
                                                       g_state.shadow_gfx.base, label_gfx, rl,
                                                       true, esvm, label_agr);
    g_state.defstate_gfx = {block_gfx, n_gfx, 3};
    const std::uint32_t n_agr = build_default_state_cb(at<std::uint32_t>(block_agr),
                                                       g_state.shadow_agr.base, label_agr, rl,
                                                       false, esvm, label_gfx);
    g_state.defstate_agr = {block_agr, n_agr, 3};
    std::free(ctx);
    std::free(sh);
    std::free(uc);
    return kOk;
}

std::int32_t sceAgcDriverSetupRegisterShadow(std::uint32_t ring, std::uint8_t agr, char load_all,
                                             char clear_shadow, std::uint32_t enable) {
    if (g_state.client_type != 0) {
        return kErrNotPermitted;
    }
    if (clear_shadow != 0) {
        const RegShadowInfo &s = agr != 0 ? g_state.shadow_agr : g_state.shadow_gfx;
        if (s.base != 0) {
            std::memset(at<void>(s.base), 0, s.size);
        }
    }
    const std::uint32_t index = ((enable ^ 1u) & 0xFFu) == 0 ? agr + 2u : agr + 4u;
    std::uint64_t start = 0;
    (void)subblock(index, &start, nullptr);
    const std::uint64_t ib = load_all != 0 ? start : start + 0x3Cu;
    const std::uint32_t size = load_all != 0 ? 0x12u : 3u;
    RingSelectArgs sel{ring, 1};
    (void)gc_ioctl(kIoctlRingSelect, &sel);
    if (ring == 0) {
        ++g_state.gfx_ring0_submits;
    } else {
        ++g_state.gfx_other_submits;
    }
    DirectIbPacket packet{{0xC0023F00u, lo32(ib), hi16(ib), size}};
    DirectSubmitArgs d{ring, 1, addr_of(&packet)};
    (void)gc_ioctl(kIoctlDirectSubmit, &d);
    return kOk;
}

std::int32_t sceAgcDriverGetRegShadowInfo(RegShadowInfo *out) {
    if (out == nullptr) {
        return kErrInvalid;
    }
    if (g_state.client_type != 0) {
        return kErrNotPermitted;
    }
    *out = g_state.shadow_gfx;
    return kOk;
}

std::int32_t sceAgcDriverGetRegShadowInfoAgr(RegShadowInfo *out) {
    if (out == nullptr) {
        return kErrInvalid;
    }
    if (g_state.client_type != 0) {
        return kErrNotPermitted;
    }
    *out = g_state.shadow_agr;
    return kOk;
}

std::int32_t sceAgcDriverSetupAsyncGraphics(std::uint32_t enable) {
    if ((g_state.submit_mode & 0xFu) == 0) {
        std::uint32_t mode = 1;
        if (gc_ioctl(kIoctlSetSubmitMode, &mode) != 0) {
            return kErrProcessOrMemory;
        }
        g_state.submit_mode = (g_state.submit_mode & ~0xFu) | 1u;
    }
    g_state.agr_enabled = enable != 0 ? 1u : 0u;
    drv_log("SetupAsyncGraphics(%u): submit mode %u, async graphics %u", enable,
         g_state.submit_mode & 0xFu, g_state.agr_enabled);
    return kOk;
}

// ---------------------------------------------------------------------------------------------
// Info for diagnostics and libSceAgc.

std::int32_t sceAgcDriverPassInfoDownward(const std::uint64_t *entries, std::uint32_t count) {
    const std::uint64_t g = g_state.gpu_info;
    if (g == 0) {
        return kOk; // deviation: null dereference in the original
    }
    put_u32(g + 0xB7250, 0x98);
    if (entries != nullptr) {
        for (std::uint32_t i = 0; i < count; ++i) {
            if (entries[2 * i] == 6) {
                put_u64(g + 0xB7258, entries[2 * i + 1]);
                put_u64(g + 0xB7260, 8);
            }
        }
    }
    std::uint64_t valid = 1;
    put_u64(g + 0xB7268, valid);
    std::uint64_t flex = 0;
    if (g_imports.configured_flexible_memory_size != nullptr &&
        g_imports.configured_flexible_memory_size(&flex) == 0) {
        valid |= 2;
        put_u64(g + 0xB7268, valid);
        put_u64(g + 0xB7270, flex);
    }
    int a = 0, b = 0, c = 0, d = 0;
    if (g_imports.get_page_table_stats != nullptr &&
        g_imports.get_page_table_stats(&a, &b, &c, &d) == 0) {
        valid |= 4;
        put_u64(g + 0xB7268, valid);
        put_u32(g + 0xB7278, static_cast<std::uint32_t>(a));
        put_u32(g + 0xB727C, static_cast<std::uint32_t>(c));
    }
    std::uint64_t info[7] = {0x38, 0, 0, 0, 0, 0, 0};
    if (g_imports.system_info_query != nullptr && g_imports.system_info_query(info) == 0) {
        valid |= 8;
        put_u64(g + 0xB7268, valid);
        std::memcpy(at<void>(g + 0xB7280), &info[1], 0x30);
    }
    return kOk;
}

std::int32_t sceAgcDriverGetReservedDmemForAgc(std::uint64_t *addr_out, std::uint32_t *size_out) {
    if (addr_out == nullptr || size_out == nullptr) {
        return kErrInvalid;
    }
    if (g_state.region_table == nullptr) {
        *addr_out = 0;
        *size_out = 0;
        return kOk;
    }
    *addr_out = region_addr(5);
    *size_out = static_cast<std::uint32_t>(region_size(5));
    return kOk;
}

} // namespace bc5::reimpl::agc_driver
