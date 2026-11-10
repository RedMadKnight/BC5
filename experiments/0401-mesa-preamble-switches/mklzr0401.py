#!/usr/bin/env python3
"""BC5 experiment 0401 series e7, tag lzr: BC5_DIRECT_LAZY_RELEASE=<seconds>[,dry][,eager] in src/libs/bc5LleAgc.cpp, off
unless set (F767's reading; anything that does not parse leaves it off and the journal says why).

The direct path pins the direct memfd in 2 MiB chunks and never gives one back (exp 0379 README, "What the code allows").
With the switch on, a chunk that has been under no view (no GPU mapping, so no submission reaches it) for the idle time,
that is not forced (hint and learned windows) and that was last seen under a view that was neither eager nor a heap of
the zero skip's list ("eager" lets eager-heap chunks go too; zero-list chunks never) is cut out of its BO: the BO's
other chunks become new imports and the old BO is retired as the merge retires one (the drain, the rebuild, free_shared),
and the cut stands only when every ring is idle after that drain. A released chunk that a view covers again is imported
in that sync, before the mappings are built. Nothing punches the memfd. Design, evidence and safety: lzr0401-notes.md.

The pure part goes into the unit and, byte for byte, into <out>/src/libs/lzr0401.inc beside it, for the CPU test
lzr0401.cpp. Functions touched: direct_sync_one (two inserted lines: lzr_pass before the mapping rebuild, lzr_confirm
after its drain); everything else is new, in one block between direct_breakdown and g_scratch. The anchors stay off the
lines exp 0379's patch0379-bc5LleAgc.diff changes, so the edit also applies after that patch (series e7: zsk, then lzr).
Input: one of INPUTS by md5, LF line endings. Every anchor must occur exactly once; an input that has the edit already is
refused; so is any other md5. After editing, the script checks that undoing every replacement (new -> old, last first)
gives the input back. Prints "<relpath> <md5>" for the unit and the .inc.
usage: mklzr0401.py <tree root in> <out dir>"""
import hashlib
import os
import sys

REL = "src/libs/bc5LleAgc.cpp"
INC = "src/libs/lzr0401.inc"
# The one list of accepted inputs, md5 -> what it is. The top session adds zsk's output (d1cfd9bb + exp 0379's zero skip).
INPUTS = {
    "8710207ea5c34ad70e48dfbbff9880fd": "zsk's output (mkzsk0401.py: exp 0379's zero skip on the e6 chain's final unit d1cfd9bb), the e7 chain's input here",
}
MARK = b"BC5_DIRECT_LAZY_RELEASE"


def tabs(text):
    """The C++ below is written with 4-space indents; the unit indents with tabs."""
    out = []
    for line in text.split("\n"):
        body = line.lstrip(" ")
        k = len(line) - len(body)
        out.append("\t" * (k // 4) + " " * (k % 4) + body)
    return "\n".join(out).encode("ascii")


# ---------------------------------------------------------------------------------------------------------------------
# The pure part: in the unit and in lzr0401.inc.
LZR_PURE = tabs(r"""// ---- experiment 0401 series e7, lzr: BC5_DIRECT_LAZY_RELEASE, the pure part --------------------------------------------
// mklzr0401.py writes this block into the unit and, byte for byte, into lzr0401.inc for the CPU test lzr0401.cpp. It needs
// <algorithm>, <cstddef>, <cstdint>, <set>, <string>, <utility> and <vector>. No GPU access, no global state.
//
// The direct path pins the direct memfd in 2 MiB chunks and never gives one back (direct_sync_one, ADR 0006; exp 0379
// README, "What the code allows"). A chunk under no view has no GPU mapping: each rebuild drops every mapping no view
// asks for. No submission can reach it, and a draw's BO list names its BO only for the BO's other chunks
// (backend/src/direct.cpp: the full list holds every imported BO that is mapped somewhere). plan() finds the imported
// chunks that have been under no view for the idle time and are not forced (S.forced: the hint and learned windows,
// the host's only record that the GPU needs memory no CPU wrote), and cuts them out of their BOs: the BO's other chunks
// become imports of their own and the old BO is retired, as the merge retires one. A chunk last seen under an eager
// view, or never seen under a view, is cut only with the "eager" word; a chunk of a zero-list heap (BC5_DIRECT_ZERO_SKIP,
// exp 0379) never. reviewed() names the released chunks a view covers again; the caller imports them before the mappings
// are built, so every mapping a rebuild makes has the chunks it would have without the switch. Nothing here punches the
// memfd: a released chunk keeps its pages and data, unpinned.
namespace Lzr0401 {

constexpr uint64_t kChunk  = 2ull << 20u;
constexpr uint64_t kSecond = 1'000'000'000ull;

struct Opts {
    bool        on      = false;
    bool        dry     = false; // count and journal; cut nothing
    bool        eager   = false; // also chunks last seen under an eager view, or never seen under a view
    uint64_t    idle_ns = 0;
    std::string why;             // the reading, for the journal
};

// BC5_DIRECT_LAZY_RELEASE=<seconds>[,dry][,eager]. Unset, empty and "0" are off (F767). The seconds are 1 to 86400 in
// decimal digits; any other text leaves the switch off, and why says so (lesson R41).
inline Opts parse(const char* e) {
    Opts o;
    if (e == nullptr || e[0] == 0 || (e[0] == '0' && e[1] == 0)) {
        o.why = e == nullptr ? "unset" : e[0] == 0 ? "empty" : "0";
        return o;
    }
    const std::string        s(e);
    std::vector<std::string> parts(1);
    for (const char c: s) {
        if (c == ',') {
            parts.emplace_back();
        } else {
            parts.back().push_back(c);
        }
    }
    uint64_t secs   = 0;
    bool     digits = !parts[0].empty() && parts[0].size() <= 5;
    for (const char c: parts[0]) {
        digits = digits && c >= '0' && c <= '9';
        if (digits) secs = secs * 10 + static_cast<uint64_t>(c - '0');
    }
    if (!digits || secs == 0 || secs > 86400) {
        o.why = "\"" + s + "\" does not parse: the idle time is 1 to 86400 seconds";
        return o;
    }
    bool dry_word = false, eager_word = false;
    for (size_t k = 1; k < parts.size(); k++) {
        if (parts[k] == "dry") {
            dry_word = true;
        } else if (parts[k] == "eager") {
            eager_word = true;
        } else {
            o.why = "\"" + s + "\" does not parse: the word \"" + parts[k] + "\" is not dry or eager";
            return o;
        }
    }
    o.on      = true;
    o.dry     = dry_word;
    o.eager   = eager_word;
    o.idle_ns = secs * kSecond;
    o.why     = std::to_string(secs) + " s" + (dry_word ? ", dry" : "") + (eager_word ? ", eager" : "");
    return o;
}

// Cuts are made only when on and not dry.
inline bool apply_allowed(const Opts& o) { return o.on && !o.dry; }

// The pass period: a quarter of the idle time, 1 to 15 seconds.
inline uint64_t period(const Opts& o) {
    const uint64_t q = o.idle_ns / 4;
    return q < kSecond ? kSecond : q > 15 * kSecond ? 15 * kSecond : q;
}

struct Range {
    uint64_t lo, hi; // [lo, hi), memfd offsets
};

// Sorted, with overlapping or touching ranges joined and empty ones dropped.
inline std::vector<Range> merged(std::vector<Range> v) {
    v.erase(std::remove_if(v.begin(), v.end(), [](const Range& r) { return r.lo >= r.hi; }), v.end());
    std::sort(v.begin(), v.end(), [](const Range& a, const Range& b) { return a.lo < b.lo; });
    std::vector<Range> out;
    for (const auto& r: v) {
        if (!out.empty() && r.lo <= out.back().hi) {
            out.back().hi = std::max(out.back().hi, r.hi);
        } else {
            out.push_back(r);
        }
    }
    return out;
}

// Whether [lo, hi) meets one of c's ranges (c from merged()).
inline bool hits(const std::vector<Range>& c, uint64_t lo, uint64_t hi) {
    const auto it = std::partition_point(c.begin(), c.end(), [lo](const Range& r) { return r.hi <= lo; });
    return it != c.end() && it->lo < hi;
}

// The views' memfd ranges by class, as direct_sync_one's import loop ranks them: eager first, then lazy, then data
// (neither); zero: a heap of the zero skip's list. V has off, size, eager and lazy (DView); zero(v) says whether v is a
// zero-list heap.
struct Covers {
    std::vector<Range> all, eager, data, lazy, zero;
};
template <class V, class Z> Covers covers(const std::vector<V>& views, Z zero) {
    Covers c;
    for (const auto& v: views) {
        if (v.size == 0) continue;
        const Range r {v.off, v.off + v.size};
        c.all.push_back(r);
        if (v.eager) {
            c.eager.push_back(r);
        } else if (v.lazy) {
            c.lazy.push_back(r);
        } else {
            c.data.push_back(r);
        }
        if (zero(v)) c.zero.push_back(r);
    }
    c.all   = merged(std::move(c.all));
    c.eager = merged(std::move(c.eager));
    c.data  = merged(std::move(c.data));
    c.lazy  = merged(std::move(c.lazy));
    c.zero  = merged(std::move(c.zero));
    return c;
}

// What the passes remember of each imported chunk.
struct Chunk {
    uint64_t off   = 0;
    uint64_t since = 0;     // when a pass first found it under no view and not forced (0: not so at the last pass)
    bool     seen  = false; // a pass found it under a view
    bool     eager = false; // ... and an eager view was among them, at the last such pass
    bool     zero  = false; // ... or a zero-list heap
};
struct State {
    std::vector<Chunk> chunks;   // the imported chunks at the last pass, by offset
    std::set<uint64_t> released; // chunks cut out and not imported again since
    uint64_t           last_pass = 0, last_report = 0, passes = 0;
    uint64_t           cuts = 0, wholes = 0, splits = 0, cut_bytes = 0, back_bytes = 0, undone = 0, import_failed = 0, deferred = 0;
};
struct BoIn {
    uint64_t off, size; // a BO of S.bos
    uint32_t id;
    uint32_t maps;      // the GPU mappings on it (S.maps)
};
struct Cut {
    uint64_t              off = 0, size = 0; // the BO
    uint32_t              id = 0, maps = 0;
    std::vector<Range>    keep;    // its chunks that stay, as runs: each becomes an import of its own
    std::vector<uint64_t> dropped; // the chunks cut out
    uint64_t              drop = 0; // their bytes
};
struct Plan {
    std::vector<Cut> cuts;
    uint64_t         imported = 0, eager_v = 0, data_v = 0, lazy_v = 0; // bytes: imported; under eager, data, lazy views
    uint64_t         forced_u = 0, unviewed = 0;     // under no view: forced; not forced
    uint64_t         seen_eager = 0, never_seen = 0; // of unviewed: last seen under an eager or zero-list view; never seen
    uint64_t         ready = 0, drop = 0;            // of unviewed: idle for the idle time; cut in this plan
    uint32_t         deferred = 0, nosplit = 0;      // BOs left for a later pass: budget or cut count; splits off
};

// A pass is due when on, at the first call, then once per period.
inline bool due(const Opts& o, const State& st, uint64_t now) { return o.on && (st.passes == 0 || now - st.last_pass >= period(o)); }

// One pass. bos: S.bos in order (disjoint; a BO not chunk-aligned is never cut); forced: S.forced; now: the sync's
// SoftCp::now_ns(); map_budget: the GPU mappings the cuts may move (the merge's budget, what the merge left of it);
// max_cuts: BOs cut per pass; splits: false when a BO may only go whole (BC5_DIRECT_ALIASES: the aliases of a BO's
// mappings come back only at the next aliases_apply); zero_skip: BC5_DIRECT_ZERO_SKIP is set. Updates st.chunks and
// counts; cuts nothing itself.
inline Plan plan(const Opts& o, State& st, const std::vector<BoIn>& bos, const Covers& cv, const std::set<uint64_t>& forced, uint64_t now, uint32_t map_budget,
                 size_t max_cuts, bool splits, bool zero_skip) {
    Plan p;
    if (!o.on) return p;
    st.last_pass = now;
    st.passes++;
    std::vector<Chunk> next;
    next.reserve(st.chunks.size());
    size_t k = 0;
    for (const auto& b: bos) {
        if (b.size == 0 || b.off % kChunk != 0 || b.size % kChunk != 0) {
            p.imported += b.size;
            continue;
        }
        std::vector<uint64_t> drop;
        for (uint64_t c = b.off; c < b.off + b.size; c += kChunk) {
            while (k < st.chunks.size() && st.chunks[k].off < c) k++;
            Chunk ch;
            ch.off = c;
            if (k < st.chunks.size() && st.chunks[k].off == c) ch = st.chunks[k];
            p.imported += kChunk;
            if (hits(cv.all, c, c + kChunk)) {
                ch.since = 0;
                ch.seen  = true;
                ch.eager = hits(cv.eager, c, c + kChunk);
                ch.zero  = hits(cv.zero, c, c + kChunk);
                if (ch.eager) {
                    p.eager_v += kChunk;
                } else if (hits(cv.data, c, c + kChunk)) {
                    p.data_v += kChunk;
                } else {
                    p.lazy_v += kChunk;
                }
            } else if (forced.count(c) != 0) {
                ch.since = 0;
                p.forced_u += kChunk;
            } else {
                p.unviewed += kChunk;
                if (ch.since == 0 || ch.since > now) ch.since = now;
                const bool ready   = now - ch.since >= o.idle_ns;
                const bool allowed = ch.seen ? !ch.zero && (o.eager || !ch.eager) : o.eager && !zero_skip;
                if (!ch.seen) {
                    p.never_seen += kChunk;
                } else if (ch.eager || ch.zero) {
                    p.seen_eager += kChunk;
                }
                if (ready) p.ready += kChunk;
                if (ready && allowed) drop.push_back(c);
            }
            next.push_back(ch);
        }
        if (drop.empty()) continue;
        const bool whole = static_cast<uint64_t>(drop.size()) * kChunk == b.size;
        if (!whole && !splits) {
            p.nosplit++;
            continue;
        }
        if (p.cuts.size() >= max_cuts || b.maps > map_budget) {
            p.deferred++;
            continue;
        }
        map_budget -= b.maps;
        Cut cut;
        cut.off  = b.off;
        cut.size = b.size;
        cut.id   = b.id;
        cut.maps = b.maps;
        uint64_t run  = 0;
        bool     open = false;
        size_t   di   = 0;
        for (uint64_t c = b.off; c < b.off + b.size; c += kChunk) {
            if (di < drop.size() && drop[di] == c) {
                di++;
                if (open) cut.keep.push_back({run, c});
                open = false;
            } else if (!open) {
                run  = c;
                open = true;
            }
        }
        if (open) cut.keep.push_back({run, b.off + b.size});
        cut.drop    = static_cast<uint64_t>(drop.size()) * kChunk;
        cut.dropped = std::move(drop);
        p.drop += cut.drop;
        p.cuts.push_back(std::move(cut));
    }
    st.chunks.swap(next);
    st.deferred += p.deferred;
    return p;
}

// The released chunks a view covers again (V has off and size), sorted.
template <class V> std::vector<uint64_t> reviewed(const std::set<uint64_t>& released, const std::vector<V>& views) {
    std::vector<uint64_t> out;
    if (released.empty()) return out;
    for (const auto& v: views) {
        if (v.size == 0) continue;
        for (auto it = released.lower_bound(v.off - v.off % kChunk); it != released.end() && *it < v.off + v.size; ++it) out.push_back(*it);
    }
    std::sort(out.begin(), out.end());
    out.erase(std::unique(out.begin(), out.end()), out.end());
    return out;
}

// Chunks (sorted, unique) as runs of neighbours of at most max_bytes each (kDMaxBo), as direct_sync_one groups imports.
inline std::vector<Range> runs(const std::vector<uint64_t>& chunks, uint64_t max_bytes) {
    std::vector<Range> out;
    for (const uint64_t c: chunks) {
        if (!out.empty() && out.back().hi == c && c + kChunk - out.back().lo <= max_bytes) {
            out.back().hi = c + kChunk;
        } else {
            out.push_back({c, c + kChunk});
        }
    }
    return out;
}

// On a sorted BO list whose B is {off, size, id, t_ns} (DBo): the end of the BO that holds off, 0 when none does
// (direct_covered_end's rule); a BO put in its place; a cut applied (the BO replaced by its kept runs with the new ids,
// false and nothing changed when the list does not hold that BO); a cut undone (the kept runs out, the BO back).
template <class B> uint64_t covered_end(const std::vector<B>& bos, uint64_t off) {
    auto it = std::upper_bound(bos.begin(), bos.end(), off, [](uint64_t o, const B& b) { return o < b.off; });
    if (it == bos.begin()) return 0;
    --it;
    return off < it->off + it->size ? it->off + it->size : 0;
}
template <class B> void insert_bo(std::vector<B>& bos, uint64_t off, uint64_t size, uint32_t id, uint64_t t_ns) {
    bos.insert(std::upper_bound(bos.begin(), bos.end(), off, [](uint64_t o, const B& b) { return o < b.off; }), B {off, size, id, t_ns});
}
template <class B> bool apply_cut(std::vector<B>& bos, const Cut& cut, const std::vector<uint32_t>& ids, uint64_t now, uint64_t* old_t) {
    if (ids.size() != cut.keep.size()) return false;
    const auto it = std::lower_bound(bos.begin(), bos.end(), cut.off, [](const B& b, uint64_t o) { return b.off < o; });
    if (it == bos.end() || it->off != cut.off || it->size != cut.size || it->id != cut.id) return false;
    if (old_t != nullptr) *old_t = it->t_ns;
    bos.erase(it);
    for (size_t i = 0; i < ids.size(); i++) insert_bo(bos, cut.keep[i].lo, cut.keep[i].hi - cut.keep[i].lo, ids[i], now);
    return true;
}
template <class B> bool undo_cut(std::vector<B>& bos, const Cut& cut, const std::vector<uint32_t>& ids, uint64_t old_t) {
    if (ids.size() != cut.keep.size()) return false;
    auto at = [&bos](uint64_t off) { return std::lower_bound(bos.begin(), bos.end(), off, [](const B& b, uint64_t o) { return b.off < o; }); };
    for (size_t i = 0; i < ids.size(); i++) {
        const auto it = at(cut.keep[i].lo);
        if (it == bos.end() || it->off != cut.keep[i].lo || it->size != cut.keep[i].hi - cut.keep[i].lo || it->id != ids[i]) return false;
    }
    for (const uint64_t c: cut.dropped) {
        if (covered_end(bos, c) != 0) return false; // something holds a cut chunk now: the BO cannot come back whole
    }
    for (size_t i = 0; i < ids.size(); i++) bos.erase(at(cut.keep[i].lo));
    insert_bo(bos, cut.off, cut.size, cut.id, old_t);
    return true;
}

// The record of cuts made, undone and taken back. A cut chunk leaves st.chunks: imported again, it starts as never seen.
inline void note_cut(State& st, const Cut& cut) {
    st.cuts++;
    (cut.keep.empty() ? st.wholes : st.splits)++;
    st.cut_bytes += cut.drop;
    for (const uint64_t c: cut.dropped) st.released.insert(c);
    st.chunks.erase(std::remove_if(st.chunks.begin(), st.chunks.end(), [&cut](const Chunk& k) { return std::binary_search(cut.dropped.begin(), cut.dropped.end(), k.off); }),
                    st.chunks.end());
}
inline void note_undo(State& st, const Cut& cut) {
    st.undone++;
    st.cuts--;
    (cut.keep.empty() ? st.wholes : st.splits)--;
    st.cut_bytes -= cut.drop;
    for (const uint64_t c: cut.dropped) st.released.erase(c);
}
inline void note_back(State& st, uint64_t c) {
    if (st.released.erase(c) != 0) st.back_bytes += kChunk;
}

} // namespace Lzr0401
""")

# ---------------------------------------------------------------------------------------------------------------------
# The host's side: the unit only.
LZR_GLUE = tabs(r"""// ---- experiment 0401 series e7, lzr: BC5_DIRECT_LAZY_RELEASE, the host's side -----------------------------------------
// lzr_pass runs in direct_sync_one between the merge and the mapping rebuild, for the direct memfd only:
//   1. released chunks a view covers again are imported (in that sync, before the rebuild maps the view); one the eager
//      or data path took already only leaves the released set;
//   2. once per pass period, not in a sync whose merge did something, plan() picks the chunks to cut. Each cut BO's kept
//      runs are imported first (a failed import leaves the BO whole), then the BO is replaced in S.bos and its id goes to
//      `retired`: the rebuild's drain (wait_jobs) runs, the mappings move to the new BOs, and the old BO is freed after
//      the rebuild, as the merge's are.
// lzr_confirm runs right after that drain: a cut stands only when every ring is idle (Device::wait_idle(0)); otherwise
// each cut is undone (its new BOs were never mapped, so they are freed at once) and the chunks wait for a later pass.
// Off (the default): one journal line at the first sync, then a return.
struct LzrDone {
    Lzr0401::Cut          cut;
    std::vector<uint32_t> ids;
    uint64_t              old_t = 0;
};
struct LzrPass {
    std::vector<LzrDone> done;
};
static Lzr0401::State g_lzr;
static uint64_t       g_lzr_rv_sig = 0; // the views' signature at the last look for released chunks under a view
static const Lzr0401::Opts& lzr_opts() {
    static const Lzr0401::Opts o = Lzr0401::parse(std::getenv("BC5_DIRECT_LAZY_RELEASE"));
    return o;
}
// Exp 0379's zero skip, read by its switch and heap names (BC5_DIRECT_ZERO_SKIP set; BC5_DIRECT_ZERO_NAMES, default
// RenderGpuWcLarge,CommitIABufferAllocator), so this block needs none of the skip's code.
static bool lzr_zero_skip() {
    static const bool on = std::getenv("BC5_DIRECT_ZERO_SKIP") != nullptr;
    return on;
}
static bool lzr_zero_name(const std::string& name) {
    static const std::vector<std::string> names = [] {
        std::vector<std::string> v;
        if (!lzr_zero_skip()) return v;
        const char* e = std::getenv("BC5_DIRECT_ZERO_NAMES");
        std::string s = e != nullptr ? e : "RenderGpuWcLarge,CommitIABufferAllocator", cur;
        for (const char c: s + ",") {
            if (c == ',') {
                if (!cur.empty()) v.push_back(cur);
                cur.clear();
            } else {
                cur.push_back(c);
            }
        }
        return v;
    }();
    return !names.empty() && std::find(names.begin(), names.end(), name) != names.end();
}
static LzrPass lzr_pass(DState& S, const std::vector<DView>& views, uint64_t sig, int fd, uint64_t now, uint32_t merged, std::vector<uint32_t>& retired, uint32_t merge_remaps,
                        uint32_t map_cap) {
    LzrPass                    out;
    const Lzr0401::Opts&       o   = lzr_opts();
    static constexpr double    mib = 1048576.0;
    static bool                said = false;
    if (!said) {
        said = true;
        if (o.on) {
            journal("lazy release (exp 0401 e7): on (%s): an imported chunk of the direct memfd under no view for %" PRIu64 " s, not forced by a hint or learned window, %s, is cut out of its "
                    "BO%s; a view over it again imports it before the mappings are built; passes every %.1f s\n",
                    o.why.c_str(), o.idle_ns / Lzr0401::kSecond, o.eager ? "eager-heap chunks too, zero-list chunks never" : "never one of an eager or zero-list heap",
                    o.dry ? " (dry: counted only, nothing cut)" : "", static_cast<double>(Lzr0401::period(o)) / 1e9);
        } else {
            journal("lazy release (exp 0401 e7): off (BC5_DIRECT_LAZY_RELEASE %s)\n", o.why.c_str());
        }
    }
    if (!o.on || S.kind != 0 || !g_dev || fd < 0) return out;
    const bool apply = Lzr0401::apply_allowed(o);
    // 1. Released chunks under a view again.
    if (apply && !g_lzr.released.empty() && sig != g_lzr_rv_sig) {
        bool                  retry = false;
        uint64_t              got = 0, had = 0;
        std::vector<uint64_t> need;
        for (const uint64_t c: Lzr0401::reviewed(g_lzr.released, views)) {
            if (Lzr0401::covered_end(S.bos, c) != 0) {
                Lzr0401::note_back(g_lzr, c); // the eager or data path imported it in this sync
                had += Lzr0401::kChunk;
            } else {
                need.push_back(c);
            }
        }
        for (const auto& r: Lzr0401::runs(need, kDMaxBo)) {
            const uint32_t id = r.hi <= S.file_size ? g_dev->import_memfd(fd, r.lo, r.hi - r.lo) : 0;
            if (id == 0) {
                retry = true;
                if (g_lzr.import_failed++ < 16) journal("lazy release (exp 0401 e7): import 0x%" PRIx64 " +0x%" PRIx64 " of released chunks under a view again FAILED (tried again at the next sync)\n", r.lo, r.hi - r.lo);
                continue;
            }
            Lzr0401::insert_bo(S.bos, r.lo, r.hi - r.lo, id, now);
            S.bytes += r.hi - r.lo;
            got += r.hi - r.lo;
            for (uint64_t c = r.lo; c < r.hi; c += Lzr0401::kChunk) Lzr0401::note_back(g_lzr, c);
        }
        static uint64_t n_back = 0;
        if ((got != 0 || had != 0) && (n_back++ < 16 || (n_back & 63u) == 0)) {
            journal("lazy release (exp 0401 e7): released chunks under a view again: %.1f MiB imported now, %.1f MiB imported by the eager or data path; %zu chunks still released\n",
                    static_cast<double>(got) / mib, static_cast<double>(had) / mib, g_lzr.released.size());
        }
        g_lzr_rv_sig = retry ? 0 : sig;
    }
    // 2. The pass.
    if (!Lzr0401::due(o, g_lzr, now) || merged != 0) return out;
    static Lzr0401::Covers cov;
    static uint64_t        cov_sig = 0;
    static bool            cov_ok  = false;
    if (!cov_ok || cov_sig != sig) {
        cov     = Lzr0401::covers(views, [](const DView& v) { return lzr_zero_name(v.name); });
        cov_sig = sig;
        cov_ok  = true;
    }
    std::unordered_map<uint32_t, uint32_t> maps_on;
    for (const auto& m: S.maps) maps_on[m.id]++;
    std::vector<Lzr0401::BoIn> bos;
    bos.reserve(S.bos.size());
    for (const auto& b: S.bos) {
        const auto it = maps_on.find(b.id);
        bos.push_back({b.off, b.size, b.id, it != maps_on.end() ? it->second : 0u});
    }
    const bool          splits = std::getenv("BC5_DIRECT_ALIASES") == nullptr;
    const Lzr0401::Plan p      = Lzr0401::plan(o, g_lzr, bos, cov, S.forced, now, map_cap > merge_remaps ? map_cap - merge_remaps : 0u, 32, splits, lzr_zero_skip());
    if (g_lzr.last_report == 0 || now - g_lzr.last_report >= 60 * Lzr0401::kSecond) {
        g_lzr.last_report = now;
        journal("lazy release (exp 0401 e7): t %.0f s: %.1f MiB imported: %.1f under eager views, %.1f under data views, %.1f under lazy views, %.1f forced and under no view, %.1f under no view "
                "(%.1f last seen under an eager or zero-list view, %.1f never seen under one; %.1f idle %" PRIu64 " s or more)%s; cut %.1f MiB in %" PRIu64 " BOs (%" PRIu64 " whole, %" PRIu64
                " split), back %.1f MiB, %zu chunks released now, %" PRIu64 " undone, %" PRIu64 " imports failed, %" PRIu64 " BOs deferred, %u not split (aliases); GTT %.1f of %.1f MiB\n",
                timing_now(), static_cast<double>(p.imported) / mib, static_cast<double>(p.eager_v) / mib, static_cast<double>(p.data_v) / mib, static_cast<double>(p.lazy_v) / mib,
                static_cast<double>(p.forced_u) / mib, static_cast<double>(p.unviewed) / mib, static_cast<double>(p.seen_eager) / mib, static_cast<double>(p.never_seen) / mib,
                static_cast<double>(p.ready) / mib, o.idle_ns / Lzr0401::kSecond, o.dry ? "; dry, nothing cut" : "", static_cast<double>(g_lzr.cut_bytes) / mib, g_lzr.cuts, g_lzr.wholes,
                g_lzr.splits, static_cast<double>(g_lzr.back_bytes) / mib, g_lzr.released.size(), g_lzr.undone, g_lzr.import_failed, g_lzr.deferred, p.nosplit,
                static_cast<double>(direct_gtt("mem_info_gtt_used")) / mib, static_cast<double>(direct_gtt("mem_info_gtt_total")) / mib);
    }
    if (!apply || p.cuts.empty()) return out;
    uint64_t cut_bytes = 0;
    uint32_t moved     = 0;
    for (const auto& cut: p.cuts) {
        std::vector<uint32_t> ids;
        bool                  ok = true;
        for (const auto& r: cut.keep) {
            const uint32_t id = g_dev->import_memfd(fd, r.lo, r.hi - r.lo);
            if (id == 0) {
                ok = false;
                break;
            }
            ids.push_back(id);
        }
        uint64_t old_t = 0;
        if (!ok || !Lzr0401::apply_cut(S.bos, cut, ids, now, &old_t)) {
            for (const uint32_t id: ids) g_dev->free_shared(id); // never mapped
            if (!ok && g_lzr.import_failed++ < 16) journal("lazy release (exp 0401 e7): an import of the kept part of BO 0x%" PRIx64 " +0x%" PRIx64 " FAILED: the BO stays whole\n", cut.off, cut.size);
            continue;
        }
        retired.push_back(cut.id);
        moved += cut.maps;
        S.bytes -= cut.drop;
        cut_bytes += cut.drop;
        Lzr0401::note_cut(g_lzr, cut);
        out.done.push_back({cut, std::move(ids), old_t});
    }
    static uint64_t n_cut = 0;
    if (!out.done.empty() && (n_cut++ < 16 || (n_cut & 63u) == 0)) {
        journal("lazy release (exp 0401 e7): cut %.1f MiB out of %zu BOs (%u mappings to move); %.1f MiB cut in all, %zu chunks released now\n", static_cast<double>(cut_bytes) / mib, out.done.size(),
                moved, static_cast<double>(g_lzr.cut_bytes) / mib, g_lzr.released.size());
    }
    return out;
}
static void lzr_confirm(DState& S, LzrPass& pass, std::vector<uint32_t>& retired) {
    if (pass.done.empty() || !g_dev) return;
    if (g_dev->wait_idle(0)) return;
    uint64_t back = 0;
    size_t   n    = 0;
    for (auto it = pass.done.rbegin(); it != pass.done.rend(); ++it) {
        if (!Lzr0401::undo_cut(S.bos, it->cut, it->ids, it->old_t)) {
            journal("lazy release (exp 0401 e7): BO 0x%" PRIx64 " +0x%" PRIx64 " could not be put back: the cut stands on a GPU that was not idle\n", it->cut.off, it->cut.size);
            continue;
        }
        for (const uint32_t id: it->ids) g_dev->free_shared(id); // never mapped
        retired.erase(std::remove(retired.begin(), retired.end(), it->cut.id), retired.end());
        S.bytes += it->cut.drop;
        back += it->cut.drop;
        n++;
        Lzr0401::note_undo(g_lzr, it->cut);
    }
    journal("lazy release (exp 0401 e7): a ring was still busy after the drain: %zu cuts undone (%.1f MiB), tried again at a later pass\n", n, static_cast<double>(back) / 1048576.0);
}

""")

BLOCK_ANCHOR = b"static void direct_breakdown(const char* why, uint32_t list_bos) {\n\tfor (auto& S: g_d) direct_breakdown_one(S, why, list_bos);\n}\n\n"
PASS_ANCHOR = b"\t// 2. the views' addresses: every (view, imported range) intersection is one GPU mapping\n"
PASS_TEXT = tabs(r"""    // Experiment 0401 series e7 (lzr, BC5_DIRECT_LAZY_RELEASE): released chunks a view covers again are imported here, and
    // once per pass period chunks under no view for the idle time are cut out of their BOs (retired as the merge retires
    // its BOs: the drain below, the rebuild, then free_shared).
    LzrPass lzr = lzr_pass(S, views, sig, fd, now, merged, retired, remaps, merge_map_cap);
""")
CONFIRM_ANCHOR = b"\tconst uint64_t t_maps0 = SoftCp::now_ns();\n\tg_dprof_drain_ns += t_maps0 - t_drain0;\n"
CONFIRM_TEXT = b"\tlzr_confirm(S, lzr, retired); // experiment 0401 series e7 (lzr): a cut stands only when every ring is idle after the drain\n"

# (what, old, new) in file order.
EDITS = (
    ("block", BLOCK_ANCHOR, BLOCK_ANCHOR + LZR_PURE + b"\n" + LZR_GLUE),
    ("pass", PASS_ANCHOR, PASS_TEXT + PASS_ANCHOR),
    ("confirm", CONFIRM_ANCHOR, CONFIRM_ANCHOR + CONFIRM_TEXT),
)

# What the inserted code relies on, as the input has it (each exactly once).
REQUIRE = (
    b"struct DBo { uint64_t off, size; uint32_t id; uint64_t t_ns; };\n",
    b"\tstd::set<uint64_t> forced; // chunk offsets the hints and learned regions asked for\n",
    b"\tstd::vector<DMap>  maps;  // sorted by va\n",
    b"static void wait_jobs();\n",
    b"static double timing_now() {\n",
    b"static uint64_t direct_gtt(const char* leaf) {\n",
    b"static void direct_sync_one(DState& S, bool force) {\n",
    b"\tconst auto               views_p = direct_views(S);\n\tconst std::vector<DView>& views  = views_p->v;\n",
    b"\tconst uint64_t sig = views_p->sig;\n",
    b"\tstd::vector<uint32_t> retired;\n\tuint32_t              merged = 0;\n",
    b"\tstatic constexpr uint32_t merge_map_cap = 512u;\n\tuint32_t remaps = 0, deferred = 0; // experiment 0167\n",
    b"\tif (!retired.empty() || sig != S.views_sig) {\n\t\twait_jobs(); // mappings are about to go or be replaced\n",
    b"\tif (sig != S.views_sig || S.bos.size() != S.bos_mapped || !retired.empty()) {\n",
    b"\tfor (const uint32_t id: retired) g_dev->free_shared(id);\n",
)


def edit(s, check_md5=True):
    if MARK in s or b"Lzr0401" in s or b"lzr_pass" in s:
        sys.exit(f"mklzr0401: {REL} has the edit already")
    got = hashlib.md5(s).hexdigest()
    if check_md5 and got not in INPUTS:
        sys.exit(f"mklzr0401: {REL} md5 {got} is not an accepted input ({', '.join(sorted(INPUTS))})")
    if b"\r\n" in s:
        sys.exit(f"mklzr0401: {REL} has CRLF line endings; this script expects LF")
    for r in REQUIRE:
        if s.count(r) != 1:
            sys.exit(f"mklzr0401: the input has {s.count(r)} copies of {r[:70]!r}, not one")
    # The two calls sit in direct_sync_one, in this order: the merge's locals, the pass, the drain, the confirm, the
    # rebuild, the frees.
    f0 = s.index(b"static void direct_sync_one(DState& S, bool force) {\n")
    f1 = s.index(b"\nstatic void direct_sync(bool force) {\n")
    order = [s.index(x) for x in (b"\tuint32_t remaps = 0, deferred = 0; // experiment 0167\n", PASS_ANCHOR, b"\t\twait_jobs(); // mappings are about to go or be replaced\n",
                                  CONFIRM_ANCHOR, b"\tif (sig != S.views_sig || S.bos.size() != S.bos_mapped || !retired.empty()) {\n",
                                  b"\tfor (const uint32_t id: retired) g_dev->free_shared(id);\n")]
    if not (f0 < order[0] < order[1] < order[2] < order[3] < order[4] < order[5] < f1):
        sys.exit("mklzr0401: direct_sync_one's steps are not in the order the edit expects")
    if not (s.index(BLOCK_ANCHOR) < f0 and s.index(b"static void wait_jobs();\n") < s.index(BLOCK_ANCHOR)):
        sys.exit("mklzr0401: the block's anchor is not between wait_jobs's declaration and direct_sync_one")
    o = s
    for what, old, new in EDITS:
        n = o.count(old)
        if n != 1:
            sys.exit(f"mklzr0401: anchor '{what}' occurs {n} times, not once")
        o = o.replace(old, new)
    if o.count(LZR_PURE) != 1 or o.count(b"lzr_pass(S, views") != 1 or o.count(b"lzr_confirm(S, lzr, retired)") != 1:
        sys.exit("mklzr0401: self-check: the inserted text is not there once")
    # Undo every replacement, last first: the input must come back.
    back = o
    for what, old, new in reversed(EDITS):
        if back.count(new) != 1:
            sys.exit(f"mklzr0401: self-check: the new text of '{what}' occurs {back.count(new)} times")
        back = back.replace(new, old)
    if back != s:
        sys.exit("mklzr0401: self-check: undoing the edits does not give the input back")
    return o


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    root, out = sys.argv[1], sys.argv[2]
    with open(os.path.join(root, REL), "rb") as f:
        s = f.read()
    o = edit(s)
    for rel, data in ((REL, o), (INC, LZR_PURE)):
        p = os.path.join(out, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
        print(f"{rel} {hashlib.md5(data).hexdigest()}")


if __name__ == "__main__":
    main()
