// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0379: the zero list and the skip set of the second title's eager render heaps — the pure parts.
//
// The host imports every 2 MiB chunk of an eager heap (BC5_DIRECT_EAGER_NAMES), data or not, and udmabuf pins each
// page it imports (ADR 0006). With RT on that pins ~12.4 GiB and the box runs out of page cache (F505); exp 0333 found
// ~2.8 GB of the two big render heaps all-zero for 20 minutes (F402). A diagnostic run scans those heaps and writes the
// chunks that were zero in every scan (a "zero list", offsets from each heap's start); a later run skips them at
// import and maps a canary slice under them, so a GPU access never faults and a GPU write is seen (bc5LleAgc.cpp,
// BC5_DIRECT_ZERO_SKIP). This header holds the list format, the scan's intersection and the skip set, so they can be
// unit-tested; the host side (scans, imports, canary mappings) lives in the KytyPlus unit libs/bc5LleAgc.cpp.
#pragma once

#include <algorithm>
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
