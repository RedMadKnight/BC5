// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0439 (tag pc439): det test of the prefix draw test through chains, on a stand-in chain (no title bytes).
// The functions below are copies of the generated unit's ib_has_draw (k439/new/bc5LleAgc.cpp, the exp 0157 test) and
// pc439_chain_draw (mkpa439.py, tag pc439) with the mapping test passed in. Cases:
//   1. a top level with a NOP and a chain to piece A, A with a call to piece B, B holding a DRAW_INDEX_2 (0x27):
//      top-level test false, chain test true (the third title's shape: draws only in pieces);
//   2. the same without the draw: both false (no prefix where nothing draws);
//   3. a draw in the top level: the top-level test true (the old path unchanged).
// BC5_PC439_PLANT_TOP (the chain test reduced to the top level, the defect) must FAIL case 1.
#include "bc5/ib_chain.hpp"

#include <cstdint>
#include <cstdio>
#include <sys/mman.h>
#include <vector>

static int g_fail = 0;
#define CHECK(x) do { if (!(x)) { std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #x); g_fail++; } } while (0)

static bool ib_has_draw(const uint32_t* ib, uint32_t num_dwords) {
    for (uint32_t i = 0; i < num_dwords;) {
        const uint32_t h = ib[i], type = h >> 30u;
        uint32_t len = 1;
        if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
        if (i + len > num_dwords) break;
        if (type == 3) {
            const uint32_t op = (h >> 8u) & 0xffu;
            if (op == 0x24 || op == 0x25 || op == 0x27 || op == 0x2c || op == 0x2d || op == 0x35 || op == 0x38) return true;
        }
        i += len;
    }
    return false;
}
static bool pc439_chain_draw(const uint32_t* ib, uint32_t num_dwords) {
#ifdef BC5_PC439_PLANT_TOP
    return ib_has_draw(ib, num_dwords);
#else
    const auto cr = bc5::ib_chain::collect(ib, num_dwords, [](uint64_t, uint64_t) { return true; }, true);
    for (size_t k = 1; k < cr.pieces.size(); k++)
        if (ib_has_draw(cr.pieces[k].src, cr.pieces[k].n)) return true;
    return false;
#endif
}

static void ib_packet(std::vector<std::uint32_t>& w, const std::uint32_t* target, std::size_t n, bool chain) {
    const auto a = reinterpret_cast<std::uintptr_t>(target);
    w.push_back(0xC0023F00u); // INDIRECT_BUFFER, 4 dwords
    w.push_back(static_cast<std::uint32_t>(a) & ~3u);
    w.push_back(static_cast<std::uint32_t>(a >> 32) & 0xffu);
    w.push_back(static_cast<std::uint32_t>(n) | (chain ? (1u << 20) : 0u));
}
// The chain walk takes 8 bits of the address high dword (ib_chain.hpp), so the stand-ins live below 2^40.
static std::uint32_t* low_copy(const std::vector<std::uint32_t>& v, std::size_t slot) {
    static std::uint32_t* base = [] {
        void* p = mmap(reinterpret_cast<void*>(0x2000000000ull), 1u << 16, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
        return p == MAP_FAILED ? nullptr : static_cast<std::uint32_t*>(p);
    }();
    if (base == nullptr) return nullptr;
    std::uint32_t* d = base + slot * 1024;
    for (std::size_t i = 0; i < v.size(); i++) d[i] = v[i];
    return d;
}

static void one(bool draw, std::size_t slot0, bool& top, bool& chain) {
    std::vector<std::uint32_t> b = {0xC0007900u | 0u, 0xFFFF1000u}; // filler: a 1-dword NOP after a 2-dword packet
    b = {0xFFFF1000u, 0xFFFF1000u};
    if (draw) b.insert(b.end(), {0xC0032700u, 0u, 0u, 3u, 0u}); // DRAW_INDEX_2 (0x27), 5 dwords
    const std::uint32_t* bl = low_copy(b, slot0);
    std::vector<std::uint32_t> a = {0xFFFF1000u};
    ib_packet(a, bl, b.size(), false); // a call to B
    const std::uint32_t* al = low_copy(a, slot0 + 1);
    std::vector<std::uint32_t> t = {0xFFFF1000u};
    ib_packet(t, al, a.size(), true); // the chain to A
    const std::uint32_t* tl = low_copy(t, slot0 + 2);
    top   = ib_has_draw(tl, static_cast<uint32_t>(t.size()));
    chain = pc439_chain_draw(tl, static_cast<uint32_t>(t.size()));
}

int main() {
    if (low_copy({0u}, 15) == nullptr) {
        std::printf("FAIL: no low mapping\n");
        return 1;
    }
    bool top = true, chain = false;
    one(true, 0, top, chain);
    std::printf("case 1 (draw in piece B): top %d chain %d\n", top, chain);
    CHECK(!top);
    CHECK(chain);
    one(false, 4, top, chain);
    std::printf("case 2 (no draw): top %d chain %d\n", top, chain);
    CHECK(!top);
    CHECK(!chain);
    std::vector<std::uint32_t> d = {0xFFFF1000u, 0xC0032700u, 0u, 0u, 3u, 0u};
    const std::uint32_t* dl = low_copy(d, 8);
    top = ib_has_draw(dl, static_cast<uint32_t>(d.size()));
    std::printf("case 3 (draw in the top level): top %d\n", top);
    CHECK(top);
    std::printf("%s (%d failures)\n", g_fail == 0 ? "PASS" : "FAIL", g_fail);
    return g_fail == 0 ? 0 : 1;
}
