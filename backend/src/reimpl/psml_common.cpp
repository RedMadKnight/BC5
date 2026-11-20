// SPDX-License-Identifier: GPL-2.0-only
// libScePsml re-creation, the parts both libraries share: module globals, import and export
// tables, the once-only module setup (system info, GPU setup, embedded shader sets, event thread),
// command-buffer and descriptor helpers, the LZ4 block decoder and the four switch sub-libraries
// plus the no-submission stubs.
//
// Everything here follows the original module's behaviour (clean-room description, see
// src/reimpl/PROVENANCE.md) unless a comment says otherwise. Packet header fields (type-3, count
// at bits 16..29, opcode at bits 8..15) follow Mesa src/amd/common/sid.h @ ab2374a (PKT3 macro).
#include "bc5/reimpl/psml_internal.hpp"

#include <cmath>
#include <cstdio>
#include <cstring>
#include <new>
#include <thread>

#if defined(__x86_64__) || defined(_M_X64)
#include <immintrin.h>
#define BC5_PSML_HAVE_CLFLUSH 1
#endif

namespace bc5::reimpl::psml {

namespace {
Imports g_imports{};
alignas(64) detail::ModuleState g_state{};

// Writable mirrors of the original's embedded shader areas: headers 0xf4000..0xfe550 (patched in
// place by sceAgcCreateShader) and code 0x100000..0x164db0 (every blob 256-byte aligned). Shaders
// are copied in from the maintainer's module file on first use, at their original offsets.
constexpr std::uint32_t kHeaderAreaVa = 0xf4000;
constexpr std::uint32_t kHeaderAreaSize = 0xa550;
constexpr std::uint32_t kCodeAreaVa = 0x100000;
constexpr std::uint32_t kCodeAreaSize = 0x64db0;
constexpr std::uint32_t kShaderHeaderSize = 0x130;
alignas(256) std::uint8_t g_header_mirror[kHeaderAreaSize];
alignas(256) std::uint8_t g_code_mirror[kCodeAreaSize];
bool g_header_copied[kHeaderAreaSize / 0x10];

// Relocated callback pointers (the original's 0x168018 timer and 0x168020 video-out callback).
using EventCallback = void (*)();
void timer_callback();
void videoout_mode_callback();
EventCallback g_timer_callback_ptr = &timer_callback;
EventCallback g_videoout_callback_ptr = &videoout_mode_callback;

constexpr std::int16_t kFilterUser = -11;
constexpr std::int16_t kFilterTimer = -7;
constexpr std::int16_t kFilterVideoOut = -13;
constexpr std::uint64_t kTimerEventId = 0x100;
constexpr std::int32_t kStopUserEventId = 1;

// One embedded shader: original header and code addresses (and, for group A, its global slot).
struct EmbeddedShader {
    std::uint32_t slot;
    std::uint32_t header;
    std::uint32_t code;
};

// Group A, the 11 small compute shaders, in creation order (psml2 section 8.2).
constexpr EmbeddedShader kSmallShaders[11] = {
    {0x16e808, 0xf9320, 0x15c600}, {0x16e810, 0xf4be0, 0x107200}, {0x16e800, 0xf4e40, 0x107700},
    {0x16e820, 0xf5430, 0x108300}, {0x16e828, 0xf9450, 0x15c900}, {0x16e818, 0xf91f0, 0x15c200},
    {0x16e830, 0xf5300, 0x108100}, {0x16e838, 0xf51d0, 0x107f00}, {0x16e840, 0xf50a0, 0x107d00},
    {0x16e848, 0xf5560, 0x108500}, {0x16e850, 0xf5690, 0x108a00},
};

// Group A, the 48 main-kernel variants: creation order and pairing slot/header/code (psml1
// section 8.1, an interoperability fact: which variant index uses which binary).
constexpr EmbeddedShader kKernelShaders[48] = {
    {0x16e858, 0xf58f0, 0x109000}, {0x16e918, 0xf5a20, 0x10a600}, {0x16e8b8, 0xf5b50, 0x10bc00},
    {0x16e978, 0xf5c80, 0x10d300}, {0x16e860, 0xf5db0, 0x10ea00}, {0x16e920, 0xf5ee0, 0x110000},
    {0x16e8c0, 0xf6010, 0x111600}, {0x16e980, 0xf6140, 0x112c00}, {0x16e878, 0xf6270, 0x114200},
    {0x16e938, 0xf63a0, 0x115c00}, {0x16e8d8, 0xf64d0, 0x117600}, {0x16e998, 0xf6600, 0x119000},
    {0x16e880, 0xf6730, 0x11aa00}, {0x16e940, 0xf6860, 0x11c300}, {0x16e8e0, 0xf6990, 0x11dc00},
    {0x16e9a0, 0xf6ac0, 0x11f600}, {0x16e898, 0xf6bf0, 0x121000}, {0x16e958, 0xf6d20, 0x122a00},
    {0x16e8f8, 0xf6e50, 0x124400}, {0x16e9b8, 0xf6f80, 0x125e00}, {0x16e8a0, 0xf70b0, 0x127800},
    {0x16e960, 0xf71e0, 0x129100}, {0x16e900, 0xf7310, 0x12aa00}, {0x16e9c0, 0xf7440, 0x12c400},
    {0x16e868, 0xf7570, 0x12de00}, {0x16e928, 0xf76a0, 0x12fb00}, {0x16e8c8, 0xf77d0, 0x131800},
    {0x16e988, 0xf7900, 0x133500}, {0x16e870, 0xf7a30, 0x135200}, {0x16e930, 0xf7b60, 0x136e00},
    {0x16e8d0, 0xf7c90, 0x138a00}, {0x16e990, 0xf7dc0, 0x13a600}, {0x16e888, 0xf7ef0, 0x13c200},
    {0x16e948, 0xf8020, 0x13e200}, {0x16e8e8, 0xf8150, 0x140200}, {0x16e9a8, 0xf8280, 0x142200},
    {0x16e890, 0xf83b0, 0x144200}, {0x16e950, 0xf84e0, 0x146100}, {0x16e8f0, 0xf8610, 0x148000},
    {0x16e9b0, 0xf8740, 0x14a000}, {0x16e8a8, 0xf8870, 0x14c000}, {0x16e968, 0xf89a0, 0x14e000},
    {0x16e908, 0xf8ad0, 0x150000}, {0x16e9c8, 0xf8c00, 0x152100}, {0x16e8b0, 0xf8d30, 0x154200},
    {0x16e970, 0xf8e60, 0x156200}, {0x16e910, 0xf8f90, 0x158200}, {0x16e9d0, 0xf90c0, 0x15a200},
};

// Group B, the 9 MFSR2 shaders (psml2 section 8.1), index = handle slot (0x16e180 + 8*i).
constexpr EmbeddedShader kMfsr2Shaders[detail::kMfsr2ShaderCount] = {
    {0x16e180, 0xf4720, 0x104900}, {0x16e188, 0xf4850, 0x105b00}, {0x16e190, 0xf4130, 0x100300},
    {0x16e198, 0xf4260, 0x100f00}, {0x16e1a0, 0xf4390, 0x102400}, {0x16e1a8, 0xf44c0, 0x103000},
    {0x16e1b0, 0xf4980, 0x106e00}, {0x16e1b8, 0xf4000, 0x100000}, {0x16e1c0, 0xf45f0, 0x104600},
};

bool default_out_of_space(AgcCommandBuffer *, std::uint32_t, void *) {
    if (g_imports.agc_debug_raise_exception != nullptr) {
        g_imports.agc_debug_raise_exception(1, 0);
    }
    return false;
}

void *event_loop(void *) {
    detail::ModuleState &s = detail::state();
    for (;;) {
        KernelEvent ev{};
        std::int32_t got = 0;
        if (g_imports.kernel_wait_equeue == nullptr ||
            g_imports.kernel_wait_equeue(s.event_queue, &ev, 1, &got, nullptr) != 0) {
            // TODO(verify): the original loops on any wait result; without a queue we stop.
            if (g_imports.kernel_wait_equeue == nullptr) {
                return nullptr;
            }
            continue;
        }
        if (!handle_event_for_tests(&ev)) {
            return nullptr;
        }
    }
}

// Timer callback (every 100 ms). The original reaches it through a relocated pointer that the
// description could not follow; this body is ours: count ticks and move to the next of the eight
// power-accounting buckets, clearing it. TODO(verify).
void timer_callback() {
    detail::ModuleState &s = detail::state();
    s.timer_ticks += 1;
    s.power_bucket_index = (s.power_bucket_index + 1) & 7;
    s.power_buckets[s.power_bucket_index].store(0);
}

// Video-out set-mode callback: query the video-out state (32-byte result) and remember whether
// its first dword is 1.
void videoout_mode_callback() {
    std::uint32_t out[8] = {};
    if (g_imports.videoout_mode_query != nullptr) {
        g_imports.videoout_mode_query(out);
    }
    detail::state().videoout_mode1 = out[0] == 1 ? 1 : 0;
}

void strncpy_s_7(char *dst, const char *src) {
    // strncpy_s(dst, 7, src, 7) by the C11 Annex K rules: a source of 7 or more characters is a
    // constraint violation and leaves the empty string.
    std::size_t n = 0;
    while (n < 7 && src[n] != '\0') {
        ++n;
    }
    if (n >= 7) {
        dst[0] = '\0';
        return;
    }
    std::memcpy(dst, src, n);
    dst[n] = '\0';
}
} // namespace

Imports &import_table() { return g_imports; }

namespace detail {

ModuleState &state() { return g_state; }

// ------------------------------------------------------------------------------------------------
// System info, gathered once (shared by both initialise paths).
// ------------------------------------------------------------------------------------------------
std::int32_t system_info_gather() {
    ModuleState &s = state();
    if (s.system_info_gathered != 0) {
        return 0;
    }
    s.compiled_sdk_version = 0;
    s.system_sw_version = 0;
    s.trinity_mode = 0;
    std::memset(s.process_info, 0, sizeof s.process_info);
    s.version_override_set = 0;
    std::memset(s.version_override, 0, sizeof s.version_override);
    s.title_allows_mode1 = 0;
    s.flag_16ec11 = 0;
    if (g_imports.kernel_compiled_sdk_version != nullptr) {
        g_imports.kernel_compiled_sdk_version(&s.compiled_sdk_version);
    }
    // The module carries a fallback for the Trinity query that returns 0: a missing import
    // therefore reads as "not PS5 Pro".
    s.trinity_mode =
        (g_imports.kernel_is_trinity_mode != nullptr && g_imports.kernel_is_trinity_mode() != 0)
            ? 1
            : 0;
    // The process-info import (pid, block, 0x98) is bound to a local "return 0" stub in the
    // original, so the block stays zero; only getpid() is really called.
    if (g_imports.getpid != nullptr) {
        (void)g_imports.getpid();
    }
    std::uint8_t sw[0x28] = {};
    st<std::uint64_t>(sw, 0, sizeof sw); // TODO(verify): size field expected by the kernel
    if (g_imports.kernel_get_prospero_system_sw_version != nullptr) {
        g_imports.kernel_get_prospero_system_sw_version(sw);
    }
    s.system_sw_version = ld<std::uint32_t>(sw, 0x24);
    s.system_info_gathered = 1;
    s.title_allows_mode1 = ((ld<std::uint32_t>(s.process_info, 0x4c) >> 30) & 1u) != 0 ? 1 : 0;
    // Quirk of the original: this clears a mfsrVersion override set before the first initialise.
    s.version_override_set = 0;
    s.flag_16ec11 = 0;
    return 0;
}

const char *effective_version_string() {
    ModuleState &s = state();
    if (s.version_override_set != 0) {
        return s.version_override;
    }
    if (ld<std::uint32_t>(s.process_info, 0x2c) != 0) {
        return reinterpret_cast<const char *>(s.process_info + 0x82);
    }
    return nullptr;
}

// ------------------------------------------------------------------------------------------------
// Module GPU setup, once, guarded by a three-state flag (0 never run, 1 running, 2 done).
// ------------------------------------------------------------------------------------------------
std::int32_t module_gpu_setup_once() {
    ModuleState &s = state();
    std::int32_t expected = 0;
    if (!s.gpu_setup_state.compare_exchange_strong(expected, 1)) {
        while (s.gpu_setup_state.load() != 2) {
            if (g_imports.kernel_usleep != nullptr) {
                g_imports.kernel_usleep(10);
            } else {
                std::this_thread::yield();
            }
        }
        return 0;
    }
    // Headers become CPU read/write + GPU read (create patches them in place); code CPU read +
    // GPU read.
    std::int32_t r = -1;
    if (g_imports.kernel_mprotect != nullptr) {
        r = g_imports.kernel_mprotect(g_header_mirror, kHeaderAreaSize, 0x12);
        if (r == 0) {
            r = g_imports.kernel_mprotect(g_code_mirror, kCodeAreaSize, 0x11);
        }
    }
    if (r != 0) {
        s.gpu_setup_state.store(2);
        return r;
    }
    // libSceAgc initialiser with the Agc API version this module was built against (13).
    r = g_imports.agc_init_with_version != nullptr
            ? g_imports.agc_init_with_version(addr(&s.agc_init_out), 13)
            : -1;
    if (r != 0) {
        // Quirk of the original: the state is NOT set to 2 here, later callers wait forever.
        return r;
    }
    // Register-default tables, public then internal (version 13). The original caches values
    // from them for its statically linked Agc helpers; this re-creation calls libSceAgc's
    // builders directly instead, so the tables are requested but nothing is cached.
    if (g_imports.agc_get_register_defaults2 != nullptr) {
        (void)g_imports.agc_get_register_defaults2(13);
    }
    if (g_imports.agc_get_register_defaults2_internal != nullptr) {
        (void)g_imports.agc_get_register_defaults2_internal(13);
    }
    if (g_imports.agc_capability_query != nullptr) {
        g_imports.agc_capability_query(&s.agc_capability);
    }
    s.gpu_setup_state.store(2);
    return 0;
}

void fetch_embedded_shader(std::uint32_t header_va, std::uint32_t code_va, void **header,
                           void **code) {
    *header = nullptr;
    *code = nullptr;
    if (header_va < kHeaderAreaVa ||
        header_va + kShaderHeaderSize > kHeaderAreaVa + kHeaderAreaSize || code_va < kCodeAreaVa) {
        return;
    }
    const std::uint32_t hoff = header_va - kHeaderAreaVa;
    const std::uint32_t coff = code_va - kCodeAreaVa;
    if (!g_header_copied[hoff / 0x10]) {
        FirmwareData *fd = firmware_data();
        if (fd == nullptr) {
            return;
        }
        const std::uint8_t *h = fd->get(kModuleName, header_va, kShaderHeaderSize);
        if (h == nullptr) {
            return;
        }
        const std::uint32_t code_size = ld<std::uint32_t>(h, 0x44);
        if (coff + static_cast<std::uint64_t>(code_size) > kCodeAreaSize) {
            return;
        }
        const std::uint8_t *c = fd->get(kModuleName, code_va, code_size);
        if (c == nullptr) {
            return;
        }
        std::memcpy(g_header_mirror + hoff, h, kShaderHeaderSize);
        std::memcpy(g_code_mirror + coff, c, code_size);
        // Only the first copy is taken: a retry hands sceAgcCreateShader the already-patched
        // header, as the original does with its own data segment.
        g_header_copied[hoff / 0x10] = true;
    }
    *header = g_header_mirror + hoff;
    *code = g_code_mirror + coff;
}

std::int32_t create_shader_checked(void **out, void *header, void *code) {
    if (out == nullptr || header == nullptr || code == nullptr) {
        return err::kAgcNull;
    }
    if ((addr(code) & 0xff) != 0) {
        return err::kAgcMisaligned;
    }
    if (g_imports.agc_create_shader == nullptr) {
        return err::kAgcNull; // TODO(verify): no Agc, the creation cannot succeed
    }
    return g_imports.agc_create_shader(out, header, addr(code));
}

std::int32_t create_common_shader_set() {
    ModuleState &s = state();
    if (s.core_shaders_created != 0) {
        return 0;
    }
    for (const EmbeddedShader &e : kSmallShaders) {
        void *h = nullptr;
        void *c = nullptr;
        fetch_embedded_shader(e.header, e.code, &h, &c);
        if (create_shader_checked(&s.group_a[slot_index(e.slot)], h, c) != 0) {
            log(kModuleName, "[PSML] failed to create an embedded shader (header 0x%x)", e.header);
            return err::kShaderOrPackage;
        }
    }
    for (const EmbeddedShader &e : kKernelShaders) {
        s.group_a[slot_index(e.slot)] = nullptr;
    }
    for (const EmbeddedShader &e : kKernelShaders) {
        void *h = nullptr;
        void *c = nullptr;
        fetch_embedded_shader(e.header, e.code, &h, &c);
        if (create_shader_checked(&s.group_a[slot_index(e.slot)], h, c) != 0) {
            log(kModuleName, "[PSML] failed to create an embedded shader (header 0x%x)", e.header);
            return err::kShaderOrPackage;
        }
    }
    s.core_shaders_created = 1;
    return 0;
}

void create_mfsr2_shaders() {
    ModuleState &s = state();
    for (int i = 0; i < kMfsr2ShaderCount; ++i) {
        void *h = nullptr;
        void *c = nullptr;
        fetch_embedded_shader(kMfsr2Shaders[i].header, kMfsr2Shaders[i].code, &h, &c);
        // Every result is ignored by the original; a failure leaves the handle as it was.
        (void)create_shader_checked(&s.mfsr2_shaders[i], h, c);
    }
}

void event_thread_start() {
    ModuleState &s = state();
    if (g_imports.kernel_create_equeue != nullptr) {
        g_imports.kernel_create_equeue(&s.event_queue, "ScePsmlEq");
    }
    videoout_mode_callback();
    if (g_imports.videoout_sys_add_set_mode_event2 != nullptr) {
        g_imports.videoout_sys_add_set_mode_event2(s.event_queue, 0, &g_videoout_callback_ptr);
    }
    s.power_bucket_index = 0;
    for (auto &b : s.power_buckets) {
        b.store(0);
    }
    s.timer_ticks = 0;
    if (g_imports.kernel_add_timer_event != nullptr) {
        g_imports.kernel_add_timer_event(s.event_queue, static_cast<std::int32_t>(kTimerEventId),
                                         100000, &g_timer_callback_ptr);
    }
    if (g_imports.kernel_add_user_event != nullptr) {
        g_imports.kernel_add_user_event(s.event_queue, kStopUserEventId);
    }
    if (g_imports.pthread_create != nullptr) {
        g_imports.pthread_create(&s.event_thread, nullptr, &event_loop, nullptr, "ScePsmlEvent");
    }
}

// ------------------------------------------------------------------------------------------------
// Command-buffer helpers.
// ------------------------------------------------------------------------------------------------
std::uint32_t user_data_base(std::uint32_t stage) {
    // INTEROP TABLE (description, rodata 0x6ac58): SH user-data register base by shader stage.
    constexpr std::uint32_t kBase[6] = {0x240, 0x0c, 0x8c, 0x10c, 0x8c, 0x10c};
    return stage < 6 ? kBase[stage] : 0x0cu;
}

void cb_init(AgcCommandBuffer &cb, std::uint32_t *base, std::uint64_t bytes) {
    cb.begin = base;
    cb.cursor = base;
    cb.end = base + (bytes & ~std::uint64_t{3}) / 4;
    cb.limit = cb.end;
    cb.out_of_space = &default_out_of_space;
    cb.user = nullptr;
    cb.reserved_dwords = 0;
    cb.pad = 0;
}

std::uint32_t cb_free_dwords(const AgcCommandBuffer &cb) {
    if (cb.cursor == nullptr || cb.limit == nullptr || cb.limit <= cb.cursor) {
        return 0;
    }
    const std::uint64_t d = static_cast<std::uint64_t>(cb.limit - cb.cursor);
    return d > cb.reserved_dwords ? static_cast<std::uint32_t>(d - cb.reserved_dwords) : 0u;
}

std::uint32_t *cb_reserve(AgcCommandBuffer &cb, std::uint32_t n) {
    if (cb_free_dwords(cb) < n) {
        if (cb.reserved_dwords > 0xffffffffu - n || cb.out_of_space == nullptr) {
            return nullptr;
        }
        if (!cb.out_of_space(&cb, cb.reserved_dwords + n, cb.user) || cb_free_dwords(cb) < n) {
            return nullptr;
        }
    }
    std::uint32_t *p = ptr<std::uint32_t>(align_up(addr(cb.cursor), 4));
    cb.cursor = p + n;
    return p;
}

std::int32_t cb_raw2(AgcCommandBuffer &cb, std::uint32_t header, std::uint32_t body) {
    std::uint32_t *p = cb_reserve(cb, 2);
    if (p == nullptr) {
        return err::kNoRoomForPacket;
    }
    p[0] = header;
    p[1] = body;
    return 0;
}

void *embed_scratch(AgcCommandBuffer &cb, std::uint32_t size, std::uint32_t align) {
    if (g_imports.agc_cb_nop == nullptr) {
        return nullptr;
    }
    std::uint32_t *nop = g_imports.agc_cb_nop(&cb, (size + align) / 4);
    if (nop == nullptr) {
        return nullptr;
    }
    void *payload = nop + 1;
    if (g_imports.agc_get_nop_payload != nullptr) {
        g_imports.agc_get_nop_payload(&payload, nop, 0);
    }
    if (payload == nullptr) {
        return nullptr;
    }
    return ptr<void>(align_up(addr(payload), align));
}

std::int32_t write_user_data(AgcCommandBuffer &cb, const void *shader, const void *data,
                             std::uint32_t dwords) {
    if (shader == nullptr) {
        return err::kAgcNull;
    }
    const std::uint32_t start = shader_slot_start(shader, 1);
    if (start == 0xffffu) {
        return 0;
    }
    const std::uint32_t stage = shader_stage(shader);
    if (stage == 0 && start + dwords > 16) {
        return err::kAgcTooManyUserRegs;
    }
    if (g_imports.agc_cb_set_sh_register_range_direct == nullptr) {
        return err::kNoRoomForPacket;
    }
    std::uint32_t *p = g_imports.agc_cb_set_sh_register_range_direct(
        &cb, user_data_base(stage) + start, nullptr, dwords);
    if (p == nullptr) {
        return err::kNoRoomForPacket;
    }
    std::memcpy(p + 2, data, dwords * 4u);
    return 0;
}

void write_user_data_pairs(AgcCommandBuffer &cb, const void *shader, std::uint64_t value,
                           void *scratch) {
    if (shader == nullptr || scratch == nullptr) {
        return;
    }
    const std::uint32_t start = shader_slot_start(shader, 1);
    if (start == 0xffffu) {
        return;
    }
    const std::uint32_t base = user_data_base(shader_stage(shader)) + start;
    // Kind 1 (an address) takes two dwords.
    RegPair pairs[2] = {{base, static_cast<std::uint32_t>(value)},
                        {base + 1, static_cast<std::uint32_t>(value >> 32)}};
    std::memcpy(scratch, pairs, sizeof pairs);
    if (g_imports.agc_dcb_set_sh_registers_indirect != nullptr) {
        g_imports.agc_dcb_set_sh_registers_indirect(&cb, addr(scratch), 2);
    }
}

void load_shader_registers(AgcCommandBuffer &cb, const void *shader) {
    if (shader != nullptr && g_imports.agc_dcb_set_sh_registers_indirect != nullptr) {
        g_imports.agc_dcb_set_sh_registers_indirect(&cb, addr(shader_regs(shader)),
                                                    shader_reg_count(shader));
    }
}

void set_shader_registers_direct(AgcCommandBuffer &cb, const void *shader) {
    if (shader != nullptr && g_imports.agc_cb_set_sh_registers_direct != nullptr) {
        g_imports.agc_cb_set_sh_registers_direct(&cb, shader_regs(shader),
                                                 shader_reg_count(shader));
    }
}

void dispatch_if_enabled(AgcCommandBuffer &cb, const void *shader, std::uint32_t x, std::uint32_t y,
                         std::uint32_t z) {
    if (shader == nullptr || g_imports.agc_cb_dispatch == nullptr) {
        return;
    }
    const std::uint32_t initiator = shader_initiator(shader);
    if ((initiator & 1u) != 0) {
        g_imports.agc_cb_dispatch(&cb, x, y, z, initiator);
    }
}

void barrier(AgcCommandBuffer &cb, std::uint32_t action) {
    // Event 7 is the CS partial flush (as named by the description); the acquire uses cache
    // control 0x380 and a poll interval of 400.
    if (g_imports.agc_dcb_event_write != nullptr) {
        g_imports.agc_dcb_event_write(&cb, 7, 0);
    }
    if (action == 0x13 && g_imports.agc_dcb_acquire_mem != nullptr) {
        g_imports.agc_dcb_acquire_mem(&cb, 0, 0, 0x380, 0x100, ~std::uint64_t{0}, 400);
    }
}

void pad_with_nop(AgcCommandBuffer &cb) {
    if (g_imports.agc_cb_nop != nullptr) {
        g_imports.agc_cb_nop(&cb, cb_free_dwords(cb));
    }
}

// ------------------------------------------------------------------------------------------------
// Descriptors. The bit positions read here (width/height at bits 30..43 / 46..59 of the qword at
// byte 4, format at dword 1 bits 20..28, type at dword 3 bits 28..31, mips at dword 3 bits 12..19,
// array range in dword 4) are the ones the description names. Where the description is silent
// the choice is ours and marked TODO(verify).
// ------------------------------------------------------------------------------------------------
std::uint32_t bytes_per_element(std::uint32_t f) {
    // TODO(verify): our own classification of the image data-format codes by element size; the
    // original uses statically linked Agc format tables the description does not reproduce.
    if (f >= 1 && f <= 6) {
        return 1;
    }
    if (f >= 7 && f <= 19) {
        return 2;
    }
    if (f >= 20 && f <= 61) {
        return 4;
    }
    if (f >= 62 && f <= 71) {
        return 8;
    }
    if (f >= 72 && f <= 74) {
        return 12;
    }
    if (f >= 75 && f <= 77) {
        return 16;
    }
    if (f == 0x84) {
        return 4;
    }
    return 0;
}

void texture_size(std::uint32_t width, std::uint32_t height, std::uint64_t format_word,
                  std::uint64_t *size, std::uint64_t *alignment) {
    // TODO(verify): own approximation of a swizzled 64 KiB-block layout: the block holds
    // 64 KiB / bpe elements, as square as possible (wider when odd). It reproduces the
    // per-profile VA sizes of the description (3 textures + 2 MiB scratch) exactly, but the
    // original's Agc tiling rules may differ for other sizes.
    const std::uint32_t bpe = bytes_per_element(static_cast<std::uint32_t>(format_word & 0x1ff));
    *alignment = 0x10000;
    if (bpe == 0 || width == 0 || height == 0) {
        *size = 0;
        return;
    }
    std::uint32_t log_bpe = 0;
    while ((1u << (log_bpe + 1)) <= bpe) {
        ++log_bpe;
    }
    const std::uint32_t e = 16 - log_bpe;
    const std::uint64_t bw = std::uint64_t{1} << ((e + 1) / 2);
    const std::uint64_t bh = std::uint64_t{1} << (e / 2);
    *size = align_up(width, bw) * align_up(height, bh) * bpe;
}

void build_texture_desc(void *out32, std::uint64_t address, std::uint32_t width,
                        std::uint32_t height, std::uint64_t format_word, std::uint32_t tiling) {
    std::uint32_t d[8] = {};
    const std::uint32_t w1 = width == 0 ? 0 : width - 1;
    const std::uint32_t h1 = height == 0 ? 0 : height - 1;
    d[0] = static_cast<std::uint32_t>(address >> 8);
    d[1] = static_cast<std::uint32_t>((address >> 40) & 0xff) |
           (static_cast<std::uint32_t>(format_word & 0x1ff) << 20) | ((w1 & 3u) << 30);
    d[2] = ((w1 >> 2) & 0xfffu) | ((h1 & 0x3fffu) << 14);
    // TODO(verify): swizzle in bits 0..11 and tiling in bits 20..24 of dword 3 are our layout.
    d[3] = static_cast<std::uint32_t>((format_word >> 32) & 0xfff) | ((tiling & 0x1fu) << 20) |
           (9u << 28);
    std::memcpy(out32, d, sizeof d);
}

void tdesc_set_size(void *t, std::uint32_t width, std::uint32_t height) {
    std::uint64_t q = ld<std::uint64_t>(t, 4);
    q &= ~((std::uint64_t{0x3fff} << 30) | (std::uint64_t{0x3fff} << 46));
    q |= static_cast<std::uint64_t>((width - 1) & 0x3fff) << 30;
    q |= static_cast<std::uint64_t>((height - 1) & 0x3fff) << 46;
    st<std::uint64_t>(t, 4, q);
}

void tdesc_set_format(void *t, std::uint32_t data_format) {
    std::uint32_t d1 = ld<std::uint32_t>(t, 4);
    d1 = (d1 & ~(0x1ffu << 20)) | ((data_format & 0x1ffu) << 20);
    st<std::uint32_t>(t, 4, d1);
}

std::int32_t build_buffer_desc(void *out16, std::uint64_t address, std::uint32_t elements,
                               std::uint32_t stride, bool allow_null) {
    // Buffer spec {address, elements, format 5, swizzle 0x204, stride, out-of-bounds mode 0 (3
    // when stride 0)}; the 16-byte V# per the description: dword0 = address bits 0..31,
    // dword1 = address bits 32..47 | stride << 16, dword2 = elements, dword3 = swizzle |
    // format << 12 | oob << 28.
    if ((stride & 3u) != 0) {
        return err::kAgcBadStride; // TODO(verify): the stride alignment rule
    }
    if (address == 0 && !allow_null) {
        return err::kAgcNull;
    }
    if ((address & 3u) != 0) {
        return err::kAgcMisaligned;
    }
    const std::uint32_t oob = stride == 0 ? 3u : 0u;
    std::uint32_t d[4];
    d[0] = static_cast<std::uint32_t>(address);
    d[1] = static_cast<std::uint32_t>((address >> 32) & 0xffff) | ((stride & 0x3fffu) << 16);
    d[2] = elements;
    d[3] = 0x204u | ((5u & 0x7fu) << 12) | (oob << 28);
    std::memcpy(out16, d, sizeof d);
    return 0;
}

std::int32_t build_typed_buffer_desc(void *out16, std::uint64_t address, std::uint64_t format_word,
                                     std::uint32_t stride) {
    if ((address & 3u) != 0) {
        return err::kAgcMisaligned;
    }
    std::uint32_t d[4];
    d[0] = static_cast<std::uint32_t>(address);
    d[1] = static_cast<std::uint32_t>((address >> 32) & 0xffff) | ((stride & 0x3fffu) << 16);
    d[2] = 1;
    d[3] = static_cast<std::uint32_t>((format_word >> 32) & 0xfff) |
           ((static_cast<std::uint32_t>(format_word) & 0x7fu) << 12);
    std::memcpy(out16, d, sizeof d);
    return 0;
}

void flush_cpu_lines(const void *p, std::uint64_t bytes) {
#if defined(BC5_PSML_HAVE_CLFLUSH)
    const std::uint64_t start = addr(p) & ~std::uint64_t{63};
    for (std::uint64_t a = start; a < addr(p) + bytes; a += 64) {
        _mm_clflush(ptr<const void>(a));
    }
#else
    (void)p;
    (void)bytes;
#endif
}

// ------------------------------------------------------------------------------------------------
// Package files: "/<sandbox word>/common/psml_package/<file>" through the libc FILE imports.
// ------------------------------------------------------------------------------------------------
void *pkg_open(const char *file_name) {
    const char *word = g_imports.kernel_get_fs_sandbox_random_word != nullptr
                           ? g_imports.kernel_get_fs_sandbox_random_word()
                           : nullptr;
    char path[256];
    std::snprintf(path, sizeof path, "/%s/common/psml_package/%s", word != nullptr ? word : "",
                  file_name);
    if (g_imports.libc_fopen_s == nullptr) {
        return nullptr;
    }
    void *fp = nullptr;
    if (g_imports.libc_fopen_s(&fp, path, "r") != 0) {
        return nullptr;
    }
    return fp;
}

bool pkg_read(void *fp, std::uint64_t offset, void *dst, std::uint64_t size) {
    if (fp == nullptr || dst == nullptr || g_imports.libc_fseek == nullptr ||
        g_imports.libc_fread == nullptr) {
        return false;
    }
    if (g_imports.libc_fseek(fp, static_cast<std::int64_t>(offset), 0) != 0) {
        return false;
    }
    return g_imports.libc_fread(dst, 1, size, fp) == size;
}

void pkg_close(void *fp) {
    if (fp != nullptr && g_imports.libc_fclose != nullptr) {
        g_imports.libc_fclose(fp);
    }
}

float half_to_float(std::uint16_t h) {
    const std::uint32_t sign = static_cast<std::uint32_t>(h & 0x8000u) << 16;
    const std::uint32_t exp = (h >> 10) & 0x1fu;
    const std::uint32_t man = h & 0x3ffu;
    if (exp == 0) {
        const float v = std::ldexp(static_cast<float>(man), -24);
        return sign != 0 ? -v : v;
    }
    if (exp == 31) {
        return u2f(sign | 0x7f800000u | (man << 13));
    }
    return u2f(sign | ((exp + 112u) << 23) | (man << 13));
}

} // namespace detail

// ------------------------------------------------------------------------------------------------
// Pure helpers.
// ------------------------------------------------------------------------------------------------
std::uint16_t float_to_half(float f) {
    const std::uint32_t u = detail::f2u(f);
    const std::uint32_t sign = (u >> 16) & 0x8000u;
    const std::int32_t exp = static_cast<std::int32_t>((u >> 23) & 0xff) - 127 + 15;
    std::uint32_t man = u & 0x7fffffu;
    if (((u >> 23) & 0xff) == 0xff) {
        return static_cast<std::uint16_t>(sign | 0x7c00u | (man != 0 ? 0x200u : 0u));
    }
    if (exp >= 31) {
        return static_cast<std::uint16_t>(sign | 0x7c00u);
    }
    if (exp <= 0) {
        if (exp < -10) {
            return static_cast<std::uint16_t>(sign);
        }
        man |= 0x800000u;
        const std::uint32_t shift = static_cast<std::uint32_t>(14 - exp);
        std::uint32_t h = man >> shift;
        const std::uint32_t rem = man & ((1u << shift) - 1u);
        const std::uint32_t half = 1u << (shift - 1);
        if (rem > half || (rem == half && (h & 1u) != 0)) {
            ++h;
        }
        return static_cast<std::uint16_t>(sign | h);
    }
    std::uint32_t h = (static_cast<std::uint32_t>(exp) << 10) | (man >> 13);
    const std::uint32_t rem = man & 0x1fffu;
    if (rem > 0x1000u || (rem == 0x1000u && (h & 1u) != 0)) {
        ++h; // may carry into the exponent, which is the correct rounding
    }
    return static_cast<std::uint16_t>(sign | h);
}

std::int32_t version_index(const char *version, std::uint32_t sdk) {
    // INTEROP TABLE (description): mfsrVersion strings and their network version index.
    static constexpr const char *kVersions[6] = {"09.40", "09.00", "09.60",
                                                 "10.20", "11.00", "11.60"};
    if (version == nullptr || version[0] == '\0') {
        if (sdk >= 0x01000000u && sdk <= 0x0fffffffu) {
            return 0;
        }
        if ((sdk >> 24) == 0x10u) {
            return 2;
        }
        if (sdk >= 0x11000000u && sdk <= 0xfeffffffu) {
            return 3;
        }
        log(detail::kModuleName,
            "[PSML] param.json mfsrVersion %s isn't supported in Compiled SDK Version 0x%08x",
            version != nullptr ? version : "(null)", sdk);
        return err::kProfileMismatch;
    }
    for (std::int32_t i = 0; i < 6; ++i) {
        if (std::strncmp(version, kVersions[i], 7) == 0) {
            return i;
        }
    }
    log(detail::kModuleName,
        "[PSML] param.json mfsrVersion %s isn't supported in Compiled SDK Version 0x%08x", version,
        sdk);
    return err::kProfileMismatch;
}

std::int32_t lz4_decompress(const void *src, void *dst, std::int32_t src_size,
                            std::int32_t dst_capacity) {
    // Our own decoder of the public LZ4 block format: sequences of {token, literal length
    // extension, literals, 16-bit little-endian offset, match length extension}; the last
    // sequence carries literals only. Every read and write is bounds-checked.
    if (src == nullptr || dst == nullptr || src_size <= 0 || dst_capacity < 0) {
        return -1;
    }
    const std::uint8_t *ip = static_cast<const std::uint8_t *>(src);
    const std::uint8_t *const iend = ip + src_size;
    std::uint8_t *op = static_cast<std::uint8_t *>(dst);
    std::uint8_t *const ostart = op;
    std::uint8_t *const oend = op + dst_capacity;
    if (dst_capacity == 0) {
        return (src_size == 1 && *ip == 0) ? 0 : -1;
    }
    for (;;) {
        if (ip >= iend) {
            return -1;
        }
        const std::uint32_t token = *ip++;
        std::uint64_t lit = token >> 4;
        if (lit == 15) {
            std::uint8_t b = 0;
            do {
                if (ip >= iend) {
                    return -1;
                }
                b = *ip++;
                lit += b;
            } while (b == 255);
        }
        if (lit > static_cast<std::uint64_t>(iend - ip) ||
            lit > static_cast<std::uint64_t>(oend - op)) {
            return -1;
        }
        std::memcpy(op, ip, lit);
        ip += lit;
        op += lit;
        if (ip == iend) {
            break; // last sequence: literals only
        }
        if (iend - ip < 2) {
            return -1;
        }
        const std::uint32_t offset =
            static_cast<std::uint32_t>(ip[0]) | (static_cast<std::uint32_t>(ip[1]) << 8);
        ip += 2;
        if (offset == 0 || offset > static_cast<std::uint64_t>(op - ostart)) {
            return -1;
        }
        std::uint64_t ml = token & 15u;
        if (ml == 15) {
            std::uint8_t b = 0;
            do {
                if (ip >= iend) {
                    return -1;
                }
                b = *ip++;
                ml += b;
            } while (b == 255);
        }
        ml += 4;
        if (ml > static_cast<std::uint64_t>(oend - op)) {
            return -1;
        }
        const std::uint8_t *match = op - offset;
        for (std::uint64_t k = 0; k < ml; ++k) {
            op[k] = match[k]; // byte-wise: overlapping copies repeat the pattern
        }
        op += ml;
    }
    return static_cast<std::int32_t>(op - ostart);
}

bool handle_event_for_tests(const KernelEvent *ev) {
    const std::int32_t filter = g_imports.kernel_get_event_filter != nullptr
                                    ? g_imports.kernel_get_event_filter(ev)
                                    : ev->filter;
    const std::uint64_t id =
        g_imports.kernel_get_event_id != nullptr ? g_imports.kernel_get_event_id(ev) : ev->ident;
    void *udata = g_imports.kernel_get_event_user_data != nullptr
                      ? g_imports.kernel_get_event_user_data(ev)
                      : ev->udata;
    if (filter == kFilterUser && id == static_cast<std::uint64_t>(kStopUserEventId)) {
        return false;
    }
    if (filter == kFilterVideoOut || (filter == kFilterTimer && id == kTimerEventId)) {
        if (udata != nullptr) {
            EventCallback cb = *static_cast<EventCallback *>(udata);
            if (cb != nullptr) {
                cb();
            }
        }
    }
    return true;
}

void reset_state_for_tests() {
    g_state.~ModuleState();
    new (&g_state) detail::ModuleState();
    g_state.simple_history_size = {4, 3840, 2160};
    std::memset(g_header_mirror, 0, sizeof g_header_mirror);
    std::memset(g_code_mirror, 0, sizeof g_code_mirror);
    std::memset(g_header_copied, 0, sizeof g_header_copied);
}

// ------------------------------------------------------------------------------------------------
// Sub-library switches and no-op exports.
// ------------------------------------------------------------------------------------------------
std::int32_t scePsmlNoSubmissionStub0() { return 0; }
std::int32_t scePsmlNoSubmissionStub1() { return 0; }
std::int32_t scePsmlNoSubmissionStub2() { return 0; }

std::int32_t scePsmlEnableSpecularAA() {
    detail::state().sharpening_permitted = 1;
    return 0;
}
std::int32_t scePsmlEnableQuality8K() {
    detail::state().feature_bits = static_cast<std::uint8_t>(detail::state().feature_bits | 1u);
    return 0;
}
std::int32_t scePsmlEnableLightweight() {
    detail::state().feature_bits = static_cast<std::uint8_t>(detail::state().feature_bits | 2u);
    return 0;
}
std::int32_t scePsmlSetMfsrVersion(const char *version) {
    if (version == nullptr) {
        return err::kInvalidParameter;
    }
    detail::ModuleState &s = detail::state();
    s.version_override_set = 1;
    strncpy_s_7(s.version_override, version);
    return 0;
}

// ------------------------------------------------------------------------------------------------
// Export and import tables.
// ------------------------------------------------------------------------------------------------
namespace {
template <typename F> void *fn(F f) { return reinterpret_cast<void *>(f); }

// Names are empty (the originals are unnamed); the proposed name is in the comment.
const ExportEntry kExports[] = {
    {"3WVD91e12ZQ", "libScePsml", "", fn(&psmlInitialize), false},
    {"+2KpvixvL6E", "libScePsml", "", fn(&mfsrGetSharedResourcesInitRequirement), false},
    {"eWoKNeB6V-k", "libScePsml", "", fn(&mfsrCreateSharedResources), false},
    {"jEevBXmagOQ", "libScePsml", "", fn(&mfsrReleaseSharedResources), false},
    {"EO9YQXmJEN8", "libScePsml", "", fn(&mfsrGetSimpleInitRequirement), false},
    {"IMlj247LdTo", "libScePsml", "", fn(&mfsrGetContextAndSharedInitRequirement), false},
    {"sjTyYheKTrU", "libScePsml", "", fn(&mfsrGetContextInitRequirementV1), false},
    {"ArakEpzsZo0", "libScePsml", "", fn(&mfsrGetContextInitRequirementV2), false},
    {"VGjrQa-WqdU", "libScePsml", "", fn(&mfsrGetContextInitRequirementV3), false},
    {"2ecEbQaf9VU", "libScePsml", "", fn(&mfsrCreateContextSimple), false},
    {"vUk2pWMx3KQ", "libScePsml", "", fn(&mfsrCreateContextWithOwnSharedResources), false},
    {"pwUkfVu0c0c", "libScePsml", "", fn(&mfsrCreateContextV1), false},
    {"gxv3i+MTEzU", "libScePsml", "", fn(&mfsrCreateContextV2), false},
    {"fccGInHrj8A", "libScePsml", "", fn(&mfsrCreateContextV3), false},
    {"JaLBe0P3jSU", "libScePsml", "", fn(&mfsrReleaseContext), false},
    {"AHalTX9wFZY", "libScePsml", "", fn(&mfsrGetDispatchCommandSize), false},
    {"CN7uea0UQso", "libScePsml", "", fn(&mfsrDispatchExplicitMatrix), false},
    {"wHto4IznfBE", "libScePsml", "", fn(&mfsrDispatchFloatCamera), false},
    {"RUNLFro+qok", "libScePsml", "", fn(&mfsrDispatchDoubleCamera), false},
    {"s2psNHUIdjk", "libScePsml", "", fn(&mfsrDispatchNative), false},
    {"94iBp3KvIuI", "libScePsml", "", fn(&mfsrDispatchNativeValidated), false},
    {"GHna9-DvnUk", "libScePsml", "", fn(&mfsrGetMipLodBias), false},
    {"GJY0MvuTcs8", "libScePsml", "", fn(&mfsrRequestCapture), false},
    {"LXq+6mIxpCw", "libScePsml", "", fn(&mfsrContextNoOpA), false},
    {"FSGaTQze0UY", "libScePsml", "", fn(&mfsrContextNoOpB), false},
    {"o+NM86gEwFE", "libScePsml_mfsr2", "", fn(&sceMfsr2Initialize), false},
    {"1ic5q-kdOsc", "libScePsml_mfsr2", "", fn(&sceMfsr2GetSharedResourcesInitRequirement), false},
    {"gMduXCLYrNg", "libScePsml_mfsr2", "", fn(&sceMfsr2CreateSharedResources), false},
    {"0GAw7SmkwII", "libScePsml_mfsr2", "", fn(&sceMfsr2ReleaseSharedResources), false},
    {"5z2gBlqxJ+0", "libScePsml_mfsr2", "", fn(&sceMfsr2GetContextInitRequirement), false},
    {"m9JLPc3wOQw", "libScePsml_mfsr2", "", fn(&sceMfsr2CreateContext), false},
    {"Kyy1baXgaVU", "libScePsml_mfsr2", "", fn(&sceMfsr2ReleaseContext), false},
    {"ZLL31lzzxr4", "libScePsml_mfsr2", "", fn(&sceMfsr2GetDispatchCommandSize), false},
    {"lrJwpLjKXRc", "libScePsml_mfsr2", "", fn(&sceMfsr2Dispatch), false},
    {"6T4lBsFKo7U", "libScePsml_nosubmission", "", fn(&scePsmlNoSubmissionStub0), false},
    {"tDFGCPGK0Fo", "libScePsml_nosubmission", "", fn(&scePsmlNoSubmissionStub1), false},
    {"fwcwm67Nopg", "libScePsml_nosubmission", "", fn(&scePsmlNoSubmissionStub2), false},
    {"xNZM9Y5lf-M", "libScePsml_specularAA", "", fn(&scePsmlEnableSpecularAA), false},
    {"lcZD9tJraAw", "libScePsml_quality8K", "", fn(&scePsmlEnableQuality8K), false},
    {"TupVXn-8vU4", "libScePsml_lightweight", "", fn(&scePsmlEnableLightweight), false},
    {"3E85qTivV78", "libScePsml_set_mfsrversion", "", fn(&scePsmlSetMfsrVersion), false},
};
static_assert(sizeof kExports / sizeof kExports[0] == 41);

template <typename T> void **slot(T *member) { return reinterpret_cast<void **>(member); }

// NIDs: the ones the description names are taken as given; the others are derived from the
// public function names with the public NID hash (SHA-1 of name + fixed suffix).
const ImportSlot kImports[] = {
    {"vSMAm3cxYTY", "libkernel", "sceKernelMprotect", slot(&g_imports.kernel_mprotect)},
    {"NcaWUxfMNIQ", "libkernel", "sceKernelMapNamedDirectMemory",
     slot(&g_imports.kernel_map_named_direct_memory)},
    {"cQke9UuBQOk", "libkernel", "sceKernelMunmap", slot(&g_imports.kernel_munmap)},
    {"kBJzF8x4SyE", "libkernel", "sceKernelBatchMap2", slot(&g_imports.kernel_batch_map2)},
    {"D0OdFMjp46I", "libkernel", "sceKernelCreateEqueue", slot(&g_imports.kernel_create_equeue)},
    {"4R6-OvI2cEA", "libkernel", "sceKernelAddUserEvent", slot(&g_imports.kernel_add_user_event)},
    {"57ZK+ODEXWY", "libkernel", "sceKernelAddTimerEvent", slot(&g_imports.kernel_add_timer_event)},
    {"F6e0kwo4cnk", "libkernel", "sceKernelTriggerUserEvent",
     slot(&g_imports.kernel_trigger_user_event)},
    {"fzyMKs9kim0", "libkernel", "sceKernelWaitEqueue", slot(&g_imports.kernel_wait_equeue)},
    {"23CPPI1tyBY", "libkernel", "sceKernelGetEventFilter",
     slot(&g_imports.kernel_get_event_filter)},
    {"mJ7aghmgvfc", "libkernel", "sceKernelGetEventId", slot(&g_imports.kernel_get_event_id)},
    {"vz+pg2zdopI", "libkernel", "sceKernelGetEventUserData",
     slot(&g_imports.kernel_get_event_user_data)},
    {"6UgtwV+0zb4", "libkernel", "scePthreadCreate", slot(&g_imports.pthread_create)},
    {"1jfXLRVzisc", "libkernel", "sceKernelUsleep", slot(&g_imports.kernel_usleep)},
    {"HoLVWNanBBc", "libkernel", "getpid", slot(&g_imports.getpid)},
    {"aML18Z0J0t0", "libkernel", "sceKernelGetProsperoSystemSwVersion",
     slot(&g_imports.kernel_get_prospero_system_sw_version)},
    {"JGfTMBOdUJo", "libkernel", "sceKernelGetFsSandboxRandomWord",
     slot(&g_imports.kernel_get_fs_sandbox_random_word)},
    {"GGeRJk1XdWc", "libkernel", "nid_GGeRJk1XdWc (compiled SDK version)",
     slot(&g_imports.kernel_compiled_sdk_version)},
    {"tU5e3f9gSiU", "libkernel", "sceKernelIsTrinityMode", slot(&g_imports.kernel_is_trinity_mode)},
    {"gO98NioN5FM", "libkernel", "sceKernelReleaseToolMemory",
     slot(&g_imports.kernel_release_tool_memory)},
    {"fYWVVDKZOCk", "libSceVideoOut", "sceVideoOutSysAddSetModeEvent2",
     slot(&g_imports.videoout_sys_add_set_mode_event2)},
    {"Ygv0S+Hi+hA", "libSceVideoOut", "nid_Ygv0S+Hi+hA (mode query)",
     slot(&g_imports.videoout_mode_query)},
    {"NL836gOLANs", "libSceLibcInternal", "fopen_s", slot(&g_imports.libc_fopen_s)},
    {"rQFVBXp-Cxg", "libSceLibcInternal", "fseek", slot(&g_imports.libc_fseek)},
    {"lbB+UlZqVG0", "libSceLibcInternal", "fread", slot(&g_imports.libc_fread)},
    {"uodLYyUip20", "libSceLibcInternal", "fclose", slot(&g_imports.libc_fclose)},
    {"f3dg2CSgRKY", "libSceAgc", "sceAgcCreateShader", slot(&g_imports.agc_create_shader)},
    {"2JtWUUiYBXs", "libSceAgc", "sceAgcGetRegisterDefaults2",
     slot(&g_imports.agc_get_register_defaults2)},
    {"wRbq6ZjNop4", "libSceAgc", "sceAgcGetRegisterDefaults2Internal",
     slot(&g_imports.agc_get_register_defaults2_internal)},
    {"UZbQjYAwwXM", "libSceAgc", "sceAgcCbSetShRegistersDirect",
     slot(&g_imports.agc_cb_set_sh_registers_direct)},
    {"n2fD4A+pb+g", "libSceAgc", "sceAgcCbSetShRegisterRangeDirect",
     slot(&g_imports.agc_cb_set_sh_register_range_direct)},
    {"k3GhuSNmBLU", "libSceAgc", "sceAgcCbDispatch", slot(&g_imports.agc_cb_dispatch)},
    {"LtTouSCZjHM", "libSceAgc", "sceAgcCbNop", slot(&g_imports.agc_cb_nop)},
    {"+kSrjIVxKFE", "libSceAgc", "sceAgcDcbPushMarker", slot(&g_imports.agc_dcb_push_marker)},
    {"N7M3+N-sBCw", "libSceAgc", "sceAgcDcbPushMarkerSpan",
     slot(&g_imports.agc_dcb_push_marker_span)},
    {"H7uZqCoNuWk", "libSceAgc", "sceAgcDcbPopMarker", slot(&g_imports.agc_dcb_pop_marker)},
    {"-HOOCn0JY48", "libSceAgc", "sceAgcDcbSetShRegistersIndirect",
     slot(&g_imports.agc_dcb_set_sh_registers_indirect)},
    {"aJf+j5yntiU", "libSceAgc", "sceAgcDcbEventWrite", slot(&g_imports.agc_dcb_event_write)},
    {"57labkp+rSQ", "libSceAgc", "sceAgcDcbAcquireMem", slot(&g_imports.agc_dcb_acquire_mem)},
    {"zARR5aCmkoY", "libSceAgc", "nid_zARR5aCmkoY", slot(&g_imports.agc_dcb_bracket_packet)},
    {"T6xuVw0KUJo", "libSceAgc", "sceAgcDebugRaiseException",
     slot(&g_imports.agc_debug_raise_exception)},
    {"23LRUSvYu1M", "libSceAgc", "nid_23LRUSvYu1M (init with version)",
     slot(&g_imports.agc_init_with_version)},
    {"BfBDZGbti7A", "libSceAgc", "nid_BfBDZGbti7A", slot(&g_imports.agc_capability_query)},
    {"V++UgBtQhn0", "libSceAgc", "nid_V++UgBtQhn0 (NOP payload address)",
     slot(&g_imports.agc_get_nop_payload)},
    {"VhLnEiTuuWo", "libSceAgcDriver", "sceAgcDriverUserDataGetPacketSize",
     slot(&g_imports.driver_user_data_get_packet_size)},
    {"-vc-xL+G8u0", "libSceAgcDriver", "sceAgcDriverUserDataWritePacket",
     slot(&g_imports.driver_user_data_write_packet)},
    {"gtvWv7DEKD4", "libSceAgcDriver", "nid_gtvWv7DEKD4 (data packet size)",
     slot(&g_imports.driver_data_packet_size)},
    {"mQfUoU5-d1g", "libSceAgcDriver", "nid_mQfUoU5-d1g (data packet)",
     slot(&g_imports.driver_write_data_packet)},
};
} // namespace

} // namespace bc5::reimpl::psml

namespace bc5::reimpl::psml {
std::span<const ExportEntry> exports() { return kExports; }
std::span<const ImportSlot> imports() { return kImports; }
} // namespace bc5::reimpl::psml
