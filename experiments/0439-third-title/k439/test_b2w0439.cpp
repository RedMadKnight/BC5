// SPDX-License-Identifier: GPL-2.0-only
// BC5 exp 0439 bake 2 (tags lw439, fw439): det test of the completion-bound word and the watchdog's per-thread wait
// slots, copies of mkb2439_add.py's functions.
//   lw: BC5_DIRECT_WAIT_MS unset, empty, junk, out of range -> 2000 ms; 100..60000 taken. The plant BC5_B2W_PLANT_LW
//       (no range check) must FAIL.
//   fw: slots set by "threads" 0..3; the oldest non-zero wins; a cleared slot drops out; all clear -> 0. The plant
//       BC5_B2W_PLANT_FW (the newest wins: the old single global's behaviour) must FAIL.
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#ifdef _WIN32 // the laptop's clang (no POSIX environment calls); the box builds it with g++
static int setenv(const char* n, const char* v, int) { return _putenv_s(n, v); }
static int unsetenv(const char* n) { return _putenv_s(n, ""); }
#endif

static uint64_t lw_parse() { // lw439_wait_ns without the static cache
    uint64_t ms = 2000;
    if (const char* e = std::getenv("BC5_DIRECT_WAIT_MS"); e != nullptr && *e != 0) {
        char*          end = nullptr;
        const uint64_t x   = std::strtoull(e, &end, 10);
#ifdef BC5_B2W_PLANT_LW
        if (end != nullptr && *end == 0) ms = x;
#else
        if (end != nullptr && *end == 0 && x >= 100 && x <= 60000) ms = x;
#endif
    }
    return ms;
}
static std::atomic<uint64_t> g_fw439[16] = {};
static void fw439_set(int index, uint64_t v) {
    if (index >= 0 && index < 16) g_fw439[index] = v;
}
static uint64_t fw439_oldest() {
    uint64_t m = 0;
    for (const auto& a : g_fw439) {
        const uint64_t x = a.load();
#ifdef BC5_B2W_PLANT_FW
        if (x != 0 && x > m) m = x;
#else
        if (x != 0 && (m == 0 || x < m)) m = x;
#endif
    }
    return m;
}

int main() {
    int f = 0;
    struct C { const char* v; uint64_t want; } cs[] = {{nullptr, 2000}, {"", 2000}, {"12000", 12000}, {"100", 100}, {"60000", 60000},
                                                       {"99", 2000}, {"60001", 2000}, {"12000ms", 2000}, {"x", 2000}, {"-1", 2000}};
    for (const auto& c : cs) {
        if (c.v) setenv("BC5_DIRECT_WAIT_MS", c.v, 1); else unsetenv("BC5_DIRECT_WAIT_MS");
        const uint64_t got = lw_parse();
        if (got != c.want) std::printf("FAIL lw [%s]: %llu, want %llu\n", c.v ? c.v : "(unset)", (unsigned long long)got, (unsigned long long)c.want), f++;
    }
    // fw: thread 2 waits since 100 (the hung GFX job), thread 0 since 500, thread 3 starts a fresh wait at 900
    fw439_set(2, 100), fw439_set(0, 500), fw439_set(3, 900);
    if (fw439_oldest() != 100) std::printf("FAIL fw: the oldest is %llu, want 100\n", (unsigned long long)fw439_oldest()), f++;
    fw439_set(3, 0), fw439_set(3, 950); // a fresh job on another ring must not hide the hung one
    if (fw439_oldest() != 100) std::printf("FAIL fw: after a fresh wait %llu, want 100\n", (unsigned long long)fw439_oldest()), f++;
    fw439_set(2, 0);
    if (fw439_oldest() != 500) std::printf("FAIL fw: after the hung one ended %llu, want 500\n", (unsigned long long)fw439_oldest()), f++;
    fw439_set(0, 0), fw439_set(3, 0);
    if (fw439_oldest() != 0) std::printf("FAIL fw: all clear %llu, want 0\n", (unsigned long long)fw439_oldest()), f++;
    fw439_set(16, 5), fw439_set(-1, 5); // out of range: ignored
    if (fw439_oldest() != 0) std::printf("FAIL fw: an out-of-range index was taken\n"), f++;
    std::printf("%s (%d failures)\n", f == 0 ? "PASS" : "FAIL", f);
    return f == 0 ? 0 : 1;
}
