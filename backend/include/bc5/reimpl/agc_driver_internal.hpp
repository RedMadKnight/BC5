// SPDX-License-Identifier: GPL-2.0-only
// libSceAgcDriver re-creation: module-internal state, import slots and helpers shared by the
// agc_driver*.cpp files. Not part of the guest ABI. Behaviour per the original module's behaviour
// (clean-room description, see src/reimpl/PROVENANCE.md).
#pragma once

#include "bc5/reimpl/agc_driver.hpp"

#include <atomic>
#include <cstdint>
#include <cstring>

namespace bc5::reimpl::agc_driver::detail {

inline constexpr const char *kModule = "libSceAgcDriver";

// ---------------------------------------------------------------------------------------------
// Imports. Every call the module makes into libkernel / libSceVideoOut goes through one of these
// slots; the host fills them from imports(). A null slot behaves like the import failing.
struct Imports {
    // libkernel
    int (*open)(const char *path, int flags, ...) = nullptr;
    int (*close)(int fd) = nullptr;
    int (*ioctl)(int fd, std::uint64_t request, void *arg) = nullptr;
    void *(*mmap)(void *addr, std::uint64_t len, int prot, int flags, int fd,
                  std::int64_t offset) = nullptr;
    int (*getpid)() = nullptr;
    int *(*error_location)() = nullptr; // __error
    int (*kevent)(void *eq, const void *changes, int nchanges, void *events, int nevents,
                  const void *timeout) = nullptr;
    int (*kernel_error)(int err) = nullptr; // sceKernelError
    std::uint64_t (*get_event_data)(const void *ev) = nullptr;
    std::uint64_t (*get_direct_memory_size)() = nullptr;
    int (*allocate_direct_memory)(std::int64_t search_start, std::int64_t search_end,
                                  std::uint64_t len, std::uint64_t align, int memory_type,
                                  std::int64_t *phys_out) = nullptr;
    int (*map_named_direct_memory)(void **addr, std::uint64_t len, int prot, int flags,
                                   std::int64_t phys, std::uint64_t align,
                                   const char *name) = nullptr;
    int (*map_named_system_flexible_memory)(void **addr, std::uint64_t len, int prot, int flags,
                                            const char *name) = nullptr;
    int (*set_virtual_range_name)(void *addr, std::uint64_t len, const char *name) = nullptr;
    int (*set_process_property)(const char *name, std::uint64_t addr, std::uint64_t size,
                                std::uint64_t addr2, std::uint64_t size2) = nullptr;
    int (*debug_raise_exception)(std::uint32_t code, std::uint64_t arg) = nullptr;
    int (*get_compiled_sdk_version)(std::uint32_t *out) = nullptr;
    std::uint64_t (*get_process_time_counter)() = nullptr;
    int (*configured_flexible_memory_size)(std::uint64_t *out) = nullptr;
    int (*get_page_table_stats)(int *a, int *b, int *c, int *d) = nullptr;
    std::uint32_t (*get_main_soc_id)() = nullptr;
    int (*get_app_info)(int pid, void *out) = nullptr;
    int (*mutex_init)(ScePthreadMutex *mutex, const void *attr, const char *name) = nullptr;
    int (*mutex_lock)(ScePthreadMutex *mutex) = nullptr;
    int (*mutex_unlock)(ScePthreadMutex *mutex) = nullptr;
    int (*mutex_destroy)(ScePthreadMutex *mutex) = nullptr;
    int (*hook_module_query)() = nullptr;    // NID LzoM-wVLJDE, meaning unknown
    int (*system_info_query)(void *out) = nullptr; // NID aj7wRdAWFeM, meaning unknown
    // libSceVideoOut
    int (*video_out_submit_eop_flip)(int handle, int buffer_index, std::uint32_t flip_mode,
                                     std::int64_t flip_arg, std::uint64_t *eop_info) = nullptr;
    int (*video_out_get_buffer_label_address)(int handle, std::uint64_t *labels) = nullptr;
    std::uint32_t (*video_out_sys_get_bus)(int handle) = nullptr;
};
extern Imports g_imports;

// ---------------------------------------------------------------------------------------------
// Module state. All zero at load except where noted.

// The "UMD memory info": the system-flexible-memory areas mapped at init (23 u64).
struct UmdMemoryInfo {
    std::uint64_t valid;
    std::uint64_t trap_code, trap_code_size;
    std::uint64_t trap_data, trap_data_size;
    std::uint64_t wfdebug, wfdebug_size;
    std::uint64_t ddid, ddid_size;
    std::uint64_t eop_fifo, eop_fifo_size;
    std::uint64_t gpu_info, gpu_info_size;
    std::uint64_t shadow_info, shadow_info_size;
    std::uint64_t cwsr, cwsr_size;
    std::uint64_t gpr_dump, gpr_dump_size;
    std::uint64_t misc, misc_size;
    std::uint64_t acqrb, acqrb_size;
};
static_assert(sizeof(UmdMemoryInfo) == 0xB8);

struct DefaultStateCb {
    std::uint64_t address;
    std::uint32_t size_dw;
    std::uint8_t policy;
};

struct TrapDescriptor {
    const std::uint8_t *code_start;
    const std::uint8_t *code_end;
    const std::uint8_t *data_start;
    const std::uint8_t *data_end;
    std::uint64_t extra;
};

struct RegionEntry {
    std::uint32_t offset;
    std::uint32_t size;
};

inline constexpr std::uint32_t kGameQueues = 56;
inline constexpr std::uint32_t kSysQueues = 8;

struct State {
    // process / device
    std::uint32_t sdk_version = 0;
    int gc_fd = -1;
    std::uint32_t client_type = 0;
    std::uint32_t client_flags = 0;
    std::uint64_t doorbell_page = 0;
    std::uint32_t gc_closed_for_reset = 0;
    std::uint64_t gfx_ring0_submits = 0;
    std::uint64_t gfx_other_submits = 0;
    std::uint32_t gfx_ib_total = 0;
    std::uint32_t gfx_last_result = 0;
    std::uint32_t gfx_reset_count = 0;
    std::uint64_t suspend_status = 0;
    std::uint64_t tsc_at_event = 0;
    std::uint64_t ptc_at_event = 0;
    // submission mode
    std::uint32_t submit_mode = 0;
    std::uint32_t agr_enabled = 0;
    std::uint32_t agr_used = 0;
    std::uint32_t prologue_sent[2] = {0, 0};
    SubmitPair pending_suspend[2] = {};
    // direct memory
    std::uint64_t dmem_base = 0;
    std::int64_t dmem_phys = 0;
    std::uint64_t dmem_size = 0;
    const RegionEntry *region_table = nullptr;
    // register shadow and default-state CBs
    RegShadowInfo shadow_gfx = {};
    RegShadowInfo shadow_agr = {};
    DefaultStateCb defstate_gfx = {};
    DefaultStateCb defstate_agr = {};
    std::uint64_t label_gfx = 0;
    std::uint64_t label_agr = 0;
    // queues
    QueueHandle gfx_main = {};
    QueueHandle gfx_agr = {};
    ComputeQueueEntry compute_game[kGameQueues] = {};
    ComputeQueueEntry compute_sys[kSysQueues] = {};
    ComputeQueueEntry *active_table = nullptr;
    // hook modules
    std::uint32_t hook_count = 0;
    std::uint32_t hook_optional_count = 0;
    // system flexible memory
    UmdMemoryInfo umd = {};
    std::uint64_t gpu_info = 0;
    std::uint64_t regshadow_copy = 0;
    std::uint64_t regshadow_copy_size = 0;
    std::uint64_t ddid_base = 0;
    std::uint64_t cwsr_base = 0;
    std::uint32_t last_wptr[256] = {};
    // workloads
    std::uint64_t workload_status = 0;
    ScePthreadMutex workload_mutex = nullptr;
    std::uint32_t workload_mask = 0;
    char workload_names[32][32] = {};
    // reset-mode stubs
    std::uint32_t reset_allowed_mask = 0;
    std::uint32_t reset_mode = 0;
    // trap handler descriptors
    TrapDescriptor trap_present = {};
    TrapDescriptor trap_absent = {};
};
extern State g_state;
extern std::atomic<std::uint64_t> g_submit_seq;

// ---------------------------------------------------------------------------------------------
// Helpers shared between the source files.

template <class T> inline T *at(std::uint64_t address) {
    return reinterpret_cast<T *>(static_cast<std::uintptr_t>(address));
}
inline std::uint64_t addr_of(const void *p) {
    return static_cast<std::uint64_t>(reinterpret_cast<std::uintptr_t>(p));
}
inline std::uint32_t lo32(std::uint64_t v) { return static_cast<std::uint32_t>(v); }
inline std::uint32_t hi32(std::uint64_t v) { return static_cast<std::uint32_t>(v >> 32); }
inline std::uint32_t hi16(std::uint64_t v) { return static_cast<std::uint32_t>(v >> 32) & 0xFFFFu; }
inline void put_u32(std::uint64_t address, std::uint32_t v) {
    std::memcpy(at<void>(address), &v, 4);
}
inline void put_u64(std::uint64_t address, std::uint64_t v) {
    std::memcpy(at<void>(address), &v, 8);
}

// ioctl on /dev/gc; a missing import counts as a failed call (-1).
int gc_ioctl(std::uint64_t request, void *arg);

// Region table (driver direct memory), sub-blocks of its first 0x8000 bytes, small blocks.
std::uint64_t region_addr(std::uint32_t index);
std::uint64_t region_size(std::uint32_t index);
std::int32_t subblock(std::uint32_t index, std::uint64_t *addr_out, std::uint64_t *size_out);

// PM4 helpers.
std::uint32_t write_user_data(std::uint32_t *dst, std::int32_t pipe_flag, std::uint32_t header_word,
                              const void *payload, std::uint32_t payload_bytes);
std::uint32_t user_data_size(std::uint32_t payload_bytes);
void write_shadow_restore_cb(std::uint32_t *dst, std::uint64_t shadow_base, bool enabled);

// Queues and submission.
std::int32_t create_queue(std::uint32_t queue_id, QueueHandle **handle_out, const void *config,
                          char force);
std::int32_t submit_single_impl(QueueHandle *handle, const SubmitPair *pair);
std::int32_t submit_multi_impl(QueueHandle *handle, const SubmitPair *pairs, std::uint32_t count);
bool get_umd_memory_info(UmdMemoryInfo *out);
ComputeQueueEntry *compute_entry_for_id(std::uint32_t queue_id);
std::int32_t mutex_lock(QueueHandle *handle);
std::int32_t mutex_unlock(QueueHandle *handle);
void mutex_init_if_needed(QueueHandle *handle);
std::uint64_t read_tsc();
void record_event_time();
bool gc_reopen();

// Logging with the module's tag.
#if defined(__GNUC__) || defined(__clang__)
#define BC5_AGCDRV_PRINTF __attribute__((format(printf, 1, 2)))
#else
#define BC5_AGCDRV_PRINTF
#endif
void drv_log(const char *fmt, ...) BC5_AGCDRV_PRINTF;

} // namespace bc5::reimpl::agc_driver::detail
