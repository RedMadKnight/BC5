// SPDX-License-Identifier: GPL-2.0-only
// Clean-room re-creation of libSceAgc (see src/reimpl/PROVENANCE.md): the *GetSize functions, the
// number of BYTES a builder writes (computed in 32 bits, returned zero-extended), per the
// original module's behaviour (clean-room description, see src/reimpl/PROVENANCE.md).
#include "bc5/reimpl/agc_internal.hpp"

namespace bc5::reimpl::agc {

using namespace detail;

namespace {
// UD(n): dwords of a driver user-data packet with an n-byte payload; 0 without the import.
std::uint32_t ud(std::uint32_t payload_bytes) {
    return g_imports.ud_get_packet_size != nullptr ? g_imports.ud_get_packet_size(payload_bytes)
                                                    : 0u;
}
std::uint64_t acquire_mem_size() { return (state().workaround_mask & 1u) != 0 ? 0x40u : 0x20u; }
std::uint64_t wait_on_address_size(std::uint32_t compare_size) {
    const std::uint32_t u = ud(4);
    const std::uint32_t e = ud(0);
    if (compare_size == 0) {
        return static_cast<std::uint32_t>((e + u) * 4u + 0x1Cu);
    }
    if (compare_size == 1) {
        return static_cast<std::uint32_t>((e + u) * 4u + 0x24u);
    }
    return 0;
}
std::uint64_t multi_draw_size(std::uint32_t body) {
    return static_cast<std::uint32_t>((2u * ud(0) + body) * 4u);
}
// INTEROP TABLE (description, agc2 section 5): bytes of the ContextStateOp sequence per op.
constexpr std::uint64_t kContextStateOpBytes[4] = {0x14, 0x6c, 0x6c, 0x80};
} // namespace

std::uint64_t sceAgcCbDispatchGetSize() { return 0x14; }
std::uint64_t sceAgcCbBranchGetSize() { return 0x38; }
std::uint64_t sceAgcCbCondWriteGetSize() { return 0x24; }
std::uint64_t sceAgcCbNopGetSize(std::uint32_t num_dwords) {
    return static_cast<std::uint32_t>(num_dwords * 4u);
}
std::uint64_t sceAgcCbQueueEndOfPipeActionGetSize() { return 0x20; }
std::uint64_t sceAgcCbSetShRegisterRangeDirectGetSize(std::uint32_t num_registers) {
    return static_cast<std::uint32_t>(num_registers * 4u + 8u);
}
std::uint64_t sceAgcCbSetUcRegisterRangeDirectGetSize(std::uint32_t num_registers) {
    return static_cast<std::uint32_t>(num_registers * 4u + 8u);
}
std::uint64_t sceAgcCbSetShRegistersDirectGetSize(std::uint32_t num_registers) {
    return static_cast<std::uint32_t>(num_registers * 12u);
}
std::uint64_t sceAgcCbSetUcRegistersDirectGetSize(std::uint32_t num_registers) {
    return static_cast<std::uint32_t>(num_registers * 12u);
}
std::uint64_t sceAgcDcbSetShRegistersIndirectGetSize() { return 0x14; }
std::uint64_t sceAgcDcbSetCxRegistersIndirectGetSize() { return 0x14; }
std::uint64_t sceAgcDcbSetUcRegistersIndirectGetSize() { return 0x14; }
std::uint64_t sceAgcDcbSetShRegisterDirectGetSize() { return 0x0C; }
std::uint64_t sceAgcDcbSetCxRegisterDirectGetSize() { return 0x0C; }
std::uint64_t sceAgcDcbSetUcRegisterDirectGetSize() { return 0x0C; }
std::uint64_t sceAgcDcbAcquireMemGetSize() { return acquire_mem_size(); }
std::uint64_t sceAgcDcbAtomicGdsGetSize() { return 0x2C; }
std::uint64_t sceAgcDcbAtomicMemGetSize() { return 0x24; }
std::uint64_t sceAgcDcbCondExecGetSize() { return 0x14; }
std::uint64_t sceAgcDcbContextStateOpGetSize(std::uint32_t op) {
    return op <= 3 ? kContextStateOpBytes[op] : 0u;
}
std::uint64_t sceAgcDcbJumpGetSize() { return 0x10; }
std::uint64_t sceAgcDcbCopyDataGetSize() { return 0x18; }
std::uint64_t sceAgcDcbDmaDataGetSize() { return 0x1C; }
std::uint64_t sceAgcDcbWriteDataGetSize(std::uint32_t num_data_dwords) {
    return static_cast<std::uint32_t>(num_data_dwords * 4u + 0x10u);
}
std::uint64_t sceAgcDcbQueueEndOfShaderActionGetSize() { return 0x20; }
std::uint64_t sceAgcDcbDispatchIndirectGetSize() { return 0x0C; }
std::uint64_t sceAgcDcbDrawIndexAutoGetSize() { return 0x0C; }
std::uint64_t sceAgcDcbDrawIndexGetSize() { return 0x18; }
std::uint64_t sceAgcDcbDrawIndexOffsetGetSize() { return 0x14; }
std::uint64_t sceAgcDcbDrawIndirectGetSize() { return 0x14; }
std::uint64_t sceAgcDcbDrawIndirectMultiGetSize() { return multi_draw_size(10); }
std::uint64_t sceAgcDcbDrawIndexIndirectMultiGetSize() { return multi_draw_size(10); }
std::uint64_t sceAgcDcbDrawIndexIndirectGetSize() { return 0x14; }
std::uint64_t sceAgcDcbDrawIndexMultiInstancedGetSize() { return multi_draw_size(9); }
std::uint64_t sceAgcDcbEventWriteGetSize(std::uint8_t event_type) {
    return (event_type & 0xFEu) == 0x38u ? 0x10u : 0x08u;
}
std::uint64_t sceAgcDcbGetLodStatsGetSize() { return 0x14; }
std::uint64_t sceAgcDcbSetBaseDispatchIndirectArgsGetSize() { return 0x10; }
std::uint64_t sceAgcDcbSetBaseDrawIndirectArgsGetSize() { return 0x10; }
std::uint64_t sceAgcDcbSetIndexSizeGetSize() { return 0x0C; }
std::uint64_t sceAgcDcbSetIndexBufferGetSize() { return 0x0C; }
std::uint64_t sceAgcDcbSetIndexCountGetSize() { return 0x08; }
std::uint64_t sceAgcDcbSetNumInstancesGetSize() { return 0x08; }
std::uint64_t sceAgcDcbStallCommandBufferParserGetSize() { return 0x08; }
std::uint64_t sceAgcDcbWaitOnAddressGetSize(std::uint32_t compare_size) {
    return wait_on_address_size(compare_size);
}
std::uint64_t sceAgcDcbRewindGetSize() { return 0x08; }
std::uint64_t sceAgcDcbBeginOcclusionQueryGetSize(std::uint32_t query_type) {
    return query_type == 1 ? 0x120u : (query_type == 0 ? 0x10u : 0u);
}
std::uint64_t sceAgcDcbEndOcclusionQueryGetSize() { return 0x10; }
std::uint64_t sceAgcDcbSetZPassPredicationEnableGetSize() { return 0x10; }
std::uint64_t sceAgcDcbSetBoolPredicationEnableGetSize() { return 0x10; }
std::uint64_t sceAgcDcbSetPredicationDisableGetSize() { return 0x10; }
std::uint64_t sceAgcDcbPrimeUtcl2GetSize() { return 0x14; }
std::uint64_t sceAgcDcbSetIndexIndirectArgsGetSize() { return 0x10; }
std::uint64_t sceAgcAcbAcquireMemGetSize() { return acquire_mem_size(); }
std::uint64_t sceAgcAcbAtomicGdsGetSize() { return 0x2C; }
std::uint64_t sceAgcAcbAtomicMemGetSize() { return 0x24; }
std::uint64_t sceAgcAcbCondExecGetSize() { return 0x14; }
std::uint64_t sceAgcAcbJumpGetSize() { return 0x10; }
std::uint64_t sceAgcAcbCopyDataGetSize() { return 0x18; }
std::uint64_t sceAgcAcbDmaDataGetSize() { return 0x1C; }
std::uint64_t sceAgcAcbDispatchIndirectGetSize() { return 0x10; }
std::uint64_t sceAgcAcbEventWriteGetSize() { return 0x08; }
std::uint64_t sceAgcAcbPrimeUtcl2GetSize() { return 0x14; }
std::uint64_t sceAgcAcbRewindGetSize() { return 0x08; }
std::uint64_t sceAgcAcbWaitOnAddressGetSize(std::uint32_t compare_size) {
    return wait_on_address_size(compare_size);
}
std::uint64_t sceAgcAcbQueueEndOfShaderActionGetSize() { return 0x20; }

} // namespace bc5::reimpl::agc
