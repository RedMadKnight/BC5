// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/ib_split.hpp"

#include <algorithm>

namespace bc5::ib_split {

namespace {

constexpr std::uint32_t kOpCondExec = 0x22;

std::size_t packet_len(std::uint32_t h) {
    const std::uint32_t type = h >> 30;
    if (type == 3 || type == 0) {
        const std::uint32_t count = (h >> 16) & 0x3fff;
        return count == 0x3fff ? 1 : count + 2;
    }
    return 1;
}

struct Range {
    std::size_t lo, hi; // a cut b with lo < b < hi is forbidden
};

// The greedy cut with pieces of at most `limit` dwords: from each piece start the largest allowed boundary
// within the limit. Fails when no such boundary exists (too long a COND_EXEC range) or when a piece beyond
// `max_pieces` would be needed; `where` is then the start that found no cut.
bool greedy(const std::vector<std::size_t> &bounds, const std::vector<Range> &ranges, std::size_t end,
            std::size_t limit, std::size_t max_pieces, std::size_t align_dw, std::size_t fallback_align_dw,
            std::vector<Piece> &out, std::uint32_t &fallback_cuts, std::size_t &where, bool &too_many) {
    out.clear();
    fallback_cuts = 0;
    too_many = false;
    const auto forbidden = [&ranges](std::size_t b) {
        return std::any_of(ranges.begin(), ranges.end(), [b](const Range &r) { return r.lo < b && b < r.hi; });
    };
    std::size_t s = 0;
    while (s < end) {
        if (end - s <= limit) {
            out.push_back({s, end - s});
            return true;
        }
        if (out.size() + 1 >= max_pieces) { // this piece would be the last allowed and cannot reach the end
            where = s;
            too_many = true;
            return false;
        }
        auto it = std::upper_bound(bounds.begin(), bounds.end(), s + limit); // first boundary > s + limit
        std::size_t cut = 0;
        bool fallback = false;
        for (std::size_t pass = 0; pass < 2 && cut == 0; ++pass) {
            const std::size_t align = pass == 0 ? align_dw : fallback_align_dw;
            for (auto j = it; j != bounds.begin();) {
                --j;
                if (*j <= s)
                    break;
                if (*j % align == 0 && !forbidden(*j)) {
                    cut = *j;
                    fallback = pass == 1;
                    break;
                }
            }
        }
        if (cut == 0) {
            where = s;
            return false;
        }
        if (fallback)
            fallback_cuts++;
        out.push_back({s, cut - s});
        s = cut;
    }
    return true;
}

} // namespace

std::vector<Piece> split(std::span<const std::uint32_t> image, std::size_t end, std::size_t max_dw,
                         std::size_t max_pieces, std::size_t align_dw, std::size_t fallback_align_dw,
                         Stats &stats) {
    stats = Stats{};
    if (end > image.size())
        end = image.size();
    if (end <= max_dw) {
        stats.pieces = 1;
        return {{0, end}};
    }
    if (max_dw == 0 || max_pieces == 0 || align_dw == 0 || fallback_align_dw == 0) {
        stats.failed = true;
        return {};
    }
    // Every packet boundary and every COND_EXEC range of [0, end).
    std::vector<std::size_t> bounds;
    std::vector<Range> ranges;
    for (std::size_t i = 0; i < end;) {
        bounds.push_back(i);
        const std::uint32_t h = image[i];
        std::size_t len = packet_len(h);
        if (i + len > end)
            len = end - i;
        if (h >> 30 == 3 && ((h >> 8) & 0xff) == kOpCondExec && len == 5) {
            const std::size_t count = image[i + 4] & 0x3fffu;
            ranges.push_back({i, i + len + count});
        }
        i += len;
    }
    bounds.push_back(end);
    stats.cond_ranges = static_cast<std::uint32_t>(ranges.size());
    // The greedy cut at the limit; when it runs out of pieces (the cuts pulled back by COND_EXEC ranges left too
    // much for the last piece), again with the limit lowered in steps towards the even share, so the pieces
    // balance; the first cut set within max_pieces wins.
    std::vector<Piece> out;
    const std::size_t even = std::min(max_dw, (end + max_pieces - 1) / max_pieces); // never above the limit
    const std::size_t step = std::max<std::size_t>(1, (max_dw - even) / 32);
    for (std::size_t limit = max_dw;; limit = limit > even + step ? limit - step : even) {
        std::uint32_t fallback = 0;
        std::size_t where = 0;
        bool too_many = false;
        if (greedy(bounds, ranges, end, limit, max_pieces, align_dw, fallback_align_dw, out, fallback, where, too_many)) {
            stats.pieces = static_cast<std::uint32_t>(out.size());
            stats.fallback_cuts = fallback;
            return out;
        }
        if (!too_many || limit == even) {
            stats.failed = true;
            stats.failed_at = where;
            stats.too_many_pieces = too_many;
            return {};
        }
    }
}

} // namespace bc5::ib_split
