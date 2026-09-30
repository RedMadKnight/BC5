// SPDX-License-Identifier: GPL-2.0-only
// direct-selftest: exercises bc5::direct::Device outside any host — the exact submission path
// of the track-B direct mode (private amdgpu device, high-VA scratch IB, policy filter, fence),
// with synthetic IBs and optionally recorded ones. Phase-3 isolation tool (experiment 0016).
//
//   direct-selftest --submit [--render-node PATH] [--ib-file FILE]... [--map-mib N]
//
// Hard rule 5 (CLAUDE.md): --submit runs on the GPU; never in tests or CI.
#include "bc5/direct.hpp"
#include "bc5/policy.hpp"

#include <cstdint>
#include <cstdio>
#include <fstream>
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
    std::snprintf(line, sizeof(line), "%s rc %d%s %.2f ms (pass %llu rewrite %llu drop %llu)\n",
                  r.ok ? "OK" : "FAILED", r.rc, r.timed_out ? " TIMEOUT" : "", r.submit_ms,
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
    std::string journal_path;
    for (int i = 1; i < argc; ++i) {
        const std::string_view a = argv[i];
        if (a == "--submit") submit = true;
        else if (a == "--render-node" && i + 1 < argc) node = argv[++i];
        else if (a == "--ib-file" && i + 1 < argc) ib_files.emplace_back(argv[++i]);
        else if (a == "--map-mib" && i + 1 < argc) map_mib = std::stoull(argv[++i]);
        else if (a == "--journal" && i + 1 < argc) journal_path = argv[++i];
        else {
            std::fputs("usage: direct-selftest --submit [--render-node PATH] [--ib-file FILE]... [--map-mib N] [--journal FILE]\n", stderr);
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
    journal("direct-selftest start\n");
    auto dev = bc5::direct::Device::open(node);
    if (!dev) return 1;
    if (map_mib != 0) {
        // Anonymous memory mapped 1:1, as the host does; touched so it is resident.
        const std::uint64_t bytes = map_mib << 20;
        void *mem = mmap(nullptr, bytes, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_POPULATE, -1, 0);
        if (mem == MAP_FAILED) return 1;
        const bool ok = dev->map_userptr(reinterpret_cast<std::uint64_t>(mem), bytes);
        std::printf("userptr 1:1 %llu MiB at %p: %s\n", static_cast<unsigned long long>(map_mib), mem, ok ? "ok" : "FAILED");
        if (!ok) return 1;
    }
    std::vector<std::uint32_t> ib;
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
