// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0439 (tag fa439): det test of fa0439.hpp (patch 0001's flat_aperture_fix scan) on synthetic programs.
// No title code: the instruction words are built from their encodings (llvm-mc gfx1013, see the header).
// BC5_FA439_PLANT_SKIP (every second push missed) and BC5_FA439_PLANT_BREV (the LDS half left) must FAIL.
#include "bc5/fa0439.hpp"

#include <cstdio>
#include <vector>

static int g_fail = 0;
#define CHECK(x) do { if (!(x)) { std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #x); g_fail++; } } while (0)

static constexpr std::uint32_t kEnd = 0xBF810000u, kNop = 0xBF800000u;
static std::uint32_t brev(std::uint32_t s, std::uint32_t v) { return 0xBE800B80u | (s << 16) | v; }
// v_med3_u32 v<d>, s<s>, 0x70000000 (literal), v<p>
static void med3(std::vector<std::uint32_t> &w, std::uint32_t d, std::uint32_t s, std::uint32_t p, std::uint32_t lit = 0x70000000u) {
    w.push_back(0xD5590000u | d);
    w.push_back(s | (0xffu << 9) | ((256u + p) << 18));
    w.push_back(lit);
}

int main() {
    { // 1. the cloth/reflection form: one brev, three pushes back to back (as in the title's box-node push of three children)
        std::vector<std::uint32_t> w{kNop, brev(49, 1), kNop};
        med3(w, 7, 49, 8); med3(w, 6, 49, 8); med3(w, 5, 49, 8);
        w.push_back(kEnd);
        const auto r = bc5::fa439::rewrite(w.data(), static_cast<std::uint32_t>(w.size()));
        CHECK(r.sites == 3);
        CHECK(r.brevs == 1);
        CHECK(w[1] == brev(49, 4));
        CHECK(w[5] == 0x10000000u && w[8] == 0x10000000u && w[11] == 0x10000000u);
        const auto again = bc5::fa439::rewrite(w.data(), static_cast<std::uint32_t>(w.size()));
        CHECK(again.sites == 0 && again.brevs == 0); // idempotent
    }
    { // 2. brev already 4 (a program met twice): the literal still rewritten, the brev not counted
        std::vector<std::uint32_t> w{brev(20, 4)};
        med3(w, 1, 20, 2);
        w.push_back(kEnd);
        const auto r = bc5::fa439::rewrite(w.data(), static_cast<std::uint32_t>(w.size()));
        CHECK(r.sites == 1 && r.brevs == 0 && w[3] == 0x10000000u);
    }
    { // 3. untouched: no brev of that SGPR; another literal; the pattern after s_endpgm; brev farther than 1,024 dwords
        std::vector<std::uint32_t> w{brev(30, 1)};
        med3(w, 1, 31, 2);                    // SGPR 31 has no brev
        med3(w, 1, 30, 2, 0x60000000u);       // not the private aperture literal
        w.push_back(kEnd);
        med3(w, 1, 30, 2);                    // after s_endpgm
        const auto before = w;
        const auto r = bc5::fa439::rewrite(w.data(), static_cast<std::uint32_t>(w.size()));
        CHECK(r.sites == 0 && r.brevs == 0 && w == before);
        std::vector<std::uint32_t> f{brev(40, 1)};
        for (int i = 0; i < 1100; i++) f.push_back(kNop);
        med3(f, 1, 40, 2);
        f.push_back(kEnd);
        const auto rf = bc5::fa439::rewrite(f.data(), static_cast<std::uint32_t>(f.size()));
        CHECK(rf.sites == 0);
    }
    { // 4. the third title's cloth layout (exp 0441's listing of 0x8000143400 / 0x8000175900): 18 pushes per program, in six
      //    box-node blocks of three behind their own s_brev_b32, ~11,900 dwords to s_endpgm. Synthetic: the same shape.
        std::vector<std::uint32_t> w(200, kNop);
        const std::uint32_t sg[6] = {49, 48, 47, 46, 45, 44};
        std::vector<std::size_t> lits;
        for (int b = 0; b < 6; b++) {
            w.push_back(brev(sg[b], 1));
            for (int i = 0; i < 40; i++) w.push_back(kNop);
            for (int p = 0; p < 3; p++) {
                med3(w, 7 - static_cast<std::uint32_t>(p), sg[b], 8);
                lits.push_back(w.size() - 1);
            }
            for (int i = 0; i < 1800; i++) w.push_back(kNop);
        }
        w.push_back(kEnd);
        const auto r = bc5::fa439::rewrite(w.data(), static_cast<std::uint32_t>(w.size()));
        std::printf("cloth layout: %u pushes, %u s_brev_b32 rewritten in %zu dwords\n", r.sites, r.brevs, w.size());
        CHECK(r.sites == 18);
        CHECK(r.brevs == 6);
        bool all = true;
        for (const auto k : lits) all = all && w[k] == 0x10000000u;
        CHECK(all);
    }
    { // 5. exp 0441's variant (c): the brev's SGPR reused by other writers between groups (s_mov_b32 s49, 0x5 here), each
      //    group behind its own brev: the nearest brev before a push is the one rewritten; the s_mov is untouched
        const std::uint32_t smov = 0xBE8003FFu | (49u << 16); // s_mov_b32 s49, literal
        std::vector<std::uint32_t> w{brev(49, 1)};
        med3(w, 7, 49, 8);
        w.push_back(smov);
        w.push_back(5);
        for (int i = 0; i < 30; i++) w.push_back(kNop);
        w.push_back(brev(49, 1));
        med3(w, 6, 49, 8);
        med3(w, 5, 49, 8);
        w.push_back(kEnd);
        const auto r = bc5::fa439::rewrite(w.data(), static_cast<std::uint32_t>(w.size()));
        CHECK(r.sites == 3 && r.brevs == 2);
        CHECK(w[0] == brev(49, 4) && w[4] == smov && w[5] == 5 && w[36] == brev(49, 4));
    }
    std::printf("%s (%d failures)\n", g_fail == 0 ? "PASS" : "FAIL", g_fail);
    return g_fail == 0 ? 0 : 1;
}
