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

// Every register-default pair table. The names follow the description: CX/SH/UC = context, SH
// and uconfig register space; SOC = SoC family 0x840F00 (every SDK version but the version-11
// group); V0_3 = SDK versions 0 to 3 on other SoCs; V11 = SDK version 11 and unknown versions;
// INT = the lists of the "Internal" descriptors.
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
