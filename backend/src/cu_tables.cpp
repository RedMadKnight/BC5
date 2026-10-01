// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/cu_tables.hpp"

#include "bc5/policy.hpp"

#include <algorithm>
#include <utility>

namespace bc5::cu_tables {

namespace {

constexpr std::uint32_t kOpCondExec = 0x22;
constexpr std::uint32_t kOpLoadShReg = 0x5f;
constexpr std::uint32_t kOpLoadShRegIndex = 0x63;
constexpr std::uint32_t kShBase = 0x2c00; // mm index of SH register offset 0
constexpr std::uint32_t kMaxTable = 4096;

std::uint64_t address(std::uint32_t lo, std::uint32_t hi) {
    return (static_cast<std::uint64_t>(lo) & ~3ull) | (static_cast<std::uint64_t>(hi & 0xffffu) << 32);
}

} // namespace

std::vector<std::uint32_t> apply(std::span<const std::uint32_t> ib, std::uint32_t cu_mask,
                                 const Readable &readable, Stats &stats) {
    std::vector<std::uint32_t> out;
    if (cu_mask == 0xffffffffu) {
        out.assign(ib.begin(), ib.end());
        return out;
    }
    const std::size_t n = ib.size();
    out.reserve(n + 256);
    std::size_t cond_end = 0;
    std::size_t i = 0;
    while (i < n) {
        const std::uint32_t h = ib[i];
        const std::uint32_t type = h >> 30;
        const std::uint32_t count = (h >> 16) & 0x3fffu;
        std::size_t len = 1;
        if (type == 3 || type == 0) len = count == 0x3fffu ? 1 : count + 2;
        if (i + len > n) break;
        std::vector<std::pair<std::uint32_t, std::uint32_t>> masked; // (SH offset, masked value)
        if (type == 3 && count != 0x3fffu) {
            const std::uint32_t op = (h >> 8) & 0xffu;
            const std::uint32_t *p = &ib[i];
            auto consider = [&](std::uint32_t sh_offset, std::uint32_t value) {
                std::uint32_t v = value;
                if (policy::mask_cu_register(kShBase + sh_offset, v, cu_mask))
                    masked.emplace_back(sh_offset, v);
            };
            if (op == kOpCondExec && len >= 5) {
                cond_end = std::max(cond_end, i + len + (p[4] & 0x3fffu));
            } else if (op == kOpLoadShRegIndex && len >= 5) {
                const std::uint64_t a = address(p[1], p[2]);
                const std::uint32_t cnt = std::min(p[4] & 0xffffu, kMaxTable);
                const bool pairs = (p[3] >> 31) != 0;
                const std::uint64_t bytes = static_cast<std::uint64_t>(cnt) * (pairs ? 8 : 4);
                if (a != 0 && cnt != 0 && readable && readable(a, bytes)) {
                    const auto *m = reinterpret_cast<const volatile std::uint32_t *>(a);
                    for (std::uint32_t k = 0; k < cnt; ++k) {
                        if (pairs) consider(m[2 * k] & 0xffffu, m[2 * k + 1]);
                        else consider((p[3] & 0xffffu) + k, m[k]);
                    }
                } else if (a != 0 && cnt != 0) {
                    stats.unreadable++;
                }
            } else if (op == kOpLoadShReg && len >= 5) {
                const std::uint64_t a = address(p[1], p[2]);
                for (std::size_t k = 3; k + 1 < len; k += 2) {
                    const std::uint32_t reg = p[k] & 0xffffu;
                    const std::uint32_t cnt = std::min(p[k + 1], kMaxTable);
                    if (cnt == 0) continue;
                    const std::uint64_t at = a + static_cast<std::uint64_t>(reg) * 4;
                    if (a != 0 && readable && readable(at, static_cast<std::uint64_t>(cnt) * 4)) {
                        const auto *m = reinterpret_cast<const volatile std::uint32_t *>(at);
                        for (std::uint32_t q = 0; q < cnt; ++q) consider(reg + q, m[q]);
                    } else {
                        stats.unreadable++;
                    }
                }
            }
        }
        for (std::size_t k = 0; k < len; ++k) out.push_back(ib[i + k]);
        if (!masked.empty()) {
            if (i < cond_end) {
                stats.conditional++;
            } else {
                stats.loads++;
                for (const auto &[off, v] : masked) {
                    out.push_back(0xC0017600u); // PKT3(SET_SH_REG, 1, 0): offset, one value
                    out.push_back(off);
                    out.push_back(v);
                    stats.overrides++;
                    stats.inserted_dwords += 3;
                }
            }
        }
        i += len;
    }
    for (; i < n; ++i) out.push_back(ib[i]);
    return out;
}

} // namespace bc5::cu_tables
