// SPDX-License-Identifier: GPL-2.0
// BC5 experiment 0438 (tag a2): the device's sorted mapping list as an immutable chunked index.
// Device::sorted_mappings() used to copy and merge every mapping (~17,000) into a new vector at each change of the
// list; in the second title's mapping storms the list changed ~900 times a second (exp 0438 result 19). A
// MappingIndex is a sorted sequence of Mappings held in chunks of at most kChunkMax entries behind a small array of
// shared, immutable chunks. index_insert / index_erase return a new index that shares every chunk but the one edited
// (one chunk copy, ~24 KiB, and the top array of shared_ptrs), so readers keep their snapshot unchanged and an edit
// costs O(chunk + chunks) instead of O(n).
// The read side models the const part of std::vector<Mapping> (size, empty, operator[], random-access begin/end), so
// std::upper_bound and range-for over a snapshot work as before; a std::vector<Mapping> converts implicitly to a
// one-chunk index.
// Order: by va; at an equal va a shared mapping comes before a userptr one (the order of the old merge), and among
// equals an insertion goes after the ones already there.
#pragma once
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <iterator>
#include <memory>
#include <utility>
#include <vector>

namespace bc5::direct {

struct Mapping;

class MappingIndex {
public:
    using Chunk = std::vector<Mapping>;
    using ChunkPtr = std::shared_ptr<const Chunk>;
    static constexpr std::size_t kChunkMax = 1024;

    MappingIndex() = default;
    MappingIndex(const std::vector<Mapping> &v) : MappingIndex(std::vector<Mapping>(v)) {} // NOLINT: implicit on purpose
    explicit MappingIndex(std::vector<Mapping> &&v) {
        if (!v.empty()) chunks_.push_back(std::make_shared<const Chunk>(std::move(v)));
        reindex();
    }
    explicit MappingIndex(std::vector<ChunkPtr> chunks) : chunks_(std::move(chunks)) { reindex(); }

    std::size_t size() const { return total_; }
    bool empty() const { return total_ == 0; }
    const std::vector<ChunkPtr> &chunks() const { return chunks_; }
    const Mapping &operator[](std::size_t i) const {
        const std::size_t k = chunk_of(i);
        return (*chunks_[k])[i - starts_[k]];
    }

    class const_iterator {
    public:
        using iterator_category = std::random_access_iterator_tag;
        using value_type = Mapping;
        using difference_type = std::ptrdiff_t;
        using pointer = const Mapping *;
        using reference = const Mapping &;
        const_iterator() = default;
        const_iterator(const MappingIndex *x, std::size_t i) : x_(x), i_(i) { locate(); }
        reference operator*() const { return (*x_->chunks_[k_])[i_ - x_->starts_[k_]]; }
        pointer operator->() const { return &**this; }
        reference operator[](difference_type n) const { return *(*this + n); }
        const_iterator &operator++() {
            ++i_;
            if (k_ + 1 < x_->chunks_.size() && i_ >= x_->starts_[k_ + 1]) ++k_;
            return *this;
        }
        const_iterator operator++(int) {
            auto t = *this;
            ++*this;
            return t;
        }
        const_iterator &operator--() {
            --i_;
            if (k_ > 0 && i_ < x_->starts_[k_]) --k_;
            return *this;
        }
        const_iterator operator--(int) {
            auto t = *this;
            --*this;
            return t;
        }
        const_iterator &operator+=(difference_type n) {
            i_ = static_cast<std::size_t>(static_cast<difference_type>(i_) + n);
            locate();
            return *this;
        }
        const_iterator &operator-=(difference_type n) { return *this += -n; }
        friend const_iterator operator+(const_iterator a, difference_type n) { return a += n; }
        friend const_iterator operator+(difference_type n, const_iterator a) { return a += n; }
        friend const_iterator operator-(const_iterator a, difference_type n) { return a -= n; }
        friend difference_type operator-(const const_iterator &a, const const_iterator &b) {
            return static_cast<difference_type>(a.i_) - static_cast<difference_type>(b.i_);
        }
        friend bool operator==(const const_iterator &a, const const_iterator &b) { return a.i_ == b.i_; }
        friend bool operator!=(const const_iterator &a, const const_iterator &b) { return a.i_ != b.i_; }
        friend bool operator<(const const_iterator &a, const const_iterator &b) { return a.i_ < b.i_; }
        friend bool operator>(const const_iterator &a, const const_iterator &b) { return a.i_ > b.i_; }
        friend bool operator<=(const const_iterator &a, const const_iterator &b) { return a.i_ <= b.i_; }
        friend bool operator>=(const const_iterator &a, const const_iterator &b) { return a.i_ >= b.i_; }

    private:
        void locate() { k_ = (x_ != nullptr && i_ < x_->total_) ? x_->chunk_of(i_) : (x_ != nullptr && !x_->chunks_.empty() ? x_->chunks_.size() - 1 : 0); }
        const MappingIndex *x_ = nullptr;
        std::size_t i_ = 0, k_ = 0;
    };
    const_iterator begin() const { return const_iterator(this, 0); }
    const_iterator end() const { return const_iterator(this, total_); }

private:
    std::size_t chunk_of(std::size_t i) const { // the chunk holding element i
        auto it = std::upper_bound(starts_.begin(), starts_.end(), i);
        return static_cast<std::size_t>(it - starts_.begin()) - 1;
    }
    void reindex() {
        std::vector<ChunkPtr> kept;
        kept.reserve(chunks_.size());
        for (auto &c : chunks_)
            if (c != nullptr && !c->empty()) kept.push_back(std::move(c));
        chunks_.swap(kept);
        starts_.resize(chunks_.size());
        total_ = 0;
        for (std::size_t k = 0; k < chunks_.size(); k++) {
            starts_[k] = total_;
            total_ += chunks_[k]->size();
        }
    }
    std::vector<ChunkPtr> chunks_;
    std::vector<std::size_t> starts_; // index of each chunk's first element
    std::size_t total_ = 0;
};

namespace mapping_index_detail {
template <typename M> inline bool before(const M &a, const M &b) { // the old merge's order: va, then shared first
    return a.va < b.va || (a.va == b.va && a.shared && !b.shared);
}
} // namespace mapping_index_detail

// A new index with m inserted (after equal ones), sharing every chunk but the one edited.
template <typename M = Mapping>
inline std::shared_ptr<const MappingIndex> index_insert(const std::shared_ptr<const MappingIndex> &x, const M &m) {
    using mapping_index_detail::before;
    std::vector<MappingIndex::ChunkPtr> ch = x ? x->chunks() : std::vector<MappingIndex::ChunkPtr>{};
    if (ch.empty()) {
        ch.push_back(std::make_shared<const MappingIndex::Chunk>(MappingIndex::Chunk{m}));
        return std::make_shared<const MappingIndex>(std::move(ch));
    }
    // the last chunk whose first element is not after m
    std::size_t k = 0;
    for (std::size_t lo = 0, hi = ch.size(); lo < hi;) {
        const std::size_t mid = (lo + hi) / 2;
        if (!before(m, ch[mid]->front())) {
            k = mid;
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }
    MappingIndex::Chunk c = *ch[k];
    auto at = std::upper_bound(c.begin(), c.end(), m, [](const M &a, const M &b) { return before(a, b); });
    c.insert(at, m);
    if (c.size() > MappingIndex::kChunkMax) {
        MappingIndex::Chunk right(c.begin() + static_cast<std::ptrdiff_t>(c.size() / 2), c.end());
        c.resize(c.size() / 2);
        ch[k] = std::make_shared<const MappingIndex::Chunk>(std::move(c));
        ch.insert(ch.begin() + static_cast<std::ptrdiff_t>(k) + 1, std::make_shared<const MappingIndex::Chunk>(std::move(right)));
    } else {
        ch[k] = std::make_shared<const MappingIndex::Chunk>(std::move(c));
    }
    return std::make_shared<const MappingIndex>(std::move(ch));
}

// A new index without the first element equal to m (va, size, readonly, shared), or x itself when none is.
template <typename M = Mapping>
inline std::shared_ptr<const MappingIndex> index_erase(const std::shared_ptr<const MappingIndex> &x, const M &m) {
    using mapping_index_detail::before;
    if (!x || x->empty()) return x;
    std::vector<MappingIndex::ChunkPtr> ch = x->chunks();
    for (std::size_t k = 0; k < ch.size(); k++) {
        const auto &c0 = *ch[k];
        if (before(c0.back(), m)) continue;         // all of this chunk is before m
        if (before(m, c0.front())) break;           // and the rest after it
        auto lo = std::lower_bound(c0.begin(), c0.end(), m, [](const M &a, const M &b) { return before(a, b); });
        for (auto it = lo; it != c0.end() && !before(m, *it); ++it) {
            if (it->va == m.va && it->size == m.size && it->readonly == m.readonly && it->shared == m.shared) {
                MappingIndex::Chunk c = c0;
                c.erase(c.begin() + (it - c0.begin()));
                ch[k] = std::make_shared<const MappingIndex::Chunk>(std::move(c));
                return std::make_shared<const MappingIndex>(std::move(ch));
            }
        }
    }
    return x;
}

} // namespace bc5::direct
