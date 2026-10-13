// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/full_state.hpp"

#include <algorithm>

namespace bc5::full_state {

namespace {

constexpr std::uint32_t kMaxTable = 0x1000;
constexpr std::size_t kMaxStack = 8;

std::uint64_t address(std::uint32_t lo, std::uint32_t hi) {
    return (static_cast<std::uint64_t>(lo) & ~3ull) | (static_cast<std::uint64_t>(hi & 0xffffu) << 32);
}

int space_of_set(std::uint8_t op) {
    switch (op) {
    case 0x68: return Config;  // SET_CONFIG_REG
    case 0x69: return Context; // SET_CONTEXT_REG
    case 0x76:                 // SET_SH_REG
    case 0x9b: return Sh;      // SET_SH_REG_INDEX
    case 0x79:                 // SET_UCONFIG_REG
    case 0x7a: return Uconfig; // SET_UCONFIG_REG_INDEX
    default: return -1;
    }
}

int space_of_load(std::uint8_t op) {
    switch (op) {
    case 0x61: return Context; // LOAD_CONTEXT_REG
    case 0x5f: return Sh;      // LOAD_SH_REG
    case 0x5e: return Uconfig; // LOAD_UCONFIG_REG
    default: return -1;
    }
}

int space_of_load_index(std::uint8_t op) {
    switch (op) {
    case 0x9f: return Context; // LOAD_CONTEXT_REG_INDEX
    case 0x63: return Sh;      // LOAD_SH_REG_INDEX
    case 0x64: return Uconfig; // LOAD_UCONFIG_REG_INDEX
    default: return -1;
    }
}

constexpr std::uint8_t kSetOp[Spaces] = {0x68, 0x69, 0x76, 0x79};

void put_header(std::vector<std::uint32_t> &out, std::uint8_t op, std::size_t body) {
    out.push_back(0xC0000000u | (static_cast<std::uint32_t>(body - 1) << 16) |
                  (static_cast<std::uint32_t>(op) << 8));
}

} // namespace

void Tracker::set(Space space, std::uint32_t offset, std::uint32_t value) {
    regs_[space][offset & 0xffffu] = value;
}

bool Tracker::get(Space space, std::uint32_t offset, std::uint32_t &value) const {
    const auto it = regs_[space].find(offset);
    if (it == regs_[space].end()) return false;
    value = it->second;
    return true;
}

bool Tracker::operator==(const Tracker &o) const {
    for (int s = 0; s < Spaces; ++s)
        if (regs_[s] != o.regs_[s]) return false;
    const auto &a = packets_, &b = o.packets_;
    return a.set_base == b.set_base && a.index_base == b.index_base &&
           a.index_buffer_size == b.index_buffer_size && a.index_type == b.index_type &&
           a.num_instances == b.num_instances;
}

void Tracker::apply(std::span<const std::uint32_t> ib, const Reader &read, Stats &stats) {
    apply_level(ib, read, stats, 0);
}

bool Tracker::first_difference(const Tracker &o, int &space, std::uint32_t &offset) const {
    for (int s = 0; s < Spaces; ++s) {
        auto a = regs_[s].begin(), b = o.regs_[s].begin();
        while (a != regs_[s].end() || b != o.regs_[s].end()) {
            if (a == regs_[s].end() || (b != o.regs_[s].end() && b->first < a->first)) {
                space = s;
                offset = b->first;
                return true;
            }
            if (b == o.regs_[s].end() || a->first < b->first || a->second != b->second) {
                space = s;
                offset = a->first;
                return true;
            }
            ++a;
            ++b;
        }
    }
    return false;
}

void Tracker::apply_level(std::span<const std::uint32_t> ib, const Reader &read, Stats &stats, int depth) {
    for (std::size_t i = 0; i < ib.size();) {
        const std::uint32_t h = ib[i];
        const std::uint32_t type = h >> 30;
        const std::uint32_t count = (h >> 16) & 0x3fffu;
        std::size_t len = 1;
        if (type == 3 || type == 0) len = count == 0x3fffu ? 1 : count + 2;
        if (i + len > ib.size()) break;
        if (type != 3 || count == 0x3fffu) {
            i += len;
            continue;
        }
        stats.packets++;
        const auto op = static_cast<std::uint8_t>((h >> 8) & 0xffu);
        const std::uint32_t *p = &ib[i];
        const auto body = [p, len] { return std::vector<std::uint32_t>(p + 1, p + len); };
        if (const int sp = space_of_set(op); sp >= 0 && len >= 3) {
            const std::uint32_t off = p[1] & 0xffffu;
            for (std::size_t k = 2; k < len; ++k) {
                set(static_cast<Space>(sp), off + static_cast<std::uint32_t>(k - 2), p[k]);
                stats.registers_set++;
            }
        } else if (const int lsp = space_of_load(op); lsp >= 0 && len >= 5) {
            const std::uint64_t base = address(p[1], p[2]);
            for (std::size_t k = 3; k + 1 < len; k += 2) {
                const std::uint32_t off = p[k] & 0xffffu;
                const std::uint32_t n = std::min(p[k + 1] & 0x3fffu, kMaxTable);
                if (n == 0) continue;
                const std::uint32_t *t = read ? read(base + static_cast<std::uint64_t>(off) * 4, n * 4ull) : nullptr;
                if (t == nullptr) {
                    stats.unreadable_tables++;
                    continue;
                }
                for (std::uint32_t q = 0; q < n; ++q) set(static_cast<Space>(lsp), off + q, t[q]);
                stats.registers_set += n;
                stats.tables++;
            }
        } else if (const int isp = space_of_load_index(op); isp >= 0 && len >= 5) {
            const std::uint64_t a = address(p[1], p[2]);
            const bool pairs = (p[3] >> 31) != 0;
            const std::uint32_t n = std::min(p[4] & 0x3fffu, kMaxTable);
            if (n != 0) {
                const std::uint32_t *t = read ? read(a, static_cast<std::uint64_t>(n) * (pairs ? 8 : 4)) : nullptr;
                if (t == nullptr) {
                    stats.unreadable_tables++;
                } else {
                    for (std::uint32_t q = 0; q < n; ++q) {
                        if (pairs) set(static_cast<Space>(isp), t[2 * q] & 0xffffu, t[2 * q + 1]);
                        else set(static_cast<Space>(isp), (p[3] & 0xffffu) + q, t[q]);
                    }
                    stats.registers_set += n;
                    stats.tables++;
                }
            }
        } else if (op == 0x12 && len >= 2) { // CLEAR_STATE
            const std::uint32_t cmd = p[1] & 0xfu;
            if (cmd == 1) {
                if (context_stack_.size() < kMaxStack) context_stack_.push_back(regs_[Context]);
                stats.pushes++;
                regs_[Context].clear();
            } else if (cmd == 2 && !context_stack_.empty()) {
                regs_[Context] = context_stack_.back();
                context_stack_.pop_back();
                stats.pops++;
            } else {
                regs_[Context].clear();
                stats.clears++;
            }
        } else if (op == 0x3f && len >= 4) { // INDIRECT_BUFFER: address lo, hi, IB_SIZE bits 19:0
            const std::uint32_t n = p[3] & 0xfffffu;
            const std::uint32_t *t =
                read && n != 0 && depth < 4 ? read(address(p[1], p[2]), n * 4ull) : nullptr;
            if (t == nullptr) {
                stats.unreadable_nested++;
            } else {
                stats.nested++;
                apply_level(std::span<const std::uint32_t>(t, n), read, stats, depth + 1);
            }
        } else if (op == 0x11 && len >= 2) { // SET_BASE: base_index in dword 1 bits 3:0
            packets_.set_base[p[1] & 0xfu] = body();
        } else if (op == 0x26) { // INDEX_BASE
            packets_.index_base = body();
        } else if (op == 0x13) { // INDEX_BUFFER_SIZE
            packets_.index_buffer_size = body();
        } else if (op == 0x2a) { // INDEX_TYPE
            packets_.index_type = body();
        } else if (op == 0x2f) { // NUM_INSTANCES
            packets_.num_instances = body();
        } else if (op == 0x28) { // CONTEXT_CONTROL
            packets_.context_control = body();
        }
        i += len;
    }
}

std::vector<std::uint32_t> Tracker::emit_prefix() const {
    std::vector<std::uint32_t> out;
    // CONTEXT_CONTROL with load and shadow enables 0x80000000, the form the policy forces.
    out.insert(out.end(), {0xC0012800u, 0x80000000u, 0x80000000u});
    out.insert(out.end(), {0xC0001200u, 0u}); // CLEAR_STATE cmd 0
    for (int s = 0; s < Spaces; ++s) {
        const auto &m = regs_[s];
        for (auto it = m.begin(); it != m.end();) {
            auto run_end = it;
            std::vector<std::uint32_t> values;
            std::uint32_t next = it->first;
            while (run_end != m.end() && run_end->first == next && values.size() < 0x3fff - 1) {
                values.push_back(run_end->second);
                ++next;
                ++run_end;
            }
            put_header(out, kSetOp[s], values.size() + 1);
            out.push_back(it->first);
            out.insert(out.end(), values.begin(), values.end());
            it = run_end;
        }
    }
    const auto put = [&out](std::uint8_t op, const std::vector<std::uint32_t> &b) {
        if (b.empty()) return;
        put_header(out, op, b.size());
        out.insert(out.end(), b.begin(), b.end());
    };
    for (const auto &[index, b] : packets_.set_base) put(0x11, b);
    put(0x26, packets_.index_base);
    put(0x13, packets_.index_buffer_size);
    put(0x2a, packets_.index_type);
    put(0x2f, packets_.num_instances);
    return out;
}

namespace {

bool is_draw(std::uint8_t op) {
    switch (op) {
    case 0x15: case 0x16: case 0x24: case 0x25: case 0x27: case 0x2c: case 0x2d: case 0x35: case 0x38:
        return true;
    default:
        return false;
    }
}

} // namespace

SplitCheck check_split(const Tracker &before, std::span<const std::uint32_t> ib, std::size_t wait,
                       const Tracker::Reader &read) {
    SplitCheck c;
    Stats st;
    wait = std::min(wait, ib.size());
    Tracker whole = before;
    whole.apply(ib.first(wait), read, st);
    c.stack_depth = whole.stack_depth();
    const auto prefix = whole.emit_prefix();
    c.prefix_dwords = prefix.size();
    Tracker piece;
    piece.apply(prefix, nullptr, st);
    std::size_t from = wait;
    for (std::size_t i = wait; i < ib.size();) {
        const std::uint32_t h = ib[i];
        const std::uint32_t type = h >> 30;
        std::size_t len = 1;
        if (type == 3 || type == 0) {
            const std::uint32_t count = (h >> 16) & 0x3fffu;
            len = count == 0x3fffu ? 1 : count + 2;
        }
        if (i + len > ib.size()) break;
        if (type == 3 && is_draw(static_cast<std::uint8_t>((h >> 8) & 0xffu))) {
            const auto seg = ib.subspan(from, i - from);
            whole.apply(seg, read, st);
            piece.apply(seg, read, st);
            from = i;
            c.draws++;
            int sp = -1;
            std::uint32_t off = 0;
            if (whole.first_difference(piece, sp, off) || !(whole == piece)) {
                if (c.mismatched_draws++ == 0) {
                    c.first_space = sp;
                    c.first_offset = off;
                }
            }
        }
        i += len;
    }
    return c;
}

} // namespace bc5::full_state
