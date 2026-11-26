// SPDX-License-Identifier: GPL-2.0-only
// Clean-room re-creation of the PS5 system module libScePsml (the PS5 Pro ML upscaler: MFSR in the
// main library "libScePsml", MFSR2 in "libScePsml_mfsr2", plus four switch sub-libraries and three
// no-op exports). Written from the behavioural description only (src/reimpl/PROVENANCE.md).
//
// Every export has a C-compatible signature (scalars and raw pointers); exports() lists them by
// NID. Every libSceAgc / libSceAgcDriver / libkernel / libc / libSceVideoOut function the module
// calls is an import slot in Imports (filled by the host glue, or by tests with fakes). A null slot
// means "not available": the module then fails the way the description says the original fails.
//
// Names of exports, structures and fields are proposals (the original exports NIDs only), per the
// original module's behaviour (clean-room description, see src/reimpl/PROVENANCE.md). Names not
// derived from the module's own messages are marked TODO(verify) where they are pure inventions.
#pragma once

#include "bc5/reimpl/module.hpp"

#include <cstddef>
#include <cstdint>

namespace bc5::reimpl::psml {

// ------------------------------------------------------------------------------------------------
// Error codes (32-bit signed results; 0 = success).
// ------------------------------------------------------------------------------------------------
namespace err {
// Main library (MFSR) facility.
inline constexpr std::int32_t kNotInitialized = static_cast<std::int32_t>(0x8a810001u);
inline constexpr std::int32_t kAlreadyInitialized = static_cast<std::int32_t>(0x8a810002u);
inline constexpr std::int32_t kProfileMismatch = static_cast<std::int32_t>(0x8a810003u);
inline constexpr std::int32_t kTooManyContexts = static_cast<std::int32_t>(0x8a810004u);
inline constexpr std::int32_t kBadContext = static_cast<std::int32_t>(0x8a810005u);
inline constexpr std::int32_t kNoRoomForPacket = static_cast<std::int32_t>(0x8a810006u);
inline constexpr std::int32_t kScratchAllocFailed = static_cast<std::int32_t>(0x8a810007u);
inline constexpr std::int32_t kNotEnoughMemory = static_cast<std::int32_t>(0x8a810008u);
inline constexpr std::int32_t kNullPointer = static_cast<std::int32_t>(0x8a810009u);
inline constexpr std::int32_t kMissingTexture = static_cast<std::int32_t>(0x8a81000au);
inline constexpr std::int32_t kKeepCopyTooLarge = static_cast<std::int32_t>(0x8a81000bu);
inline constexpr std::int32_t kInvalidParameter = static_cast<std::int32_t>(0x8a81000du);
inline constexpr std::int32_t kPlatformInitFailed = static_cast<std::int32_t>(0x8a810010u);
inline constexpr std::int32_t kShaderOrPackage = static_cast<std::int32_t>(0x8a810011u);
inline constexpr std::int32_t kNotTrinity = static_cast<std::int32_t>(0x8a810012u);
inline constexpr std::int32_t kOutputTooSmall = static_cast<std::int32_t>(0x8a810013u);
inline constexpr std::int32_t kSharedResourcesArg = static_cast<std::int32_t>(0x8a810014u);
inline constexpr std::int32_t kSharedExists = static_cast<std::int32_t>(0x8a810015u);
inline constexpr std::int32_t kVideoOutRefused = static_cast<std::int32_t>(0x8a810016u);
// MFSR2 facility.
inline constexpr std::int32_t k2NotInitialized = static_cast<std::int32_t>(0x8a8a0001u);
inline constexpr std::int32_t k2AlreadyInitialized = static_cast<std::int32_t>(0x8a8a0002u);
inline constexpr std::int32_t k2InvalidProfile = static_cast<std::int32_t>(0x8a8a0003u);
inline constexpr std::int32_t k2NullContext = static_cast<std::int32_t>(0x8a8a0005u);
inline constexpr std::int32_t k2NoCommandSpace = static_cast<std::int32_t>(0x8a8a0007u);
inline constexpr std::int32_t k2NullPointer = static_cast<std::int32_t>(0x8a8a0009u);
inline constexpr std::int32_t k2MissingTexture = static_cast<std::int32_t>(0x8a8a000au);
inline constexpr std::int32_t k2BadTexture = static_cast<std::int32_t>(0x8a8a000bu);
inline constexpr std::int32_t k2InvalidParameter = static_cast<std::int32_t>(0x8a8a000du);
inline constexpr std::int32_t k2RenderRectTooSmall = static_cast<std::int32_t>(0x8a8a000eu);
inline constexpr std::int32_t k2NotTrinity = static_cast<std::int32_t>(0x8a8a0012u);
inline constexpr std::int32_t k2NullSharedResources = static_cast<std::int32_t>(0x8a8a0014u);
inline constexpr std::int32_t k2TooManyObjects = static_cast<std::int32_t>(0x8a8a0015u);
// Agc-style errors of the descriptor / shader helpers.
inline constexpr std::int32_t kAgcMisaligned = static_cast<std::int32_t>(0x8a6c0002u);
inline constexpr std::int32_t kAgcNull = static_cast<std::int32_t>(0x8a6c000au);
inline constexpr std::int32_t kAgcTooManyUserRegs = static_cast<std::int32_t>(0x8a6c000bu);
inline constexpr std::int32_t kAgcBadStride = static_cast<std::int32_t>(0x8a6c002eu);
} // namespace err

// ------------------------------------------------------------------------------------------------
// Agc command-buffer object (0x38 bytes). The layout is the one every libSceAgc builder takes
// (per the libSceAgc clean-room description, agc1 section 3.1); the module builds one over the
// caller's reserved region and passes it to the imported builders.
// ------------------------------------------------------------------------------------------------
struct AgcCommandBuffer;
using AgcOutOfSpaceFn = bool (*)(AgcCommandBuffer *cb, std::uint32_t required_dwords, void *user);
struct AgcCommandBuffer {
    std::uint32_t *begin;
    std::uint32_t *end;
    std::uint32_t *cursor;
    std::uint32_t *limit;
    AgcOutOfSpaceFn out_of_space;
    void *user;
    std::uint32_t reserved_dwords;
    std::uint32_t pad;
};
static_assert(sizeof(AgcCommandBuffer) == 0x38);

// Register pair {offset, value} (8 bytes), as in the Agc register lists.
struct RegPair {
    std::uint32_t offset;
    std::uint32_t value;
};

// Kernel event (32 bytes) as returned by the event-queue wait. TODO(verify): field names.
struct KernelEvent {
    std::uint64_t ident;
    std::int16_t filter;
    std::uint16_t flags;
    std::uint32_t fflags;
    std::int64_t data;
    void *udata;
};
static_assert(sizeof(KernelEvent) == 32);

// One entry of the kernel's batch-map call (used only to undo a partial mapping list).
// TODO(verify): layout and the "unmap" operation value are inventions sized like the kernel's own
// batch-map entry.
struct BatchMapEntry {
    void *start;
    std::int64_t offset;
    std::uint64_t length;
    std::uint8_t protection;
    std::uint8_t type;
    std::int16_t reserved;
    std::int32_t operation;
};
inline constexpr std::int32_t kBatchMapOpUnmap = 1; // TODO(verify)

// ------------------------------------------------------------------------------------------------
// Import slots. Signatures are the ones the description gives (or the libSceAgc / libSceAgcDriver
// descriptions for those libraries). Pointer-to-function members; nullptr = not available.
// ------------------------------------------------------------------------------------------------
struct Imports {
    // libkernel
    std::int32_t (*kernel_mprotect)(const void *addr, std::uint64_t len, std::int32_t prot);
    std::int32_t (*kernel_map_named_direct_memory)(void **addr, std::uint64_t len,
                                                   std::int32_t prot, std::int32_t flags,
                                                   std::int64_t direct_offset,
                                                   std::uint64_t alignment, const char *name);
    std::int32_t (*kernel_munmap)(void *addr, std::uint64_t len);
    std::int32_t (*kernel_batch_map2)(const BatchMapEntry *entries, std::int32_t count,
                                      std::int32_t *done, std::int32_t flags);
    std::int32_t (*kernel_create_equeue)(void **eq, const char *name);
    std::int32_t (*kernel_add_user_event)(void *eq, std::int32_t id);
    std::int32_t (*kernel_add_timer_event)(void *eq, std::int32_t id, std::uint64_t usec,
                                           void *udata);
    std::int32_t (*kernel_trigger_user_event)(void *eq, std::int32_t id, void *udata);
    std::int32_t (*kernel_wait_equeue)(void *eq, KernelEvent *ev, std::int32_t num,
                                       std::int32_t *out, const std::uint32_t *timeout);
    std::int32_t (*kernel_get_event_filter)(const KernelEvent *ev);
    std::uint64_t (*kernel_get_event_id)(const KernelEvent *ev);
    void *(*kernel_get_event_user_data)(const KernelEvent *ev);
    std::int32_t (*pthread_create)(std::uint64_t *thread, const void *attr, void *(*entry)(void *),
                                   void *arg, const char *name);
    std::int32_t (*kernel_usleep)(std::uint32_t usec);
    std::int32_t (*getpid)();
    std::int32_t (*kernel_get_prospero_system_sw_version)(void *buf_0x28);
    const char *(*kernel_get_fs_sandbox_random_word)();
    std::int32_t (*kernel_compiled_sdk_version)(std::uint32_t *out); // NID GGeRJk1XdWc
    std::int32_t (*kernel_is_trinity_mode)();                        // NID tU5e3f9gSiU
    std::int32_t (*kernel_release_tool_memory)(std::uint64_t addr, std::uint64_t size);
    // libSceVideoOut
    std::int32_t (*videoout_sys_add_set_mode_event2)(void *eq, std::int32_t handle, void *udata);
    std::int32_t (*videoout_mode_query)(void *out32); // NID Ygv0S+Hi+hA, TODO(verify) signature
    // libSceLibcInternal (package files)
    std::int32_t (*libc_fopen_s)(void **fp, const char *path, const char *mode);
    std::int32_t (*libc_fseek)(void *fp, std::int64_t offset, std::int32_t whence);
    std::uint64_t (*libc_fread)(void *dst, std::uint64_t size, std::uint64_t count, void *fp);
    std::int32_t (*libc_fclose)(void *fp);
    // libSceAgc
    std::int32_t (*agc_create_shader)(void **out_shader, void *header, std::uint64_t code);
    const void *(*agc_get_register_defaults2)(std::uint32_t version);
    const void *(*agc_get_register_defaults2_internal)(std::uint32_t version);
    std::uint32_t *(*agc_cb_set_sh_registers_direct)(AgcCommandBuffer *cb, const RegPair *regs,
                                                     std::uint32_t count);
    std::uint32_t *(*agc_cb_set_sh_register_range_direct)(AgcCommandBuffer *cb,
                                                          std::uint32_t start_offset,
                                                          const std::uint32_t *values,
                                                          std::uint32_t count);
    std::uint32_t *(*agc_cb_dispatch)(AgcCommandBuffer *cb, std::uint32_t x, std::uint32_t y,
                                      std::uint32_t z, std::uint32_t initiator);
    std::uint32_t *(*agc_cb_nop)(AgcCommandBuffer *cb, std::uint32_t num_dwords);
    std::uint32_t *(*agc_dcb_push_marker)(AgcCommandBuffer *cb, const char *name,
                                          std::uint32_t color);
    std::uint32_t *(*agc_dcb_push_marker_span)(AgcCommandBuffer *cb, const char *name,
                                               std::uint32_t name_length, std::uint32_t color);
    std::uint32_t *(*agc_dcb_pop_marker)(AgcCommandBuffer *cb);
    std::uint32_t *(*agc_dcb_set_sh_registers_indirect)(AgcCommandBuffer *cb,
                                                        std::uint64_t pairs_address,
                                                        std::uint32_t num_regs);
    std::uint32_t *(*agc_dcb_event_write)(AgcCommandBuffer *cb, std::uint32_t event_type,
                                          std::uint64_t address);
    std::uint32_t *(*agc_dcb_acquire_mem)(AgcCommandBuffer *cb, std::uint8_t engine,
                                          std::uint32_t coher_control, std::uint32_t gcr_control,
                                          std::uint64_t base, std::uint64_t size,
                                          std::uint32_t poll_cycles);
    // NID zARR5aCmkoY: the 11-dword packet bracketing the persistent network.
    std::uint32_t *(*agc_dcb_bracket_packet)(AgcCommandBuffer *cb, std::int32_t engine,
                                             std::uint32_t op_flags, std::int32_t mode,
                                             std::uint32_t flag40, std::uint32_t field32,
                                             std::uint16_t gds_offset, std::uint16_t gds_size,
                                             std::uint32_t field5, std::uint32_t field6,
                                             std::uint64_t data0, std::uint64_t data1);
    void (*agc_debug_raise_exception)(std::uint32_t code, std::uint64_t arg);
    std::int32_t (*agc_init_with_version)(std::uint64_t ignored,
                                          std::uint32_t version); // 23LRUSvYu1M
    std::int32_t (*agc_capability_query)(std::uint8_t *out);      // BfBDZGbti7A
    std::int32_t (*agc_get_nop_payload)(void **out_payload, const std::uint32_t *packet,
                                        std::int32_t has_sub_header); // V++UgBtQhn0
    // libSceAgcDriver
    std::uint32_t (*driver_user_data_get_packet_size)(std::uint32_t payload_bytes);
    std::uint32_t (*driver_user_data_write_packet)(std::uint32_t *dst, std::int32_t pipe_flag,
                                                   std::uint32_t header_word, const void *payload,
                                                   std::uint32_t payload_bytes);
    std::uint32_t (*driver_data_packet_size)(std::uint32_t payload_bytes); // gtvWv7DEKD4
    std::uint32_t (*driver_write_data_packet)(std::uint32_t *dst, std::uint32_t tag,
                                              const void *payload,
                                              std::uint32_t payload_bytes); // mQfUoU5-d1g
};

// The module's import table (the slots imports() hands to the host glue).
Imports &import_table();

// ------------------------------------------------------------------------------------------------
// Caller-visible structures, main library (MFSR).
// ------------------------------------------------------------------------------------------------
struct MemoryRequirement {    // also the MFSR2 InitRequirement
    std::uint64_t alignment;  // 0x200000
    std::uint64_t block_size; // 0x200000
    std::uint64_t block_count;
};
static_assert(sizeof(MemoryRequirement) == 0x18);

struct PhysicalBlock { // MFSR: each block is 2 MiB
    std::uint64_t direct_offset;
    std::uint64_t unused;
};

struct SharedResourcesInitParameters {
    std::uint32_t profile;
    std::uint32_t reserved;
    const PhysicalBlock *blocks;
    std::uint64_t block_count;
    std::uint64_t virtual_address_start;
};
static_assert(sizeof(SharedResourcesInitParameters) == 0x20);

struct SimpleInitParameters {
    std::uint32_t profile;
    std::uint32_t pad;
    const PhysicalBlock *blocks;
    std::uint64_t block_count;
};
static_assert(sizeof(SimpleInitParameters) == 0x18);

struct TextureSizeInfo {
    std::uint32_t bytes_per_element;
    std::uint32_t width;
    std::uint32_t height;
};

struct FsrLutSize {
    std::uint32_t horizontal;
    std::uint32_t vertical;
};

struct ContextInitParametersV1 {
    std::uint32_t profile;
    std::uint32_t reserved0;
    const PhysicalBlock *blocks;
    std::uint64_t block_count;
    std::uint16_t output_width;
    std::uint16_t output_height;
    std::uint32_t reserved1;
    const void *depth_keep_template;   // 32-byte texture descriptor
    const void *history_keep_template; // 32-byte texture descriptor
    std::uint64_t unused;
    void *shared_resources;
};
static_assert(sizeof(ContextInitParametersV1) == 0x40);

struct ContextInitParametersV2 {
    std::uint32_t profile;
    std::uint32_t flags; // m_flags, bit0 = kSupportFsr
    const PhysicalBlock *blocks;
    std::uint64_t block_count;
    std::uint16_t output_width;
    std::uint16_t output_height;
    std::uint32_t reserved1;
    const TextureSizeInfo *depth_keep_size;
    const TextureSizeInfo *history_keep_size;
    std::uint64_t unused;
    void *shared_resources;
    const TextureSizeInfo *reactive_keep_size;
    const FsrLutSize *max_size_fsr_lut_for_keep_copy;
    const void *reserved_textures[2];
};
static_assert(sizeof(ContextInitParametersV2) == 0x60);

struct DispatchCommandRegion {
    std::uint32_t *start;
    std::uint32_t size_dwords;
    std::uint32_t pad;
};
static_assert(sizeof(DispatchCommandRegion) == 16);

inline constexpr std::uint32_t kKSupportFsr = 1;

// ------------------------------------------------------------------------------------------------
// Caller-visible structures, MFSR2.
// ------------------------------------------------------------------------------------------------
struct Mfsr2MemoryBlock {
    std::uint64_t direct_offset;
    std::uint64_t length;
};

struct Mfsr2SharedResourcesInitParameters {
    std::uint32_t profile;
    std::uint32_t pad;
    const Mfsr2MemoryBlock *blocks;
    std::uint64_t block_count;
    std::uint16_t max_output_width;
    std::uint16_t max_output_height;
    std::uint32_t reserved;
};
static_assert(sizeof(Mfsr2SharedResourcesInitParameters) == 0x20);

struct Mfsr2ContextInitParameters {
    std::uint32_t profile;
    std::uint32_t reserved0;
    void *shared_resources;
    const Mfsr2MemoryBlock *blocks;
    std::uint64_t block_count;
    std::uint64_t unused;
    std::uint16_t output_color_width;
    std::uint16_t output_color_height;
    std::uint32_t input_color_space;
};
static_assert(sizeof(Mfsr2ContextInitParameters) == 0x30);

struct Mfsr2RawCommandSpan {
    std::uint32_t *start;
    std::uint32_t size_dwords;
    std::uint32_t pad;
};

struct Mfsr2DispatchParameters {
    const void *output_color;
    const void *color;
    const void *motion_vectors;
    const void *depth;
    const void *exposure;
    const void *reserved_pointer;
    float pre_exposure;
    std::uint32_t render_rect[4]; // x, y, width, height
    float jitter[2];
    float motion_vector_scale[2];
    float motion_vector_offset[2];
    float camera_near;
    float camera_far;
    std::uint8_t reset;
    std::uint8_t reserved1[3];
    std::uint32_t option_flags;
    float sharpness;
};
static_assert(sizeof(Mfsr2DispatchParameters) == 0x70);

// ------------------------------------------------------------------------------------------------
// Exports. Proposed names; the NIDs are in exports().
// ------------------------------------------------------------------------------------------------
// libScePsml (MFSR)
std::int32_t psmlInitialize();
std::int32_t mfsrGetSharedResourcesInitRequirement(MemoryRequirement *out,
                                                   const SharedResourcesInitParameters *params);
std::int32_t mfsrCreateSharedResources(void **out, const SharedResourcesInitParameters *params);
std::int32_t mfsrReleaseSharedResources(void *shared);
std::int32_t mfsrGetSimpleInitRequirement(MemoryRequirement *out,
                                          const SimpleInitParameters *params);
std::int32_t mfsrGetContextAndSharedInitRequirement(MemoryRequirement *out,
                                                    const ContextInitParametersV1 *params);
std::int32_t mfsrGetContextInitRequirementV1(MemoryRequirement *out,
                                             const ContextInitParametersV1 *params);
std::int32_t mfsrGetContextInitRequirementV2(MemoryRequirement *out,
                                             const ContextInitParametersV2 *params);
std::int32_t mfsrGetContextInitRequirementV3(MemoryRequirement *out,
                                             const ContextInitParametersV2 *params);
std::int32_t mfsrCreateContextSimple(void **out, const SimpleInitParameters *params);
std::int32_t mfsrCreateContextWithOwnSharedResources(void **out,
                                                     const ContextInitParametersV1 *params);
std::int32_t mfsrCreateContextV1(void **out, const ContextInitParametersV1 *params);
std::int32_t mfsrCreateContextV2(void **out, const ContextInitParametersV2 *params);
std::int32_t mfsrCreateContextV3(void **out, const ContextInitParametersV2 *params);
std::int32_t mfsrReleaseContext(void *ctx);
std::int32_t mfsrGetDispatchCommandSize(const void *ctx, std::uint32_t *out_dwords);
std::int32_t mfsrDispatchExplicitMatrix(void *ctx, const DispatchCommandRegion *region,
                                        const void *params);
std::int32_t mfsrDispatchFloatCamera(void *ctx, const DispatchCommandRegion *region,
                                     const void *params);
std::int32_t mfsrDispatchDoubleCamera(void *ctx, const DispatchCommandRegion *region,
                                      const void *params);
std::int32_t mfsrDispatchNative(void *ctx, const DispatchCommandRegion *region, const void *params);
std::int32_t mfsrDispatchNativeValidated(void *ctx, const DispatchCommandRegion *region,
                                         const void *params);
std::int32_t mfsrGetMipLodBias(const void *ctx, float *out_bias, std::uint32_t render_width);
std::int32_t mfsrRequestCapture(void *ctx);
std::int32_t mfsrContextNoOpA(void *ctx);
std::int32_t mfsrContextNoOpB(void *ctx);

// libScePsml_mfsr2
std::int32_t sceMfsr2Initialize();
std::int32_t
sceMfsr2GetSharedResourcesInitRequirement(MemoryRequirement *req,
                                          const Mfsr2SharedResourcesInitParameters *params);
std::int32_t sceMfsr2CreateSharedResources(void **out_shared,
                                           const Mfsr2SharedResourcesInitParameters *params);
std::int32_t sceMfsr2ReleaseSharedResources(void *shared);
std::int32_t sceMfsr2GetContextInitRequirement(MemoryRequirement *req,
                                               const Mfsr2ContextInitParameters *params);
std::int32_t sceMfsr2CreateContext(void **out_context, const Mfsr2ContextInitParameters *params);
std::int32_t sceMfsr2ReleaseContext(void *ctx);
std::int32_t sceMfsr2GetDispatchCommandSize(const void *ctx, std::uint32_t *out_dwords);
std::int32_t sceMfsr2Dispatch(void *ctx, const Mfsr2RawCommandSpan *span,
                              const Mfsr2DispatchParameters *params);

// libScePsml_nosubmission (all arguments ignored)
std::int32_t scePsmlNoSubmissionStub0();
std::int32_t scePsmlNoSubmissionStub1();
std::int32_t scePsmlNoSubmissionStub2();
// libScePsml_specularAA / _quality8K / _lightweight / _set_mfsrversion
std::int32_t scePsmlEnableSpecularAA();
std::int32_t scePsmlEnableQuality8K();
std::int32_t scePsmlEnableLightweight();
std::int32_t scePsmlSetMfsrVersion(const char *version);

// ------------------------------------------------------------------------------------------------
// Pure helpers exposed for tests.
// ------------------------------------------------------------------------------------------------
// LZ4 raw-block decoder ("safe" variant): bytes written, or a negative value on malformed input.
std::int32_t lz4_decompress(const void *src, void *dst, std::int32_t src_size,
                            std::int32_t dst_capacity);
// Tile tables of the persistent MFSR2 network (30 entries each): 0, -1 bad width, -2 bad height,
// -3 more than 30 items.
std::int32_t tile_table_a(std::uint32_t *out30, std::int32_t w, std::int32_t h);
std::int32_t tile_table_b(std::uint32_t *out30, std::int32_t w, std::int32_t h);
std::int32_t tile_table_c(std::uint32_t *out30, std::int32_t w, std::int32_t h);
// Depth-linearisation parameters (A, B, C, D), mode 1 as the MFSR2 dispatch uses it.
void depth_params(float out[4], float camera_near, float camera_far, bool inverted);
// mfsrVersion string -> network version index (0..5), or kProfileMismatch.
std::int32_t version_index(const char *version, std::uint32_t compiled_sdk_version);
// IEEE half from float (round to nearest even).
std::uint16_t float_to_half(float f);

// Test support: put every module global back to its load-time state (bss zero, data defaults).
void reset_state_for_tests();
// Test support: run the event-loop body once for one event (as the event thread would).
// Returns false when the event is the stop signal.
bool handle_event_for_tests(const KernelEvent *ev);

} // namespace bc5::reimpl::psml
