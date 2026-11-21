// SPDX-License-Identifier: GPL-2.0-only
// BC5 exp 0439 (tag ib439): det tests of bc5/ib_chain.hpp (BC5_DIRECT_IB_CHAIN), synthetic buffers only.
//   g++ -std=c++20 -O1 -I<repo>/backend/include test_ib0439.cpp -o t && ./t          (PASS expected)
//   g++ -std=c++20 -O1 -DBC5_IB439_PLANT -I<repo>/backend/include test_ib0439.cpp -o tp && ./tp   (FAIL expected)
// 1. a 73-segment chain (the third title's frame shape, exp 0440) is collected whole, every segment at depth 0, and a
//    label write in its last segment is found by a writer scan over the pieces;
// 2. chain and call mixed: calls keep the 3-level limit, a chain from a depth-3 piece is still followed;
// 3. a chain cycle is refused;
// 4. switch off: collect() gives exactly what direct.cpp's loop gave before exp 0439 (verbatim copy below), over 2000
//    random IB trees with chains and calls;
// 5. with the switch on, a tree without chain bits gives the same pieces as with it off.
#include "bc5/ib_chain.hpp"

#include <cstdio>
#include <memory>
#include <random>
#include <vector>
#include <cstdlib>
#include <sys/mman.h>

using bc5::ib_chain::collect;
namespace ic = bc5::ib_chain;

static int g_fail = 0;
#define CHECK(c)                                                                                                       \
    do {                                                                                                               \
        if (!(c)) {                                                                                                    \
            std::printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #c);                                                    \
            g_fail++;                                                                                                  \
        }                                                                                                              \
    } while (0)

// Buffers live in one mapping below 2^40 (an INDIRECT_BUFFER carries a 40-bit address, as the title's guest addresses
// are); each buffer is a fixed slot of 4096 dwords, used through a small span-like view.
struct Buf {
    std::uint32_t *p = nullptr;
    std::size_t n = 0;
    void push_back(std::uint32_t v) { p[n++] = v; }
    const std::uint32_t *data() const { return p; }
    std::size_t size() const { return n; }
    std::uint32_t &operator[](std::size_t i) { return p[i]; }
};
struct Arena {
    static constexpr std::size_t kSlot = 4096;
    std::uint32_t *base = nullptr;
    std::size_t used = 0;
    std::vector<std::unique_ptr<Buf>> bufs;
    Arena() {
        static std::uintptr_t next = 0x1000000000ull;
        void *m = mmap(reinterpret_cast<void *>(next), 512 * kSlot * 4, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
        if (m == MAP_FAILED || reinterpret_cast<std::uintptr_t>(m) >= (1ull << 40)) { std::printf("FAIL: no mapping below 2^40\n"); std::exit(2); }
        base = static_cast<std::uint32_t *>(m);
        next += 512 * kSlot * 4;
    }
    ~Arena() { munmap(base, 512 * kSlot * 4); }
    Buf &make(std::size_t n_nops) {
        bufs.push_back(std::make_unique<Buf>());
        Buf &b = *bufs.back();
        b.p = base + kSlot * used++;
        for (std::size_t i = 0; i < n_nops; ++i) b.push_back(0xffff1000u); // header-only NOP
        return b;
    }
};
static void ib(Buf &b, const Buf &t, bool chain) {
    const auto a = reinterpret_cast<std::uint64_t>(t.data());
    b.push_back(0xC0023F00u); // PKT3(INDIRECT_BUFFER, 2)
    b.push_back(static_cast<std::uint32_t>(a & 0xfffffffcu));
    b.push_back(static_cast<std::uint32_t>((a >> 32) & 0xffu));
    b.push_back(static_cast<std::uint32_t>(t.size()) | (chain ? ic::kChainBit : 0u));
}
static void write_data(Buf &b, std::uint64_t addr, std::uint32_t v) {
    b.push_back(0xC0033700u);            // PKT3(WRITE_DATA, 3)
    b.push_back(2u << 8);                // dst sel 2 (memory)
    b.push_back(static_cast<std::uint32_t>(addr));
    b.push_back(static_cast<std::uint32_t>(addr >> 32));
    b.push_back(v);
}
// A label-writer scan over the collected pieces (flat per piece, as the host's scans are).
static bool writes(const ic::Result &r, std::uint64_t addr) {
    for (const auto &p : r.pieces)
        for (std::size_t i = 0; i + 4 < p.n;) {
            const std::uint32_t h = p.src[i];
            std::size_t len = 1;
            if ((h >> 30) == 3) {
                const std::uint32_t c = (h >> 16) & 0x3fff;
                len = c == 0x3fff ? 1 : c + 2;
            }
            if ((h >> 30) == 3 && ((h >> 8) & 0xff) == 0x37 && (p.src[i + 2] | (std::uint64_t(p.src[i + 3]) << 32)) == addr) return true;
            i += len;
        }
    return false;
}

// direct.cpp submit_impl's piece loop before exp 0439, verbatim in substance (nested_targets with no mapped filter).
struct OldPiece {
    const std::uint32_t *src;
    std::size_t n;
    int depth;
};
static std::vector<OldPiece> old_collect(const std::uint32_t *root, std::size_t n) {
    std::vector<OldPiece> pieces{{root, n, 0}};
    for (std::size_t k = 0; k < pieces.size() && pieces.size() < 64; ++k) {
        if (pieces[k].depth >= 3) continue;
        std::vector<ic::Target> targets;
        ic::targets_of(std::span<const std::uint32_t>(pieces[k].src, pieces[k].n), {}, targets);
        for (const auto &t : targets) {
            bool seen = false;
            for (const auto &q : pieces) seen = seen || (q.src == t.src && q.n == t.n);
            if (seen) continue;
            pieces.push_back({t.src, t.n, pieces[k].depth + 1});
        }
    }
    return pieces;
}
static bool same(const ic::Result &r, const std::vector<OldPiece> &o) {
    if (r.pieces.size() != o.size()) return false;
    for (std::size_t i = 0; i < o.size(); ++i)
        if (r.pieces[i].src != o[i].src || r.pieces[i].n != o[i].n || r.pieces[i].depth != o[i].depth) return false;
    return true;
}

int main() {
    const std::uint64_t kLabel0 = 0x2000000000ull;
    { // 1. the 73-segment chain: build from the tail so each segment can point at the next
        Arena ar;
        std::vector<Buf *> seg(73);
        for (int k = 72; k >= 0; --k) {
            auto &b = ar.make(k == 0 ? 99 : 120);
            if (k == 72) write_data(b, kLabel0, 2); // the frame's label-0 write, last segment
            else ib(b, *seg[k + 1], true);         // each segment ends in a chain to the next
            seg[k] = &b;
        }
        const auto r = collect(seg[0]->data(), seg[0]->size(), {}, true);
        CHECK(!r.cycle && !r.chain_cap);
        CHECK(r.pieces.size() == 73);
        CHECK(r.chains == 72);
        CHECK(r.longest_chain == 72);
        bool all0 = true;
        for (const auto &p : r.pieces) all0 = all0 && p.depth == 0;
        CHECK(all0);
        CHECK(writes(r, kLabel0));
        const auto off = collect(seg[0]->data(), seg[0]->size(), {}, false); // today: cut after segment 3
        CHECK(off.pieces.size() == 4);
        CHECK(!writes(off, kLabel0));
        std::printf("1. 73-segment chain: on %zu pieces, %zu chains, longest %zu, label-0 write %s; off %zu pieces, write %s\n", r.pieces.size(), r.chains,
                    r.longest_chain, writes(r, kLabel0) ? "found" : "MISSING", off.pieces.size(), writes(off, kLabel0) ? "found" : "missing");
    }
    { // 2. calls keep their limit, a chain from the deepest call level is still followed
        Arena ar;
        auto &e = ar.make(8);
        write_data(e, kLabel0 + 0x40, 1);
        auto &d = ar.make(9);
        auto &c = ar.make(4);
        ib(c, d, false); // a 4th-level call: not followed
        ib(c, e, true);  // a chain at level 3: followed
        auto &b = ar.make(5);
        ib(b, c, false);
        auto &a = ar.make(6);
        ib(a, b, false);
        auto &h = ar.make(7);
        ib(h, a, false);
        const auto r = collect(h.data(), h.size(), {}, true);
        bool has_d = false, has_e = false;
        int de = -1;
        for (const auto &p : r.pieces) {
            has_d = has_d || p.src == d.data();
            if (p.src == e.data()) { has_e = true; de = p.depth; }
        }
        CHECK(!has_d);
        CHECK(has_e && de == 3);
        CHECK(r.over_depth == 1);
        CHECK(writes(r, kLabel0 + 0x40));
        std::printf("2. calls and a chain: 4th-level call %s, chain from level 3 %s at depth %d, over depth %zu\n", has_d ? "FOLLOWED" : "not followed",
                    has_e ? "followed" : "NOT FOLLOWED", de, r.over_depth);
    }
    { // 3. a chain cycle
        Arena ar;
        auto &x = ar.make(3);
        auto &y = ar.make(3);
        ib(y, x, true);
        ib(x, y, true);
        y[6] = static_cast<std::uint32_t>(x.size()) | ic::kChainBit; // the sizes as they are once both packets exist
        x[6] = static_cast<std::uint32_t>(y.size()) | ic::kChainBit;
        const auto r = collect(x.data(), x.size(), {}, true);
        CHECK(r.cycle);
        auto &s = ar.make(2); // a chain to itself
        ib(s, s, true);
        s[5] = static_cast<std::uint32_t>(s.size()) | ic::kChainBit;
        CHECK(collect(s.data(), s.size(), {}, true).cycle);
        std::printf("3. chain cycles: x<->y %s, self %s\n", r.cycle ? "refused" : "NOT REFUSED", collect(s.data(), s.size(), {}, true).cycle ? "refused" : "NOT REFUSED");
    }
    { // 4./5. random trees: off == the old loop; on without chain bits == off
        std::mt19937 rng(439);
        int diff_off = 0, diff_on_nochain = 0;
        for (int it = 0; it < 2000; ++it) {
            for (int pass = 0; pass < 2; ++pass) {
                const bool chains = pass == 0;
                Arena ar;
                const int nb = 2 + static_cast<int>(rng() % 40);
                std::vector<Buf *> bs;
                for (int k = 0; k < nb; ++k) bs.push_back(&ar.make(1 + rng() % 6));
                for (int k = 0; k < nb; ++k) { // only forward edges: no cycles in the random trees
                    const int edges = static_cast<int>(rng() % 4);
                    for (int j = 0; j < edges && k + 1 < nb; ++j) {
                        const int t = k + 1 + static_cast<int>(rng() % (nb - k - 1));
                        ib(*bs[k], *bs[t], chains && (rng() % 2) == 0);
                        bs[k]->push_back(0xffff1000u);
                    }
                }
                // the targets' sizes were taken when the packet was written; freeze them by re-writing every size dword
                for (auto *b : bs)
                    for (std::size_t i = 0; i + 3 < b->size(); ++i)
                        if ((*b)[i] == 0xC0023F00u)
                            for (auto *t : bs)
                                if (reinterpret_cast<std::uint64_t>(t->data()) == ((std::uint64_t((*b)[i + 2]) << 32) | (*b)[i + 1]))
                                    (*b)[i + 3] = static_cast<std::uint32_t>(t->size()) | ((*b)[i + 3] & ic::kChainBit);
                const auto o = old_collect(bs[0]->data(), bs[0]->size());
                if (chains && !same(collect(bs[0]->data(), bs[0]->size(), {}, false), o)) diff_off++;
                if (!chains && !same(collect(bs[0]->data(), bs[0]->size(), {}, true), o)) diff_on_nochain++;
            }
        }
        CHECK(diff_off == 0);
        CHECK(diff_on_nochain == 0);
        std::printf("4. 2000 random trees: off differs from the old loop in %d; 5. on without chain bits differs in %d\n", diff_off, diff_on_nochain);
    }
    std::printf("%s (%d failed checks)\n", g_fail == 0 ? "PASS" : "FAIL", g_fail);
    return g_fail == 0 ? 0 : 1;
}
