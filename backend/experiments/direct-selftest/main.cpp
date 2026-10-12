// SPDX-License-Identifier: GPL-2.0-only
// direct-selftest: exercises bc5::direct::Device outside any host — the exact submission path
// of the track-B direct mode (private amdgpu device, high-VA scratch IB, policy filter, fence),
// with synthetic IBs and optionally recorded ones. Phase-3 isolation tool (experiment 0016).
//
//   direct-selftest --submit [--render-node PATH] [--ib-file FILE]... [--map-mib N] [--cp-check]
//
// --cp-check (experiment 0052): the CP check of bc5/indirect_check.hpp on five argument triples,
// with the dispatch replaced by a WRITE_DATA (no shader runs): the write must happen for sane
// group counts only. The packets go in the unfiltered prologue (the policy drops COND_WRITE).
//
// Hard rule 5 (CLAUDE.md): --submit runs on the GPU; never in tests or CI.
#include "bc5/direct.hpp"
#include "bc5/indirect_check.hpp"
#include "bc5/policy.hpp"

#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <string>
#include <string_view>
#include <vector>

#ifdef BC5_WITH_AMDGPU
#include <sys/mman.h>
#include <unistd.h>
#endif

namespace {

std::vector<std::uint32_t> load_dwords(const std::string &path) {
    std::vector<std::uint32_t> words;
    std::ifstream in(path, std::ios::binary);
    unsigned char b[4];
    while (in && in.read(reinterpret_cast<char *>(b), 4)) {
        words.push_back(static_cast<std::uint32_t>(b[0]) | (static_cast<std::uint32_t>(b[1]) << 8) |
                        (static_cast<std::uint32_t>(b[2]) << 16) |
                        (static_cast<std::uint32_t>(b[3]) << 24));
    }
    return words;
}

#ifdef BC5_WITH_AMDGPU
std::string g_journal; // --journal FILE: fsync'd line before and after every submit

void journal(const char *text) {
    if (g_journal.empty()) return;
    if (FILE *f = std::fopen(g_journal.c_str(), "a")) {
        std::fputs(text, f);
        std::fflush(f);
        fsync(fileno(f));
        std::fclose(f);
    }
}

bool run(bc5::direct::Device &dev, const char *name, const std::vector<std::uint32_t> &ib) {
    bc5::policy::FilterOptions opt;
    char line[256];
    std::snprintf(line, sizeof(line), "%-24s %4zu dwords ... ", name, ib.size());
    std::fputs(line, stdout);
    std::fflush(stdout);
    journal(line);
    const auto r = dev.submit(ib, opt, 2'000'000'000ull);
    std::snprintf(line, sizeof(line), "%s rc %d%s seq %llu %.2f ms (pass %llu rewrite %llu drop %llu)\n",
                  r.ok ? "OK" : "FAILED", r.rc, r.timed_out ? " TIMEOUT" : "",
                  static_cast<unsigned long long>(r.seq_no), r.submit_ms,
                  static_cast<unsigned long long>(r.filter.passed),
                  static_cast<unsigned long long>(r.filter.rewritten),
                  static_cast<unsigned long long>(r.filter.dropped));
    std::fputs(line, stdout);
    std::fflush(stdout);
    journal(line);
    return r.ok;
}
#endif

} // namespace

int main(int argc, char **argv) {
    std::string node = "/dev/dri/renderD128";
    std::vector<std::string> ib_files;
    std::uint64_t map_mib = 0;
    bool submit = false;
    bool synthetic = true;
    bool cp_check = false;
    std::string journal_path;
    bc5::direct::OpenOptions open_opts;
    for (int i = 1; i < argc; ++i) {
        const std::string_view a = argv[i];
        if (a == "--submit") submit = true;
        else if (a == "--render-node" && i + 1 < argc) node = argv[++i];
        else if (a == "--ib-file" && i + 1 < argc) ib_files.emplace_back(argv[++i]);
        else if (a == "--map-mib" && i + 1 < argc) map_mib = std::stoull(argv[++i]);
        else if (a == "--journal" && i + 1 < argc) journal_path = argv[++i];
        else if (a == "--dedup") open_opts.deduplicate_device = true;
        else if (a == "--legacy-va") open_opts.legacy_scratch_va = true;
        else if (a == "--skip-synthetic") synthetic = false;
        else if (a == "--cp-check") cp_check = true;
        else {
            std::fputs("usage: direct-selftest --submit [--render-node PATH] [--ib-file FILE]... [--map-mib N] [--journal FILE]\n"
                       "                       [--dedup] [--legacy-va] [--skip-synthetic] [--cp-check]\n", stderr);
            return 2;
        }
    }
    if (!submit) {
        std::puts("direct-selftest: nothing done without --submit");
        return 0;
    }
#ifdef BC5_WITH_AMDGPU
    std::fputs("direct-selftest: --submit runs on the GPU (GFX ring); a bad submission can hang or reset the machine.\n", stderr);
    g_journal = journal_path;
    char hdr[160];
    std::snprintf(hdr, sizeof(hdr), "direct-selftest start (dedup %d, legacy-va %d, synthetic %d)\n",
                  open_opts.deduplicate_device ? 1 : 0, open_opts.legacy_scratch_va ? 1 : 0, synthetic ? 1 : 0);
    journal(hdr);
    auto dev = bc5::direct::Device::open(node, open_opts);
    if (!dev) return 1;
    if (cp_check && map_mib == 0) map_mib = 1;
    void *mem = nullptr;
    if (map_mib != 0) {
        // Anonymous memory mapped 1:1, as the host does; touched so it is resident.
        const std::uint64_t bytes = map_mib << 20;
        mem = mmap(nullptr, bytes, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_POPULATE, -1, 0);
        if (mem == MAP_FAILED) return 1;
        const bool ok = dev->map_userptr(reinterpret_cast<std::uint64_t>(mem), bytes);
        std::printf("userptr 1:1 %llu MiB at %p: %s\n", static_cast<unsigned long long>(map_mib), mem, ok ? "ok" : "FAILED");
        if (!ok) return 1;
    }
    if (cp_check) {
        // Per case a 4 KiB page of the mapping: arguments at +0x40, the result word at +0x80, the
        // flag and its confirm word at +0x100. Expected: the result written (1) only when all
        // three counts are within bc5::policy::FilterOptions{}.gpu_check_max.
        const bc5::policy::FilterOptions defaults;
        struct Case {
            std::uint32_t x, y, z;
            bool runs;
        };
        const Case cases[] = {{44, 1, 1, true},
                              {0x7f800000u, 0x7f800000u, 0x7f800000u, false},
                              {28800, 0xff800000u, 1, false},
                              {1, 1, 2000, false},
                              {1u << 20, 1024, 1024, true}};
        int failures = 0;
        for (std::size_t k = 0; k < std::size(cases); ++k) {
            auto *page = reinterpret_cast<volatile std::uint32_t *>(static_cast<char *>(mem) + 0x1000 * k);
            const std::uint64_t va = reinterpret_cast<std::uint64_t>(page);
            page[0x40 / 4] = cases[k].x;
            page[0x44 / 4] = cases[k].y;
            page[0x48 / 4] = cases[k].z;
            page[0x80 / 4] = 0xdeadu;
            page[0x100 / 4] = 0xdeadu;
            page[0x104 / 4] = 0xdeadu;
            // SET_BASE index 1 = the page, DISPATCH_INDIRECT offset 0x40; then the dispatch is
            // replaced by WRITE_DATA result = 1 and the COND_EXEC count set to its 5 dwords.
            const std::vector<std::uint32_t> in = {0xC0021100u, 1u, static_cast<std::uint32_t>(va),
                                                   static_cast<std::uint32_t>(va >> 32), 0xC0011600u, 0x40u, 0x41u};
            std::vector<std::size_t> refs;
            bc5::indirect_check::Stats st;
            auto seq = bc5::indirect_check::apply(in, 0, defaults.gpu_check_max, defaults.gpu_check_draw_max, refs, st);
            bc5::indirect_check::patch(seq, refs, va + 0x100);
            seq.resize(seq.size() - 3);
            seq.back() = 5;
            const std::uint64_t res = va + 0x80;
            seq.insert(seq.end(), {0xC0033700u, (5u << 8) | (1u << 20), static_cast<std::uint32_t>(res),
                                   static_cast<std::uint32_t>(res >> 32), 1u});
            bc5::policy::FilterOptions opt;
            opt.prologue = seq;
            const auto r = dev->submit(std::vector<std::uint32_t>(8, bc5::policy::kNop), opt, 2'000'000'000ull);
            const std::uint32_t got = page[0x80 / 4], flag = page[0x100 / 4], confirm = page[0x104 / 4];
            const bool pass = r.ok && got == (cases[k].runs ? 1u : 0xdeadu) &&
                              flag == (cases[k].runs ? 1u : 0u) && confirm == 0u;
            std::printf("cp-check %u %u %u: %s rc %d%s, result 0x%x flag 0x%x confirm 0x%x -> %s\n", cases[k].x,
                        cases[k].y, cases[k].z, r.ok ? "OK" : "FAILED", r.rc, r.timed_out ? " TIMEOUT" : "", got,
                        flag, confirm, pass ? "as expected" : "WRONG");
            std::fflush(stdout);
            if (!pass) failures++;
            if (!r.ok) return 1;
        }
        std::printf("cp-check: %d wrong\n", failures);
        return failures == 0 ? 0 : 1;
    }
    std::vector<std::uint32_t> ib;
    if (synthetic) {
        ib.assign(8, bc5::policy::kNop);
        if (!run(*dev, "8 nops", ib)) return 1;
        ib.assign(152, bc5::policy::kNop);
        if (!run(*dev, "152 nops", ib)) return 1;
        ib.assign(152, bc5::policy::kNop);
        ib[7] = 0xc0012800u; ib[8] = 0x80000000u; ib[9] = 0x80000000u;
        ib[138] = 0xc0012800u; ib[139] = 0x80000000u; ib[140] = 0x80000000u;
        for (int i = 0; i < 4; ++i) {
            if (!run(*dev, "cc at 8 and 139", ib)) return 1;
        }
    }
    for (const auto &f : ib_files) {
        const auto words = load_dwords(f);
        if (words.empty()) {
            std::fprintf(stderr, "cannot read %s\n", f.c_str());
            return 1;
        }
        if (!run(*dev, f.c_str(), words)) return 1;
    }
    std::puts("direct-selftest: all passed");
    return 0;
#else
    std::fputs("built without BC5_WITH_AMDGPU\n", stderr);
    return 2;
#endif
}
