// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0349 (0346's harness plus --split): an offline harness that runs the backend's passes of a GFX-ring job over the title's IB dumps
// (ib-timeout-*.bin / ib-*.bin: little-endian dwords, the buffer the host handed to the backend) and prints the
// resulting IB packet by packet, plus one line per DISPATCH_INDIRECT with the base the CP check polls. Built twice:
// against main d0c2668's backend (policy::filter + shadow_labels + indirect_check) and against 0346's (the same with
// host_indirect in between and the per-type bases in the check), so the two outputs can be diffed. No GPU, no memory
// of the title: the host's drops (RT off, unmapped) are not replayed, the mappings are "everything" and the counts a
// reader would find are unknown (reported as 1 1 1) — the diff shows which packets each build inserts or changes and
// which addresses its CP polls read, not what the title's memory held. Dumps in submission order carry the bases.
//   --split <max dwords> [--pieces <n>]: cut the final IB as experiment 0349's submit does (default 4 pieces)
//   harness [--split <dw> [--pieces <n>]] [--window <hex>] [--base-gfx <hex>] [--base-comp <hex>] [--shadow] [--packets] <dump.bin>...
#include "bc5/indirect_check.hpp"
#include "bc5/policy.hpp"
#include "bc5/shadow_labels.hpp"
#ifdef BC5_HARNESS_0346
#include "bc5/host_indirect.hpp"
#include "bc5/ib_split.hpp"
#endif

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

namespace {

std::size_t packet_len(std::uint32_t h) {
    const std::uint32_t t = h >> 30;
    if (t == 3 || t == 0) {
        const std::uint32_t c = (h >> 16) & 0x3fff;
        return c == 0x3fff ? 1 : c + 2;
    }
    return 1;
}

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

// One line per packet of the final IB (type-3: opcode and the first dwords), for the diff.
void print_packets(const std::vector<std::uint32_t> &ib) {
    for (std::size_t i = 0; i < ib.size();) {
        const std::uint32_t h = ib[i];
        std::size_t len = packet_len(h);
        if (i + len > ib.size()) len = ib.size() - i;
        if (h >> 30 == 3) {
            std::printf("  %7zu op %02x len %3zu:", i, (h >> 8) & 0xff, len);
            for (std::size_t k = 1; k < len && k < 8; ++k) std::printf(" %08x", ib[i + k]);
            std::printf("\n");
        } else {
            std::printf("  %7zu type %u len %zu\n", i, h >> 30, len);
        }
        i += len;
    }
}

// For every DISPATCH_INDIRECT of the final IB: the SET_BASE index-1 registers in effect (per type, and as one
// register), whether a CP check precedes it and the address its first COND_WRITE polls.
void print_dispatches(const std::vector<std::uint32_t> &ib, std::uint64_t base_gfx, std::uint64_t base_comp) {
    std::uint64_t bases[2] = {base_gfx, base_comp}, single = base_gfx != 0 ? base_gfx : base_comp;
    std::uint64_t poll = 0;
    bool check = false;
    for (std::size_t i = 0; i < ib.size();) {
        const std::uint32_t h = ib[i];
        std::size_t len = packet_len(h);
        if (i + len > ib.size()) len = ib.size() - i;
        if (h >> 30 == 3) {
            const std::uint32_t op = (h >> 8) & 0xff, type = (h >> 1) & 1u;
            if (op == 0x11 && len >= 4 && (ib[i + 1] & 0xfu) == 1) {
                const std::uint64_t a = (static_cast<std::uint64_t>(ib[i + 2]) & ~3ull) | (static_cast<std::uint64_t>(ib[i + 3] & 0xffffu) << 32);
                bases[type] = a;
                single = a;
                std::printf("  set_base at %zu: type %s = 0x%llx\n", i, type ? "compute" : "gfx", static_cast<unsigned long long>(a));
            } else if (op == 0x45 && len >= 8 && !check) { // the first COND_WRITE of a check
                poll = (static_cast<std::uint64_t>(ib[i + 2]) & ~3ull) | (static_cast<std::uint64_t>(ib[i + 3] & 0xffffu) << 32);
                check = true;
            } else if (op == 0x16 && len == 3) {
                const std::uint64_t by_type = bases[type] + ib[i + 1], by_single = single + ib[i + 1];
                std::printf("  dispatch at %zu: type %s offset 0x%x -> by type 0x%llx, by one register 0x%llx; %s%s\n", i, type ? "compute" : "gfx",
                            ib[i + 1], static_cast<unsigned long long>(by_type), static_cast<unsigned long long>(by_single),
                            check ? "checked, polls 0x" : "UNCHECKED", check ? "" : "");
                if (check) std::printf("    poll 0x%llx (%s)\n", static_cast<unsigned long long>(poll), poll == by_type ? "= by type" : (poll == by_single ? "= by one register" : "DIFFERS from both"));
                check = false;
            } else if (op == 0x15) {
                check = false;
            }
        }
        i += len;
    }
}

} // namespace

int main(int argc, char **argv) {
    std::uint64_t window = 0, base_gfx = 0, base_comp = 0;
    bool shadow = false, packets = false, zeroed = false;
    std::size_t split_max = 0, split_pieces = 4;
    std::vector<const char *> files;
    for (int a = 1; a < argc; ++a) {
        if (!std::strcmp(argv[a], "--window") && a + 1 < argc) window = std::strtoull(argv[++a], nullptr, 16);
        else if (!std::strcmp(argv[a], "--base-gfx") && a + 1 < argc) base_gfx = std::strtoull(argv[++a], nullptr, 16);
        else if (!std::strcmp(argv[a], "--base-comp") && a + 1 < argc) base_comp = std::strtoull(argv[++a], nullptr, 16);
        else if (!std::strcmp(argv[a], "--shadow")) shadow = true;
        else if (!std::strcmp(argv[a], "--zeroed")) zeroed = true; // the title's SET_BASE 0 seen before the first dump
        else if (!std::strcmp(argv[a], "--packets")) packets = true;
        else if (!std::strcmp(argv[a], "--split") && a + 1 < argc) split_max = std::strtoull(argv[++a], nullptr, 0);
        else if (!std::strcmp(argv[a], "--pieces") && a + 1 < argc) split_pieces = std::strtoull(argv[++a], nullptr, 0);
        else files.push_back(argv[a]);
    }
    if (files.empty()) {
        std::fprintf(stderr, "usage: harness [--window hex] [--base-gfx hex] [--base-comp hex] [--shadow] [--packets] dump.bin...\n");
        return 2;
    }
#ifdef BC5_HARNESS_0346
    std::printf("harness: 0346's backend (host_indirect, per-type bases in the check)\n");
#else
    std::printf("harness: main d0c2668's backend\n");
#endif
    const std::uint32_t max[3] = {1u << 20, 1u << 10, 1u << 10};
    const std::uint32_t draw_max[2] = {1u << 22, 1024};
    const bc5::indirect_check::ProductLimit product;
    for (const char *path : files) {
        const std::vector<std::uint32_t> ib = load(path);
        std::printf("== %s: %zu dwords\n", path, ib.size());
        bc5::policy::FilterOptions opt;
        opt.gpu_check_indirect = true;
        opt.clear_int_sel = true;
        opt.mapped = [](std::uint64_t, std::uint64_t) { return true; };
        std::vector<std::uint32_t> out(ib.size());
        bc5::policy::FilterStats fs;
        bc5::policy::filter(bc5::policy::Policy::builtin(), ib, out, opt, fs);
        std::printf("filter: passed %llu rewritten %llu dropped %llu unsatisfiable-wait drops %llu\n", static_cast<unsigned long long>(fs.passed),
                    static_cast<unsigned long long>(fs.rewritten), static_cast<unsigned long long>(fs.dropped), static_cast<unsigned long long>(fs.unsatisfiable_wait_drops));
#ifdef BC5_HARNESS_0346
        {
            // third version: one register; --base-gfx is its carried value, --zeroed says the title's zeroing was seen
            const bc5::host_indirect::Register carried{base_gfx, zeroed};
            const std::vector<bc5::host_indirect::Region> everything = {{0, ~0ull}};
            const bc5::host_indirect::Reader reader = [](std::uint64_t, std::uint32_t (&c)[3]) { c[0] = c[1] = c[2] = 1; return true; };
            bc5::host_indirect::Stats hs;
            const auto decisions = bc5::host_indirect::resolve_indirect(out, carried, window, everything, reader, bc5::host_indirect::Limits{}, hs);
            for (const auto &d : decisions) {
                if (d.decision == bc5::host_indirect::Decision::Leave) continue;
                std::printf("host_indirect: dispatch at %zu (%s type, program 0x%llx): %s window 0x%llx + offset 0x%llx -> 0x%llx page 0x%llx\n", d.at,
                            d.shader_type ? "compute" : "gfx", static_cast<unsigned long long>(d.program),
                            d.decision == bc5::host_indirect::Decision::Rewrite ? "REWRITE" : "DROP", static_cast<unsigned long long>(d.window),
                            static_cast<unsigned long long>(d.address - d.window), static_cast<unsigned long long>(d.address), static_cast<unsigned long long>(d.page));
            }
            const bool ok = bc5::host_indirect::rewrite_verified(out, decisions, hs);
            std::printf("host_indirect: left non-zero %u, left never-set %u, rewritten %u, dropped no-candidate %u unmapped %u unreadable %u insane %u; overflow NOPs %u; rewrite_verified %s; register out 0x%llx%s; window seen 0x%llx\n",
                        hs.left_nonzero, hs.left_never_set, hs.rewritten, hs.dropped_no_candidate, hs.dropped_unmapped, hs.dropped_unreadable, hs.dropped_insane, hs.nop_on_overflow,
                        ok ? "ok" : "OVERFLOW", static_cast<unsigned long long>(hs.register_out.base), hs.register_out.zeroed ? " (zeroed)" : "",
                        static_cast<unsigned long long>(hs.window_seen));
            base_gfx = hs.register_out.base;
            zeroed = hs.register_out.zeroed;
            if (hs.window_seen != 0) window = hs.window_seen;
        }
#endif
        if (shadow) {
            bc5::shadow_labels::Stats ss;
            const bool ok = bc5::shadow_labels::apply(out, 64, ss);
            std::printf("shadow: labels %u writes %u waits %u overflow %u %s\n", ss.labels, ss.writes, ss.waits, ss.overflow, ok ? "" : "FAILED");
        }
        std::vector<std::size_t> refs;
        bc5::indirect_check::Stats st;
        const std::uint64_t base_before_gfx = base_gfx, base_before_comp = base_comp;
        out = bc5::indirect_check::apply(out, 0, max, draw_max, refs, st, false, &product);
        std::printf("check: checked %u (staircase %u) unbased %u NOP-ed %u inserted %u -> %zu dwords\n", st.checked, st.product_checked, st.unbased, st.conditional, st.inserted_dwords, out.size());
#ifdef BC5_HARNESS_0346
        if (split_max != 0) { // experiment 0349: the cut over the final IB, as Device::submit does it
            bc5::ib_split::Stats ss;
            const auto pcs = bc5::ib_split::split(out, out.size(), split_max, split_pieces, 64, 8, ss);
            if (pcs.empty()) std::printf("split: FAILED at %zu: %s (%u COND_EXEC ranges)\n", ss.failed_at, ss.too_many_pieces ? "more pieces would be needed" : "no boundary", ss.cond_ranges);
            else {
                std::printf("split: %zu dwords over %zu into %zu pieces:", out.size(), split_max, pcs.size());
                for (const auto &p : pcs) std::printf(" [%zu +%zu]", p.off, p.n);
                std::printf("; %u COND_EXEC ranges, %u fallback cuts\n", ss.cond_ranges, ss.fallback_cuts);
            }
        }
#endif
        print_dispatches(out, base_before_gfx, base_before_comp);
        if (packets) print_packets(out);
#ifndef BC5_HARNESS_0346
        // main's backend carries nothing; the bases seen in this IB are kept only for the next file's report
        for (std::size_t i = 0; i < out.size();) {
            const std::uint32_t h = out[i];
            std::size_t len = packet_len(h);
            if (i + len > out.size()) len = out.size() - i;
            if (h >> 30 == 3 && ((h >> 8) & 0xff) == 0x11 && len >= 4 && (out[i + 1] & 0xfu) == 1) {
                const std::uint64_t a = (static_cast<std::uint64_t>(out[i + 2]) & ~3ull) | (static_cast<std::uint64_t>(out[i + 3] & 0xffffu) << 32);
                (((h >> 1) & 1u) ? base_comp : base_gfx) = a;
            }
            i += len;
        }
#endif
    }
    return 0;
}
