// BC5 experiment 0438 (tag a2): mapping_index.hpp against today's rebuild of Device::sorted_mappings().
// Random sequences of inserts and erases of disjoint mappings (shared and userptr, some read-only, a few at an equal
// va); after every edit:
//   1. the index, read through begin()/end() and operator[], equals the old rebuild: the userptrs sorted by va and
//      merged into the shared maps in va order (a shared one first at an equal va), direct.cpp sorted_mappings();
//   2. the host's covered_sorted() (bake unit, the K1r hole rule) gives the same answer over both, on random ranges;
//   3. a snapshot taken before the edit still reads as it did (the chunks are shared, never changed);
//   4. no chunk is empty or over kChunkMax.
// -DA2_BROKEN makes index_erase keep the element: the test must then FAIL.
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <random>
#include <vector>

namespace bc5::direct {
struct Mapping {
    std::uint64_t va = 0;
    std::uint64_t size = 0;
    bool readonly = false;
    bool shared = false;
};
} // namespace bc5::direct
#include "mapping_index.hpp"

using bc5::direct::Mapping;
using bc5::direct::MappingIndex;

static int fails = 0;
#define CHECK(c, ...)                                  \
    do {                                               \
        if (!(c)) {                                    \
            if (fails < 20) {                          \
                std::printf("FAIL line %d: ", __LINE__); \
                std::printf(__VA_ARGS__);              \
                std::printf("\n");                     \
            }                                          \
            fails++;                                   \
        }                                              \
    } while (0)

// today's rebuild (direct.cpp Device::sorted_mappings)
static std::vector<Mapping> old_rebuild(const std::vector<Mapping> &shared_sorted, std::vector<Mapping> users) {
    std::sort(users.begin(), users.end(), [](const Mapping &x, const Mapping &y) { return x.va < y.va; });
    std::vector<Mapping> out;
    auto u = users.begin();
    for (const auto &m : shared_sorted) {
        while (u != users.end() && u->va < m.va) out.push_back(*u++);
        out.push_back(m);
    }
    out.insert(out.end(), u, users.end());
    return out;
}
// the bake unit's covered_sorted (cv412::hole(shared, readonly) = shared && readonly)
template <typename V> static bool covered_sorted(const V &maps, uint64_t a, uint64_t bytes) {
    const uint64_t end = a + bytes;
    uint64_t pos = a;
    for (int guard = 0; pos < end && guard < 64; guard++) {
        auto it = std::upper_bound(maps.begin(), maps.end(), pos, [](uint64_t v, const Mapping &m) { return v < m.va; });
        if (it == maps.begin()) return false;
        --it;
        if (it->shared && it->readonly) return false;
        if (pos >= it->va + it->size) return false;
        pos = it->va + it->size;
    }
    return pos >= end;
}
static bool same(const Mapping &a, const Mapping &b) { return a.va == b.va && a.size == b.size && a.readonly == b.readonly && a.shared == b.shared; }

#ifdef A2_BROKEN
template <typename M> static std::shared_ptr<const MappingIndex> erase_under_test(const std::shared_ptr<const MappingIndex> &x, const M &) { return x; }
#else
template <typename M> static std::shared_ptr<const MappingIndex> erase_under_test(const std::shared_ptr<const MappingIndex> &x, const M &m) {
    return bc5::direct::index_erase(x, m);
}
#endif

int main() {
    std::mt19937_64 rng(438);
    uint64_t edits = 0, queries = 0, snaps = 0, max_chunks = 0;
    for (int scen = 0; scen < 40; scen++) {
        constexpr int kSlots = 6000; // 64 KiB slots: mappings inside one slot never overlap another slot's
        std::vector<int> state(kSlots, 0); // 0 free, 1 shared, 2 user
        std::vector<Mapping> shared_sorted, users;
        std::shared_ptr<const MappingIndex> idx;
        const int ops = 3000 + static_cast<int>(rng() % 6000);
        for (int op = 0; op < ops; op++) {
            const int s = static_cast<int>(rng() % kSlots);
            const uint64_t va = 0x100000000ull + static_cast<uint64_t>(s) * 0x10000ull;
            auto prev = idx;
            std::vector<Mapping> prev_flat;
            if (prev && (op % 97) == 0) prev_flat.assign(prev->begin(), prev->end());
            if (state[s] == 0) {
                Mapping m;
                m.va = va;
                m.size = 0x1000ull * (1 + rng() % 16);
                m.shared = (rng() % 8) != 0;
                m.readonly = (rng() % 5) == 0;
                state[s] = m.shared ? 1 : 2;
                if (m.shared) {
                    auto at = std::upper_bound(shared_sorted.begin(), shared_sorted.end(), m.va, [](uint64_t v, const Mapping &x) { return v < x.va; });
                    shared_sorted.insert(at, m);
                } else {
                    users.push_back(m);
                }
                idx = bc5::direct::index_insert(idx, m);
            } else {
                auto &from = state[s] == 1 ? shared_sorted : users;
                auto it = std::find_if(from.begin(), from.end(), [&](const Mapping &x) { return x.va == va; });
                const Mapping m = *it;
                from.erase(it);
                state[s] = 0;
                idx = erase_under_test(idx, m);
            }
            edits++;
            const auto ref = old_rebuild(shared_sorted, users);
            CHECK(idx && idx->size() == ref.size(), "scenario %d op %d: size %zu, want %zu", scen, op, idx ? idx->size() : 0, ref.size());
            if (idx && idx->size() == ref.size() && (op % 7 == 0 || op + 1 == ops)) {
                size_t i = 0;
                for (const auto &m : *idx) {
                    CHECK(same(m, ref[i]), "scenario %d op %d: element %zu differs (va 0x%" PRIx64 " vs 0x%" PRIx64 ")", scen, op, i, m.va, ref[i].va);
                    CHECK(same((*idx)[i], ref[i]), "scenario %d op %d: operator[] %zu differs", scen, op, i);
                    i++;
                }
                for (const auto &c : idx->chunks()) CHECK(!c->empty() && c->size() <= MappingIndex::kChunkMax, "scenario %d op %d: chunk of %zu", scen, op, c->size());
                if (idx->chunks().size() > max_chunks) max_chunks = idx->chunks().size();
            }
            if (idx) {
                for (int q = 0; q < 8; q++) {
                    const uint64_t a = 0x100000000ull + (rng() % (static_cast<uint64_t>(kSlots) * 0x10000ull)) - 0x8000ull;
                    const uint64_t n = 1 + rng() % 0x30000ull;
                    CHECK(covered_sorted(*idx, a, n) == covered_sorted(ref, a, n), "scenario %d op %d: covered(0x%" PRIx64 ", 0x%" PRIx64 ") differs", scen, op, a, n);
                    queries++;
                }
            }
            if (!prev_flat.empty()) {
                std::vector<Mapping> now(prev->begin(), prev->end());
                bool eq = now.size() == prev_flat.size();
                for (size_t i = 0; eq && i < now.size(); i++) eq = same(now[i], prev_flat[i]);
                CHECK(eq, "scenario %d op %d: an earlier snapshot changed", scen, op);
                snaps++;
            }
        }
    }
    // an implicit one-chunk index from a plain vector, as the host's diagnostic callers pass one
    const std::vector<Mapping> plain{{0x1000, 0x1000, false, true}, {0x3000, 0x1000, false, false}};
    const MappingIndex from_plain = plain;
    CHECK(from_plain.size() == 2 && covered_sorted(from_plain, 0x1000, 0x1000) && !covered_sorted(from_plain, 0x2000, 0x10), "the implicit index from a vector");
    std::printf("a2 test: %" PRIu64 " edits, %" PRIu64 " covered queries, %" PRIu64 " snapshot checks, at most %" PRIu64 " chunks; %s (%d failures)\n", edits, queries, snaps,
                max_chunks, fails == 0 ? "PASS" : "FAIL", fails);
    return fails == 0 ? 0 : 1;
}
