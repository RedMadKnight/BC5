// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/host_indirect.hpp"

#include "bc5/indirect_check.hpp"

#include <algorithm>

namespace bc5::host_indirect {

namespace {

constexpr std::uint32_t kOpSetBase = 0x11;
constexpr std::uint32_t kOpDispatchIndirect = 0x16;
constexpr std::uint32_t kOpSetShReg = 0x76;
constexpr std::uint32_t kShComputePgmLo = 0x20c;
constexpr std::uint32_t kNopHeader = 0xC0001000u; // PKT3(NOP, 0, 0); count = the packet's length - 2
constexpr std::uint64_t kPageMask = ~0xfffull;

std::size_t packet_len(std::uint32_t h) {
    const std::uint32_t type = h >> 30;
    if (type == 3 || type == 0) {
        const std::uint32_t count = (h >> 16) & 0x3fff;
        return count == 0x3fff ? 1 : count + 2;
    }
    return 1;
}

bool sane(const std::uint32_t (&c)[3], const Limits &l) {
    if (c[0] > l.per_dim || c[1] > l.per_dim || c[2] > l.per_dim)
        return false;
    const std::uint64_t xy = static_cast<std::uint64_t>(c[0]) * c[1];
    if (xy > l.product)
        return false;
    return xy * c[2] <= l.product;
}

} // namespace

const Region *region_of(const std::vector<Region> &regions, std::uint64_t va, std::uint64_t bytes) {
    auto it = std::upper_bound(regions.begin(), regions.end(), va,
                               [](std::uint64_t a, const Region &r) { return a < r.va; });
    if (it == regions.begin())
        return nullptr;
    --it;
    return va >= it->va && va + bytes <= it->va + it->size ? &*it : nullptr;
}

std::vector<Resolution> resolve_indirect(std::span<const std::uint32_t> ib, const Register &carried,
                                         std::uint64_t window, const std::vector<Region> &regions,
                                         const Reader &read, const Limits &limits, Stats &stats) {
    std::vector<Resolution> out;
    Register reg = carried;
    std::uint64_t program = 0;
    for (std::size_t i = 0; i < ib.size();) {
        const std::uint32_t h = ib[i];
        std::size_t len = packet_len(h);
        if (i + len > ib.size())
            len = ib.size() - i;
        if (h >> 30 != 3) {
            i += len;
            continue;
        }
        const std::uint32_t op = (h >> 8) & 0xff;
        if (op == kOpSetBase && len >= 4 && (ib[i + 1] & 0xfu) == 1) {
            const std::uint64_t a = (static_cast<std::uint64_t>(ib[i + 2]) & ~3ull) |
                                    (static_cast<std::uint64_t>(ib[i + 3] & 0xffffu) << 32);
            reg.base = a;
            reg.zeroed = a == 0;
            if (a != 0)
                stats.window_seen = a & ~0xffffffffull;
        } else if (op == kOpSetShReg && len >= 3) {
            const std::uint32_t first = ib[i + 1] & 0xffffu;
            for (std::size_t k = 0; k + 2 < len; ++k) {
                if (first + k == kShComputePgmLo)
                    program = (program & ~0xffffffff00ull) | (static_cast<std::uint64_t>(ib[i + 2 + k]) << 8);
                if (first + k == kShComputePgmLo + 1)
                    program = (program & 0xffffffff00ull) | (static_cast<std::uint64_t>(ib[i + 2 + k] & 0xffu) << 40);
            }
        } else if (op == kOpDispatchIndirect && len == 3) {
            Resolution r;
            r.at = i;
            r.shader_type = (h >> 1) & 1u;
            r.program = program;
            r.base = reg.base;
            if (reg.base != 0) {
                r.address = reg.base + ib[i + 1];
                r.decision = Decision::Leave;
                r.why = Why::NonZero;
                stats.left_nonzero++;
            } else if (!reg.zeroed) {
                r.address = ib[i + 1];
                r.decision = Decision::Leave;
                r.why = Why::NeverSet;
                stats.left_never_set++;
            } else {
                r.window = window;
                if (window == 0) {
                    r.address = ib[i + 1];
                    r.decision = Decision::Drop;
                    r.why = Why::NoCandidate;
                    stats.dropped_no_candidate++;
                } else {
                    r.address = window + ib[i + 1];
                    r.page = r.address & kPageMask;
                    if (region_of(regions, r.address, 12) == nullptr) {
                        r.decision = Decision::Drop;
                        r.why = Why::NotRealMapping;
                        stats.dropped_unmapped++;
                    } else if (!read || !read(r.address, r.counts)) {
                        r.decision = Decision::Drop;
                        r.why = Why::Unreadable;
                        stats.dropped_unreadable++;
                    } else if (!sane(r.counts, limits)) {
                        r.decision = Decision::Drop;
                        r.why = Why::Insane;
                        stats.dropped_insane++;
                    } else {
                        r.decision = Decision::Rewrite;
                        r.why = Why::Verified;
                        stats.rewritten++;
                    }
                }
            }
            out.push_back(r);
        }
        i += len;
    }
    stats.register_out = reg;
    return out;
}

bool rewrite_verified(std::vector<std::uint32_t> &ib, const std::vector<Resolution> &decisions, Stats &stats) {
    std::vector<indirect_check::Insert> inserts;
    const auto nop = [&ib](std::size_t at) {
        const std::size_t len = packet_len(ib[at]);
        ib[at] = kNopHeader | (static_cast<std::uint32_t>(len - 2) << 16);
    };
    for (const Resolution &r : decisions) {
        if (r.at + 3 > ib.size())
            continue;
        if (r.decision == Decision::Drop) {
            nop(r.at);
        } else if (r.decision == Decision::Rewrite) {
            const std::uint32_t header = r.shader_type != 0 ? kSetBaseCompute : kSetBaseGfx;
            ib[r.at + 1] = static_cast<std::uint32_t>(r.address - r.page);
            inserts.push_back({r.at, {header, 1u, static_cast<std::uint32_t>(r.page),
                                      static_cast<std::uint32_t>(r.page >> 32) & 0xffffu}});
            inserts.push_back({r.at + 3, {header, 1u, 0u, 0u}}); // the register back to 0, as the title left it
        }
    }
    if (inserts.empty())
        return true;
    if (indirect_check::insert_before(ib, inserts))
        return true;
    for (const Resolution &r : decisions) { // a COND_EXEC count would overflow: the rewrites run nowhere instead
        if (r.decision == Decision::Rewrite && r.at + 3 <= ib.size()) {
            ib[r.at + 1] = static_cast<std::uint32_t>(r.address - r.window); // the offset as it was
            nop(r.at);
            stats.nop_on_overflow++;
        }
    }
    return false;
}

} // namespace bc5::host_indirect
