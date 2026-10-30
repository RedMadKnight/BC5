// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0381 (F679): the graphics queue's compute registers after a merged async compute
// buffer. With BC5_DIRECT_COMPUTE_RING=-1 (exp 0342) the title's acbs run on the GFX ring and
// share its COMPUTE_* SH registers; on the console an acb runs on its own queue, so a dcb may
// dispatch with the user data an earlier dcb left (the second title's 0x909977100 inherits
// COMPUTE_USER_DATA_0 = 0x11, and after an acb it got 0x11d00860 and faulted at 0x860xxxxxxxx).
// BC5_DIRECT_ACB_STATE_RESTORE=1 puts the dcb tracker's compute registers in front of every dcb
// that dispatches (or calls an IB2, which may), in the dcb's own chain segment (ADR 0010), so no
// other job can run between the restore and the dcb. Header-only: the shared backend archive
// links unchanged.
//
// Register offsets (SH space, dword offset from 0xB000) from tools/bc5-agc/regdb/gfx10.json
// (Mesa, MIT): COMPUTE_START_X 0x204, COMPUTE_NUM_THREAD_X..Z 0x207-0x209, COMPUTE_PGM_LO/HI
// 0x20c/0x20d, COMPUTE_PGM_RSRC1/2 0x212/0x213, COMPUTE_VMID 0x214, COMPUTE_RESOURCE_LIMITS 0x215,
// COMPUTE_TMPRING_SIZE 0x218, COMPUTE_PGM_RSRC3 0x228, COMPUTE_USER_DATA_0..15 0x240-0x24f,
// COMPUTE_DISPATCH_TUNNEL 0x27d. COMPUTE_DISPATCH_INITIATOR and COMPUTE_DIM_X..Z (0x200-0x203)
// belong to the dispatch packet and are never replayed.
#pragma once

#include "bc5/full_state.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <span>
#include <vector>

namespace bc5::acb_restore {

inline constexpr std::uint32_t kFirst = 0x204u; // COMPUTE_START_X
inline constexpr std::uint32_t kEnd = 0x400u;   // past the SH compute block, as the CS prefix
inline constexpr std::uint32_t kVmid = 0x214u;  // the kernel's: never replayed from title state
inline constexpr std::uint32_t kUserData0 = 0x240u;

inline bool replayable(std::uint32_t off) { return off >= kFirst && off < kEnd && off != kVmid; }

// Type-3 packet length in dwords (type 0 counts the same way, type 2 is one dword).
inline std::uint32_t packet_len(std::uint32_t h) {
    const std::uint32_t type = h >> 30, c = (h >> 16) & 0x3fffu;
    if (type == 3 || type == 0) return c == 0x3fffu ? 1u : c + 2u;
    return 1u;
}

// True if ib has a DISPATCH_DIRECT (0x15), DISPATCH_INDIRECT (0x16) or INDIRECT_BUFFER (0x3f) at
// its top level (Mesa sid.h opcodes): the buffers whose dispatches could inherit compute state.
inline bool wants(std::span<const std::uint32_t> ib) {
    for (std::size_t i = 0; i < ib.size();) {
        const std::uint32_t h = ib[i], len = packet_len(h);
        if (h >> 30 == 3) {
            const std::uint32_t op = (h >> 8) & 0xffu;
            if (op == 0x15 || op == 0x16 || op == 0x3f) return true;
        }
        i += len;
    }
    return false;
}

// The tracked compute registers as SET_SH_REG runs (one packet per run of tracked offsets, as
// the CS prefix builds them); *regs = registers written.
inline std::vector<std::uint32_t> runs(const full_state::Tracker &t, std::size_t *regs = nullptr) {
    std::vector<std::uint32_t> p, vals;
    std::uint32_t first = 0;
    std::size_t n = 0;
    const auto flush = [&] {
        if (vals.empty()) return;
        p.push_back(0xC0007600u | (static_cast<std::uint32_t>(vals.size()) << 16)); // COUNT = body - 1
        p.push_back(first);
        p.insert(p.end(), vals.begin(), vals.end());
        n += vals.size();
        vals.clear();
    };
    for (std::uint32_t o = kFirst; o < kEnd; ++o) {
        std::uint32_t v = 0;
        if (!replayable(o) || !t.get(full_state::Sh, o, v)) {
            flush();
            continue;
        }
        if (vals.empty()) first = o;
        vals.push_back(v);
    }
    flush();
    if (regs != nullptr) *regs = n;
    return p;
}

// A chain offset's place (Codex review REVIEW-06-J2): the dispatch journal runs on the assembled
// chain, so its offsets include earlier segments and every host prefix. S has the ChainSeg fields
// off (where the segment's prefix starts), prefix and n. seg is -1 outside every segment; orig is
// the offset in the title's own buffer, meaningful unless in_prefix.
struct Where {
    int seg = -1;
    std::uint32_t orig = 0;
    bool in_prefix = false;
};
template <class S> Where locate(std::span<const S> segs, std::uint32_t q) {
    Where w;
    w.orig = q;
    for (std::size_t i = 0; i < segs.size(); ++i) {
        const S &s = segs[i];
        if (q < s.off || q - s.off >= s.prefix + s.n) continue;
        w.seg = static_cast<int>(i);
        w.in_prefix = q - s.off < s.prefix;
        w.orig = w.in_prefix ? q - s.off : q - s.off - s.prefix;
        break;
    }
    return w;
}

// The value a run of SET_SH_REG packets gives SH register reg, the last one if it is set twice:
// what a prefix really emitted, read from its dwords.
inline bool sh_value(std::span<const std::uint32_t> pre, std::uint32_t reg, std::uint32_t &value) {
    bool found = false;
    for (std::size_t i = 0; i < pre.size();) {
        const std::uint32_t h = pre[i], len = packet_len(h);
        if (i + len > pre.size()) break;
        if (h >> 30 == 3 && ((h >> 8) & 0xffu) == 0x76u && len >= 3) {
            const std::uint32_t first = pre[i + 1] & 0xffffu;
            if (reg >= first && reg - first < len - 2) {
                value = pre[i + 2 + (reg - first)];
                found = true;
            }
        }
        i += len;
    }
    return found;
}

// The compute SH registers acbs write: SET_SH_REG(_INDEX) 0x76/0x9b, LOAD_SH_REG 0x5f ranges,
// LOAD_SH_REG_INDEX 0x63 (flat ranges, or pairs read through the reader), and INDIRECT_BUFFER
// 0x3f followed through the reader (4 levels). Tables the reader cannot read are counted.
class Touched {
public:
    using Reader = full_state::Tracker::Reader;

    void scan(std::span<const std::uint32_t> ib, const Reader &read) { scan_level(ib, read, 0); }
    bool has(std::uint32_t off) const { return off >= kFirst && off < kEnd && bits_[off - kFirst] != 0; }
    std::size_t count() const { return n_; }
    std::size_t unreadable() const { return unreadable_; }
    // Offsets an acb wrote that the dcb tracker does not know: their graphics-queue value is
    // unknown, so the restore leaves them as the acb left them.
    std::vector<std::uint32_t> missing(const full_state::Tracker &t) const {
        std::vector<std::uint32_t> out;
        for (std::uint32_t o = kFirst; o < kEnd; ++o) {
            std::uint32_t v = 0;
            if (has(o) && replayable(o) && !t.get(full_state::Sh, o, v)) out.push_back(o);
        }
        return out;
    }

private:
    void mark(std::uint32_t off, std::uint32_t n) {
        for (std::uint32_t k = 0; k < n; ++k) {
            const std::uint32_t o = off + k;
            if (o < kFirst || o >= kEnd || bits_[o - kFirst] != 0) continue;
            bits_[o - kFirst] = 1;
            ++n_;
        }
    }
    static std::uint64_t address(std::uint32_t lo, std::uint32_t hi) {
        return (lo & ~3u) | (static_cast<std::uint64_t>(hi & 0xffffu) << 32);
    }
    void scan_level(std::span<const std::uint32_t> ib, const Reader &read, int depth) {
        for (std::size_t i = 0; i < ib.size();) {
            const std::uint32_t h = ib[i], len = packet_len(h);
            if (i + len > ib.size()) break;
            const std::uint32_t *p = &ib[i];
            const std::uint32_t op = (h >> 8) & 0xffu;
            if (h >> 30 != 3 || len == 1) {
                i += len;
                continue;
            }
            if ((op == 0x76 || op == 0x9b) && len >= 3) {
                mark(p[1] & 0xffffu, len - 2);
            } else if (op == 0x5f && len >= 5) {
                for (std::uint32_t k = 3; k + 1 < len; k += 2) mark(p[k] & 0xffffu, p[k + 1] & 0x3fffu);
            } else if (op == 0x63 && len >= 5) {
                const std::uint32_t n = p[4] & 0x3fffu;
                if ((p[3] >> 31) == 0) {
                    mark(p[3] & 0xffffu, n);
                } else if (n != 0) {
                    const std::uint32_t *t = read ? read(address(p[1], p[2]), n * 8ull) : nullptr;
                    if (t == nullptr) ++unreadable_;
                    else
                        for (std::uint32_t q = 0; q < n; ++q) mark(t[2 * q] & 0xffffu, 1);
                }
            } else if (op == 0x3f && len >= 4) {
                const std::uint32_t n = p[3] & 0xfffffu;
                const std::uint32_t *t = read && n != 0 && depth < 4 ? read(address(p[1], p[2]), n * 4ull) : nullptr;
                if (t == nullptr) ++unreadable_;
                else scan_level(std::span<const std::uint32_t>(t, n), read, depth + 1);
            }
            i += len;
        }
    }
    std::array<std::uint8_t, kEnd - kFirst> bits_{};
    std::size_t n_ = 0;
    std::size_t unreadable_ = 0;
};

} // namespace bc5::acb_restore
