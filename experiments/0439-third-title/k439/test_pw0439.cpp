// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0439 (tag pw439): det test of the piece filter options (new/be/direct.cpp, BC5_0439_PIECE_WAITS) with
// the real policy::filter (the private backend copy new/be/policy.cpp). A stand-in piece: a memory WAIT_REG_MEM on a
// label the piece does not write (another queue's label, 0x2000008080) at dword 0, then a WRITE_DATA at dword 7. The
// root's options carry keep_wait_offsets {0} and drop_offsets {7} (root offsets that happen to equal the piece's).
//   mode 0, empty root lists: the wait is dropped (the defect: no cross-queue wait in a piece reaches the GPU);
//   mode 0, the root lists: the wait is kept and the WRITE_DATA dropped, both by the root's offsets (the leak);
//   mode 1, the root lists: the wait dropped, the WRITE_DATA kept (the lists do not reach the piece);
//   mode 2, the root lists: the wait kept as a wait of its own (not by a root offset), the WRITE_DATA kept.
// BC5_PW439_PLANT_NOCLEAR (mode 1 leaves the lists) must FAIL.
#include "bc5/policy.hpp"

#include <cstdint>
#include <cstdio>
#include <span>
#include <vector>

using namespace bc5;
static int g_fail = 0;
#define CHECK(x) do { if (!(x)) { std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #x); g_fail++; } } while (0)

static policy::FilterOptions piece_opts(const policy::FilterOptions& fopt, int pw439) { // as in new/be/direct.cpp
    policy::FilterOptions nested_opt = fopt;
    nested_opt.stat_sample_va = 0;
#ifndef BC5_PW439_PLANT_NOCLEAR
    if (pw439 >= 1) {
        nested_opt.drop_offsets.clear();
        nested_opt.keep_wait_offsets.clear();
    }
#endif
    if (pw439 >= 2) nested_opt.self_waits_only = false;
    return nested_opt;
}

struct Out {
    bool wait_kept, write_kept;
    policy::FilterStats st;
};
static Out run(const policy::FilterOptions& root, int mode) {
    const std::vector<std::uint32_t> piece = {
        0xC0053C00u, 0x00000013u, 0x00008080u, 0x00000020u, 1u, 0xffffffffu, 4u, // WAIT_REG_MEM mem, ==, 0x2000008080 == 1
        0xC0033700u, 0x00000500u, 0x00009000u, 0x00000020u, 7u,                   // WRITE_DATA to 0x2000009000
    };
    std::vector<std::uint32_t> out(piece.size(), 0);
    Out o{};
    policy::filter(policy::Policy::builtin(), std::span<const std::uint32_t>(piece), std::span<std::uint32_t>(out), piece_opts(root, mode), o.st);
    o.wait_kept  = out[0] == piece[0];
    o.write_kept = out[7] == piece[7];
    return o;
}

int main() {
    policy::FilterOptions empty;
    policy::FilterOptions lists;
    lists.keep_wait_offsets = {0};
    lists.drop_offsets      = {7};
    Out a = run(empty, 0), b = run(lists, 0), c = run(lists, 1), d = run(lists, 2);
    std::printf("mode 0, empty lists: wait %d write %d (unsatisfiable drops %llu)\n", a.wait_kept, a.write_kept, (unsigned long long)a.st.unsatisfiable_wait_drops);
    std::printf("mode 0, root lists:  wait %d write %d (root-offset keeps %llu, root-offset drops %llu)\n", b.wait_kept, b.write_kept, (unsigned long long)b.st.ring_ordered_waits,
                (unsigned long long)b.st.offset_drops);
    std::printf("mode 1, root lists:  wait %d write %d (unsatisfiable drops %llu, root-offset drops %llu)\n", c.wait_kept, c.write_kept, (unsigned long long)c.st.unsatisfiable_wait_drops,
                (unsigned long long)c.st.offset_drops);
    std::printf("mode 2, root lists:  wait %d write %d (root-offset keeps %llu)\n", d.wait_kept, d.write_kept, (unsigned long long)d.st.ring_ordered_waits);
    CHECK(!a.wait_kept && a.st.unsatisfiable_wait_drops == 1 && a.write_kept);
    CHECK(b.wait_kept && b.st.ring_ordered_waits == 1 && !b.write_kept && b.st.offset_drops == 1);
    CHECK(!c.wait_kept && c.st.unsatisfiable_wait_drops == 1 && c.write_kept && c.st.offset_drops == 0);
    CHECK(d.wait_kept && d.st.ring_ordered_waits == 0 && d.write_kept);
    std::printf("%s (%d failures)\n", g_fail == 0 ? "PASS" : "FAIL", g_fail);
    return g_fail == 0 ? 0 : 1;
}
