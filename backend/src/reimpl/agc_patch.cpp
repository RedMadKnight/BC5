// SPDX-License-Identifier: GPL-2.0-only
// Clean-room re-creation of libSceAgc (see src/reimpl/PROVENANCE.md): packet patch helpers and
// packet utilities. Each patch helper checks the opcode byte (byte 1 of the header) and rewrites
// one field of a packet a builder wrote earlier; field positions are per the original module's
// behaviour (clean-room description, see src/reimpl/PROVENANCE.md).
#include "bc5/reimpl/agc_internal.hpp"

namespace bc5::reimpl::agc {

using namespace detail;

namespace {

// One-dword NOP form: opcode 0x10 with count 0x3FFF.
std::uint32_t packet_size_dwords(std::uint32_t header) {
    if ((header & 0x3FFFFF00u) == 0x3FFF1000u) {
        return 1;
    }
    return ((header >> 16) & 0x3FFFu) + 2u;
}

void set_address_dw12(std::uint32_t *p, std::uint64_t address) {
    p[1] = (p[1] & 3u) | (lo32(address) & 0xFFFFFFFCu);
    p[2] = hi32(address);
}

void set_count14(std::uint32_t *p, std::uint32_t index, std::uint32_t count) {
    p[index] = (p[index] & ~0x3FFFu) | (count & 0x3FFFu);
}

void store64(std::uint32_t *p, std::uint32_t index, std::uint64_t value) {
    p[index] = lo32(value);
    p[index + 1] = hi32(value);
}

// Wait-on-memory sequence: a 4-dword user-data marker (opcode 0x79) then the wait packet.
std::uint32_t *wait_packet(std::uint32_t *sequence) {
    if (packet_size_dwords(sequence[0]) != 4 || opcode_of(sequence) != 0x79) {
        return nullptr;
    }
    std::uint32_t *w = sequence + 4;
    const std::uint8_t op = opcode_of(w);
    return (op == 0x3C || op == 0x93) ? w : nullptr;
}

std::int32_t set_branch_target(std::uint32_t *p, unsigned first, std::uint64_t address,
                               std::uint32_t size_dwords, bool with_policy,
                               std::uint8_t cache_policy) {
    if (opcode_of(p) != 0x3F) {
        return kErrWrongPacket;
    }
    p[first] = (p[first] & 3u) | (lo32(address) & ~3u);
    p[first + 1] = hi32(address);
    if (with_policy) {
        p[first + 2] = (p[first + 2] & 0xCFF00000u) |
                       ((static_cast<std::uint32_t>(cache_policy) & 3u) << 28) |
                       (size_dwords & 0xFFFFFu);
    } else {
        p[first + 2] = (p[first + 2] & 0xFFF00000u) | (size_dwords & 0xFFFFFu);
    }
    return kOk;
}

} // namespace

// ---- branch / jump ------------------------------------------------------------------------------

std::int32_t sceAgcBranchPatchSetThenTarget(std::uint32_t *packet, std::uint64_t then_address,
                                            std::uint32_t then_size_dwords) {
    return set_branch_target(packet, 8, then_address, then_size_dwords, false, 0);
}

std::int32_t sceAgcBranchPatchSetElseTarget(std::uint32_t *packet, std::uint64_t else_address,
                                            std::uint32_t else_size_dwords) {
    return set_branch_target(packet, 11, else_address, else_size_dwords, false, 0);
}

std::int32_t agcBranchPatchSetThenTargetEx(std::uint32_t *packet, std::uint8_t cache_policy,
                                           std::uint64_t then_address,
                                           std::uint32_t then_size_dwords) {
    return set_branch_target(packet, 8, then_address, then_size_dwords, true, cache_policy);
}

std::int32_t agcBranchPatchSetElseTargetEx(std::uint32_t *packet, std::uint8_t cache_policy,
                                           std::uint64_t else_address,
                                           std::uint32_t else_size_dwords) {
    return set_branch_target(packet, 11, else_address, else_size_dwords, true, cache_policy);
}

std::int32_t sceAgcBranchPatchSetCompareAddress(std::uint32_t *packet, std::uint64_t address) {
    if (opcode_of(packet) != 0x3F) {
        return kErrWrongPacket;
    }
    packet[2] = (packet[2] & 7u) | (lo32(address) & 0xFFFFFFF8u);
    packet[3] = hi32(address);
    return kOk;
}

std::int32_t sceAgcJumpPatchSetTarget(std::uint32_t *packet, std::uint64_t target_address,
                                      std::uint32_t size_dwords) {
    return set_branch_target(packet, 1, target_address, size_dwords, false, 0);
}

std::int32_t agcJumpPatchSetTargetEx(std::uint32_t *packet, std::uint8_t mode,
                                     std::uint64_t target_address, std::uint32_t size_dwords) {
    return set_branch_target(packet, 1, target_address, size_dwords, true, mode);
}

// ---- register loads from memory -----------------------------------------------------------------

namespace {
std::int32_t reg_load_set_address(std::uint32_t *p, std::uint8_t opcode, std::uint64_t address) {
    if (opcode_of(p) != opcode) {
        return kErrWrongPacket;
    }
    set_address_dw12(p, address);
    return kOk;
}
std::int32_t reg_load_set_count(std::uint32_t *p, std::uint8_t opcode, std::uint32_t count) {
    if (opcode_of(p) != opcode) {
        return kErrWrongPacket;
    }
    set_count14(p, 4, count);
    return kOk;
}
std::int32_t reg_load_add(std::uint32_t *p, std::uint8_t opcode, std::int32_t delta) {
    if (opcode_of(p) != opcode) {
        return kErrWrongPacket;
    }
    set_count14(p, 4, (p[4] & 0x3FFFu) + static_cast<std::uint32_t>(delta));
    return kOk;
}
} // namespace

std::int32_t sceAgcSetShRegIndirectPatchSetAddress(std::uint32_t *packet, std::uint64_t address) {
    return reg_load_set_address(packet, 0x63, address);
}
std::int32_t sceAgcSetShRegIndirectPatchSetNumRegisters(std::uint32_t *packet, std::uint32_t num) {
    return reg_load_set_count(packet, 0x63, num);
}
std::int32_t sceAgcSetShRegIndirectPatchAddRegisters(std::uint32_t *packet, std::int32_t delta) {
    return reg_load_add(packet, 0x63, delta);
}
std::int32_t sceAgcSetCxRegIndirectPatchSetAddress(std::uint32_t *packet, std::uint64_t address) {
    return reg_load_set_address(packet, 0x9F, address);
}
std::int32_t sceAgcSetCxRegIndirectPatchSetNumRegisters(std::uint32_t *packet, std::uint32_t num) {
    return reg_load_set_count(packet, 0x9F, num);
}
std::int32_t sceAgcSetCxRegIndirectPatchAddRegisters(std::uint32_t *packet, std::int32_t delta) {
    return reg_load_add(packet, 0x9F, delta);
}
std::int32_t sceAgcSetUcRegIndirectPatchSetAddress(std::uint32_t *packet, std::uint64_t address) {
    return reg_load_set_address(packet, 0x64, address);
}
std::int32_t sceAgcSetUcRegIndirectPatchSetNumRegisters(std::uint32_t *packet, std::uint32_t num) {
    return reg_load_set_count(packet, 0x64, num);
}
std::int32_t sceAgcSetUcRegIndirectPatchAddRegisters(std::uint32_t *packet, std::int32_t delta) {
    return reg_load_add(packet, 0x64, delta);
}

// ---- COND_EXEC / REWIND ---------------------------------------------------------------------------

namespace {
std::int32_t cond_exec_set_end(std::uint32_t *packet, const void *end_of_block) {
    if (opcode_of(packet) != 0x22) {
        return kErrWrongPacket;
    }
    // Only the low 32 bits of both pointers take part.
    const std::uint32_t d = lo32(addr(end_of_block)) - lo32(addr(packet));
    set_count14(packet, 4, (d >> 2) - 5u);
    return kOk;
}
std::int32_t cond_exec_set_address(std::uint32_t *packet, std::uint64_t address) {
    if (opcode_of(packet) != 0x22) {
        return kErrWrongPacket;
    }
    set_address_dw12(packet, address);
    return kOk;
}
std::int32_t rewind_set_state(std::uint32_t *packet, std::uint8_t valid) {
    if (opcode_of(packet) != 0x59) {
        return kErrWrongPacket;
    }
    packet[1] = (packet[1] & 0x7FFFFFFFu) | ((static_cast<std::uint32_t>(valid) & 1u) << 31);
    return kOk;
}
} // namespace

std::int32_t sceAgcCondExecPatchSetEnd(std::uint32_t *packet, const void *end_of_block) {
    return cond_exec_set_end(packet, end_of_block);
}
std::int32_t sceAgcCondExecPatchSetCommandAddress(std::uint32_t *packet, std::uint64_t address) {
    return cond_exec_set_address(packet, address);
}
std::int32_t sceAgcAsyncCondExecPatchSetEnd(std::uint32_t *packet, const void *end_of_block) {
    return cond_exec_set_end(packet, end_of_block);
}
std::int32_t sceAgcAsyncCondExecPatchSetCommandAddress(std::uint32_t *packet, std::uint64_t address) {
    return cond_exec_set_address(packet, address);
}
std::int32_t sceAgcRewindPatchSetRewindState(std::uint32_t *packet, std::uint8_t valid) {
    return rewind_set_state(packet, valid);
}
std::int32_t sceAgcAsyncRewindPatchSetRewindState(std::uint32_t *packet, std::uint8_t valid) {
    return rewind_set_state(packet, valid);
}

// ---- packet utilities -----------------------------------------------------------------------------

std::int32_t sceAgcSetPacketPredication(std::uint32_t *packet, std::int32_t predication) {
    packet[0] = (packet[0] & ~1u) | (predication == 1 ? 1u : 0u);
    return kOk;
}

std::uint32_t sceAgcGetPacketSize(const std::uint32_t *packet) {
    return packet_size_dwords(packet[0]);
}

std::int32_t sceAgcSetNop(std::uint32_t *packet) {
    packet[0] = (packet[0] & 0xFFFF00FFu) | (0x10u << 8);
    return kOk;
}

std::int32_t sceAgcSetRangePredication(std::uint32_t *begin, std::uint32_t *end,
                                       std::uint8_t predication) {
    std::uint32_t *p = begin;
    while (p < end) {
        const std::uint32_t n = packet_size_dwords(p[0]);
        p[0] = (p[0] & ~1u) | (predication == 1 ? 1u : 0u);
        p += n;
    }
    return kOk;
}

std::int32_t sceAgcGetDataPacketPayloadAddress(void **out_payload, const std::uint32_t *packet,
                                               std::int32_t has_sub_header) {
    *out_payload = ptr<void>(addr(packet) + 4u + (has_sub_header != 0 ? 4u : 0u));
    return kOk;
}

std::int32_t agcGetDataPacketPayloadAddressChecked(void **out_payload, const std::uint32_t *packet,
                                                   std::int32_t has_sub_header) {
    if (has_sub_header != 0) {
        *out_payload = ptr<void>(addr(packet + 2));
    } else if (((packet[0] >> 16) & 0x3FFFu) == 0x3FFFu) {
        *out_payload = nullptr;
    } else {
        *out_payload = ptr<void>(addr(packet + 1));
    }
    return kOk;
}

std::int32_t sceAgcGetDataPacketPayloadRange(PayloadRange *out, const std::uint32_t *packet,
                                             std::int32_t has_sub_header) {
    const std::uint32_t count = (packet[0] >> 16) & 0x3FFFu;
    if (has_sub_header != 0) {
        out->begin = ptr<void>(addr(packet + 2));
        out->size_bytes = static_cast<std::uint64_t>(count) * 4u;
    } else if (count == 0x3FFFu) {
        out->begin = nullptr;
        out->size_bytes = 0;
    } else {
        out->begin = ptr<void>(addr(packet + 1));
        out->size_bytes = static_cast<std::uint64_t>(count) * 4u + 4u;
    }
    return kOk;
}

// ---- DMA_DATA -------------------------------------------------------------------------------------

std::int32_t sceAgcDmaDataPatchSetDstAddressOrOffset(std::uint32_t *packet, std::uint64_t dst) {
    if (opcode_of(packet) != 0x50) {
        return kErrWrongPacket;
    }
    store64(packet, 4, dst);
    return kOk;
}

std::int32_t sceAgcDmaDataPatchSetSrcAddressOrOffsetOrImmediate(std::uint32_t *packet,
                                                                std::uint64_t src) {
    if (opcode_of(packet) != 0x50) {
        return kErrWrongPacket;
    }
    store64(packet, 2, src);
    return kOk;
}

// ---- wait on memory -------------------------------------------------------------------------------

std::int32_t sceAgcWaitRegMemPatchAddress(std::uint32_t *sequence, std::uint64_t address) {
    if (packet_size_dwords(sequence[0]) != 4 || opcode_of(sequence) != 0x79) {
        return kErrWrongPacket;
    }
    // The marker is updated before the wait packet is checked (side effect kept).
    sequence[2] = (sequence[2] & 0xFFFF0000u) | (hi32(address) & 0xFFFFu);
    sequence[3] = lo32(address);
    std::uint32_t *w = sequence + 4;
    const std::uint8_t op = opcode_of(w);
    if (op == 0x3C) {
        w[2] = (w[2] & 3u) | (lo32(address) & 0xFFFFFFFCu);
    } else if (op == 0x93) {
        w[2] = (w[2] & 7u) | (lo32(address) & 0xFFFFFFF8u);
    } else {
        return kErrWrongPacket;
    }
    w[3] = (w[3] & 0xFFFC0000u) | (hi32(address) & 0x3FFFFu);
    return kOk;
}

std::int32_t sceAgcWaitRegMemPatchCompareFunction(std::uint32_t *sequence, std::uint8_t func) {
    std::uint32_t *w = wait_packet(sequence);
    if (w == nullptr) {
        return kErrWrongPacket;
    }
    w[1] = (w[1] & ~7u) | (static_cast<std::uint32_t>(func) & 7u);
    return kOk;
}

std::int32_t sceAgcWaitRegMemPatchReference(std::uint32_t *sequence, std::uint32_t reference) {
    std::uint32_t *w = wait_packet(sequence);
    if (w == nullptr) {
        return kErrWrongPacket;
    }
    w[4] = reference;
    return kOk;
}

std::int32_t sceAgcWaitRegMemPatchMask(std::uint32_t *sequence, std::uint32_t mask) {
    std::uint32_t *w = wait_packet(sequence);
    if (w == nullptr) {
        return kErrWrongPacket;
    }
    w[opcode_of(w) == 0x3C ? 5 : 6] = mask;
    return kOk;
}

// ---- end-of-pipe action (RELEASE_MEM) -----------------------------------------------------------

std::int32_t sceAgcQueueEndOfPipeActionPatchAddress(std::uint32_t *packet, std::uint64_t address) {
    if (opcode_of(packet) != 0x49) {
        return kErrWrongPacket;
    }
    if (((packet[2] >> 24) & 7u) == 4u) {
        return kOk;
    }
    packet[3] = (packet[3] & 3u) | (lo32(address) & 0xFFFFFFFCu);
    packet[4] = hi32(address);
    return kOk;
}

std::int32_t sceAgcQueueEndOfPipeActionPatchGcrCntl(std::uint32_t *packet, std::uint32_t gcr_cntl) {
    if (opcode_of(packet) != 0x49) {
        return kErrWrongPacket;
    }
    packet[1] = (packet[1] & ~0x00FFF000u) | ((gcr_cntl & 0xFFFu) << 12);
    return kOk;
}

std::int32_t sceAgcQueueEndOfPipeActionPatchType(std::uint32_t *packet, std::uint8_t event_type) {
    if (opcode_of(packet) != 0x49) {
        return kErrWrongPacket;
    }
    const std::uint32_t ev = event_type;
    packet[1] = (packet[1] & ~0xF3Fu) + 0x500u + ((ev > 0x2Eu ? 1u : 0u) << 8) + (ev & 0x3Fu);
    return kOk;
}

std::int32_t sceAgcQueueEndOfPipeActionPatchData(std::uint32_t *packet, std::uint64_t data) {
    if (opcode_of(packet) != 0x49) {
        return kErrWrongPacket;
    }
    if (((packet[2] >> 29) & 7u) == 5u || ((packet[2] >> 24) & 7u) == 4u) {
        return kOk;
    }
    store64(packet, 5, data);
    return kOk;
}

// ---- ACQUIRE_MEM / WRITE_DATA -------------------------------------------------------------------

std::int32_t sceAgcAcquireMemSetEngine(std::uint32_t *packet, std::uint8_t engine) {
    if (opcode_of(packet) != 0x58) {
        return kErrWrongPacket;
    }
    packet[1] = (packet[1] & 0x7FFFFFFFu) | ((static_cast<std::uint32_t>(engine) & 1u) << 31);
    return kOk;
}

namespace {
std::int32_t write_data_set_address(std::uint32_t *packet, std::uint64_t address) {
    if (opcode_of(packet) != 0x37) {
        return kErrWrongPacket;
    }
    store64(packet, 2, address); // whole 64 bits, no masking
    return kOk;
}
std::int32_t write_data_set_policy(std::uint32_t *packet, std::uint8_t policy) {
    if (opcode_of(packet) != 0x37) {
        return kErrWrongPacket;
    }
    packet[1] = (packet[1] & ~(3u << 25)) | ((static_cast<std::uint32_t>(policy) & 3u) << 25);
    return kOk;
}
} // namespace

std::int32_t agcWriteDataPatchSetAddress(std::uint32_t *packet, std::uint64_t address) {
    return write_data_set_address(packet, address);
}
std::int32_t agcWriteDataPatchSetAddress2(std::uint32_t *packet, std::uint64_t address) {
    return write_data_set_address(packet, address);
}
std::int32_t agcWriteDataPatchSetCachePolicy(std::uint32_t *packet, std::uint8_t policy) {
    return write_data_set_policy(packet, policy);
}
std::int32_t agcWriteDataPatchSetCachePolicy2(std::uint32_t *packet, std::uint8_t policy) {
    return write_data_set_policy(packet, policy);
}

std::int32_t agcWriteDataPatchSetDestination(std::uint32_t *packet, std::uint8_t dest) {
    if (opcode_of(packet) != 0x37) {
        return kErrWrongPacket;
    }
    const std::uint32_t d = dest;
    // Bit 31 is cleared as a side effect (as in the original).
    packet[1] = (packet[1] & 0x3FFFF0FFu) | ((d & 1u) << 30) | (((d >> 1) & 0xFu) << 8);
    return kOk;
}

std::int32_t agcWriteDataPatchSetDstSel(std::uint32_t *packet, std::uint8_t dst_sel) {
    if (opcode_of(packet) != 0x37) {
        return kErrWrongPacket;
    }
    packet[1] = (packet[1] & ~0xF00u) | ((static_cast<std::uint32_t>(dst_sel) & 0xFu) << 8);
    return kOk;
}

} // namespace bc5::reimpl::agc
