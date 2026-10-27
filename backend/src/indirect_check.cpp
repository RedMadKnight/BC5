// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/indirect_check.hpp"

#include <algorithm>

namespace bc5::indirect_check {

namespace {

constexpr std::uint32_t kOpSetBase = 0x11;
constexpr std::uint32_t kOpDispatchIndirect = 0x16;
constexpr std::uint32_t kOpDrawIndirect = 0x24;
constexpr std::uint32_t kOpDrawIndexIndirect = 0x25;
constexpr std::uint32_t kOpCondExec = 0x22;

constexpr std::uint32_t kWriteData = 0xC0033700u; // PKT3(WRITE_DATA, 3, 0)
constexpr std::uint32_t kWriteDataMem = 5u << 8;  // DST_SEL memory
constexpr std::uint32_t kWrConfirm = 1u << 20;
constexpr std::uint32_t kCondWrite = 0xC0074500u; // PKT3(COND_WRITE, 7, 0)
constexpr std::uint32_t kGreater = 6;
constexpr std::uint32_t kPollMem = 1u << 4;
constexpr std::uint32_t kWriteMem = 1u << 8;
constexpr std::uint32_t kPfpSyncMe = 0xC0004200u; // PKT3(PFP_SYNC_ME, 0, 0)
constexpr std::uint32_t kCondExec = 0xC0032200u;  // PKT3(COND_EXEC, 3, 0), GFX7+ form

// The argument dwords the check compares for an indirect packet, 0 for other packets:
// DISPATCH_INDIRECT (GFX form, 3 dwords) x, y, z; DRAW_INDIRECT and DRAW_INDEX_INDIRECT (5 dwords)
// the vertex or index count and the instance count (Mesa radv_cs_emit_indirect_draw_packet; the
// arguments as VkDrawIndirectCommand / VkDrawIndexedIndirectCommand).
std::uint32_t checked_dims(std::uint32_t h, std::size_t len, bool compute_ring) {
    if (h >> 30 != 3)
        return 0;
    const std::uint32_t op = (h >> 8) & 0xff;
    if (op == kOpDispatchIndirect && len == (compute_ring ? 4u : 3u))
        return 3;
    if (compute_ring)
        return 0;
    if ((op == kOpDrawIndirect || op == kOpDrawIndexIndirect) && len == 5)
        return 2;
    return 0;
}

std::size_t packet_len(std::uint32_t h) {
    const std::uint32_t type = h >> 30;
    if (type == 3 || type == 0) {
        const std::uint32_t count = (h >> 16) & 0x3fff;
        return count == 0x3fff ? 1 : count + 2;
    }
    return 1;
}

} // namespace

std::vector<std::uint32_t> apply(std::span<const std::uint32_t> ib_in, std::uint64_t base_in,
                                 const std::uint32_t (&max)[3], const std::uint32_t (&draw_max)[2],
                                 std::vector<std::size_t> &flag_refs, Stats &stats,
                                 bool compute_ring, const ProductLimit *product) {
    // ADR 0010 section A: a COND_EXEC range whose grown count no longer fits has its own checked
    // packets NOP-ed (nothing of that range runs unchecked) and the pass runs again over the
    // rest; it used to give up on the whole IB, which in a chain is several buffers.
    std::vector<std::uint32_t> excluded; // ib_in with those packets NOP-ed, once needed
    std::span<const std::uint32_t> ib = ib_in;
    const Stats at_entry = stats;
    std::uint32_t dropped_total = 0;
    for (int attempt = 0; attempt < 64; ++attempt) {
    std::uint64_t base = base_in;
    std::uint32_t dispatches = 0;
    bool has_cond_exec = false;
    for (std::size_t i = 0; i < ib.size();) {
        const std::uint32_t h = ib[i];
        const std::size_t len = packet_len(h);
        const std::uint32_t op = (h >> 8) & 0xff;
        if (h >> 30 == 3 && op == kOpCondExec)
            has_cond_exec = true;
        if (checked_dims(h, len, compute_ring) != 0)
            dispatches++;
        i += len;
    }
    if (dispatches == 0)
        return {ib.begin(), ib.end()};
    std::vector<std::uint32_t> out;
    out.reserve(ib.size() + dispatches * (kCheckDwords + (product != nullptr ? kProductDwords : 0) + 2));
    // The IB's own COND_EXECs skip a count of dwords: a check inserted inside one's range grows it.
    // new_at[i]: where the packet at offset i starts in out, its inserted check included.
    std::vector<std::size_t> new_at;
    struct Cond {
        std::size_t old_start, old_end, at;
    };
    std::vector<Cond> conds;
    if (has_cond_exec)
        new_at.assign(ib.size() + 1, ~std::size_t{0});
    for (std::size_t i = 0; i < ib.size();) {
        const std::uint32_t h = ib[i];
        std::size_t len = packet_len(h);
        if (i + len > ib.size())
            len = ib.size() - i;
        const std::uint32_t op = (h >> 8) & 0xff;
        if (has_cond_exec)
            new_at[i] = out.size();
        if (h >> 30 == 3 && op == kOpCondExec && len == 5) {
            conds.push_back({i + len, i + len + (ib[i + 4] & 0x3fffu), out.size()});
        }
        if (h >> 30 == 3 && op == kOpSetBase && len >= 4 && (ib[i + 1] & 0xfu) == 1) {
            base = (static_cast<std::uint64_t>(ib[i + 2]) & ~3ull) |
                   (static_cast<std::uint64_t>(ib[i + 3] & 0xffffu) << 32);
        }
        if (const std::uint32_t dims = checked_dims(h, len, compute_ring); dims != 0) {
            const std::uint32_t *limit = dims == 3 ? max : draw_max;
            const std::size_t before = out.size();
            if (base != 0 || compute_ring) {
                const std::uint64_t args =
                    compute_ring ? (static_cast<std::uint64_t>(ib[i + 1]) & ~3ull) |
                                       (static_cast<std::uint64_t>(ib[i + 2] & 0xffffu) << 32)
                                 : base + ib[i + 1];
                const auto flag_at = [&out, &flag_refs](std::uint32_t off) {
                    flag_refs.push_back(out.size());
                    out.push_back(off); // lo: the offset of the word, patch() adds the flag's address
                    out.push_back(0);   // hi
                };
                const auto flag = [&flag_at] { flag_at(0); };
                const bool stair = product != nullptr && dims == 3 && !compute_ring;
                out.insert(out.end(), {kWriteData, kWriteDataMem});
                flag();
                out.push_back(1);
                if (stair) { // experiment 0341: flag2 = 0
                    out.insert(out.end(), {kWriteData, kWriteDataMem});
                    flag_at(8);
                    out.push_back(0);
                }
                for (std::uint32_t k = 0; k < dims; ++k) {
                    const std::uint64_t a = args + 4 * k;
                    out.insert(out.end(), {kCondWrite, kGreater | kPollMem | kWriteMem,
                                           static_cast<std::uint32_t>(a) & ~3u,
                                           static_cast<std::uint32_t>(a >> 32) & 0xffffu, limit[k],
                                           0xffffffffu});
                    flag();
                    out.push_back(0);
                }
                if (stair) { // experiment 0341: the staircase
                    for (std::uint32_t k = 1; k < 3; ++k) { // y, z > yz_min ? flag2 = 1
                        const std::uint64_t a = args + 4 * k;
                        out.insert(out.end(), {kCondWrite, kGreater | kPollMem | kWriteMem,
                                               static_cast<std::uint32_t>(a) & ~3u,
                                               static_cast<std::uint32_t>(a >> 32) & 0xffffu,
                                               product->yz_min, 0xffffffffu});
                        flag_at(8);
                        out.push_back(1);
                    }
                    out.insert(out.end(), {kWriteData, kWriteDataMem | kWrConfirm});
                    flag_at(12); // confirm2: the flag's address + 12
                    out.push_back(0);
                    out.insert(out.end(), {kPfpSyncMe, 0u});
                    out.push_back(kCondExec); // flag2 != 0: the x check below runs
                    flag_at(8);
                    out.insert(out.end(), {0u, 9u});
                    out.insert(out.end(), {kCondWrite, kGreater | kPollMem | kWriteMem, // x > x_limit ? flag = 0
                                           static_cast<std::uint32_t>(args) & ~3u,
                                           static_cast<std::uint32_t>(args >> 32) & 0xffffu,
                                           product->x_limit, 0xffffffffu});
                    flag();
                    out.push_back(0);
                    stats.product_checked++;
                }
                out.insert(out.end(), {kWriteData, kWriteDataMem | kWrConfirm});
                flag_at(4); // the confirm word: the flag's address + 4
                out.push_back(0);
                if (!compute_ring)
                    out.insert(out.end(), {kPfpSyncMe, 0u});
                out.push_back(kCondExec);
                flag();
                out.insert(out.end(), {0u, static_cast<std::uint32_t>(len)});
                stats.checked++;
            } else {
                out.insert(out.end(), {kPfpSyncMe, 0u});
                stats.unbased++;
            }
            stats.inserted_dwords += static_cast<std::uint32_t>(out.size() - before);
        }
        out.insert(out.end(), ib.begin() + static_cast<std::ptrdiff_t>(i),
                   ib.begin() + static_cast<std::ptrdiff_t>(i + len));
        i += len;
    }
    if (has_cond_exec) {
        new_at[ib.size()] = out.size();
        std::vector<std::pair<std::size_t, std::size_t>> overflow; // old [start, end) of such ranges
        for (const Cond &c : conds) {
            std::size_t e = c.old_end < ib.size() ? c.old_end : ib.size();
            while (new_at[e] == ~std::size_t{0})
                e++; // a range ending inside a packet: to its end
            const std::size_t count = new_at[e] - (c.at + 5);
            if (count > 0x3fffu)
                overflow.emplace_back(c.old_start, e);
            out[c.at + 4] =
                (out[c.at + 4] & ~0x3fffu) | static_cast<std::uint32_t>(count & 0x3fffu);
        }
        if (!overflow.empty()) { // those ranges' checked packets are NOP-ed; the rest is redone
            if (excluded.empty())
                excluded.assign(ib_in.begin(), ib_in.end());
            std::uint32_t dropped = 0;
            for (std::size_t i = 0; i < excluded.size();) {
                const std::size_t len = packet_len(excluded[i]);
                bool inside = false;
                for (const auto &[lo, hi] : overflow)
                    inside = inside || (i >= lo && i < hi);
                if (inside && checked_dims(excluded[i], len, compute_ring) != 0) {
                    excluded[i] = 0xC0001000u | (static_cast<std::uint32_t>(len - 2) << 16); // NOP
                    dropped++;
                }
                i += len;
            }
            flag_refs.clear();
            dropped_total += dropped;
            stats = at_entry;
            stats.conditional += dropped_total;
            if (dropped == 0) // cannot happen: a range holds the packet whose check grew it
                break;
            ib = excluded;
            continue;
        }
    }
    return out;
    }
    // no fit in 64 attempts: every checked packet NOP-ed, as the whole-IB fallback did
    std::vector<std::uint32_t> out(ib_in.begin(), ib_in.end());
    flag_refs.clear();
    stats = at_entry;
    for (std::size_t i = 0; i < out.size();) {
        const std::size_t len = packet_len(out[i]);
        if (checked_dims(out[i], len, compute_ring) != 0) {
            out[i] = 0xC0001000u | (static_cast<std::uint32_t>(len - 2) << 16); // NOP
            stats.conditional++;
        }
        i += len;
    }
    return out;
}

bool insert_before(std::vector<std::uint32_t> &ib, const std::vector<Insert> &inserts) {
    if (inserts.empty())
        return true;
    std::vector<std::uint32_t> out;
    std::size_t extra = 0;
    for (const Insert &in : inserts)
        extra += in.words.size();
    out.reserve(ib.size() + extra);
    std::vector<std::size_t> new_at(ib.size() + 1, ~std::size_t{0});
    struct Cond {
        std::size_t old_start, old_end, at;
    };
    std::vector<Cond> conds;
    std::size_t next = 0;
    for (std::size_t i = 0; i < ib.size();) {
        std::size_t len = packet_len(ib[i]);
        if (i + len > ib.size())
            len = ib.size() - i;
        new_at[i] = out.size();
        while (next < inserts.size() && inserts[next].at <= i) {
            if (inserts[next].at == i) {
                out.insert(out.end(), inserts[next].words.begin(), inserts[next].words.end());
            }
            next++;
        }
        if (ib[i] >> 30 == 3 && ((ib[i] >> 8) & 0xff) == kOpCondExec && len == 5) {
            conds.push_back({i + len, i + len + (ib[i + 4] & 0x3fffu), out.size()});
        }
        out.insert(out.end(), ib.begin() + static_cast<std::ptrdiff_t>(i),
                   ib.begin() + static_cast<std::ptrdiff_t>(i + len));
        i += len;
    }
    new_at[ib.size()] = out.size();
    while (next < inserts.size()) { // experiment 0341: inserts at the IB's end, after every range
        out.insert(out.end(), inserts[next].words.begin(), inserts[next].words.end());
        next++;
    }
    for (const Cond &c : conds) {
        std::size_t e = c.old_end < ib.size() ? c.old_end : ib.size();
        while (new_at[e] == ~std::size_t{0})
            e++;
        const std::size_t count = new_at[e] - (c.at + 5);
        if (count > 0x3fffu)
            return false;
        out[c.at + 4] = (out[c.at + 4] & ~0x3fffu) | static_cast<std::uint32_t>(count);
    }
    ib.swap(out);
    return true;
}

void patch(std::span<std::uint32_t> ib, const std::vector<std::size_t> &flag_refs,
           std::uint64_t flag_va) {
    for (const std::size_t r : flag_refs) {
        if (r + 1 >= ib.size())
            continue;
        const std::uint64_t a = flag_va + ib[r]; // ib[r] holds 0, or 4 for the confirm word
        ib[r] = static_cast<std::uint32_t>(a);
        ib[r + 1] = static_cast<std::uint32_t>(a >> 32) & 0xffffu;
    }
}

} // namespace bc5::indirect_check
