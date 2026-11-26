// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0367: an offline harness for bc5::full_state::Tracker::emit_prefix. It is built twice, against main's
// backend/src/full_state.cpp and against exp 0367's (candidate C1), and both builds print every prefix they emit,
// packet by packet, so that a plain diff of the two outputs shows any packet that differs. Inputs:
//   - the title's IB dumps given on the command line (little-endian dwords), applied in order to one tracker with no
//     reader (LOAD_* tables and nested IBs unreadable, as the harness has no title memory); the prefix after each;
//   - randomized trackers: SET_CONFIG/CONTEXT/SH/UCONFIG runs at random offsets (past the flat arrays too, into the
//     overflow maps), CLEAR_STATE 0/1/2 (clears, pushes, pops), SET_BASE, INDEX_BASE, INDEX_BUFFER_SIZE, INDEX_TYPE,
//     NUM_INSTANCES; the prefix after each random buffer.
// It also checks candidate C2's reordering (the prefix emitted from the tracker before the buffer is applied, against
// the prefix of a copy taken before applying, as bc5LleAgc.cpp's piece_check does today), and times emit_prefix and the
// tracker copy on a tracker filled like the title's (F72: ~921 context, ~150 SH, ~57 uconfig registers).
//   harness0367 [--quiet] <dump.bin>...      (prints to stdout; timing lines start with "timing")
#include "bc5/full_state.hpp"

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iterator>
#include <random>
#include <span>
#include <vector>

namespace {

using bc5::full_state::Stats;
using bc5::full_state::Tracker;

std::vector<std::uint32_t> load(const char *path) {
    std::ifstream f(path, std::ios::binary);
    std::vector<char> bytes((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
    std::vector<std::uint32_t> ib(bytes.size() / 4);
    for (std::size_t i = 0; i < ib.size(); ++i) {
        std::uint32_t v = 0;
        for (int k = 3; k >= 0; --k) v = (v << 8) | static_cast<unsigned char>(bytes[4 * i + static_cast<std::size_t>(k)]);
        ib[i] = v;
    }
    return ib;
}

std::uint64_t fnv(const std::vector<std::uint32_t> &v) {
    std::uint64_t h = 1469598103934665603ull;
    for (const std::uint32_t x : v) h = (h ^ x) * 1099511628211ull;
    return h;
}

bool quiet = false;
std::uint64_t cases = 0, total_dwords = 0, total_packets = 0;

// Every packet of the prefix on one line: offset, header, body dwords (all of them).
void print_prefix(const char *what, std::uint64_t n, const std::vector<std::uint32_t> &p) {
    cases++;
    total_dwords += p.size();
    std::printf("%s %llu: %zu dwords, fnv %016llx\n", what, static_cast<unsigned long long>(n), p.size(), static_cast<unsigned long long>(fnv(p)));
    for (std::size_t i = 0; i < p.size();) {
        const std::uint32_t h = p[i];
        std::size_t len = 1;
        if ((h >> 30) == 3 || (h >> 30) == 0) {
            const std::uint32_t c = (h >> 16) & 0x3fffu;
            len = c == 0x3fffu ? 1 : c + 2;
        }
        if (i + len > p.size()) len = p.size() - i;
        total_packets++;
        if (!quiet) {
            std::printf("  %6zu %08x", i, h);
            for (std::size_t k = 1; k < len; ++k) std::printf(" %08x", p[i + k]);
            std::printf("\n");
        }
        i += len;
    }
}

void put(std::vector<std::uint32_t> &ib, std::uint8_t op, std::initializer_list<std::uint32_t> body) {
    ib.push_back(0xC0000000u | (static_cast<std::uint32_t>(body.size() - 1) << 16) | (static_cast<std::uint32_t>(op) << 8));
    ib.insert(ib.end(), body);
}

// A random buffer of state packets.
std::vector<std::uint32_t> random_ib(std::mt19937_64 &rng) {
    std::vector<std::uint32_t> ib;
    const std::uint8_t set_ops[] = {0x68, 0x69, 0x76, 0x9b, 0x79, 0x7a};
    const std::uint32_t flat[] = {0xc00, 0x2000, 0x2000, 0x400, 0x400, 0x4000, 0x4000};
    const int packets = static_cast<int>(rng() % 40) + 1;
    for (int p = 0; p < packets; ++p) {
        const unsigned r = static_cast<unsigned>(rng() % 100);
        if (r < 80) { // a SET run
            const int si = static_cast<int>(rng() % 6);
            const std::uint8_t op = set_ops[si];
            const std::uint32_t lim = (rng() % 8 == 0) ? 0x10000u : flat[si == 0 ? 0 : (si <= 1 ? 1 : (si <= 3 ? 3 : 5))];
            std::uint32_t off = static_cast<std::uint32_t>(rng() % lim);
            if (rng() % 10 == 0) off = lim - 1 - static_cast<std::uint32_t>(rng() % 4); // runs across the flat array's end
            const std::uint32_t n = static_cast<std::uint32_t>(rng() % (rng() % 20 == 0 ? 600 : 24)) + 1;
            std::vector<std::uint32_t> body = {off};
            for (std::uint32_t k = 0; k < n; ++k) body.push_back(static_cast<std::uint32_t>(rng()));
            ib.push_back(0xC0000000u | (static_cast<std::uint32_t>(body.size() - 1) << 16) | (static_cast<std::uint32_t>(op) << 8));
            ib.insert(ib.end(), body.begin(), body.end());
        } else if (r < 86) { // CLEAR_STATE cmd 0, 1 (push), 2 (pop)
            put(ib, 0x12, {static_cast<std::uint32_t>(rng() % 3)});
        } else if (r < 90) {
            put(ib, 0x11, {static_cast<std::uint32_t>(rng() % 4), static_cast<std::uint32_t>(rng()), static_cast<std::uint32_t>(rng())});
        } else if (r < 93) {
            put(ib, 0x26, {static_cast<std::uint32_t>(rng()), static_cast<std::uint32_t>(rng())});
        } else if (r < 95) {
            put(ib, 0x13, {static_cast<std::uint32_t>(rng())});
        } else if (r < 97) {
            put(ib, 0x2a, {static_cast<std::uint32_t>(rng() % 3)});
        } else {
            put(ib, 0x2f, {static_cast<std::uint32_t>(rng() % 100)});
        }
    }
    return ib;
}

// A tracker shaped like the title's: context 0x000-0x39f (928), SH 0x00-0x95 (150), uconfig 0x200-0x238 (57).
Tracker title_like() {
    std::vector<std::uint32_t> ib;
    std::vector<std::uint32_t> ctx = {0};
    for (std::uint32_t k = 0; k < 928; ++k) ctx.push_back(0x1000 + k);
    ib.push_back(0xC0000000u | (static_cast<std::uint32_t>(ctx.size() - 1) << 16) | (0x69u << 8));
    ib.insert(ib.end(), ctx.begin(), ctx.end());
    std::vector<std::uint32_t> sh = {0};
    for (std::uint32_t k = 0; k < 150; ++k) sh.push_back(0x2000 + k);
    ib.push_back(0xC0000000u | (static_cast<std::uint32_t>(sh.size() - 1) << 16) | (0x76u << 8));
    ib.insert(ib.end(), sh.begin(), sh.end());
    std::vector<std::uint32_t> uc = {0x200};
    for (std::uint32_t k = 0; k < 57; ++k) uc.push_back(0x3000 + k);
    ib.push_back(0xC0000000u | (static_cast<std::uint32_t>(uc.size() - 1) << 16) | (0x79u << 8));
    ib.insert(ib.end(), uc.begin(), uc.end());
    Tracker t;
    Stats st;
    t.apply(ib, nullptr, st);
    return t;
}

} // namespace

int main(int argc, char **argv) {
    std::vector<const char *> files;
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--quiet") == 0) quiet = true;
        else files.push_back(argv[i]);
    }
    Stats st;
    // 1. the dumps, in order, on one tracker; candidate C2's order checked on a second one
    Tracker t, t2;
    std::uint64_t c2_equal = 0, c2_diff = 0;
    for (std::size_t f = 0; f < files.size(); ++f) {
        const auto ib = load(files[f]);
        const auto before = t2.emit_prefix(); // C2: emitted before the buffer is applied
        const Tracker copy = t;                // today: a copy before the buffer, emitted later
        t.apply(ib, nullptr, st);
        t2.apply(ib, nullptr, st);
        const auto later = copy.emit_prefix();
        (before == later ? c2_equal : c2_diff)++;
        print_prefix("dump", f, t.emit_prefix());
    }
    // 2. randomized trackers
    std::mt19937_64 rng(0x0367);
    for (std::uint64_t n = 0; n < 3000; ++n) {
        Tracker r;
        Tracker r2;
        const int bufs = static_cast<int>(rng() % 6) + 1;
        for (int b = 0; b < bufs; ++b) {
            const auto ib = random_ib(rng);
            const auto before = r2.emit_prefix();
            const Tracker copy = r;
            r.apply(ib, nullptr, st);
            r2.apply(ib, nullptr, st);
            (before == copy.emit_prefix() ? c2_equal : c2_diff)++;
        }
        print_prefix("random", n, r.emit_prefix());
    }
    std::printf("summary: %llu prefixes, %llu dwords, %llu packets; C2 order: %llu equal, %llu different\n", static_cast<unsigned long long>(cases),
                static_cast<unsigned long long>(total_dwords), static_cast<unsigned long long>(total_packets), static_cast<unsigned long long>(c2_equal),
                static_cast<unsigned long long>(c2_diff));
    // 3. timing on a title-like tracker
    const Tracker big = title_like();
    std::size_t sink = 0;
    const int reps = 20000;
    auto t0 = std::chrono::steady_clock::now();
    for (int k = 0; k < reps; ++k) sink += big.emit_prefix().size();
    auto t1 = std::chrono::steady_clock::now();
    for (int k = 0; k < reps; ++k) {
        const Tracker c = big;
        sink += c.count(bc5::full_state::Context);
    }
    auto t2c = std::chrono::steady_clock::now();
    std::fprintf(stderr, "timing: emit_prefix %.2f us per call (%zu dwords), tracker copy %.2f us per copy (sink %zu)\n",
                 std::chrono::duration<double, std::micro>(t1 - t0).count() / reps, big.emit_prefix().size(),
                 std::chrono::duration<double, std::micro>(t2c - t1).count() / reps, sink);
    return 0;
}
