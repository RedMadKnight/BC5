// SPDX-License-Identifier: GPL-2.0-only
//
// BC5 exp 0439 (tag ib439): INDIRECT_BUFFER chains, BC5_DIRECT_IB_CHAIN (off unless "1").
//
// INDIRECT_BUFFER (0x3f) with bit 20 of its size dword clear is a call that returns; with the bit set it is a CHAIN: the
// target replaces the rest of the current buffer, so it adds no nesting level and the tail after the packet is never
// read (AMD PAL c5e8000 src/core/hw/gfxip/gfx9/chip/gfx9_plus_merged_f32_pfp_pm4_packets.h:2580; shadPS4 1b9d159 made
// the same correction; our own note, bc5/acb_restore.hpp PORT-CHAIN, F760). The third title's frame is one dcb of 73
// segments chained this way (exp 0440, yotei-memdump); every IB walker that counted a chain as one more level cut it
// after segment 3 and the frame's tail (its label-0 write among them) was dropped silently.
//
// The rule: a chain keeps its parent's depth and has no count limit of its own beyond kMaxChainPieces; a call keeps the
// old depth limit (3) and the old cap (64 pieces). A chain or call to one of its own ancestors is a cycle: refused
// loudly, never followed. With the switch off collect() returns exactly what direct.cpp's loop built before.
#pragma once

#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <functional>
#include <span>
#include <vector>

namespace bc5::ib_chain {

inline constexpr std::uint32_t kChainBit = 1u << 20u;
inline constexpr int kMaxCallDepth = 3;             // direct.cpp before exp 0439: `if (pieces[k].depth >= 3) continue`
inline constexpr std::size_t kMaxCallPieces = 64;   // direct.cpp before exp 0439: `pieces.size() < 64`
inline constexpr std::size_t kMaxChainPieces = 4096; // a sane bound; exceeding it is refused loudly

inline bool is_chain(std::uint32_t size_dw) { return (size_dw & kChainBit) != 0; }

// The switch, read once.
inline bool enabled() {
    static const bool v = [] {
        const char *e = std::getenv("BC5_DIRECT_IB_CHAIN");
        return e != nullptr && e[0] == '1' && e[1] == 0;
    }();
    return v;
}

// The depth a target runs at.
inline int child_depth(int depth, std::uint32_t size_dw, bool rule) {
#if defined(BC5_IB439_PLANT) // the det test's planted bug: a chain counted as one more level (must FAIL)
    (void)size_dw;
    (void)rule;
    return depth + 1;
#else
    return rule && is_chain(size_dw) ? depth : depth + 1;
#endif
}

struct Piece {
    const std::uint32_t *src = nullptr;
    std::size_t n = 0;
    int depth = 0;
    int parent = -1;     // index of the piece whose packet first led here
    bool chained = false; // reached by a chain packet
};

struct Result {
    std::vector<Piece> pieces;
    std::size_t chains = 0;          // chain packets whose target became a piece
    std::size_t longest_chain = 0;   // the longest run of chain links from one piece
    std::size_t over_depth = 0;      // call targets not followed: the call depth limit
    std::size_t over_cap = 0;        // targets not followed: a piece cap
    bool cycle = false;              // a target is one of its own ancestors (rule on only)
    bool chain_cap = false;          // kMaxChainPieces reached (rule on only)
};

// One IB target in a buffer: the packet's offset, the target and its size dword.
struct Target {
    std::size_t at = 0;
    const std::uint32_t *src = nullptr;
    std::size_t n = 0;
    std::uint32_t size_dw = 0;
};

// INDIRECT_BUFFER / INDIRECT_BUFFER_CNST targets of a buffer that `mapped` accepts (direct.cpp nested_targets'
// reading: address lo & ~3, hi & 0xff, size bits 19:0; a header-only 0x3fff count is one dword).
inline void targets_of(std::span<const std::uint32_t> ib, const std::function<bool(std::uint64_t, std::uint64_t)> &mapped,
                       std::vector<Target> &out) {
    for (std::size_t i = 0; i < ib.size();) {
        const std::uint32_t h = ib[i];
        const std::uint32_t type = h >> 30;
        std::size_t len = 1;
        if (type == 3 || type == 0) {
            const std::uint32_t count = (h >> 16) & 0x3fff;
            len = count == 0x3fff ? 1 : count + 2;
        }
        if (i + len > ib.size()) break;
        const std::uint32_t op = (h >> 8) & 0xff;
        if (type == 3 && (op == 0x3f || op == 0x33) && len >= 4) {
            const std::uint64_t a = (static_cast<std::uint64_t>(ib[i + 1]) & ~3ull) |
                                    (static_cast<std::uint64_t>(ib[i + 2] & 0xffu) << 32);
            const std::size_t n = ib[i + 3] & 0xfffffu;
            if (a != 0 && n != 0 && (!mapped || mapped(a, n * 4)))
                out.push_back({i, reinterpret_cast<const std::uint32_t *>(a), n, ib[i + 3]});
        }
        i += len;
    }
}

// The pieces a submit copies: the root, then every IB it reaches, breadth first, each (src, n) once.
inline Result collect(const std::uint32_t *root, std::size_t root_n,
                      const std::function<bool(std::uint64_t, std::uint64_t)> &mapped, bool rule) {
    Result r;
    r.pieces.push_back({root, root_n, 0, -1, false});
    std::size_t calls = 1, chain_pieces = 0;
    for (std::size_t k = 0; k < r.pieces.size(); ++k) {
        if (!rule && r.pieces.size() >= kMaxCallPieces) break; // the old loop's condition, exactly
        std::vector<Target> ts;
        targets_of(std::span<const std::uint32_t>(r.pieces[k].src, r.pieces[k].n), mapped, ts);
        if (!rule) {
            if (r.pieces[k].depth >= kMaxCallDepth) {
                r.over_depth += ts.size();
                continue;
            }
            for (const auto &t : ts) {
                bool seen = false;
                for (const auto &q : r.pieces) seen = seen || (q.src == t.src && q.n == t.n);
                if (seen) continue;
                r.pieces.push_back({t.src, t.n, r.pieces[k].depth + 1, static_cast<int>(k), false});
            }
            continue;
        }
        for (const auto &t : ts) {
            const bool chain = is_chain(t.size_dw);
            const int d = child_depth(r.pieces[k].depth, t.size_dw, true);
            if (!chain && r.pieces[k].depth >= kMaxCallDepth) {
                r.over_depth++;
                continue;
            }
            // a cycle: the target is this piece or one of its ancestors
            for (int a = static_cast<int>(k); a >= 0; a = r.pieces[static_cast<std::size_t>(a)].parent) {
                const Piece &anc = r.pieces[static_cast<std::size_t>(a)];
                if (anc.src == t.src && anc.n == t.n) {
                    r.cycle = true;
                    return r;
                }
            }
            bool seen = false;
            for (const auto &q : r.pieces) seen = seen || (q.src == t.src && q.n == t.n);
            if (seen) continue;
            if (chain ? chain_pieces >= kMaxChainPieces : calls >= kMaxCallPieces) {
                r.over_cap++;
                if (chain) {
                    r.chain_cap = true;
                    return r;
                }
                continue;
            }
            (chain ? chain_pieces : calls)++;
            if (chain) r.chains++;
            r.pieces.push_back({t.src, t.n, d, static_cast<int>(k), chain});
            if (chain) {
                std::size_t len = 0;
                for (int a = static_cast<int>(r.pieces.size()) - 1; a >= 0 && r.pieces[static_cast<std::size_t>(a)].chained;
                     a = r.pieces[static_cast<std::size_t>(a)].parent)
                    len++;
                if (len > r.longest_chain) r.longest_chain = len;
            }
        }
    }
    return r;
}

// exp 0439 (tag fl439): BC5_DIRECT_IB_CHAIN_FLAT ("1": compute jobs, "2": every job, else off). A chain at the top level
// of a job is laid out flat: each segment is copied up to and including its chain packet, the chain packet becomes
// one-dword NOPs of its length (0xffff1000, as the filter drops a packet), nothing after it is copied (the CP never runs a
// segment's tail past its chain), and the chain's target follows directly. So the CP never switches buffers inside the job,
// and the state a segment sets before its chain is simply still there for the next segment (the frame-229 hang: the first
// dispatch after a chain on a compute ring, its program set before the chain, never finished; the first chain the host
// ever ran on a compute ring). Refused (the job keeps today's layout) when a segment holds a COND_EXEC before its chain (a
// conditional chain), on a cycle, an unmapped target, or past kMaxFlatDwords. Calls (bit 20 clear) are left as they are.
inline int flat_mode() {
    static const int v = [] {
        const char *e = std::getenv("BC5_DIRECT_IB_CHAIN_FLAT");
        if (e == nullptr || e[1] != 0) return 0;
        return e[0] == '1' ? 1 : e[0] == '2' ? 2 : 0;
    }();
    return v;
}
inline constexpr std::size_t kMaxFlatDwords = 1u << 20;
inline constexpr std::uint32_t kFlatNop = 0xffff1000u;

struct FlatSeg {
    const std::uint32_t *src = nullptr; // the guest segment
    std::size_t n = 0;                  // its dwords copied (up to and including its chain packet, or all of the last)
    std::size_t off = 0;                // its first dword in the flat buffer
};
enum class FlatResult { NoChain, Flattened, Refused };

inline FlatResult flatten(std::span<const std::uint32_t> top, const std::function<bool(std::uint64_t, std::uint64_t)> &mapped,
                          std::vector<std::uint32_t> &out, std::vector<FlatSeg> &segs, const char **why = nullptr) {
    out.clear();
    segs.clear();
    const std::uint32_t *src = top.data();
    std::size_t n = top.size();
    auto refuse = [&](const char *w) {
        if (why != nullptr) *why = w;
        out.clear();
        segs.clear();
        return FlatResult::Refused;
    };
    for (std::size_t seg = 0;; ++seg) {
        if (seg >= kMaxChainPieces) return refuse("over 4096 segments");
        for (const auto &s : segs)
            if (s.src == src) return refuse("a chain cycle");
        // the first chain packet at this segment's top level, and whether a COND_EXEC comes before it
        std::size_t chain_at = n, chain_len = 0;
        bool cond = false;
        for (std::size_t i = 0; i < n;) {
            const std::uint32_t h = src[i], type = h >> 30;
            std::size_t len = 1;
            if (type == 3 || type == 0) {
                const std::uint32_t c = (h >> 16) & 0x3fff;
                len = c == 0x3fff ? 1 : c + 2;
            }
            if (i + len > n) break;
            const std::uint32_t op = (h >> 8) & 0xff;
            if (type == 3 && op == 0x22) cond = true;
            if (type == 3 && (op == 0x3f || op == 0x33) && len >= 4 && is_chain(src[i + 3])) {
                chain_at = i;
                chain_len = len;
                break;
            }
            i += len;
        }
        if (chain_at == n) { // the last segment: all of it
            if (seg == 0) return FlatResult::NoChain;
            if (out.size() + n > kMaxFlatDwords) return refuse("over the flat size bound");
#if !defined(BC5_FL439_PLANT) // the det test's planted bug: the last chunk dropped (must FAIL)
            segs.push_back({src, n, out.size()});
            out.insert(out.end(), src, src + n);
#endif
            return FlatResult::Flattened;
        }
        if (cond) return refuse("a COND_EXEC before the chain (a conditional chain)");
        const std::uint64_t a = (static_cast<std::uint64_t>(src[chain_at + 1]) & ~3ull) |
                                (static_cast<std::uint64_t>(src[chain_at + 2] & 0xffu) << 32);
        const std::size_t tn = src[chain_at + 3] & 0xfffffu;
        if (a == 0 || tn == 0 || (mapped && !mapped(a, tn * 4))) return refuse("a chain target not mapped");
        const std::size_t copy_n = chain_at + chain_len;
        if (out.size() + copy_n > kMaxFlatDwords) return refuse("over the flat size bound");
        segs.push_back({src, copy_n, out.size()});
        out.insert(out.end(), src, src + chain_at);
        out.insert(out.end(), chain_len, kFlatNop);
        src = reinterpret_cast<const std::uint32_t *>(a);
        n = tn;
    }
}

} // namespace bc5::ib_chain
