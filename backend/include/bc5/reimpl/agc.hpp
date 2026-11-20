// SPDX-License-Identifier: GPL-2.0-only
// Clean-room re-creation of libSceAgc (see src/reimpl/PROVENANCE.md): every export of the module
// with a C-compatible signature. Names starting with sceAgc are the module's own export names;
// exports whose original name is unknown carry a descriptive name of our own (prefix `agc`), the
// NID that the guest links them by is in exports() (agc_exports.cpp).
//
// PM4 packet layouts follow the original module's behaviour (clean-room description, see
// src/reimpl/PROVENANCE.md); opcode names, where given in comments, are from Mesa
// src/amd/common/sid.h (commit ab2374a).
#pragma once

#include "bc5/reimpl/agc_cb.hpp"
#include "bc5/reimpl/module.hpp"

#include <cstddef>
#include <cstdint>

namespace bc5::reimpl::agc {

// ---- error codes (int32) ----------------------------------------------------------------------
inline constexpr std::int32_t kOk = 0;
inline constexpr std::int32_t kErrInternal = static_cast<std::int32_t>(0x8A6C0001u);
inline constexpr std::int32_t kErrAlign = static_cast<std::int32_t>(0x8A6C0002u);
inline constexpr std::int32_t kErrShaderMagic = static_cast<std::int32_t>(0x8A6C0003u);
inline constexpr std::int32_t kErrShaderVersion = static_cast<std::int32_t>(0x8A6C0004u);
inline constexpr std::int32_t kErrNoFreeSlot = static_cast<std::int32_t>(0x8A6C0004u);
inline constexpr std::int32_t kErrRegNotFound = static_cast<std::int32_t>(0x8A6C0005u);
inline constexpr std::int32_t kErrIncompatibleHalves = static_cast<std::int32_t>(0x8A6C0008u);
inline constexpr std::int32_t kErrNullPointer = static_cast<std::int32_t>(0x8A6C000Au);
inline constexpr std::int32_t kErrRange = static_cast<std::int32_t>(0x8A6C000Bu);
inline constexpr std::int32_t kErrWrongPacket = static_cast<std::int32_t>(0x8A6C000Cu);
inline constexpr std::int32_t kErrAlreadyCreated = static_cast<std::int32_t>(0x8A6C001Fu);
inline constexpr std::int32_t kErrNotInitialised = static_cast<std::int32_t>(0x8A6C002Fu);
inline constexpr std::int32_t kErrTargetUnsupported = static_cast<std::int32_t>(0x8A6C003Du);
inline constexpr std::int32_t kErrDebugShader = static_cast<std::int32_t>(0x8A6C0042u);
inline constexpr std::int32_t kErrSemaphoreSet = static_cast<std::int32_t>(0x8A6C0048u);
inline constexpr std::int32_t kErrSemaphoreNotSet = static_cast<std::int32_t>(0x8A6C0049u);

// ---- public structures ------------------------------------------------------------------------

// Register-defaults descriptor returned by the sceAgcGetRegisterDefaults* functions (0x40 bytes).
// Each list field points at a cell that holds the pair-array pointer.
struct RegisterDefaults {
    RegPair **cx;              // 0x00
    RegPair **sh;              // 0x08
    RegPair **uc;              // 0x10
    void *fourth;              // 0x18
    std::uint32_t cx_count;    // 0x20
    std::uint32_t sh_count;    // 0x24
    std::uint32_t uc_count;    // 0x28
    std::uint32_t fourth_count; // 0x2c
    const void *name_table;    // 0x30 12-byte entries {hash, location, ?}
    std::uint32_t name_count;  // 0x38
    std::uint32_t padding;     // 0x3c
};
static_assert(sizeof(RegisterDefaults) == 0x40);
static_assert(offsetof(RegisterDefaults, cx_count) == 0x20);
static_assert(offsetof(RegisterDefaults, name_table) == 0x30);

// Shader header object (0x60 bytes) that the application loads and sceAgcCreateShader converts in
// place. Pointer fields hold self-relative offsets before creation and absolute addresses after.
struct Shader {
    std::uint32_t magic;          // 0x00 0x34333231
    std::uint32_t version;        // 0x04 0x18
    std::uint64_t extra;          // 0x08 -> 5-qword sub-block
    std::uint64_t code_address;   // 0x10 0 before creation
    std::uint64_t ctx_regs;       // 0x18 -> RegPair[num_ctx_regs]
    std::uint64_t sh_regs;        // 0x20 -> RegPair[num_sh_regs]
    std::uint64_t info;           // 0x28 -> shader info block
    std::uint64_t ps_inputs;      // 0x30 -> uint32[num_ps_inputs]
    std::uint64_t vs_outputs;     // 0x38 -> uint32[num_vs_outputs]
    std::uint32_t header_bytes;   // 0x40
    std::uint32_t code_bytes;     // 0x44
    std::uint32_t unknown48;      // 0x48
    std::uint32_t target;         // 0x4c bits 0..30 target id, bit 31 debug-only
    std::uint32_t num_ps_inputs;  // 0x50
    std::uint16_t unknown54;      // 0x54
    std::uint16_t num_vs_outputs; // 0x56
    std::uint16_t unknown58;      // 0x58
    std::uint8_t stage;           // 0x5a
    std::uint8_t num_ctx_regs;    // 0x5b
    std::uint8_t num_sh_regs;     // 0x5c
    std::uint8_t unknown5d[3];    // 0x5d
};
static_assert(sizeof(Shader) == 0x60);
static_assert(offsetof(Shader, code_address) == 0x10);
static_assert(offsetof(Shader, info) == 0x28);
static_assert(offsetof(Shader, header_bytes) == 0x40);
static_assert(offsetof(Shader, target) == 0x4c);
static_assert(offsetof(Shader, num_vs_outputs) == 0x56);
static_assert(offsetof(Shader, stage) == 0x5a);
static_assert(offsetof(Shader, num_sh_regs) == 0x5c);

// Shader info block offsets (only these are used).
inline constexpr std::size_t kInfoUcSlot0 = 0x00;      // RegPair
inline constexpr std::size_t kInfoStagesEnable = 0x08; // RegPair (value at +0x0c)
inline constexpr std::size_t kInfoGsOutPrim = 0x20;    // RegPair
inline constexpr std::size_t kInfoUcSlot1 = 0x28;      // RegPair

struct PrimStateCx {
    RegPair stages_enable;
    RegPair gs_out_prim_type;
};
static_assert(sizeof(PrimStateCx) == 16);
struct PrimStateUc {
    RegPair pairs[3];
};
static_assert(sizeof(PrimStateUc) == 24);
struct LinkOutput {
    RegPair interpolants[32];
    PrimStateCx prim;
};
static_assert(sizeof(LinkOutput) == 0x110);

struct PayloadRange {
    void *begin;
    std::uint64_t size_bytes;
};
static_assert(sizeof(PayloadRange) == 16);

struct FusedShaderSize {
    std::uint64_t size_bytes;
    std::uint32_t alignment;
    std::uint32_t unused;
};
static_assert(sizeof(FusedShaderSize) == 16);

// The driver's command-buffer descriptor (16-byte stride): {u64 address, u32 dwords, u8 flag}.
struct CbDescriptor {
    std::uint64_t address;
    std::uint32_t size_dwords;
    std::uint8_t flag;
    std::uint8_t padding[3];
};
static_assert(sizeof(CbDescriptor) == 16);

// ---- module lifetime (DT_INIT / DT_FINI of the original; the host glue calls these once the
// imports are resolved) ---------------------------------------------------------------------------
std::int32_t module_load();
void module_unload();

// ---- ACB builders -----------------------------------------------------------------------------
std::uint32_t *sceAgcAcbAtomicMem(CommandBuffer *cb, std::uint32_t atomic_op, std::uint32_t command,
                                  std::uint64_t address, std::uint8_t cache_policy,
                                  std::uint64_t src_data, std::uint64_t cmp_data,
                                  std::uint32_t loop_interval);
std::uint32_t *sceAgcAcbAcquireMem(CommandBuffer *cb, std::uint32_t gcr_control,
                                   std::uint64_t base_address, std::uint64_t size_bytes,
                                   std::uint32_t poll_cycles);
std::uint32_t *sceAgcAcbCondExec(CommandBuffer *cb, std::uint64_t condition_address,
                                 std::uint32_t num_dwords);
std::uint32_t *sceAgcAcbCopyData(CommandBuffer *cb, std::uint32_t dst_sel,
                                 std::uint8_t dst_cache_policy, std::uint64_t dst_address,
                                 std::uint32_t src_sel, std::uint32_t src_cache_policy,
                                 std::uint64_t src_address_or_data, std::uint8_t count_sel,
                                 std::uint8_t write_confirm);
std::uint32_t *sceAgcAcbDispatchIndirect(CommandBuffer *cb, std::uint64_t args_address,
                                         std::uint32_t initiator_flags);
std::uint32_t *sceAgcAcbDmaData(CommandBuffer *cb, std::uint32_t dst_sel,
                                std::uint8_t dst_cache_policy, std::uint64_t dst_address,
                                std::uint32_t src_sel, std::uint8_t src_cache_policy,
                                std::uint64_t src_address_or_data, std::uint32_t byte_count,
                                std::uint8_t flag30, std::uint8_t flag31);
std::uint32_t *sceAgcAcbEventWrite(CommandBuffer *cb, std::uint32_t event_type);
std::uint32_t *agcAcbCopyActiveShDefaults(CommandBuffer *cb); // nid rPtseVo5ToI
std::uint32_t *sceAgcAcbResetQueue(CommandBuffer *cb, std::uint16_t flags, std::uint32_t queue_slot);
std::uint32_t *sceAgcAcbJump(CommandBuffer *cb, std::uint8_t cache_policy,
                             std::uint64_t target_address, std::uint32_t size_dwords);
std::uint32_t *sceAgcAcbWriteData(CommandBuffer *cb, std::uint32_t dst_sel, std::uint8_t cache_policy,
                                  std::uint64_t dst_address, const std::uint32_t *data,
                                  std::uint32_t num_dwords, std::uint8_t write_one_address,
                                  std::uint8_t write_confirm);
std::uint32_t *sceAgcAcbWaitRegMem(CommandBuffer *cb, std::int32_t size, std::uint8_t compare_func,
                                   std::uint8_t cache_policy, std::uint64_t address,
                                   std::uint64_t reference, std::uint64_t mask,
                                   std::uint32_t poll_cycles);
std::uint32_t *sceAgcAcbRewind(CommandBuffer *cb, std::uint32_t valid, std::uint8_t offload_enable);
std::uint32_t *sceAgcAcbPrimeUtcl2(CommandBuffer *cb, std::uint8_t cache_permissions,
                                   std::uint8_t prime_mode, std::uint64_t address,
                                   std::uint32_t num_pages);
std::uint32_t *sceAgcAcbAtomicGds(CommandBuffer *cb, std::uint32_t op_flags, std::int32_t mode,
                                  std::uint32_t flag40, std::uint32_t field32,
                                  std::uint64_t gds_offset, std::uint16_t gds_size,
                                  std::uint32_t field5, std::uint32_t field6, std::uint64_t data0,
                                  std::uint64_t data1);
std::uint32_t *agcAcbAtomicGdsOp8(CommandBuffer *cb, std::uint32_t op_flags, std::int32_t mode,
                                  std::uint32_t flag40, std::uint32_t field32,
                                  std::uint64_t gds_offset, std::uint16_t gds_size,
                                  std::uint32_t field5, std::uint32_t field6, std::uint64_t data0,
                                  std::uint64_t data1); // nid gQkqkLttcpw
std::uint32_t *sceAgcAcbSetMarkerSpan(CommandBuffer *cb, const char *name, std::uint32_t name_length,
                                      std::uint32_t color);
std::uint32_t *sceAgcAcbSetMarker(CommandBuffer *cb, const char *name, std::uint32_t color);
std::uint32_t *sceAgcAcbPushMarkerSpan(CommandBuffer *cb, const char *name,
                                       std::uint32_t name_length, std::uint32_t color);
std::uint32_t *sceAgcAcbPushMarker(CommandBuffer *cb, const char *name, std::uint32_t color);
std::uint32_t *sceAgcAcbPopMarker(CommandBuffer *cb);
std::uint32_t *sceAgcAcbSetFlip(CommandBuffer *cb, std::uint32_t arg0, std::uint32_t arg1,
                                std::uint32_t arg2, std::uint64_t arg3);
std::uint32_t *sceAgcAcbMemSemaphore(CommandBuffer *cb, std::uint64_t address,
                                     std::uint8_t use_mailbox, std::uint8_t signal_type,
                                     std::int32_t sem_sel);
std::uint32_t *sceAgcAcbWaitUntilSafeForRendering(CommandBuffer *cb, std::uint32_t arg0,
                                                  std::uint32_t arg1);
std::uint32_t *sceAgcAcbSetWorkloadsActive(CommandBuffer *cb, std::uint32_t arg0,
                                           std::uint64_t arg1, std::uint32_t arg2);
std::uint32_t *sceAgcAcbSetWorkloadComplete(CommandBuffer *cb, std::uint32_t arg0,
                                            std::uint32_t arg1);
std::uint32_t *sceAgcAcbSetWorkloadStreamInactive(CommandBuffer *cb, std::uint32_t arg0);

// ---- queue-agnostic builders --------------------------------------------------------------------
std::uint32_t *sceAgcCbBranch(CommandBuffer *cb, std::uint32_t mode, std::uint32_t compare_func,
                              std::uint64_t compare_address, std::uint64_t reference,
                              std::uint64_t mask, std::uint8_t then_cache_policy,
                              std::uint64_t then_address, std::uint32_t then_size_dwords,
                              std::uint8_t else_cache_policy, std::uint64_t else_address,
                              std::uint32_t else_size_dwords);
std::uint32_t *sceAgcCbDispatch(CommandBuffer *cb, std::uint32_t groups_x, std::uint32_t groups_y,
                                std::uint32_t groups_z, std::uint32_t initiator_flags);
std::uint32_t *sceAgcCbCondWrite(CommandBuffer *cb, std::uint32_t compare_func,
                                 std::uint32_t write_space, std::uint64_t write_address,
                                 std::uint32_t write_data, std::uint64_t poll_address,
                                 std::uint32_t reference, std::uint32_t mask);
std::uint32_t *sceAgcCbMemSemaphore(CommandBuffer *cb, std::uint64_t address,
                                    std::uint32_t use_mailbox, std::uint32_t signal_type,
                                    std::int32_t sem_sel);
std::uint32_t *sceAgcCbNop(CommandBuffer *cb, std::uint32_t num_dwords);
std::uint32_t *sceAgcCbReleaseMem(CommandBuffer *cb, std::uint8_t event_type,
                                  std::uint32_t gcr_control, std::uint32_t dst_sel,
                                  std::uint8_t cache_policy, std::uint64_t address,
                                  std::uint32_t data_sel, std::uint64_t data,
                                  std::uint16_t gds_offset, std::uint16_t gds_count,
                                  std::uint8_t interrupt_sel, std::uint32_t interrupt_context_id);
std::uint32_t *sceAgcCbSetShRegisterRangeDirect(CommandBuffer *cb, std::uint32_t start_offset,
                                                const std::uint32_t *values, std::uint32_t count);
std::uint32_t *sceAgcCbSetUcRegisterRangeDirect(CommandBuffer *cb, std::uint32_t start_offset,
                                                const std::uint32_t *values, std::uint32_t count);
std::uint32_t *sceAgcCbSetShRegistersDirect(CommandBuffer *cb, const RegPair *regs,
                                            std::uint32_t count);
std::uint32_t *sceAgcCbSetUcRegistersDirect(CommandBuffer *cb, const RegPair *regs,
                                            std::uint32_t count);
std::uint32_t *agcCbFillMemory(CommandBuffer *cb, std::uint64_t dst_address,
                               const std::uint64_t *pattern, std::uint64_t size_bytes); // 6nths4DHNrs

// ---- DCB builders -----------------------------------------------------------------------------
std::uint32_t *sceAgcDcbSetCxRegisterDirect(CommandBuffer *cb, RegPair reg);
std::uint32_t *sceAgcDcbSetCfRegisterDirect(CommandBuffer *cb, RegPair reg);
std::uint32_t *sceAgcDcbAcquireMem(CommandBuffer *cb, std::uint8_t engine, std::uint32_t coher_control,
                                   std::uint32_t gcr_control, std::uint64_t base_address,
                                   std::uint64_t size_bytes, std::uint32_t poll_cycles);
std::uint32_t *sceAgcDcbAtomicMem(CommandBuffer *cb, std::int32_t engine, std::uint32_t atomic_op,
                                  std::uint32_t command, std::uint8_t cache_policy,
                                  std::uint64_t address, std::uint64_t src_data,
                                  std::uint64_t cmp_data, std::uint32_t loop_interval);
std::uint32_t *sceAgcDcbClearState(CommandBuffer *cb, std::uint32_t op);
std::uint32_t *agcDcbContextStateOpNotify(CommandBuffer *cb, std::uint64_t op); // qj7QZpgr9Uw
std::uint32_t *sceAgcDcbSetCxRegistersIndirect(CommandBuffer *cb, std::uint64_t pairs_address,
                                               std::uint32_t num_regs);
std::uint32_t *sceAgcDcbContextStateOp(CommandBuffer *cb, std::uint32_t op);
std::uint32_t *sceAgcDcbCondExec(CommandBuffer *cb, std::uint64_t condition_address,
                                 std::uint32_t num_dwords);
std::uint32_t *sceAgcDcbJump(CommandBuffer *cb, std::uint32_t chain, std::uint8_t cache_policy,
                             std::uint64_t target_address, std::uint32_t size_dwords);
std::uint32_t *sceAgcDcbCopyData(CommandBuffer *cb, std::uint8_t dst_sel_enc,
                                 std::uint8_t dst_cache_policy, std::uint64_t dst_address,
                                 std::uint32_t src_sel_enc, std::uint32_t src_cache_policy,
                                 std::uint64_t src_address_or_data, std::uint8_t count_sel,
                                 std::uint8_t write_confirm);
std::uint32_t *sceAgcDcbDmaData(CommandBuffer *cb, std::uint8_t engine, std::uint32_t dst_sel,
                                std::uint8_t dst_cache_policy, std::uint64_t dst_address,
                                std::uint32_t src_sel, std::uint8_t src_cache_policy,
                                std::uint64_t src_address_or_data, std::uint32_t byte_count,
                                std::uint8_t flag30, std::uint8_t flag31, std::uint8_t cp_sync);
std::uint32_t *sceAgcDcbWriteData(CommandBuffer *cb, std::uint32_t dst_sel_enc,
                                  std::uint8_t cache_policy, std::uint64_t dst_address,
                                  const std::uint32_t *data, std::uint32_t num_dwords,
                                  std::uint8_t write_one_address, std::uint8_t write_confirm);
std::uint32_t *sceAgcDcbSetShRegistersIndirect(CommandBuffer *cb, std::uint64_t pairs_address,
                                               std::uint32_t num_regs);
std::uint32_t *sceAgcDcbSetUcRegistersIndirect(CommandBuffer *cb, std::uint64_t pairs_address,
                                               std::uint32_t num_regs);
std::uint32_t *sceAgcDcbSetUcRegisterDirect(CommandBuffer *cb, RegPair reg);
std::uint32_t *sceAgcDcbSetShRegisterDirect(CommandBuffer *cb, RegPair reg);
std::uint32_t *sceAgcDcbSetCfRegisterRangeDirect(CommandBuffer *cb, std::uint32_t start_offset,
                                                 const std::uint32_t *values, std::uint32_t count);
std::uint32_t *sceAgcDcbDispatchIndirect(CommandBuffer *cb, std::uint32_t args_offset,
                                         std::uint32_t initiator_flags);
std::uint32_t *sceAgcDcbDrawIndexAuto(CommandBuffer *cb, std::uint32_t vertex_count,
                                      std::uint64_t modifier);
std::uint32_t *sceAgcDcbDrawIndex(CommandBuffer *cb, std::uint32_t index_count,
                                  std::uint64_t index_address, std::uint64_t modifier);
std::uint32_t *sceAgcDcbDrawIndexOffset(CommandBuffer *cb, std::uint32_t index_offset,
                                        std::uint32_t index_count, std::uint64_t modifier);
std::uint32_t *sceAgcDcbDrawIndirect(CommandBuffer *cb, std::uint32_t args_offset,
                                     std::uint64_t modifier);
std::uint32_t *sceAgcDcbDrawIndirectMulti(CommandBuffer *cb, std::uint32_t args_offset,
                                          std::uint8_t count_indirect_enable, std::uint32_t max_count,
                                          std::uint64_t count_address, std::uint32_t stride,
                                          std::uint64_t modifier);
std::uint32_t *sceAgcDcbDrawIndexIndirectMulti(CommandBuffer *cb, std::uint32_t args_offset,
                                               std::uint8_t count_indirect_enable,
                                               std::uint32_t max_count,
                                               std::uint64_t count_address, std::uint32_t stride,
                                               std::uint64_t modifier);
std::uint32_t *sceAgcDcbDrawIndexIndirect(CommandBuffer *cb, std::uint32_t args_offset,
                                          std::uint64_t modifier);
std::uint32_t *sceAgcDcbDrawIndexMultiInstanced(CommandBuffer *cb, std::uint32_t arg0,
                                                std::uint64_t index_address,
                                                std::uint64_t instance_data_address,
                                                std::uint32_t index_count, std::uint64_t modifier);
std::uint32_t *sceAgcDcbEventWrite(CommandBuffer *cb, std::uint32_t event_type, std::uint64_t address);
std::uint32_t *sceAgcDcbGetLodStats(CommandBuffer *cb, std::uint8_t cache_policy,
                                    std::uint64_t out_address, std::uint32_t arg0,
                                    std::uint32_t field_a, std::uint32_t flag_b, std::uint8_t flag_c,
                                    std::uint32_t field_d);
std::uint32_t *agcDcbResetActiveQueue(CommandBuffer *cb); // Xvcgh9xNNkY
std::uint32_t *sceAgcDcbSetBaseIndirectArgs(CommandBuffer *cb, std::int32_t compute,
                                            std::uint64_t base_address);
std::uint32_t *sceAgcDcbSetIndexSize(CommandBuffer *cb, std::uint8_t index_size,
                                     std::uint8_t cache_policy);
std::uint32_t *agcDcbSetIndexSizeEx(CommandBuffer *cb, std::uint8_t index_size,
                                    std::uint8_t cache_policy, std::uint32_t extra_flag); // -KRzWekV120
std::uint32_t *sceAgcDcbSetIndexBuffer(CommandBuffer *cb, std::uint64_t index_address);
std::uint32_t *sceAgcDcbSetIndexCount(CommandBuffer *cb, std::uint32_t index_count);
std::uint32_t *sceAgcDcbSetNumInstances(CommandBuffer *cb, std::uint32_t num_instances);
std::uint32_t *sceAgcDcbStallCommandBufferParser(CommandBuffer *cb);
std::uint32_t *sceAgcDcbWaitRegMem(CommandBuffer *cb, std::int32_t size, std::uint8_t compare_func,
                                   std::uint32_t engine_and_op, std::uint8_t cache_policy,
                                   std::uint64_t address, std::uint64_t reference,
                                   std::uint64_t mask, std::uint32_t poll_cycles);
std::uint32_t *sceAgcDcbRewind(CommandBuffer *cb, std::uint32_t valid);
std::uint32_t *sceAgcDcbPrimeUtcl2(CommandBuffer *cb, std::uint8_t cache_permissions,
                                   std::uint8_t prime_mode, std::uint64_t address,
                                   std::uint32_t num_pages);
std::uint32_t *sceAgcDcbResetQueue(CommandBuffer *cb, std::uint16_t flags, std::uint32_t queue_slot);
std::uint32_t *sceAgcDcbSetIndexIndirectArgs(CommandBuffer *cb, std::uint64_t address,
                                             std::uint32_t value16);
std::uint32_t *sceAgcDcbSetPredication(CommandBuffer *cb, std::uint32_t predicate_bool,
                                       std::uint32_t predicate_op, std::uint32_t hint,
                                       std::uint64_t address);
std::uint32_t *sceAgcDcbAtomicGds(CommandBuffer *cb, std::int32_t engine, std::uint32_t op_flags,
                                  std::int32_t mode, std::uint32_t flag40, std::uint32_t field32,
                                  std::uint16_t gds_offset, std::uint16_t gds_size,
                                  std::uint32_t field5, std::uint32_t field6, std::uint64_t data0,
                                  std::uint64_t data1);
std::uint32_t *agcDcbAtomicGdsOp8(CommandBuffer *cb, std::int32_t engine, std::uint32_t op_flags,
                                  std::int32_t mode, std::uint32_t flag40, std::uint32_t field32,
                                  std::uint16_t gds_offset, std::uint16_t gds_size,
                                  std::uint32_t field5, std::uint32_t field6, std::uint64_t data0,
                                  std::uint64_t data1); // zARR5aCmkoY
std::uint32_t *sceAgcDcbSetMarkerSpan(CommandBuffer *cb, const char *name, std::uint32_t name_length,
                                      std::uint32_t color);
std::uint32_t *sceAgcDcbSetMarker(CommandBuffer *cb, const char *name, std::uint32_t color);
std::uint32_t *sceAgcDcbPushMarkerSpan(CommandBuffer *cb, const char *name,
                                       std::uint32_t name_length, std::uint32_t color);
std::uint32_t *sceAgcDcbPushMarker(CommandBuffer *cb, const char *name, std::uint32_t color);
std::uint32_t *sceAgcDcbPopMarker(CommandBuffer *cb);
std::uint32_t *sceAgcDcbSetFlip(CommandBuffer *cb, std::uint32_t arg0, std::uint32_t arg1,
                                std::uint32_t arg2, std::uint64_t arg3);
std::uint32_t *sceAgcDcbWaitUntilSafeForRendering(CommandBuffer *cb, std::uint32_t arg0,
                                                  std::uint32_t arg1);
std::uint32_t *sceAgcDcbMemSemaphore(CommandBuffer *cb, std::uint64_t address,
                                     std::uint8_t use_mailbox, std::uint8_t signal_type,
                                     std::int32_t sem_sel);
std::uint32_t *sceAgcDcbSetWorkloadsActive(CommandBuffer *cb, std::uint32_t arg0,
                                           std::uint64_t arg1, std::uint64_t arg2);
std::uint32_t *sceAgcDcbSetWorkloadComplete(CommandBuffer *cb, std::uint32_t arg0,
                                            std::uint32_t arg1);
std::uint32_t *sceAgcDcbSetWorkloadStreamInactive(CommandBuffer *cb, std::uint32_t arg0);

// ---- module / system functions ------------------------------------------------------------------
std::int32_t sceAgcSetStaticBuffer(std::uint32_t index, const std::uint64_t *entry);
std::int32_t sceAgcGetStaticBuffer(std::uint32_t index, std::uint64_t *entry_out);
std::int32_t agcSetStaticWord(std::uint32_t index, std::uint64_t value);  // 86rJnbZUpr4
std::int32_t agcGetStaticWord(std::uint32_t index, std::uint64_t *out);   // NbiQSQ-UL+M
std::int32_t agcSetSuspendConfig(std::uint32_t config);                    // RTpj-tIlvZc
std::uint32_t agcGetSuspendConfig();                                       // SwI6QxqwAC0
std::int32_t sceAgcSetAmmSemaphoreMemory(std::uint64_t address, std::uint64_t size_bytes);
std::int32_t agcSetSemaphoreMemoryLimited(std::uint64_t address, std::uint64_t size_bytes); // v3G+IipShZs
std::int32_t sceAgcGetSemaphoreLabel(std::uint32_t index, std::uint64_t *address_out);
std::int32_t sceAgcGetDefaultCxStateFlat(std::uint32_t *out, std::uint32_t first_reg,
                                         std::uint32_t end_reg, std::uint32_t slot_index);
std::int32_t agcSetTrustedRange(std::uint64_t range_lo, std::uint64_t range_hi); // shuFv6ZAOsI
std::int32_t sceAgcSuspendPoint();
std::int32_t sceAgcSetSubmitMode(std::uint32_t mode);
std::int32_t sceAgcInit(std::uint32_t sdk_version);
std::int32_t agcInitWithVersion(std::uint64_t ignored, std::uint32_t sdk_version); // 23LRUSvYu1M
std::int32_t agcQueryKernelFlag(std::uint8_t *out);                                 // BfBDZGbti7A
std::int32_t sceAgcSuspendPointAndCheckStatus(std::uint64_t status_arg);
const RegisterDefaults *agcGetRegisterDefaultsForVersion(std::uint32_t sdk_version); // ddU6mOWyY40
const RegisterDefaults *agcGetRegisterDefaultsInternalForVersion(std::uint32_t sdk_version); // MGEQ
const RegisterDefaults *sceAgcGetRegisterDefaults2(std::uint32_t sdk_version);
const RegisterDefaults *sceAgcGetRegisterDefaults2Internal(std::uint32_t sdk_version);
const RegisterDefaults *sceAgcGetRegisterDefaults();
const RegisterDefaults *sceAgcGetRegisterDefaultsInternal();
std::int32_t sceAgcDebugRaiseException(std::uint32_t code, std::uint64_t arg);
std::int32_t agcGetCuMaskOverridesForVersion(const RegPair **pairs_out, const std::uint32_t **masks_out,
                                             std::uint32_t *count_out,
                                             std::uint32_t sdk_version); // Eq7asRCcfMs
std::int32_t agcGetCuMaskOverrides(const RegPair **pairs_out, const std::uint32_t **masks_out,
                                   std::uint32_t *count_out); // pRO4U9d0vaA
std::int32_t agcGetComputeThreadMaskOverrides(const RegPair **pairs_out,
                                              const std::uint32_t **masks_out,
                                              std::uint32_t *count_out); // h4h5EQ-Y20M

// ---- packet patch helpers and utilities ---------------------------------------------------------
std::int32_t sceAgcBranchPatchSetThenTarget(std::uint32_t *packet, std::uint64_t then_address,
                                            std::uint32_t then_size_dwords);
std::int32_t sceAgcBranchPatchSetElseTarget(std::uint32_t *packet, std::uint64_t else_address,
                                            std::uint32_t else_size_dwords);
std::int32_t agcBranchPatchSetThenTargetEx(std::uint32_t *packet, std::uint8_t cache_policy,
                                           std::uint64_t then_address,
                                           std::uint32_t then_size_dwords); // 7Wa3aeJgeVU
std::int32_t agcBranchPatchSetElseTargetEx(std::uint32_t *packet, std::uint8_t cache_policy,
                                           std::uint64_t else_address,
                                           std::uint32_t else_size_dwords); // rP5xLdOf26k
std::int32_t sceAgcBranchPatchSetCompareAddress(std::uint32_t *packet, std::uint64_t address);
std::int32_t sceAgcJumpPatchSetTarget(std::uint32_t *packet, std::uint64_t target_address,
                                      std::uint32_t size_dwords);
std::int32_t agcJumpPatchSetTargetEx(std::uint32_t *packet, std::uint8_t mode,
                                     std::uint64_t target_address,
                                     std::uint32_t size_dwords); // Ikfdt-rIqCE
std::int32_t sceAgcSetShRegIndirectPatchSetAddress(std::uint32_t *packet, std::uint64_t address);
std::int32_t sceAgcSetShRegIndirectPatchSetNumRegisters(std::uint32_t *packet, std::uint32_t num);
std::int32_t sceAgcSetShRegIndirectPatchAddRegisters(std::uint32_t *packet, std::int32_t delta);
std::int32_t sceAgcSetCxRegIndirectPatchSetAddress(std::uint32_t *packet, std::uint64_t address);
std::int32_t sceAgcSetCxRegIndirectPatchSetNumRegisters(std::uint32_t *packet, std::uint32_t num);
std::int32_t sceAgcSetCxRegIndirectPatchAddRegisters(std::uint32_t *packet, std::int32_t delta);
std::int32_t sceAgcSetUcRegIndirectPatchSetAddress(std::uint32_t *packet, std::uint64_t address);
std::int32_t sceAgcSetUcRegIndirectPatchSetNumRegisters(std::uint32_t *packet, std::uint32_t num);
std::int32_t sceAgcSetUcRegIndirectPatchAddRegisters(std::uint32_t *packet, std::int32_t delta);
std::int32_t sceAgcCondExecPatchSetEnd(std::uint32_t *packet, const void *end_of_block);
std::int32_t sceAgcCondExecPatchSetCommandAddress(std::uint32_t *packet, std::uint64_t address);
std::int32_t sceAgcAsyncCondExecPatchSetEnd(std::uint32_t *packet, const void *end_of_block);
std::int32_t sceAgcAsyncCondExecPatchSetCommandAddress(std::uint32_t *packet, std::uint64_t address);
std::int32_t sceAgcRewindPatchSetRewindState(std::uint32_t *packet, std::uint8_t valid);
std::int32_t sceAgcAsyncRewindPatchSetRewindState(std::uint32_t *packet, std::uint8_t valid);
std::int32_t sceAgcSetPacketPredication(std::uint32_t *packet, std::int32_t predication);
std::uint32_t sceAgcGetPacketSize(const std::uint32_t *packet);
std::int32_t sceAgcSetNop(std::uint32_t *packet);
std::int32_t sceAgcSetRangePredication(std::uint32_t *begin, std::uint32_t *end,
                                       std::uint8_t predication);
std::int32_t sceAgcGetDataPacketPayloadAddress(void **out_payload, const std::uint32_t *packet,
                                               std::int32_t has_sub_header);
std::int32_t agcGetDataPacketPayloadAddressChecked(void **out_payload, const std::uint32_t *packet,
                                                   std::int32_t has_sub_header); // V++UgBtQhn0
std::int32_t sceAgcGetDataPacketPayloadRange(PayloadRange *out, const std::uint32_t *packet,
                                             std::int32_t has_sub_header);
std::int32_t sceAgcDmaDataPatchSetDstAddressOrOffset(std::uint32_t *packet, std::uint64_t dst);
std::int32_t sceAgcDmaDataPatchSetSrcAddressOrOffsetOrImmediate(std::uint32_t *packet,
                                                                std::uint64_t src);
std::int32_t sceAgcWaitRegMemPatchAddress(std::uint32_t *sequence, std::uint64_t address);
std::int32_t sceAgcWaitRegMemPatchCompareFunction(std::uint32_t *sequence, std::uint8_t func);
std::int32_t sceAgcWaitRegMemPatchReference(std::uint32_t *sequence, std::uint32_t reference);
std::int32_t sceAgcWaitRegMemPatchMask(std::uint32_t *sequence, std::uint32_t mask);
std::int32_t sceAgcQueueEndOfPipeActionPatchAddress(std::uint32_t *packet, std::uint64_t address);
std::int32_t sceAgcQueueEndOfPipeActionPatchGcrCntl(std::uint32_t *packet, std::uint32_t gcr_cntl);
std::int32_t sceAgcQueueEndOfPipeActionPatchType(std::uint32_t *packet, std::uint8_t event_type);
std::int32_t sceAgcQueueEndOfPipeActionPatchData(std::uint32_t *packet, std::uint64_t data);
std::int32_t sceAgcAcquireMemSetEngine(std::uint32_t *packet, std::uint8_t engine);
std::int32_t agcWriteDataPatchSetAddress(std::uint32_t *packet, std::uint64_t address);   // fPSCdQxgpSw
std::int32_t agcWriteDataPatchSetCachePolicy(std::uint32_t *packet, std::uint8_t policy); // eAy8eGNsCuU
std::int32_t agcWriteDataPatchSetDestination(std::uint32_t *packet, std::uint8_t dest);   // tmy-+rBpspY
std::int32_t agcWriteDataPatchSetAddress2(std::uint32_t *packet, std::uint64_t address);  // d4NZIlguzv0
std::int32_t agcWriteDataPatchSetCachePolicy2(std::uint32_t *packet, std::uint8_t policy); // y5K5tPktiL8
std::int32_t agcWriteDataPatchSetDstSel(std::uint32_t *packet, std::uint8_t dst_sel);     // EJBA4dbmvfg

// ---- GetSize functions (bytes a builder writes) -------------------------------------------------
std::uint64_t sceAgcCbDispatchGetSize();
std::uint64_t sceAgcCbBranchGetSize();
std::uint64_t sceAgcCbCondWriteGetSize();
std::uint64_t sceAgcCbNopGetSize(std::uint32_t num_dwords);
std::uint64_t sceAgcCbQueueEndOfPipeActionGetSize();
std::uint64_t sceAgcCbSetShRegisterRangeDirectGetSize(std::uint32_t num_registers);
std::uint64_t sceAgcCbSetUcRegisterRangeDirectGetSize(std::uint32_t num_registers);
std::uint64_t sceAgcCbSetShRegistersDirectGetSize(std::uint32_t num_registers);
std::uint64_t sceAgcCbSetUcRegistersDirectGetSize(std::uint32_t num_registers);
std::uint64_t sceAgcDcbSetShRegistersIndirectGetSize();
std::uint64_t sceAgcDcbSetCxRegistersIndirectGetSize();
std::uint64_t sceAgcDcbSetUcRegistersIndirectGetSize();
std::uint64_t sceAgcDcbSetShRegisterDirectGetSize();
std::uint64_t sceAgcDcbSetCxRegisterDirectGetSize();
std::uint64_t sceAgcDcbSetUcRegisterDirectGetSize();
std::uint64_t sceAgcDcbAcquireMemGetSize();
std::uint64_t sceAgcDcbAtomicGdsGetSize();
std::uint64_t sceAgcDcbAtomicMemGetSize();
std::uint64_t sceAgcDcbCondExecGetSize();
std::uint64_t sceAgcDcbContextStateOpGetSize(std::uint32_t op);
std::uint64_t sceAgcDcbJumpGetSize();
std::uint64_t sceAgcDcbCopyDataGetSize();
std::uint64_t sceAgcDcbDmaDataGetSize();
std::uint64_t sceAgcDcbWriteDataGetSize(std::uint32_t num_data_dwords);
std::uint64_t sceAgcDcbQueueEndOfShaderActionGetSize();
std::uint64_t sceAgcDcbDispatchIndirectGetSize();
std::uint64_t sceAgcDcbDrawIndexAutoGetSize();
std::uint64_t sceAgcDcbDrawIndexGetSize();
std::uint64_t sceAgcDcbDrawIndexOffsetGetSize();
std::uint64_t sceAgcDcbDrawIndirectGetSize();
std::uint64_t sceAgcDcbDrawIndirectMultiGetSize();
std::uint64_t sceAgcDcbDrawIndexIndirectMultiGetSize();
std::uint64_t sceAgcDcbDrawIndexIndirectGetSize();
std::uint64_t sceAgcDcbDrawIndexMultiInstancedGetSize();
std::uint64_t sceAgcDcbEventWriteGetSize(std::uint8_t event_type);
std::uint64_t sceAgcDcbGetLodStatsGetSize();
std::uint64_t sceAgcDcbSetBaseDispatchIndirectArgsGetSize();
std::uint64_t sceAgcDcbSetBaseDrawIndirectArgsGetSize();
std::uint64_t sceAgcDcbSetIndexSizeGetSize();
std::uint64_t sceAgcDcbSetIndexBufferGetSize();
std::uint64_t sceAgcDcbSetIndexCountGetSize();
std::uint64_t sceAgcDcbSetNumInstancesGetSize();
std::uint64_t sceAgcDcbStallCommandBufferParserGetSize();
std::uint64_t sceAgcDcbWaitOnAddressGetSize(std::uint32_t compare_size);
std::uint64_t sceAgcDcbRewindGetSize();
std::uint64_t sceAgcDcbBeginOcclusionQueryGetSize(std::uint32_t query_type);
std::uint64_t sceAgcDcbEndOcclusionQueryGetSize();
std::uint64_t sceAgcDcbSetZPassPredicationEnableGetSize();
std::uint64_t sceAgcDcbSetBoolPredicationEnableGetSize();
std::uint64_t sceAgcDcbSetPredicationDisableGetSize();
std::uint64_t sceAgcDcbPrimeUtcl2GetSize();
std::uint64_t sceAgcDcbSetIndexIndirectArgsGetSize();
std::uint64_t sceAgcAcbAcquireMemGetSize();
std::uint64_t sceAgcAcbAtomicGdsGetSize();
std::uint64_t sceAgcAcbAtomicMemGetSize();
std::uint64_t sceAgcAcbCondExecGetSize();
std::uint64_t sceAgcAcbJumpGetSize();
std::uint64_t sceAgcAcbCopyDataGetSize();
std::uint64_t sceAgcAcbDmaDataGetSize();
std::uint64_t sceAgcAcbDispatchIndirectGetSize();
std::uint64_t sceAgcAcbEventWriteGetSize();
std::uint64_t sceAgcAcbPrimeUtcl2GetSize();
std::uint64_t sceAgcAcbRewindGetSize();
std::uint64_t sceAgcAcbWaitOnAddressGetSize(std::uint32_t compare_size);
std::uint64_t sceAgcAcbQueueEndOfShaderActionGetSize();

// ---- shader objects -------------------------------------------------------------------------------
std::int32_t sceAgcCreateShader(Shader **out_shader, Shader *header, std::uint64_t code_address);
std::int32_t agcGetFusedShaderSize64(std::uint64_t *out_size_align, const Shader *first_half,
                                     const Shader *second_half); // dolOmWH+huQ
std::int32_t sceAgcGetFusedShaderSize(FusedShaderSize *out, const Shader *first_half,
                                      const Shader *second_half);
std::int32_t sceAgcFuseShaderHalves(Shader *out, const Shader *first_half, Shader *second_half,
                                    RegPair *reg_buffer);
std::int32_t agcFuseShaderHalves2(Shader *out, const Shader *first_half, Shader *second_half,
                                  RegPair *reg_buffer); // fd5Bp5tGTgo
std::int32_t sceAgcLinkShaders(LinkOutput *out, PrimStateUc *out_uc, const Shader *aux_shader,
                               const Shader *main_shader, const Shader *ps_shader,
                               std::uint32_t prim_type);
std::int32_t sceAgcCreateInterpolantMapping(RegPair *out, const Shader *vs_shader,
                                            const Shader *ps_shader);
std::int32_t sceAgcUpdateInterpolantMapping(RegPair *out, const Shader *vs_shader,
                                            const Shader *ps_shader);
std::int32_t agcCreateInterpolantMappingB(RegPair *out, const Shader *vs_shader,
                                          const Shader *ps_shader); // HV4j+E0MBHE
std::int32_t agcUpdateInterpolantMappingB(RegPair *out, const Shader *vs_shader,
                                          const Shader *ps_shader); // k0E7vkgqAuE
std::int32_t agcCreateInterpolantMappingC(RegPair *out, const Shader *vs_shader,
                                          const Shader *ps_shader); // dbOlWdppb4o
std::int32_t agcUpdateInterpolantMappingC(RegPair *out, const Shader *vs_shader,
                                          const Shader *ps_shader); // vieBRwlh1Lw
std::int32_t sceAgcCreatePrimState(PrimStateCx *out_cx, PrimStateUc *out_uc,
                                   const Shader *aux_shader, const Shader *main_shader,
                                   std::uint32_t prim_type);
std::int32_t sceAgcUpdatePrimState(PrimStateCx *cx, PrimStateUc *uc, std::uint32_t prim_type);
std::int32_t sceAgcGetGsOversubscription(RegPair *out, const Shader *gs_shader, std::uint32_t budget,
                                         float fraction);
std::int32_t agcGetShaderExportFlag(std::uint32_t *out_value, const Shader *shader); // ICkECTBxrMw

// Exported 4-byte data object (nid bi4pcLifd1k), zero-initialised, unused by the module.
extern std::uint32_t g_exported_word;

// ---- test support (not exported to the guest) -----------------------------------------------------
namespace testing {
// Reset every module global to its load-time initial value (before module_load()).
void reset();
// The fixed GPU address the static area must land on (0xFE0040000 on the console). Tests point it
// at their own buffer.
void set_expected_static_area(std::uint64_t address);
// Mark the internal shaders as BC5's own (as the own-data init path does).
void set_internal_own(bool value);
void set_soc_id(std::uint32_t soc_id);
void set_workaround_mask(std::uint32_t mask);
void set_trace_initiator(std::uint32_t index_1_to_10, std::uint32_t value);
void set_use_clear_state_for_cx(std::uint32_t value);
void set_kernel_flag(bool value);
void set_dmem(std::uint64_t cursor, std::uint64_t end);
void set_sync_label(std::uint64_t address);
// Install a fake for the import with this NID; false when the NID is not an import of the module.
bool set_import(const char *nid, void *function);
// Clear every import slot.
void clear_imports();
// Queue-state slot access: version, trusted, tables, prebuilt stream, resume DCB.
struct SlotView {
    RegPair *cx;
    RegPair *sh;
    RegPair *uc;
    std::uint32_t cx_count, sh_count, uc_count, uc_special_count;
    std::uint32_t *sh_stream;
    std::uint32_t sh_stream_bytes;
    std::uint32_t *resume_dcb;
    std::uint32_t resume_dwords;
    std::uint32_t version;
    bool trusted;
};
SlotView slot(std::uint32_t index);
void set_slot(std::uint32_t index, const SlotView &view);
void set_active_slot(std::int32_t index, bool suspend_ready);
std::uint64_t static_area();
std::uint64_t sync_label();
std::uint32_t workaround_mask();
std::uint64_t semaphore_base();
std::uint64_t semaphore_size();
const Shader *fill_shader();
void set_fill_shader(const Shader *shader);
void set_restore_pairs(RegPair a, RegPair b);
// Resolved register descriptor by its address in the original image (e.g. 0x45c90); nullptr if
// this re-creation does not model that descriptor.
RegPair *descriptor(std::uint64_t vaddr);
} // namespace testing

} // namespace bc5::reimpl::agc
