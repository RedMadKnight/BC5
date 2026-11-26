// SPDX-License-Identifier: GPL-2.0-only
// BC5 exp 0439 (tag pw439, mode 3; the top session's order of 11-23 after F916): the piece-wait decision of
// BC5_0439_PIECE_WAITS=3. A chained or called piece is filtered with self_waits_only, which drops every
// WAIT_REG_MEM[64] on a label the same piece does not write earlier; mode 2 kept them all and deadlocked at once (F916:
// a kept wait's writer sat in a GFX piece stopped at its own kept wait, so the "only submitted jobs are pending, so no
// cycle" argument of w428 failed). Mode 3 keeps such an open wait only when it cannot take part in a cycle:
//   - memory already meets it (kKeepMet), or
//   - the label's last pending write registered by a job already in the kernel meets it (kKeepPending; the host's
//     table g_plw, the test a root wait gets in ring_will_satisfy, without r438's early entries),
// and drops it, as today, when the label is written anywhere in the same job (kDropSameJob: the write may sit after
// the wait on this ring), when no submitted writer proves it (kDropNoProof), or when the host's table is busy
// (kDropBusy). Every kept wait then points at an earlier-submitted job, so the waits keep submit order: no cycle.
// The packet walk and label forms are the filter's own (policy.cpp label_of: WRITE_DATA DST_SEL 1/2/5, RELEASE_MEM,
// EVENT_WRITE_EOP, ATOMIC_MEM; WAIT_REG_MEM 0x3c / WAIT_REG_MEM64 0x93 with MEM_SPACE bit 4 of dword 1; Mesa sid.h).
#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <span>
#include <vector>

namespace bc5::pw439 {

enum Decision : int { kDropNoProof = 0, kKeepPending = 1, kKeepMet = 2, kDropBusy = 3, kDropSameJob = 4, kSamePiece = 5, kCount = 6 };

inline const char *name(int d) {
    static const char *const k[kCount] = {"dropped, no submitted writer", "kept, a submitted writer", "kept, memory meets it",
                                          "dropped, host table busy", "dropped, written in the same job", "same piece (the filter keeps it)"};
    return d >= 0 && d < kCount ? k[d] : "?";
}

inline std::uint32_t packet_len(std::uint32_t h) {
    const std::uint32_t ty = h >> 30;
    if (ty == 3 || ty == 0) {
        const std::uint32_t c = (h >> 16) & 0x3fffu;
        return c == 0x3fffu ? 1u : c + 2u;
    }
    return 1u;
}

inline std::uint64_t addr(const std::uint32_t *p, int lo, int hi) {
    return (static_cast<std::uint64_t>(p[lo]) & ~3ull) | (static_cast<std::uint64_t>(p[hi] & 0xffffu) << 32);
}

// The label a type-3 packet writes, or 0 (policy.cpp label_of).
inline std::uint64_t label_write(const std::uint32_t *p, std::uint32_t len) {
    if ((p[0] >> 30) != 3) return 0;
    const std::uint32_t op = (p[0] >> 8) & 0xffu, dst_sel = len >= 2 ? (p[1] >> 8) & 0xfu : 0;
    switch (op) {
    case 0x37: return (len >= 4 && (dst_sel == 1 || dst_sel == 2 || dst_sel == 5)) ? addr(p, 2, 3) : 0; // WRITE_DATA
    case 0x49: return len >= 6 ? addr(p, 3, 4) : 0;                                                    // RELEASE_MEM
    case 0x47: return len >= 4 ? addr(p, 2, 3) : 0;                                                    // EVENT_WRITE_EOP
    case 0x1e: return len >= 4 ? addr(p, 2, 3) : 0;                                                    // ATOMIC_MEM
    default: return 0;
    }
}

// A memory WAIT_REG_MEM[64]'s label, or 0.
inline std::uint64_t wait_label(const std::uint32_t *p, std::uint32_t len, bool &is64) {
    if ((p[0] >> 30) != 3 || len < 4) return 0;
    const std::uint32_t op = (p[0] >> 8) & 0xffu;
    if (op != 0x3c && op != 0x93) return 0;
    if (((p[1] >> 4) & 1u) == 0) return 0;
    is64 = op == 0x93;
    return addr(p, 2, 3);
}

// Every label a buffer writes, appended (unsorted).
inline void labels_written(std::span<const std::uint32_t> b, std::vector<std::uint64_t> &out) {
    for (std::size_t i = 0; i < b.size();) {
        const std::uint32_t len = packet_len(b[i]);
        if (i + len > b.size()) break;
        if (const std::uint64_t l = label_write(&b[i], len); l != 0) out.push_back(l);
        i += len;
    }
}

struct OpenWait {
    std::uint32_t off; // dword offset in the piece (the filter's keep_wait_offsets unit)
    std::uint64_t label;
    bool is64;
};

// The piece's memory waits on labels no earlier packet of the piece writes (the ones self_waits_only drops);
// same_piece counts the others.
inline void open_waits(std::span<const std::uint32_t> b, std::vector<OpenWait> &out, std::uint64_t &same_piece) {
    std::vector<std::uint64_t> written;
    for (std::size_t i = 0; i < b.size();) {
        const std::uint32_t len = packet_len(b[i]);
        if (i + len > b.size()) break;
        bool is64 = false;
        if (const std::uint64_t w = wait_label(&b[i], len, is64); w != 0) {
            if (std::find(written.begin(), written.end(), w) != written.end()) same_piece++;
            else out.push_back({static_cast<std::uint32_t>(i), w, is64});
        } else if (const std::uint64_t l = label_write(&b[i], len); l != 0) {
            written.push_back(l);
        }
        i += len;
    }
}

// Mode 3 for one piece: the offsets to keep (appended to keep) and the decisions counted in counts[kCount].
// job_written: every label the whole job writes (root and all pieces), sorted. hook(pkt, is64) is the host's test
// (kKeepPending, kKeepMet, kDropNoProof or kDropBusy); null: everything open is dropped (kDropNoProof).
// note(label, decision) sees each open wait's decision (the host prints dropped labels once).
template <typename Hook, typename Note>
inline void decide(std::span<const std::uint32_t> piece, const std::vector<std::uint64_t> &job_written, Hook &&hook, Note &&note,
                   std::vector<std::uint32_t> &keep, std::uint64_t *counts) {
    std::vector<OpenWait> open;
    std::uint64_t same = 0;
    open_waits(piece, open, same);
    counts[kSamePiece] += same;
    for (const OpenWait &w : open) {
        int d;
        if (std::binary_search(job_written.begin(), job_written.end(), w.label)) {
            d = kDropSameJob;
        } else {
            d = hook(&piece[w.off], w.is64);
            if (d != kKeepPending && d != kKeepMet && d != kDropBusy) d = kDropNoProof; // only the host's four answers
        }
        counts[d]++;
        if (d == kKeepPending || d == kKeepMet) keep.push_back(w.off);
        note(w.label, d);
    }
}

} // namespace bc5::pw439
