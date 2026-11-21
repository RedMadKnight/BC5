// SPDX-License-Identifier: GPL-2.0-only
// The register catcher, see include/bc5/reg_catch.hpp.
#include "bc5/reg_catch.hpp"

#include "bc5/env_flag.hpp"

#include <cstdlib>
#include <cstring>

namespace bc5::reg_catch {

namespace {

struct Space {
    std::uint32_t base; // absolute dword offset of the space
    std::uint32_t size; // dwords
};

// Mesa src/amd/common/sid.h (0866ae7), bytes / 4.
constexpr Space kConfig{0x2000, 0xC00};
constexpr Space kSh{0x2C00, 0x400};
constexpr Space kContext{0xA000, 0x400};
constexpr Space kUconfig{0xC000, 0x4000};

bool set_space(std::uint8_t op, Space &s) {
    switch (op) {
    case 0x68: s = kConfig; return true;
    case 0x69: s = kContext; return true;
    case 0x76:
    case 0x9b: s = kSh; return true;
    case 0x79:
    case 0x7a: s = kUconfig; return true;
    default: return false;
    }
}

bool load_index_space(std::uint8_t op, Space &s) {
    switch (op) {
    case 0x9f: s = kContext; return true;
    case 0x63: s = kSh; return true;
    case 0x64: s = kUconfig; return true;
    default: return false;
    }
}

} // namespace

Mode parse_mode(const char *value) {
    if (!env_on(value)) {
        return Mode::Off;
    }
    return std::strcmp(value, "fatal") == 0 ? Mode::Fatal : Mode::Log;
}

#ifdef _MSC_VER
#pragma warning(push)
#pragma warning(disable : 4996) // getenv: read once, at the first IB
#endif
Mode mode() {
    static const Mode m = parse_mode(std::getenv("BC5_REG_CATCH"));
    return m;
}
#ifdef _MSC_VER
#pragma warning(pop)
#endif

Finding check(const std::uint32_t *p, std::uint32_t len,
              const std::function<bool(std::uint64_t, std::uint64_t)> &mapped) {
    Finding f;
    if (len < 2 || (p[0] >> 30) != 3) {
        return f;
    }
    const auto op = static_cast<std::uint8_t>((p[0] >> 8) & 0xFFu);
    Space s{};
    if (set_space(op, s)) {
        // dword 1: register offset relative to the space (low 16 bits; the index field above).
        const std::uint32_t first = p[1] & 0xFFFFu;
        const std::uint32_t count = len - 2;
        if (first >= s.size || count > s.size - first) {
            f.reason = "SET_* writes outside its register space";
            f.reg = first;
            f.index = first >= s.size ? 0 : s.size - first;
        }
        return f;
    }
    if (load_index_space(op, s) && len >= 5 && (p[3] & 0x80000000u) != 0) {
        const std::uint64_t a = (static_cast<std::uint64_t>(p[1]) & ~3ull) |
                                (static_cast<std::uint64_t>(p[2]) << 32);
        const std::uint32_t count = p[4] & 0x3FFFu;
        if (count == 0 || a == 0 || !mapped || !mapped(a, 8ull * count)) {
            return f; // the list is not readable here: not checked
        }
        const auto *pairs = reinterpret_cast<const std::uint32_t *>(static_cast<std::uintptr_t>(a));
        for (std::uint32_t k = 0; k < count; ++k) {
            const std::uint32_t off = pairs[2 * k];
            if (off >= s.size) {
                f.reason = "LOAD_*_REG_INDEX list names a register outside its space";
                f.reg = off;
                f.index = k;
                return f;
            }
        }
    }
    return f;
}

} // namespace bc5::reg_catch
