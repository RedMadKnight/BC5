// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0412 (tag mf412): the CPU test of mkmem0412.py's edit. VirtualRanges::QuerySpan's loop, copied here
// with the range type cut to what the loop reads, is run from the table's first element (the old walk) and from the
// range std::upper_bound finds (the new one) on random sorted tables without overlaps, and both must return the same
// answer and the same parts for every query: inside one range, across touching ranges, across a hole, before the first
// range, after the last, at exact starts and ends.
//   clang++ -std=c++20 -O1 -Wall -Wextra -Werror memfast0412.cpp -o memfast0412 && ./memfast0412
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <random>
#include <vector>

struct Range {
    uint64_t start = 0, size = 0, offset = 0;
    int      type = 0; // 2: Direct (the offset moves with the part)
    bool     operator==(const Range& o) const { return start == o.start && size == o.size && offset == o.offset && type == o.type; }
};
static uint64_t End(uint64_t start, uint64_t size) { return start + size; }

static bool query(const std::vector<Range>& m_ranges, uint64_t start, uint64_t size, std::vector<Range>* out, bool fast) {
    out->clear();
    if (start == 0 || size == 0 || size > UINT64_MAX - start) return false;
    const auto end     = start + size;
    auto       current = start;
    auto       first = m_ranges.begin();
    if (fast) {
        first = std::upper_bound(m_ranges.begin(), m_ranges.end(), start, [](uint64_t v, const Range& r) { return v < r.start; });
        if (first != m_ranges.begin()) --first;
    }
    for (auto it = first; it != m_ranges.end(); ++it) {
        const auto& range     = *it;
        const auto  range_end = End(range.start, range.size);
        if (range_end <= current) continue;
        if (range.start > current) break;
        Range part = range;
        part.start = current;
        part.size  = std::min(end, range_end) - current;
        if (part.type == 2) part.offset += current - range.start;
        out->push_back(part);
        current += part.size;
        if (current == end) return true;
    }
    out->clear();
    return false;
}

int main() {
    std::mt19937_64 rng(412);
    uint64_t        checks = 0, ok = 0, hits = 0;
    for (int table = 0; table < 200; table++) {
        std::vector<Range> t;
        uint64_t           at = 0x4000 * (1 + rng() % 8);
        const int          n = table < 5 ? table : 1 + static_cast<int>(rng() % 3000);
        for (int i = 0; i < n; i++) {
            if (rng() % 3 == 0) at += 0x4000 * (1 + rng() % 16); // a hole
            const uint64_t size = 0x4000 * (1 + rng() % 8);
            t.push_back({at, size, rng() % (1ull << 30), static_cast<int>(rng() % 4)});
            at += size;
        }
        std::vector<uint64_t> points {1, 0x4000, at, at + 0x4000, UINT64_MAX - 0x4000};
        for (const auto& r: t) {
            points.push_back(r.start);
            points.push_back(r.start + r.size);
            points.push_back(r.start + r.size / 2);
            if (points.size() > 4000) break;
        }
        for (int q = 0; q < 3000; q++) {
            const uint64_t start = q < 5 ? (q == 0 ? 0 : points[static_cast<size_t>(q)]) : points[rng() % points.size()] + (rng() % 4 == 0 ? 0x1000 * (rng() % 8) : 0);
            const uint64_t size = q == 1 ? 0 : q == 2 ? UINT64_MAX : 0x1000 * (1 + rng() % 96);
            std::vector<Range> a, b;
            const bool         ra = query(t, start, size, &a, false), rb = query(t, start, size, &b, true);
            checks++;
            if (ra == rb && a == b) ok++;
            else if (checks - ok <= 5) std::printf("FAIL table %d start 0x%llx size 0x%llx: old %d (%zu parts), new %d (%zu parts)\n", table, static_cast<unsigned long long>(start), static_cast<unsigned long long>(size), ra, a.size(), rb, b.size());
            if (ra) hits++;
        }
    }
    const bool mixed = hits > checks / 20 && hits < checks - checks / 20; // both answers occur often, so the test is not vacuous
    if (!mixed) std::printf("FAIL the queries are not mixed: %llu of %llu found a span\n", static_cast<unsigned long long>(hits), static_cast<unsigned long long>(checks));
    std::printf("memfast0412: %llu of %llu%s; end\n", static_cast<unsigned long long>(mixed ? ok : 0), static_cast<unsigned long long>(checks), mixed ? "" : " (not mixed)");
    return ok == checks && mixed ? 0 : 1;
}
