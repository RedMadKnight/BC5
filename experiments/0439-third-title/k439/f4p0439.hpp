// BC5 exp 0439 (tag f4p439, arm A; GPL-2.0, ours). The memory waits of a GFX job's pieces, for ho430's cycle guard
// (F2) when the piece waits reach the GPU (BC5_0439_PIECE_WAITS=2). Pure: the caller gives the root's executed packet
// offsets and a reader that returns a piece's dwords when its range is mapped (nullptr otherwise).
// PM4 type-3 header: count in bits 29:16 (0x3fff = a one-dword NOP form), opcode in bits 15:8; INDIRECT_BUFFER 0x3f,
// INDIRECT_BUFFER_CNST 0x33 (address dwords 1-2, size in dword 3 bits 19:0, CHAIN bit 20); WAIT_REG_MEM 0x3c and
// WAIT_REG_MEM64 0x93 (MEM_SPACE dword 1 bit 4, address dwords 2-3) — the layouts the unit's own decoders use
// (bc5LleAgc.cpp wait_satisfied, the timeout probe's piece walk; tools/bc5-agc).
#pragma once
#include <algorithm>
#include <cstdint>
#include <functional>
#include <utility>
#include <vector>

namespace bc5::f4p439 {

inline uint32_t pkt_len(uint32_t h) {
    if ((h >> 30u) != 3 && (h >> 30u) != 0) return 1;
    const uint32_t c = (h >> 16u) & 0x3fffu;
    return c == 0x3fffu ? 1 : c + 2;
}
inline uint64_t addr(const uint32_t* w) { return (static_cast<uint64_t>(w[0]) & ~3ull) | (static_cast<uint64_t>(w[1] & 0xffffu) << 32u); }

using Reader = std::function<const uint32_t*(uint64_t address, uint32_t dwords)>;

// The memory-wait labels of every piece the root's executed IB packets call or chain to (calls one level deeper, to
// depth 3; chains at their own depth; each address once; at most max_pieces pieces). The root's own waits are not
// included (ho430 records those).
inline std::vector<uint64_t> piece_waits(const uint32_t* root, uint32_t n, const std::vector<uint32_t>& executed, const Reader& read, size_t max_pieces = 256) {
    struct Ib {
        uint64_t a;
        uint32_t n;
        int      depth;
    };
    std::vector<Ib> todo;
    size_t          e = 0;
    for (uint32_t q = 0; q < n;) {
        const uint32_t h = root[q], len = pkt_len(h);
        if (q + len > n) break;
        while (e < executed.size() && executed[e] < q) e++;
        const bool ran = e < executed.size() && executed[e] == q;
        const uint32_t op = (h >> 8u) & 0xffu;
        if ((h >> 30u) == 3 && ran && (op == 0x3f || op == 0x33) && len >= 4) todo.push_back({addr(root + q + 1), root[q + 3] & 0xfffffu, (root[q + 3] & (1u << 20)) != 0 ? 0 : 1});
        q += len;
    }
    std::vector<uint64_t> waits, seen;
    for (size_t t = 0; t < todo.size() && t < max_pieces; t++) {
        const Ib ib = todo[t];
        if (ib.a == 0 || ib.n == 0 || ib.n > (1u << 20) || ib.depth > 3 || std::find(seen.begin(), seen.end(), ib.a) != seen.end()) continue;
        seen.push_back(ib.a);
        const uint32_t* b = read(ib.a, ib.n);
        if (b == nullptr) continue;
        for (uint32_t q = 0; q < ib.n;) {
            const uint32_t h = b[q], len = pkt_len(h);
            if (q + len > ib.n) break;
            if ((h >> 30u) == 3) {
                const uint32_t op = (h >> 8u) & 0xffu;
                if ((op == 0x3c || op == 0x93) && len >= 4 && ((b[q + 1] >> 4u) & 1u) != 0) waits.push_back(addr(b + q + 2));
                if ((op == 0x3f || op == 0x33) && len >= 4) todo.push_back({addr(b + q + 1), b[q + 3] & 0xfffffu, ib.depth + ((b[q + 3] & (1u << 20)) != 0 ? 0 : 1)});
            }
            q += len;
        }
    }
    return waits;
}

// F2's question: does a writer job holding these kept waits wait on a label the waiting buffer writes (a cycle)?
inline bool cycle(const std::vector<uint64_t>& writer_kept_waits, const std::vector<uint64_t>& buffer_writes) {
    for (const uint64_t l: writer_kept_waits)
        if (std::find(buffer_writes.begin(), buffer_writes.end(), l) != buffer_writes.end()) return true;
    return false;
}

// Arm C (tag tsp439): where to split a dcb so that its root's label releases are their own kernel job: the offset of
// the root's final packet when it is a CHAIN (INDIRECT_BUFFER 0x3f / 0x33 with bit 20 of dword 3) that ends the buffer
// and something precedes it, else -1. A root without such a tail chain is not split; a chain elsewhere in the root is
// not a split point (the root goes on after it only for a call, and a chain ends the buffer).
inline int64_t tail_chain_at(const uint32_t* root, uint32_t n) {
    uint32_t last = 0, last_len = 0;
    bool     any  = false;
    for (uint32_t q = 0; q < n;) {
        const uint32_t h = root[q], len = pkt_len(h);
        if (q + len > n) return -1;
        last = q, last_len = len, any = true;
        q += len;
    }
    if (!any || last == 0 || last + last_len != n) return -1;
    const uint32_t h = root[last], op = (h >> 8u) & 0xffu;
    if ((h >> 30u) != 3 || (op != 0x3f && op != 0x33) || last_len < 4) return -1;
    return (root[last + 3] & (1u << 20)) != 0 ? static_cast<int64_t>(last) : -1;
}

} // namespace bc5::f4p439
