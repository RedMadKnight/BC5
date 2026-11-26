// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0384 (F761): a prototype, in this directory only. Nothing in backend/ or the host includes it, and it
// emits nothing. It follows the same stream as bc5::full_state::Tracker with its OWN value store, because a CHAIN makes the
// two disagree on the value itself (Codex's F761 review: flags alone could not keep the old bytes).
//
// The contract: a register reported Certain holds that value at EVERY end of the stream, under both readings of a
// COND_EXEC that runs past a buffer's end (see the boundary contract below), in the host's view of the packets and tables.
// Anything else is Uncertain or Absent, and Certain says nothing about whether it is safe to send: an emission policy
// needs groups of dependent registers (a program pointer and its resources), which is a separate question.
//
// Control flow: INDIRECT_BUFFER (0x3f) with bit 20 of the size dword is a CHAIN (AMD PAL c5e8000
// src/core/hw/gfxip/gfx9/chip/gfx9_plus_merged_f32_pfp_pm4_packets.h:2580). Opcodes and register spaces are those of
// backend/src/full_state.cpp. COND_EXEC's count is its fifth dword, as the host reads it.
//
// The boundary contract. What the CP does when a COND_EXEC's count runs past the end of its buffer has no source here
// (TODO(verify)). It may stop at the end, or carry on into what comes next. So the rest of the count is carried as
// conditional into the next packets: a write there is Uncertain, which is right under both readings. A count ending inside
// a packet means the skipping way decodes other dwords: everything is Uncertain and the rest of the buffer conditional.
//
// Tables are modelled whole. The count fields are 14 bits, as the tracker masks them (TODO(verify) the width), so a declared
// range is at most 16,383 entries and there is no cap here: Codex's review of cbea178 showed that a cap, copied from
// full_state.cpp's kMaxTable, left a stale Certain past the entries read. A table that cannot be read is Uncertain: its range
// for a flat load, its whole space for pairs, which can name any register.
//
// Not modelled, and so not covered by the contract: SET_BASE, INDEX_BASE, INDEX_BUFFER_SIZE, INDEX_TYPE, NUM_INSTANCES and
// CONTEXT_CONTROL (counted in stats.unmodelled_packets); INDIRECT_BUFFER_CONST 0x33; the longer conditional IB (any other
// length of 0x3f makes everything Uncertain); the GPU writing a table after the CPU read it.
#pragma once

#include "bc5/full_state.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <map>
#include <set>
#include <span>
#include <tuple>
#include <utility>
#include <vector>

namespace bc5::shadow {

enum class State { Absent, Certain, Uncertain };

struct Stats {
    std::size_t cannot_follow = 0;      // unreadable, cycle or limit: everything went Uncertain
    std::size_t malformed = 0;          // truncated, type 1, 0x3f of another length
    std::size_t count_inside_packet = 0;
    std::size_t count_past_end = 0;
    std::size_t conditional_chains = 0;
    std::size_t chains = 0;
    std::size_t unmodelled_packets = 0;
    std::size_t unreadable_tables = 0;
};

class ShadowState {
public:
    using Reader = full_state::Tracker::Reader;
    // For the tests: each switch turned off is a mutant that the oracle has to catch.
    struct Options {
        bool chain_ends_level = true;
        bool carry = true;
        bool conditional_writes = true;
        bool cannot_follow_clobbers = true;
        bool conditional_chain_tail = true;
        bool inside_packet = true;
        bool table_cap = false; // the old tracker's 4,096-entry cap, the bug Codex found: on only as a mutant
    };
    static constexpr std::size_t kMaxDepth = 32; // calls and chains together
    static constexpr std::uint32_t kCapMutant = 0x1000;

    ShadowState() = default;
    explicit ShadowState(Options o) : opt_(o) {}

    // One buffer, in submission order, as Tracker::apply.
    void apply(std::span<const std::uint32_t> ib, const Reader &read) {
        std::set<std::size_t> take;
        take.swap(carry_);
        level(ib, read, false, 0, take);
    }

    State get(full_state::Space s, std::uint32_t off, std::uint32_t &value) const {
        const auto &m = regs_[static_cast<std::size_t>(s)];
        const auto it = m.find(off);
        if (it == m.end()) return State::Absent;
        value = it->second.value;
        return certain(s, it->second) ? State::Certain : State::Uncertain;
    }
    // How many different counts may still be running at the end of the last buffer. It is a set: different ways through a
    // buffer leave it with different counts, and each can land somewhere else in the next one.
    std::size_t carried() const { return carry_.size(); }
    const Stats &stats() const { return stats_; }

private:
    struct Entry {
        std::uint32_t value = 0;
        std::uint64_t epoch = 0;
        bool uncertain = false;
    };
    using Regs = std::map<std::uint32_t, Entry>;
    static constexpr std::size_t kSpaces = full_state::Spaces;

    bool certain(full_state::Space s, const Entry &e) const {
        return !e.uncertain && e.epoch == epoch_[static_cast<std::size_t>(s)];
    }
    void write(full_state::Space s, std::uint32_t off, std::uint32_t v, bool conditional) {
        Entry &e = regs_[static_cast<std::size_t>(s)][off];
        if (conditional && opt_.conditional_writes) {
            // regs_ just made a new entry if there was none: it must read as uncertain.
            const bool same = e.epoch != 0 && certain(s, e) && e.value == v;
            if (!same) {
                e.value = v;
                e.uncertain = true;
                e.epoch = epoch_[static_cast<std::size_t>(s)];
            }
            return;
        }
        e = {v, epoch_[static_cast<std::size_t>(s)], false};
    }
    void mark_uncertain(full_state::Space s, std::uint32_t off) {
        const auto it = regs_[static_cast<std::size_t>(s)].find(off);
        if (it != regs_[static_cast<std::size_t>(s)].end()) it->second.uncertain = true;
    }
    void clobber_space(full_state::Space s) {
        if (opt_.cannot_follow_clobbers) ++epoch_[static_cast<std::size_t>(s)];
    }
    void clobber_all() {
        for (std::size_t s = 0; s < kSpaces; ++s) clobber_space(static_cast<full_state::Space>(s));
    }
    static int space_of_set(std::uint32_t op) {
        switch (op) {
        case 0x68: return full_state::Config;
        case 0x69: return full_state::Context;
        case 0x76:
        case 0x9b: return full_state::Sh;
        case 0x79:
        case 0x7a: return full_state::Uconfig;
        default: return -1;
        }
    }
    static int space_of_load(std::uint32_t op) {
        switch (op) {
        case 0x61: return full_state::Context;
        case 0x5f: return full_state::Sh;
        case 0x5e: return full_state::Uconfig;
        default: return -1;
        }
    }
    static int space_of_load_index(std::uint32_t op) {
        switch (op) {
        case 0x9f: return full_state::Context;
        case 0x63: return full_state::Sh;
        case 0x64: return full_state::Uconfig;
        default: return -1;
        }
    }
    std::uint32_t table_count(std::uint32_t n) const { return opt_.table_cap ? std::min(n, kCapMutant) : n; }
    static std::uint64_t address(std::uint32_t lo, std::uint32_t hi) {
        return (static_cast<std::uint64_t>(lo) & ~3ull) | (static_cast<std::uint64_t>(hi & 0xffffu) << 32);
    }
    void clear_state(std::uint32_t cmd, bool conditional) {
        const auto ctx = static_cast<std::size_t>(full_state::Context);
        if (conditional) {
            clobber_space(full_state::Context);
            stack_known_ = false;
            return;
        }
        if (cmd == 1) {
            stack_.push_back(regs_[ctx]);
            regs_[ctx].clear();
        } else if (cmd == 2) {
            if (stack_known_ && !stack_.empty()) {
                regs_[ctx] = stack_.back();
                stack_.pop_back();
            } else {
                clobber_space(full_state::Context);
            }
        } else {
            regs_[ctx].clear();
        }
    }
    void level(std::span<const std::uint32_t> ib, const Reader &read, bool conditional, std::size_t depth,
               const std::set<std::size_t> &skips_in) {
        std::set<std::size_t> targets; // where COND_EXEC counts end
        std::size_t until = 0;         // the dwords below this are under a COND_EXEC
        std::set<std::size_t> pending; // the counts left at the end of this buffer
        const auto add_count = [&](std::size_t end) {
            if (end > ib.size()) {
                pending.insert(end - ib.size());
                until = ib.size();
                ++stats_.count_past_end;
            } else {
                targets.insert(end);
                until = std::max(until, end);
            }
        };
        if (opt_.carry)
            for (const std::size_t k : skips_in) add_count(k);
        std::size_t i = 0;
        while (i < ib.size()) {
            const std::uint32_t h = ib[i], type = h >> 30, count = (h >> 16) & 0x3fffu;
            const std::uint32_t op = (h >> 8) & 0xffu;
            const std::size_t len = (type == 3 || type == 0) && count != 0x3fffu ? count + 2u : 1u;
            const auto inside = targets.upper_bound(i);
            if (inside != targets.end() && *inside < i + len) {
                ++stats_.count_inside_packet;
                if (opt_.inside_packet) {
                    clobber_all();
                    conditional = true;
                }
            }
            bool c = conditional || i < until;
            if (type == 1 || i + len > ib.size() || (type == 3 && count == 0x3fffu && op != 0x10)) {
                ++stats_.malformed;
                clobber_all();
                break;
            }
            if (type != 3 || op == 0x10) {
                i += len;
                continue;
            }
            const std::uint32_t *p = &ib[i];
            // A short form of a known packet: nobody knows what the CP does with it. The length is checked here, before any
            // body dword is read.
            const bool loads = space_of_load(op) >= 0, indexed = space_of_load_index(op) >= 0;
            if ((space_of_set(op) >= 0 && len < 3) || (loads && (len < 5 || (len - 3) % 2 != 0)) || (indexed && len < 5) ||
                (op == 0x22 && len < 5) || (op == 0x12 && len < 2) || (op == 0x3f && len != 4)) {
                ++stats_.malformed;
                clobber_all();
                i += len;
                continue;
            }
            if (const int sp = space_of_set(op); sp >= 0) {
                const std::uint32_t off = p[1] & 0xffffu;
                for (std::size_t k = 2; k < len; ++k)
                    write(static_cast<full_state::Space>(sp), off + static_cast<std::uint32_t>(k - 2), p[k], c);
            } else if (const int lsp = space_of_load(op); lsp >= 0) {
                const auto s = static_cast<full_state::Space>(lsp);
                const std::uint64_t base = address(p[1], p[2]);
                for (std::size_t k = 3; k + 1 < len; k += 2) {
                    const std::uint32_t off = p[k] & 0xffffu, n = table_count(p[k + 1] & 0x3fffu);
                    if (n == 0) continue;
                    const std::uint32_t *t = read ? read(base + static_cast<std::uint64_t>(off) * 4, n * 4ull) : nullptr;
                    for (std::uint32_t q = 0; q < n; ++q) {
                        if (t != nullptr) write(s, off + q, t[q], c);
                        else mark_uncertain(s, off + q);
                    }
                    if (t == nullptr) ++stats_.unreadable_tables;
                }
            } else if (const int isp = space_of_load_index(op); isp >= 0) {
                const auto s = static_cast<full_state::Space>(isp);
                const std::uint64_t a = address(p[1], p[2]);
                const bool pairs = (p[3] >> 31) != 0;
                const std::uint32_t n = table_count(p[4] & 0x3fffu);
                if (n != 0) {
                    const std::uint32_t *t = read ? read(a, static_cast<std::uint64_t>(n) * (pairs ? 8 : 4)) : nullptr;
                    if (t == nullptr) {
                        ++stats_.unreadable_tables;
                        if (pairs) clobber_space(s);
                        else
                            for (std::uint32_t q = 0; q < n; ++q) mark_uncertain(s, (p[3] & 0xffffu) + q);
                    } else {
                        for (std::uint32_t q = 0; q < n; ++q) {
                            if (pairs) write(s, t[2 * q] & 0xffffu, t[2 * q + 1], c);
                            else write(s, (p[3] & 0xffffu) + q, t[q], c);
                        }
                    }
                }
            } else if (op == 0x12) { // CLEAR_STATE
                clear_state(p[1] & 0xfu, c);
            } else if (op == 0x22) { // COND_EXEC
                add_count(i + len + (p[4] & 0x3fffu));
            } else if (op == 0x3f) {
                const std::uint64_t a = address(p[1], p[2]);
                const std::uint32_t n = p[3] & 0xfffffu;
                const bool chain = (p[3] & (1u << 20)) != 0;
                const std::pair<std::uint64_t, std::uint32_t> id{a, n};
                const std::uint32_t *t = read && n != 0 ? read(a, n * 4ull) : nullptr;
                const bool follow = t != nullptr && depth < kMaxDepth &&
                                    std::find(active_.begin(), active_.end(), id) == active_.end();
                stats_.chains += chain;
                if (follow) {
                    active_.push_back(id);
                    level(std::span<const std::uint32_t>(t, n), read, c, depth + 1, {});
                    active_.pop_back();
                } else {
                    ++stats_.cannot_follow;
                    clobber_all();
                }
                // A CHAIN's end is this buffer's end, so a count left by its target runs on after this buffer, and the
                // tail has nothing to do with it. After a call it runs on in the tail.
                if (chain && !c && opt_.chain_ends_level) {
                    carry_.insert(pending.begin(), pending.end());
                    return;
                }
                if (chain && c) {
                    ++stats_.conditional_chains;
                    if (opt_.conditional_chain_tail) conditional = true; // taken: the tail never runs
                }
                std::set<std::size_t> left;
                left.swap(carry_);
                if (opt_.carry)
                    for (const std::size_t k : left) {
                        if (chain) pending.insert(k);
                        else add_count(i + len + k);
                    }
            } else if (op == 0x11 || op == 0x26 || op == 0x13 || op == 0x2a || op == 0x2f || op == 0x28) {
                ++stats_.unmodelled_packets;
            }
            i += len;
        }
        carry_.insert(pending.begin(), pending.end());
    }

    Options opt_{};
    std::array<Regs, kSpaces> regs_{};
    std::array<std::uint64_t, kSpaces> epoch_{1, 1, 1, 1}; // from 1: epoch 0 marks a new entry
    std::vector<Regs> stack_{};
    bool stack_known_ = true;
    std::vector<std::pair<std::uint64_t, std::uint32_t>> active_{};
    std::set<std::size_t> carry_{};
    Stats stats_{};
};

// The old tracker and the shadow side by side, sharing nothing but the stream.
struct Pair {
    full_state::Tracker old{};
    ShadowState shadow{};
    full_state::Stats old_stats{};
    void apply(std::span<const std::uint32_t> ib, const ShadowState::Reader &read) {
        old.apply(ib, read, old_stats);
        shadow.apply(ib, read);
    }
};

} // namespace bc5::shadow
