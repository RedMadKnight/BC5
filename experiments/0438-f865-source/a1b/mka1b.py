# SPDX-License-Identifier: GPL-2.0-only
# BC5 exp 0438 A1b (tag a1b438), on top of A1 (mka1.py): with KYTY_BC5_0438_A1=1 the BC5 host readers stop copying
# the whole range table.
#   1. VirtualRangesMap keeps the table also as sorted immutable chunks (<= KYTY_BC5_0438_A1B_CHUNK ranges, 512)
#      behind shared pointers, rebuilt copy-on-write and only where an edit touched it (the edited keys are noted
#      at every node change; the chunks are brought up to date at the next reader, under the lock). The readers
#      Bc5ForEachMappedRange, Bc5RangesWithDirty and Bc5ForEachPrivateRegion take the chunk array's pointer under
#      the lock and walk it outside, as they walked their copy before.
#   2. A change ring (KYTY_BC5_0438_A1B_RING entries, 4096: generation -> the call's span) and a new reader
#      Bc5RangesTouchingSince(since, ...) that gives a reader with its own last generation the spans since then and
#      their touching ranges, without emptying the shared log; *complete false when `since` left the ring.
#   3. Outside the lean build (BC5_LEAN), KYTY_BC5_0438_A1J=<file> appends every mutating call of VirtualRanges with
#      its arguments and result to a binary file (72-byte records, buffered), for replay (test_a1b438 --replay).
# KYTY_BC5_0438_A1 unset or not "1": the old code exactly as A1 left it (no ring, no chunks, no journal).
#   python -I mka1b.py IN_memory_a1.cpp OUT_memory.cpp         IN must be A1's output (md5 pinned)
#   python -I mka1b.py --extract OUT_memory.cpp DIR [b1..b4]    DIR/a1b_real.h + DIR/a1b_readers.inc for the test
#   python -I mka1b.py --extract-today IN_memory_a1.cpp DIR     DIR/today_readers.inc (the readers as they are today)
import hashlib
import re
import sys

IN_MD5 = "515db92450deb37bb7082b29e0de7bf0"       # mka1.py's output from memory.cpp aa7d7f5b3fdbbe8d57bd440e7aa80922
DISP_MD5 = "e2a302ba16cce5f08bba7a344c4cbebd"     # A1's dispatcher class, replaced whole
READERS_MD5 = "b3ce1caa7927ae10ec831c3b4b9a8395"  # the reader functions in IN (unchanged from memory.cpp)

DISP_BEGIN = b"// The class the rest of memory.cpp uses: one of the two, chosen once per process from KYTY_BC5_0438_A1"
A1_END = b"// ---- end BC5 exp 0438 A1 (tag a1438) ----\n"
READERS_BEGIN = b"static std::unique_ptr<VirtualRanges>     g_virtual_ranges;\n"
READERS_END = b"static std::unique_ptr<GuestAddressSpace> g_guest_address_space;\n"


def tabs(s):
    """4-space indentation at a line's start -> tabs (memory.cpp's style); the text is written with spaces here."""
    out = []
    for line in s.split("\n"):
        m = re.match(r"^( {4})+", line)
        if m:
            n = len(m.group(0)) // 4
            line = "\t" * n + line[len(m.group(0)):]
        out.append(line)
    return "\n".join(out).encode()


CHUNKS = tabs(r'''
// ---- BC5 exp 0438 A1b (tag a1b438, mka1b.py) ------------------------------------------------------------------------
// The range table as immutable sorted chunks, for the host readers (Bc5ForEachMappedRange, Bc5RangesWithDirty,
// Bc5ForEachPrivateRegion) when KYTY_BC5_0438_A1=1: VirtualRangesMap hands out a shared pointer to the current chunk
// array and an edit builds new chunks only where it changed the table (copy on write), so a reader neither copies
// the table nor holds the lock while it walks. Chunks are never empty and a chunk boundary always lies between two
// different starts (only a run of equal starts, possible at UINT64_MAX, may make a chunk longer than the limit).
#ifndef KYTY_BC5_0438_A1B_CHUNK
#define KYTY_BC5_0438_A1B_CHUNK 512
#endif
#ifndef KYTY_BC5_0438_A1B_RING
#define KYTY_BC5_0438_A1B_RING 4096
#endif
struct VirtualRangesChunks {
    using Range = VirtualRangesVec::Range;
    using Chunk = std::vector<Range>;
    struct Pos {
        size_t c = 0; // chunk
        size_t i = 0; // range in it
    };
    std::vector<std::shared_ptr<const Chunk>> chunks;
    size_t                                    total = 0;

    [[nodiscard]] bool  IsBegin(const Pos& p) const { return p.c == 0 && p.i == 0; }
    [[nodiscard]] bool  AtEnd(const Pos& p) const { return p.c >= chunks.size(); }
    const Range&        At(const Pos& p) const { return (*chunks[p.c])[p.i]; }
    void                Next(Pos* p) const {
        if (++p->i >= chunks[p->c]->size()) {
            p->c++;
            p->i = 0;
        }
    }
    void Prev(Pos* p) const { // p is not the first range
        if (p->i > 0) {
            p->i--;
        } else {
            p->c--;
            p->i = chunks[p->c]->size() - 1;
        }
    }
    // std::upper_bound over the ranges by start: the first range starting after v (AtEnd when there is none)
    [[nodiscard]] Pos UpperBound(uint64_t v) const {
        auto c = std::upper_bound(chunks.begin(), chunks.end(), v,
                                  [](uint64_t x, const std::shared_ptr<const Chunk>& k) { return x < k->back().start; });
        if (c == chunks.end()) return {chunks.size(), 0};
        auto r = std::upper_bound((*c)->begin(), (*c)->end(), v, [](uint64_t x, const Range& k) { return x < k.start; });
        return {static_cast<size_t>(c - chunks.begin()), static_cast<size_t>(r - (*c)->begin())};
    }
};

'''.lstrip("\n"))

MAP_PUBLIC = tabs(r'''
    // ---- exp 0438 A1b (tag a1b438) ----
    // The table as immutable chunks: the ranges of Snapshot in the same order. What the pointer shows never changes;
    // an edit after the lock is released builds new chunks for the next caller.
    std::shared_ptr<const VirtualRangesChunks> Chunks() {
        Common::LockGuard lock(m_mutex);
        return ChunksUnlocked();
    }

    // SnapshotWithDirty with the chunks in place of the copy: one hold of the mutex, the same log, emptied the same way.
    void ChunksWithDirty(std::shared_ptr<const VirtualRangesChunks>* out, uint64_t* gen, std::vector<std::pair<uint64_t, uint64_t>>* spans,
                         bool* complete) {
        EXIT_IF(out == nullptr || gen == nullptr || spans == nullptr || complete == nullptr);
        Common::LockGuard lock(m_mutex);
        *out      = ChunksUnlocked();
        *gen      = m_gen.load(std::memory_order_acquire);
        *complete = m_dirty_on && !m_dirty_overflow;
        spans->clear();
        spans->swap(m_dirty);
        m_dirty_on       = true;
        m_dirty_overflow = false;
    }

    // DirtyWithTouching for a reader that keeps its own generation: the spans of the calls after generation `since` up
    // to now, from the change ring, and per span the ranges that overlap or touch it now. Nothing is emptied, so
    // readers do not take each other's spans. *complete false (spans and touching empty): `since` is 0, ahead of now,
    // or more than KYTY_BC5_0438_A1B_RING calls back.
    void TouchingSince(uint64_t since, uint64_t* gen, std::vector<std::pair<uint64_t, uint64_t>>* spans,
                       std::vector<std::vector<Range>>* touching, bool* complete) {
        EXIT_IF(gen == nullptr || spans == nullptr || touching == nullptr || complete == nullptr);
        Common::LockGuard lock(m_mutex);
        *gen = m_gen.load(std::memory_order_acquire);
        spans->clear();
        touching->clear();
        *complete = A1bRingSpansUnlocked(since, *gen, spans);
        if (!*complete) return;
        touching->reserve(spans->size());
        for (const auto& [start, size]: *spans) {
            const auto [a, b] = TouchingUnlocked(start, End(start, size));
            auto& v           = touching->emplace_back();
            for (auto it = a; it != b; ++it) v.push_back(it->second);
        }
    }

'''.lstrip("\n"))

MAP_PRIVATE = tabs(r'''
    // ---- exp 0438 A1b (tag a1b438): chunk upkeep and the change ring, all under m_mutex ----
    // A node with this start was inserted, erased or changed in the current call (one key interval per generation).
    void A1bKey(uint64_t key) {
        if (m_ck_full) return;
        const uint64_t g = m_gen.load(std::memory_order_relaxed);
        if (!m_ck_dirty.empty() && m_ck_dirty_gen == g) {
            auto& d  = m_ck_dirty.back();
            d.first  = std::min(d.first, key);
            d.second = std::max(d.second, key);
            return;
        }
        if (m_ck_dirty.size() >= 4096) { // no reader for a long time: rebuild everything at the next one
            m_ck_full = true;
            m_ck_dirty.clear();
            return;
        }
        m_ck_dirty.emplace_back(key, key);
        m_ck_dirty_gen = g;
    }

    // [from, to) of the map cut into chunks of at most KYTY_BC5_0438_A1B_CHUNK ranges, of even length, never
    // between two equal starts; appended to t.
    static void A1bSlice(Map::const_iterator from, Map::const_iterator to, VirtualRangesChunks* t) {
        const auto m = static_cast<size_t>(std::distance(from, to));
        if (m == 0) return;
        const size_t k      = (m + KYTY_BC5_0438_A1B_CHUNK - 1) / KYTY_BC5_0438_A1B_CHUNK;
        const size_t target = (m + k - 1) / k;
        auto         cur    = std::make_shared<VirtualRangesChunks::Chunk>();
        cur->reserve(target);
        for (auto it = from; it != to; ++it) {
            if (cur->size() >= target && it->first != cur->back().start) {
                t->chunks.push_back(std::move(cur));
                cur = std::make_shared<VirtualRangesChunks::Chunk>();
                cur->reserve(target);
            }
            cur->push_back(it->second);
        }
        t->chunks.push_back(std::move(cur));
    }

    // The chunks as the map is now. Unchanged chunks are shared with the previous array; a chunk that holds a noted
    // key (or would, for a new key) is rebuilt with its run of neighbours from the map.
    const std::shared_ptr<const VirtualRangesChunks>& ChunksUnlocked() {
        if (m_ck != nullptr && !m_ck_full && m_ck_dirty.empty()) return m_ck;
        auto t = std::make_shared<VirtualRangesChunks>();
        if (m_ck == nullptr || m_ck_full || m_ck->chunks.empty()) {
            A1bSlice(m_ranges.cbegin(), m_ranges.cend(), t.get());
        } else {
            const auto&  old = m_ck->chunks;
            const size_t n   = old.size();
            // the chunk a key belongs to: the last one whose first start is <= key (the first chunk for a smaller key)
            auto chunk_of = [&](uint64_t key) -> size_t {
                auto it = std::upper_bound(old.begin(), old.end(), key,
                                           [](uint64_t v, const std::shared_ptr<const VirtualRangesChunks::Chunk>& c) { return v < c->front().start; });
                return it == old.begin() ? 0 : static_cast<size_t>(it - old.begin()) - 1;
            };
            std::vector<std::pair<size_t, size_t>> runs; // [a, b], chunk indices
            runs.reserve(m_ck_dirty.size());
            for (const auto& [lo, hi]: m_ck_dirty) runs.emplace_back(chunk_of(lo), chunk_of(hi));
            std::sort(runs.begin(), runs.end());
            std::vector<std::pair<size_t, size_t>> fin;
            for (auto r: runs) {
                while (!fin.empty() && r.first <= fin.back().second + 1) {
                    r = {fin.back().first, std::max(fin.back().second, r.second)};
                    fin.pop_back();
                }
                size_t count = 0;
                for (size_t i = r.first; i <= r.second; i++) count += old[i]->size();
                if (count < KYTY_BC5_0438_A1B_CHUNK / 2) { // a small run takes a neighbour, so chunks do not crumble
                    if (r.second + 1 < n) {
                        r.second++;
                    } else if (r.first > 0) {
                        r.first--;
                    }
                }
                while (!fin.empty() && r.first <= fin.back().second + 1) {
                    r = {fin.back().first, std::max(fin.back().second, r.second)};
                    fin.pop_back();
                }
                fin.push_back(r);
            }
            size_t next = 0;
            for (const auto& [a, b]: fin) {
                for (; next < a; next++) t->chunks.push_back(old[next]);
                const auto from = a == 0 ? m_ranges.cbegin() : m_ranges.lower_bound(old[a]->front().start);
                const auto to   = b + 1 >= n ? m_ranges.cend() : m_ranges.lower_bound(old[b + 1]->front().start); // a1b-b4
                A1bSlice(from, to, t.get());
                next = b + 1;
            }
            for (; next < n; next++) t->chunks.push_back(old[next]);
        }
        for (const auto& c: t->chunks) t->total += c->size();
        m_ck      = std::move(t);
        m_ck_full = false;
        m_ck_dirty.clear();
        return m_ck;
    }

    // Every mutator's call, from NoteDirtyUnlocked (right after its generation bump): that generation and its span.
    struct A1bRingEntry {
        uint64_t gen   = 0;
        uint64_t start = 0;
        uint64_t size  = 0;
    };
    void A1bRingPushUnlocked(uint64_t start, uint64_t size) {
        const uint64_t g = m_gen.load(std::memory_order_relaxed);
        m_ring[g % KYTY_BC5_0438_A1B_RING] = {g, start, size}; // a1b-b2
    }
    bool A1bRingSpansUnlocked(uint64_t since, uint64_t now, std::vector<std::pair<uint64_t, uint64_t>>* out) {
        if (since == 0 || since > now || now - since > KYTY_BC5_0438_A1B_RING) return false;
        out->reserve(now - since);
        for (uint64_t g = since + 1; g <= now; g++) {
            const auto& e = m_ring[g % KYTY_BC5_0438_A1B_RING];
            if (e.gen != g) { // not this call's entry: a gap (never expected; the reader takes the full path)
                out->clear();
                return false;
            }
            out->emplace_back(e.start, e.size);
        }
        return true;
    }

    std::shared_ptr<const VirtualRangesChunks>          m_ck;               // the current chunks (null: never built)
    std::vector<std::pair<uint64_t, uint64_t>>          m_ck_dirty;         // key intervals edited since they were built
    uint64_t                                            m_ck_dirty_gen = 0; // the generation of m_ck_dirty.back()
    bool                                                m_ck_full      = false;
    std::array<A1bRingEntry, KYTY_BC5_0438_A1B_RING>    m_ring {};
'''.lstrip("\n"))

JOURNAL_AND_DISPATCHER = tabs(r'''
#if !defined(BC5_LEAN)
// exp 0438 A1b (tag a1b438): KYTY_BC5_0438_A1J=<file>, records only (never read back by the emulator): every mutating
// call of VirtualRanges with its arguments and its result, in the order the calls changed the table, so that a real
// run's sequence can be replayed (test_a1b438 --replay). File: "BC5A1J01", uint32 record size (72), uint32 0, then
// one Rec per call, little endian. Buffered: written every 1,024 records and when VirtualRanges is destroyed (a
// crash loses at most the last 1,023). Only with KYTY_BC5_0438_A1=1; compiled out in the lean build.
class VirtualRangesJournal {
public:
    enum Op : uint8_t { kAdd = 1, kRemove, kReleaseReserved, kConsumeReserved, kConsumeReservedSpan, kRename, kProtect, kSetMemoryType };
    struct Rec {
        uint8_t  op;
        uint8_t  type;   // VirtualRangeType (Add, ConsumeReserved, ConsumeReservedSpan; else 0)
        uint8_t  flags;  // 1 disallow_merge, 2 name was null (Add, Rename), 4 first_range was given
        uint8_t  result; // 0 false, 1 true, 2 void
        int32_t  protection;
        int32_t  memory_type;
        uint32_t reserved;
        uint64_t start;
        uint64_t size;
        uint64_t offset;
        char     name[32]; // the first 31 characters, as CopyVirtualRangeName keeps them
    };
    static_assert(sizeof(Rec) == 72, "journal record layout");
    static_assert(KERNEL_MAXIMUM_NAME_LENGTH <= 32, "a journal name holds every character a range keeps");
    static constexpr uint32_t kBuffered = 1024;

    static std::unique_ptr<VirtualRangesJournal> Open(const char* path) {
        FILE* f = std::fopen(path, "wb");
        std::fprintf(stderr, "[bc5] exp 0438 A1b journal %s: %s (tag a1b438)\n", f != nullptr ? "on" : "FAILED to open", path);
        if (f == nullptr) return nullptr;
        const uint32_t h[2] = {static_cast<uint32_t>(sizeof(Rec)), 0};
        std::fwrite("BC5A1J01", 1, 8, f);
        std::fwrite(h, sizeof(h), 1, f);
        return std::unique_ptr<VirtualRangesJournal>(new VirtualRangesJournal(f));
    }
    VirtualRangesJournal(const VirtualRangesJournal&)            = delete;
    VirtualRangesJournal& operator=(const VirtualRangesJournal&) = delete;
    ~VirtualRangesJournal() {
        Flush();
        std::fclose(m_f);
    }

    void Write(Op op, uint64_t start, uint64_t size, uint64_t offset, int protection, int memory_type, VirtualRangeType type,
               const char* name, bool has_name, bool disallow_merge, bool first_range, int result) {
        Rec r {};
        r.op          = op;
        r.type        = static_cast<uint8_t>(type);
        r.flags       = static_cast<uint8_t>((disallow_merge ? 1 : 0) | (has_name && name == nullptr ? 2 : 0) | (first_range ? 4 : 0));
        r.result      = static_cast<uint8_t>(result);
        r.protection  = protection;
        r.memory_type = memory_type;
        r.start       = start;
        r.size        = size;
        r.offset      = offset;
        if (has_name && name != nullptr) std::strncpy(r.name, name, sizeof(r.name) - 1);
        m_buf.push_back(r);
        if (m_buf.size() >= kBuffered) Flush();
    }
    void Flush() {
        if (!m_buf.empty()) std::fwrite(m_buf.data(), sizeof(Rec), m_buf.size(), m_f);
        m_buf.clear();
        std::fflush(m_f);
    }

    std::mutex mutex; // held across a journaled call and its record, so the file has the table's order

private:
    explicit VirtualRangesJournal(FILE* f): m_f(f) { m_buf.reserve(kBuffered); }
    FILE*            m_f;
    std::vector<Rec> m_buf;
};
#endif

// The class the rest of memory.cpp uses: one of the two, chosen once per process from KYTY_BC5_0438_A1 ("1" = map).
// exp 0438 A1b (tag a1b438): with the map, also Chunks/ChunksWithDirty/TouchingSince for the readers below, and the
// journal of KYTY_BC5_0438_A1J (map only, not in the lean build). The vector mode is A1's, call for call.
class VirtualRanges {
public:
    using Range = VirtualRangesVec::Range;

    VirtualRanges(): VirtualRanges(A1bJournalPath()) {}
    explicit VirtualRanges(const char* journal_path): m_a1(A1On()) {
        if (m_a1) {
            m_map = std::make_unique<VirtualRangesMap>();
        } else {
            m_vec = std::make_unique<VirtualRangesVec>();
        }
#if !defined(BC5_LEAN)
        if (m_a1 && journal_path != nullptr && journal_path[0] != 0) m_journal = VirtualRangesJournal::Open(journal_path);
#else
        (void)journal_path;
#endif
    }

    static bool A1On() {
        static const bool on = [] {
            const char* e  = std::getenv("KYTY_BC5_0438_A1");
            const bool  v  = e != nullptr && std::strcmp(e, "1") == 0;
            std::fprintf(stderr, "[bc5] exp 0438 A1 ranges map: %s (tag a1438)\n", v ? "on" : "off");
            return v;
        }();
        return on;
    }
    // KYTY_BC5_0438_A1J, read once; null in the lean build
    static const char* A1bJournalPath() {
#if !defined(BC5_LEAN)
        static const char* p = BC5_DIAG_ENV("KYTY_BC5_0438_A1J");
        return p;
#else
        return nullptr;
#endif
    }

    [[nodiscard]] bool A1() const { return m_a1; }
    // exp 0438 A1b: the map's chunk readers (only when A1() is true)
    std::shared_ptr<const VirtualRangesChunks> Chunks() {
        EXIT_IF(!m_a1);
        return m_map->Chunks();
    }
    void ChunksWithDirty(std::shared_ptr<const VirtualRangesChunks>* out, uint64_t* gen, std::vector<std::pair<uint64_t, uint64_t>>* spans,
                         bool* complete) {
        EXIT_IF(!m_a1);
        m_map->ChunksWithDirty(out, gen, spans, complete);
    }
    void TouchingSince(uint64_t since, uint64_t* gen, std::vector<std::pair<uint64_t, uint64_t>>* spans,
                       std::vector<std::vector<Range>>* touching, bool* complete) {
        EXIT_IF(!m_a1);
        m_map->TouchingSince(since, gen, spans, touching, complete);
    }

    [[nodiscard]] uint64_t Generation() const { return m_a1 ? m_map->Generation() : m_vec->Generation(); }
    void Overlapping(uint64_t lo, uint64_t hi, std::vector<std::pair<uint64_t, uint64_t>>* out) {
        m_a1 ? m_map->Overlapping(lo, hi, out) : m_vec->Overlapping(lo, hi, out);
    }
    bool Add(uint64_t start, uint64_t size, uint64_t offset, int protection, int memory_type, VirtualRangeType type,
             const char* name, bool disallow_merge = false) {
#if !defined(BC5_LEAN)
        if (m_journal != nullptr) {
            std::lock_guard<std::mutex> jl(m_journal->mutex);
            const bool r = m_map->Add(start, size, offset, protection, memory_type, type, name, disallow_merge);
            m_journal->Write(VirtualRangesJournal::kAdd, start, size, offset, protection, memory_type, type, name, true, disallow_merge, false, r ? 1 : 0);
            return r;
        }
#endif
        return m_a1 ? m_map->Add(start, size, offset, protection, memory_type, type, name, disallow_merge)
                    : m_vec->Add(start, size, offset, protection, memory_type, type, name, disallow_merge);
    }
    bool Remove(uint64_t start, uint64_t size) {
#if !defined(BC5_LEAN)
        if (m_journal != nullptr) {
            std::lock_guard<std::mutex> jl(m_journal->mutex);
            const bool r = m_map->Remove(start, size);
            m_journal->Write(VirtualRangesJournal::kRemove, start, size, 0, 0, 0, VirtualRangeType::Reserved, nullptr, false, false, false, r ? 1 : 0);
            return r;
        }
#endif
        return m_a1 ? m_map->Remove(start, size) : m_vec->Remove(start, size);
    }
    bool HasOverlap(uint64_t start, uint64_t size) { return m_a1 ? m_map->HasOverlap(start, size) : m_vec->HasOverlap(start, size); }
    bool QueryOverlap(uint64_t start, uint64_t size, Range* out) {
        return m_a1 ? m_map->QueryOverlap(start, size, out) : m_vec->QueryOverlap(start, size, out);
    }
    bool ReleaseReserved(uint64_t start, uint64_t size) {
#if !defined(BC5_LEAN)
        if (m_journal != nullptr) {
            std::lock_guard<std::mutex> jl(m_journal->mutex);
            const bool r = m_map->ReleaseReserved(start, size);
            m_journal->Write(VirtualRangesJournal::kReleaseReserved, start, size, 0, 0, 0, VirtualRangeType::Reserved, nullptr, false, false, false, r ? 1 : 0);
            return r;
        }
#endif
        return m_a1 ? m_map->ReleaseReserved(start, size) : m_vec->ReleaseReserved(start, size);
    }
    bool ConsumeReserved(uint64_t start, uint64_t size, VirtualRangeType type = VirtualRangeType::Reserved) {
#if !defined(BC5_LEAN)
        if (m_journal != nullptr) {
            std::lock_guard<std::mutex> jl(m_journal->mutex);
            const bool r = m_map->ConsumeReserved(start, size, type);
            m_journal->Write(VirtualRangesJournal::kConsumeReserved, start, size, 0, 0, 0, type, nullptr, false, false, false, r ? 1 : 0);
            return r;
        }
#endif
        return m_a1 ? m_map->ConsumeReserved(start, size, type) : m_vec->ConsumeReserved(start, size, type);
    }
    bool ConsumeReservedSpan(uint64_t start, uint64_t size, Range* first_range = nullptr,
                             VirtualRangeType type = VirtualRangeType::Reserved) {
#if !defined(BC5_LEAN)
        if (m_journal != nullptr) {
            std::lock_guard<std::mutex> jl(m_journal->mutex);
            const bool r = m_map->ConsumeReservedSpan(start, size, first_range, type);
            m_journal->Write(VirtualRangesJournal::kConsumeReservedSpan, start, size, 0, 0, 0, type, nullptr, false, false, first_range != nullptr,
                             r ? 1 : 0);
            return r;
        }
#endif
        return m_a1 ? m_map->ConsumeReservedSpan(start, size, first_range, type)
                    : m_vec->ConsumeReservedSpan(start, size, first_range, type);
    }
    void Rename(uint64_t start, uint64_t size, const char* name) {
#if !defined(BC5_LEAN)
        if (m_journal != nullptr) {
            std::lock_guard<std::mutex> jl(m_journal->mutex);
            m_map->Rename(start, size, name);
            m_journal->Write(VirtualRangesJournal::kRename, start, size, 0, 0, 0, VirtualRangeType::Reserved, name, true, false, false, 2);
            return;
        }
#endif
        m_a1 ? m_map->Rename(start, size, name) : m_vec->Rename(start, size, name);
    }
    void Protect(uint64_t start, uint64_t size, int protection) {
#if !defined(BC5_LEAN)
        if (m_journal != nullptr) {
            std::lock_guard<std::mutex> jl(m_journal->mutex);
            m_map->Protect(start, size, protection);
            m_journal->Write(VirtualRangesJournal::kProtect, start, size, 0, protection, 0, VirtualRangeType::Reserved, nullptr, false, false, false, 2); // a1b-b3
            return;
        }
#endif
        m_a1 ? m_map->Protect(start, size, protection) : m_vec->Protect(start, size, protection);
    }
    void SetMemoryType(uint64_t start, uint64_t size, int memory_type) {
#if !defined(BC5_LEAN)
        if (m_journal != nullptr) {
            std::lock_guard<std::mutex> jl(m_journal->mutex);
            m_map->SetMemoryType(start, size, memory_type);
            m_journal->Write(VirtualRangesJournal::kSetMemoryType, start, size, 0, 0, memory_type, VirtualRangeType::Reserved, nullptr, false, false, false, 2);
            return;
        }
#endif
        m_a1 ? m_map->SetMemoryType(start, size, memory_type) : m_vec->SetMemoryType(start, size, memory_type);
    }
    bool Query(uint64_t addr, int flags, Range* out) { return m_a1 ? m_map->Query(addr, flags, out) : m_vec->Query(addr, flags, out); }
    void Snapshot(std::vector<Range>* out) { m_a1 ? m_map->Snapshot(out) : m_vec->Snapshot(out); }
    void SnapshotWithDirty(std::vector<Range>* out, uint64_t* gen, std::vector<std::pair<uint64_t, uint64_t>>* spans, bool* complete) {
        m_a1 ? m_map->SnapshotWithDirty(out, gen, spans, complete) : m_vec->SnapshotWithDirty(out, gen, spans, complete);
    }
    bool QuerySpan(uint64_t start, uint64_t size, std::vector<Range>* out) {
        return m_a1 ? m_map->QuerySpan(start, size, out) : m_vec->QuerySpan(start, size, out);
    }
    uint64_t ClampRangeSize(uint64_t virtual_addr, uint64_t size) {
        return m_a1 ? m_map->ClampRangeSize(virtual_addr, size) : m_vec->ClampRangeSize(virtual_addr, size);
    }
    uint64_t CountPageTableEntries(bool gpu) { return m_a1 ? m_map->CountPageTableEntries(gpu) : m_vec->CountPageTableEntries(gpu); }
    void DirtyWithTouching(uint64_t* gen, std::vector<std::pair<uint64_t, uint64_t>>* spans, std::vector<std::vector<Range>>* touching, bool* complete) {
        m_a1 ? m_map->DirtyWithTouching(gen, spans, touching, complete) : m_vec->DirtyWithTouching(gen, spans, touching, complete);
    }

private:
    const bool                        m_a1;
    std::unique_ptr<VirtualRangesVec> m_vec;
    std::unique_ptr<VirtualRangesMap> m_map;
#if !defined(BC5_LEAN)
    std::unique_ptr<VirtualRangesJournal> m_journal; // KYTY_BC5_0438_A1J
#endif
};
'''.lstrip("\n"))

MAPPED_TYPE = tabs(r'''
// exp 0438 A1b (tag a1b438): the type code of the readers' switch below (-1: reserved, not reported).
static int A1bMappedType(VirtualRangeType t) {
    switch (t) {
        case VirtualRangeType::Direct: return 0;
        case VirtualRangeType::Flexible: return 1;
        case VirtualRangeType::Pooled: return 2;
        case VirtualRangeType::Stack: return 3;
        case VirtualRangeType::Code: return 4;
        case VirtualRangeType::Runtime: return 5;
        default: return -1;
    }
}

'''.lstrip("\n"))

FOREACH_A1B = tabs(r'''
    if (g_virtual_ranges->A1()) { // exp 0438 A1b (tag a1b438): the shared immutable chunks, walked outside the lock
        const auto table = g_virtual_ranges->Chunks();
        for (const auto& chunk: table->chunks) {
            for (const auto& r: *chunk) {
                const int type = A1bMappedType(r.type);
                if (type >= 0) {
                    if (cb != nullptr) cb(r.start, r.size, type, r.protection, r.name, ctx);
                    if (cb2 != nullptr) cb2(r.start, r.size, r.offset, type, r.protection, r.name, ctx);
                }
            }
        }
        return;
    }
'''.lstrip("\n"))

WITHDIRTY_A1B = tabs(r'''
    if (g_virtual_ranges->A1()) { // exp 0438 A1b (tag a1b438): the chunks in place of the copy, the same log
        std::shared_ptr<const VirtualRangesChunks> table;
        g_virtual_ranges->ChunksWithDirty(&table, gen, spans, complete);
        for (const auto& chunk: table->chunks) {
            for (const auto& r: *chunk) {
                const int type = A1bMappedType(r.type);
                if (type >= 0) cb(r.start, r.size, r.offset, type, r.protection, r.name, ctx);
            }
        }
        return true;
    }
'''.lstrip("\n"))

TOUCHING_SINCE = tabs(r'''
// exp 0438 A1b (tag a1b438): Bc5RangesDirtyTouching for a reader that keeps its own generation: `since` is the *gen
// its last call gave. Nothing is emptied, so such readers do not take each other's spans (or Bc5RangesDirtyTouching's).
// *complete false (spans empty, no callback): `since` is unknown to the change ring (0, ahead of now, or more than
// KYTY_BC5_0438_A1B_RING calls back) or KYTY_BC5_0438_A1 is off; the reader then takes the full path
// (Bc5ForEachMappedRange). Not declared in memory.h yet: it has no caller.
bool Bc5RangesTouchingSince(uint64_t since, void (*cb)(size_t, uint64_t, uint64_t, uint64_t, int, int, const char*, void*), void* ctx,
                            uint64_t* gen, std::vector<std::pair<uint64_t, uint64_t>>* spans, bool* complete) {
    if (g_virtual_ranges == nullptr || cb == nullptr || gen == nullptr || spans == nullptr || complete == nullptr) {
        return false;
    }
    if (!g_virtual_ranges->A1()) {
        *gen = g_virtual_ranges->Generation();
        spans->clear();
        *complete = false;
        return true;
    }
    std::vector<std::vector<VirtualRanges::Range>> touching;
    g_virtual_ranges->TouchingSince(since, gen, spans, &touching, complete);
    for (size_t i = 0; i < touching.size(); i++) {
        for (const auto& r: touching[i]) {
            const int type = A1bMappedType(r.type);
            if (type >= 0) cb(i, r.start, r.size, r.offset, type, r.protection, r.name, ctx);
        }
    }
    return true;
}
'''.lstrip("\n"))

PRIVATE_A1B = tabs(r'''
    if (g_virtual_ranges != nullptr && g_virtual_ranges->A1()) { // exp 0438 A1b (tag a1b438): the same search on the chunks
        const auto t = g_virtual_ranges->Chunks();
        for (const auto& [start, size]: regions) {
            int         type = -1;
            const char* name = "";
            auto        p    = t->UpperBound(start);
            if (!t->IsBegin(p)) {
                t->Prev(&p);
            }
            for (; !t->AtEnd(p) && t->At(p).start <= start; t->Next(&p)) {
                const auto& r = t->At(p);
                if (start >= r.start && start < r.start + r.size) {
                    type = A1bMappedType(r.type);
                    name = r.name;
                    break;
                }
            }
            cb(start, size, type, name != nullptr ? name : "", ctx);
        }
        return;
    }
'''.lstrip("\n"))

T = "\t"
EDITS = [
    # (what, old, new) each old must occur exactly once in the file
    ("chunks struct", b"class VirtualRangesMap {\npublic:\n\tusing Range = VirtualRangesVec::Range;\n",
     CHUNKS + b"class VirtualRangesMap {\npublic:\n\tusing Range = VirtualRangesVec::Range;\n"),
    ("map ring push", b"\t}\n\n\tvoid NoteDirtyUnlocked(uint64_t start, uint64_t size) {\n\t\tif (!m_dirty_on) return;\n",
     b"\t}\n\n\tvoid NoteDirtyUnlocked(uint64_t start, uint64_t size) {\n"
     b"\t\tA1bRingPushUnlocked(start, size); // exp 0438 A1b: every call, ahead of the log's own checks\n\t\tif (!m_dirty_on) return;\n"),
    ("map Add key", b"\t\tMergeAroundUnlocked(m_ranges.emplace_hint(position, start, r));\n",
     b"\t\tA1bKey(start);\n\t\tMergeAroundUnlocked(m_ranges.emplace_hint(position, start, r));\n"),
    ("map Remove key",
     b"\t\tif (position != m_ranges.end() && position->second.start == start && position->second.size == size) {\n\t\t\tm_ranges.erase(position);\n",
     b"\t\tif (position != m_ranges.end() && position->second.start == start && position->second.size == size) {\n\t\t\tA1bKey(start);\n\t\t\tm_ranges.erase(position);\n"),
    ("map ReleaseReserved key", b"\t\t\t\tm_ranges.erase(it);\n\t\t\t\tbreak;\n",
     b"\t\t\t\tA1bKey(start);\n\t\t\t\tm_ranges.erase(it);\n\t\t\t\tbreak;\n"),
    ("map Rename key", b"\t\t\tCopyVirtualRangeName(position->second.name, name);\n\t\t\tMergeAroundUnlocked(position);\n",
     b"\t\t\tA1bKey(start); // a1b-b1\n\t\t\tCopyVirtualRangeName(position->second.name, name);\n\t\t\tMergeAroundUnlocked(position);\n"),
    ("map merge left key", b"\t\t\t\tprevious->second.size += it->second.size;\n\t\t\t\tm_ranges.erase(it);\n",
     b"\t\t\t\tA1bKey(previous->first);\n\t\t\t\tA1bKey(it->first);\n\t\t\t\tprevious->second.size += it->second.size;\n\t\t\t\tm_ranges.erase(it);\n"),
    ("map merge right key", b"\t\t\tit->second.size += next->second.size;\n\t\t\tm_ranges.erase(next);\n",
     b"\t\t\tA1bKey(it->first);\n\t\t\tA1bKey(next->first);\n\t\t\tit->second.size += next->second.size;\n\t\t\tm_ranges.erase(next);\n"),
    ("map edit split keys",
     b"\t\t\tconst auto next_it = std::next(it);\n\t\t\tif (has_left) {\n\t\t\t\tit->second = left; // the node shrinks to the left piece\n",
     b"\t\t\tconst auto next_it = std::next(it);\n\t\t\tA1bKey(r.start);\n\t\t\tA1bKey(mid.start);\n\t\t\tif (has_right) A1bKey(right.start);\n"
     b"\t\t\tif (has_left) {\n\t\t\t\tit->second = left; // the node shrinks to the left piece\n"),
    ("map edit merge keys", b"\t\t\t\tcur->second.size += next->second.size;\n",
     b"\t\t\t\tA1bKey(cur->first);\n\t\t\t\tA1bKey(next->first);\n\t\t\t\tcur->second.size += next->second.size;\n"),
    ("map remove split keys",
     b"\t\t\tconst auto  next_it   = std::next(it);\n\t\t\tif (has_left) {\n\t\t\t\tit->second = left;\n\t\t\t} else {\n",
     b"\t\t\tconst auto  next_it   = std::next(it);\n\t\t\tA1bKey(r.start);\n\t\t\tif (has_right) A1bKey(right.start);\n"
     b"\t\t\tif (has_left) {\n\t\t\t\tit->second = left;\n\t\t\t} else {\n"),
    ("map public", b"private:\n\tusing Map = std::multimap<uint64_t, Range>; // a multimap: see the note at the class head\n",
     MAP_PUBLIC + b"private:\n\tusing Map = std::multimap<uint64_t, Range>; // a multimap: see the note at the class head\n"),
    ("map private", b"\tMap                                        m_ranges;\n\tstd::vector<Range>                         m_sorted;         // SortedUnlocked's cache\n",
     MAP_PRIVATE + b"\n\tMap                                        m_ranges;\n\tstd::vector<Range>                         m_sorted;         // SortedUnlocked's cache\n"),
    ("type helper", b"// BC5: enumerates the guest's mapped (non-reserved) ranges: start, size, type (0 direct,\n",
     MAPPED_TYPE + b"// BC5: enumerates the guest's mapped (non-reserved) ranges: start, size, type (0 direct,\n"),
    ("ForEachMappedRange", b"\tif (g_virtual_ranges == nullptr || (cb == nullptr && cb2 == nullptr)) {\n\t\treturn;\n\t}\n",
     b"\tif (g_virtual_ranges == nullptr || (cb == nullptr && cb2 == nullptr)) {\n\t\treturn;\n\t}\n" + FOREACH_A1B),
    ("RangesWithDirty", b"\tstd::vector<VirtualRanges::Range> ranges;\n\tg_virtual_ranges->SnapshotWithDirty(&ranges, gen, spans, complete);\n",
     WITHDIRTY_A1B + b"\tstd::vector<VirtualRanges::Range> ranges;\n\tg_virtual_ranges->SnapshotWithDirty(&ranges, gen, spans, complete);\n"),
    ("TouchingSince", b"// BC5 (experiment 0415, tag mr415): Bc5ForEachMappedRange's callback over one snapshot",
     TOUCHING_SINCE + b"// BC5 (experiment 0415, tag mr415): Bc5ForEachMappedRange's callback over one snapshot"),
    ("ForEachPrivateRegion", b"\tstd::vector<VirtualRanges::Range> ranges;\n\tif (g_virtual_ranges != nullptr) {\n\t\tg_virtual_ranges->Snapshot(&ranges);\n\t}\n",
     PRIVATE_A1B + b"\tstd::vector<VirtualRanges::Range> ranges;\n\tif (g_virtual_ranges != nullptr) {\n\t\tg_virtual_ranges->Snapshot(&ranges);\n\t}\n"),
]

# Planted bugs for the test.
MUTANTS = {
    "b1": (b"\t\t\tA1bKey(start); // a1b-b1\n", b""),  # an in-place rename does not mark its chunk: the chunk is not replaced
    "b2": (b"\t\tm_ring[g % KYTY_BC5_0438_A1B_RING] = {g, start, size}; // a1b-b2\n",
           b"\t\tif (size != 0) m_ring[g % KYTY_BC5_0438_A1B_RING] = {g, start, size};\n"),  # a ring entry skipped
    "b3": (b"\t\t\tm_journal->Write(VirtualRangesJournal::kProtect, start, size, 0, protection, 0, VirtualRangeType::Reserved, nullptr, false, false, false, 2); // a1b-b3\n",
           b""),  # Protect calls missing from the journal file
    "b4": (b"m_ranges.lower_bound(old[b + 1]->front().start); // a1b-b4\n",
           b"m_ranges.upper_bound(old[b + 1]->front().start);\n"),  # a rebuilt run also takes the next chunk's first range
}


def md5(b):
    return hashlib.md5(b).hexdigest()


def once(data, old, new, what):
    n = data.count(old)
    assert n == 1, f"{what}: {n} matches, want 1"
    return data.replace(old, new)


def segment(data, begin, end, what):
    assert data.count(begin) == 1 and data.count(end) == 1, f"{what}: markers"
    i = data.find(begin)
    j = data.find(end, i)
    assert j > i, f"{what}: order"
    return i, j


def apply(src, dst):
    data = open(src, "rb").read()
    assert md5(data) == IN_MD5, f"input md5 {md5(data)}, pinned {IN_MD5} (A1's output)"
    assert b"\r\n" not in data
    i, j = segment(data, DISP_BEGIN, A1_END, "dispatcher")
    assert md5(data[i:j]) == DISP_MD5, "dispatcher text changed"
    data = data[:i] + JOURNAL_AND_DISPATCHER + data[j:]
    for what, old, new in EDITS:
        data = once(data, old, new, what)
    assert b"\r\n" not in data
    open(dst, "wb").write(data)
    print(f"in  md5 {IN_MD5}\nout md5 {md5(data)}\nreplacements {len(EDITS) + 1}, each exactly once")


def cut(data, begin, end, what, include_end=False):
    i, j = segment(data, begin, end, what)
    return data[i:j + (len(end) if include_end else 0)]


def readers(data):
    i, j = segment(data, READERS_BEGIN, READERS_END, "readers")
    return data[i + len(READERS_BEGIN):j]


def extract(src, outdir, mutant=None):
    data = open(src, "rb").read()
    consts = cut(data, b"constexpr int PROT_CPU_READ", b"constexpr uint64_t DEFAULT_FLEXIBLE_MEMORY_SIZE", "constants")
    helpers = cut(data, b"static void CopyVirtualRangeName", b"#if defined(KYTY_VIRTUAL_MEMORY_ALLOCATION_TESTS)\nstatic uint32_t g_test_backing_store", "helpers")
    classes = cut(data, b"enum class VirtualRangeType {", A1_END, "classes", True)
    rd = readers(data)
    if mutant:
        old, new = MUTANTS[mutant]
        if classes.count(old) == 1:
            classes = classes.replace(old, new)
        else:
            rd = once(rd, old, new, f"mutant {mutant}")
    tag = md5(data).encode() + (b" mutant " + mutant.encode() if mutant else b"")
    hdr = (b"// generated by mka1b.py --extract from " + tag + b"\n#pragma once\n#include \"stub_a1b.h\"\nnamespace Libs::LibKernel::Memory {\n" +
           consts + helpers + classes + b"} // namespace Libs::LibKernel::Memory\n")
    inc = b"// generated by mka1b.py --extract from " + tag + b": the reader functions, for test_a1b438.cpp\n" + rd
    open(outdir + "/a1b_real.h", "wb").write(hdr)
    open(outdir + "/a1b_readers.inc", "wb").write(inc)
    print(f"extract {outdir} from {md5(data)}{' mutant ' + mutant if mutant else ''}: a1b_real.h {md5(hdr)}, a1b_readers.inc {md5(inc)}")


def extract_today(src, outdir):
    data = open(src, "rb").read()
    assert md5(data) == IN_MD5, f"input md5 {md5(data)}, pinned {IN_MD5}"
    rd = readers(data)
    assert md5(READERS_BEGIN + rd) == READERS_MD5, "today's readers changed"
    inc = b"// generated by mka1b.py --extract-today from " + md5(data).encode() + b": today's reader functions\n" + rd
    open(outdir + "/today_readers.inc", "wb").write(inc)
    print(f"extract-today {outdir}: today_readers.inc {md5(inc)}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--extract":
        assert len(a) in (3, 4), "usage: mka1b.py --extract OUT_memory.cpp DIR [b1|b2|b3|b4]"
        extract(a[1], a[2], a[3] if len(a) == 4 else None)
    elif a and a[0] == "--extract-today":
        assert len(a) == 3, "usage: mka1b.py --extract-today IN_memory_a1.cpp DIR"
        extract_today(a[1], a[2])
    else:
        assert len(a) == 2, "usage: mka1b.py IN_memory_a1.cpp OUT_memory.cpp"
        apply(a[0], a[1])
