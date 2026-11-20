// SPDX-License-Identifier: GPL-2.0-only
// Clean-room re-creation of libSceAgc (see src/reimpl/PROVENANCE.md): module-internal state,
// import slots and helpers shared by the agc*.cpp files. Not part of the guest ABI.
#pragma once

#include "bc5/reimpl/agc.hpp"

#include <cstdint>
#include <cstring>

#if defined(_MSC_VER)
#include <intrin.h>
#pragma intrinsic(_ReturnAddress)
#define BC5_AGC_RETURN_ADDRESS()                                                                   \
    static_cast<std::uint64_t>(reinterpret_cast<std::uintptr_t>(_ReturnAddress()))
#else
#define BC5_AGC_RETURN_ADDRESS()                                                                   \
    static_cast<std::uint64_t>(reinterpret_cast<std::uintptr_t>(__builtin_return_address(0)))
#endif

namespace bc5::reimpl::agc::detail {

inline constexpr const char *kModule = "libSceAgc";

// ---- import slots (resolved by the host glue; nullptr = not available) --------------------------
struct Imports {
    // libSceAgcDriver
    std::uint32_t (*ud_get_packet_size)(std::uint32_t payload_bytes);
    std::uint32_t (*ud_write_packet)(std::uint32_t *dst, int pipe_flag, std::uint32_t header_word,
                                     const void *payload, std::uint32_t payload_bytes);
    std::uint32_t (*ud_write_set_marker)(std::uint32_t *dst, int pipe_flag, const char *text,
                                         std::uint32_t text_bytes, std::uint32_t color);
    std::uint32_t (*ud_write_push_marker)(std::uint32_t *dst, int pipe_flag, const char *text,
                                          std::uint32_t text_bytes, std::uint32_t color);
    std::uint32_t (*ud_write_pop_marker)(std::uint32_t *dst, int pipe_flag);
    std::uint32_t (*get_set_flip_size)();
    std::uint32_t (*get_wait_rendering_size)();
    int (*set_flip)(std::uint32_t **cursor, std::uint32_t reserved_dwords, int pipe_flag, int arg0,
                    int arg1, std::uint32_t arg2, std::int64_t arg3);
    int (*wait_until_safe)(std::uint32_t **cursor, std::uint32_t reserved_dwords, int pipe_flag,
                           int arg0, int arg1);
    std::uint32_t (*get_workloads_active_size)();
    std::uint32_t (*get_workload_complete_size)();
    std::uint32_t (*get_workload_stream_inactive_size)();
    int (*set_workloads_active)(std::uint32_t *dst, int pipe_flag, std::uint32_t arg0,
                                const std::uint32_t *arg1, std::uint32_t arg2);
    int (*set_workload_complete)(std::uint32_t *dst, int pipe_flag, std::uint32_t arg0,
                                 std::uint32_t arg1);
    int (*set_workload_stream_inactive)(std::uint32_t *dst, int pipe_flag, std::uint32_t arg0);
    int (*get_trace_initiator)(std::uint32_t index);
    int (*tmp_init_idhs)(std::uint32_t *pairs, std::uint32_t count);
    int (*patch_clear_state)(const std::uint32_t *pairs, std::uint32_t count);
    int (*notify_default_states)(const std::uint32_t *cx, const std::uint32_t *sh,
                                 const std::uint32_t *uc, std::uint32_t n_cx, std::uint32_t n_sh,
                                 std::uint32_t n_uc);
    int (*pass_info_downward)(const std::uint64_t *entries, std::uint32_t count);
    int (*submit_acb)(std::uint32_t queue_id, const CbDescriptor *desc);
    int (*register_gpu_reset_callbacks)(const void *callbacks);
    int (*suspend_submit)(const CbDescriptor *desc, std::uint32_t *status_out,
                          std::uint32_t suspend_arg); // NID kAPt2J4U3v8
    int (*set_kernel_submit_flag)(int enable);        // NID oFb2hMcoJa4
    std::uint8_t (*is_esvm)();                        // NID SFB48L57OKQ
    int (*raise_exception)(int kind, std::uint64_t arg); // NID yuO+lNrj+Do
    int (*is_pa_debug)();
    int (*get_reserved_dmem)(std::uint64_t *addr_out, std::uint32_t *size_out);
    // libkernel
    std::uint32_t (*get_main_soc_id)();
    int (*mutex_init)(void **mutex, const void *attr, const char *name);
    int (*mutex_lock)(void **mutex);
    int (*mutex_unlock)(void **mutex);
    int (*mutex_destroy)(void **mutex);
    int (*getpid)();
    int (*get_app_info)(int pid, void *info);
    int (*title_workaround_is_enabled)(const void *info, std::uint32_t id, int *out);
    int (*query_app_type)(void *buffer);   // NID GGeRJk1XdWc = sceKernelGetProsperoCompiledSdkVersion (NID hash of the name)
    int (*query_kernel_flag)();            // NID tU5e3f9gSiU, TODO(verify) meaning
    int (*get_app_category_type)(int pid, int *category);
    // libSceRegMgr / libSceSysmodule
    int (*regmgr_get_int)(std::uint64_t key, int unused, int *out);
    int (*sysmodule_load_internal)(std::uint32_t id);
    // libSceShaderTranscode_minimal (weak: a missing slot behaves as returning 0)
    int (*transcode_query)(); // NID wDAAPuG6uN4
    // libc
    void *(*memcpy)(void *dst, const void *src, std::size_t n);
    void *(*memset)(void *dst, int value, std::size_t n);
    std::size_t (*strlen)(const char *s);
};
extern Imports g_imports;

// ---- module state -----------------------------------------------------------------------------
struct QueueSlot {
    RegPair *cx;
    RegPair *sh;
    RegPair *uc;
    std::uint32_t cx_count;
    std::uint32_t sh_count;
    std::uint32_t uc_count;
    std::uint32_t uc_special_count;
    std::uint32_t *sh_stream;
    std::uint32_t sh_stream_bytes;
    std::uint32_t *resume_dcb;
    std::uint32_t resume_dwords;
    std::uint32_t version; // 0 = free
    std::uint8_t trusted;
};

struct State {
    std::uint8_t suspend_not_ready;
    std::int32_t active_slot;
    std::uint64_t static_area;
    std::uint64_t expected_static_area;
    std::uint32_t suspend_config;
    std::uint32_t workaround_mask;
    QueueSlot slots[2];
    RegPair restore_a; // SH 0x216 default (compute static thread-management mask)
    RegPair restore_b; // SH 0x217 default
    std::uint32_t trace_initiator[11]; // index 1..10
    std::uint64_t trusted_lo;
    std::uint64_t trusted_hi;
    void *mutex;
    std::uint64_t sync_label;
    std::uint64_t sem_base;
    std::uint64_t sem_size;
    bool internal_shaders_created;
    std::uint32_t soc_id;
    bool kernel_flag;
    std::uint32_t use_clear_state_for_cx;
    bool regmgr_available;
    std::uint64_t dmem_cursor;
    std::uint64_t dmem_end;
    const Shader *fill_shader;
    std::uint32_t uc_special_offset; // descriptor at 0x45C40 of the original (unresolved here)
};
State &state();
void reset_state();

inline constexpr std::uint64_t kStaticAreaAddress = 0xFE0040000ull;
inline constexpr std::uint32_t kSocA = 0x840F00; // `(soc & ~0x1F)` comparisons
inline constexpr std::uint32_t kSocB = 0x840FC0;

inline std::uint32_t soc_class() { return state().soc_id & ~0x1Fu; }

// ---- small helpers ------------------------------------------------------------------------------
inline std::uint32_t lo32(std::uint64_t v) { return static_cast<std::uint32_t>(v); }
inline std::uint32_t hi32(std::uint64_t v) { return static_cast<std::uint32_t>(v >> 32); }
template <typename T> inline T *ptr(std::uint64_t address) {
    return reinterpret_cast<T *>(static_cast<std::uintptr_t>(address));
}
inline std::uint64_t addr(const void *p) {
    return static_cast<std::uint64_t>(reinterpret_cast<std::uintptr_t>(p));
}
inline std::uint8_t opcode_of(const std::uint32_t *packet) {
    return static_cast<std::uint8_t>((packet[0] >> 8) & 0xFF);
}
// Type-3 header for a packet of n dwords total (count field n - 2, 14 bits).
inline std::uint32_t hdr(std::uint32_t opcode, std::uint32_t total_dwords) {
    return 0xC0000000u | (((total_dwords - 2u) & 0x3FFFu) << 16) | (opcode << 8);
}

void copy_bytes(void *dst, const void *src, std::size_t n);
void fill_bytes(void *dst, int value, std::size_t n);
std::size_t string_length(const char *s);

// Write `n` dwords at the cursor that a soft reservation has checked, return their start.
std::uint32_t *emit_raw(CommandBuffer *cb, const std::uint32_t *dwords, std::uint32_t n);
// Strict reservation + copy of the given dwords; nullptr on failure.
std::uint32_t *emit(CommandBuffer *cb, const std::uint32_t *dwords, std::uint32_t n);

// Driver user-data packet at the (unaligned) cursor; returns the start, advances the cursor.
std::uint32_t *write_user_data(CommandBuffer *cb, int is_acb, std::uint32_t id, const void *payload,
                               std::uint32_t payload_bytes);

// Locks of the module mutex: failures are logged and ignored.
void mutex_lock();
void mutex_unlock();

bool is_trusted_caller(std::uint64_t return_address);
QueueSlot *slot_for_queue(std::uint32_t index);
QueueSlot *active_slot();
std::uint64_t dmem_alloc(std::uint64_t size, std::uint64_t align);
std::uint64_t dmem_peek(std::uint64_t size, std::uint64_t align);

// Weak import wDAAPuG6uN4: a missing slot behaves as the module's own weak stub (returns 0).
int transcode_query();

// H8 / H9 / H10 / reset bodies (agc_dcb.cpp, agc_acb.cpp).
std::uint32_t *conditional_roll_notify(CommandBuffer *cb, std::uint32_t op, bool update_label);
std::uint32_t *conditional_clear_state(CommandBuffer *cb);
std::uint32_t *emit_load_cx_defaults(CommandBuffer *cb, const QueueSlot *slot);
std::uint32_t *dcb_reset_queue_body(CommandBuffer *cb, std::uint16_t flags, QueueSlot *slot,
                                    bool trusted);
std::uint32_t *acb_reset_queue_body(CommandBuffer *cb, std::uint16_t flags, QueueSlot *slot,
                                    bool trusted);

// Driver-backed and shared builder bodies (agc_acb.cpp), used by both queue kinds.
std::uint32_t *marker(CommandBuffer *cb, int is_acb, bool push, const char *name,
                      std::uint32_t length, std::uint32_t color);
std::uint32_t *pop_marker(CommandBuffer *cb, int is_acb);
std::uint32_t *set_flip(CommandBuffer *cb, int is_acb, std::uint32_t arg0, std::uint32_t arg1,
                        std::uint32_t arg2, std::uint64_t arg3);
std::uint32_t *wait_until_safe(CommandBuffer *cb, int is_acb, std::uint32_t arg0,
                               std::uint32_t arg1);
std::uint32_t *workloads_active(CommandBuffer *cb, int is_acb, std::uint32_t arg0,
                                std::uint64_t arg1, std::uint32_t arg2);
std::uint32_t *workload_complete(CommandBuffer *cb, int is_acb, std::uint32_t arg0,
                                 std::uint32_t arg1);
std::uint32_t *workload_stream_inactive(CommandBuffer *cb, int is_acb, std::uint32_t arg0);
std::uint32_t *wait_reg_mem(CommandBuffer *cb, int is_acb, std::int32_t size,
                            std::uint32_t control32, std::uint32_t control64,
                            std::uint64_t address, std::uint64_t reference, std::uint64_t mask,
                            std::uint32_t poll_cycles);
std::uint32_t *mem_semaphore(CommandBuffer *cb, int begin_is_acb, int end_is_acb,
                             std::uint64_t address, std::uint8_t use_mailbox,
                             std::uint8_t signal_type, std::int32_t sem_sel);
std::uint32_t *write_data(CommandBuffer *cb, std::uint32_t control, std::uint32_t address_lo,
                          std::uint32_t address_hi, const std::uint32_t *data,
                          std::uint32_t num_dwords);
std::uint32_t atomic_gds_control(std::uint32_t op_flags, std::int32_t mode, bool op8);
std::uint32_t *atomic_gds(CommandBuffer *cb, std::uint32_t control, std::uint32_t flag40,
                          std::uint32_t field32, std::uint32_t gds_offset, std::uint16_t gds_size,
                          std::uint32_t field5, std::uint32_t field6, std::uint64_t data0,
                          std::uint64_t data1);

// Suspend helpers (agc_system.cpp).
std::uint32_t get_suspend_flags();
std::uint32_t suspend_mode(std::uint32_t flags);

// Register descriptors (agc_shader.cpp): resolved by init; the table maps the original image's
// descriptor address to our storage.
struct Descriptors {
    RegPair compute_pgm[2]; // 0x45c90
    RegPair ps_pgm[2];      // 0x45ce0
    RegPair es_pgm[2];      // 0x45ca0
    RegPair ls_pgm[2];      // 0x45cd0
    RegPair gs_pgm[2];      // 0x45cb0
    RegPair hs_pgm[2];      // 0x45cc0
    RegPair gs_rsrc1;       // 0x459d8
    RegPair gs_rsrc2;       // 0x459f0
    RegPair hs_rsrc1;       // 0x459e0
    RegPair hs_rsrc2;       // 0x459f8
    RegPair hs_duplicated;  // 0x45f28
    RegPair ps_input_cntl0; // 0x45db8
    RegPair stages_enable;  // 0x45a68
    RegPair gs_out_prim;    // 0x45a30
    RegPair prim_uc0;       // 0x458c8
    RegPair prim_uc1;       // 0x458f0
    RegPair prim_type;      // 0x45a58
    RegPair gs_over_e;      // 0x458d8
    RegPair gs_over_a;      // 0x45f58
    RegPair gs_over_b;      // 0x45f00
    RegPair gs_over_c;      // 0x45f48
    RegPair gs_over_d;      // 0x45f10
    RegPair gs_over_out0;   // 0x45f08
    RegPair gs_over_out1;   // 0x45f30
};
Descriptors &descriptors();
void reset_descriptors();
std::int32_t resolve_descriptors(std::uint32_t sdk_version);
RegPair *descriptor_by_vaddr(std::uint64_t vaddr);

// Internal shaders (agc_shader.cpp), created once by init.
std::int32_t create_internal_shaders();

// Register-default selection (agc_system.cpp).
void reset_defaults_cache();

// Primitive-type class table lookup (firmware data at 0x23f1c).
std::uint32_t prim_class(std::uint32_t prim_type);

} // namespace bc5::reimpl::agc::detail
