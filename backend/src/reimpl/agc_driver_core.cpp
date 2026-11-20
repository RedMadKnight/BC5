// SPDX-License-Identifier: GPL-2.0-only
// libSceAgcDriver re-creation: module state, imports, memory layout helpers and the load-time
// initialisation (open /dev/gc, map the doorbell and the system areas, install the trap handler,
// allocate the driver's direct memory, create the queues).
//
// Everything here follows the original module's behaviour (clean-room description, see
// src/reimpl/PROVENANCE.md); names are ours.
#include "bc5/reimpl/agc_driver_internal.hpp"
#include "bc5/reimpl/agc_driver_tables.hpp"
#include "bc5/reimpl/data_source.hpp"

#include <cstdarg>
#include <cstdio>
#include <cstring>

#if defined(_MSC_VER) && (defined(_M_X64) || defined(_M_IX86))
#include <intrin.h>
#endif

namespace bc5::reimpl::agc_driver {
namespace detail {

Imports g_imports;
State g_state;
std::atomic<std::uint64_t> g_submit_seq{0};

void drv_log(const char *fmt, ...) {
    char buf[512];
    va_list ap;
    va_start(ap, fmt);
    std::vsnprintf(buf, sizeof buf, fmt, ap);
    va_end(ap);
    bc5::reimpl::log(kModule, "%s", buf);
}

std::uint64_t read_tsc() {
#if defined(_MSC_VER) && (defined(_M_X64) || defined(_M_IX86))
    return __rdtsc();
#elif (defined(__GNUC__) || defined(__clang__)) && (defined(__x86_64__) || defined(__i386__))
    return __builtin_ia32_rdtsc();
#else
    return 0;
#endif
}

int gc_ioctl(std::uint64_t request, void *arg) {
    if (g_imports.ioctl == nullptr) {
        return -1;
    }
    return g_imports.ioctl(g_state.gc_fd, request, arg);
}

// ---------------------------------------------------------------------------------------------
// Direct-memory layout. INTEROP TABLEs spelled out by the description: {offset, size} per region,
// for a game and for a compositor process.
namespace {
constexpr RegionEntry kRegionsGame[7] = {
    {0x8000, 0x19000},  // graphics register shadow
    {0x21000, 0x19000}, // Agr register shadow
    {0x3A000, 0x200},   // workload status array
    {0x3A200, 0x200},   // "empty IB"
    {0x3A400, 0x5C00},  // unused
    {0x40000, 0x1B0000}, // reserved for libSceAgc
    {0x1E0000, 0x10000}, // unused
};
constexpr RegionEntry kRegionsCompositor[7] = {
    {0x8000, 0}, {0x8000, 0}, {0x8000, 0x200}, {0x8200, 0x200}, {0x8400, 0x7C00}, {0x10000, 0},
    {0, 0},
};
// Sub-blocks of the first 0x8000 bytes (same for both process kinds): default-state CBs (gfx,
// Agr), shadow-restore CBs enabled (gfx, Agr), disabled (gfx, Agr), unused.
constexpr RegionEntry kSubblocks[7] = {
    {0x0, 0x400}, {0x400, 0x400}, {0x800, 0x80}, {0x880, 0x80},
    {0x900, 0x80}, {0x980, 0x80}, {0xA00, 0x600},
};
// Small blocks; only entry 2 (the 16 bytes that receive the init-tail ioctl's output) is used.
constexpr RegionEntry kSmallBlocks[3] = {{0, 0x1000}, {0x1000, 0x6FF0}, {0x7FF0, 0x10}};

constexpr std::uint64_t kNoSize = ~std::uint64_t{0};
} // namespace

std::uint64_t region_addr(std::uint32_t index) {
    if (g_state.region_table == nullptr || index >= 7) {
        return 0;
    }
    return g_state.dmem_base + g_state.region_table[index].offset;
}

std::uint64_t region_size(std::uint32_t index) {
    if (g_state.region_table == nullptr || index >= 7) {
        return kNoSize;
    }
    return g_state.region_table[index].size;
}

std::int32_t subblock(std::uint32_t index, std::uint64_t *addr_out, std::uint64_t *size_out) {
    if (index >= 7) {
        return kErrInvalid;
    }
    if (addr_out != nullptr) {
        *addr_out = g_state.dmem_base + kSubblocks[index].offset;
    }
    if (size_out != nullptr) {
        *size_out = kSubblocks[index].size;
    }
    return kOk;
}

namespace {

std::uint64_t small_block_addr(std::uint32_t index) {
    return index >= 3 ? 0 : g_state.dmem_base + kSmallBlocks[index].offset;
}

// ---------------------------------------------------------------------------------------------
// GPU info area ("SceGnmGpuInfo") header: diagnostic logs for external tools.
void write_gpu_info_header(bool first_open) {
    const std::uint64_t g = g_state.gpu_info;
    if (g == 0) {
        return;
    }
    put_u32(g + 0x0, 0);
    put_u32(g + 0xB6440, 0xE10);
    put_u32(g + 0xB6444, 0);    // compute-log write index
    put_u32(g + 0xB6448, 0);    // compute-log count
    put_u32(g + 0xB644C, 0x40); // compute-log capacity
    std::memset(at<void>(g + 0xB6C50), 0, 0xB7250 - 0xB6C50);
    if (!first_open) {
        return;
    }
    put_u32(g + 0xB72E8, 0x8010);
    put_u32(g + 0xB72EC, 0x400); // ring-0 log capacity
    put_u32(g + 0xB72F0, 0);     // ring-0 log index
    std::memset(at<void>(g + 0xB72F4), 0, 0xBF2F8 - 0xB72F4);
    put_u32(g + 0xBF2F8, 0x4010);
    put_u32(g + 0xBF2FC, 0x200); // other-ring log capacity
    put_u32(g + 0xBF300, 0);     // other-ring log index
    std::memset(at<void>(g + 0xBF304), 0, 0x4004);
}

void set_process_property(const char *name, std::uint64_t a, std::uint64_t b, std::uint64_t c,
                          std::uint64_t d) {
    if (g_imports.set_process_property != nullptr) {
        g_imports.set_process_property(name, a, b, c, d);
    }
}

void set_range_name(std::uint64_t address, std::uint64_t size, const char *name) {
    if (g_imports.set_virtual_range_name != nullptr) {
        g_imports.set_virtual_range_name(at<void>(address), size, name);
    }
}

// ---------------------------------------------------------------------------------------------
// System flexible memory areas, mapped once in a game process.
struct AreaSpec {
    const char *name;
    std::uint64_t hint;
    std::uint64_t size;
    int prot;
    std::uint64_t UmdMemoryInfo::*address;
    std::uint64_t UmdMemoryInfo::*size_field;
};

bool allocate_system_areas() {
    UmdMemoryInfo &u = g_state.umd;
    if (u.valid != 0) {
        return true;
    }
    // The "special kit" query is a constant 0 in this module, so the smaller sizes apply.
    static const AreaSpec kAreas[] = {
        {"SceGnmGpuInfo", 0xFE0300000u, 0x100000, 0x3, &UmdMemoryInfo::gpu_info,
         &UmdMemoryInfo::gpu_info_size},
        {"SceGnmTrapCode", 0xF00000000u, 0x4000, 0x33, &UmdMemoryInfo::trap_code,
         &UmdMemoryInfo::trap_code_size},
        {"SceGnmTrapData", 0xF00000000u, 0x4000, 0x33, &UmdMemoryInfo::trap_data,
         &UmdMemoryInfo::trap_data_size},
        {"SceGnmDdid", 0xF00000000u, 0xFC000, 0x33, &UmdMemoryInfo::ddid,
         &UmdMemoryInfo::ddid_size},
        {"SceGnmEopFifo", 0xF00000000u, 0x3C000, 0x33, &UmdMemoryInfo::eop_fifo,
         &UmdMemoryInfo::eop_fifo_size},
        {"SceGnmShadowRegInfo", 0xF00000000u, 0x4000, 0x33, &UmdMemoryInfo::shadow_info,
         &UmdMemoryInfo::shadow_info_size},
        {"SceGnmCwsr", 0xF00000000u, 0x1000000, 0x33, &UmdMemoryInfo::cwsr,
         &UmdMemoryInfo::cwsr_size},
        {"SceGnmMisc", 0xF00000000u, 0x4000, 0x33, &UmdMemoryInfo::misc,
         &UmdMemoryInfo::misc_size},
        {"SceGnmACQRB", 0xF00000000u, 0x1E0000, 0x33, &UmdMemoryInfo::acqrb,
         &UmdMemoryInfo::acqrb_size},
    };
    for (const AreaSpec &a : kAreas) {
        void *p = at<void>(a.hint);
        const int rc = g_imports.map_named_system_flexible_memory == nullptr
                           ? -1
                           : g_imports.map_named_system_flexible_memory(&p, a.size, a.prot, 0,
                                                                        a.name);
        if (rc != 0) {
            drv_log("cannot allocate the %s area (%d)", a.name, rc);
            return false;
        }
        u.*a.address = addr_of(p);
        u.*a.size_field = a.size;
        if (a.address == &UmdMemoryInfo::gpu_info) {
            g_state.gpu_info = addr_of(p);
        } else if (a.address == &UmdMemoryInfo::ddid) {
            std::memset(p, 0, a.size);
            g_state.ddid_base = addr_of(p);
        } else if (a.address == &UmdMemoryInfo::cwsr) {
            g_state.cwsr_base = addr_of(p);
        }
    }
    // The wavefront-debug area lives at a fixed address and is not mapped here; the GPR dump area
    // starts at the CWSR area, and the register-shadow copy right after the GPR dump.
    u.wfdebug = 0xC80008000u;
    u.wfdebug_size = 0x40000;
    u.gpr_dump = u.cwsr;
    u.gpr_dump_size = 0xA00000;
    g_state.regshadow_copy = u.cwsr + u.gpr_dump_size;
    // TODO(verify): the description does not give the copy's size; we use the shadow span.
    g_state.regshadow_copy_size = 2 * 0x19000;
    u.valid = 1;
    return true;
}

std::uint64_t round_up_256(std::uint64_t v) { return (v + 0xFF) & ~std::uint64_t{0xFF}; }

// Installs the GPU trap handler: copies the handler code into the TrapCode area and hands the
// kernel the debug resources (ioctl 0x80888123). Failures only print.
void install_trap_handler() {
    std::uint8_t app_info[0x400] = {};
    std::uint32_t app_mode = 0;
    if (g_imports.get_app_info != nullptr) {
        const int pid = g_imports.getpid != nullptr ? g_imports.getpid() : 0;
        if (g_imports.get_app_info(pid, app_info) == 0) {
            app_mode = app_info[0x48];
        }
    }
    if (app_mode >= 4) {
        drv_log("no trap handler for mode %u", app_mode);
        return;
    }
    // Mode table: {present, absent, absent, present}.
    const TrapDescriptor &d =
        (app_mode == 0 || app_mode == 3) ? g_state.trap_present : g_state.trap_absent;
    if (d.code_start == nullptr || d.code_end <= d.code_start) {
        drv_log("failed to get the trap handler code");
        return;
    }
    const UmdMemoryInfo &u = g_state.umd;
    const auto code_bytes = static_cast<std::uint64_t>(d.code_end - d.code_start);
    const std::uint64_t data_bytes =
        (d.data_start != nullptr && d.data_end > d.data_start)
            ? static_cast<std::uint64_t>(d.data_end - d.data_start)
            : 0;
    const std::uint64_t code_size = round_up_256(code_bytes);
    const std::uint64_t data_size = round_up_256(data_bytes);
    if (code_size + data_size > u.trap_code_size) {
        drv_log("no space for the trap handler code and data");
        return;
    }
    std::memcpy(at<void>(u.trap_code), d.code_start, code_bytes);
    std::uint64_t data_copy = 0;
    if (data_bytes != 0) {
        data_copy = u.trap_code + code_size;
        std::memcpy(at<void>(data_copy), d.data_start, data_bytes);
    }
    if (u.wfdebug_size < 0x3CA00) {
        drv_log("wavefront debug data buffer too small");
        return;
    }
    put_u64(u.trap_data + 0x00, u.cwsr);
    put_u64(u.trap_data + 0x08, u.cwsr);
    put_u64(u.trap_data + 0x10, u.wfdebug);

    TrapHandlerArgs args{};
    args.code_address = u.trap_code;
    args.code_size = code_size;
    args.data_address = u.trap_data;
    args.data_size = u.trap_data_size;
    args.cwsr_address = u.cwsr;
    args.cwsr_size = u.cwsr_size;
    args.wfdebug_address = u.wfdebug;
    args.wfdebug_size = 0x3BB00;
    args.ddid_address = u.ddid;
    args.ddid_size = u.ddid_size;
    args.handler_data_address = data_copy;
    args.handler_data_size = data_bytes != 0 ? data_size : 0;
    args.wfdebug_handler_data_address = data_bytes != 0 ? u.wfdebug + 0x3BB00 : 0;
    args.wfdebug_handler_data_size = data_bytes != 0 ? 0x200 : 0;
    args.wfdebug_tail_address = u.wfdebug + 0x3BD00;
    args.wfdebug_tail_size = 0xD00;
    args.extra = static_cast<std::uint32_t>(d.extra);
    args.zero = 0;
    if (gc_ioctl(kIoctlSetTrapHandler, &args) != 0) {
        drv_log("cannot set the trap handler resources");
    }
}

constexpr std::uint32_t kGcFailed = 0xFFFFFFFFu;

// Opens /dev/gc and sets up what the client kind needs. Returns the client-info word, or
// kGcFailed.
std::uint32_t gc_open_first() {
    const int fd = g_imports.open != nullptr ? g_imports.open("/dev/gc", 2) : -1;
    if (fd < 0) {
        drv_log("cannot initialise the GPU (%i)", fd);
        return kGcFailed;
    }
    g_state.gc_fd = fd;
    std::uint32_t info = 0;
    (void)gc_ioctl(kIoctlClientInfo, &info);
    if ((info & 0xFFFFu) == 0) {
        if (g_state.doorbell_page == 0 || g_state.doorbell_page == ~std::uint64_t{0}) {
            void *p = g_imports.mmap == nullptr
                          ? reinterpret_cast<void *>(~std::uintptr_t{0})
                          : g_imports.mmap(at<void>(0xFE0200000u), 0x4000, 0x22, 1, fd, 0);
            if (p == nullptr || p == reinterpret_cast<void *>(~std::uintptr_t{0})) {
                if (g_imports.close != nullptr) {
                    g_imports.close(fd);
                }
                drv_log("cannot initialise the GPU (doorbell mapping failed)");
                return kGcFailed;
            }
            g_state.doorbell_page = addr_of(p);
            set_range_name(g_state.doorbell_page, 0x4000, "SceGnmDingDong");
        }
        std::uint32_t sdk = 0x3000000; // queried, unused
        if (g_imports.get_compiled_sdk_version != nullptr) {
            (void)g_imports.get_compiled_sdk_version(&sdk);
        }
        if (allocate_system_areas()) {
            install_trap_handler();
        }
    }
    if (g_state.gpu_info != 0) {
        write_gpu_info_header(true);
        set_process_property("Sce.Debug:Gnm", g_state.gpu_info, g_state.umd.gpu_info_size, 0, 0);
        set_range_name(g_state.gpu_info, g_state.umd.gpu_info_size, "SceGnmDumpArea");
    }
    return info;
}

// Allocates and maps the driver's own direct memory ("SceAgcDriver").
std::int32_t allocate_driver_dmem() {
    std::uint64_t size = 0;
    const RegionEntry *table = nullptr;
    if (g_state.client_type == 0) {
        size = 0x200000;
        table = kRegionsGame;
    } else if (g_state.client_type == 1) {
        size = 0x10000;
        table = kRegionsCompositor;
    } else {
        return kOk;
    }
    if (g_imports.allocate_direct_memory == nullptr || g_imports.map_named_direct_memory == nullptr) {
        return kErrProcessOrMemory;
    }
    const std::uint64_t total =
        g_imports.get_direct_memory_size != nullptr ? g_imports.get_direct_memory_size() : 0;
    std::int64_t phys = 0;
    if (g_imports.allocate_direct_memory(0, static_cast<std::int64_t>(total), size, size, 0xC,
                                         &phys) != 0) {
        return kErrProcessOrMemory;
    }
    int prot = 0x33;
    if ((g_state.client_flags & 1u) != 0) {
        prot = 0x13;
        drv_log("ESVM process: driver memory is mapped without GPU write");
    }
    void *p = at<void>(0xFE0000000u);
    if (g_imports.map_named_direct_memory(&p, size, prot, 0, phys, size, "SceAgcDriver") != 0) {
        return kErrProcessOrMemory;
    }
    std::memset(p, 0, size);
    g_state.dmem_base = addr_of(p);
    g_state.dmem_phys = phys;
    g_state.dmem_size = size;
    g_state.region_table = table;
    return kOk;
}

void fill_shadow_info(RegShadowInfo &info, std::uint32_t region) {
    info.base = region_addr(region);
    info.size = static_cast<std::uint32_t>(region_size(region));
    info.ctx_first = 0;
    info.ctx_last = 0x3BF;
    info.sh_first = 0x2000;
    info.sh_last = 0x2281;
    info.uc_first = 0x2400;
    info.uc_last = 0x2843;
    info.zero = 0;
}

void register_debug_properties(bool game) {
    const UmdMemoryInfo &u = g_state.umd;
    const std::uint64_t span = 2 * 0x19000;
    if (game) {
        set_process_property("Sce.Debug:Gn2", u.ddid, u.ddid_size, g_state.regshadow_copy, span);
        set_process_property("Sce.Debug:Gn3", u.gpr_dump, u.gpr_dump_size, 0, 0);
        set_process_property("Sce.Debug:Gn4", g_state.shadow_gfx.base, span, u.shadow_info, 0x4000);
        set_range_name(g_state.shadow_gfx.base, span, "SceAgcRegShadow");
        set_range_name(u.gpr_dump, u.gpr_dump_size, "SceAgcGprDumpArea");
        set_range_name(g_state.regshadow_copy, g_state.regshadow_copy_size, "SceAgcRegShadowCopy");
        set_range_name(u.shadow_info, u.shadow_info_size, "SceAgcRegShadowInfo");
        set_range_name(u.ddid, u.ddid_size, "SceAgcDdid");
        if (u.shadow_info != 0) {
            std::memcpy(at<void>(u.shadow_info), &g_state.shadow_gfx, sizeof(RegShadowInfo));
            std::memcpy(at<void>(u.shadow_info + sizeof(RegShadowInfo)), &g_state.shadow_agr,
                        sizeof(RegShadowInfo));
        }
    } else {
        set_process_property("Sce.Debug:Gn2", u.ddid, u.ddid_size, 0, 0);
        set_range_name(u.ddid, u.ddid_size, "SceAgcDdid");
    }
}

std::int32_t register_hook_modules() {
    if (g_state.hook_count != 0) {
        drv_log("submission modules already loaded");
        return kErrHooksLoaded;
    }
    // The optional module's only callback is a no-op pre-submit hook, so registering it changes
    // nothing observable beyond the counters; the default module is hard-wired.
    if (g_imports.hook_module_query != nullptr && g_imports.hook_module_query() != 0) {
        ++g_state.hook_optional_count;
        ++g_state.hook_count;
    }
    ++g_state.hook_count;
    return kOk;
}

std::int32_t workload_init() {
    const std::uint64_t a = region_addr(2);
    if (region_size(2) < 0x100 || (a & 0xF) != 0) {
        drv_log("workload tracking init failed");
        return kErrNullCommandBuffer;
    }
    g_state.workload_status = a;
    g_state.workload_mask = 1u;
    std::memset(g_state.workload_names[0], 0, 32);
    std::memcpy(g_state.workload_names[0], "System", 7);
    if (g_imports.mutex_init != nullptr) {
        g_imports.mutex_init(&g_state.workload_mutex, nullptr, "SceAgcDriverWorkloads");
    }
    return kOk;
}

// The "present" trap-handler descriptor: our own minimal handler (agc_driver_tables.cpp, one
// s_endpgm), or with BC5_REIMPL_FW_DATA the original's 0x2400-byte handler from the maintainer's
// own module file. Either way install_trap_handler() sends the original's ioctl (0x80888123)
// with it; BC5's host only traces that ioctl and never runs the handler on the GPU.
// FW_COMPARE does not compare the two: they differ by design.
void load_trap_descriptor() {
    g_state.trap_present = {};
    g_state.trap_absent = {};
    const std::uint8_t *code = nullptr;
    std::uint64_t size = 0;
    if (FirmwareData *fw = bc5::reimpl::firmware_data_for_use(); fw != nullptr) {
        code = fw->get(kModule, tables::kTrapHandlerImageAddress, tables::kTrapHandlerImageSize);
        size = tables::kTrapHandlerImageSize;
    }
    if (code == nullptr) {
        const std::span<const std::uint8_t> own = tables::trap_handler_code();
        code = own.data();
        size = own.size();
    }
    g_state.trap_present.code_start = code;
    g_state.trap_present.code_end = code + size;
}

} // namespace

void record_event_time() {
    g_state.tsc_at_event = read_tsc() >> 4;
    g_state.ptc_at_event = g_imports.get_process_time_counter != nullptr
                               ? g_imports.get_process_time_counter() >> 4
                               : 0;
}

bool get_umd_memory_info(UmdMemoryInfo *out) {
    if (g_state.umd.valid == 0) {
        return false;
    }
    *out = g_state.umd;
    return true;
}

// Re-open after a compositor closed /dev/gc for a GPU reset.
bool gc_reopen() {
    const int fd = g_imports.open != nullptr ? g_imports.open("/dev/gc", 2) : -1;
    if (fd < 0) {
        return false;
    }
    g_state.gc_fd = fd;
    std::uint32_t info = 0;
    (void)gc_ioctl(kIoctlClientInfo, &info);
    if (g_state.gpu_info != 0) {
        write_gpu_info_header(false);
        set_process_property("Sce.Debug:Gnm", g_state.gpu_info, g_state.umd.gpu_info_size, 0, 0);
        set_range_name(g_state.gpu_info, g_state.umd.gpu_info_size, "SceGnmDumpArea");
    }
    set_process_property("Sce.Debug:Gn2", g_state.umd.ddid, g_state.umd.ddid_size, 0, 0);
    set_range_name(g_state.umd.ddid, g_state.umd.ddid_size, "SceAgcDdid");
    return true;
}

} // namespace detail

using namespace detail;

std::int32_t initialize() {
    // 1-2: pending suspend pairs, trap handler descriptor.
    g_state.pending_suspend[0] = {};
    g_state.pending_suspend[1] = {};
    load_trap_descriptor();
    // 3-4: the device.
    const std::uint32_t info = gc_open_first();
    if (info == kGcFailed) {
        return kErrGeneric;
    }
    g_state.client_type = info & 0xFFFFu;
    g_state.client_flags = info >> 16;
    // 5: SDK version.
    if (g_imports.get_compiled_sdk_version == nullptr ||
        g_imports.get_compiled_sdk_version(&g_state.sdk_version) != 0) {
        g_state.sdk_version = 0;
    }
    // 6-7: hook modules, driver memory (errors only printed).
    if (register_hook_modules() != kOk) {
        drv_log("internal components init failed");
    }
    if (allocate_driver_dmem() != kOk) {
        drv_log("internal memory init failed");
    }
    // 8: per client kind.
    if (g_state.client_type == 0) {
        fill_shadow_info(g_state.shadow_gfx, 0);
        fill_shadow_info(g_state.shadow_agr, 1);
        if (g_state.dmem_base != 0) { // deviation: UB in the original when the allocation failed
            const std::uint64_t empty_ib = region_addr(3);
            put_u32(empty_ib, 0xC0001000u); // NOP covering the 2-dword buffer
            put_u32(empty_ib + 4, 0);
            std::uint64_t sb = 0;
            (void)subblock(2, &sb, nullptr);
            write_shadow_restore_cb(at<std::uint32_t>(sb), g_state.shadow_gfx.base, true);
            (void)subblock(4, &sb, nullptr);
            write_shadow_restore_cb(at<std::uint32_t>(sb), g_state.shadow_gfx.base, false);
            (void)subblock(3, &sb, nullptr);
            write_shadow_restore_cb(at<std::uint32_t>(sb), g_state.shadow_agr.base, true);
            (void)subblock(5, &sb, nullptr);
            write_shadow_restore_cb(at<std::uint32_t>(sb), g_state.shadow_agr.base, false);
        }
        QueueHandle *h = nullptr;
        (void)create_queue(0, &h, nullptr, 0);
        (void)create_queue(4, &h, nullptr, 0);
        g_state.gfx_ring0_submits = 0;
        g_state.gfx_other_submits = 0;
        g_state.active_table = g_state.compute_game;
        std::memset(static_cast<void *>(g_state.compute_game), 0, sizeof g_state.compute_game);
        for (std::uint32_t id = 0x20; id < 0x58; ++id) {
            (void)create_queue(id, &h, nullptr, 0);
        }
        if ((g_state.client_flags & 1u) != 0) {
            drv_log("ESVM process: register shadowing disabled");
        }
        if (g_state.shadow_gfx.base != 0) {
            std::memset(at<void>(g_state.shadow_gfx.base), 0, g_state.shadow_gfx.size);
        }
        if (g_state.shadow_agr.base != 0) {
            std::memset(at<void>(g_state.shadow_agr.base), 0, g_state.shadow_agr.size);
        }
        g_state.agr_enabled = 0;
        g_state.submit_mode = 1;
        std::uint32_t zero = 0;
        (void)gc_ioctl(kIoctlGameInitReset, &zero);
        std::uint32_t mode = 1;
        (void)gc_ioctl(kIoctlSetSubmitMode, &mode);
        register_debug_properties(true);
        drv_log("initialised, submit mode %u", g_state.submit_mode);
    } else if (g_state.client_type == 1) {
        QueueHandle *h = nullptr;
        (void)create_queue(3, &h, nullptr, 0);
        g_state.active_table = g_state.compute_sys;
        std::memset(static_cast<void *>(g_state.compute_sys), 0, sizeof g_state.compute_sys);
        register_debug_properties(false);
    }
    // 9: workloads.
    (void)workload_init();
    // 10: timestamps.
    record_event_time();
    // 11: init-tail query into the last small block.
    std::uint8_t tail[16];
    std::memset(tail, 0xFF, sizeof tail);
    const std::uint64_t tail_dst = g_state.dmem_base != 0 ? small_block_addr(2) : 0;
    if (tail_dst != 0) {
        std::memset(at<void>(tail_dst), 0xFF, 16);
    }
    const bool tail_ok = gc_ioctl(kIoctlInitTail, tail) == 0;
    if (tail_dst != 0) {
        if (tail_ok) {
            std::memcpy(at<void>(tail_dst), tail, 16);
        } else {
            std::memset(at<void>(tail_dst), 0, 16);
        }
    }
    return kOk;
}

void reset_for_tests() {
    g_state = State{};
    g_submit_seq.store(0);
}

} // namespace bc5::reimpl::agc_driver
