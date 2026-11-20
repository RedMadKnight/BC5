// SPDX-License-Identifier: GPL-2.0-only
// Clean-room re-creation of libSceAgc (see src/reimpl/PROVENANCE.md): shader objects (creation,
// fusing of two halves, interpolant mapping, primitive state, GS oversubscription), the register
// descriptors they use, and the module's internal shaders.
//
// Register offsets are per the original module's behaviour (clean-room description, see
// src/reimpl/PROVENANCE.md). Where a comment gives an AMD name it is from Mesa
// src/amd/common/sid.h (commit ab2374a) and only TODO(verify) for this hardware generation:
// COMPUTE_PGM_LO (SH 0x20C), SPI_SHADER_PGM_LO_PS (0x08), SPI_SHADER_PGM_LO_ES (0xC8),
// SPI_SHADER_PGM_LO_LS (0x148), SPI_SHADER_PGM_LO_GS (0x88), SPI_SHADER_PGM_LO_HS (0x108),
// SPI_PS_INPUT_CNTL_0 (context 0x191), VGT_SHADER_STAGES_EN (context 0x2D5),
// VGT_GS_OUT_PRIM_TYPE (context 0x29B), VGT_PRIMITIVE_TYPE (uconfig 0x242).
#include "bc5/reimpl/agc_internal.hpp"
#include "bc5/reimpl/agc_fill_shader.hpp"
#include "bc5/reimpl/agc_tables.hpp"
#include "bc5/reimpl/data_source.hpp"

#include <algorithm>
#include <cmath>

namespace bc5::reimpl::agc {

using namespace detail;

std::uint32_t g_exported_word = 0;

namespace {

constexpr std::uint32_t kUnresolved = 0x10000000u;
constexpr std::uint32_t kShaderMagic = 0x34333231u;
constexpr std::uint32_t kShaderVersion = 0x18u;

Descriptors g_descriptors;

// Which defaults list a descriptor is resolved from.
enum class Db { Public, Internal };
struct DescriptorSpec {
    std::uint64_t vaddr;
    RegPair *storage;
    int pairs;      // 1 or 2 (program address LO+HI)
    Db db;
    int list;       // 0 context, 1 SH, 2 uconfig
    std::uint32_t offset;   // resolved offset (interop fact of the description)
    std::uint32_t fallback; // default value used when the defaults tables are not available
};

DescriptorSpec *specs(std::size_t &count) {
    Descriptors &d = g_descriptors;
    static DescriptorSpec table[] = {
        {0x45c90, d.compute_pgm, 2, Db::Public, 1, 0x20c, 0},
        {0x45ce0, d.ps_pgm, 2, Db::Public, 1, 0x008, 0},
        {0x45ca0, d.es_pgm, 2, Db::Public, 1, 0x0c8, 0},
        {0x45cd0, d.ls_pgm, 2, Db::Public, 1, 0x148, 0},
        {0x45cb0, d.gs_pgm, 2, Db::Public, 1, 0x088, 0},
        {0x45cc0, d.hs_pgm, 2, Db::Public, 1, 0x108, 0},
        {0x459d8, &d.gs_rsrc1, 1, Db::Public, 1, 0x08a, 0},
        {0x459f0, &d.gs_rsrc2, 1, Db::Public, 1, 0x08b, 0},
        {0x459e0, &d.hs_rsrc1, 1, Db::Public, 1, 0x10a, 0},
        {0x459f8, &d.hs_rsrc2, 1, Db::Public, 1, 0x10b, 0},
        {0x45f28, &d.hs_duplicated, 1, Db::Internal, 1, 0x100, 0x00ffffff},
        {0x45db8, &d.ps_input_cntl0, 1, Db::Public, 0, 0x191, 0},
        {0x45a68, &d.stages_enable, 1, Db::Public, 0, 0x2d5, 0x2000},
        {0x45a30, &d.gs_out_prim, 1, Db::Public, 0, 0x29b, 2},
        {0x458c8, &d.prim_uc0, 1, Db::Public, 2, 0x25b, 0},
        {0x458f0, &d.prim_uc1, 1, Db::Public, 2, 0x262, 0},
        {0x45a58, &d.prim_type, 1, Db::Public, 2, 0x242, 0},
        {0x458d8, &d.gs_over_e, 1, Db::Public, 0, 0x1ff, 0},
        {0x45f58, &d.gs_over_a, 1, Db::Internal, 0, 0x291, 0},
        {0x45f00, &d.gs_over_b, 1, Db::Internal, 0, 0x2d3, 0},
        {0x45f48, &d.gs_over_c, 1, Db::Internal, 0, 0x1b1, 0},
        {0x45f10, &d.gs_over_d, 1, Db::Internal, 0, 0x207, 0},
        {0x45f08, &d.gs_over_out0, 1, Db::Internal, 2, 0x260, 0},
        {0x45f30, &d.gs_over_out1, 1, Db::Internal, 1, 0x081, 0},
    };
    count = sizeof(table) / sizeof(table[0]);
    return table;
}

const RegPair *find_pair(const RegPair *list, std::uint32_t count, std::uint32_t offset) {
    if (list == nullptr) {
        return nullptr;
    }
    for (std::uint32_t i = 0; i < count; ++i) {
        if (list[i].offset == offset) {
            return &list[i];
        }
    }
    return nullptr;
}
RegPair *find_pair(RegPair *list, std::uint32_t count, std::uint32_t offset) {
    return const_cast<RegPair *>(find_pair(static_cast<const RegPair *>(list), count, offset));
}

RegPair read_pair(std::uint64_t base, std::size_t offset) {
    RegPair r{};
    std::memcpy(&r, ptr<const std::uint8_t>(base) + offset, sizeof r);
    return r;
}
std::uint32_t read_u32(std::uint64_t base, std::size_t offset) {
    std::uint32_t v = 0;
    std::memcpy(&v, ptr<const std::uint8_t>(base) + offset, 4);
    return v;
}

} // namespace

// ---- register descriptors -----------------------------------------------------------------------

namespace detail {

Descriptors &descriptors() { return g_descriptors; }

void reset_descriptors() {
    std::size_t n = 0;
    DescriptorSpec *t = specs(n);
    for (std::size_t i = 0; i < n; ++i) {
        for (int k = 0; k < t[i].pairs; ++k) {
            t[i].storage[k] = RegPair{kUnresolved, 0};
        }
    }
}

RegPair *descriptor_by_vaddr(std::uint64_t vaddr) {
    std::size_t n = 0;
    DescriptorSpec *t = specs(n);
    for (std::size_t i = 0; i < n; ++i) {
        if (t[i].vaddr == vaddr) {
            return t[i].storage;
        }
    }
    return nullptr;
}

// The original looks each descriptor up by a 32-bit name hash in the name table of the defaults
// database. The name table's location is not part of the description (it sits behind relocated
// pointers), so this re-creation looks the register up by its offset (given by the description)
// in the same list of the same database; absent -> all-ones, as in the original. When the defaults
// tables are not available at all (no firmware data), the description's resolved values are used.
std::int32_t resolve_descriptors(std::uint32_t sdk_version) {
    const RegisterDefaults *dbs[2] = {sceAgcGetRegisterDefaults2(sdk_version),
                                      sceAgcGetRegisterDefaults2Internal(sdk_version)};
    std::size_t n = 0;
    DescriptorSpec *t = specs(n);
    for (std::size_t i = 0; i < n; ++i) {
        const RegisterDefaults *db = dbs[t[i].db == Db::Public ? 0 : 1];
        RegPair *const *cells[3] = {db->cx, db->sh, db->uc};
        const std::uint32_t counts[3] = {db->cx_count, db->sh_count, db->uc_count};
        const RegPair *list = cells[t[i].list] != nullptr ? *cells[t[i].list] : nullptr;
        const std::uint32_t count = counts[t[i].list];
        for (int k = 0; k < t[i].pairs; ++k) {
            const std::uint32_t off = t[i].offset + static_cast<std::uint32_t>(k);
            if (list == nullptr || count == 0) {
                t[i].storage[k] = RegPair{off, k == 0 ? t[i].fallback : 0u};
            } else if (const RegPair *p = find_pair(list, count, off); p != nullptr) {
                t[i].storage[k] = *p;
            } else {
                t[i].storage[k] = RegPair{0xFFFFFFFFu, 0xFFFFFFFFu};
            }
        }
    }
    // Restore values for the compute static thread-management masks (SH 0x216 / 0x217), from the
    // internal defaults.
    const RegisterDefaults *in = dbs[1];
    const RegPair *sh = in->sh != nullptr ? *in->sh : nullptr;
    const RegPair *a = find_pair(sh, in->sh_count, 0x216);
    const RegPair *b = find_pair(sh, in->sh_count, 0x217);
    state().restore_a = a != nullptr ? *a : RegPair{0xFFFFFFFFu, 0xFFFFFFFFu};
    state().restore_b = b != nullptr ? *b : RegPair{0xFFFFFFFFu, 0xFFFFFFFFu};
    return kOk;
}

std::uint32_t prim_class(std::uint32_t prim_type) {
    if (prim_type < 1 || prim_type > 18) {
        return 2;
    }
    // 18 u32 classes indexed by primType - 1: our own table (agc_tables.cpp), or the copy at
    // image address 0x23f1c of the module file with BC5_REIMPL_FW_DATA.
    const std::span<const std::uint32_t> own = tables::prim_classes();
    compare_table_with_firmware(kModule, "PRIM-CLASS", tables::kPrimClassImageAddress, own.data(),
                                own.size(), 1);
    FirmwareData *fw = firmware_data_for_use();
    if (const std::uint8_t *table =
            fw != nullptr ? fw->get(kModule, tables::kPrimClassImageAddress, own.size_bytes())
                          : nullptr;
        table != nullptr) {
        std::uint32_t v = 0;
        std::memcpy(&v, table + 4u * (prim_type - 1u), 4);
        return v;
    }
    return own[prim_type - 1u];
}

} // namespace detail

// ---- shader creation ------------------------------------------------------------------------------

namespace {

void relocate_field(std::uint64_t *field) {
    if (*field != 0) {
        *field = addr(field) + *field;
    }
}

void relocate_header(Shader *h) {
    relocate_field(&h->extra);
    relocate_field(&h->info);
    relocate_field(&h->ctx_regs);
    relocate_field(&h->sh_regs);
    relocate_field(&h->ps_inputs);
    relocate_field(&h->vs_outputs);
    if (h->extra == 0) {
        return; // deviation: UB in the original (the sub-block is converted unconditionally)
    }
    auto *sub = ptr<std::uint64_t>(h->extra);
    for (int i = 0; i < 5; ++i) {
        relocate_field(&sub[i]);
    }
}

const RegPair *program_descriptor(std::uint8_t stage) {
    Descriptors &d = g_descriptors;
    switch (stage) {
    case 0:
        return d.compute_pgm;
    case 1:
        return d.ps_pgm;
    case 2:
        return d.es_pgm;
    case 3:
        return d.ls_pgm;
    case 6:
        return d.gs_pgm;
    case 7:
        return d.hs_pgm;
    default:
        return nullptr;
    }
}

bool target_supported(std::uint32_t target) {
    const std::uint32_t t = target & 0x7FFFFFFFu;
    const bool kflag = state().kernel_flag;
    const bool soc = (state().soc_id & 0xFFFFFFF0u) == 0x840FC0u;
    if (t == 10) {
        return !kflag;
    }
    if (t == 12) {
        return kflag;
    }
    if (t == 13) {
        return !kflag && !soc;
    }
    if (t == 15) {
        return kflag && !soc;
    }
    if (t > 12) {
        return !soc;
    }
    return true;
}

} // namespace

std::int32_t sceAgcCreateShader(Shader **out_shader, Shader *header, std::uint64_t code_address) {
    if (header->magic != kShaderMagic) {
        return kErrShaderMagic;
    }
    if (header->version != kShaderVersion) {
        return kErrShaderVersion;
    }
    if (header->code_address != 0) {
        return kErrAlreadyCreated;
    }
    if (g_descriptors.compute_pgm[0].offset == kUnresolved) {
        return kErrNotInitialised;
    }
    if (!target_supported(header->target)) {
        return kErrTargetUnsupported;
    }
    if ((header->target & 0x80000000u) != 0 &&
        (g_imports.is_pa_debug == nullptr || g_imports.is_pa_debug() == 0)) {
        return kErrDebugShader;
    }
    // The shader-replacement path (GPU transcoding arena) is never enabled in this re-creation,
    // see module_load(); the caller's header and code are used as they are.
    relocate_header(header);
    header->code_address = code_address;
    const RegPair *desc = program_descriptor(header->stage);
    if (desc != nullptr) {
        auto *regs = ptr<RegPair>(header->sh_regs);
        RegPair *lo = find_pair(regs, header->num_sh_regs, desc[0].offset);
        if (lo == nullptr) {
            mutex_unlock(); // quirk of the original: unlock without a lock on this path
            return kErrRegNotFound;
        }
        // LO holds the code offset in 256-byte units; HI's low byte gets the carry above bit 40.
        const std::uint64_t a = code_address + static_cast<std::uint64_t>(lo->value) * 256u;
        lo->value = static_cast<std::uint32_t>(a >> 8);
        const auto index = static_cast<std::uint32_t>(lo - regs);
        if (index + 1u < header->num_sh_regs) { // deviation: UB in the original past the end
            RegPair &hi = regs[index + 1u];
            const auto byte = static_cast<std::uint8_t>((hi.value & 0xFFu) + ((a >> 40) & 0xFFu));
            hi.value = (hi.value & ~0xFFu) | byte;
        }
    }
    if (out_shader != nullptr) {
        *out_shader = header;
    }
    return kOk;
}

// ---- fusing --------------------------------------------------------------------------------------

namespace {

bool stage_pair(const Shader *first, const Shader *second, bool &hs) {
    if (first->stage == 5 && second->stage == 7) {
        hs = true;
        return true;
    }
    if (first->stage == 4 && second->stage == 6) {
        hs = false;
        return true;
    }
    return false;
}

std::uint32_t max_field(std::uint32_t a, std::uint32_t b, std::uint32_t shift, std::uint32_t mask) {
    return std::max((a >> shift) & mask, (b >> shift) & mask);
}
std::uint32_t put_field(std::uint32_t v, std::uint32_t shift, std::uint32_t mask,
                        std::uint32_t field) {
    return (v & ~(mask << shift)) | ((field & mask) << shift);
}

std::int32_t fuse(Shader *out, const Shader *first, Shader *second, RegPair *reg_buffer,
                  bool second_variant) {
    bool hs = false;
    if (!stage_pair(first, second, hs)) {
        return kErrIncompatibleHalves;
    }
    std::memcpy(out, second, sizeof(Shader));
    out->stage = hs ? 3 : 2;
    const unsigned bit = hs ? 21 : 22;
    if (((read_u32(first->info, 0x0C) >> bit) & 1u) != ((read_u32(second->info, 0x0C) >> bit) & 1u)) {
        return kErrIncompatibleHalves;
    }
    if (reg_buffer != nullptr) {
        copy_bytes(reg_buffer, ptr<const RegPair>(second->sh_regs), 8ull * second->num_sh_regs);
        out->sh_regs = addr(reg_buffer);
    }
    auto *o = ptr<RegPair>(out->sh_regs);
    const std::uint32_t on = out->num_sh_regs;
    auto *f = ptr<RegPair>(first->sh_regs);
    const std::uint32_t fn = first->num_sh_regs;
    const Descriptors &d = g_descriptors;

    // Duplicated register: both occurrences come from the first half.
    const std::uint32_t x = hs ? d.hs_duplicated.offset : 0x80u;
    RegPair *f1 = find_pair(f, fn, x);
    RegPair *o1 = find_pair(o, on, x);
    RegPair *f2 = f1 != nullptr ? find_pair(f1 + 1, fn - static_cast<std::uint32_t>(f1 - f) - 1u, x)
                                : nullptr;
    RegPair *o2 = o1 != nullptr ? find_pair(o1 + 1, on - static_cast<std::uint32_t>(o1 - o) - 1u, x)
                                : nullptr;
    // deviation: the original searches some of these lists without a bound (crash when absent).
    if (f1 == nullptr || f2 == nullptr || o1 == nullptr || o2 == nullptr) {
        return kErrRegNotFound;
    }
    o1->value = f1->value;
    o2->value = f2->value;

    const RegPair &r1d = hs ? d.hs_rsrc1 : d.gs_rsrc1;
    const RegPair &r2d = hs ? d.hs_rsrc2 : d.gs_rsrc2;
    RegPair *fr1 = find_pair(f, fn, r1d.offset);
    RegPair *fr2 = find_pair(f, fn, r2d.offset);
    RegPair *or1 = find_pair(o, on, r1d.offset);
    RegPair *or2 = find_pair(o, on, r2d.offset);
    if (fr1 == nullptr || fr2 == nullptr || or1 == nullptr || or2 == nullptr) {
        return kErrRegNotFound; // deviation (see above)
    }
    const std::uint32_t F1 = fr1->value;
    const std::uint32_t F2 = fr2->value;
    std::uint32_t O1 = or1->value;
    std::uint32_t O2 = or2->value;
    if (second_variant) {
        const std::uint32_t vf = (F1 & 0x3Fu) * 8u + 8u;
        const std::uint32_t vo = (O1 & 0x3Fu) * 8u + 8u;
        const std::uint32_t vmax = std::max(vf, vo);
        const std::uint32_t a = vo / 2u + (O2 >> 28) * 8u;
        const std::uint32_t b = vf / 2u + (F2 >> 28) * 8u;
        const std::uint32_t m = std::max(a, b);
        std::uint32_t top = 0;
        if (vmax / 2u < m) {
            top = ((m - std::min(a, b)) * 0x400000u + 0x1C00000u) & 0xF0000000u;
        }
        O1 = put_field(O1, 0, 0x3Fu, vmax / 8u - 1u);
        O2 = (O2 & 0x0FFFFFFFu) | top;
    } else {
        O1 = put_field(O1, 0, 0x3Fu, max_field(F1, O1, 0, 0x3Fu));
        O2 = put_field(O2, 28, 0xFu, max_field(F2, O2, 28, 0xFu));
    }
    if (hs) {
        O1 = put_field(O1, 28, 3u, max_field(F1, O1, 28, 3u));
    } else {
        O1 = put_field(O1, 29, 3u, max_field(F1, O1, 29, 3u));
    }
    const std::uint32_t keep = 0x3Eu | (1u << 27);
    O2 = (O2 & ~keep) | (F2 & keep);
    if (!hs) {
        O2 = put_field(O2, 16, 3u, max_field(F2, O2, 16, 3u));
        O2 = (O2 & ~(1u << 18)) | (F2 & (1u << 18));
    }
    or1->value = O1;
    or2->value = O2;

    const RegPair *p = hs ? d.ls_pgm : d.es_pgm;
    RegPair *lo = find_pair(o, on, p[0].offset);
    if (lo == nullptr) {
        return kErrRegNotFound; // deviation (see above)
    }
    lo->value = static_cast<std::uint32_t>(first->code_address >> 8);
    const auto index = static_cast<std::uint32_t>(lo - o);
    if (index + 1u < on) {
        o[index + 1u].value = (o[index + 1u].value & ~0xFFu) |
                              static_cast<std::uint32_t>((first->code_address >> 40) & 0xFFu);
    }
    out->extra = second_variant ? 0u : first->extra;
    return kOk;
}

} // namespace

std::int32_t agcGetFusedShaderSize64(std::uint64_t *out_size_align, const Shader *first_half,
                                     const Shader *second_half) {
    bool hs = false;
    if (!stage_pair(first_half, second_half, hs)) {
        return kErrIncompatibleHalves;
    }
    out_size_align[0] = static_cast<std::uint64_t>(second_half->num_sh_regs) * 8u;
    out_size_align[1] = 4;
    return kOk;
}

std::int32_t sceAgcGetFusedShaderSize(FusedShaderSize *out, const Shader *first_half,
                                      const Shader *second_half) {
    bool hs = false;
    if (!stage_pair(first_half, second_half, hs)) {
        return kErrIncompatibleHalves;
    }
    out->size_bytes = static_cast<std::uint64_t>(second_half->num_sh_regs) * 8u;
    out->alignment = 4; // the 4 bytes after it are not written
    return kOk;
}

std::int32_t sceAgcFuseShaderHalves(Shader *out, const Shader *first_half, Shader *second_half,
                                    RegPair *reg_buffer) {
    return fuse(out, first_half, second_half, reg_buffer, false);
}

std::int32_t agcFuseShaderHalves2(Shader *out, const Shader *first_half, Shader *second_half,
                                  RegPair *reg_buffer) {
    return fuse(out, first_half, second_half, reg_buffer, true);
}

// ---- interpolant mapping ---------------------------------------------------------------------------

namespace {

enum class Variant { A, B, C };

RegPair default_interpolant(std::uint32_t i) {
    const RegPair base = g_descriptors.ps_input_cntl0;
    return RegPair{base.offset + i, (base.value & ~0x1Fu) + i};
}

RegPair ps_input_control(std::uint32_t i, std::uint32_t ps, const std::uint32_t *vs,
                         std::uint32_t num_vs, Variant variant) {
    const RegPair base = g_descriptors.ps_input_cntl0;
    std::uint32_t k = 0;
    while (k < num_vs && (vs[k] & 0xFFu) != (ps & 0xFFu)) {
        ++k;
    }
    const bool found = k < num_vs;
    const std::uint32_t v = found ? vs[k] : 0u;
    const std::uint32_t b22 = (ps >> 22) & 1u;
    const std::uint32_t b24 = (ps >> 24) & 1u;
    const std::uint32_t slot = found ? (v >> 8) & 0x1Fu : 0u;
    const std::uint32_t b10 = found ? (b22 != 0 ? 1u : b24) : 0u;
    const std::uint32_t def = (ps >> 28) & 3u;
    const std::uint32_t s = (ps >> 20) & 3u;
    std::uint32_t value = 0;
    if (s == 0) {
        std::uint32_t flat = 0;
        if (variant == Variant::A) {
            flat = (found && b22 == 0) ? b24 : 1u;
        } else {
            flat = found ? b24 : 1u;
        }
        value = (base.value & ~(0x1Fu | 0x20u | 0x300u | 0x400u)) | slot | (flat << 5) |
                (def << 8) | (b10 << 10);
    } else {
        const std::uint32_t t = found ? (v & ps) : 0u;
        const std::uint32_t hi2 = (ps >> 30) & 3u;
        const std::uint32_t cleared = 0x1Fu | 0x20u | 0x300u | 0x400u | (1u << 19) | (1u << 20) |
                                      (3u << 21) | (3u << 24);
        value = (base.value & ~cleared) | (s << 24) | (1u << 19) | slot | (b10 << 10) | (hi2 << 21);
        if (variant == Variant::C && s == 2) {
            // TODO(verify): bits 8..9 from psDesc bits 30..31 (marked UNSURE in the description).
            const std::uint32_t b5 = found ? (((t >> 21) & 1u) ^ 1u) : 1u;
            value |= (b5 << 5) | (hi2 << 8);
        } else {
            const std::uint32_t b5 = found ? (((t >> 20) & 1u) ^ 1u) : 1u;
            const std::uint32_t b20 = found ? (((t >> 21) & 1u) ^ 1u) : 1u;
            value |= (b5 << 5) | (b20 << 20) | (def << 8);
        }
    }
    return RegPair{base.offset + i, value};
}

std::int32_t create_mapping(RegPair *out, const Shader *vs, const Shader *ps, Variant variant) {
    if (ps == nullptr) {
        for (std::uint32_t i = 0; i < 32; ++i) {
            out[i] = default_interpolant(i);
        }
        return kOk;
    }
    const std::uint32_t n = ps->num_ps_inputs;
    const auto *inputs = ptr<const std::uint32_t>(ps->ps_inputs);
    const auto *outputs = ptr<const std::uint32_t>(vs->vs_outputs);
    for (std::uint32_t i = 0; i < n; ++i) {
        out[i] = ps_input_control(i, inputs[i], outputs, vs->num_vs_outputs, variant);
    }
    for (std::uint32_t i = n; i < 32; ++i) {
        out[i] = default_interpolant(i);
    }
    return kOk;
}

std::int32_t update_mapping(RegPair *out, const Shader *vs, const Shader *ps, Variant variant) {
    const std::uint32_t n = ps->num_ps_inputs;
    if (n == 0) {
        return kOk;
    }
    const auto *inputs = ptr<const std::uint32_t>(ps->ps_inputs);
    const auto *outputs = ptr<const std::uint32_t>(vs->vs_outputs);
    for (std::uint32_t i = 0; i < n; ++i) {
        out[i] = ps_input_control(i, inputs[i], outputs, vs->num_vs_outputs, variant);
    }
    return kOk;
}

} // namespace

std::int32_t sceAgcCreateInterpolantMapping(RegPair *out, const Shader *vs_shader,
                                            const Shader *ps_shader) {
    return create_mapping(out, vs_shader, ps_shader, Variant::A);
}
std::int32_t sceAgcUpdateInterpolantMapping(RegPair *out, const Shader *vs_shader,
                                            const Shader *ps_shader) {
    return update_mapping(out, vs_shader, ps_shader, Variant::A);
}
std::int32_t agcCreateInterpolantMappingB(RegPair *out, const Shader *vs_shader,
                                          const Shader *ps_shader) {
    return create_mapping(out, vs_shader, ps_shader, Variant::B);
}
std::int32_t agcUpdateInterpolantMappingB(RegPair *out, const Shader *vs_shader,
                                          const Shader *ps_shader) {
    return update_mapping(out, vs_shader, ps_shader, Variant::B);
}
std::int32_t agcCreateInterpolantMappingC(RegPair *out, const Shader *vs_shader,
                                          const Shader *ps_shader) {
    return create_mapping(out, vs_shader, ps_shader, Variant::C);
}
std::int32_t agcUpdateInterpolantMappingC(RegPair *out, const Shader *vs_shader,
                                          const Shader *ps_shader) {
    return update_mapping(out, vs_shader, ps_shader, Variant::C);
}

// ---- primitive state and linking -------------------------------------------------------------------

std::int32_t sceAgcCreatePrimState(PrimStateCx *out_cx, PrimStateUc *out_uc,
                                   const Shader *aux_shader, const Shader *main_shader,
                                   std::uint32_t prim_type) {
    const Descriptors &d = g_descriptors;
    if (out_cx != nullptr) {
        RegPair c0 = read_pair(main_shader->info, kInfoStagesEnable);
        RegPair c1 = d.gs_out_prim;
        if ((c0.value & 0x20u) == 0) {
            c1.value = (c1.value & ~7u) | prim_class(prim_type);
        } else {
            c1 = read_pair(main_shader->info, kInfoGsOutPrim);
        }
        if (aux_shader != nullptr) {
            c0.value |= read_u32(aux_shader->info, 0x0C);
            if ((c0.value & 0x20u) == 0) {
                c1 = read_pair(aux_shader->info, kInfoGsOutPrim);
            }
        }
        out_cx->stages_enable = c0;
        out_cx->gs_out_prim_type = c1;
    }
    if (out_uc != nullptr) {
        out_uc->pairs[0] = read_pair(main_shader->info, kInfoUcSlot0);
        out_uc->pairs[1] = read_pair((aux_shader != nullptr ? aux_shader : main_shader)->info,
                                     kInfoUcSlot1);
        out_uc->pairs[2] = RegPair{d.prim_type.offset, (d.prim_type.value & ~0x1Fu) | prim_type};
    }
    return kOk;
}

std::int32_t sceAgcUpdatePrimState(PrimStateCx *cx, PrimStateUc *uc, std::uint32_t prim_type) {
    if (cx != nullptr && (cx->stages_enable.value & 0x24u) == 0) {
        cx->gs_out_prim_type.value = (cx->gs_out_prim_type.value & ~7u) | (prim_class(prim_type) & 7u);
    }
    if (uc != nullptr) {
        uc->pairs[2].value = (uc->pairs[2].value & ~0x1Fu) | prim_type;
    }
    return kOk;
}

std::int32_t sceAgcLinkShaders(LinkOutput *out, PrimStateUc *out_uc, const Shader *aux_shader,
                               const Shader *main_shader, const Shader *ps_shader,
                               std::uint32_t prim_type) {
    const Descriptors &d = g_descriptors;
    if (out != nullptr) {
        out->prim.stages_enable = d.stages_enable;
        out->prim.gs_out_prim_type = d.gs_out_prim;
        if (main_shader != nullptr) {
            out->prim.stages_enable = read_pair(main_shader->info, kInfoStagesEnable);
            if ((out->prim.stages_enable.value & 0x20u) == 0) {
                out->prim.gs_out_prim_type.value = (d.gs_out_prim.value & ~7u) | prim_class(prim_type);
            } else {
                out->prim.gs_out_prim_type = read_pair(main_shader->info, kInfoGsOutPrim);
            }
            create_mapping(out->interpolants, main_shader, ps_shader, Variant::A);
        }
        if (aux_shader != nullptr) {
            out->prim.stages_enable.value |= read_u32(aux_shader->info, 0x0C);
            if ((out->prim.stages_enable.value & 0x20u) == 0) {
                out->prim.gs_out_prim_type = read_pair(aux_shader->info, kInfoGsOutPrim);
            }
        }
    }
    if (out_uc != nullptr) {
        const RegPair src0 =
            main_shader != nullptr ? read_pair(main_shader->info, kInfoUcSlot0) : d.prim_uc0;
        out_uc->pairs[0] = src0;
        out_uc->pairs[1] = d.prim_uc1;
        out_uc->pairs[2] = RegPair{d.prim_type.offset, (d.prim_type.value & ~0x1Fu) | prim_type};
        if (main_shader != nullptr) {
            out_uc->pairs[1] = read_pair(main_shader->info, kInfoUcSlot1);
        }
        if (aux_shader != nullptr) {
            out_uc->pairs[1] = read_pair(aux_shader->info, kInfoUcSlot1);
        }
        if (state().soc_id == kSocA) {
            out_uc->pairs[1] = src0;
        }
    }
    return kOk;
}

// ---- GS oversubscription ---------------------------------------------------------------------------

std::int32_t sceAgcGetGsOversubscription(RegPair *out, const Shader *gs_shader, std::uint32_t budget,
                                         float fraction) {
    const Descriptors &d = g_descriptors;
    out[1] = d.gs_over_out1;
    out[0] = d.gs_over_out0;
    const std::uint32_t v0 = out[0].value;
    const std::uint32_t v1 = out[1].value;
    if (budget == 0) {
        return kOk;
    }
    if (budget == 0xFFFFFFFFu) {
        out[1].value = v1 | 0x7F0000u;
        out[0].value = v0 | 0x7FFu;
        return kOk;
    }
    const auto *ctx = ptr<const RegPair>(gs_shader->ctx_regs);
    const std::uint32_t nctx = gs_shader->num_ctx_regs;
    const RegPair *pa = find_pair(ctx, nctx, d.gs_over_a.offset);
    const RegPair *pb = find_pair(ctx, nctx, d.gs_over_b.offset);
    const RegPair *pc = find_pair(ctx, nctx, d.gs_over_c.offset);
    const RegPair *pd = find_pair(ctx, nctx, d.gs_over_d.offset);
    const RegPair *pe = find_pair(ctx, nctx, d.gs_over_e.offset);
    if (pa == nullptr || pb == nullptr || pc == nullptr || pd == nullptr || pe == nullptr) {
        return kErrRegNotFound; // deviation: UB in the original (NULL dereferenced)
    }
    const std::uint32_t A = pa->value;
    const std::uint32_t B = pb->value;
    const std::uint32_t C = pc->value;
    const std::uint32_t D = pd->value;
    const std::uint32_t E = pe->value;
    const std::uint32_t half = ((read_u32(gs_shader->info, 0x0C) >> 22) & 1u) == 0 ? 1u : 0u;
    const std::uint32_t y = ((E & 0x3FFu) + 31u) >> 5;
    if (y == 0) {
        return kOk; // deviation: UB in the original (division by zero); defaults stay
    }
    const std::uint32_t x = ((B & 0x1FFu) * ((A >> 11) & 0x7FFu) + 31u) >> 5;
    const std::uint32_t m = std::max(x, y) >> half;
    const std::uint32_t m1 = std::max(m, 1u);
    const std::uint32_t k = 1u + ((D >> 21) & 1u) + ((D >> 22) & 1u) + ((D >> 23) & 1u);
    const std::uint32_t c = (C & 0x80u) == 0 ? ((C >> 2) & 0xFu) * 2u + 2u : 0u;
    const std::uint32_t low_a = ((c != 0 ? 0x800u / c : 0x800u) / y) * m1;
    const std::uint32_t low_b = (((0x80u / k) * 4u) / y) * m1;
    const std::uint32_t high_a = ((c != 0 ? 0x1000u / c : 0x800u) / y) * m1;
    const std::uint32_t high_b = ((((0x17Eu / k) & 0xFFFFu) * 4u) / y) * m1;
    const std::uint32_t lo = std::min(low_a, low_b);
    const std::uint32_t cap = std::min({high_a, high_b, budget >> (half + 5u), 0x400u});
    const std::uint32_t span = cap > lo ? cap - lo : 0u;
    const float fv = std::fma(static_cast<float>(span), fraction, static_cast<float>(lo));
    const auto v = static_cast<std::uint32_t>(static_cast<std::int64_t>(fv));
    if (v > lo) {
        if (v < low_b) {
            const std::uint64_t num = static_cast<std::uint64_t>(v - low_a) << 10;
            const std::uint64_t den = std::max<std::uint32_t>(high_a - low_a, 1u);
            const auto r = static_cast<std::uint32_t>(std::min<std::uint64_t>(num / den, 0x400u));
            const std::uint32_t f = r != 0 ? r - 1u : 0u;
            out[0].value = (v0 & 0xFFFFF800u) + 1u + (f & 0x3FFu) * 2u;
            out[1].value = v1 | 0x7F0000u;
        } else {
            const std::uint64_t num = static_cast<std::uint64_t>(v - low_b) * 0x7Fu;
            const std::uint64_t den = std::max<std::uint32_t>(high_b - low_b, 1u);
            const auto r = static_cast<std::uint32_t>(std::min<std::uint64_t>(num / den, 0x7Fu));
            out[1].value = (v1 & 0xFF80FFFFu) | (r << 16);
            out[0].value = v0 | 0x7FFu;
        }
    }
    return kOk;
}

std::int32_t agcGetShaderExportFlag(std::uint32_t *out_value, const Shader *shader) {
    const auto *ctx = ptr<const RegPair>(shader->ctx_regs);
    std::uint32_t result = 0;
    for (std::uint32_t i = 0; i < shader->num_ctx_regs; ++i) {
        if (ctx[i].offset == 0x1C2u && (ctx[i].value & 0xFu) == 2u) {
            result = 8;
            break;
        }
    }
    *out_value = result;
    return kOk;
}

// ---- internal shaders ------------------------------------------------------------------------------

namespace detail {

namespace {

// The original module's five internal shaders, read from the module file (BC5_REIMPL_FW_DATA only).
// TODO(verify): the description gives the ten locations and says "which pair is used depends on
// sceAgcDriverIsPaDebug"; read here as five shaders, each with a normal (even index) and a
// PA-debug (odd index) build, the first of them being the fill shader used by agcCbFillMemory.
std::int32_t create_firmware_shaders(FirmwareData *fw) {
    static constexpr std::uint64_t kHeaders[10] = {0x2c000, 0x2c130, 0x2c260, 0x2c390, 0x2c4c0,
                                                   0x2c5f0, 0x2c720, 0x2c850, 0x2c980, 0x2cab0};
    static constexpr std::uint64_t kCode[10] = {0x30000, 0x30100, 0x30b00, 0x31400, 0x31600,
                                                0x31a00, 0x31d00, 0x32300, 0x32900, 0x32b00};
    const bool pa = g_imports.is_pa_debug != nullptr && g_imports.is_pa_debug() != 0;
    std::uint64_t code_table[16] = {};
    for (int k = 0; k < 5; ++k) {
        const int idx = 2 * k + (pa ? 1 : 0);
        const std::uint8_t *h0 = fw->get(kModule, kHeaders[idx], sizeof(Shader));
        if (h0 == nullptr) {
            log(kModule, "internal shader header 0x%llx unavailable",
                static_cast<unsigned long long>(kHeaders[idx]));
            return kOk; // deviation: without the module file the internal shaders are skipped
        }
        Shader probe{};
        std::memcpy(&probe, h0, sizeof probe);
        const std::uint32_t header_bytes = std::max<std::uint32_t>(probe.header_bytes, sizeof(Shader));
        const std::uint8_t *hb = fw->get(kModule, kHeaders[idx], header_bytes);
        const std::uint8_t *cb = fw->get(kModule, kCode[idx], probe.code_bytes);
        if (hb == nullptr || cb == nullptr) {
            log(kModule, "internal shader %d unavailable", idx);
            return kOk; // deviation (see above)
        }
        const std::uint64_t hdst = dmem_alloc(header_bytes, 16);
        const std::uint64_t cdst = dmem_alloc(probe.code_bytes, 256);
        if (hdst == 0 || cdst == 0) {
            return kErrInternal;
        }
        copy_bytes(ptr<void>(hdst), hb, header_bytes);
        copy_bytes(ptr<void>(cdst), cb, probe.code_bytes);
        Shader *created = nullptr;
        const std::int32_t rc = sceAgcCreateShader(&created, ptr<Shader>(hdst), cdst);
        if (rc != kOk) {
            return rc;
        }
        code_table[k] = cdst;
        if (k == 0) {
            state().fill_shader = created;
        }
    }
    const std::uint64_t table = dmem_alloc(sizeof code_table, 8);
    if (table == 0) {
        return kErrInternal;
    }
    copy_bytes(ptr<void>(table), code_table, sizeof code_table);
    const std::uint64_t entry[2] = {table, sizeof code_table}; // TODO(verify) entry layout
    sceAgcSetStaticBuffer(0, entry);
    return kOk;
}

// Our own internal shaders: only the fill shader (agc_fill_shader.cpp), and only once its code
// has been assembled. The original's other four internal shaders are not re-created: their
// purpose is not described, and on BC5 they are never executed (the original only lists their
// code addresses in static buffer 0), so their slots stay 0.
std::int32_t create_own_shaders() {
    const std::span<const std::uint32_t> code = fill_shader::code();
    if (code.empty()) {
        log(kModule, "own fill shader not assembled yet; fill shader absent");
        return kOk; // as without module files before: CbMemsetExclusive has no shader
    }
    const auto code_bytes = static_cast<std::uint32_t>(code.size_bytes());
    const std::uint64_t hdst = dmem_alloc(fill_shader::header_bytes(), 16);
    const std::uint64_t cdst = dmem_alloc(code_bytes, 256);
    if (hdst == 0 || cdst == 0) {
        return kErrInternal;
    }
    fill_shader::build_header(ptr<std::uint8_t>(hdst), code_bytes);
    copy_bytes(ptr<void>(cdst), code.data(), code_bytes);
    Shader *created = nullptr;
    const std::int32_t rc = sceAgcCreateShader(&created, ptr<Shader>(hdst), cdst);
    if (rc != kOk) {
        return rc;
    }
    state().fill_shader = created;
    std::uint64_t code_table[16] = {};
    code_table[0] = cdst;
    const std::uint64_t table = dmem_alloc(sizeof code_table, 8);
    if (table == 0) {
        return kErrInternal;
    }
    copy_bytes(ptr<void>(table), code_table, sizeof code_table);
    const std::uint64_t entry[2] = {table, sizeof code_table}; // TODO(verify) entry layout
    sceAgcSetStaticBuffer(0, entry);
    return kOk;
}

} // namespace

std::int32_t create_internal_shaders() {
    if (FirmwareData *fw = firmware_data_for_use(); fw != nullptr) {
        return create_firmware_shaders(fw);
    }
    return create_own_shaders();
}

} // namespace detail

} // namespace bc5::reimpl::agc
