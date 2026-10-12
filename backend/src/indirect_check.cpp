// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/indirect_check.hpp"

namespace bc5::indirect_check {

namespace {

constexpr std::uint32_t kOpSetBase = 0x11;
constexpr std::uint32_t kOpDispatchIndirect = 0x16;
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

std::size_t packet_len(std::uint32_t h) {
    const std::uint32_t type = h >> 30;
    if (type == 3 || type == 0) {
        const std::uint32_t count = (h >> 16) & 0x3fff;
        return count == 0x3fff ? 1 : count + 2;
    }
    return 1;
}

} // namespace

std::vector<std::uint32_t> apply(std::span<const std::uint32_t> ib, std::uint64_t base,
                                 const std::uint32_t (&max)[3], std::vector<std::size_t> &flag_refs,
                                 Stats &stats) {
    std::uint32_t dispatches = 0;
    bool has_cond_exec = false;
    for (std::size_t i = 0; i < ib.size();) {
        const std::uint32_t h = ib[i];
        const std::size_t len = packet_len(h);
        const std::uint32_t op = (h >> 8) & 0xff;
        if (h >> 30 == 3 && op == kOpCondExec)
            has_cond_exec = true;
        if (h >> 30 == 3 && op == kOpDispatchIndirect && len == 3)
            dispatches++;
        i += len;
    }
    if (dispatches == 0)
        return {ib.begin(), ib.end()};
    std::vector<std::uint32_t> out;
    out.reserve(ib.size() + dispatches * (kCheckDwords + 2));
    // The IB's own COND_EXECs skip a count of dwords: a check inserted inside one's range grows it.
    // new_at[i]: where the packet at offset i starts in out, its inserted check included.
    std::vector<std::size_t> new_at;
    struct Cond {
        std::size_t old_end, at;
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
            conds.push_back({i + len + (ib[i + 4] & 0x3fffu), out.size()});
        }
        if (h >> 30 == 3 && op == kOpSetBase && len >= 4 && (ib[i + 1] & 0xfu) == 1) {
            base = (static_cast<std::uint64_t>(ib[i + 2]) & ~3ull) |
                   (static_cast<std::uint64_t>(ib[i + 3] & 0xffffu) << 32);
        }
        if (h >> 30 == 3 && op == kOpDispatchIndirect && len == 3) {
            const std::size_t before = out.size();
            if (base != 0) {
                const std::uint64_t args = base + ib[i + 1];
                const auto flag = [&out, &flag_refs] {
                    flag_refs.push_back(out.size());
                    out.push_back(0); // lo, filled in by patch()
                    out.push_back(0); // hi
                };
                out.insert(out.end(), {kWriteData, kWriteDataMem});
                flag();
                out.push_back(1);
                for (std::uint32_t k = 0; k < 3; ++k) {
                    const std::uint64_t a = args + 4 * k;
                    out.insert(out.end(), {kCondWrite, kGreater | kPollMem | kWriteMem,
                                           static_cast<std::uint32_t>(a) & ~3u,
                                           static_cast<std::uint32_t>(a >> 32) & 0xffffu, max[k],
                                           0xffffffffu});
                    flag();
                    out.push_back(0);
                }
                out.insert(out.end(), {kWriteData, kWriteDataMem | kWrConfirm});
                flag_refs.push_back(out.size());
                out.push_back(
                    4); // the confirm word: the flag's address + 4 (patch() adds the base)
                out.push_back(0);
                out.push_back(0);
                out.insert(out.end(), {kPfpSyncMe, 0u, kCondExec});
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
        bool fits = true;
        for (const Cond &c : conds) {
            std::size_t e = c.old_end < ib.size() ? c.old_end : ib.size();
            while (new_at[e] == ~std::size_t{0})
                e++; // a range ending inside a packet: to its end
            const std::size_t count = new_at[e] - (c.at + 5);
            if (count > 0x3fffu)
                fits = false;
            out[c.at + 4] =
                (out[c.at + 4] & ~0x3fffu) | static_cast<std::uint32_t>(count & 0x3fffu);
        }
        if (!fits) { // a grown range no longer fits the count: no dispatch of this IB runs
                     // unchecked
            out.assign(ib.begin(), ib.end());
            flag_refs.clear();
            for (std::size_t i = 0; i < out.size();) {
                const std::size_t len = packet_len(out[i]);
                if (out[i] >> 30 == 3 && ((out[i] >> 8) & 0xff) == kOpDispatchIndirect &&
                    len == 3) {
                    out[i] = 0xC0011000u; // PKT3(NOP, 1, 0) over the 3 dwords
                }
                i += len;
            }
            stats.conditional += dispatches;
            stats.checked = 0;
            stats.unbased = 0;
            stats.inserted_dwords = 0;
        }
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
        std::size_t old_end, at;
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
            conds.push_back({i + len + (ib[i + 4] & 0x3fffu), out.size()});
        }
        out.insert(out.end(), ib.begin() + static_cast<std::ptrdiff_t>(i),
                   ib.begin() + static_cast<std::ptrdiff_t>(i + len));
        i += len;
    }
    new_at[ib.size()] = out.size();
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
