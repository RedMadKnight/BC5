// SPDX-License-Identifier: GPL-2.0-only
// Own-source data tables of the libSceAgc re-creation: the register-default sets, the console
// variant CU-mask rows and the primitive-class table. They are written in this repository from a
// description of their meaning (clean-room, see src/reimpl/PROVENANCE.md), with register, field
// and enum names from Mesa's gfx10 register database (tools/bc5-agc/regdb/gfx10.json, MIT); they
// replace the reads of the original module file (firmware_data()), which stay available behind
// BC5_REIMPL_FW_DATA=1 (see data_source.hpp).
#pragma once

#include "bc5/reimpl/agc_cb.hpp"

#include <cstdint>
#include <span>

namespace bc5::reimpl::agc::tables {

// Every register-default pair table. The names follow the descriptions (desc2/tables.md and
// tables2.md): CX/SH/UC = context, SH and uconfig register space; Int..Cx/Sh/Uc = the lists of the
// "Internal" descriptors; Fourth = list 3 of an internal descriptor (space not determined). Groups:
// SOC = SoC family 0x840F00; V0_3, V4, V5_6, V7, V8, V9, V10_12 = those SDK versions on other SoCs;
// OTHER = SDK version 11 and 13 and above without a shader transcoder (and the old API for 11 and
// above); V11 = the same versions with a shader transcoder (new API only).
enum class TableId {
    CxSoc,
    ShSoc,
    UcSoc,
    IntSocA, // internal, context
    IntSocB, // internal, SH
    CxV0_3,
    ShV0_3,
    UcV0_3,
    CxV11,
    ShV11,
    UcV11,
    IntV11_1, // internal, context
    IntV11_2, // internal, SH
    IntV11_3, // internal, uconfig
    // tables2.md
    CxOther,
    ShOther,
    UcOther,
    IntOtherCx,
    IntOtherSh,
    IntOtherUc,
    FourthOther,
    IntV0_3Cx,
    IntV0_3Sh,
    FourthV0_3,
    CxV4,
    ShV4,
    UcV4,
    IntV4Cx,
    IntV4Sh,
    FourthV4,
    CxV5_6,
    ShV5_6,
    UcV5_6,
    IntV5_6Cx,
    IntV5_6Sh,
    FourthV5_6,
    CxV7,
    ShV7,
    UcV7,
    IntV7Cx,
    IntV7Sh,
    FourthV7,
    CxV8,
    ShV8,
    UcV8,
    IntV8Cx,
    IntV8Sh,
    FourthV8,
    CxV9,
    ShV9,
    UcV9,
    IntV9Cx,
    IntV9Sh,
    IntV9Uc,
    FourthV9,
    CxV10_12,
    ShV10_12,
    UcV10_12,
    IntV10_12Cx,
    IntV10_12Sh,
    IntV10_12Uc,
    FourthV10_12,
    FourthSoc,
    FourthV11,
    Count
};
inline constexpr int kTableCount = static_cast<int>(TableId::Count);

// Short name for logs ("CX-SOC", ...).
const char *table_name(TableId id);

// The table in its stored (unpatched) form, in table order. Built once, never modified; the
// selector copies it into writable memory before patching.
std::span<const RegPair> table(TableId id);

// The address of the table in the original module image (base 0), only used to read the
// firmware's copy behind BC5_REIMPL_FW_DATA / BC5_REIMPL_FW_COMPARE. 0 when not known.
std::uint64_t table_image_address(TableId id);

// Which own table the original image address `vaddr` holds; false when none.
bool table_at_image_address(std::uint64_t vaddr, TableId &out);

// Console-variant CU-mask override rows: 6 rows x 10 pairs (SH space), row = variant + (SDK
// version > 12 ? 3 : 0).
inline constexpr std::uint32_t kCuRowCount = 6;
inline constexpr std::uint32_t kCuColumnCount = 10;
inline constexpr std::uint64_t kCuRowsImageAddress = 0x1BDB0;
std::span<const RegPair> cu_rows();

// Primitive class (the GS output primitive type to assume) for the AGC primitive types 1..18,
// indexed by type - 1.
inline constexpr std::uint32_t kPrimClassCount = 18;
inline constexpr std::uint64_t kPrimClassImageAddress = 0x23f1c;
std::span<const std::uint32_t> prim_classes();

} // namespace bc5::reimpl::agc::tables
