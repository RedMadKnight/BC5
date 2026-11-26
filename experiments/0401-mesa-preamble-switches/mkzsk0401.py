#!/usr/bin/env python3
"""BC5 experiment 0401 series e7, tag zsk: experiment 0379's zero skip carried onto the e6 unit src/libs/bc5LleAgc.cpp
(md5 pinned in INPUTS below: main's unit + mkunit0401.py + e4's mkfl0401.py + e5's mkeq0405.py and mkgpu0405.py).
  BC5_DIRECT_ZERO_SKIP=<list>  the zero skip, default off (unset, empty or "0": off, the e6 path). Any other value is the
                               path of a zero list (exp 0379's format, e.g. exp 0388's zero-list-moving.txt): the listed
                               all-zero 2 MiB chunks of the eager heaps it names are left out of the eager import (never
                               pinned), with a canary slice mapped under them; a CPU write, a hint window, a canary hit and
                               a device reopen take chunks back.
  BC5_DIRECT_ZEROSCAN_AT/_OUT, BC5_DIRECT_ZERO_NAMES, BC5_DIRECT_ZERO_MIN_MIB: exp 0379's scan diagnostic, carried as is.
The edit re-applies exp 0379's patch0379-bc5LleAgc.diff (made on main's unit), each hunk located by content, with the
changes listed in zsk0401-notes.md ("Hunks"). bc5/zero_skip.hpp (backend/include/bc5, 782ca0e9) is inlined at the top of
the unit, lines 13-228 byte for byte (no include path change, nothing beside the unit). The seams bc5_zsk0401_* serve the
CPU test zsk0401.cpp only. Every anchor must occur exactly once; a unit that has the edit already is refused, and so is
an input whose md5 is not INPUTS' (the top session re-pins INPUTS when it chains scripts: zsk -> lzr -> cap). After the
edit the script reverts it in memory and asserts that the input comes back byte for byte. Prints "<rel> <md5>" for the
output (one file: the unit).
usage: mkzsk0401.py <tree root in> <out dir>"""
import hashlib
import os
import sys

# The one input this script edits, by md5 (re-pinned here, and only here, when the chain changes).
INPUTS = {"src/libs/bc5LleAgc.cpp": "d1cfd9bb1f1b3485bed4207a7f064d4f"}  # e6's unit (e5 chain: ... mkeq0405, mkgpu0405)
REL = "src/libs/bc5LleAgc.cpp"
# Present only once this edit (or exp 0379's or 0388's) is in: refuse such an input.
MARKS = (b"BC5_DIRECT_ZERO_SKIP", b"bc5_zsk0401_", b"zskip_resolve", b"namespace bc5::zero_skip", b"bc5/zero_skip.hpp\"")
# backend/include/bc5/zero_skip.hpp (md5 782ca0e94aa9ca708a33f185a0c6a42c, exp 0379), lines 13-228: its md5 and size.
HEADER_MD5, HEADER_LEN = "8355b699a5443434a23b607e3df1b397", 8876


def tabs(text):
    """The C++ below is written with 4-space indents; the unit indents with tabs."""
    out = []
    for line in text.split("\n"):
        body = line.lstrip(" ")
        k = len(line) - len(body)
        out.append("\t" * (k // 4) + " " * (k % 4) + body)
    return "\n".join(out).encode("ascii")


# ---------------------------------------------------------------------------------------------------------------------
# The header, verbatim (its own 4-space indents kept, so it diffs clean against backend/include/bc5/zero_skip.hpp).
ZERO_SKIP_HPP = r"""#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <map>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

namespace bc5::zero_skip {

inline constexpr std::uint64_t kChunk = 2ull << 20u;

// One heap of the list: its name, its total size (a later run uses the list only if the heap has the same size) and
// its zero runs as (offset from the heap's start, length), chunk aligned, sorted, disjoint.
struct Heap {
    std::string                                       name;
    std::uint64_t                                     size  = 0;
    std::uint32_t                                     scans = 0;
    std::vector<std::pair<std::uint64_t, std::uint64_t>> runs;
};

// The file: "# comment" lines; "heap <name> <size hex> <scans>"; "zero <name> <offset hex> <length hex>".
inline std::string format_list(const std::vector<Heap>& heaps) {
    std::string s = "# bc5 zero list v1 (experiment 0379): chunks all-zero in every scan, offsets from the heap's start\n";
    char        line[256];
    for (const auto& h: heaps) {
        std::snprintf(line, sizeof line, "heap %s 0x%llx %u\n", h.name.c_str(), static_cast<unsigned long long>(h.size), h.scans);
        s += line;
        for (const auto& [o, n]: h.runs) {
            std::snprintf(line, sizeof line, "zero %s 0x%llx 0x%llx\n", h.name.c_str(), static_cast<unsigned long long>(o), static_cast<unsigned long long>(n));
            s += line;
        }
    }
    return s;
}

// Parses format_list's output. Malformed lines, runs that are not chunk aligned, out of the heap or overlapping, and
// runs of an unknown heap are dropped; `bad` counts them.
inline std::vector<Heap> parse_list(const std::string& text, std::uint32_t* bad = nullptr) {
    std::vector<Heap>  heaps;
    std::uint32_t      nbad = 0;
    std::istringstream in(text);
    std::string        line;
    auto               find = [&heaps](const std::string& n) -> Heap* {
        for (auto& h: heaps) {
            if (h.name == n) return &h;
        }
        return nullptr;
    };
    while (std::getline(in, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty() || line[0] == '#') continue;
        std::istringstream ls(line);
        std::string        kind, name, a, b;
        if (!(ls >> kind >> name >> a >> b)) { nbad++; continue; }
        char*                    e1 = nullptr;
        char*                    e2 = nullptr;
        const unsigned long long x  = std::strtoull(a.c_str(), &e1, 16);
        const unsigned long long y  = std::strtoull(b.c_str(), &e2, kind == "heap" ? 10 : 16);
        if (*e1 != 0 || *e2 != 0) { nbad++; continue; }
        if (kind == "heap") {
            if (find(name) != nullptr || x == 0) { nbad++; continue; }
            heaps.push_back({name, x, static_cast<std::uint32_t>(y), {}});
        } else if (kind == "zero") {
            Heap* h = find(name);
            if (h == nullptr || x % kChunk != 0 || y == 0 || y % kChunk != 0 || x + y > h->size || x + y < x ||
                (!h->runs.empty() && h->runs.back().first + h->runs.back().second > x)) {
                nbad++;
                continue;
            }
            h->runs.emplace_back(x, y);
        } else {
            nbad++;
        }
    }
    if (bad != nullptr) *bad = nbad;
    return heaps;
}

// The scan's state for one heap: chunk i is a candidate while it was all-zero in every scan so far.
class ZeroMask {
public:
    explicit ZeroMask(std::uint64_t heap_size) : zero_((heap_size + kChunk - 1) / kChunk, 1) {}
    std::size_t chunks() const { return zero_.size(); }
    std::uint32_t scans() const { return scans_; }
    // One scan's result for every chunk (1 = all zero now).
    void intersect(const std::vector<std::uint8_t>& now) {
        for (std::size_t i = 0; i < zero_.size(); i++) zero_[i] = zero_[i] != 0 && i < now.size() && now[i] != 0 ? 1 : 0;
        scans_++;
    }
    std::uint64_t zero_bytes() const {
        return static_cast<std::uint64_t>(std::count(zero_.begin(), zero_.end(), std::uint8_t {1})) * kChunk;
    }
    // Runs of at least min_bytes, as (offset, length); a last partial chunk is never listed.
    std::vector<std::pair<std::uint64_t, std::uint64_t>> runs(std::uint64_t heap_size, std::uint64_t min_bytes) const {
        std::vector<std::pair<std::uint64_t, std::uint64_t>> r;
        const std::size_t whole = static_cast<std::size_t>(heap_size / kChunk);
        for (std::size_t i = 0; i < whole;) {
            if (zero_[i] == 0) { i++; continue; }
            std::size_t j = i;
            while (j < whole && zero_[j] != 0) j++;
            const std::uint64_t n = static_cast<std::uint64_t>(j - i) * kChunk;
            if (scans_ != 0 && n >= min_bytes) r.emplace_back(static_cast<std::uint64_t>(i) * kChunk, n);
            i = j;
        }
        return r;
    }

private:
    std::vector<std::uint8_t> zero_;
    std::uint32_t             scans_ = 0;
};

// True when [p, p + n) holds only zero bytes.
inline bool all_zero(const void* p, std::size_t n) {
    const auto* b = static_cast<const unsigned char*>(p);
    std::size_t i = 0;
    for (; i + 8 <= n; i += 8) {
        std::uint64_t w = 0;
        std::memcpy(&w, b + i, 8);
        if (w != 0) return false;
    }
    for (; i < n; i++) {
        if (b[i] != 0) return false;
    }
    return true;
}

// The run's skip set at run time, in absolute chunk offsets (file offsets of the direct-memory memfd). Each run keeps
// its index (its canary slice) for the session; chunks leave one at a time (a CPU write, a hint) or a run at a time
// (a canary hit).
class SkipSet {
public:
    // Adds a run [off, off + len) with a new index; returns the index. Overlaps with present chunks are not added.
    std::uint32_t add_run(std::uint64_t off, std::uint64_t len) {
        const auto idx = static_cast<std::uint32_t>(runs_.size());
        runs_.push_back({off, len});
        for (std::uint64_t c = off; c < off + len; c += kChunk) {
            if (chunk_.emplace(c, idx).second) bytes_ += kChunk;
        }
        return idx;
    }
    bool          contains(std::uint64_t c) const { return chunk_.count(c) != 0; }
    bool          empty() const { return chunk_.empty(); }
    std::uint64_t bytes() const { return bytes_; }
    std::size_t   run_count() const { return runs_.size(); }
    // The run index of a skipped chunk, or -1.
    long run_of(std::uint64_t c) const {
        const auto it = chunk_.find(c);
        return it == chunk_.end() ? -1 : static_cast<long>(it->second);
    }
    std::pair<std::uint64_t, std::uint64_t> run(std::uint32_t idx) const { return runs_.at(idx); }
    // Chunks of run idx still skipped.
    std::uint64_t run_left(std::uint32_t idx) const {
        std::uint64_t n = 0;
        const auto [o, l] = runs_.at(idx);
        for (std::uint64_t c = o; c < o + l; c += kChunk) {
            const auto it = chunk_.find(c);
            if (it != chunk_.end() && it->second == idx) n += kChunk;
        }
        return n;
    }
    // Takes one chunk back; true if it was skipped.
    bool erase_chunk(std::uint64_t c) {
        if (chunk_.erase(c) == 0) return false;
        bytes_ -= kChunk;
        return true;
    }
    // Takes a whole run back; returns the bytes that were still skipped.
    std::uint64_t erase_run(std::uint32_t idx) {
        std::uint64_t n = 0;
        const auto [o, l] = runs_.at(idx);
        for (std::uint64_t c = o; c < o + l; c += kChunk) {
            const auto it = chunk_.find(c);
            if (it != chunk_.end() && it->second == idx) {
                chunk_.erase(it);
                n += kChunk;
            }
        }
        bytes_ -= n;
        return n;
    }
    // Skipped chunks in [lo, hi), ascending.
    std::vector<std::uint64_t> chunks_in(std::uint64_t lo, std::uint64_t hi) const {
        std::vector<std::uint64_t> v;
        for (auto it = chunk_.lower_bound(lo & ~(kChunk - 1)); it != chunk_.end() && it->first < hi; ++it) v.push_back(it->first);
        return v;
    }
    void clear() {
        chunk_.clear();
        runs_.clear();
        bytes_ = 0;
    }

private:
    std::map<std::uint64_t, std::uint32_t>               chunk_; // chunk offset -> run index
    std::vector<std::pair<std::uint64_t, std::uint64_t>> runs_;
    std::uint64_t                                        bytes_ = 0;
};

// Places a list heap at its absolute file offset `base` (the lowest offset of the heap's views) into the skip set.
// Returns the bytes added.
inline std::uint64_t place(const Heap& h, std::uint64_t base, SkipSet* set) {
    std::uint64_t n = 0;
    for (const auto& [o, l]: h.runs) {
        const std::uint64_t before = set->bytes();
        set->add_run(base + o, l);
        n += set->bytes() - before;
    }
    return n;
}

} // namespace bc5::zero_skip
"""

# 1. After the direct path's includes: two system headers and the inlined header (exp 0379's include hunk).
E1_OLD = b'#include "bc5/full_state.hpp"\n'
E1_NEW = (E1_OLD + tabs(r"""#include <sys/resource.h> // experiment 0379 (exp 0401 e7, mkzsk0401.py): setpriority, for the zero scan and the canary
#include <sys/syscall.h>  // experiment 0379: SYS_gettid
// ---- experiment 0379's backend/include/bc5/zero_skip.hpp (782ca0e9) lines 13-228, inlined by exp 0401's mkzsk0401.py ----
// Series e7 changes no include path, so the header's text is here, byte for byte; the backend keeps its copy and its
// Catch2 test (backend/tests/zero_skip_test.cpp). The skip's host side is in namespace Direct, before direct_sync_one.
""") + ZERO_SKIP_HPP.encode("ascii") + tabs(r"""// ---- end of experiment 0379's zero_skip.hpp ------------------------------------------------------------------------
"""))

# 2. The scan and skip block before direct_sync_one (exp 0379's raw/zskip_block.cpp, with the changes the notes list),
#    then the CPU test's seams.
ZSK_BLOCK = tabs(r"""// ---- experiment 0379: the zero list (BC5_DIRECT_ZEROSCAN_AT/_OUT) and the skip (BC5_DIRECT_ZERO_SKIP) ---------------
// RenderGpuWcLarge and CommitIABufferAllocator are eager, so every chunk of them is pinned, and exp 0333 found ~2.8 GB
// of them all-zero for 20 minutes (F402); with RT on the box then runs out of page cache (F505). A diagnostic run scans
// the named heaps (BC5_DIRECT_ZERO_NAMES) on a background thread at the given times and writes the chunks that were
// all-zero in every scan (bc5/zero_skip.hpp). A later run leaves those chunks out of the eager import. Each skipped
// run is mapped onto its own 2 MiB slice of one canary BO at every VA that maps it, so a GPU access never faults: a
// read gets zeros, a write shows in the slice, which a background thread checks (one slice per 50 ms), and the run
// is then taken back. A CPU write (SEEK_DATA), a hint window and a device reopen take chunks back too; a learned
// window does not (the learned windows in these heaps predate their eager import, F96). Off unless
// BC5_DIRECT_ZERO_SKIP names a list.
// Exp 0401 series e7 (mkzsk0401.py, zsk0401-notes.md): exp 0379's patch0379-bc5LleAgc.diff carried onto the e6 unit, for
// the memory pressure of the e6 plays. Against 0379's text: BC5_DIRECT_ZERO_SKIP is read as every e-series switch (unset,
// empty and "0" are off, any other value is the list's path); bc5/zero_skip.hpp is inlined at the top of the unit; the
// canary check, the start of a sync and the hint take-back are functions of their own (the same statements), and a
// learned window is marked by a scope guard (ZLearned); a canary hit on a run that hints and CPU writes have already taken
// back in full is retired (0379 kept its flag raised, which forced a full sync at every later call while anything stayed
// skipped); the seams bc5_zsk0401_* at the end serve the CPU test zsk0401.cpp only.
static const std::vector<std::string>& zero_names() {
    static const std::vector<std::string> names = [] {
        std::vector<std::string> v;
        const char*              e = std::getenv("BC5_DIRECT_ZERO_NAMES");
        std::string              s = e != nullptr ? e : "RenderGpuWcLarge,CommitIABufferAllocator", cur;
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
    return names;
}
// The file range a named heap's eager views span (the lowest offset and the span), 0 when none is there yet.
static std::pair<uint64_t, uint64_t> zero_heap_span(const std::vector<DView>& views, const std::string& name) {
    uint64_t lo = ~0ull, hi = 0;
    for (const auto& v: views) {
        if (!v.eager || v.name != name) continue;
        lo = std::min(lo, v.off);
        hi = std::max(hi, v.off + v.size);
    }
    return hi > lo ? std::pair<uint64_t, uint64_t> {lo, hi - lo} : std::pair<uint64_t, uint64_t> {0, 0};
}

// The diagnostic scan (arm S).
struct ZScanHeap {
    std::string                                  name;
    uint64_t                                     base = 0, span = 0;
    std::vector<std::pair<uint64_t, uint64_t>> ranges; // the views' file ranges
};
static std::mutex                                      g_zscan_mutex;
static std::map<std::string, bc5::zero_skip::ZeroMask> g_zscan_masks;
static std::map<std::string, uint64_t>                 g_zscan_spans;
static std::atomic<bool>                               g_zscan_busy {false};
static void zscan_run(int fd, std::vector<ZScanHeap> heaps, double t_start, uint32_t k) {
    setpriority(PRIO_PROCESS, static_cast<id_t>(syscall(SYS_gettid)), 19);
    const char*         out     = std::getenv("BC5_DIRECT_ZEROSCAN_OUT");
    const uint64_t      min_mib = std::getenv("BC5_DIRECT_ZERO_MIN_MIB") != nullptr ? std::strtoull(std::getenv("BC5_DIRECT_ZERO_MIN_MIB"), nullptr, 10) : 8ull;
    std::vector<char>   buf(kDChunk);
    std::vector<bc5::zero_skip::Heap> list;
    for (const auto& h: heaps) {
        const size_t         n = static_cast<size_t>((h.span + kDChunk - 1) / kDChunk);
        std::vector<uint8_t> now(n, 0);
        uint64_t             zero_now = 0;
        for (size_t i = 0; i < n; i++) {
            const uint64_t c = h.base + static_cast<uint64_t>(i) * kDChunk;
            bool           in = false;
            for (const auto& [a, b]: h.ranges) in = in || (c >= a && c + kDChunk <= b);
            if (!in) continue; // not wholly inside a view: never listed
            const ssize_t r = pread(fd, buf.data(), kDChunk, static_cast<off_t>(c));
            if (r == static_cast<ssize_t>(kDChunk) && bc5::zero_skip::all_zero(buf.data(), kDChunk)) {
                now[i] = 1;
                zero_now += kDChunk;
            }
        }
        std::lock_guard lk(g_zscan_mutex);
        if (auto s = g_zscan_spans.find(h.name); s != g_zscan_spans.end() && s->second != h.span) {
            journal("zero scan %u: %s spans 0x%" PRIx64 ", not 0x%" PRIx64 " as before: its mask starts again\n", k, h.name.c_str(), h.span, s->second);
            g_zscan_masks.erase(h.name);
        }
        g_zscan_spans[h.name] = h.span;
        auto& m = g_zscan_masks.try_emplace(h.name, h.span).first->second;
        m.intersect(now);
        bc5::zero_skip::Heap lh {h.name, h.span, m.scans(), m.runs(h.span, min_mib << 20u)};
        uint64_t             listed = 0;
        for (const auto& [o, l]: lh.runs) listed += l;
        journal("zero scan %u at t %.1f s: %s %.1f MiB, zero now %.1f MiB, zero in all %u scans %.1f MiB, listed %.1f MiB in %zu runs of >= %" PRIu64 " MiB (%.0f ms)\n", k,
                t_start, h.name.c_str(), static_cast<double>(h.span) / 1048576.0, static_cast<double>(zero_now) / 1048576.0, m.scans(),
                static_cast<double>(m.zero_bytes()) / 1048576.0, static_cast<double>(listed) / 1048576.0, lh.runs.size(), min_mib, (timing_now() - t_start) * 1000.0);
        list.push_back(std::move(lh));
    }
    if (out != nullptr) {
        const std::string tmp = std::string(out) + ".tmp";
        if (FILE* f = std::fopen(tmp.c_str(), "w")) {
            const std::string text = bc5::zero_skip::format_list(list);
            const bool        ok   = std::fwrite(text.data(), 1, text.size(), f) == text.size();
            if (std::fclose(f) == 0 && ok && std::rename(tmp.c_str(), out) == 0) journal("zero scan %u: list written to %s\n", k, out);
        }
    }
    g_zscan_busy = false;
}
static void zscan_tick(const DState& S, const std::vector<DView>& views) {
    static const std::vector<double> at = [] {
        std::vector<double> v;
        if (const char* e = BC5_DIAG_ENV("BC5_DIRECT_ZEROSCAN_AT"); e != nullptr) {
            for (const char* p = e; *p != 0;) {
                char* end = nullptr;
                const double t = std::strtod(p, &end);
                if (end == p) break;
                v.push_back(t);
                p = *end == ',' ? end + 1 : end;
            }
            std::sort(v.begin(), v.end());
        }
        return v;
    }();
    static size_t   next = 0;
    static uint32_t k    = 0;
    if (S.kind != 0 || next >= at.size() || timing_now() < at[next] || g_zscan_busy) return;
    const double t = timing_now();
    while (next < at.size() && at[next] <= t) next++; // times that passed while a scan ran go to this one
    std::vector<ZScanHeap> heaps;
    for (const auto& name: zero_names()) {
        const auto [base, span] = zero_heap_span(views, name);
        if (span == 0) continue;
        ZScanHeap h {name, base, span, {}};
        for (const auto& v: views) {
            if (v.eager && v.name == name) h.ranges.emplace_back(v.off, v.off + v.size);
        }
        heaps.push_back(std::move(h));
    }
    const int fd = dstate_fd(S);
    if (heaps.empty() || fd < 0) return;
    g_zscan_busy = true;
    std::thread(zscan_run, fd, std::move(heaps), t, ++k).detach();
}

// The skip (arm B). One thread does the sync, the forcing and the mapping (as the rest of this path); the canary
// thread only reads the slices and raises a run's flag.
static bc5::zero_skip::SkipSet                  g_zskip;
struct ZPiece { uint64_t size; uint32_t run; };
static std::map<uint64_t, ZPiece>               g_zpieces; // canary mappings by VA
static std::set<std::string>                    g_zskip_placed; // list heaps placed or refused
static std::vector<bc5::zero_skip::Heap>        g_zskip_list;
static bool                                     g_zskip_off = false;
static int                                      g_zcanary_fd = -1;
static uint32_t                                 g_zcanary_id = 0;
static const unsigned char*                     g_zcanary_cpu = nullptr;
static std::unique_ptr<std::atomic<uint8_t>[]>  g_zflag; // per run: 0 watched, 1 hit (not yet taken back), 2 done
static size_t                                   g_zruns = 0; // the list's runs: one slice each, whatever order the heaps are placed in
static std::vector<uint64_t>                    g_zleft; // per run: bytes still skipped (0: nothing to look at)
static std::atomic<bool>                        g_zcanary_stop {false};
static uint64_t g_zstat_cpu = 0, g_zstat_hint = 0, g_zstat_hits = 0, g_zstat_placed = 0;
static thread_local bool t_force_learned = false; // direct_force called for a learned window (map_window)
static bool                                     g_zsk_cpu_test = false; // exp 0401 e7: set by zsk0401.cpp only (bc5_zsk0401_reset): a canary with no BO
static const char* zskip_path() {
    static const char* p = bc5::env_on(std::getenv("BC5_DIRECT_ZERO_SKIP")) ? std::getenv("BC5_DIRECT_ZERO_SKIP") : nullptr; // exp 0401 e7: unset, empty and "0" are off (F767)
    return p;
}
// One look at run r's canary slice (exp 0401 e7: the watcher's loop body as 0379 wrote it, in a function of its own).
static void zcanary_check(size_t r) {
    if (g_zflag[r].load() != 0) return;
    const unsigned char* p = g_zcanary_cpu + r * kDChunk;
    // TODO(verify): whether the CPU sees the GPU's writes to an imported udmabuf page without a flush; the
    // lines are flushed first, so a stale cached zero line cannot hide a write.
    for (uint64_t o = 0; o < kDChunk; o += 64) __builtin_ia32_clflush(p + o);
    __builtin_ia32_mfence();
    if (!bc5::zero_skip::all_zero(p, kDChunk)) g_zflag[r] = 1;
}
static void zcanary_watch(size_t runs) {
    setpriority(PRIO_PROCESS, static_cast<id_t>(syscall(SYS_gettid)), 10);
    for (size_t r = 0; !g_zcanary_stop; r = (r + 1) % runs) {
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
        zcanary_check(r);
    }
}
// Unmaps the canary mappings that overlap [lo, hi) (a real mapping is about to go there).
static void zskip_release(uint64_t lo, uint64_t hi) {
    auto it = g_zpieces.lower_bound(lo >= kDChunk ? lo - kDChunk : 0);
    while (it != g_zpieces.end() && it->first < hi) {
        if (it->first + it->second.size > lo) {
            if (g_dev) g_dev->unmap_shared(it->first);
            it = g_zpieces.erase(it);
        } else {
            ++it;
        }
    }
}
// Maps the canary under every skipped chunk at every VA a view gives it, where no canary is yet.
static void zskip_map(const std::vector<DView>& views) {
    if (g_zskip.empty() || g_zcanary_id == 0 || !g_dev) return;
    uint32_t added = 0, failed = 0;
    for (const auto& v: views) {
        for (const uint64_t c: g_zskip.chunks_in(v.off, v.off + v.size)) {
            const uint64_t lo = std::max(c, v.off), hi = std::min(c + kDChunk, v.off + v.size);
            if (lo >= hi) continue;
            const uint64_t va = v.va + (lo - v.off);
            if (g_zpieces.count(va) != 0) continue;
            const long run = g_zskip.run_of(c);
            if (run < 0) continue;
            if (g_dev->map_shared(g_zcanary_id, static_cast<uint64_t>(run) * kDChunk + (lo - c), hi - lo, va)) {
                g_zpieces.emplace(va, ZPiece {hi - lo, static_cast<uint32_t>(run)});
                added++;
            } else {
                failed++;
            }
        }
    }
    if (added != 0 || failed != 0) journal("zero skip: canary +%u mappings (%zu)%s\n", added, g_zpieces.size(), failed != 0 ? "; SOME CANARY MAPS FAILED" : "");
}
// Places the list's heaps once their views are there (same span as in the list), before their first import.
static bool zskip_resolve(const std::vector<DView>& views) {
    if (zskip_path() == nullptr || g_zskip_off || g_zskip_placed.size() == g_zskip_list.size() + 1) return false;
    if (g_zskip_placed.empty()) { // first call: load the list
        g_zskip_placed.insert(""); // the marker that the list was read
        std::string text;
        if (FILE* f = std::fopen(zskip_path(), "r")) {
            char   b[4096];
            size_t n = 0;
            while ((n = std::fread(b, 1, sizeof b, f)) > 0) text.append(b, n);
            std::fclose(f);
        }
        uint32_t bad = 0;
        g_zskip_list = bc5::zero_skip::parse_list(text, &bad);
        uint64_t total = 0;
        for (const auto& h: g_zskip_list) {
            for (const auto& [o, l]: h.runs) total += l;
        }
        journal("zero skip: list %s, %zu heaps, %.1f MiB listed, %u bad lines\n", zskip_path(), g_zskip_list.size(), static_cast<double>(total) / 1048576.0, bad);
    }
    bool placed = false;
    for (const auto& h: g_zskip_list) {
        if (g_zskip_placed.count(h.name) != 0) continue;
        const auto [base, span] = zero_heap_span(views, h.name);
        if (span == 0) continue; // not there yet
        g_zskip_placed.insert(h.name);
        if (span != h.size) {
            journal("zero skip: %s spans 0x%" PRIx64 ", the list says 0x%" PRIx64 ": not skipped\n", h.name.c_str(), span, h.size);
            continue;
        }
        if (g_zskip.run_count() + h.runs.size() > (g_zruns != 0 ? g_zruns : ~size_t {0})) { journal("zero skip: %s: no canary slice left: not skipped\n", h.name.c_str()); continue; }
        const uint64_t n = bc5::zero_skip::place(h, base, &g_zskip);
        g_zstat_placed += n;
        placed = true;
        journal("zero skip: %s at file 0x%" PRIx64 ": %.1f MiB in %zu runs skipped\n", h.name.c_str(), base, static_cast<double>(n) / 1048576.0, h.runs.size());
    }
    if (!placed) return false;
    // The canary: one memfd BO with one 2 MiB slice for each run of the list, made at the first placement (add_run
    // numbers the runs in placement order, so every placed run has a slice).
    if (g_zcanary_id == 0 && g_zcanary_fd < 0) {
        g_zruns = 0;
        for (const auto& h: g_zskip_list) g_zruns += h.runs.size();
        const uint64_t size = static_cast<uint64_t>(g_zruns) * kDChunk;
        g_zcanary_fd = memfd_create("bc5-zero-canary", MFD_CLOEXEC | MFD_ALLOW_SEALING);
        void* cpu = MAP_FAILED;
        if (g_zcanary_fd >= 0 && ftruncate(g_zcanary_fd, static_cast<off_t>(size)) == 0 && fcntl(g_zcanary_fd, F_ADD_SEALS, F_SEAL_SHRINK) == 0) {
            cpu = mmap(nullptr, size, PROT_READ, MAP_SHARED, g_zcanary_fd, 0);
        }
        g_zcanary_id = cpu != MAP_FAILED && g_dev ? g_dev->import_memfd(g_zcanary_fd, 0, size) : (cpu != MAP_FAILED && g_zsk_cpu_test ? 1u : 0u); // exp 0401 e7: zsk0401.cpp's canary has no BO
        if (g_zcanary_id == 0) {
            journal("zero skip: the canary BO (%zu runs) could not be made: nothing skipped\n", g_zruns);
            g_zskip.clear();
            g_zskip_off = true;
            return false;
        }
        g_zcanary_cpu = static_cast<const unsigned char*>(cpu);
        g_zflag.reset(new std::atomic<uint8_t>[g_zruns]);
        g_zleft.assign(g_zruns, 0);
        for (size_t r = 0; r < g_zruns; r++) g_zflag[r] = 0;
        std::thread(zcanary_watch, g_zruns).detach();
        journal("zero skip: canary BO %u, %zu slices of 2 MiB\n", g_zcanary_id, g_zruns);
    }
    for (size_t r = 0; r < g_zskip.run_count() && r < g_zleft.size(); r++) {
        if (g_zleft[r] == 0 && g_zflag[r].load() == 0) g_zleft[r] = g_zskip.run_left(static_cast<uint32_t>(r));
    }
    return true;
}
// Takes back the chunks of skipped runs the CPU has written (SEEK_DATA) and the runs whose canary was hit.
static void zskip_take_back(DState& S, int fd) {
    if (S.kind != 0 || g_zskip.empty()) return;
    for (size_t r = 0; r < g_zskip.run_count() && r < g_zruns; r++) {
        if (g_zflag[r].load() != 1) continue;
        if (g_zleft[r] == 0) { // exp 0401 e7: hints and CPU writes took the whole run back already: the hit is retired
            g_zflag[r] = 2;
            const auto [o, l] = g_zskip.run(static_cast<uint32_t>(r));
            journal("zero skip: canary hit in run %zu (file 0x%" PRIx64 " +%.1f MiB) after all of it was taken back: nothing to take\n", r, o, static_cast<double>(l) / 1048576.0);
            continue;
        }
        g_zflag[r] = 2;
        const auto     [o, l] = g_zskip.run(static_cast<uint32_t>(r));
        const uint64_t n      = g_zskip.erase_run(static_cast<uint32_t>(r));
        g_zleft[r]            = 0;
        g_zstat_hits++;
        S.blocks = ~0ull;
        journal("zero skip: canary hit in run %zu (file 0x%" PRIx64 " +%.1f MiB): %.1f MiB taken back\n", r, o, static_cast<double>(l) / 1048576.0, static_cast<double>(n) / 1048576.0);
    }
    for (size_t r = 0; r < g_zskip.run_count() && r < g_zleft.size(); r++) {
        if (g_zleft[r] == 0) continue;
        const auto [o, l] = g_zskip.run(static_cast<uint32_t>(r));
        for (uint64_t pos = o; pos < o + l;) {
            const off_t d = lseek(fd, static_cast<off_t>(pos), SEEK_DATA);
            if (d < 0 || static_cast<uint64_t>(d) >= o + l) break;
            const uint64_t c = static_cast<uint64_t>(d) & ~(kDChunk - 1);
            if (g_zskip.run_of(c) == static_cast<long>(r) && g_zskip.erase_chunk(c)) {
                g_zstat_cpu++;
                g_zleft[r] -= kDChunk;
            }
            pos = c + kDChunk;
        }
    }
}
static void zskip_report() {
    static double last = 0.0;
    if (zskip_path() == nullptr || g_zskip_placed.empty() || timing_now() - last < 60.0) return;
    last = timing_now();
    journal("zero skip: %.1f MiB still skipped of %.1f placed; taken back: %" PRIu64 " chunks by CPU writes, %" PRIu64 " by hints, %" PRIu64 " runs by canary hits; %zu canary mappings%s\n",
            static_cast<double>(g_zskip.bytes()) / 1048576.0, static_cast<double>(g_zstat_placed) / 1048576.0, g_zstat_cpu, g_zstat_hint, g_zstat_hits, g_zpieces.size(),
            g_zskip_off ? "; OFF" : "");
}
// After a device reopen the canary BO and its mappings are gone: the skip ends and everything is imported.
static void zskip_disable(const char* why) {
    if (zskip_path() == nullptr) return;
    g_zcanary_stop = true;
    g_zskip.clear();
    g_zpieces.clear();
    g_zcanary_id = 0;
    g_zskip_off  = true;
    journal("zero skip: off (%s)\n", why);
}
// Experiment 0379, in direct_force: a hint window (a render target, a user-data pointer) takes a skipped chunk back; a
// learned window (map_window, under ZLearned) does not. True when chunk c left the skip set; direct_force then counts the
// chunk as asked for, as 0379's "|| back" did (exp 0401 e7: 0379's statements, in a function of their own).
static bool zskip_hint_back(DState& S, uint64_t c) {
    if (S.kind != 0 || t_force_learned || g_zskip.empty()) return false;
    const long run = g_zskip.run_of(c);
    if (run < 0 || !g_zskip.erase_chunk(c)) return false;
    g_zstat_hint++;
    if (static_cast<size_t>(run) < g_zleft.size()) g_zleft[static_cast<size_t>(run)] -= kDChunk;
    S.blocks = ~0ull;
    return true;
}
// Experiment 0379, in map_window: direct_force for a learned window leaves skipped chunks skipped (exp 0401 e7: a scope
// guard instead of 0379's set, call, reset around the call, so map_window's own lines stay as they are).
struct ZLearned {
    explicit ZLearned(bool learned) { t_force_learned = learned; }
    ~ZLearned() { t_force_learned = false; }
    ZLearned(const ZLearned&)            = delete;
    ZLearned& operator=(const ZLearned&) = delete;
};
// Experiment 0379, at the start of direct_sync_one: places the zero list before the heaps' first import; a canary hit
// forces a full sync. True when a heap was placed just now (exp 0401 e7: 0379's lines, in a function of their own).
static bool zskip_sync_start(DState& S, const std::vector<DView>& views) {
    const bool zskip_new = S.kind == 0 && zskip_resolve(views);
    if (S.kind == 0) {
        zscan_tick(S, views);
        zskip_report();
        for (size_t r = 0; r < g_zskip.run_count() && r < g_zruns && !g_zskip.empty(); r++) {
            if (g_zflag[r].load() == 1) S.blocks = ~0ull;
        }
        if (zskip_new) S.blocks = ~0ull;
    }
    return zskip_new;
}

// ---- exp 0401 series e7: the seams of the CPU test zsk0401.cpp (always compiled in, never called by the emulator) ------
// The list's pure parts (bc5::zero_skip) run on the seams' own skip set; the skip's steps run on this session's state,
// with no device: bc5_zsk0401_reset(1) lets zskip_resolve make its canary memfd without a BO (g_zsk_cpu_test), and the
// canary watcher then runs as in a session. Nothing is reset once a canary watcher reads the slices.
static bc5::zero_skip::SkipSet g_zsk_test_set; // bc5_zsk0401_set's and bc5_zsk0401_place_set's own, never the session's
extern "C" int bc5_zsk0401_switch(char* path, size_t cap) {
    const char* p = zskip_path();
    if (p != nullptr && path != nullptr && cap != 0) std::snprintf(path, cap, "%s", p);
    return p != nullptr ? 1 : 0;
}
// parse_list, then format_list of what it kept, into out (cap bytes). The heaps kept; *bad: the lines dropped.
extern "C" uint32_t bc5_zsk0401_list(const char* text, char* out, size_t cap, uint32_t* bad) {
    const std::vector<bc5::zero_skip::Heap> heaps = bc5::zero_skip::parse_list(text != nullptr ? text : "", bad);
    if (out != nullptr && cap != 0) std::snprintf(out, cap, "%s", bc5::zero_skip::format_list(heaps).c_str());
    return static_cast<uint32_t>(heaps.size());
}
// A ZeroMask of heap_size given n_scans scans one after another (scan k: lens[k] entries, 1 = all zero now). info: chunks,
// scans, zero bytes; runs: up to cap (offset, length) pairs of runs(heap_size, min_bytes). The runs it gives.
extern "C" size_t bc5_zsk0401_mask(uint64_t heap_size, const uint8_t* scans, const size_t* lens, size_t n_scans, uint64_t min_bytes, uint64_t* info, uint64_t* runs, size_t cap) {
    bc5::zero_skip::ZeroMask m(heap_size);
    size_t                   at = 0;
    for (size_t k = 0; k < n_scans; k++) {
        m.intersect(std::vector<uint8_t>(scans + at, scans + at + lens[k]));
        at += lens[k];
    }
    const auto r = m.runs(heap_size, min_bytes);
    info[0]      = m.chunks();
    info[1]      = m.scans();
    info[2]      = m.zero_bytes();
    for (size_t i = 0; i < r.size() && i < cap; i++) {
        runs[2 * i]     = r[i].first;
        runs[2 * i + 1] = r[i].second;
    }
    return r.size();
}
extern "C" int bc5_zsk0401_all_zero(const void* p, size_t n) {
    return bc5::zero_skip::all_zero(p, n) ? 1 : 0;
}
// The seams' own skip set: 0 clear, 1 add_run(a, b) (its index), 2 contains(a), 3 run_of(a) + 1 (0: none), 4 bytes,
// 5 run_count, 6 run_left(a), 7 erase_chunk(a), 8 erase_run(a), 9 chunks_in(a, b)'s size, 10 its element k (~0: none),
// 11 empty.
extern "C" uint64_t bc5_zsk0401_set(int op, uint64_t a, uint64_t b, uint64_t k) {
    auto& s = g_zsk_test_set;
    switch (op) {
    case 0: s.clear(); return 0;
    case 1: return s.add_run(a, b);
    case 2: return s.contains(a) ? 1 : 0;
    case 3: return static_cast<uint64_t>(s.run_of(a) + 1);
    case 4: return s.bytes();
    case 5: return s.run_count();
    case 6: return s.run_left(static_cast<uint32_t>(a));
    case 7: return s.erase_chunk(a) ? 1 : 0;
    case 8: return s.erase_run(static_cast<uint32_t>(a));
    case 9: return s.chunks_in(a, b).size();
    case 10: {
        const std::vector<uint64_t> v = s.chunks_in(a, b);
        return k < v.size() ? v[k] : ~0ull;
    }
    case 11: return s.empty() ? 1 : 0;
    default: return ~0ull;
    }
}
// Every heap of the list `text` placed at file offset base into the seams' own set (bc5::zero_skip::place): bytes added.
extern "C" uint64_t bc5_zsk0401_place_set(const char* text, uint64_t base) {
    uint64_t n = 0;
    for (const auto& h: bc5::zero_skip::parse_list(text != nullptr ? text : "")) n += bc5::zero_skip::place(h, base, &g_zsk_test_set);
    return n;
}
// This session's skip: 0 bytes still skipped, 1 runs placed, 2 the list's runs (canary slices), 3 the canary BO id, 4 off,
// 5 heaps read from the list, 6 bytes placed, 7 chunks taken back by hints, 8 by CPU writes, 9 runs by canary hits,
// 10 canary mappings, 11 the watcher told to stop, 12 contains(a), 13 run_of(a) + 1 (0: none), 14 g_zleft[a] (~0: none),
// 15 g_zflag[a] (255: none), 16 t_force_learned on this thread, 17 the canary memfd + 1 (0: none), 18 heaps placed or
// refused.
extern "C" uint64_t bc5_zsk0401_state(int what, uint64_t a) {
    switch (what) {
    case 0: return g_zskip.bytes();
    case 1: return g_zskip.run_count();
    case 2: return g_zruns;
    case 3: return g_zcanary_id;
    case 4: return g_zskip_off ? 1 : 0;
    case 5: return g_zskip_list.size();
    case 6: return g_zstat_placed;
    case 7: return g_zstat_hint;
    case 8: return g_zstat_cpu;
    case 9: return g_zstat_hits;
    case 10: return g_zpieces.size();
    case 11: return g_zcanary_stop.load() ? 1 : 0;
    case 12: return g_zskip.contains(a) ? 1 : 0;
    case 13: return static_cast<uint64_t>(g_zskip.run_of(a) + 1);
    case 14: return a < g_zleft.size() ? g_zleft[a] : ~0ull;
    case 15: return g_zflag != nullptr && a < g_zruns ? static_cast<uint64_t>(g_zflag[a].load()) : uint64_t {255};
    case 16: return t_force_learned ? 1 : 0;
    case 17: return static_cast<uint64_t>(g_zcanary_fd + 1);
    case 18: return g_zskip_placed.empty() ? size_t {0} : g_zskip_placed.size() - 1; // without the "list read" marker
    default: return ~0ull;
    }
}
// Clears this session's skip as it was at the start (the list is read again at the next zskip_resolve); cpu_canary 1 lets
// zskip_resolve make its canary without a device. -1, and nothing cleared, once a canary watcher runs.
extern "C" int bc5_zsk0401_reset(int cpu_canary) {
    if (g_zcanary_cpu != nullptr) return -1;
    g_zskip.clear();
    g_zpieces.clear();
    g_zskip_placed.clear();
    g_zskip_list.clear();
    g_zskip_off = false;
    if (g_zcanary_fd >= 0) close(g_zcanary_fd);
    g_zcanary_fd = -1;
    g_zcanary_id = 0;
    g_zflag.reset();
    g_zruns = 0;
    g_zleft.clear();
    g_zstat_cpu = g_zstat_hint = g_zstat_hits = g_zstat_placed = 0;
    g_zsk_cpu_test = cpu_canary != 0;
    return 0;
}
// n views of direct memory: names[i] at file offset offs[i], sizes[i] bytes, eager[i], at va 0x10000000000 + offs[i].
static std::vector<DView> zsk_views(const char* const* names, const uint64_t* offs, const uint64_t* sizes, const int* eager, size_t n) {
    std::vector<DView> v;
    for (size_t i = 0; i < n; i++) v.push_back(DView {0x10000000000ull + offs[i], sizes[i], offs[i], names[i], false, eager[i] != 0});
    return v;
}
// A state of this kind (0 direct memory, 1 private memory) with this st_blocks mark.
static DState zsk_state(int kind, uint64_t blocks) {
    DState S {};
    S.kind   = kind;
    S.label  = kind == 0 ? "direct" : "private";
    S.blocks = blocks;
    return S;
}
// zskip_sync_start over those views; *blocks: the state's mark before and after. 1 when a heap was placed just now.
extern "C" int bc5_zsk0401_sync_start(int kind, const char* const* names, const uint64_t* offs, const uint64_t* sizes, const int* eager, size_t n, uint64_t* blocks) {
    DState     S = zsk_state(kind, *blocks);
    const bool r = zskip_sync_start(S, zsk_views(names, offs, sizes, eager, n));
    *blocks      = S.blocks;
    return r ? 1 : 0;
}
// zskip_hint_back for chunk c, as direct_force calls it for a hint window (learned 0) or, under map_window's guard, for a
// learned window (learned 1). 1 when the chunk left the skip set.
extern "C" int bc5_zsk0401_hint(int kind, uint64_t c, int learned, uint64_t* blocks) {
    DState S    = zsk_state(kind, *blocks);
    bool   back = false;
    {
        const ZLearned guard(learned != 0);
        back = zskip_hint_back(S, c);
    }
    *blocks = S.blocks;
    return back ? 1 : 0;
}
// zskip_take_back over the direct-memory file fd.
extern "C" void bc5_zsk0401_take_back(int kind, int fd, uint64_t* blocks) {
    DState S = zsk_state(kind, *blocks);
    zskip_take_back(S, fd);
    *blocks = S.blocks;
}
// A canary mapping at va (size bytes, run `run`) when size is not 0, then zskip_release(lo, hi) when hi > lo: the
// mappings left.
extern "C" size_t bc5_zsk0401_pieces(uint64_t va, uint64_t size, uint32_t run, uint64_t lo, uint64_t hi) {
    if (size != 0) g_zpieces.emplace(va, ZPiece {size, run});
    if (hi > lo) zskip_release(lo, hi);
    return g_zpieces.size();
}
extern "C" void bc5_zsk0401_disable() {
    zskip_disable("exp 0401 zsk0401.cpp");
}
// ---- end of experiment 0379's zero skip (exp 0401 e7) -------------------------------------------------------------------

""")

E2_OLD = b"static void direct_sync_one(DState& S, bool force) {\n"
E2_NEW = ZSK_BLOCK + E2_OLD

# 3. direct_sync_one: the list placed, the scan tick and a hit's full sync, before the fast path (0379's hunk 3).
E3_OLD = tabs("""    const uint64_t sig = views_p->sig;
    if (sig != S.views_sig) g_layout_gen++;
""")
E3_NEW = E3_OLD + tabs("""    const bool zskip_new = zskip_sync_start(S, views); // experiment 0379 (exp 0401 e7): place the zero list; a canary hit forces a full sync
""")
# 4. The take-back at the start of the full path (0379's hunk 4).
E4_OLD = tabs("""    const uint64_t t_scan0 = SoftCp::now_ns(); // experiment 0169
""")
E4_NEW = E4_OLD + tabs("""    zskip_take_back(S, fd); // experiment 0379: CPU writes and canary hits take skipped chunks back
    const bool zskip_on = S.kind == 0 && !g_zskip.empty();
""")
# 5. The eager loop skips the listed chunks (0379's hunk 5).
E5_A = tabs("""            for (uint64_t c = v.off & ~(kDChunk - 1); c < v.off + v.size; c += kDChunk) {
""")
E5_B = tabs("""                if (direct_covered_end(S, c) == 0) need.push_back(c);
""")
E5_OLD = E5_A + E5_B
E5_NEW = E5_A + tabs("""                if (zskip_on && g_zskip.contains(c)) continue; // experiment 0379: on the zero list, under the canary
""") + E5_B
# 6. The forced loop too: a chunk still skipped there is forced only by a learned window (0379's hunk 6).
E6_A = tabs("""    for (const uint64_t c: S.forced) {
""")
E6_B = tabs("""        if (direct_covered_end(S, c) == 0) need.push_back(c);
""")
E6_OLD = E6_A + E6_B
E6_NEW = E6_A + tabs("""        if (zskip_on && g_zskip.contains(c)) continue; // experiment 0379: forced only by a learned window
""") + E6_B
# 7. The canary mappings under a real mapping go first (0379's hunk 7).
E7_OLD = tabs("""                if (g_dev->map_shared(w.id, w.bo_off, w.size, w.va)) {
""")
E7_NEW = tabs("""                if (!g_zpieces.empty()) zskip_release(w.va, w.va + w.size); // experiment 0379
""") + E7_OLD
# 8. The canary mapped after a rebuild (0379's hunk 8).
E8_A = tabs("""        S.maps.swap(next);
""")
E8_B = tabs("""        S.views_sig  = sig;
""")
E8_OLD = E8_A + E8_B
E8_NEW = E8_A + tabs("""        if (S.kind == 0 && (zskip_new || sig != S.views_sig)) zskip_map(views); // experiment 0379
""") + E8_B
# 9. direct_force: a hint takes a skipped chunk back (0379's hunk 9, as one inserted line; today's line stays).
E9_OLD = tabs("""                if (S.forced.insert(c).second) here += kDChunk;
""")
E9_NEW = tabs("""                if (zskip_hint_back(S, c) && S.forced.count(c) != 0) here += kDChunk; // experiment 0379: a hint takes a skipped chunk back (with the next line: 0379's "|| back")
""") + E9_OLD
# 10. map_window: a learned window leaves skipped chunks skipped (0379's hunk 10, as a guard; today's lines stay).
E10_OLD = b"static void map_window(uint64_t lo, uint64_t hi, std::vector<bc5::direct::Mapping>& have, const char* what, uint64_t addr) {\n"
E10_NEW = E10_OLD + tabs("""    const ZLearned zlearned(std::strcmp(what, "learned") == 0); // experiment 0379: a learned window leaves skipped chunks skipped
""")
# 11. The device reopen ends the skip (0379's hunk 11; e6's reopen block is indented one level less than main's was).
E11_OLD = tabs("""        g_scratch.clear();
        g_scratch_id = 0;
""")
E11_NEW = E11_OLD + tabs("""        zskip_disable("device reopen"); // experiment 0379
""")

# (old, new, what) in file order; each old must occur exactly once in the input.
EDITS = (
    (E1_OLD, E1_NEW, "includes and the inlined zero_skip.hpp"),
    (E2_OLD, E2_NEW, "the scan and skip block and the seams, before direct_sync_one"),
    (E3_OLD, E3_NEW, "direct_sync_one: zskip_sync_start"),
    (E4_OLD, E4_NEW, "direct_sync_one: zskip_take_back, zskip_on"),
    (E5_OLD, E5_NEW, "direct_sync_one: the eager loop"),
    (E6_OLD, E6_NEW, "direct_sync_one: the forced loop"),
    (E7_OLD, E7_NEW, "direct_sync_one: zskip_release before a mapping"),
    (E8_OLD, E8_NEW, "direct_sync_one: zskip_map after the rebuild"),
    (E9_OLD, E9_NEW, "direct_force: zskip_hint_back"),
    (E10_OLD, E10_NEW, "map_window: ZLearned"),
    (E11_OLD, E11_NEW, "the device reopen: zskip_disable"),
)


def eol_of(s):
    crlf, lf = s.count(b"\r\n"), s.count(b"\n")
    assert crlf == 0 or crlf == lf, ("mixed line endings", crlf, lf)
    return b"\r\n" if crlf else b"\n"


def code_only(t):
    """t without its // comments, string literals and character literals (comments write intervals as [lo, hi))."""
    out, i, n = bytearray(), 0, len(t)
    while i < n:
        c = t[i:i + 1]
        if t.startswith(b"//", i):
            j = t.find(b"\n", i)
            i = n if j < 0 else j
        elif c in (b'"', b"'"):
            j = i + 1
            while j < n and t[j:j + 1] != c:
                j += 2 if t[j:j + 1] == b"\\" else 1
            out += c + c
            i = j + 1
        else:
            out += c
            i += 1
    return bytes(out)


def balance(t):
    t = code_only(t)
    return tuple(t.count(a) - t.count(b) for a, b in ((b"{", b"}"), (b"(", b")"), (b"[", b"]")))


def inserted(old, new):
    """The lines new adds to old, or None when new is not old with whole lines inserted."""
    a, b = old.splitlines(keepends=True), new.splitlines(keepends=True)
    added, i = [], 0
    for line in b:
        if i < len(a) and line == a[i]:
            i += 1
        else:
            added.append(line)
    return b"".join(added) if i == len(a) else None


def edit(s):
    for m in MARKS:
        assert m not in s, f"{REL} has this edit (or exp 0379's) already ({m.decode()} is in it)"
    hdr = ZERO_SKIP_HPP.encode("ascii")
    assert len(hdr) == HEADER_LEN and hashlib.md5(hdr).hexdigest() == HEADER_MD5, "the inlined zero_skip.hpp is not 782ca0e9's lines 13-228"
    eol = eol_of(s)
    conv = [(o.replace(b"\n", eol), n.replace(b"\n", eol), w) for o, n, w in EDITS]
    pos = []
    for old, new, what in conv:
        assert s.count(old) == 1, (what, old[:100], s.count(old))
        add = inserted(old, new)
        assert add, ("whole lines inserted, nothing changed", what)
        assert balance(add) == (0, 0, 0), ("braces, parentheses or brackets", what, balance(add))
        add.decode("ascii")
        pos.append(s.index(old))
    assert pos == sorted(pos), "the anchors are not in file order"
    # The direct path's region: every anchor but the include lies in it (namespace Direct, under KYTY_BC5_DIRECT).
    lo = s.index(b"#if defined(KYTY_BC5_DIRECT)" + eol + b"static std::unique_ptr<bc5::direct::Device> g_dev;")
    hi = s.index(b"#else" + eol + b"static void init_once() {}" + eol, lo)
    assert all(lo < p < hi for p in pos[1:]), "an anchor lies outside the direct path"
    inc_lo = s.index(b"#if defined(KYTY_BC5_DIRECT)" + eol + b'#include "bc5/direct.hpp"')
    assert inc_lo < pos[0] < s.index(b"#endif", inc_lo), "the include anchor is not in the direct path's include block"
    o = s
    for old, new, what in conv:
        o = o.replace(old, new, 1)
    # Every new text is in once; the switch is read in one place; each function's first mention is its definition.
    for _old, new, what in conv:
        assert o.count(new) == 1, ("new text", what, o.count(new))
    assert o.count(b'std::getenv("BC5_DIRECT_ZERO_SKIP")') == 2 and o.count(b"static const char* zskip_path() {") == 1
    for defn in (b"static void zcanary_check(", b"static void zcanary_watch(", b"static void zskip_release(", b"static void zskip_map(",
                 b"static bool zskip_resolve(", b"static void zskip_take_back(", b"static void zskip_report(",
                 b"static void zskip_disable(", b"static bool zskip_hint_back(", b"static bool zskip_sync_start(",
                 b"static std::vector<DView> zsk_views(", b"static DState zsk_state("):
        name = defn[defn.rindex(b" ") + 1:]
        assert o.count(defn) == 1 and o.index(name) == o.index(defn) + len(defn) - len(name), ("used before its definition", name)
    assert o.index(b"struct ZLearned {") < o.index(b"ZLearned zlearned(") and o.index(b"struct ZLearned {") < o.index(b"ZLearned guard(")
    assert o.index(b"namespace bc5::zero_skip {") < o.index(b"static bc5::zero_skip::SkipSet")
    assert eol_of(o) == eol
    # Reverting the edit gives the input back, byte for byte.
    r = o
    for old, new, what in reversed(conv):
        assert r.count(new) == 1, ("revert", what)
        r = r.replace(new, old, 1)
    assert r == s, "the edit does not revert to the input"
    assert balance(o) == balance(s)
    return o


def main():
    args = sys.argv[1:]
    assert len(args) == 2, __doc__
    root, out = args
    assert os.path.realpath(root) != os.path.realpath(out), "the out dir is the input tree: refused"
    with open(os.path.join(root, REL), "rb") as f:
        s = f.read()
    md5 = hashlib.md5(s).hexdigest()
    for m in MARKS:
        assert m not in s, f"{REL} has this edit (or exp 0379's) already ({m.decode()} is in it)"
    assert md5 == INPUTS[REL], f"{REL} is {md5}, not the pinned input {INPUTS[REL]} (re-pin INPUTS when the chain changes)"
    o = edit(s)
    p = os.path.join(out, REL)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(o)
    print(f"{REL} {hashlib.md5(o).hexdigest()}")


if __name__ == "__main__":
    main()
