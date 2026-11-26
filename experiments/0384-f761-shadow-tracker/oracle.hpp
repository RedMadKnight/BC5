// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0384: the oracle. It runs real PM4 dwords the slow and obvious way: every way through every COND_EXEC,
// over a sequence of buffers, for three SH registers. What cannot be followed may leave anything: one way untouched, one way
// all three registers overwritten with kAny. carry says which reading of a count past a buffer's end is used.
// It is a test tool for small synthetic streams, and it knows only what the generator produces.
#pragma once

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <map>
#include <span>
#include <utility>
#include <vector>

namespace bc5::oracle {

inline constexpr std::uint32_t kReg0 = 0x240;
inline constexpr std::size_t kRegs = 3;
inline constexpr std::int64_t kUnset = -1, kAny = -2;
inline constexpr std::size_t kMaxDepth = 32;

using Memory = std::map<std::uint64_t, std::vector<std::uint32_t>>;

struct Way {
    std::array<std::int64_t, kRegs> r{kUnset, kUnset, kUnset};
    std::size_t skip = 0; // the count left past the end
    bool operator<(const Way &o) const { return r != o.r ? r < o.r : skip < o.skip; }
    bool operator==(const Way &o) const { return r == o.r && skip == o.skip; }
};

class Oracle {
public:
    Oracle(const Memory &m, bool carry) : mem_(m), carry_(carry) {}
    bool overflowed() const { return overflow_; }

    std::vector<Way> run(const std::vector<std::vector<std::uint32_t>> &buffers) {
        std::vector<Way> ways{Way{}};
        for (const auto &b : buffers) {
            std::vector<Way> next;
            for (const Way &w : ways) {
                std::vector<Way> out;
                Way start = w;
                const std::size_t i = start.skip;
                start.skip = 0;
                walk(b, i, start, out, 0);
                next.insert(next.end(), out.begin(), out.end());
            }
            unique(next);
            ways = std::move(next);
            if (overflow_) break;
        }
        return ways;
    }

private:
    static void unique(std::vector<Way> &v) {
        std::sort(v.begin(), v.end());
        v.erase(std::unique(v.begin(), v.end()), v.end());
    }
    static Way all_any(Way w) {
        w.r.fill(kAny);
        return w;
    }
    void write(Way &w, std::uint32_t off, std::uint32_t v) const {
        if (off >= kReg0 && off - kReg0 < kRegs) w.r[off - kReg0] = v;
    }
    // A flat load: unreadable, the range may be anything, one way untouched and one way overwritten.
    void load_range(std::span<const std::uint32_t> ib, std::size_t i, std::size_t len, Way &st, std::vector<Way> &out,
                    std::size_t depth, Memory::const_iterator it, std::uint32_t off, std::uint32_t n) {
        if (it != mem_.end() && it->second.size() == n) {
            for (std::uint32_t q = 0; q < n; ++q) write(st, off + q, it->second[q]);
            return;
        }
        Way any = st;
        for (std::uint32_t q = 0; q < n; ++q)
            if (off + q >= kReg0 && off + q - kReg0 < kRegs) any.r[off + q - kReg0] = kAny;
        if (any.r != st.r) walk(ib, i + len, any, out, depth);
    }
    void walk(std::span<const std::uint32_t> ib, std::size_t i, Way st, std::vector<Way> &out, std::size_t depth) {
        if (++steps_ > 400000 || out.size() > 4096) {
            overflow_ = true;
            return;
        }
        for (;;) {
            if (i >= ib.size()) {
                st.skip = carry_ ? i - ib.size() : 0;
                out.push_back(st);
                return;
            }
            const std::uint32_t h = ib[i], type = h >> 30, count = (h >> 16) & 0x3fffu, op = (h >> 8) & 0xffu;
            const std::size_t len = (type == 3 || type == 0) && count != 0x3fffu ? count + 2u : 1u;
            if (type == 1 || i + len > ib.size()) { // nobody knows: unchanged, or anything
                st.skip = 0;
                out.push_back(st);
                out.push_back(all_any(st));
                return;
            }
            const std::uint32_t *p = &ib[i];
            // A short form of a known packet: unchanged, or anything. No body dword is read before this.
            if (type == 3 && (((op == 0x76 || op == 0x9b) && len < 3) || ((op == 0x22 || op == 0x63) && len < 5) ||
                              (op == 0x5f && (len < 5 || (len - 3) % 2 != 0)) || (op == 0x3f && len != 4))) {
                walk(ib, i + len, all_any(st), out, depth);
                i += len;
                continue;
            }
            if (type == 3 && (op == 0x76 || op == 0x9b)) {
                for (std::size_t k = 2; k < len; ++k) write(st, (p[1] & 0xffffu) + static_cast<std::uint32_t>(k - 2), p[k]);
            } else if (type == 3 && op == 0x22) {
                walk(ib, i + len + (p[4] & 0x3fffu), st, out, depth);
            } else if (type == 3 && op == 0x63) {
                const std::uint64_t a = (static_cast<std::uint64_t>(p[1]) & ~3ull) | (static_cast<std::uint64_t>(p[2] & 0xffffu) << 32);
                const auto it = mem_.find(a);
                const std::uint32_t n = p[4] & 0x3fffu;
                if ((p[3] >> 31) != 0) { // pairs: an unreadable table can name any register
                    if (it == mem_.end() || it->second.size() != n * 2ull) {
                        if (n != 0) walk(ib, i + len, all_any(st), out, depth);
                    } else {
                        for (std::uint32_t q = 0; q < n; ++q) write(st, it->second[2 * q] & 0xffffu, it->second[2 * q + 1]);
                    }
                } else {
                    load_range(ib, i, len, st, out, depth, it, p[3] & 0xffffu, n);
                }
            } else if (type == 3 && op == 0x5f) {
                const std::uint64_t base = (static_cast<std::uint64_t>(p[1]) & ~3ull) | (static_cast<std::uint64_t>(p[2] & 0xffffu) << 32);
                for (std::size_t k = 3; k + 1 < len; k += 2) {
                    const std::uint32_t off = p[k] & 0xffffu, n = p[k + 1] & 0x3fffu;
                    if (n != 0) load_range(ib, i, len, st, out, depth, mem_.find(base + off * 4ull), off, n);
                }
            } else if (type == 3 && op == 0x3f) {
                const std::uint64_t a = (static_cast<std::uint64_t>(p[1]) & ~3ull) | (static_cast<std::uint64_t>(p[2] & 0xffffu) << 32);
                const std::uint32_t n = p[3] & 0xfffffu;
                const bool chain = (p[3] & (1u << 20)) != 0;
                const auto it = mem_.find(a);
                const bool readable = len == 4 && it != mem_.end() && it->second.size() == n && n != 0;
                const bool cycle = std::find(active_.begin(), active_.end(), a) != active_.end();
                std::vector<Way> afters;
                if (readable && !cycle && depth < kMaxDepth) {
                    active_.push_back(a);
                    Way in = st;
                    in.skip = 0;
                    walk(it->second, 0, in, afters, depth + 1);
                    active_.pop_back();
                } else {
                    afters = {st, all_any(st)};
                }
                unique(afters);
                for (const Way &w : afters) {
                    if (chain) out.push_back(w); // the target's end is this buffer's end
                    else {
                        Way after = w;
                        const std::size_t skip = after.skip;
                        after.skip = 0;
                        walk(ib, i + len + skip, after, out, depth);
                    }
                }
                return;
            }
            i += len;
        }
    }
    const Memory &mem_;
    bool carry_;
    bool overflow_ = false;
    std::size_t steps_ = 0;
    std::vector<std::uint64_t> active_{};
};

} // namespace bc5::oracle
