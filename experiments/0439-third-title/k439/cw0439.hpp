// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0439 (tag cw439): the chain-following writer scan (README item 49, F896; the top session, 11-22 ~09:30).
// register_label_writes reads a job's top-level dwords only, so the label releases of a dcb that is one chain of
// pieces (the third title's: 73 segments) never reach the pending-write table, and every mechanism on it is blind to
// them. With BC5_0439_CHAIN_WRITERS=1 the job's chained and called pieces (bc5/ib_chain.hpp collect, the same walk the
// import scans and the timeout probe's piece dump use) are registered too, every packet start of a piece taken as
// executed. Risk, stated: a piece's label write that the filter would drop is registered all the same; a wait on it is
// then kept for the GPU and never met. RELEASE_MEM, EVENT_WRITE_EOP and WRITE_DATA to memory pass the filter as they are.
#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

#include "bc5/ib_chain.hpp"

namespace bc5::cw439 {

// The packet starts of one piece (type-3 and type-0 headers walked as the filter walks them).
inline std::vector<std::uint32_t> starts(const std::uint32_t *w, std::size_t n) {
    std::vector<std::uint32_t> r;
    for (std::size_t q = 0; q < n;) {
        const std::uint32_t h = w[q], type = h >> 30u;
        std::size_t len = 1;
        if (type == 3 || type == 0) {
            const std::uint32_t c = (h >> 16u) & 0x3fffu;
            len = c == 0x3fffu ? 1 : c + 2;
        }
        if (q + len > n) break;
        if (type == 3) r.push_back(static_cast<std::uint32_t>(q));
        q += len;
    }
    return r;
}

// Calls fn(piece_src, piece_n, starts) for every piece of the job but the top one (k >= 1). mapped(a, bytes) as for
// ib_chain::collect. Returns the number of pieces visited.
template <typename M, typename F> std::size_t each_piece(const std::uint32_t *ib, std::uint32_t n, M mapped, F fn) {
    const auto cr = bc5::ib_chain::collect(ib, n, mapped, true);
    std::size_t k = 1;
#if defined(BC5_CW439_PLANT_FIRST) // the planted bug: the first chained piece skipped
    k = 2;
#endif
    for (; k < cr.pieces.size(); k++) fn(cr.pieces[k].src, static_cast<std::uint32_t>(cr.pieces[k].n), starts(cr.pieces[k].src, cr.pieces[k].n));
    return cr.pieces.size() > 0 ? cr.pieces.size() - 1 : 0;
}

} // namespace bc5::cw439
