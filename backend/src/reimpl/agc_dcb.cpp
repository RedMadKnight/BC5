// SPDX-License-Identifier: GPL-2.0-only
// Clean-room re-creation of libSceAgc (see src/reimpl/PROVENANCE.md): the sceAgcDcb* builders
// (graphics queue), the context-state operations and the queue-reset sequence.
//
// Packet layouts are per the original module's behaviour (clean-room description, see
// src/reimpl/PROVENANCE.md). Opcode names in comments are from Mesa src/amd/common/sid.h
// (commit ab2374a): PKT3_SET_BASE 0x11, PKT3_CLEAR_STATE 0x12, PKT3_INDEX_BUFFER_SIZE 0x13,
// PKT3_SET_PREDICATION 0x20, PKT3_DRAW_INDIRECT 0x24, PKT3_DRAW_INDEX_INDIRECT 0x25,
// PKT3_INDEX_BASE 0x26, PKT3_DRAW_INDEX_2 0x27, PKT3_CONTEXT_CONTROL 0x28,
// PKT3_DRAW_INDIRECT_MULTI 0x2C, PKT3_DRAW_INDEX_AUTO 0x2D, PKT3_NUM_INSTANCES 0x2F,
// PKT3_DRAW_INDEX_OFFSET_2 0x35, PKT3_DRAW_INDEX_INDIRECT_MULTI 0x38, PKT3_PFP_SYNC_ME 0x42,
// PKT3_SET_CONFIG_REG 0x68, PKT3_SET_CONTEXT_REG 0x69, PKT3_SET_UCONFIG_REG_INDEX 0x7A.
// The register-load opcodes 0x63 / 0x64 / 0x9F, 0x3A, 0x8E and 0x91 are TODO(verify) names.
#include "bc5/reimpl/agc_internal.hpp"

#include "bc5/reg_catch.hpp" // BC5: the register catcher for the slot's own lists

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <functional>

namespace bc5::reimpl::agc {

using namespace detail;

namespace {

std::uint32_t *set_one(CommandBuffer *cb, std::uint32_t header, RegPair reg) {
    const std::uint32_t d[3] = {header, reg.offset & 0xFFFFu, reg.value};
    return emit(cb, d, 3);
}

std::uint32_t *indirect_load(CommandBuffer *cb, std::uint32_t header, std::uint64_t address,
                             std::uint32_t count) {
    const std::uint32_t d[5] = {header, lo32(address) & ~3u, hi32(address), 0x80000000u,
                                count & 0x3FFFu};
    return emit(cb, d, 5);
}

// BC5 (run rmplN01, 2026-11-21): the slot's default tables are register lists the CP reads from
// memory, out of the host filter's sight. With the register catcher on (bc5/reg_catch.hpp, switch
// BC5_REG_CATCH) each list is checked before its load packet is built: every
// offset inside its space. "fatal" ends the process with exit 87.
std::uint32_t *slot_load(CommandBuffer *cb, std::uint32_t header, std::uint64_t address,
                         std::uint32_t count, const char *what) {
    const bc5::reg_catch::Mode m = bc5::reg_catch::mode();
    if (m != bc5::reg_catch::Mode::Off && count != 0) {
        const std::uint32_t pkt[5] = {header, lo32(address) & ~3u, hi32(address), 0x80000000u,
                                      count & 0x3FFFu};
        const std::function<bool(std::uint64_t, std::uint64_t)> mapped =
            [](std::uint64_t, std::uint64_t) { return true; }; // our own DMEM, in this process
        const bc5::reg_catch::Finding f = bc5::reg_catch::check(pkt, 5, mapped);
        if (f.reason != nullptr) {
            log(kModule, "REG-CATCH slot %s list: %s (pair %u, offset 0x%x)", what, f.reason,
                f.index, f.reg);
            if (m == bc5::reg_catch::Mode::Fatal) {
                std::fflush(stderr);
                std::_Exit(87);
            }
        }
    }
    return indirect_load(cb, header, address, count);
}

std::uint32_t uc_load_header() {
    return soc_class() == kSocA ? 0xC0036800u : 0xC0036400u;
}

// Draw modifier (64-bit) decoding.
std::uint32_t stage_base(std::uint64_t modifier) {
    const auto sel = static_cast<std::uint32_t>((modifier >> 29) & 7u);
    return (sel == 3 || sel == 5) ? 0x10Cu : 0x08Cu;
}
std::uint32_t location(std::uint64_t modifier, unsigned present_bit, unsigned slot_shift) {
    if (((modifier >> present_bit) & 1u) == 0) {
        return 0x280u;
    }
    return stage_base(modifier) + static_cast<std::uint32_t>((modifier >> slot_shift) & 0x1Fu);
}
std::uint32_t bit5(std::uint64_t modifier) {
    return ((modifier >> 32) & 1u) != 0 ? 0u : static_cast<std::uint32_t>((modifier >> 3) & 0x20u);
}
std::uint32_t mbit(std::uint64_t modifier, unsigned bit) {
    return static_cast<std::uint32_t>((modifier >> bit) & 1u);
}

std::uint32_t *multi_draw(CommandBuffer *cb, std::uint32_t begin_id, const std::uint32_t *packet,
                          std::uint32_t n) {
    if (g_imports.ud_get_packet_size == nullptr || g_imports.ud_write_packet == nullptr) {
        return nullptr;
    }
    const std::uint32_t e = g_imports.ud_get_packet_size(0);
    if (!reserve_soft(cb, 2u * e + n)) {
        return nullptr;
    }
    std::uint32_t *start = write_user_data(cb, 0, begin_id, nullptr, 0);
    emit_raw(cb, packet, n);
    write_user_data(cb, 0, 0xC6000000u, nullptr, 0);
    return start;
}

const std::uint32_t kContextControl1[3] = {0xC0012800u, 0u, 0x80018001u};
const std::uint32_t kContextControl2[3] = {0xC0012800u, 0u, 0x80018003u};

} // namespace

// ---- helpers H8 / H9 / H10 --------------------------------------------------------------------

namespace detail {

std::uint32_t *emit_load_cx_defaults(CommandBuffer *cb, const QueueSlot *slot) {
    if (slot == nullptr) {
        return nullptr; // deviation: UB in the original (no active slot)
    }
    return slot_load(cb, 0xC0039F00u, addr(slot->cx), slot->cx_count, "cx");
}

std::uint32_t *conditional_roll_notify(CommandBuffer *cb, std::uint32_t op, bool update_label) {
    if (op == 0) {
        return nullptr;
    }
    const bool full = op == 1 || op == 3;
    if (!ensure_space(cb, 22)) {
        return nullptr;
    }
    const std::uint64_t label = state().sync_label;
    std::uint32_t *r = sceAgcDcbCondExec(cb, label + (full ? 0u : 4u), 8);
    if (std::uint32_t *rm = sceAgcCbReleaseMem(cb, 0x28, 0, 1, 3, 0, 0, 0, 0, 0, 4, 0);
        rm != nullptr) {
        // Interrupt context id tags the roll for the driver.
        rm[7] = (rm[7] & 0xF0000000u) | (0x08100000u + (op & 0xFFFFFu));
    }
    if (update_label) {
        sceAgcDcbAtomicMem(cb, 1, 0x67, 2, 0, label, full ? 1ull : 0x100000000ull, 0, 400);
    }
    return r;
}

std::uint32_t *conditional_clear_state(CommandBuffer *cb) {
    if (!ensure_space(cb, 16)) {
        return nullptr;
    }
    const std::uint64_t label = state().sync_label;
    std::uint32_t *r = sceAgcDcbCondExec(cb, label, 11);
    sceAgcDcbClearState(cb, 2);
    sceAgcDcbAtomicMem(cb, 1, 0x67, 2, 0, label, 0x100000000ull, 0, 400);
    return r;
}

std::uint32_t *dcb_reset_queue_body(CommandBuffer *cb, std::uint16_t flags, QueueSlot *slot,
                                    bool trusted) {
    if ((flags & 0x8000u) != 0) {
        slot = active_slot();
    }
    if (slot == nullptr) {
        return nullptr; // deviation: UB in the original (NULL slot dereferenced)
    }
    if (g_imports.ud_get_packet_size == nullptr || g_imports.ud_write_packet == nullptr) {
        return nullptr;
    }
    std::uint32_t *r = sceAgcCbNop(cb, 1);
    if (r == nullptr) {
        return nullptr;
    }
    const std::uint32_t id = 0xCE000000u | ((trusted ? 0u : 1u) << 22) |
                             ((slot->trusted != 0 ? 0u : 1u) << 21) | flags;
    if (!reserve_soft(cb, g_imports.ud_get_packet_size(4))) {
        return nullptr;
    }
    write_user_data(cb, 0, id, &slot->version, 4);
    if ((flags & 0x80u) != 0) {
        const std::uint32_t d[2] = {0xC0004600u, 0x407u};
        if (emit(cb, d, 2) == nullptr) {
            return nullptr;
        }
    }
    if ((flags & 0x100u) != 0) {
        const std::uint32_t d[2] = {0xC0004600u, 0x410u};
        if (emit(cb, d, 2) == nullptr) {
            return nullptr;
        }
    }
    if ((flags & 0x400u) != 0) {
        conditional_clear_state(cb); // result not checked (as in the original)
    }
    if ((flags & 1u) != 0) {
        if (state().use_clear_state_for_cx == 0) {
            if (emit_load_cx_defaults(cb, slot) == nullptr) {
                return nullptr;
            }
        } else {
            const std::uint32_t d[2] = {0xC0001200u, 0u};
            if (emit(cb, d, 2) == nullptr) {
                return nullptr;
            }
        }
    }
    if ((flags & 2u) != 0) {
        if (slot_load(cb, 0xC0036300u, addr(slot->sh), slot->sh_count, "sh") == nullptr) {
            return nullptr;
        }
    }
    const bool uc_main = (flags & 4u) != 0;
    const bool uc_special = (flags & 0x800u) != 0;
    if (uc_main || uc_special) {
        std::uint64_t a = addr(slot->uc);
        std::uint32_t count = slot->uc_count;
        if (uc_main && !uc_special) {
            count = slot->uc_count - slot->uc_special_count;
        } else if (!uc_main) {
            a += 8ull * (slot->uc_count - slot->uc_special_count);
            count = slot->uc_special_count;
        }
        if (slot_load(cb, uc_load_header(), a, count, "uc") == nullptr) {
            return nullptr;
        }
    }
    if ((flags & 8u) != 0) {
        const std::uint32_t d[2] = {0xC0002F00u, 1u};
        if (emit(cb, d, 2) == nullptr) {
            return nullptr;
        }
    }
    if ((flags & 0x10u) != 0) {
        const std::uint32_t a[3] = {0xC0017A00u, 0x20000243u, 0x480u};
        const std::uint32_t b[3] = {0xC0012600u, 0u, 0u};
        if (emit(cb, a, 3) == nullptr || emit(cb, b, 3) == nullptr ||
            sceAgcDcbSetIndexCount(cb, 0xFFFFFFFFu) == nullptr) {
            return nullptr;
        }
    }
    if ((flags & 0x20u) != 0) {
        if (sceAgcDcbSetBaseIndirectArgs(cb, 1, 0) == nullptr ||
            sceAgcDcbSetBaseIndirectArgs(cb, 0, 0) == nullptr) {
            return nullptr;
        }
    }
    if ((flags & 0x40u) != 0) {
        if (sceAgcDcbAcquireMem(cb, 1, 0x06007FC0u, 0xC3E1u, 0, 0xFFFFFFFFFFFFFFFFull, 400) ==
                nullptr ||
            sceAgcDcbEventWrite(cb, 0x2E, 0) == nullptr ||
            sceAgcDcbEventWrite(cb, 0x2C, 0) == nullptr) {
            return nullptr;
        }
    }
    if ((flags & 0x200u) != 0) {
        if (sceAgcDcbEventWrite(cb, 0x38, 0x7FFFC00u) == nullptr) {
            return nullptr;
        }
    }
    if (!ensure_space(cb, g_imports.ud_get_packet_size(0))) {
        return nullptr;
    }
    write_user_data(cb, 0, (id & 0xCF600000u) | 0xCE800000u, nullptr, 0);
    return r;
}

} // namespace detail

// ---- register writes ----------------------------------------------------------------------------

std::uint32_t *sceAgcDcbSetCxRegisterDirect(CommandBuffer *cb, RegPair reg) {
    return set_one(cb, 0xC0016900u, reg);
}
std::uint32_t *sceAgcDcbSetCfRegisterDirect(CommandBuffer *cb, RegPair reg) {
    return set_one(cb, 0xC0016800u, reg);
}
std::uint32_t *sceAgcDcbSetUcRegisterDirect(CommandBuffer *cb, RegPair reg) {
    return set_one(cb, 0xC0017900u, reg);
}
std::uint32_t *sceAgcDcbSetShRegisterDirect(CommandBuffer *cb, RegPair reg) {
    return set_one(cb, 0xC0017600u, reg);
}

std::uint32_t *sceAgcDcbSetCxRegistersIndirect(CommandBuffer *cb, std::uint64_t pairs_address,
                                               std::uint32_t num_regs) {
    return indirect_load(cb, 0xC0039F00u, pairs_address, num_regs);
}
std::uint32_t *sceAgcDcbSetShRegistersIndirect(CommandBuffer *cb, std::uint64_t pairs_address,
                                               std::uint32_t num_regs) {
    return indirect_load(cb, 0xC0036300u, pairs_address, num_regs);
}
std::uint32_t *sceAgcDcbSetUcRegistersIndirect(CommandBuffer *cb, std::uint64_t pairs_address,
                                               std::uint32_t num_regs) {
    return indirect_load(cb, uc_load_header(), pairs_address, num_regs);
}

std::uint32_t *sceAgcDcbSetCfRegisterRangeDirect(CommandBuffer *cb, std::uint32_t start_offset,
                                                 const std::uint32_t *values, std::uint32_t count) {
    if (values == nullptr) {
        return nullptr; // deviation: UB in the original (values[0] is always read)
    }
    if (!reserve_soft(cb, count + 2u)) {
        return nullptr;
    }
    std::uint32_t *p = reserve_strict(cb, 3);
    if (p == nullptr) {
        return nullptr;
    }
    p[0] = 0xC0006800u | (count << 16);
    p[1] = start_offset & 0xFFFFu;
    p[2] = values[0];
    if (count >= 2) {
        if (std::uint32_t *q = reserve_strict(cb, count - 1u); q != nullptr) {
            copy_bytes(q, values + 1, 4ull * (count - 1u));
        }
    }
    return p;
}

// ---- memory / sync ------------------------------------------------------------------------------

std::uint32_t *sceAgcDcbAcquireMem(CommandBuffer *cb, std::uint8_t engine, std::uint32_t coher_control,
                                   std::uint32_t gcr_control, std::uint64_t base_address,
                                   std::uint64_t size_bytes, std::uint32_t poll_cycles) {
    std::uint32_t g = gcr_control;
    if ((g & 0xC000u) == 0x4000u) {
        g |= 0x8000u;
    }
    const std::uint64_t t = (((base_address & 0xFFu) + size_bytes) & 0xFFFFFFFFFFFFull) + 0xFFu;
    const std::uint64_t sz = std::min<std::uint64_t>(t, 0xFFFFFFFFFF00ull - base_address);
    std::uint64_t range = sz >> 8;
    const std::uint32_t poll = std::min<std::uint32_t>(poll_cycles >> 4, 0xFFFFu);
    const std::uint32_t w = state().workaround_mask;
    const std::uint32_t eng = static_cast<std::uint32_t>(engine) << 31;
    std::uint32_t coher = coher_control;
    std::uint32_t *extra = nullptr;
    if ((w & 1u) != 0 && (g & 0x108u) == 0x108u && (g & 0x2A0u) != 0) {
        const std::uint32_t x[8] = {0xC0065800u,
                                    eng | (coher & 0x06007FC0u),
                                    static_cast<std::uint32_t>(range),
                                    static_cast<std::uint32_t>(range >> 32) & 0xFFu,
                                    static_cast<std::uint32_t>(base_address >> 8),
                                    static_cast<std::uint32_t>(base_address >> 40),
                                    poll,
                                    0x100u};
        extra = emit(cb, x, 8);
        if (extra == nullptr) {
            return nullptr;
        }
        g &= ~0x100u;
        coher = 0;
    } else {
        if ((w & 1u) != 0 && (g & 0x108u) == 0x108u) {
            g &= 0xFFFFFD53u;
        } else if ((w & 1u) == 0 && (w & 2u) != 0 && (g & 0x108u) == 0x108u) {
            g &= ~0xCu;
        }
        if ((coher & 0x4000000u) != 0) {
            // "Whole memory" mode.
            coher |= 0x4000u;
            range = 0xFFFFFFFFFEull;
            base_address = 0x100;
            std::uint32_t g2 = g & ~8u;
            if ((g & 2u) != 0) {
                g2 = (g & 0xFFFFFFF4u) | 1u;
            }
            if ((g2 & 0x1000u) != 0) {
                g2 &= 0xFFFFEFF7u;
            }
            g = g2;
        }
    }
    const std::uint32_t d[8] = {0xC0065800u,
                                eng | (coher & 0x06007FC0u),
                                static_cast<std::uint32_t>(range),
                                static_cast<std::uint32_t>(range >> 32) & 0xFFu,
                                static_cast<std::uint32_t>(base_address >> 8),
                                static_cast<std::uint32_t>(base_address >> 40),
                                poll,
                                g & 0x7FFFFu};
    std::uint32_t *main_packet = emit(cb, d, 8);
    if (main_packet == nullptr) {
        return nullptr;
    }
    return extra != nullptr ? extra : main_packet;
}

std::uint32_t *sceAgcDcbAtomicMem(CommandBuffer *cb, std::int32_t engine, std::uint32_t atomic_op,
                                  std::uint32_t command, std::uint8_t cache_policy,
                                  std::uint64_t address, std::uint64_t src_data,
                                  std::uint64_t cmp_data, std::uint32_t loop_interval) {
    const std::uint32_t d[9] = {0xC0071E00u,
                                (static_cast<std::uint32_t>(engine) << 30) |
                                    ((static_cast<std::uint32_t>(cache_policy) & 3u) << 25) |
                                    ((command & 0xFu) << 8) | (atomic_op & 0x7Fu),
                                lo32(address),
                                hi32(address),
                                lo32(src_data),
                                hi32(src_data),
                                lo32(cmp_data),
                                hi32(cmp_data),
                                std::min<std::uint32_t>(loop_interval >> 6, 0xFFFu)};
    return emit(cb, d, 9);
}

std::uint32_t *sceAgcDcbClearState(CommandBuffer *cb, std::uint32_t op) {
    const std::uint32_t d[2] = {0xC0001200u, op & 0xFu};
    return emit(cb, d, 2);
}

std::uint32_t *sceAgcDcbContextStateOp(CommandBuffer *cb, std::uint32_t op) {
    switch (op) {
    case 0:
        return emit_load_cx_defaults(cb, active_slot());
    case 1:
    case 2:
    case 3: {
        std::uint32_t *r = emit(cb, op == 2 ? kContextControl2 : kContextControl1, 3);
        if (r == nullptr) {
            return nullptr;
        }
        const std::uint32_t ucs = state().use_clear_state_for_cx;
        const std::uint32_t arg = op == 3 ? (ucs != 0 ? 3u : 1u) : op;
        if (sceAgcDcbClearState(cb, arg) == nullptr) {
            return nullptr;
        }
        if (op == 3 && ucs == 0 && emit_load_cx_defaults(cb, active_slot()) == nullptr) {
            return nullptr;
        }
        return r;
    }
    default:
        sceAgcDcbClearState(cb, op & 0xFu);
        return nullptr;
    }
}

std::uint32_t *agcDcbContextStateOpNotify(CommandBuffer *cb, std::uint64_t op64) {
    const auto op = static_cast<std::uint32_t>(op64);
    switch (op) {
    case 0:
        return emit_load_cx_defaults(cb, active_slot());
    case 1:
    case 3: {
        std::uint32_t *r = conditional_roll_notify(cb, op, true);
        if (r == nullptr || emit(cb, kContextControl1, 3) == nullptr) {
            return nullptr;
        }
        const std::uint32_t ucs = state().use_clear_state_for_cx;
        const std::uint32_t arg = op == 3 ? (ucs != 0 ? 3u : 1u) : 1u;
        if (sceAgcDcbClearState(cb, arg) == nullptr) {
            return nullptr;
        }
        if (op == 3 && ucs == 0 && emit_load_cx_defaults(cb, active_slot()) == nullptr) {
            return nullptr;
        }
        return r;
    }
    case 2: {
        std::uint32_t *r = emit(cb, kContextControl2, 3);
        if (r == nullptr || conditional_roll_notify(cb, 2, true) == nullptr ||
            sceAgcDcbClearState(cb, 2) == nullptr) {
            return nullptr;
        }
        return r;
    }
    default:
        sceAgcDcbClearState(cb, op & 0xFu);
        return nullptr;
    }
}

std::uint32_t *sceAgcDcbCondExec(CommandBuffer *cb, std::uint64_t condition_address,
                                 std::uint32_t num_dwords) {
    return sceAgcAcbCondExec(cb, condition_address, num_dwords);
}

std::uint32_t *sceAgcDcbJump(CommandBuffer *cb, std::uint32_t chain, std::uint8_t cache_policy,
                             std::uint64_t target_address, std::uint32_t size_dwords) {
    const std::uint32_t d[4] = {
        0xC0023F00u, lo32(target_address) & ~3u, hi32(target_address),
        ((chain & 1u) << 20) + 0x0F200000u +
            (((static_cast<std::uint32_t>(cache_policy) & 3u) << 28) | (size_dwords & 0xFFFFFu))};
    return emit(cb, d, 4);
}

std::uint32_t *sceAgcDcbCopyData(CommandBuffer *cb, std::uint8_t dst_sel_enc,
                                 std::uint8_t dst_cache_policy, std::uint64_t dst_address,
                                 std::uint32_t src_sel_enc, std::uint32_t src_cache_policy,
                                 std::uint64_t src_address_or_data, std::uint8_t count_sel,
                                 std::uint8_t write_confirm) {
    const std::uint32_t d[6] = {
        0xC0044000u,
        ((src_sel_enc & 1u) << 30) | ((static_cast<std::uint32_t>(dst_cache_policy) & 3u) << 25) |
            ((static_cast<std::uint32_t>(write_confirm) & 1u) << 20) |
            ((static_cast<std::uint32_t>(count_sel) & 1u) << 16) |
            ((src_cache_policy & 3u) << 13) |
            (((static_cast<std::uint32_t>(dst_sel_enc) >> 1) & 0xFu) << 8) |
            ((src_sel_enc >> 1) & 0xFu),
        lo32(src_address_or_data),
        hi32(src_address_or_data),
        lo32(dst_address),
        hi32(dst_address)};
    return emit(cb, d, 6);
}

std::uint32_t *sceAgcDcbDmaData(CommandBuffer *cb, std::uint8_t engine, std::uint32_t dst_sel,
                                std::uint8_t dst_cache_policy, std::uint64_t dst_address,
                                std::uint32_t src_sel, std::uint8_t src_cache_policy,
                                std::uint64_t src_address_or_data, std::uint32_t byte_count,
                                std::uint8_t flag30, std::uint8_t flag31, std::uint8_t cp_sync) {
    std::uint64_t src = src_address_or_data;
    const bool e1 = engine == 1;
    if (src_sel == 100) {
        src = e1 ? 0x30158u : 0x30184u;
    } else if (src_sel == 0x24) {
        src = e1 ? 0x30150u : 0x3017Cu;
    } else if (src_sel == 0x14) {
        src = e1 ? 0x30148u : 0x30174u;
    }
    const std::uint32_t d[7] = {
        0xC0055000u,
        ((src_sel & 3u) << 29) | ((static_cast<std::uint32_t>(dst_cache_policy) & 3u) << 25) |
            ((dst_sel & 3u) << 20) | ((static_cast<std::uint32_t>(src_cache_policy) & 3u) << 13) |
            (static_cast<std::uint32_t>(engine) & 1u) | (static_cast<std::uint32_t>(cp_sync) << 31),
        lo32(src),
        hi32(src),
        lo32(dst_address),
        hi32(dst_address),
        (static_cast<std::uint32_t>(flag31) << 31) |
            ((static_cast<std::uint32_t>(flag30) & 1u) << 30) | ((dst_sel & 8u) << 26) |
            ((dst_sel & 4u) << 25) | ((src_sel & 8u) << 25) | ((src_sel & 4u) << 24) |
            (byte_count & 0x3FFFFFFu)};
    return emit(cb, d, 7);
}

std::uint32_t *sceAgcDcbWriteData(CommandBuffer *cb, std::uint32_t dst_sel_enc,
                                  std::uint8_t cache_policy, std::uint64_t dst_address,
                                  const std::uint32_t *data, std::uint32_t num_dwords,
                                  std::uint8_t write_one_address, std::uint8_t write_confirm) {
    const std::uint32_t confirm = static_cast<std::uint8_t>(dst_sel_enc) != 0
                                      ? (static_cast<std::uint32_t>(write_confirm) & 1u)
                                      : 0u;
    const std::uint32_t control = ((dst_sel_enc & 1u) << 30) |
                                  ((static_cast<std::uint32_t>(cache_policy) & 3u) << 25) |
                                  (confirm << 20) |
                                  ((static_cast<std::uint32_t>(write_one_address) & 1u) << 16) |
                                  ((dst_sel_enc & 0x1Eu) << 7);
    return write_data(cb, control, lo32(dst_address) & ~3u, hi32(dst_address), data, num_dwords);
}

// ---- draws and dispatch -------------------------------------------------------------------------

std::uint32_t *sceAgcDcbDispatchIndirect(CommandBuffer *cb, std::uint32_t args_offset,
                                         std::uint32_t initiator_flags) {
    const std::uint32_t d[3] = {0xC0011600u, args_offset,
                                (initiator_flags & 0xA038u) | state().trace_initiator[10] | 0x41u};
    return emit(cb, d, 3);
}

std::uint32_t *sceAgcDcbDrawIndexAuto(CommandBuffer *cb, std::uint32_t vertex_count,
                                      std::uint64_t modifier) {
    const std::uint32_t d[3] = {0xC0012D00u, vertex_count,
                                2u | bit5(modifier) | state().trace_initiator[2]};
    return emit(cb, d, 3);
}

std::uint32_t *sceAgcDcbDrawIndex(CommandBuffer *cb, std::uint32_t index_count,
                                  std::uint64_t index_address, std::uint64_t modifier) {
    const std::uint32_t d[6] = {0xC0042700u,
                                std::max<std::uint32_t>(index_count, 1u),
                                lo32(index_address),
                                hi32(index_address),
                                index_count,
                                bit5(modifier) | state().trace_initiator[1]};
    return emit(cb, d, 6);
}

std::uint32_t *sceAgcDcbDrawIndexOffset(CommandBuffer *cb, std::uint32_t index_offset,
                                        std::uint32_t index_count, std::uint64_t modifier) {
    const std::uint32_t d[5] = {0xC0033500u, std::max<std::uint32_t>(index_count, 1u), index_offset,
                                index_count, bit5(modifier) | state().trace_initiator[3]};
    return emit(cb, d, 5);
}

std::uint32_t *sceAgcDcbDrawIndirect(CommandBuffer *cb, std::uint32_t args_offset,
                                     std::uint64_t modifier) {
    const std::uint32_t d[5] = {0xC0032400u, args_offset, location(modifier, 0, 9),
                                location(modifier, 2, 19),
                                2u | bit5(modifier) | state().trace_initiator[7]};
    return emit(cb, d, 5);
}

std::uint32_t *sceAgcDcbDrawIndirectMulti(CommandBuffer *cb, std::uint32_t args_offset,
                                          std::uint8_t count_indirect_enable, std::uint32_t max_count,
                                          std::uint64_t count_address, std::uint32_t stride,
                                          std::uint64_t modifier) {
    const std::uint32_t d[10] = {
        0xC0082C00u,
        args_offset,
        location(modifier, 0, 9),
        location(modifier, 2, 19),
        (mbit(modifier, 3) << 31) | ((static_cast<std::uint32_t>(count_indirect_enable) & 1u) << 30) |
            (mbit(modifier, 4) << 27) | location(modifier, 3, 24),
        max_count,
        lo32(count_address) & ~3u,
        hi32(count_address),
        stride,
        2u | bit5(modifier) | state().trace_initiator[8]};
    return multi_draw(cb, 0xC6000008u, d, 10);
}

std::uint32_t *sceAgcDcbDrawIndexIndirectMulti(CommandBuffer *cb, std::uint32_t args_offset,
                                               std::uint8_t count_indirect_enable,
                                               std::uint32_t max_count,
                                               std::uint64_t count_address, std::uint32_t stride,
                                               std::uint64_t modifier) {
    const std::uint32_t draw_index =
        mbit(modifier, 1) != 0 ? (stage_base(modifier) +
                                  static_cast<std::uint32_t>((modifier >> 14) & 0x1Fu))
                                     << 16
                               : 0u;
    const std::uint32_t d[10] = {
        0xC0083800u,
        args_offset,
        location(modifier, 0, 9) | draw_index,
        location(modifier, 2, 19),
        (mbit(modifier, 3) << 31) | ((static_cast<std::uint32_t>(count_indirect_enable) & 1u) << 30) |
            (mbit(modifier, 1) << 28) | (mbit(modifier, 4) << 27) | location(modifier, 3, 24),
        max_count,
        lo32(count_address) & ~3u,
        hi32(count_address),
        stride,
        bit5(modifier) | state().trace_initiator[5]};
    return multi_draw(cb, 0xC6000005u, d, 10);
}

std::uint32_t *sceAgcDcbDrawIndexIndirect(CommandBuffer *cb, std::uint32_t args_offset,
                                          std::uint64_t modifier) {
    const std::uint32_t draw_index =
        mbit(modifier, 1) != 0 ? (stage_base(modifier) +
                                  static_cast<std::uint32_t>((modifier >> 14) & 0x1Fu))
                                     << 16
                               : 0u;
    const std::uint32_t d[5] = {0xC0032500u, args_offset, location(modifier, 0, 9) | draw_index,
                                location(modifier, 2, 19) | (mbit(modifier, 1) << 28),
                                bit5(modifier) | state().trace_initiator[4]};
    return emit(cb, d, 5);
}

std::uint32_t *sceAgcDcbDrawIndexMultiInstanced(CommandBuffer *cb, std::uint32_t arg0,
                                                std::uint64_t index_address,
                                                std::uint64_t instance_data_address,
                                                std::uint32_t index_count, std::uint64_t modifier) {
    const std::uint32_t d[9] = {0xC0073A00u,
                                arg0,
                                lo32(index_address),
                                hi32(index_address),
                                std::max<std::uint32_t>(index_count, 1u),
                                lo32(instance_data_address),
                                hi32(instance_data_address),
                                index_count,
                                0x80u | bit5(modifier) | state().trace_initiator[6]};
    return multi_draw(cb, 0xC6000006u, d, 9);
}

std::uint32_t *sceAgcDcbEventWrite(CommandBuffer *cb, std::uint32_t event_type, std::uint64_t address) {
    const std::uint32_t n = (event_type & 0xFEu) == 0x38u ? 4u : 2u;
    std::uint32_t d[4] = {0xC0004600u | ((n - 2u) << 16), 0, 0, 0};
    if (event_type == 7 || event_type == 15 || event_type == 16) {
        d[1] = (event_type & 0xFFu) | 0x400u;
    } else if (event_type == 0x38 || event_type == 0x39) {
        d[1] = (event_type & 0xFFu) | 0x100u;
    } else {
        d[1] = event_type & 0x3Fu;
    }
    if (n == 4) {
        d[2] = lo32(address) & ~7u;
        d[3] = hi32(address);
    }
    return emit(cb, d, n);
}

std::uint32_t *sceAgcDcbGetLodStats(CommandBuffer *cb, std::uint8_t cache_policy,
                                    std::uint64_t out_address, std::uint32_t arg0,
                                    std::uint32_t field_a, std::uint32_t flag_b, std::uint8_t flag_c,
                                    std::uint32_t field_d) {
    const std::uint32_t d[5] = {0xC0038E00u, arg0, lo32(out_address) & ~0x3Fu, hi32(out_address),
                                ((static_cast<std::uint32_t>(cache_policy) & 3u) << 28) |
                                    ((static_cast<std::uint32_t>(flag_c) & 1u) << 19) |
                                    ((flag_b & 1u) << 18) | ((field_a & 0xFFu) << 10) |
                                    ((field_d & 0xFFu) << 2)};
    return emit(cb, d, 5);
}

// ---- index state --------------------------------------------------------------------------------

std::uint32_t *sceAgcDcbSetBaseIndirectArgs(CommandBuffer *cb, std::int32_t compute,
                                            std::uint64_t base_address) {
    const std::uint32_t d[4] = {0xC0021100u | (static_cast<std::uint32_t>(compute) << 1), 1u,
                                lo32(base_address) & ~7u, hi32(base_address)};
    return emit(cb, d, 4);
}

std::uint32_t *sceAgcDcbSetIndexSize(CommandBuffer *cb, std::uint8_t index_size,
                                     std::uint8_t cache_policy) {
    const std::uint32_t d[3] = {
        0xC0017A00u, 0x20000243u,
        0x400u | static_cast<std::uint8_t>((static_cast<std::uint32_t>(index_size) & 3u) |
                                           (static_cast<std::uint32_t>(cache_policy) << 6))};
    return emit(cb, d, 3);
}

std::uint32_t *agcDcbSetIndexSizeEx(CommandBuffer *cb, std::uint8_t index_size,
                                    std::uint8_t cache_policy, std::uint32_t extra_flag) {
    const std::uint32_t d[3] = {
        0xC0017A00u, 0x20000243u,
        0x400u + (extra_flag & 1u) * 0x4000u +
            static_cast<std::uint8_t>((static_cast<std::uint32_t>(index_size) & 3u) |
                                      (static_cast<std::uint32_t>(cache_policy) << 6))};
    return emit(cb, d, 3);
}

std::uint32_t *sceAgcDcbSetIndexBuffer(CommandBuffer *cb, std::uint64_t index_address) {
    const std::uint32_t d[3] = {0xC0012600u, lo32(index_address) & ~1u, hi32(index_address)};
    return emit(cb, d, 3);
}

std::uint32_t *sceAgcDcbSetIndexCount(CommandBuffer *cb, std::uint32_t index_count) {
    const std::uint32_t d[2] = {0xC0001300u, std::max<std::uint32_t>(index_count, 1u)};
    return emit(cb, d, 2);
}

std::uint32_t *sceAgcDcbSetNumInstances(CommandBuffer *cb, std::uint32_t num_instances) {
    const std::uint32_t d[2] = {0xC0002F00u, num_instances};
    return emit(cb, d, 2);
}

std::uint32_t *sceAgcDcbStallCommandBufferParser(CommandBuffer *cb) {
    const std::uint32_t d[2] = {0xC0004200u, 0u};
    return emit(cb, d, 2);
}

std::uint32_t *sceAgcDcbSetIndexIndirectArgs(CommandBuffer *cb, std::uint64_t address,
                                             std::uint32_t value16) {
    const std::uint32_t d[4] = {0xC0029100u, lo32(address) & ~0xFu, hi32(address),
                                value16 & 0xFFFFu};
    return emit(cb, d, 4);
}

std::uint32_t *sceAgcDcbSetPredication(CommandBuffer *cb, std::uint32_t predicate_bool,
                                       std::uint32_t predicate_op, std::uint32_t hint,
                                       std::uint64_t address) {
    const std::uint32_t d[4] = {0xC0022000u,
                                ((predicate_op & 7u) << 16) | ((predicate_bool & 1u) << 8) |
                                    ((hint & 1u) << 12),
                                lo32(address) & ~0xFu, hi32(address)};
    return emit(cb, d, 4);
}

// ---- other packets ------------------------------------------------------------------------------

std::uint32_t *sceAgcDcbWaitRegMem(CommandBuffer *cb, std::int32_t size, std::uint8_t compare_func,
                                   std::uint32_t engine_and_op, std::uint8_t cache_policy,
                                   std::uint64_t address, std::uint64_t reference,
                                   std::uint64_t mask, std::uint32_t poll_cycles) {
    const std::uint32_t common = ((static_cast<std::uint32_t>(cache_policy) & 3u) << 25) | 0x10u |
                                 (static_cast<std::uint32_t>(compare_func) & 7u);
    // The two packet sizes map engine_and_op differently (as in the original).
    const std::uint32_t c32 = common | ((engine_and_op & 3u) << 8) | ((engine_and_op & 0xCu) << 4);
    const std::uint32_t c64 = common | ((engine_and_op & 1u) << 8) | ((engine_and_op & 6u) << 5);
    return wait_reg_mem(cb, 0, size, c32, c64, address, reference, mask, poll_cycles);
}

std::uint32_t *sceAgcDcbRewind(CommandBuffer *cb, std::uint32_t valid) {
    const std::uint32_t d[2] = {0xC0005900u, valid << 31};
    return emit(cb, d, 2);
}

std::uint32_t *sceAgcDcbPrimeUtcl2(CommandBuffer *cb, std::uint8_t cache_permissions,
                                   std::uint8_t prime_mode, std::uint64_t address,
                                   std::uint32_t num_pages) {
    const std::uint32_t d[5] = {
        0xC0035D00u,
        0x40000000u |
            static_cast<std::uint8_t>(((static_cast<std::uint32_t>(prime_mode) & 1u) << 3) |
                                      (static_cast<std::uint32_t>(cache_permissions) & 7u)),
        lo32(address) & 0xFFFFC000u, hi32(address), num_pages & 0x3FFFu};
    return emit(cb, d, 5);
}

std::uint32_t *sceAgcDcbResetQueue(CommandBuffer *cb, std::uint16_t flags, std::uint32_t queue_slot) {
    const bool trusted = is_trusted_caller(BC5_AGC_RETURN_ADDRESS());
    return dcb_reset_queue_body(cb, flags, slot_for_queue(queue_slot), trusted);
}

std::uint32_t *agcDcbResetActiveQueue(CommandBuffer *cb) {
    QueueSlot *slot = active_slot();
    if (slot == nullptr) {
        return nullptr;
    }
    const bool trusted = is_trusted_caller(BC5_AGC_RETURN_ADDRESS());
    return dcb_reset_queue_body(cb, 0x0BFF, slot, trusted);
}

std::uint32_t *sceAgcDcbAtomicGds(CommandBuffer *cb, std::int32_t engine, std::uint32_t op_flags,
                                  std::int32_t mode, std::uint32_t flag40, std::uint32_t field32,
                                  std::uint16_t gds_offset, std::uint16_t gds_size,
                                  std::uint32_t field5, std::uint32_t field6, std::uint64_t data0,
                                  std::uint64_t data1) {
    return atomic_gds(cb,
                      atomic_gds_control(op_flags, mode, false) |
                          (static_cast<std::uint32_t>(engine) << 30),
                      flag40, field32, gds_offset, gds_size, field5, field6, data0, data1);
}

std::uint32_t *agcDcbAtomicGdsOp8(CommandBuffer *cb, std::int32_t engine, std::uint32_t op_flags,
                                  std::int32_t mode, std::uint32_t flag40, std::uint32_t field32,
                                  std::uint16_t gds_offset, std::uint16_t gds_size,
                                  std::uint32_t field5, std::uint32_t field6, std::uint64_t data0,
                                  std::uint64_t data1) {
    return atomic_gds(cb,
                      atomic_gds_control(op_flags, mode, true) |
                          (static_cast<std::uint32_t>(engine) << 30),
                      flag40, field32, gds_offset, gds_size, field5, field6, data0, data1);
}

std::uint32_t *sceAgcDcbSetMarkerSpan(CommandBuffer *cb, const char *name, std::uint32_t name_length,
                                      std::uint32_t color) {
    return marker(cb, 0, false, name, name_length, color);
}

std::uint32_t *sceAgcDcbSetMarker(CommandBuffer *cb, const char *name, std::uint32_t color) {
    const auto len = name != nullptr ? static_cast<std::uint32_t>(string_length(name)) : 0u;
    return marker(cb, 0, false, name, len, color);
}

std::uint32_t *sceAgcDcbPushMarkerSpan(CommandBuffer *cb, const char *name,
                                       std::uint32_t name_length, std::uint32_t color) {
    return marker(cb, 0, true, name, name_length, color);
}

std::uint32_t *sceAgcDcbPushMarker(CommandBuffer *cb, const char *name, std::uint32_t color) {
    const auto len = name != nullptr ? static_cast<std::uint32_t>(string_length(name)) : 0u;
    return marker(cb, 0, true, name, len, color);
}

std::uint32_t *sceAgcDcbPopMarker(CommandBuffer *cb) { return pop_marker(cb, 0); }

std::uint32_t *sceAgcDcbSetFlip(CommandBuffer *cb, std::uint32_t arg0, std::uint32_t arg1,
                                std::uint32_t arg2, std::uint64_t arg3) {
    return set_flip(cb, 0, arg0, arg1, arg2, arg3);
}

std::uint32_t *sceAgcDcbWaitUntilSafeForRendering(CommandBuffer *cb, std::uint32_t arg0,
                                                  std::uint32_t arg1) {
    return wait_until_safe(cb, 0, arg0, arg1);
}

std::uint32_t *sceAgcDcbMemSemaphore(CommandBuffer *cb, std::uint64_t address,
                                     std::uint8_t use_mailbox, std::uint8_t signal_type,
                                     std::int32_t sem_sel) {
    // The original writes the begin marker with the compute flag set and the end marker without.
    return mem_semaphore(cb, 1, 0, address, use_mailbox, signal_type, sem_sel);
}

std::uint32_t *sceAgcDcbSetWorkloadsActive(CommandBuffer *cb, std::uint32_t arg0,
                                           std::uint64_t arg1, std::uint64_t arg2) {
    return workloads_active(cb, 0, arg0, arg1, static_cast<std::uint32_t>(arg2));
}

std::uint32_t *sceAgcDcbSetWorkloadComplete(CommandBuffer *cb, std::uint32_t arg0,
                                            std::uint32_t arg1) {
    return workload_complete(cb, 0, arg0, arg1);
}

std::uint32_t *sceAgcDcbSetWorkloadStreamInactive(CommandBuffer *cb, std::uint32_t arg0) {
    return workload_stream_inactive(cb, 0, arg0);
}

} // namespace bc5::reimpl::agc
