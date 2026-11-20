// SPDX-License-Identifier: GPL-2.0-only
// Internal state and helpers shared by the libScePsml re-creation's source files
// (psml_common.cpp, psml_mfsr.cpp, psml_mfsr2.cpp). Not part of any host interface.
// Per the original module's behaviour (clean-room description, see src/reimpl/PROVENANCE.md).
#pragma once

#include "bc5/reimpl/psml.hpp"

#include <atomic>
#include <cstdint>
#include <cstring>

namespace bc5::reimpl::psml::detail {

inline constexpr const char *kModuleName = "libScePsml";

// ---- byte-offset access into mapped objects (memcpy keeps it free of aliasing issues) ----------
template <typename T> inline T ld(const void *base, std::uint64_t off) {
    T v;
    std::memcpy(&v, static_cast<const std::uint8_t *>(base) + off, sizeof(T));
    return v;
}
template <typename T> inline void st(void *base, std::uint64_t off, T v) {
    std::memcpy(static_cast<std::uint8_t *>(base) + off, &v, sizeof(T));
}
inline std::uint8_t *bp(void *p) { return static_cast<std::uint8_t *>(p); }
inline std::uint64_t addr(const void *p) { return reinterpret_cast<std::uint64_t>(p); }
template <typename T = std::uint8_t> inline T *ptr(std::uint64_t a) {
    return reinterpret_cast<T *>(a);
}
inline constexpr std::uint64_t align_up(std::uint64_t v, std::uint64_t a) {
    return (v + a - 1) & ~(a - 1);
}
inline std::uint32_t f2u(float f) {
    std::uint32_t u;
    std::memcpy(&u, &f, 4);
    return u;
}
inline float u2f(std::uint32_t u) {
    float f;
    std::memcpy(&f, &u, 4);
    return f;
}

// ---- module globals (the original's bss/data; addresses in comments are the original's) --------
inline constexpr int kGroupACount = 59; // slots 0x16e800..0x16e9d0
inline constexpr int kMfsr2ShaderCount = 9;

struct ModuleState {
    // Main library (part 1)
    std::uint8_t initialised;                // 0x16ec18
    std::atomic<std::int32_t> context_count; // 0x16ec1c
    std::atomic<std::int32_t> shared_count;  // 0x16ec20
    std::uint8_t feature_bits;               // 0x16ec28
    TextureSizeInfo simple_history_size;     // 0x16ec2c
    std::uint8_t capture_message_printed;    // 0x16ec24
    std::uint8_t flag_16ec38;                // set at init, no reader
    std::uint8_t videoout_mode1;             // 0x16ec39
    std::uint8_t title_allows_mode1;         // 0x16ec10
    std::uint8_t flag_16ec11;                // cleared at gather
    // Shared by both parts
    std::uint8_t system_info_gathered;          // 0x16eb59
    std::uint32_t compiled_sdk_version;         // 0x16eb60
    std::uint32_t system_sw_version;            // 0x16eb64
    std::uint8_t trinity_mode;                  // 0x16eb68
    std::uint8_t process_info[0x98];            // 0x16eb70 (stays zero: stubbed import)
    std::uint8_t version_override_set;          // 0x16ec08
    char version_override[7];                   // 0x16ec09
    std::uint32_t agc_init_out;                 // 0x16ec3c
    std::atomic<std::int32_t> gpu_setup_state;  // 0x16ec40
    std::uint8_t agc_capability;                // 0x16ec44
    std::uint8_t core_shaders_created;          // 0x16eb58
    void *group_a[kGroupACount];                // 0x16e800 + 8*i
    void *event_queue;                          // 0x16e140
    std::uint64_t event_thread;                 // 0x16e148
    std::int32_t power_bucket_index;            // 0x16e7d0
    std::atomic<std::int32_t> power_buckets[8]; // 0x16e7d4
    std::int32_t timer_ticks;                   // 0x16e7f4
    std::uint8_t sharpening_permitted;          // 0x16e7f8
    // MFSR2 (part 2)
    std::uint8_t mfsr2_initialised;                // 0x16e168
    std::atomic<std::int32_t> mfsr2_context_count; // 0x16e16c
    std::atomic<std::int32_t> mfsr2_shared_count;  // 0x16e170
    void *mfsr2_shaders[kMfsr2ShaderCount];        // 0x16e180
    std::uint32_t mfsr2_dispatch_counter;          // 0x16e1c8
    std::uint8_t package_scratch_a[0x300];         // 0x16e1d0
    std::uint8_t package_scratch_b[0x300];         // 0x16e4d0
};
ModuleState &state();

// Index of a group-A slot address (0x16e800..0x16e9d0) in state().group_a.
inline constexpr int slot_index(std::uint32_t slot_addr) {
    return static_cast<int>((slot_addr - 0x16e800u) / 8u);
}

// ---- shared module setup (both libraries' initialise paths) ------------------------------------
std::int32_t system_info_gather();       // once
std::int32_t module_gpu_setup_once();    // once, three-state flag
std::int32_t create_common_shader_set(); // the 59 group-A shaders, once
void create_mfsr2_shaders();             // the 9 group-B shaders, results ignored
void event_thread_start();
const char *effective_version_string();

// Shader creation through the aligned-code wrapper ("createShaderChecked").
std::int32_t create_shader_checked(void **out, void *header, void *code);
// Copy one embedded shader (header 0x130 bytes, code from header +0x44) from the maintainer's
// module file into the module's writable mirrors; nullptr pair when unavailable.
void fetch_embedded_shader(std::uint32_t header_va, std::uint32_t code_va, void **header,
                           void **code);

// ---- shader object accessors (fields of a created Agc shader header) ----------------------------
inline const RegPair *shader_regs(const void *sh) {
    return ptr<const RegPair>(ld<std::uint64_t>(sh, 0x20));
}
inline std::uint32_t shader_reg_count(const void *sh) { return ld<std::uint8_t>(sh, 0x5c); }
inline std::uint32_t shader_stage(const void *sh) { return ld<std::uint8_t>(sh, 0x5a); }
inline const std::uint8_t *shader_layout(const void *sh) {
    return ptr<const std::uint8_t>(ld<std::uint64_t>(sh, 0x28));
}
inline std::uint32_t shader_initiator(const void *sh) {
    const std::uint8_t *l = shader_layout(sh);
    return l == nullptr ? 0u : ld<std::uint32_t>(l, 0x10);
}
// User-data slot start of a kind (0xFFFF = none).
inline std::uint32_t shader_slot_start(const void *sh, std::uint32_t kind) {
    const std::uint8_t *l = shader_layout(sh);
    return l == nullptr ? 0xffffu : ld<std::uint16_t>(l, 2u * kind);
}
std::uint32_t user_data_base(std::uint32_t stage);

// ---- command-buffer helpers --------------------------------------------------------------------
void cb_init(AgcCommandBuffer &cb, std::uint32_t *base, std::uint64_t bytes);
std::uint32_t cb_free_dwords(const AgcCommandBuffer &cb);
// reserveDwords rule of the module's own packets: nullptr when it does not fit.
std::uint32_t *cb_reserve(AgcCommandBuffer &cb, std::uint32_t n);
// A 2-dword type-3 packet built by the module; 0 or kNoRoomForPacket.
std::int32_t cb_raw2(AgcCommandBuffer &cb, std::uint32_t header, std::uint32_t body);
// Take `size` bytes aligned to `align` from the command stream inside a NOP payload.
void *embed_scratch(AgcCommandBuffer &cb, std::uint32_t size, std::uint32_t align);
// Binder-form user data: SET_SH_REG range at stage base + slot start of kind 1, then the data.
std::int32_t write_user_data(AgcCommandBuffer &cb, const void *shader, const void *data,
                             std::uint32_t dwords);
// Pair-form user data loaded with SetShRegistersIndirect (64-bit value into kind 1).
void write_user_data_pairs(AgcCommandBuffer &cb, const void *shader, std::uint64_t value,
                           void *scratch);
void load_shader_registers(AgcCommandBuffer &cb, const void *shader);
void set_shader_registers_direct(AgcCommandBuffer &cb, const void *shader);
void dispatch_if_enabled(AgcCommandBuffer &cb, const void *shader, std::uint32_t x, std::uint32_t y,
                         std::uint32_t z);
// barrier(cb, 1, action): CS partial flush, plus a cache acquire when action == 0x13.
void barrier(AgcCommandBuffer &cb, std::uint32_t action);
void pad_with_nop(AgcCommandBuffer &cb);

// ---- descriptors ------------------------------------------------------------------------------
// Agc "format word": low 32 bits = image/buffer data format, bits 32..43 = destination swizzle.
std::uint32_t bytes_per_element(std::uint32_t data_format);
// {size, alignment} of a 2D texture (own approximation, see psml_common.cpp).
void texture_size(std::uint32_t width, std::uint32_t height, std::uint64_t format_word,
                  std::uint64_t *size, std::uint64_t *alignment);
void build_texture_desc(void *out32, std::uint64_t address, std::uint32_t width,
                        std::uint32_t height, std::uint64_t format_word, std::uint32_t tiling);
std::int32_t build_buffer_desc(void *out16, std::uint64_t address, std::uint32_t elements,
                               std::uint32_t stride, bool allow_null = false);
std::int32_t build_typed_buffer_desc(void *out16, std::uint64_t address, std::uint64_t format_word,
                                     std::uint32_t stride);
inline std::uint32_t tdesc_width(const void *t) {
    return static_cast<std::uint32_t>((ld<std::uint64_t>(t, 4) >> 30) & 0x3fff) + 1u;
}
inline std::uint32_t tdesc_height(const void *t) {
    return static_cast<std::uint32_t>((ld<std::uint64_t>(t, 4) >> 46) & 0x3fff) + 1u;
}
inline std::uint32_t tdesc_format(const void *t) {
    return (ld<std::uint32_t>(t, 4) >> 20) & 0x1ffu;
}
inline std::uint64_t tdesc_address(const void *t) {
    return (static_cast<std::uint64_t>(ld<std::uint32_t>(t, 0)) << 8) |
           (static_cast<std::uint64_t>(ld<std::uint32_t>(t, 4) & 0xffu) << 40);
}
void tdesc_set_size(void *t, std::uint32_t width, std::uint32_t height);
void tdesc_set_format(void *t, std::uint32_t data_format);

// CPU cache-line flush of data the GPU reads (CLFLUSH on x86).
void flush_cpu_lines(const void *p, std::uint64_t bytes);

// Package-file helpers (libc FILE imports).
void *pkg_open(const char *file_name);
bool pkg_read(void *fp, std::uint64_t offset, void *dst, std::uint64_t size);
void pkg_close(void *fp);

float half_to_float(std::uint16_t h);

} // namespace bc5::reimpl::psml::detail
