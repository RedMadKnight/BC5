// SPDX-License-Identifier: GPL-2.0-only
// direct-selftest: exercises bc5::direct::Device outside any host — the exact submission path
// of the track-B direct mode (private amdgpu device, high-VA scratch IB, policy filter, fence),
// with synthetic IBs and optionally recorded ones. Phase-3 isolation tool (experiment 0016).
//
//   direct-selftest --submit [--render-node PATH] [--ib-file FILE]... [--map-mib N] [--cp-check]
//                   [--compute-ring N]
//
// --cp-check (experiment 0052): the CP check of bc5/indirect_check.hpp on five argument triples,
// with the dispatch replaced by a WRITE_DATA (no shader runs): the write must happen for sane
// group counts only. The packets go in the unfiltered prologue (the policy drops COND_WRITE).
//
// --zero-check (experiment 0380): as --cp-check with the zero-dimension guard on and four more
// triples with a 0 count, which must not write the result either.
//
// --compute-ring N (ADR 0009, ladder step 5): Device::submit's own path on compute ring N, one
// job at a time, stopping at the first failure. No shader runs.
//   1 nop        the filter's one-dword NOP (0xffff1000) on the MEC
//   2 timestamps WRITE_DATA with the job timestamps (COPY_DATA, RELEASE_MEM DATA_SEL 3)
//   3 events     RELEASE_MEM BOTTOM_OF_PIPE_TS/5 and CS_DONE/6 with data
//   4 cp-check   the indirect-count check of the MEC form (COND_WRITE, COND_EXEC) on five triples
//                (nine with --zero-check: the zero guard on, four more with a 0 count)
//   5 overlap    a 64 MiB CP DMA fill on the GFX ring, then a compute job: their timestamps overlap
//   6 wait       a compute job waits for a label that a later GFX job writes; a userptr range is
//                mapped while it waits, and a second compute job writes into it
//   7 gds        DMA_DATA fill of GDS and GDS -> memory on the compute ring, the GDS BO listed
//
// Hard rule 5 (CLAUDE.md): --submit runs on the GPU; never in tests or CI.
#include "bc5/direct.hpp"
#include "bc5/indirect_check.hpp"
#include "bc5/policy.hpp"
#include "bc5/selftest_route.hpp" // experiment 0380 (REVIEW-05): which test the command line selects

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

// ADR 0009, ladder step 5 (see the top of the file). mem: 80 MiB mapped 1:1.
int compute_ladder(bc5::direct::Device &dev, char *mem, int ring, bool zero_check) {
    using bc5::direct::kGfxRing;
    constexpr std::uint64_t kTimeout = 2'000'000'000ull;
    dev.set_async(true);
    const auto va = [mem](std::size_t off) { return reinterpret_cast<std::uint64_t>(mem + off); };
    const auto word = [mem](std::size_t off) -> volatile std::uint32_t & {
        return *reinterpret_cast<volatile std::uint32_t *>(mem + off);
    };
    // WRITE_DATA to memory with WR_CONFIRM (Mesa sid.h: DST_SEL 5, WR_CONFIRM bit 20).
    const auto write_data = [](std::uint64_t a, std::uint32_t v) {
        return std::vector<std::uint32_t>{0xC0033700u, (5u << 8) | (1u << 20), static_cast<std::uint32_t>(a),
                                          static_cast<std::uint32_t>(a >> 32), v};
    };
    char line[320];
    const auto report = [&line](const char *name, const bc5::direct::SubmitResult &q, const char *verdict) {
        std::snprintf(line, sizeof(line), "%-11s ring %d %s rc %d%s seq %llu ts %llu..%llu gfx-only %llu -> %s\n", name,
                      q.ring, q.ok ? "OK" : "FAILED", q.rc, q.timed_out ? " TIMEOUT" : "",
                      static_cast<unsigned long long>(q.seq_no), static_cast<unsigned long long>(q.gpu_start),
                      static_cast<unsigned long long>(q.gpu_end),
                      static_cast<unsigned long long>(q.filter.gfx_only_drops), verdict);
        std::fputs(line, stdout);
        std::fflush(stdout);
        journal(line);
    };
    const auto queue = [&dev](const std::vector<std::uint32_t> &ib, const bc5::policy::FilterOptions &opt, int r,
                              bool gds = false) { return dev.submit(ib, opt, kTimeout, gds, r); };
    const auto finish = [&dev](const bc5::direct::SubmitResult &q) {
        auto f = dev.finish(q.seq_no, q.slot, kTimeout);
        f.filter = q.filter;
        return f;
    };
    const auto once = [&](const std::vector<std::uint32_t> &ib, const bc5::policy::FilterOptions &opt, int r,
                          bool gds = false) {
        const auto q = queue(ib, opt, r, gds);
        return q.pending ? finish(q) : q;
    };
    journal("compute ladder start\n");
    bc5::policy::FilterOptions plain;

    // 1 nop
    auto r = once(std::vector<std::uint32_t>(8, bc5::policy::kNop), plain, ring);
    report("1 nop", r, r.ok ? "as expected" : "WRONG");
    if (!r.ok) return 1;

    // 2 timestamps
    word(0) = 0xdead;
    bc5::policy::FilterOptions ts;
    ts.job_timestamps = true;
    r = once(write_data(va(0), 0x2222), ts, ring);
    bool pass = r.ok && word(0) == 0x2222 && r.gpu_start != 0 && r.gpu_end >= r.gpu_start;
    report("2 timestamps", r, pass ? "as expected" : "WRONG");
    if (!pass) return 1;

    // 3 events: RELEASE_MEM (Mesa sid.h: EVENT_TYPE 5:0, EVENT_INDEX 11:8, DATA_SEL 31:29 = 1 for
    // 32 bits of data); BOTTOM_OF_PIPE_TS 0x28 / index 5, then CS_DONE 0x2f / index 6
    word(0x40) = 0xdead;
    word(0x48) = 0xdead;
    std::vector<std::uint32_t> ev = {0xC0064900u, 0x28u | (5u << 8), 1u << 29, static_cast<std::uint32_t>(va(0x40)),
                                     static_cast<std::uint32_t>(va(0x40) >> 32), 0x5150u, 0u, 0u,
                                     0xC0064900u, 0x2fu | (6u << 8), 1u << 29, static_cast<std::uint32_t>(va(0x48)),
                                     static_cast<std::uint32_t>(va(0x48) >> 32), 0x6160u, 0u, 0u};
    r = once(ev, plain, ring);
    pass = r.ok && word(0x40) == 0x5150 && word(0x48) == 0x6160;
    std::snprintf(line, sizeof(line), "  bottom-of-pipe 0x%x cs-done 0x%x\n", word(0x40), word(0x48));
    std::fputs(line, stdout);
    report("3 events", r, pass ? "as expected" : "WRONG");
    if (!pass) return 1;

    // 4 cp-check, MEC form: as --cp-check, the dispatch replaced by WRITE_DATA result = 1
    {
        const bc5::policy::FilterOptions defaults;
        struct Case {
            std::uint32_t x, y, z;
            bool runs;
        };
        const Case cases[] = {{44, 1, 1, true},
                              {0x7f800000u, 0x7f800000u, 0x7f800000u, false},
                              {28800, 0xff800000u, 1, false},
                              {1, 1, 2000, false},
                              {1u << 20, 1024, 1024, true},
                              // experiment 0380 (--zero-check only, with the zero guard on): a 0 count must
                              // not run (Codex review REVIEW-05: they ran before without the guard)
                              {0, 1, 1, false},
                              {1, 0, 1, false},
                              {1, 1, 0, false},
                              {0, 0, 0, false}};
        int wrong = 0;
        const std::size_t n_cases = zero_check ? std::size(cases) : 5;
        for (std::size_t k = 0; k < n_cases; ++k) {
            const std::size_t page = 0x1000 * (k + 1);
            word(page + 0x40) = cases[k].x;
            word(page + 0x44) = cases[k].y;
            word(page + 0x48) = cases[k].z;
            word(page + 0x80) = 0xdead;
            word(page + 0x100) = 0xdead;
            word(page + 0x104) = 0xdead;
            const std::uint64_t args = va(page + 0x40);
            const std::vector<std::uint32_t> in = {0xC0021602u, static_cast<std::uint32_t>(args),
                                                   static_cast<std::uint32_t>(args >> 32), 0x41u};
            std::vector<std::size_t> refs;
            bc5::indirect_check::Stats st;
            auto seq = bc5::indirect_check::apply(in, 0, defaults.gpu_check_max, defaults.gpu_check_draw_max, refs,
                                                  st, true, nullptr, zero_check);
            bc5::indirect_check::patch(seq, refs, va(page + 0x100));
            seq.resize(seq.size() - 4); // the dispatch; COND_EXEC's count becomes the WRITE_DATA's 5
            seq.back() = 5;
            const auto wd = write_data(va(page + 0x80), 1);
            seq.insert(seq.end(), wd.begin(), wd.end());
            bc5::policy::FilterOptions opt;
            opt.prologue = seq;
            r = once(std::vector<std::uint32_t>(8, bc5::policy::kNop), opt, ring);
            const bool ok = r.ok && word(page + 0x80) == (cases[k].runs ? 1u : 0xdeadu) &&
                            word(page + 0x100) == (cases[k].runs ? 1u : 0u) && word(page + 0x104) == 0u;
            std::snprintf(line, sizeof(line), "  cp-check %u %u %u: result 0x%x flag 0x%x confirm 0x%x -> %s\n",
                          cases[k].x, cases[k].y, cases[k].z, word(page + 0x80), word(page + 0x100),
                          word(page + 0x104), ok ? "as expected" : "WRONG");
            std::fputs(line, stdout);
            journal(line);
            if (!r.ok) {
                report("4 cp-check", r, "WRONG");
                return 1;
            }
            if (!ok) wrong++;
        }
        report("4 cp-check", r, wrong == 0 ? "as expected" : "WRONG");
        if (wrong != 0) return 1;
    }

    // 5 overlap: DMA_DATA fills (SRC_SEL 2 data, DST_SEL 3 L2; BYTE_COUNT in the command dword)
    // of 64 MiB at +8 MiB on the GFX ring, then a compute job; the compute job must start before
    // the fill ends (no ordering between the rings, no implicit sync between our own jobs).
    {
        std::vector<std::uint32_t> fill;
        constexpr std::uint32_t kChunk = 1u << 20;
        for (std::uint32_t k = 0; k < 64; ++k) {
            const std::uint64_t d = va((8u << 20) + static_cast<std::size_t>(k) * kChunk);
            fill.insert(fill.end(), {0xC0055000u, (2u << 29) | (3u << 20), 0x5a5a5a5au, 0u,
                                     static_cast<std::uint32_t>(d), static_cast<std::uint32_t>(d >> 32), kChunk});
        }
        word(0x80) = 0xdead;
        const auto g = queue(fill, ts, kGfxRing);
        const auto c = queue(write_data(va(0x80), 0x5555), ts, ring);
        const auto gf = g.pending ? finish(g) : g;
        const auto cf = c.pending ? finish(c) : c;
        pass = gf.ok && cf.ok && word(0x80) == 0x5555 && cf.gpu_start != 0 && cf.gpu_start < gf.gpu_end &&
               word((8u << 20) + (64u << 20) - 4) == 0x5a5a5a5au;
        report("5 fill gfx", gf, gf.ok ? "done" : "WRONG");
        report("5 overlap", cf, pass ? "as expected (compute started inside the fill)" : "WRONG");
        if (!pass) return 1;
    }

    // 6 wait: WAIT_REG_MEM (Mesa sid.h: FUNCTION 2:0 = 3 equal, MEM_SPACE bit 4; address, reference,
    // mask, poll interval) on a label the GFX job writes afterwards, kept for the GPU.
    {
        word(0xc0) = 0;
        word(0xc4) = 0xdead;
        std::vector<std::uint32_t> wait = {0xC0053C00u, 3u | (1u << 4), static_cast<std::uint32_t>(va(0xc0)),
                                           static_cast<std::uint32_t>(va(0xc0) >> 32), 1u, 0xffffffffu, 4u};
        const auto wd = write_data(va(0xc4), 0x6666);
        wait.insert(wait.end(), wd.begin(), wd.end());
        bc5::policy::FilterOptions kept = ts;
        kept.keep_wait_offsets = {0};
        const auto c = queue(wait, kept, ring);
        // mapped while the compute job waits (TLB flush with the compute ring busy)
        void *more = mmap(nullptr, 1u << 20, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_POPULATE, -1, 0);
        const bool mapped = more != MAP_FAILED && dev.map_userptr(reinterpret_cast<std::uint64_t>(more), 1u << 20);
        const bool still_waiting = word(0xc4) == 0xdead;
        const auto g = queue(write_data(va(0xc0), 1), ts, kGfxRing);
        const auto gf = g.pending ? finish(g) : g;
        const auto cf = c.pending ? finish(c) : c;
        pass = cf.ok && gf.ok && mapped && still_waiting && word(0xc4) == 0x6666 && cf.filter.ring_ordered_waits == 1;
        std::snprintf(line, sizeof(line), "  mapped %d, waiting before the GFX job %d, result 0x%x\n", mapped ? 1 : 0,
                      still_waiting ? 1 : 0, word(0xc4));
        std::fputs(line, stdout);
        report("6 wait", cf, pass ? "as expected" : "WRONG");
        if (!pass) return 1;
        auto *m = static_cast<volatile std::uint32_t *>(more);
        m[0] = 0xdead;
        r = once(write_data(reinterpret_cast<std::uint64_t>(more), 0x6767), plain, ring);
        pass = r.ok && m[0] == 0x6767;
        report("6 new range", r, pass ? "as expected" : "WRONG");
        if (!pass) return 1;
    }

    // 7 gds: DMA_DATA DATA -> GDS offset 0 (SRC_SEL 2, DST_SEL 1), GDS -> memory (SRC_SEL 1,
    // DST_SEL 3), the GDS BO on the list (with_gds); no shadow.
    {
        word(0x100) = 0xdead;
        const std::vector<std::uint32_t> gds = {
            0xC0055000u, (2u << 29) | (1u << 20), 0x7777u, 0u, 0u, 0u, 4u,
            0xC0055000u, (1u << 29) | (3u << 20), 0u, 0u, static_cast<std::uint32_t>(va(0x100)),
            static_cast<std::uint32_t>(va(0x100) >> 32), 4u};
        bc5::policy::FilterOptions opt;
        opt.drop_gds = false;
        r = once(gds, opt, ring, true);
        pass = r.ok && word(0x100) == 0x7777;
        std::snprintf(line, sizeof(line), "  gds read back 0x%x\n", word(0x100));
        std::fputs(line, stdout);
        report("7 gds", r, pass ? "as expected" : "WRONG");
        if (!pass) return 1;
    }
    std::puts("compute ladder: all passed");
    journal("compute ladder: all passed\n");
    return 0;
}
#endif

} // namespace

int main(int argc, char **argv) {
    std::string node = "/dev/dri/renderD128";
    std::vector<std::string> ib_files;
    std::uint64_t map_mib = 0;
    bool submit = false;
    bool synthetic = true;
    bool cp_check = false, zero_check = false;
    int compute_ring = -1;
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
        else if (a == "--zero-check") cp_check = zero_check = true; // experiment 0380
        else if (a == "--compute-ring" && i + 1 < argc) compute_ring = std::stoi(argv[++i]);
        else {
            std::fputs("usage: direct-selftest --submit [--render-node PATH] [--ib-file FILE]... [--map-mib N] [--journal FILE]\n"
                       "                       [--dedup] [--legacy-va] [--skip-synthetic] [--cp-check] [--zero-check]\n"
                       "                       [--compute-ring N]\n", stderr);
            return 2;
        }
    }
    const bc5::selftest::Path path = bc5::selftest::route({submit, cp_check, zero_check, compute_ring});
    if (path == bc5::selftest::Path::nothing) {
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
    if (compute_ring >= 0) open_opts.gds_kib = 4; // step 7
    auto dev = bc5::direct::Device::open(node, open_opts);
    if (!dev) return 1;
    if (cp_check && map_mib == 0) map_mib = 1;
    if (compute_ring >= 0 && map_mib < 80) map_mib = 80;
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
    if (path == bc5::selftest::Path::gfx_check) {
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
                              {1u << 20, 1024, 1024, true},
                              // experiment 0380 (--zero-check only): a 0 count must not run (REVIEW-05: missing)
                              {0, 1, 1, false},
                              {1, 0, 1, false},
                              {1, 1, 0, false},
                              {0, 0, 0, false}};
        int failures = 0;
        const std::size_t n_cases = zero_check ? std::size(cases) : 5; // --cp-check: the five of 0052
        for (std::size_t k = 0; k < n_cases; ++k) {
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
            auto seq = bc5::indirect_check::apply(in, 0, defaults.gpu_check_max, defaults.gpu_check_draw_max, refs, st,
                                                  false, nullptr, zero_check);
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
    if (path == bc5::selftest::Path::compute_ladder)
        return compute_ladder(*dev, static_cast<char *>(mem), compute_ring, zero_check);
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
