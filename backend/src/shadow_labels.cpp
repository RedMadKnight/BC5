// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/shadow_labels.hpp"

#include "bc5/indirect_check.hpp"

#include <algorithm>

namespace bc5::shadow_labels {

namespace {

constexpr std::uint32_t kOpWriteData = 0x37;
constexpr std::uint32_t kOpWaitRegMem = 0x3c;
constexpr std::uint32_t kOpReleaseMem = 0x49;
constexpr std::uint32_t kOpWaitRegMem64 = 0x93;

std::size_t packet_len(std::uint32_t h) {
    const std::uint32_t type = h >> 30;
    if (type == 3 || type == 0) {
        const std::uint32_t count = (h >> 16) & 0x3fff;
        return count == 0x3fff ? 1 : count + 2;
    }
    return 1;
}

std::uint64_t address_at(const std::uint32_t *p, std::size_t lo) {
    return (static_cast<std::uint64_t>(p[lo]) & ~3ull) |
           (static_cast<std::uint64_t>(p[lo + 1] & 0xffffu) << 32);
}

// The label a type-3 packet writes (RELEASE_MEM with a 32- or 64-bit value, WRITE_DATA to memory)
// and the index of its address lo dword; 0 for other packets.
std::uint64_t written_label(const std::uint32_t *p, std::size_t len, std::size_t &lo) {
    if (p[0] >> 30 != 3)
        return 0;
    const std::uint32_t op = (p[0] >> 8) & 0xff;
    if (op == kOpReleaseMem && len >= 6) {
        const std::uint32_t data_sel = (p[2] >> 29) & 7u;
        if (data_sel != 1 && data_sel != 2)
            return 0;
        lo = 3;
        return address_at(p, 3);
    }
    if (op == kOpWriteData && len >= 5) {
        const std::uint32_t dst_sel = (p[1] >> 8) & 0xf;
        if (dst_sel != 1 && dst_sel != 2 && dst_sel != 5)
            return 0;
        lo = 2;
        return address_at(p, 2);
    }
    return 0;
}

// The label a memory-space WAIT_REG_MEM[64] polls, and the index of its address lo dword.
std::uint64_t waited_label(const std::uint32_t *p, std::size_t len, std::size_t &lo) {
    if (p[0] >> 30 != 3)
        return 0;
    const std::uint32_t op = (p[0] >> 8) & 0xff;
    if ((op != kOpWaitRegMem && op != kOpWaitRegMem64) || len < 7)
        return 0;
    if (((p[1] >> 4) & 1u) == 0)
        return 0; // a register poll
    lo = 2;
    return address_at(p, 2);
}

} // namespace

bool apply(std::vector<std::uint32_t> &ib, std::uint32_t max_slots, Stats &stats) {
    struct Writer {
        std::size_t at, len, lo;
        std::uint64_t label;
    };
    struct Wait {
        std::size_t at, lo;
        std::uint64_t label;
    };
    std::vector<Writer> writers;
    std::vector<Wait> waits;
    for (std::size_t i = 0; i < ib.size();) {
        std::size_t len = packet_len(ib[i]);
        if (i + len > ib.size())
            len = ib.size() - i;
        std::size_t lo = 0;
        if (const std::uint64_t label = written_label(&ib[i], len, lo); label != 0)
            writers.push_back({i, len, lo, label});
        else if (const std::uint64_t w = waited_label(&ib[i], len, lo); w != 0)
            waits.push_back({i, lo, w});
        i += len;
    }
    if (waits.empty())
        return true;
    // the labels: those a writer precedes, in order of first wait
    std::vector<std::uint64_t> labels;
    for (const Wait &w : waits) {
        if (std::find(labels.begin(), labels.end(), w.label) != labels.end())
            continue;
        bool written = false;
        for (const Writer &wr : writers)
            written = written || (wr.label == w.label && wr.at < w.at);
        if (!written)
            continue;
        if (labels.size() >= max_slots) {
            stats.overflow++;
            continue;
        }
        labels.push_back(w.label);
    }
    if (labels.empty())
        return true;
    auto slot_of = [&labels](std::uint64_t label) -> std::uint32_t {
        const auto it = std::find(labels.begin(), labels.end(), label);
        return it == labels.end() ? ~0u : static_cast<std::uint32_t>(it - labels.begin());
    };
    // the copies: each writer of a shadowed label followed by the same packet at the slot
    std::vector<indirect_check::Insert> inserts;
    std::uint32_t writes = 0;
    for (const Writer &wr : writers) {
        const std::uint32_t slot = slot_of(wr.label);
        if (slot == ~0u)
            continue;
        indirect_check::Insert in;
        in.at = wr.at; // right before the writer: inside the same COND_EXEC range as it, so that a
                       // skipped writer's copy is skipped too (a copy after the range would not be)
        in.words.assign(ib.begin() + static_cast<std::ptrdiff_t>(wr.at),
                        ib.begin() + static_cast<std::ptrdiff_t>(wr.at + wr.len));
        in.words[wr.lo] = static_cast<std::uint32_t>(kSlotBytes * slot);
        in.words[wr.lo + 1] = kMarkerHi;
        inserts.push_back(std::move(in));
        writes++;
    }
    // the waits: redirected in place first (the copy keeps the offsets of the originals)
    std::vector<std::pair<std::size_t, std::uint32_t>> redirected; // (lo index, slot)
    for (const Wait &w : waits) {
        const std::uint32_t slot = slot_of(w.label);
        if (slot == ~0u)
            continue;
        bool written = false; // a wait before the label's first writer keeps the title's label:
        for (const Writer &wr : writers) // it may wait on an earlier job's value (keep_wait_offsets)
            written = written || (wr.label == w.label && wr.at < w.at);
        if (!written)
            continue;
        redirected.emplace_back(w.at + w.lo, slot);
    }
    for (const auto &[lo, slot] : redirected) {
        ib[lo] = static_cast<std::uint32_t>(kSlotBytes * slot);
        ib[lo + 1] = kMarkerHi;
    }
    if (!indirect_check::insert_before(ib, inserts)) {
        // insert_before left ib unchanged, but the waits were rewritten above: restore them
        for (const Wait &w : waits) {
            if (ib[w.at + w.lo + 1] != kMarkerHi)
                continue;
            ib[w.at + w.lo] = static_cast<std::uint32_t>(w.label & 0xffffffffu);
            ib[w.at + w.lo + 1] = static_cast<std::uint32_t>(w.label >> 32);
        }
        stats.failed = true;
        return false;
    }
    stats.labels += static_cast<std::uint32_t>(labels.size());
    stats.writes += writes;
    stats.waits += static_cast<std::uint32_t>(redirected.size());
    return true;
}

std::uint32_t patch(std::span<std::uint32_t> ib, std::uint64_t shadow_va) {
    std::uint32_t slots = 0;
    for (std::size_t i = 0; i < ib.size();) {
        std::size_t len = packet_len(ib[i]);
        if (i + len > ib.size())
            len = ib.size() - i;
        std::size_t lo = 0;
        bool marked = false;
        if (ib[i] >> 30 == 3) {
            const std::uint32_t op = (ib[i] >> 8) & 0xff;
            if (op == kOpReleaseMem && len >= 6) {
                lo = 3;
                marked = true;
            } else if (op == kOpWriteData && len >= 5) {
                lo = 2;
                marked = true;
            } else if ((op == kOpWaitRegMem || op == kOpWaitRegMem64) && len >= 7) {
                lo = 2;
                marked = true;
            }
        }
        if (marked && ib[i + lo + 1] == kMarkerHi) {
            const std::uint32_t slot = static_cast<std::uint32_t>(ib[i + lo] / kSlotBytes);
            const std::uint64_t a = shadow_va + kSlotBytes * slot;
            ib[i + lo] = static_cast<std::uint32_t>(a);
            ib[i + lo + 1] = static_cast<std::uint32_t>(a >> 32) & 0xffffu;
            slots = std::max(slots, slot + 1);
        }
        i += len;
    }
    return slots;
}

} // namespace bc5::shadow_labels
