// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0381: indirect draw arguments at submit and at completion (bc5/draw_args.hpp).
#include "bc5/draw_args.hpp"

#include <cstdio>

namespace bc5::draw_args {

namespace {

constexpr std::uint32_t kOpSetBase = 0x11;
constexpr std::uint32_t kOpDrawIndirect = 0x24;
constexpr std::uint32_t kOpDrawIndexIndirect = 0x25;

std::size_t packet_len(std::uint32_t h) {
    const std::uint32_t type = h >> 30;
    if (type == 3 || type == 0) {
        const std::uint32_t count = (h >> 16) & 0x3fff;
        return count == 0x3fff ? 1 : count + 2;
    }
    return 1;
}

} // namespace

std::vector<Rec> scan(std::span<const std::uint32_t> ib, std::uint64_t base_in, const Reader &read,
                      std::uint32_t *unbased) {
    std::vector<Rec> out;
    std::uint64_t base = base_in;
    for (std::size_t i = 0; i < ib.size();) {
        const std::uint32_t h = ib[i];
        const std::size_t len = packet_len(h);
        if (i + len > ib.size())
            break;
        const std::uint32_t op = (h >> 8) & 0xff;
        if (h >> 30 == 3 && op == kOpSetBase && len >= 4 && (ib[i + 1] & 0xfu) == 1) {
            base = (static_cast<std::uint64_t>(ib[i + 2]) & ~3ull) |
                   (static_cast<std::uint64_t>(ib[i + 3] & 0xffffu) << 32);
        }
        if (h >> 30 == 3 && (op == kOpDrawIndirect || op == kOpDrawIndexIndirect) && len == 5) {
            if (base == 0) {
                if (unbased != nullptr)
                    ++*unbased;
            } else {
                Rec r;
                r.at = static_cast<std::uint32_t>(i);
                r.op = op;
                r.base = base;
                r.addr = base + ib[i + 1];
                r.read = read && read(r.addr, r.v);
                out.push_back(r);
            }
        }
        i += len;
    }
    return out;
}

bool index_like(const std::uint32_t (&v)[4]) {
    int steps = 0;
    for (int k = 0; k < 3; ++k)
        if (v[k + 1] == v[k] + 1)
            steps++;
    return steps >= 2 && (v[0] > 0xffffu || v[1] > 0xffffu);
}

std::uint32_t classify(const Rec &r, const Limits &lim) {
    if (!r.read)
        return kUnread;
    std::uint32_t f = 0;
    if (r.v[0] > lim.vertices)
        f |= kOverVertices;
    if (r.v[1] > lim.instances)
        f |= kOverInstances;
    if (index_like(r.v))
        f |= kIndexLike;
    return f;
}

std::string flag_names(std::uint32_t flags) {
    if (flags == 0)
        return "-";
    std::string s;
    const auto add = [&s](const char *n) {
        if (!s.empty())
            s += ',';
        s += n;
    };
    if (flags & kOverVertices)
        add("over-vertices");
    if (flags & kOverInstances)
        add("over-instances");
    if (flags & kIndexLike)
        add("index-like");
    if (flags & kUnread)
        add("unread");
    return s;
}

namespace {

std::string words(const Rec &r) {
    if (!r.read)
        return "v ? ? ? ?";
    char buf[64];
    std::snprintf(buf, sizeof(buf), "v %08x %08x %08x %08x", r.v[0], r.v[1], r.v[2], r.v[3]);
    return buf;
}

} // namespace

std::string line(const char *phase, std::uint64_t seq, const Rec &r, std::uint32_t flags,
                 const char *then_phase, const Rec *then, std::uint32_t then_flags) {
    char head[160];
    std::snprintf(head, sizeof(head), "draw-args %s seq %llu at %u op 0x%02x base 0x%llx addr 0x%llx ", phase,
                  static_cast<unsigned long long>(seq), r.at, r.op, static_cast<unsigned long long>(r.base),
                  static_cast<unsigned long long>(r.addr));
    std::string s = head + words(r) + " flags " + flag_names(flags);
    if (then_phase != nullptr && then != nullptr) {
        bool changed = then->read != r.read;
        for (int k = 0; k < 4 && !changed; ++k)
            changed = then->v[k] != r.v[k];
        s += std::string(" | ") + then_phase + " " + words(*then) + " flags " + flag_names(then_flags) +
             " changed " + (changed ? "yes" : "no");
    }
    return s;
}

std::vector<Rec> reread(const std::vector<Rec> &recs, const Reader &read) {
    std::vector<Rec> out = recs;
    for (Rec &r : out) {
        r.v[0] = r.v[1] = r.v[2] = r.v[3] = 0;
        r.read = read && read(r.addr, r.v);
    }
    return out;
}

} // namespace bc5::draw_args
