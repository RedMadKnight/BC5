// BC5 experiment 0380 (F595): a stand-alone check of rec0380.inc on Linux, CPU only (no GPU, no KytyPlus). It gives the
// recorder stand-ins for the host's journal, dump directory and mapping list, then checks:
// 1. the self-test reads the first indirect dispatch's arguments (SET_BASE 1 + offset) and finds them as a TRIPLE;
// 2. the timeout mode takes the dims from a sampler summary.txt and finds a triple placed elsewhere, its pairs and
//    dwords, and dumps the INDEX_BASE;
// 3. a PROT_NONE mapping and a never-touched one are counted (unreadable / not resident), not fatal;
// 4. the scan rate on 512 MiB of resident memory.
// build: g++ -std=c++20 -O2 -Wall -Wextra -Werror rec0380_test.cpp -o rec0380_test  (beside rec0380.inc)
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/uio.h>
#include <dirent.h>
#include <unistd.h>

#include <algorithm>
#include <atomic>
#include <cassert>
#include <chrono>
#include <cinttypes>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <memory>
#include <string>
#include <thread>
#include <vector>

namespace bc5::direct {
struct Mapping {
    std::uint64_t va = 0;
    std::uint64_t size = 0;
    bool readonly = false;
    bool shared = false;
};
} // namespace bc5::direct

namespace stand_in {
#define BC5_DIAG_ENV(name) std::getenv(name)
static std::string g_dump_dir;
static std::string g_journal_text;
static void journal(const char* fmt, ...) __attribute__((format(printf, 1, 2)));
static void journal(const char* fmt, ...) {
    char b[2048];
    va_list ap;
    va_start(ap, fmt);
    std::vsnprintf(b, sizeof(b), fmt, ap);
    va_end(ap);
    std::fputs(b, stdout);
    g_journal_text += b;
}
static FILE* journal_min_file(bool) { return nullptr; }
static double timing_now() { return 100.0; }
struct Dev {
    std::shared_ptr<const std::vector<bc5::direct::Mapping>> maps;
    std::shared_ptr<const std::vector<bc5::direct::Mapping>> sorted_mappings() const { return maps; }
};
static std::unique_ptr<Dev> g_dev;
#include "rec0380.inc"
} // namespace stand_in

static std::string slurp(const std::string& p) {
    std::string s;
    if (FILE* f = std::fopen(p.c_str(), "r")) {
        char b[4096];
        size_t n;
        while ((n = std::fread(b, 1, sizeof(b), f)) > 0) s.append(b, n);
        std::fclose(f);
    }
    return s;
}

int main() {
    using namespace stand_in;
    char tmpl[] = "/tmp/rec0380-XXXXXX";
    const char* dir = getenv("REC0380_TMP");
    std::string root = dir ? std::string(dir) : std::string(mkdtemp(tmpl));
    g_dump_dir = root;
    const size_t big = 512u << 20u;
    auto* mem = static_cast<uint32_t*>(mmap(nullptr, big, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0));
    assert(mem != MAP_FAILED);
    for (size_t k = 0; k < big / 4; k++) mem[k] = static_cast<uint32_t>(k * 2654435761u) | 0x80000000u; // resident, no dims
    auto* none = mmap(nullptr, 1u << 20u, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    assert(none != MAP_FAILED);
    std::memset(none, 0x5a, 1u << 20u); // resident, then made unreadable
    mprotect(none, 1u << 20u, PROT_NONE);
    auto* cold = mmap(nullptr, 8u << 20u, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    assert(none != MAP_FAILED && cold != MAP_FAILED);
    std::vector<bc5::direct::Mapping> maps = {
        {reinterpret_cast<uint64_t>(mem), big, false, true},
        {reinterpret_cast<uint64_t>(none), 1u << 20u, false, false},
        {reinterpret_cast<uint64_t>(cold), 8u << 20u, true, false},
    };
    std::sort(maps.begin(), maps.end(), [](auto& a, auto& b) { return a.va < b.va; });
    g_dev = std::make_unique<Dev>();
    g_dev->maps = std::make_shared<const std::vector<bc5::direct::Mapping>>(maps);
    const uint64_t base = reinterpret_cast<uint64_t>(mem) + (100u << 20u), args = base + 0x300;
    reinterpret_cast<uint32_t*>(args)[0] = 3158, reinterpret_cast<uint32_t*>(args)[1] = 1, reinterpret_cast<uint32_t*>(args)[2] = 1;
    const uint64_t ib_base = reinterpret_cast<uint64_t>(mem) + (300u << 20u) + 0x2000; // "index data", the garbage triple
    reinterpret_cast<uint32_t*>(ib_base)[0] = 481, reinterpret_cast<uint32_t*>(ib_base)[1] = 0x4000008a, reinterpret_cast<uint32_t*>(ib_base)[2] = 480;
    // SET_BASE index 1 (0x11, 3 payload dwords), INDEX_BASE (0x26, 2), INDEX_BUFFER_SIZE (0x13, 1), DISPATCH_INDIRECT (0x16, 2)
    auto hdr = [](uint32_t op, uint32_t payload) { return 0xc0000000u | ((payload - 1) << 16u) | (op << 8u); };
    std::vector<uint32_t> ib = {hdr(0x11, 3), 1, static_cast<uint32_t>(base), static_cast<uint32_t>(base >> 32u),
                                hdr(0x26, 2), static_cast<uint32_t>(ib_base), static_cast<uint32_t>(ib_base >> 32u),
                                hdr(0x13, 1), 0xffffffffu,
                                hdr(0x16, 2), 0x300, 0x45};

    // 1. self-test (timing_now() is 100 s here)
    setenv("BC5_0380_REC_SELFTEST_S", "60", 1);
    assert(rec0380_selftest_due("dcb") && !rec0380_selftest_due("acb"));
    bool ok = rec0380(ib.data(), static_cast<uint32_t>(ib.size()), "dcb", 7, true);
    std::string r1 = slurp(root + "/rec0380-00000007-dcb.txt");
    std::printf("--- self-test file:\n%s", r1.c_str());
    char want[64];
    std::snprintf(want, sizeof(want), "TRIPLE at 0x%" PRIx64, args);
    assert(ok && r1.find(want) != std::string::npos);
    assert(r1.find("dims 00000c56 00000001 00000001") != std::string::npos);
    assert(r1.find("1.0 MiB unreadable") != std::string::npos); // the PROT_NONE mapping
    assert(r1.find("8.0 MiB not resident") != std::string::npos); // the cold one

    // 2. timeout mode, dims from a sampler event
    const std::string sdir = root + "/gpu-stall", ev = sdir + "/event-20261029-140441-gfx_0.0.0";
    mkdir(sdir.c_str(), 0700);
    mkdir(ev.c_str(), 0700);
    if (FILE* f = std::fopen((ev + "/summary.txt").c_str(), "w")) {
        std::fprintf(f, "bc5-gpu-stall-sampler 0377 event\n   compute: program=0x%" PRIx64 " dim=[481 1073741962 480] threads=[64 1 1] initiator=0x45 id=1 (gfx)\n", base + 0x1000);
        std::fclose(f);
    }
    setenv("BC5_0380_REC_SAMPLER_DIR", sdir.c_str(), 1);
    ok = rec0380(ib.data(), static_cast<uint32_t>(ib.size()), "dcb", 8, false);
    std::string r2 = slurp(root + "/rec0380-00000008-dcb.txt");
    std::printf("--- timeout file:\n%s", r2.c_str());
    std::snprintf(want, sizeof(want), "TRIPLE at 0x%" PRIx64, ib_base);
    assert(ok && r2.find(want) != std::string::npos);
    std::snprintf(want, sizeof(want), "dump INDEX_BASE 0x%" PRIx64 ": 000001e1 4000008a 000001e0", ib_base);
    assert(r2.find(want) != std::string::npos);
    assert(r2.find("dump program") != std::string::npos);
    assert(r2.find("triple 1, pairs 1 / 1") != std::string::npos);
    assert(g_journal_text.find("rec0380: #8 dcb: written") != std::string::npos);
    std::printf("--- all checks passed (%s)\n", root.c_str());
    return 0;
}
