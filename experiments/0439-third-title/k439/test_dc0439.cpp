// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0439 (tag dc439): the offline test of dc0439.hpp. No GPU: the block lookup on a synthetic context,
// the decompress IB's packets, the backend's policy filter (Policy::builtin, as the host uses it) over the IB, and the
// state stack putting the title's context back at the pop. Built in the ubuntu distrobox against the shared backend
// archive (test_dc0439.sh).
#include "bc5/dc0439.hpp"
#include "bc5/policy.hpp"
#include "bc5/state_stack.hpp"

#include <cstdio>
#include <cstdlib>
#include <map>

static int g_fail = 0;
#define CHECK(c)                                                                 \
    do {                                                                         \
        if (!(c)) {                                                              \
            std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #c);             \
            g_fail++;                                                            \
        }                                                                        \
    } while (0)

using bc5::state_stack::Context;

// Every packet of an IB: (op, offset, length); false when one runs past the end.
static bool walk(const std::vector<std::uint32_t> &ib, std::vector<std::array<std::uint32_t, 3>> &out) {
    for (std::size_t i = 0; i < ib.size();) {
        const std::uint32_t h = ib[i];
        if ((h >> 30) != 3) return false;
        const std::uint32_t len = ((h >> 16) & 0x3fffu) + 2;
        if (i + len > ib.size()) return false;
        out.push_back({(h >> 8) & 0xffu, static_cast<std::uint32_t>(i), len});
        i += len;
    }
    return true;
}

// The context and SH/UCONFIG writes of an IB: reg -> value, per kind.
static void writes(const std::vector<std::uint32_t> &ib, std::map<std::uint32_t, std::uint32_t> &c, std::map<std::uint32_t, std::uint32_t> &sh,
                   std::map<std::uint32_t, std::uint32_t> &uc) {
    std::vector<std::array<std::uint32_t, 3>> p;
    walk(ib, p);
    for (auto [op, at, len]: p) {
        auto *m = op == 0x69 ? &c : op == 0x76 ? &sh : (op == 0x79 || op == 0x7a) ? &uc : nullptr;
        if (m == nullptr) continue;
        const std::uint32_t reg = ib[at + 1] & 0xffffu;
        for (std::uint32_t k = 2; k < len; k++) (*m)[reg + k - 2] = ib[at + k];
    }
}

int main() {
    // 1. find(): MRT 2 holds the surface 0x5005160000 with its metadata 0x5007168000, MRT 0 another target.
    Context ctx;
    auto set = [&](std::uint32_t r, std::uint32_t v) {
        ctx.value[r] = v;
        ctx.valid.set(r);
    };
    const std::uint64_t surf = 0x5005160000ull, meta = 0x5007168000ull;
    set(bc5::dc439::kCbColor0Base + 0, 0x12340000u);
    for (std::uint32_t k = 0; k < 15; k++) set(bc5::dc439::kCbColor0Base + 2 * 15 + k, 0x1000u + k);
    set(bc5::dc439::kCbColor0Base + 2 * 15 + 0, static_cast<std::uint32_t>(surf >> 8));
    set(bc5::dc439::kCbColor0Base + 2 * 15 + 4, (1u << 28) | (0xau << 2)); // DCC_ENABLE, FORMAT 8_8_8_8
    set(bc5::dc439::kCbColor0Base + 2 * 15 + 13, static_cast<std::uint32_t>(meta >> 8));
    set(bc5::dc439::kCbBaseExt + 2, 0);
    set(bc5::dc439::kCbDccExt + 2, 0);
    set(bc5::dc439::kCbAttrib3 + 2, (27u << 14) | (1u << 30)); // SW_MODE 27, DCC_PIPE_ALIGNED
    set(bc5::dc439::kCbAttrib2 + 2, 0x0aaa5555u);
    auto b = bc5::dc439::find(ctx.value, ctx.valid, surf);
    CHECK(b.valid && b.mrt == 2);
    CHECK(b.base() == surf && b.dcc_base() == meta && b.dcc_enable());
    CHECK(b.sw_mode() == 27 && b.dcc_pipe_aligned() && !b.meta_linear());
    CHECK(b.attrib2 == 0x0aaa5555u && b.c[5] == 0x1005u);
    CHECK(!bc5::dc439::find(ctx.value, ctx.valid, surf + 0x10000).valid);  // another address
    CHECK(!bc5::dc439::find(ctx.value, ctx.valid, surf + 0x80).valid);     // not 256-byte aligned
    // a BASE_EXT that moves the address above 2^40 no longer matches
    set(bc5::dc439::kCbBaseExt + 2, 1);
    CHECK(!bc5::dc439::find(ctx.value, ctx.valid, surf).valid);
    set(bc5::dc439::kCbBaseExt + 2, 0);

    // 2. build(): the packets end where the IB ends, push first and pop last, MRT0 = the block, MODE 6, one draw.
    const std::uint64_t vs = 0xFE00700000ull, ps = 0xFE00700100ull;
    const auto ib = bc5::dc439::build(b, 3840, 2160, vs, ps);
    std::vector<std::array<std::uint32_t, 3>> pk;
    CHECK(walk(ib, pk));
    CHECK(!pk.empty() && pk.front()[0] == 0x12 && ib[pk.front()[1] + 1] == 1);
    CHECK(pk.back()[0] == 0x12 && ib[pk.back()[1] + 1] == 2);
    int draws = 0;
    for (auto [op, at, len]: pk)
        if (op == 0x2d) {
            draws++;
            CHECK(len == 3 && ib[at + 1] == 3 && ib[at + 2] == 2);
        }
    CHECK(draws == 1);
    std::map<std::uint32_t, std::uint32_t> c, sh, uc;
    writes(ib, c, sh, uc);
    CHECK(c[bc5::dc439::kCbColor0Base] == static_cast<std::uint32_t>(surf >> 8));
    CHECK(c[bc5::dc439::kCbColor0Base + 13] == static_cast<std::uint32_t>(meta >> 8));
    CHECK(c[bc5::dc439::kCbColor0Base + 4] == ((1u << 28) | (0xau << 2)));
    CHECK(c[bc5::dc439::kCbAttrib3] == ((27u << 14) | (1u << 30)));
    CHECK(((c[bc5::dc439::kCbColorControl] >> 4) & 7u) == 6u && ((c[bc5::dc439::kCbColorControl] >> 16) & 0xffu) == 0xccu);
    // CB_SHADER_MASK 0xf (RADV's rule for custom blend modes; 0 left every key unchanged, exp 0439 items 38-39)
    CHECK(c[bc5::dc439::kCbTargetMask] == 0xfu && c[bc5::dc439::kCbShaderMask] == 0xfu);
    CHECK(c[0x082] == (3840u | (2160u << 16)) && c[0x091] == c[0x082] && c[0x00d] == c[0x082] && c[0x095] == c[0x082]);
    CHECK(c[0x1c4] == 0 && c[0x1c5] == 0); // Z and COL export formats ZERO
    CHECK(c[0x206] == 0x300u);             // window-space positions
    CHECK(sh[0x048] == static_cast<std::uint32_t>(vs >> 8) && sh[0x049] == static_cast<std::uint32_t>(vs >> 40) && sh[0x008] == static_cast<std::uint32_t>(ps >> 8));
    CHECK(sh[0x04c] == bc5::dc439::f32(3840.0f) && sh[0x04d] == bc5::dc439::f32(2160.0f));
    CHECK(uc[0x242] == 0x11u && uc[0x25b] == 128u);
    // nothing is written into MRTs 1..7 (their FORMAT stays at the clear state's 0)
    for (std::uint32_t m = 1; m < 8; m++) CHECK(c.count(bc5::dc439::kCbColor0Base + m * 15 + 4) == 0);
    // the shaders end with s_endpgm and are padded to their arrays
    CHECK(bc5::dc439::kVs[12] == 0xBF810000u && bc5::dc439::kPs[2] == 0xBF810000u);

    // 3. The host's filter (Policy::builtin) passes every packet: CLEAR_STATE 1/2 become cmd 0, nothing is dropped.
    std::vector<std::uint32_t> out(ib.size() + 64);
    bc5::policy::FilterOptions opt;
    opt.mapped = [](std::uint64_t, std::uint64_t) { return true; };
    bc5::policy::FilterStats st;
    const std::size_t n = bc5::policy::filter(bc5::policy::Policy::builtin(), ib, out, opt, st);
    std::printf("filter: %zu of %zu dwords, packets %llu passed %llu rewritten %llu dropped %llu clear_state_rewrites %llu truncated %llu\n", n, ib.size(),
                (unsigned long long)st.packets, (unsigned long long)st.passed, (unsigned long long)st.rewritten, (unsigned long long)st.dropped,
                (unsigned long long)st.clear_state_rewrites, (unsigned long long)st.truncated);
    CHECK(st.dropped == 0 && st.truncated == 0);
    CHECK(st.clear_state_rewrites == 2);
    for (std::size_t i = 0; i < n && i < ib.size(); i++) {
        if (out[i] != ib[i] && !(i == pk.front()[1] + 1 || i == pk.back()[1] + 1)) {
            std::printf("  dword %zu changed: 0x%08x -> 0x%08x\n", i, ib[i], out[i]);
        }
    }

    // 4. The state stack over a title IB, then the decompress IB: after the pop the title's CB_COLOR_CONTROL,
    //    scissor and MRT0 are what the title set.
    bc5::state_stack::Tracker t;
    std::vector<std::uint32_t> title = {bc5::dc439::pkt3(0x69, 3), bc5::dc439::kCbColorControl, 0x00cc0010u, 0u,
                                        bc5::dc439::pkt3(0x69, 2), 0x082, 0x04380780u,
                                        bc5::dc439::pkt3(0x69, 2), bc5::dc439::kCbColor0Base, 0x77777700u};
    bc5::state_stack::Stats ss;
    std::vector<std::uint32_t> tio = title;
    t.apply_in_place(title, tio, opt.mapped, ss);
    std::vector<std::uint32_t> fio(out.begin(), out.begin() + static_cast<std::ptrdiff_t>(n));
    t.apply_in_place(ib, fio, opt.mapped, ss);
    std::printf("state stack: pushes %u pops %u restored %u inserted %u\n", ss.pushes, ss.pops, ss.restored_regs, ss.inserted_dwords);
    CHECK(ss.pushes == 1 && ss.pops == 1 && ss.restored_regs >= 3);
    const auto &cx = t.context();
    CHECK(cx.value[bc5::dc439::kCbColorControl] == 0x00cc0010u && cx.value[0x082] == 0x04380780u && cx.value[bc5::dc439::kCbColor0Base] == 0x77777700u);
    // the restore is in the IB that runs: after the decompress IB's last packet the title's values are written back
    std::map<std::uint32_t, std::uint32_t> rc, rsh, ruc;
    std::vector<std::uint32_t> tail(fio.begin() + static_cast<std::ptrdiff_t>(pk.back()[1]), fio.end());
    // skip NOPs the pop left in place
    std::vector<std::uint32_t> tail2;
    for (std::size_t i = 0; i < tail.size(); i++)
        if (tail[i] != bc5::policy::kNop) {
            tail2.assign(tail.begin() + static_cast<std::ptrdiff_t>(i), tail.end());
            break;
        }
    writes(tail2, rc, rsh, ruc);
    CHECK(rc[bc5::dc439::kCbColorControl] == 0x00cc0010u && rc[0x082] == 0x04380780u);
    // 5. walk_draws(): the surface bound to MRT0 for one draw, then MRT0 rebound to another target before the job ends
    //    (p1: no MRT on the surface at any job's end). The draw's block is caught; the job-end context has none.
    {
        using bc5::dc439::pkt3;
        std::vector<std::uint32_t> j;
        j.push_back(pkt3(0x69, 2));
        j.push_back(bc5::dc439::kCbTargetMask);
        j.push_back(0xfu);
        j.push_back(pkt3(0x69, 1 + 15));
        j.push_back(bc5::dc439::kCbColor0Base);
        for (std::uint32_t k = 0; k < 15; k++) j.push_back(k == 0 ? static_cast<std::uint32_t>(surf >> 8) : k == 13 ? static_cast<std::uint32_t>(meta >> 8) : k == 4 ? (1u << 28) : 0u);
        j.push_back(pkt3(0x2d, 2)); // the draw into the surface
        j.push_back(3);
        j.push_back(2);
        j.push_back(pkt3(0x69, 2)); // MRT0 rebound
        j.push_back(bc5::dc439::kCbColor0Base);
        j.push_back(0x66660000u);
        j.push_back(pkt3(0x2d, 2));
        j.push_back(3);
        j.push_back(2);
        bc5::dc439::Ctx cx;
        std::vector<std::uint64_t> addrs = {surf, surf + 0x2030000};
        std::vector<bc5::dc439::Hit> hits(2);
        bc5::dc439::walk_draws(j.data(), j.size(), cx, addrs, hits, [](std::uint64_t, std::uint64_t) { return false; });
        CHECK(hits[0].draws == 1 && hits[0].block.valid && hits[0].block.mrt == 0 && hits[0].block.dcc_base() == meta && hits[0].block.dcc_enable());
        CHECK(hits[1].draws == 0);
        CHECK(!bc5::dc439::find(cx.value, cx.valid, surf).valid); // the job-end context no longer has it
        CHECK(bc5::dc439::count_base(j.data(), j.size(), static_cast<std::uint32_t>(surf >> 8), [](std::uint64_t, std::uint64_t) { return false; }) == 1);
    }
    // 6. The AGC end-of-pipe ident and data, and the 3-bit INT_SEL (BC5_DIRECT_AGC_EOP_IDENT).
    CHECK(bc5::dc439::agc_eop_ident(false, 0x33) == 0u);       // the graphics CP: 0
    CHECK(bc5::dc439::agc_eop_ident(true, 0x33) == 0x52u);     // the third title's ProxySet Cull ident, slot 0x33
    CHECK(bc5::dc439::agc_eop_ident(true, 0x1) == 0x20u);      // the first compute queue
    CHECK(bc5::dc439::agc_eop_data(0x08100001u, 0x52u) == ((0x08100001ull << 16) | 0x52u));
    CHECK((bc5::dc439::agc_eop_data(0x1234u, 0x52u) >> 16) == 0x1234u); // GetEqContextId = data >> 16
    CHECK(bc5::dc439::release_mem_int_sel(4u << 24) == 4u);    // the third title's roll interrupts: 4, not 0
    CHECK(bc5::dc439::release_mem_int_sel(3u << 24) == 3u);
    CHECK(bc5::dc439::release_mem_int_sel((4u << 24) | (2u << 29)) == 4u); // DATA_SEL above it does not leak in
    CHECK(((4u << 24) >> 24 & 3u) == 0u);                      // the old 2-bit read loses it
    std::printf("%s (%d failures); IB %zu dwords\n", g_fail == 0 ? "PASS" : "FAIL", g_fail, ib.size());
    return g_fail == 0 ? 0 : 1;
}
