// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0439 (tag cw439): det test of the chain-following writer scan (cw0439.hpp) on a stand-in chain (no title
// bytes): a top-level IB with a NOP and an INDIRECT_BUFFER chain (bit 20 of its size dword set) to piece A, which holds
// a RELEASE_MEM of label L1 and a call (bit 20 clear) to piece B with a WRITE_DATA of label L2. The walk must visit A and
// B (not the top one) and give each piece's packet starts, so both labels reach the caller. BC5_CW439_PLANT_FIRST (the
// first chained piece skipped) must FAIL.
#include "bc5/cw0439.hpp"

#include <cstdint>
#include <sys/mman.h>
#include <cstdio>
#include <vector>

static int g_fail = 0;
#define CHECK(x) do { if (!(x)) { std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #x); g_fail++; } } while (0)

static void ib_packet(std::vector<std::uint32_t> &w, const std::uint32_t *target, std::size_t n, bool chain) {
    const auto a = reinterpret_cast<std::uintptr_t>(target);
    w.push_back(0xC0023F00u); // INDIRECT_BUFFER, 4 dwords
    w.push_back(static_cast<std::uint32_t>(a) & ~3u);
    w.push_back(static_cast<std::uint32_t>(a >> 32) & 0xffu);
    w.push_back(static_cast<std::uint32_t>(n) | (chain ? (1u << 20) : 0u));
}

// The chain walk takes 8 bits of an INDIRECT_BUFFER's address high dword (a 40-bit GPU VA, ib_chain.hpp targets_of), so
// the stand-in pieces live in a mapping below 2^40, as the guest's do.
static std::uint32_t *low_copy(const std::vector<std::uint32_t> &v, std::size_t slot) {
    static std::uint32_t *base = [] {
        void *p = mmap(reinterpret_cast<void *>(0x2000000000ull), 1u << 16, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
        return p == MAP_FAILED ? nullptr : static_cast<std::uint32_t *>(p);
    }();
    if (base == nullptr) return nullptr;
    std::uint32_t *d = base + slot * 1024;
    for (std::size_t i = 0; i < v.size(); i++) d[i] = v[i];
    return d;
}

int main() {
    std::vector<std::uint32_t> b = {
        0xC0033700u, 0x00000500u, 0x00002000u, 0x00000020u, 7u, // WRITE_DATA to memory (DST_SEL 5) of L2 = 0x2000002000
        0xFFFF1000u, 0xFFFF1000u, 0xFFFF1000u,
    };
    std::vector<std::uint32_t> a = {
        0xC0064900u, 0x00000528u, 0x40010000u, 0x00001000u, 0x00000020u, 1u, 0u, 0u, // RELEASE_MEM of L1 = 0x2000001000
    };
    const std::uint32_t *bl = low_copy(b, 0);
    if (bl == nullptr) {
        std::printf("FAIL: no low mapping\n");
        return 1;
    }
    ib_packet(a, bl, b.size(), false); // a call to B
    const std::uint32_t *al = low_copy(a, 1);
    std::vector<std::uint32_t> top = {0xFFFF1000u};
    ib_packet(top, al, a.size(), true); // the chain to A
    const std::uint32_t *tl = low_copy(top, 2);
    std::vector<std::uint64_t> labels;
    std::size_t visited = 0;
    const auto mapped = [](std::uint64_t, std::uint64_t) { return true; };
    const std::size_t n = bc5::cw439::each_piece(tl, static_cast<std::uint32_t>(top.size()), mapped,
                                                 [&](const std::uint32_t *src, std::uint32_t pn, const std::vector<std::uint32_t> &st) {
                                                     visited++;
                                                     for (const auto q : st) {
                                                         const std::uint32_t *w = src + q;
                                                         const std::uint32_t op = (w[0] >> 8u) & 0xffu;
                                                         if (op == 0x49) labels.push_back((w[3] & ~3u) | (static_cast<std::uint64_t>(w[4] & 0xffffu) << 32u));
                                                         if (op == 0x37) labels.push_back((w[2] & ~3u) | (static_cast<std::uint64_t>(w[3] & 0xffffu) << 32u));
                                                     }
                                                     (void)pn;
                                                 });
    std::printf("pieces below the top: %zu, visited %zu, labels %zu\n", n, visited, labels.size());
    CHECK(n == 2);
    CHECK(visited == 2);
    bool l1 = false, l2 = false;
    for (const auto l : labels) l1 = l1 || l == 0x2000001000ull, l2 = l2 || l == 0x2000002000ull;
    CHECK(l1);
    CHECK(l2);
    const auto st = bc5::cw439::starts(bl, b.size());
    CHECK(st.size() == 4 && st[0] == 0 && st[1] == 5 && st[3] == 7); // WRITE_DATA, then three 1-dword NOP fillers (count 0x3fff)
    std::printf("%s (%d failures)\n", g_fail == 0 ? "PASS" : "FAIL", g_fail);
    return g_fail == 0 ? 0 : 1;
}
