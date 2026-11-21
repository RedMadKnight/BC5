// SPDX-License-Identifier: GPL-2.0-only
// Clean-room re-creation of the PS5 system module libSceAgcDriver (see
// backend/src/reimpl/PROVENANCE.md). Written from a behavioural description only.
//
// The module is the user-mode half of the GPU driver: it talks to the kernel through ioctls on
// /dev/gc, writes INDIRECT_BUFFER packets straight into user-mapped compute rings and rings their
// doorbells, and writes small PM4 sequences into callers' command buffers. Every export has a
// C-compatible signature; guest pointers are host pointers and GPU addresses are plain u64.
//
// Struct layouts and ioctl request codes below are interoperability facts: per the original
// module's behaviour (clean-room description, see src/reimpl/PROVENANCE.md). Field names are ours.
#pragma once

#include "bc5/reimpl/module.hpp"

#include <cstddef>
#include <cstdint>

namespace bc5::reimpl::agc_driver {

// ---------------------------------------------------------------------------------------------
// Error codes (values are ABI; names are ours).
inline constexpr std::int32_t kOk = 0;
inline constexpr std::int32_t kErrNotPermitted = static_cast<std::int32_t>(0x8A6D0001u);
inline constexpr std::int32_t kErrInvalid = static_cast<std::int32_t>(0x8A6D0003u);
inline constexpr std::int32_t kErrProcessOrMemory = static_cast<std::int32_t>(0x8A6D0005u);
inline constexpr std::int32_t kErrHooksLoaded = static_cast<std::int32_t>(0x8A6D0006u);
inline constexpr std::int32_t kErrUmdMemoryOrUnmap = static_cast<std::int32_t>(0x8A6D0007u);
inline constexpr std::int32_t kErrMapOrClose = static_cast<std::int32_t>(0x8A6D0008u);
inline constexpr std::int32_t kErrGfxSubmit = static_cast<std::int32_t>(0x8A6D0100u);
inline constexpr std::int32_t kErrGfxPrologue = static_cast<std::int32_t>(0x8A6D0102u);
inline constexpr std::int32_t kErrQueueLock = static_cast<std::int32_t>(0x8A6D0105u);
inline constexpr std::int32_t kErrDirectSubmit = static_cast<std::int32_t>(0x8A6D0106u);
inline constexpr std::int32_t kErrSuspendCheck = static_cast<std::int32_t>(0x8A6D0107u);
inline constexpr std::int32_t kErrIdhsSubmitted = static_cast<std::int32_t>(0x8A6D0108u);
inline constexpr std::int32_t kErrMultiZero = static_cast<std::int32_t>(0x8A6D0109u);
inline constexpr std::int32_t kErrGeneric = static_cast<std::int32_t>(0x8A6DFFFFu);
inline constexpr std::int32_t kErrWfSizeZero = static_cast<std::int32_t>(0x8A6C0001u);
inline constexpr std::int32_t kErrWfNull = static_cast<std::int32_t>(0x8A6C000Au);
inline constexpr std::int32_t kErrStreamId = static_cast<std::int32_t>(0x8A6C0033u);
inline constexpr std::int32_t kErrWorkloadList = static_cast<std::int32_t>(0x8A6C0034u);
inline constexpr std::int32_t kErrStreamName = static_cast<std::int32_t>(0x8A6C0035u);
inline constexpr std::int32_t kErrStreamNotRegistered = static_cast<std::int32_t>(0x8A6C003Au);
inline constexpr std::int32_t kErrNullCommandBuffer = static_cast<std::int32_t>(0x8A6C003Bu);
inline constexpr std::int32_t kErrFeatureUnavailable = static_cast<std::int32_t>(0x8A6C0045u);
inline constexpr std::int32_t kErrResetMode = static_cast<std::int32_t>(0x8A6C0047u);
inline constexpr std::int32_t kErrCaptureUnavailable = static_cast<std::int32_t>(0x8A6C1000u);
inline constexpr std::int32_t kErrResourceRegistration = static_cast<std::int32_t>(0x8A6C9018u);
inline constexpr std::int32_t kErrDisplayBufferIndex = static_cast<std::int32_t>(0x8029000Au);

// ---------------------------------------------------------------------------------------------
// ioctl request codes on /dev/gc (the reachable ones).
inline constexpr std::uint64_t kIoctlClientInfo = 0xC004812Eu;
inline constexpr std::uint64_t kIoctlSetTrapHandler = 0x80888123u;
inline constexpr std::uint64_t kIoctlInitTail = 0xC010813Bu;
inline constexpr std::uint64_t kIoctlGameInitReset = 0x80048134u;
inline constexpr std::uint64_t kIoctlSetSubmitMode = 0x80048126u;
inline constexpr std::uint64_t kIoctlMapComputeQueue = 0xC0408121u;
inline constexpr std::uint64_t kIoctlUnmapComputeQueue = 0xC00C810Eu;
inline constexpr std::uint64_t kIoctlGfxPrologue = 0xC0488131u;
inline constexpr std::uint64_t kIoctlGfxSubmit = 0xC0188132u;
inline constexpr std::uint64_t kIoctlGfxSuspend = 0xC0088133u;
inline constexpr std::uint64_t kIoctlSuspendCheck = 0xC0108139u;
inline constexpr std::uint64_t kIoctlRingSelect = 0xC0088101u;
inline constexpr std::uint64_t kIoctlDirectSubmit = 0xC0108102u;
inline constexpr std::uint64_t kIoctlDirectSubmitTagged = 0xC018810Au;
inline constexpr std::uint64_t kIoctlPatchClearState = 0xC010812Cu;
inline constexpr std::uint64_t kIoctlSetTfRing = 0x80108128u;
inline constexpr std::uint64_t kIoctlGetTfRing = 0x40108129u;
inline constexpr std::uint64_t kIoctlSetHsOffchip = 0x8004812Au;
inline constexpr std::uint64_t kIoctlGetHsOffchip = 0x4004812Bu;
inline constexpr std::uint64_t kIoctlDebugHwStatus = 0xC0088111u;
inline constexpr std::uint64_t kIoctlSysClientNumber = 0xC0048113u;
inline constexpr std::uint64_t kIoctlSysIsGameClosed = 0xC0048115u;
inline constexpr std::uint64_t kIoctlSysSubmitDone45 = 0xC0048118u;
inline constexpr std::uint64_t kIoctlSysGfxResetStatus = 0x4004813Eu;
inline constexpr std::uint64_t kIoctlCwsr = 0xC008812Du;
inline constexpr std::uint64_t kIoctlHp3dLock = 0x80048138u;
inline constexpr std::uint64_t kIoctlForwardPair = 0x80088140u;

// ---------------------------------------------------------------------------------------------
// Caller-visible structures.

// One command buffer as callers describe it (16-byte stride).
struct CommandBufferDesc {
    std::uint64_t address; // GPU address
    std::uint32_t size_dw; // size in dwords, low 20 bits used
    std::uint8_t flags;    // copied, never interpreted by this module
    std::uint8_t pad[3];
};
static_assert(sizeof(CommandBufferDesc) == 0x10);
static_assert(offsetof(CommandBufferDesc, size_dw) == 0x08);
static_assert(offsetof(CommandBufferDesc, flags) == 0x0C);

// Internal pair: "A" (zero for user submits, or a pending suspend-point buffer) then "B".
struct SubmitPair {
    CommandBufferDesc a;
    CommandBufferDesc b;
};
static_assert(sizeof(SubmitPair) == 0x20);

using ScePthreadMutex = void *;

// The queue handle CreateQueue returns (0x50 bytes).
struct QueueHandle {
    std::uint32_t struct_size;   // 0x00, 0x38 by default
    std::uint32_t queue_id;      // 0x04
    std::uint32_t flags;         // 0x08, bit 17 = "kernel flag"
    std::uint32_t suspend_arg;   // 0x0C
    std::uint32_t direct_tag;    // 0x10, compositor: use the tagged direct submit
    std::uint32_t batch_first;   // 0x14
    std::uint32_t batch_left;    // 0x18
    std::uint32_t pad1c;         // 0x1C
    std::uint64_t seq;           // 0x20
    std::uint64_t submit_count;  // 0x28
    std::uint64_t tag;           // 0x30
    ScePthreadMutex mutex;       // 0x38
    std::uint64_t entry;         // 0x40, owning ComputeQueueEntry (0 for graphics)
    std::uint8_t mutex_ready;    // 0x48
    std::uint8_t pad49[7];
};
static_assert(sizeof(QueueHandle) == 0x50);
static_assert(offsetof(QueueHandle, flags) == 0x08);
static_assert(offsetof(QueueHandle, suspend_arg) == 0x0C);
static_assert(offsetof(QueueHandle, direct_tag) == 0x10);
static_assert(offsetof(QueueHandle, batch_first) == 0x14);
static_assert(offsetof(QueueHandle, batch_left) == 0x18);
static_assert(offsetof(QueueHandle, seq) == 0x20);
static_assert(offsetof(QueueHandle, submit_count) == 0x28);
static_assert(offsetof(QueueHandle, tag) == 0x30);
static_assert(offsetof(QueueHandle, mutex) == 0x38);
static_assert(offsetof(QueueHandle, entry) == 0x40);
static_assert(offsetof(QueueHandle, mutex_ready) == 0x48);

inline constexpr std::uint32_t kQueueKernelFlag = 0x20000u;

// One user compute queue (0x90 bytes).
struct ComputeQueueEntry {
    std::uint32_t queue_id;       // 0x00
    std::uint32_t pad04;          // 0x04
    QueueHandle handle;           // 0x08
    std::uint64_t doorbell_slot;  // 0x58
    std::uint64_t ring_base;      // 0x60
    std::uint64_t eop_area;       // 0x68
    std::uint64_t rptr_report;    // 0x70
    std::uint32_t created;        // 0x78
    std::uint32_t ring_size;      // 0x7C
    std::uint32_t eop_size;       // 0x80
    std::uint32_t ring_size2;     // 0x84
    std::uint32_t wptr_dw;        // 0x88
    std::uint32_t pad8c;          // 0x8C
};
static_assert(sizeof(ComputeQueueEntry) == 0x90);
static_assert(offsetof(ComputeQueueEntry, handle) == 0x08);
static_assert(offsetof(ComputeQueueEntry, doorbell_slot) == 0x58);
static_assert(offsetof(ComputeQueueEntry, ring_base) == 0x60);
static_assert(offsetof(ComputeQueueEntry, eop_area) == 0x68);
static_assert(offsetof(ComputeQueueEntry, rptr_report) == 0x70);
static_assert(offsetof(ComputeQueueEntry, created) == 0x78);
static_assert(offsetof(ComputeQueueEntry, ring_size) == 0x7C);
static_assert(offsetof(ComputeQueueEntry, wptr_dw) == 0x88);

// Register shadow layout (0x28 bytes).
struct RegShadowInfo {
    std::uint64_t base;
    std::uint32_t size;
    std::uint32_t ctx_first, ctx_last;
    std::uint32_t sh_first, sh_last;
    std::uint32_t uc_first, uc_last;
    std::uint32_t zero;
};
static_assert(sizeof(RegShadowInfo) == 0x28);
static_assert(offsetof(RegShadowInfo, ctx_first) == 0x0C);
static_assert(offsetof(RegShadowInfo, uc_last) == 0x20);

// Element of the graphics submit ioctl's IB array (16 bytes).
struct GraphicsIbEntry {
    std::uint32_t addr_lo;
    std::uint32_t addr_hi; // bits 32..47 in the low 16 bits
    std::uint32_t size_dw; // bits 0..19
    std::uint32_t flags;   // bit 0
};
static_assert(sizeof(GraphicsIbEntry) == 0x10);

// Direct IB packet: one INDIRECT_BUFFER PM4 packet of 4 dwords.
struct DirectIbPacket {
    std::uint32_t dw[4];
};
static_assert(sizeof(DirectIbPacket) == 0x10);

// ---------------------------------------------------------------------------------------------
// ioctl argument layouts.
struct GfxSubmitArgs { // 0xC0188132
    std::uint32_t ring;
    std::uint32_t count;
    std::uint64_t entries; // GraphicsIbEntry*
    std::uint32_t result;  // pre-set 1, kernel writes 0
    std::uint32_t zero;
};
static_assert(sizeof(GfxSubmitArgs) == 0x18);
static_assert(offsetof(GfxSubmitArgs, result) == 0x10);

struct GfxPrologueArgs { // 0xC0488131
    std::uint32_t ring;
    std::uint32_t pm4[15];
    std::uint32_t result;
    std::uint32_t extra_ib_used;
};
static_assert(sizeof(GfxPrologueArgs) == 0x48);
static_assert(offsetof(GfxPrologueArgs, result) == 0x40);

struct GfxSuspendArgs { // 0xC0088133
    std::uint32_t ring;
    std::uint32_t result;
};
static_assert(sizeof(GfxSuspendArgs) == 8);

struct SuspendCheckArgs { // 0xC0108139
    std::uint32_t status;
    std::uint32_t arg;
    std::uint64_t out;
};
static_assert(sizeof(SuspendCheckArgs) == 0x10);

struct RingSelectArgs { // 0xC0088101
    std::uint32_t ring;
    std::uint32_t mode;
};
static_assert(sizeof(RingSelectArgs) == 8);

struct DirectSubmitArgs { // 0xC0108102
    std::uint32_t ring;
    std::uint32_t count;
    std::uint64_t packets; // DirectIbPacket*
};
static_assert(sizeof(DirectSubmitArgs) == 0x10);

struct DirectSubmitTaggedArgs { // 0xC018810A
    std::uint32_t tag;
    std::uint32_t ring;
    std::uint32_t count;
    std::uint32_t zero;
    std::uint64_t packets;
};
static_assert(sizeof(DirectSubmitTaggedArgs) == 0x18);
static_assert(offsetof(DirectSubmitTaggedArgs, packets) == 0x10);

struct PatchClearStateArgs { // 0xC010812C
    std::uint64_t pairs; // {u32 reg index, u32 value}[]
    std::uint32_t count;
    std::uint32_t zero;
};
static_assert(sizeof(PatchClearStateArgs) == 0x10);

struct TfRingArgs { // 0x80108128 / 0x40108129
    std::uint64_t address;
    std::uint32_t size;
    std::uint32_t pad;
};
static_assert(sizeof(TfRingArgs) == 0x10);

struct MapQueueArgs { // 0xC0408121
    std::uint32_t me;
    std::uint32_t pipe;
    std::uint32_t queue;
    std::uint32_t vqid;
    std::uint64_t ring_base;
    std::uint64_t rptr_report;
    std::uint64_t doorbell_page;
    std::uint32_t ring_size_log2;
    std::uint32_t extra;
    std::uint64_t eop_address;
    std::uint64_t eop_size;
};
static_assert(sizeof(MapQueueArgs) == 0x40);
static_assert(offsetof(MapQueueArgs, ring_size_log2) == 0x28);
static_assert(offsetof(MapQueueArgs, eop_address) == 0x30);

struct UnmapQueueArgs { // 0xC00C810E
    std::uint32_t me;
    std::uint32_t pipe;
    std::uint32_t queue;
};
static_assert(sizeof(UnmapQueueArgs) == 12);

struct TrapHandlerArgs { // 0x80888123
    std::uint64_t code_address;
    std::uint64_t code_size;
    std::uint64_t data_address;
    std::uint64_t data_size;
    std::uint64_t cwsr_address;
    std::uint64_t cwsr_size;
    std::uint64_t wfdebug_address;
    std::uint64_t wfdebug_size;
    std::uint64_t ddid_address;
    std::uint64_t ddid_size;
    std::uint64_t handler_data_address;
    std::uint64_t handler_data_size;
    std::uint64_t wfdebug_handler_data_address;
    std::uint64_t wfdebug_handler_data_size;
    std::uint64_t wfdebug_tail_address;
    std::uint64_t wfdebug_tail_size;
    std::uint32_t extra;
    std::uint32_t zero;
};
static_assert(sizeof(TrapHandlerArgs) == 0x88);
static_assert(offsetof(TrapHandlerArgs, extra) == 0x80);

struct U32PairArgs { // CWSR, debug status, 0x80088140
    std::uint32_t first;
    std::uint32_t second;
};
static_assert(sizeof(U32PairArgs) == 8);

// kevent change entry (32 bytes).
struct KernelEvent {
    std::uint64_t ident;
    std::int16_t filter;
    std::uint16_t flags;
    std::uint32_t fflags;
    std::int64_t data;
    std::uint64_t udata;
};
static_assert(sizeof(KernelEvent) == 0x20);
static_assert(offsetof(KernelEvent, data) == 0x10);

// ---------------------------------------------------------------------------------------------
// Module lifecycle (not exports). The host calls initialize() once after resolving imports(), the
// way the original runs its initializer at load; the result is informational only.
std::int32_t initialize();
// Tests only: forget every global (no device calls).
void reset_for_tests();
// Test seam: return a compute queue entry (0x20..) to its load-time state, as for a queue the
// title never created (zeroed handle).
void forget_compute_queue_for_tests(std::uint32_t queue_id);

// ---------------------------------------------------------------------------------------------
// Exports (C-compatible signatures). Functions whose original name is unknown are named after
// their NID ('+' and '-' become '_').
// Queues and submission
std::int32_t sceAgcDriverSubmitDcb(const CommandBufferDesc *desc);
std::int32_t sceAgcDriverAgrSubmitDcb(const CommandBufferDesc *desc);
std::int32_t sceAgcDriverSubmitAcb(std::uint32_t queue_id, const CommandBufferDesc *desc);
std::int32_t sceAgcDriverSubmitCommandBuffer(QueueHandle *handle, const CommandBufferDesc *desc);
std::int32_t nid_F5ZTyyVUHTs(std::uint32_t queue_id, const CommandBufferDesc *desc,
                             std::uint64_t tag);
std::int32_t nid_Hb3p8BJm2PI(std::uint32_t queue_id, const CommandBufferDesc *desc,
                             std::uint64_t tag);
std::int32_t sceAgcDriverSubmitMultiCommandBuffers(QueueHandle *handle, const std::uint64_t *addrs,
                                                   const std::uint32_t *sizes_dw,
                                                   std::uint32_t count);
std::int32_t sceAgcDriverSubmitMultiDcbs(const std::uint64_t *addrs, const std::uint32_t *sizes_dw,
                                         std::uint32_t count);
std::int32_t sceAgcDriverAgrSubmitMultiDcbs(const std::uint64_t *addrs,
                                            const std::uint32_t *sizes_dw, std::uint32_t count);
std::int32_t sceAgcDriverSubmitMultiAcbs(std::uint32_t queue_id, const std::uint64_t *addrs,
                                         const std::uint32_t *sizes_dw, std::uint32_t count);
std::int32_t nid_kAPt2J4U3v8(const CommandBufferDesc *desc, std::uint32_t *status_out,
                             std::uint32_t suspend_arg);
std::int32_t sceAgcDriverSuspendPointSubmit(const CommandBufferDesc *desc,
                                            std::uint32_t *status_out);
std::int32_t sceAgcDriverIsSuspendPointInFlight();
std::int32_t sceAgcDriverCreateQueue(std::uint32_t queue_id, QueueHandle **handle_out,
                                     const void *config, char force);
std::int32_t sceAgcDriverDestroyQueue(QueueHandle *handle);
std::int32_t nid_dwoD_LJDQy8();
std::int32_t nid_NRO47jBXLiI();
std::int32_t sceAgcDriverSubmitToHDRScopesACQ(const CommandBufferDesc *desc);
std::int32_t sceAgcDriverIDHSSubmit(const CommandBufferDesc *desc);
std::int32_t sceAgcDriverCwsrSuspendAcq(std::uint32_t *result_out);
std::int32_t sceAgcDriverCwsrResumeAcq();
std::int32_t nid_oFb2hMcoJa4(std::int32_t enable);
std::uint8_t nid_SFB48L57OKQ();

// Register shadow, default state, async graphics
std::int32_t sceAgcDriverSetupRegisterShadow(std::uint32_t ring, std::uint8_t agr, char load_all,
                                             char clear_shadow, std::uint32_t enable);
std::int32_t sceAgcDriverGetRegShadowInfo(RegShadowInfo *out);
std::int32_t sceAgcDriverGetRegShadowInfoAgr(RegShadowInfo *out);
std::int32_t sceAgcDriverSetupAsyncGraphics(std::uint32_t enable);
std::int32_t sceAgcDriverTmpInitIdhs(std::uint32_t *pairs);
std::int32_t sceAgcDriverPatchClearState(const std::uint32_t *pairs, std::uint32_t count);
std::int32_t sceAgcDriverNotifyDefaultStates(const std::uint32_t *ctx_regs,
                                             const std::uint32_t *sh_regs,
                                             const std::uint32_t *uc_regs, std::uint32_t n_ctx,
                                             std::uint32_t n_sh, std::uint32_t n_uc);
std::int32_t sceAgcDriverPassInfoDownward(const std::uint64_t *entries, std::uint32_t count);
std::int32_t sceAgcDriverGetReservedDmemForAgc(std::uint64_t *addr_out, std::uint32_t *size_out);

// Kernel settings and debug
std::int32_t sceAgcDriverSetTFRing(std::uint64_t gpu_addr, std::uint32_t size_bytes);
std::int32_t sceAgcDriverGetTFRing(std::uint64_t *addr_out, std::uint32_t *size_out);
std::int32_t sceAgcDriverSetHsOffchipParam(std::uint32_t value_a, std::uint32_t value_b);
std::int32_t sceAgcDriverGetHsOffchipParam(std::uint16_t *value_a_out, std::uint16_t *value_b_out);
std::int32_t sceAgcDriverDebugHardwareStatus(std::int32_t mode);
std::int32_t sceAgcDriverIsTraceInProgress();
std::int32_t sceAgcDriverGetShaderDebuggingStatus();
void *nid_NhnGMuunz0Y();
std::int32_t sceAgcDriverGetGpuRefClks();
std::int32_t sceAgcDriverSetTargetRingForDiag();
std::int32_t nid_yuO_lNrj_Do(std::int32_t kind, std::uint64_t arg);
std::int32_t sceAgcDriverIsPaDebug();
std::int32_t sceAgcDriverGetGpuPrintfWorkArea();
std::int32_t sceAgcDriverRegisterGpuResetCallbacks();
std::int32_t sceAgcDriverUnregisterGpuResetCallbacks();
std::int32_t sceAgcDriverGetTraceInitiator();
std::int32_t sceAgcDriverAllocateToolMemoryForGpuReset(std::uint64_t a1, std::uint64_t a2,
                                                       std::uint64_t a3, void *out);
std::int32_t sceAgcDriverGetAllocatedToolMemoryForGpuReset(std::uint64_t a1, void *out);
std::int32_t sceAgcDriverModuleRegistration(std::uint32_t index, const void *interface_ptr);
std::int32_t nid_6v_D6CQHA4Y();

// System helpers
std::int32_t sceAgcDriverSysGetClientNumber();
std::int32_t sceAgcDriverSysIsGameClosed();
std::int32_t sceAgcDriverSysEnableSubmitDone45Exception();
std::uint32_t sceAgcDriverSysGetGfxAppGpuResetStatus();
std::int32_t sceAgcDriverSysSubmitFlipHandleProxy();
std::int32_t sceAgcDriverHp3dLockStart();
std::int32_t sceAgcDriverHp3dLockEnd();
std::int32_t nid_NQLvUnSDyBU(std::uint32_t a, std::uint32_t b);

// Event queue
std::int32_t sceAgcDriverAddEqEvent(void *eq, std::int32_t event_id, void *udata);
std::int32_t sceAgcDriverDeleteEqEvent(void *eq, std::int32_t event_id);
std::uint64_t sceAgcDriverGetEqEventType(const void *ev);
std::uint64_t sceAgcDriverGetEqContextId(const void *ev);

// Workloads
std::int32_t sceAgcDriverRegisterWorkloadStream(std::uint32_t stream_id, const char *name);
std::int32_t sceAgcDriverUnregisterWorkloadStream(std::uint32_t stream_id);
std::int32_t sceAgcDriverGetWorkloadStreamInfo(std::uint32_t stream_id, char *name_out,
                                               std::size_t name_cap,
                                               std::uint64_t *active_mask_out);
std::uint32_t sceAgcDriverGetSetWorkloadsActivePacketSize();
std::uint32_t sceAgcDriverGetSetWorkloadCompletePacketSize();
std::uint32_t sceAgcDriverGetSetWorkloadStreamInactivePacketSize();
std::int32_t sceAgcDriverSetWorkloadsActive(std::uint32_t *dst, std::int32_t pipe_flag,
                                            std::uint32_t stream_id,
                                            const std::uint32_t *workload_indices,
                                            std::uint32_t count);
std::int32_t sceAgcDriverSetWorkloadComplete(std::uint32_t *dst, std::int32_t pipe_flag,
                                             std::uint32_t stream_id,
                                             std::uint32_t workload_index);
std::int32_t sceAgcDriverSetWorkloadStreamInactive(std::uint32_t *dst, std::int32_t pipe_flag,
                                                   std::uint32_t stream_id);

// User data / markers / NOP blobs
std::uint32_t sceAgcDriverUserDataGetPacketSize(std::uint32_t payload_bytes);
std::uint32_t sceAgcDriverUserDataWritePacket(std::uint32_t *dst, std::int32_t pipe_flag,
                                              std::uint32_t header_word, const void *payload,
                                              std::uint32_t payload_bytes);
std::uint32_t sceAgcDriverUserDataWriteSetMarker(std::uint32_t *dst, std::int32_t pipe_flag,
                                                 const char *text, std::uint32_t text_bytes,
                                                 std::uint32_t color);
std::uint32_t sceAgcDriverUserDataWritePushMarker(std::uint32_t *dst, std::int32_t pipe_flag,
                                                  const char *text, std::uint32_t text_bytes,
                                                  std::uint32_t color);
std::uint32_t sceAgcDriverUserDataWritePopMarker(std::uint32_t *dst, std::int32_t pipe_flag);
std::int32_t sceAgcDriverUserDataImmediateWrite();
std::int32_t sceAgcDriverUserDataImmediateWritePacket();
std::uint32_t nid_gtvWv7DEKD4(std::uint32_t payload_bytes);
std::uint32_t nid_mQfUoU5_d1g(std::uint32_t *dst, std::uint32_t tag, const void *payload,
                              std::uint32_t payload_bytes);

// Flip
std::uint32_t sceAgcDriverGetSetFlipPacketSizeInDwords();
std::uint32_t sceAgcDriverGetWaitRenderingPacketSizeInDwords();
std::int32_t sceAgcDriverSetFlip(std::uint32_t **cursor, std::uint32_t reserved_dwords,
                                 std::int32_t pipe_flag, std::int32_t videoout_handle,
                                 std::int32_t buffer_index, std::uint32_t flip_mode,
                                 std::int64_t flip_arg);
std::int32_t sceAgcDriverWaitUntilSafeForRendering(std::uint32_t **cursor,
                                                   std::uint32_t reserved_dwords,
                                                   std::int32_t pipe_flag,
                                                   std::int32_t videoout_handle,
                                                   std::int32_t buffer_index);

// Resource registration stubs (all return kErrResourceRegistration)
std::int32_t sceAgcDriverQueryResourceRegistrationUserMemoryRequirements(std::uint64_t *size_out);
std::int32_t sceAgcDriverInitResourceRegistration();
std::int32_t sceAgcDriverGetResourceRegistrationMaxNameLength();
std::int32_t sceAgcDriverRegisterOwner();
std::int32_t sceAgcDriverRegisterResource();
std::int32_t nid_JQc0956gCf0();
std::int32_t sceAgcDriverRegisterGdsResource();
std::int32_t sceAgcDriverUnregisterResource();
std::int32_t sceAgcDriverUnregisterOwnerAndResources();
std::int32_t sceAgcDriverUnregisterAllResourcesForOwner();
std::int32_t sceAgcDriverRegisterDefaultOwner();
std::int32_t sceAgcDriverGetDefaultOwner();
std::int32_t sceAgcDriverFindResourcesPublic();
std::int32_t sceAgcDriverGetResourceName();
std::int32_t sceAgcDriverGetResourceType();
std::int32_t sceAgcDriverGetResourceBaseAddressAndSizeInBytes();
std::int32_t sceAgcDriverGetResourceUserData();
std::int32_t sceAgcDriverSetResourceUserData();
std::int32_t sceAgcDriverGetResourceShaderGuid();
std::int32_t sceAgcDriverGetOwnerName();

// Capture / validation stubs
std::int32_t sceAgcDriverTriggerCapture();
std::int32_t sceAgcDriverRequestCaptureStart();
std::int32_t sceAgcDriverRequestCaptureStop();
std::int32_t sceAgcDriverIsCaptureInProgress();
std::int32_t sceAgcDriverIsSubmitValidationEnabled();
std::int32_t nid_jwKQ1B98Q0g();
std::int32_t nid_m9n9wJC2D_4();
std::int32_t nid__iAOE3jCnkk();
std::int32_t nid_WHIOMbb_iIU();
std::int32_t nid_chJWZcNSzjk();
std::int32_t nid_ICaGtkEIXTk();
std::int32_t sceAgcDriverSetValidationErrorOutputFrequency();

// libSceAgcDriverPaDebug
std::int32_t sceAgcDriverGetPaDebugInterfaceVersion();
std::int32_t nid__MqhSEVvAPw();
std::int32_t nid_Jkypw0U_HYo();
std::int32_t sceAgcDriverSubmitMultiCommandBuffersDirect();
std::int32_t sceAgcDriverSuspendPointSubmitDirect();
std::int32_t sceAgcDriverAcquireRazorACQ();
std::int32_t sceAgcDriverReleaseRazorACQ();
std::int32_t sceAgcDriverSubmitToRazorACQ();
std::int32_t sceAgcDriverIsSuspendPointInFlightDirect();
std::int32_t nid_o2gvlIFMF1o();
std::int32_t nid_tD2ECNSuTQQ();
std::int32_t nid_9rDcI6cJb_8(std::uint32_t enable);
void nid_O144kUYDSBo();
void nid_NmE3PfE211o();
std::int32_t nid_wxdcyVqXJEY();
std::int32_t nid_1l15IdtXNWw();
std::int32_t nid_8CXPPlNmvIc();
std::int32_t nid_V_rBNI2HzGA();
std::int32_t nid_kFiKcGagv5k();
std::int32_t nid_EqwPDQyh_Ec(std::uint32_t *out);
std::int32_t nid__JFkLpCDeHM();
std::int32_t nid_gpF0LZ3_19c();
std::int32_t nid_J6S2TMmGWgA();
std::int32_t nid_8j6_e3dPf4c();
std::int32_t nid_nhzPF9s5WF0();
std::int32_t nid_Cia3HgY0WiY();
std::uint8_t nid__NIAY3DWpOw();
std::uint64_t nid_LgctzJSGy7s();
std::int32_t nid_6WO4CscVnfM();
std::int32_t nid_pto0YBGGOJo(std::uint32_t *out);
std::int32_t sceAgcDriverSetTFRingDirect();
std::int32_t sceAgcDriverSetHsOffchipParamDirect();
std::int32_t nid_VerAUWCtrX0();
std::int32_t nid_IGYqP_WKCgc();
std::int32_t nid__CSrlr1yY_o();
std::int32_t nid_mxyUaQfPgb8();
std::int32_t nid_DGN_IaHNR8o();
std::int32_t nid_38aK8XQj6Cg();
std::int32_t nid_nTwzz_6W9Jg();
std::int32_t sceAgcDriverSdmaCopyLinearBlocking();
std::int32_t sceAgcDriverRegisterCaptureInterface();
std::int32_t sceAgcDriverDeregisterCaptureInterface();
std::int32_t nid_sW7yp7NVlrk();
std::int32_t nid_1QTqF_hYqQE();

// libSceAgcDriverDebugWavefronts_nosubmission
std::int32_t nid_JvVqPfac9vE(std::uint32_t *out);
std::int32_t nid_CkL1hUyKZyo(std::uint32_t *buffer, std::uint32_t *count_out, std::uint64_t a3,
                             std::uint32_t buffer_dwords);
std::int32_t nid_6fugJiMPLGQ(std::uint64_t *out);
std::int32_t nid_cRjqDvsrGkg(std::uint64_t *out);
std::int32_t nid_dN1zf573IKU(std::uint64_t *out);
std::int32_t nid_IfCY5tDfgK8(void *buffer, std::size_t bytes);
std::int32_t nid_RXqABdLqFFA(void *buffer, std::size_t bytes);

// libSceAgcDriverDebugReset_nosubmission
std::int32_t nid_Dg_D0_2_m8g();
std::int32_t nid_4JOwdjYqMpU(std::uint32_t reset_mode_bits);
std::uint32_t nid_KKrEe_LWNG8();
std::uint32_t nid_qDjJ_CgiMzs();

} // namespace bc5::reimpl::agc_driver
