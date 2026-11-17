// BC5 exp 0432, item X (tag x432): the mapping rebuild by view diff against the whole rebuild, on random view lists.
// The body under test is cut from the edited unit itself (x432_body.inc, made by test_x432.sh), not retyped.
//   test_x432.sh <edited bc5LleAgc.cpp>     builds and runs this; prints PASS or the first failing case
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <iterator>
#include <map>
#include <memory>
#include <random>
#include <string>
#include <utility>
#include <vector>

struct DView {
    uint64_t va, size, off;
    std::string name;
    bool lazy, eager;
};
struct DBo {
    uint64_t off, size;
    uint32_t id;
    uint64_t t_ns;
};
struct DMap {
    uint64_t va, size, bo_off;
    uint32_t id;
    bool operator==(const DMap &o) const { return va == o.va && size == o.size && bo_off == o.bo_off && id == o.id; }
};
struct DViews {
    std::vector<DView> v;
    uint64_t sig = 0;
    bool sorted = true;
};
struct DState {
    int kind = 0;
    std::vector<DBo> bos;
    std::vector<DMap> maps;
};
// the device: what is mapped where; mapping over a live mapping or unmapping nothing is an error of the caller
struct Dev {
    std::map<uint64_t, DMap> live;
    int errors = 0;
    bool overlaps(uint64_t va, uint64_t size) const {
        auto it = live.lower_bound(va);
        if (it != live.end() && it->first < va + size) return true;
        if (it != live.begin()) {
            --it;
            if (it->second.va + it->second.size > va) return true;
        }
        return false;
    }
    bool map_shared(uint32_t id, uint64_t bo_off, uint64_t size, uint64_t va) {
        if (overlaps(va, size)) errors++;
        live[va] = DMap{va, size, bo_off, id};
        return true;
    }
    void unmap_shared(uint64_t va) {
        if (live.erase(va) != 1) errors++;
    }
};
static Dev *g_dev = nullptr;
static std::vector<int> g_scratch, g_zpieces;
static void scratch_release(uint64_t, uint64_t) {}
static void zskip_release(uint64_t, uint64_t) {}
namespace d432 {
static uint64_t g_x_diff = 0, g_x_views = 0;
}

static void whole(const DState &S, const std::vector<DView> &views, std::vector<DMap> &out) {
    for (const auto &v : views) {
        const uint64_t vend = v.off + v.size;
        auto it = std::upper_bound(S.bos.begin(), S.bos.end(), v.off, [](uint64_t o, const DBo &b) { return o < b.off; });
        if (it != S.bos.begin()) --it;
        for (; it != S.bos.end() && it->off < vend; ++it) {
            const uint64_t lo = it->off > v.off ? it->off : v.off;
            const uint64_t hi = it->off + it->size < vend ? it->off + it->size : vend;
            if (lo >= hi) continue;
            out.push_back({v.va + (lo - v.off), hi - lo, lo - it->off, it->id});
        }
    }
}

static void by_diff(DState &S, std::shared_ptr<const DViews> x432_prev[2], const std::vector<DView> &views, uint32_t &mapped, uint32_t &unmapped, uint32_t &map_failed) {
    const int x432_k = 0;
    {
#include "x432_body.inc"
    }
}

int main() {
    std::mt19937_64 rng(432);
    const uint64_t P = 0x4000;
    auto rnd = [&rng](uint64_t n) { return n == 0 ? 0 : rng() % n; };
    uint64_t kept_total = 0, dropped_total = 0, added_total = 0;
    for (int c = 0; c < 20000; c++) {
        DState S;
        const uint64_t file = (64 + rnd(64)) * P;
        uint32_t id = 1;
        for (uint64_t o = rnd(4) * P; o < file;) { // disjoint imported ranges with holes
            const uint64_t sz = (1 + rnd(6)) * P;
            if (o + sz > file) break;
            S.bos.push_back({o, sz, id++, 0});
            o += sz + rnd(3) * P;
        }
        auto views = [&](int n) {
            std::vector<DView> v;
            uint64_t va = 0x100000;
            for (int i = 0; i < n; i++) {
                va += rnd(3) * P;
                const uint64_t sz = (1 + rnd(8)) * P;
                v.push_back({va, sz, rnd(file / P) * P, "", false, false});
                va += sz;
            }
            return v;
        };
        auto oldp = std::make_shared<DViews>();
        oldp->v = views(static_cast<int>(rnd(40)));
        std::vector<DView> nv = oldp->v;
        const int edits = static_cast<int>(rnd(6));
        for (int e = 0; e < edits && !nv.empty(); e++) {
            const size_t i = rnd(nv.size());
            switch (rnd(6)) {
            case 0: nv.erase(nv.begin() + static_cast<std::ptrdiff_t>(i)); break;
            case 1: nv[i].off = rnd(file / P) * P; break;
            case 2:
                if (nv[i].size > P) nv[i].size -= P; // shrink at the end
                break;
            case 3:
                if (nv[i].size > P) { // cut the front off
                    nv[i].va += P;
                    nv[i].off += P;
                    nv[i].size -= P;
                }
                break;
            case 4:
                if (nv[i].size > 2 * P) { // split in two, the second part elsewhere in the file
                    DView b = nv[i];
                    const uint64_t h = (nv[i].size / P / 2) * P;
                    nv[i].size = h;
                    b.va += h;
                    b.size -= h;
                    b.off = rnd(file / P) * P;
                    nv.insert(nv.begin() + static_cast<std::ptrdiff_t>(i) + 1, b);
                }
                break;
            default: { // grow into the gap behind it, or a new view in that gap
                const uint64_t end = nv[i].va + nv[i].size;
                const uint64_t lim = i + 1 < nv.size() ? nv[i + 1].va : end + 4 * P;
                if (lim >= end + P) {
                    if (rnd(2) == 0) nv[i].size += P;
                    else nv.insert(nv.begin() + static_cast<std::ptrdiff_t>(i) + 1, DView{end, P, rnd(file / P) * P, "", false, false});
                }
            }
            }
        }
        if (rnd(10) == 0) nv = views(static_cast<int>(rnd(40))); // sometimes a wholly new list
        for (size_t i = 1; i < nv.size(); i++) {
            if (nv[i - 1].va + nv[i - 1].size > nv[i].va) {
                std::printf("FAIL: case %d: the generator made overlapping views\n", c);
                return 1;
            }
        }
        Dev dev;
        g_dev = &dev;
        whole(S, oldp->v, S.maps);
        for (const auto &m : S.maps) dev.map_shared(m.id, m.bo_off, m.size, m.va);
        const size_t before = S.maps.size();
        std::shared_ptr<const DViews> prev[2] = {oldp, nullptr};
        uint32_t mapped = 0, unmapped = 0, failed = 0;
        by_diff(S, prev, nv, mapped, unmapped, failed);
        std::vector<DMap> want;
        whole(S, nv, want);
        bool ok = dev.errors == 0 && want == S.maps && dev.live.size() == want.size() && before - unmapped + mapped == want.size();
        if (ok) {
            size_t i = 0;
            for (const auto &[va, m] : dev.live) ok = ok && m == want[i++];
        }
        if (!ok) {
            std::printf("FAIL: case %d: %zu old views, %zu new; mappings %zu, the whole rebuild %zu, the device %zu, device errors %d\n", c, oldp->v.size(), nv.size(), S.maps.size(),
                        want.size(), dev.live.size(), dev.errors);
            return 1;
        }
        kept_total += before - unmapped;
        dropped_total += unmapped;
        added_total += mapped;
    }
    std::printf("PASS: 20000 cases; mappings kept %llu, dropped %llu, added %llu\n", static_cast<unsigned long long>(kept_total), static_cast<unsigned long long>(dropped_total),
                static_cast<unsigned long long>(added_total));
    return 0;
}
