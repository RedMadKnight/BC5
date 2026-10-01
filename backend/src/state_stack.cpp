// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/state_stack.hpp"

#include "bc5/policy.hpp"

#include <algorithm>

namespace bc5::state_stack {

namespace {

constexpr std::uint32_t kOpClearState = 0x12;
constexpr std::uint32_t kOpCondExec = 0x22;
constexpr std::uint32_t kOpLoadContextReg = 0x61;
constexpr std::uint32_t kOpSetContextReg = 0x69;
constexpr std::uint32_t kOpLoadContextRegIndex = 0x9f;
constexpr std::size_t kMaxDepth = 8;
constexpr std::uint32_t kMaxTable = 4096;

std::uint64_t address(std::uint32_t lo, std::uint32_t hi) {
    return (static_cast<std::uint64_t>(lo) & ~3ull) | (static_cast<std::uint64_t>(hi & 0xffffu) << 32);
}

// SET_CONTEXT_REG packets for every valid register of a snapshot, one per run.
void emit_restore(const Context &c, std::vector<std::uint32_t> &out, Stats &stats) {
    for (std::size_t r = 0; r < kContextRegs;) {
        if (!c.valid.test(r)) {
            ++r;
            continue;
        }
        std::size_t e = r;
        while (e < kContextRegs && c.valid.test(e)) ++e;
        const auto n = static_cast<std::uint32_t>(e - r);
        out.push_back(0xC0006900u | (n << 16)); // PKT3(SET_CONTEXT_REG, n, 0): offset + n values
        out.push_back(static_cast<std::uint32_t>(r));
        for (std::size_t k = r; k < e; ++k) out.push_back(c.value[k]);
        stats.restored_regs += n;
        stats.inserted_dwords += n + 2;
        r = e;
    }
}

} // namespace

std::vector<std::uint32_t> Tracker::apply(std::span<const std::uint32_t> src,
                                          std::span<const std::uint32_t> filtered,
                                          const Readable &readable, Stats &stats) {
    std::vector<std::uint32_t> out;
    const std::size_t n = std::min(src.size(), filtered.size());
    out.reserve(n + 2048);
    std::size_t cond_end = 0; // packets before this offset sit inside a COND_EXEC range
    std::size_t i = 0;
    while (i < n) {
        const std::uint32_t h = src[i];
        const std::uint32_t type = h >> 30;
        const std::uint32_t count = (h >> 16) & 0x3fffu;
        std::size_t len = 1;
        if (type == 3 || type == 0) len = count == 0x3fffu ? 1 : count + 2;
        if (i + len > n) break; // truncated: the filter NOP-ed the rest
        const bool packet = type == 3 && count != 0x3fffu;
        const bool live = packet && filtered[i] != policy::kNop;
        const bool conditional = i < cond_end;
        bool replaced = false;
        if (live) {
            const std::uint32_t op = (h >> 8) & 0xffu;
            const std::uint32_t *p = &src[i];
            if (op == kOpCondExec && len >= 5) {
                // addr lo, addr hi, reserved, EXEC_COUNT: the next EXEC_COUNT dwords run only if
                // the dword at the address is not zero.
                cond_end = std::max(cond_end, i + len + (p[4] & 0x3fffu));
            } else if (op == kOpClearState && len >= 2) {
                const std::uint32_t cmd = p[1] & 0xfu;
                if (conditional) {
                    stats.conditional++;
                } else if (cmd == 1) {
                    if (stack_.size() < kMaxDepth) stack_.push_back(ctx_);
                    stats.pushes++;
                    ctx_.valid.reset(); // the filter's cmd 0 runs: the kernel's clear state
                } else if (cmd == 2 && !stack_.empty()) {
                    ctx_ = stack_.back();
                    stack_.pop_back();
                    stats.pops++;
                    for (std::size_t k = 0; k < len; ++k) out.push_back(policy::kNop);
                    emit_restore(ctx_, out, stats);
                    replaced = true;
                } else {
                    if (cmd == 2) stats.unmatched_pops++;
                    ctx_.valid.reset();
                }
            } else if (!conditional && op == kOpSetContextReg && len >= 3) {
                const std::uint32_t reg = p[1] & 0xffffu;
                for (std::size_t k = 2; k < len; ++k)
                    set(reg + static_cast<std::uint32_t>(k - 2), filtered[i + k]);
            } else if (!conditional && op == kOpLoadContextRegIndex && len >= 5) {
                // addr lo (| index), addr hi, reg offset | DATA_FORMAT << 31, count. DATA_FORMAT 1:
                // the memory holds (offset, value) pairs; 0: values for consecutive registers.
                const std::uint64_t a = address(p[1], p[2]);
                const std::uint32_t cnt = std::min(p[4] & 0xffffu, kMaxTable);
                const bool pairs = (p[3] >> 31) != 0;
                const std::uint64_t bytes = static_cast<std::uint64_t>(cnt) * (pairs ? 8 : 4);
                if (a != 0 && cnt != 0 && readable && readable(a, bytes)) {
                    const auto *m = reinterpret_cast<const volatile std::uint32_t *>(a);
                    for (std::uint32_t k = 0; k < cnt; ++k) {
                        if (pairs) set(m[2 * k] & 0xffffu, m[2 * k + 1]);
                        else set((p[3] & 0xffffu) + k, m[k]);
                    }
                    stats.tables++;
                } else if (a != 0 && cnt != 0) {
                    stats.unreadable_tables++;
                }
            } else if (!conditional && op == kOpLoadContextReg && len >= 5) {
                // addr lo, addr hi, then (reg offset, count) pairs: values at addr + offset * 4.
                const std::uint64_t a = address(p[1], p[2]);
                for (std::size_t k = 3; k + 1 < len; k += 2) {
                    const std::uint32_t reg = p[k] & 0xffffu;
                    const std::uint32_t cnt = std::min(p[k + 1], kMaxTable);
                    if (cnt == 0) continue;
                    const std::uint64_t at = a + static_cast<std::uint64_t>(reg) * 4;
                    if (a != 0 && readable && readable(at, static_cast<std::uint64_t>(cnt) * 4)) {
                        const auto *m = reinterpret_cast<const volatile std::uint32_t *>(at);
                        for (std::uint32_t q = 0; q < cnt; ++q) set(reg + q, m[q]);
                        stats.tables++;
                    } else {
                        stats.unreadable_tables++;
                    }
                }
            }
        }
        if (!replaced) {
            for (std::size_t k = 0; k < len; ++k) out.push_back(filtered[i + k]);
        }
        i += len;
    }
    for (; i < n; ++i) out.push_back(filtered[i]);
    return out;
}

} // namespace bc5::state_stack
