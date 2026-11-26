#!/usr/bin/env python3
"""BC5 exp 0439, bake 2 (tag b2439): the backend part, on top of bake 1 (exp 0442's backend, branch
exp/0442-title-defaults-audit e1383e89). Applied to the bake-1 files, bytes in, bytes out (LF), every edit exactly once.
    b2be439.py <bake-1 backend dir (backend/: src/direct.cpp, src/full_state.cpp, src/policy.cpp)> <ib-be.diff applied dir>
The second argument is the same three files after exp 0439's chain hunks (the branch's 4b456815..HEAD diff of
backend/src/{direct,full_state,policy}.cpp and include/bc5/ib_chain.hpp; two direct.cpp hunks placed by hand where
bake 1 removed host_indirect). This script checks that pair, then edits the result in place:
  ds439 (D, D2): the DMA-sync block of exp 0050 replaced by bc5/ds0439.hpp's points() with C off, the words renamed
       BC5_DIRECT_DMA_SYNC_MEC / BC5_DIRECT_DMA_SYNC_LABEL (on only when "1"; switch_defaults.hpp kSoft sets them), no
       log line (one archive serves normal and lean).
  The chain hunks' count lines (fl439 "laid out flat" / "NOT laid out flat", ib439 "submit #n with chains") removed
       (diagnosis; the backend archive is shared with lean). Kept: ib439's refusal and its NOP-ed-targets line (a
       failure must stay visible).
"""
import hashlib, os, sys

b1, t = sys.argv[1], sys.argv[2]
B1_PINS = {"src/direct.cpp": "35fca52f", "src/full_state.cpp": "29f7dd6d", "src/policy.cpp": "107bb1b6"}  # bake 1 at 24ed91cc
if os.environ.get("B2BE_DIRECT"):  # exp 0439 (11-22 night): bake 1c+1d's direct.cpp (9956715f); the anchors were checked on it
    B1_PINS["src/direct.cpp"] = os.environ["B2BE_DIRECT"]
if os.environ.get("B2BE_POLICY"):  # exp 0439 (11-23): bakeR's policy.cpp (99303017, the register catcher's include and check)
    B1_PINS["src/policy.cpp"] = os.environ["B2BE_POLICY"]


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()[:8]


for f, m in B1_PINS.items():
    assert md5(os.path.join(b1, f)) == m, (f, md5(os.path.join(b1, f)), m)
p = os.path.join(t, "src/direct.cpp")
s = open(p, "rb").read().decode("utf-8")
assert "\r" not in s


def rep(a, b):
    global s
    c = s.count(a)
    assert c == 1, (a[:80], c)
    s = s.replace(a, b)


# the two chain hunks that `patch -p1 < b2-ib-be.diff` cannot place on bake 1 (their context was host_indirect, which
# bake 1 removed): the include line, and the executed offsets per guest segment after executed_offsets_of
if '#include "bc5/ib_chain.hpp"' not in s:
    rep('#include "bc5/ib_split.hpp"\n', '#include "bc5/ib_chain.hpp" // exp 0439 (tag ib439)\n#include "bc5/ib_split.hpp"\n')
if 'the executed offsets per guest segment' not in s:
    rep('''    executed_offsets_of(ib, main_out.data(), r.executed_offsets);
''', '''    executed_offsets_of(ib, main_out.data(), r.executed_offsets);
    if (!flat_segs.empty()) { // exp 0439 (tag fl439): the executed offsets per guest segment (the first stays the IB's own)
        const std::vector<std::uint32_t> all = std::move(r.executed_offsets);
        r.executed_offsets.clear();
        for (std::size_t s = 0; s < flat_segs.size(); ++s) {
            std::vector<std::uint32_t> ex;
            for (const std::uint32_t o : all)
                if (o >= flat_segs[s].off && o < flat_segs[s].off + flat_segs[s].n) ex.push_back(static_cast<std::uint32_t>(o - flat_segs[s].off));
            if (s == 0) r.executed_offsets = std::move(ex);
            else r.nested.push_back({reinterpret_cast<std::uint64_t>(flat_segs[s].src), static_cast<std::uint32_t>(flat_segs[s].n), std::move(ex)});
        }
    }
''')
assert s.count("tag ib439") >= 4 and s.count("tag fl439") >= 2, "the chain hunks are not in " + p

rep('#include "bc5/ib_chain.hpp" // exp 0439 (tag ib439)\n',
    '#include "bc5/ib_chain.hpp" // exp 0439 (tag ib439)\n#include "bc5/ds0439.hpp" // exp 0439 (tag ds439)\n')
rep('''        if (fr == ib_chain::FlatResult::Flattened) {
            const std::uint64_t c = ++n_flat;
            if (c <= 16 || c % 1000 == 0)
                std::fprintf(stderr, "bc5-direct: exp 0439 (tag fl439): %s job of %zu dwords at %p laid out flat: %zu segments, %zu dwords (%llu such jobs)\\n",
                             comp ? "compute" : "GFX", ib.size(), static_cast<const void *>(ib.data()), flat_segs.size(), flat_local.size(), static_cast<unsigned long long>(c));
            ib = std::span<const std::uint32_t>(flat_local.data(), flat_local.size());
        } else if (fr == ib_chain::FlatResult::Refused) {
            const std::uint64_t c = ++n_flat_refused;
            if (c <= 16 || c % 1000 == 0)
                std::fprintf(stderr, "bc5-direct: exp 0439 (tag fl439): %s job of %zu dwords at %p NOT laid out flat (%s): today's layout (%llu such jobs)\\n",
                             comp ? "compute" : "GFX", ib.size(), static_cast<const void *>(ib.data()), why != nullptr ? why : "?", static_cast<unsigned long long>(c));
        }''', '''        if (fr == ib_chain::FlatResult::Flattened) {
            ++n_flat;
            ib = std::span<const std::uint32_t>(flat_local.data(), flat_local.size());
        } else if (fr == ib_chain::FlatResult::Refused) {
            ++n_flat_refused; // a refused chain keeps today's layout
        }''')
rep('''        if (cr.chains != 0) {
            const std::uint64_t c = ++n_chained;
            if (c <= 8 || c % 1000 == 0)
                std::fprintf(stderr, "bc5-direct: exp 0439 (tag ib439): submit #%llu with chains: %zu pieces, %zu chained, longest chain %zu, %zu call targets over depth, %zu over the cap\\n",
                             static_cast<unsigned long long>(c), cr.pieces.size(), cr.chains, cr.longest_chain, cr.over_depth, cr.over_cap);
        }''', '''        if (cr.chains != 0) ++n_chained;''')
rep('''    if (opt.dma_sync_before_dispatch && !comp) { // the MEC waits for its DMA itself
        std::vector<indirect_check::Insert> waits;
        bool pending = false;
        for (std::size_t i = 0; i < main_out.size();) {
            const std::uint32_t h = main_out[i];
            const std::uint32_t type = h >> 30;
            std::size_t len = 1;
            if (type == 3 || type == 0) {
                const std::uint32_t count = (h >> 16) & 0x3fff;
                len = count == 0x3fff ? 1 : count + 2;
            }
            if (i + len > main_out.size()) len = main_out.size() - i;
            const std::uint32_t op = (h >> 8) & 0xff;
            if (type == 3 && op == 0x50 && len >= 2) pending = (main_out[i + 1] & 0x80000000u) == 0;
            if (type == 3 && (op == 0x15 || op == 0x16) && pending) {
                waits.push_back({i, {0xC0055000u, 0xE0300000u, 0u, 0u, 0u, 0u, 0u}});
                pending = false;
            }
            i += len;
        }
        if (indirect_check::insert_before(main_out, waits)) r.filter.dma_syncs += waits.size();
    }''', '''    // exp 0439 (tag ds439, bake 2): BC5_DIRECT_DMA_SYNC_MEC=1 (D) puts the same wait before the first dispatch after an
    // unsynced DMA_DATA on the compute rings too (the claim that the MEC waits for its DMA itself has no source; the
    // third title copies GDS counters to indirect arguments with DMA_DATA a few packets before the dispatch that reads
    // them); BC5_DIRECT_DMA_SYNC_LABEL=1 (D2) also before the first label write after one and at the end of a buffer
    // ending with one pending. Both set for every title by switch_defaults.hpp kSoft; "0" turns each off. The GFX ring
    // keeps experiment 0050's wait (opt.dma_sync_before_dispatch). bc5/ds0439.hpp, det-tested (k439/test_ds0439.cpp).
    static const bool d439 = [] {
        const char *e = std::getenv("BC5_DIRECT_DMA_SYNC_MEC");
        return e != nullptr && e[0] == '1' && e[1] == 0;
    }();
    static const bool l439 = [] {
        const char *e = std::getenv("BC5_DIRECT_DMA_SYNC_LABEL");
        return e != nullptr && e[0] == '1' && e[1] == 0;
    }();
    {
        std::vector<indirect_check::Insert> waits;
        for (auto &p : ds439::points(main_out, comp, opt.dma_sync_before_dispatch, d439, false, l439))
            waits.push_back({p.first, std::move(p.second)});
        if (!waits.empty() && indirect_check::insert_before(main_out, waits)) r.filter.dma_syncs += waits.size();
    }''')
open(p, "wb").write(s.encode("utf-8"))
# exp 0439 (11-23): on bakeR's policy.cpp the diff's include hunk fails (reg_catch.hpp's include follows policy_tsv.hpp's
# line, its context); the include is placed here, the other three policy hunks apply as they are
pp = os.path.join(t, "src/policy.cpp")
ps = open(pp, "rb").read().decode("utf-8")
assert "\r" not in ps and ps.count("ib_chain::") >= 3, "policy.cpp lacks the chain hunks"
if '#include "bc5/ib_chain.hpp"' not in ps:
    a = '#include "bc5/policy.hpp"\n'
    assert ps.count(a) == 1
    ps = ps.replace(a, a + '#include "bc5/ib_chain.hpp" // exp 0439 (tag ib439)\n')
    open(pp, "wb").write(ps.encode("utf-8"))
print("b2be439: direct.cpp", md5(p), "full_state.cpp", md5(os.path.join(t, "src/full_state.cpp")), "policy.cpp", md5(os.path.join(t, "src/policy.cpp")))
