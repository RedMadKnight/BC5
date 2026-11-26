// SPDX-License-Identifier: GPL-2.0-only
// Small helpers to write a register value by the meaning of its fields, so that the own-source
// default tables (agc_tables.cpp, agc_fill_shader.cpp) read like "CB_COLOR_CONTROL.MODE =
// CB_NORMAL" instead of a bare number. Field positions come from the generated agc_regdb.hpp
// (Mesa's gfx10 register database, tools/bc5-agc/regdb/gfx10.json, MIT).
#pragma once

#include <bit>
#include <cstdint>

namespace bc5::reimpl::regdb {

// One register field: its least and most significant bit, both inclusive (gfx10.json "bits").
struct Field {
    std::uint32_t lo;
    std::uint32_t hi;
};

constexpr std::uint32_t field_width(Field f) { return f.hi - f.lo + 1u; }

constexpr std::uint32_t field_mask(Field f) {
    return field_width(f) >= 32u ? 0xFFFFFFFFu : ((1u << field_width(f)) - 1u) << f.lo;
}

namespace detail {
// Deliberately not constexpr: calling it in a constant expression is a compile error.
inline std::uint32_t value_does_not_fit_field(std::uint32_t value) { return value; }
} // namespace detail

// The field holding `value`. Evaluated at compile time only, so a value that does not fit its
// field (a mistake in the table source) fails to compile.
consteval std::uint32_t fld(Field f, std::uint32_t value) {
    if (field_width(f) < 32u && (value >> field_width(f)) != 0u) {
        value = detail::value_does_not_fit_field(value);
    }
    return (value << f.lo) & field_mask(f);
}

// Every bit of the field set ("FIELD = all ones").
consteval std::uint32_t all_ones(Field f) { return field_mask(f); }

// The k least significant bits of the field set, the rest clear ("FIELD = low k bits set").
consteval std::uint32_t low_bits(Field f, std::uint32_t k) {
    return fld(f, k >= 32u ? 0xFFFFFFFFu : (1u << k) - 1u);
}

// Absolute bit positions, only for bits the descriptions give by position (no gfx10 name or
// outside every gfx10 field).
constexpr std::uint32_t bit(std::uint32_t k) { return 1u << k; }
constexpr std::uint32_t bits(std::uint32_t lo, std::uint32_t hi) {
    return (hi - lo + 1u >= 32u ? 0xFFFFFFFFu : ((1u << (hi - lo + 1u)) - 1u)) << lo;
}

// Whole-register values.
inline constexpr std::uint32_t kAll32 = 0xFFFFFFFFu;
inline constexpr std::uint32_t kFloatOne = std::bit_cast<std::uint32_t>(1.0f);

} // namespace bc5::reimpl::regdb
