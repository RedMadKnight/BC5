// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0412: the CPU test of guard0412.inc's pure part (no system call, no host). Builds on the laptop and on the box:
//   clang++ -std=c++20 -Wall -Wextra -Werror -I <dir of env_flag.hpp> test0412.cpp -o test0412 && ./test0412
// Prints "test0412: N of N; end" and returns 0 when every check holds.
#include <algorithm>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <string>
#include <vector>

#include "env_flag.hpp"

#define GUARD0412_TEST 1
#include "guard0412.inc"

static int g_n = 0, g_ok = 0;
#define CHECK(...)                                                                \
    do {                                                                         \
        g_n++;                                                                   \
        if (__VA_ARGS__) g_ok++;                                                         \
        else std::printf("FAIL line %d: %s\n", __LINE__, #__VA_ARGS__);                    \
    } while (0)

int main() {
    using namespace g412;
    const uint64_t M = 1ull << 20u;
    { // switches: off forms
        const Cfg c = parse(nullptr, "", "0", nullptr, nullptr, "0", "");
        CHECK(!c.ledger && c.mlock == 0 && !c.f_random && !c.f_dontneed && c.psi == 0.0 && c.cap == 0 && c.apply_ns == 0 && c.bad.empty() && !c.worker());
    }
    { // switches: on forms
        const Cfg c = parse("1", "guest", "random,dontneed", "/games/T", "7.5", "11600", "50");
        CHECK(c.ledger && c.mlock == 2 && c.f_random && c.f_dontneed && c.root == "/games/T/" && c.psi == 7.5 && c.cap == 11600 * M && c.apply_ns == 50'000'000ull);
        CHECK(c.bad.empty() && c.worker());
        CHECK(parse(nullptr, "pinned", nullptr, nullptr, nullptr, nullptr, nullptr).mlock == 1);
        CHECK(parse(nullptr, "1", nullptr, nullptr, nullptr, nullptr, nullptr).mlock == 1);
        const Cfg d = parse(nullptr, nullptr, "dontneed", "/g/", nullptr, nullptr, nullptr);
        CHECK(d.f_dontneed && !d.f_random && d.psi == 10.0 && d.root == "/g/"); // dontneed brings its default threshold
        const Cfg a = parse(nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, "100");
        CHECK(a.apply_ns == 100'000'000ull && !a.worker()); // the put-off alone needs no thread
    }
    { // switches: values that are not understood stay off and are named
        const Cfg c = parse("1", "all", "random", nullptr, "200", "12", "0x10");
        CHECK(c.ledger && c.mlock == 0 && !c.f_random && c.psi == 0.0 && c.cap == 0 && c.apply_ns == 0);
        CHECK(c.bad == " BC5_GUARD_MLOCK BC5_GUARD_FILE BC5_GUARD_PSI BC5_GUARD_PIN_CAP BC5_GUARD_APPLY_MIN_MS");
        CHECK(!parse(nullptr, nullptr, "random", "/", nullptr, nullptr, nullptr).f_random);       // "/" is refused as a root
        CHECK(!parse(nullptr, nullptr, "random", "games", nullptr, nullptr, nullptr).f_random);   // a relative root too
        CHECK(!parse(nullptr, nullptr, "random,", "/g", nullptr, nullptr, nullptr).f_random);     // an empty word
        CHECK(!parse(nullptr, nullptr, "random,drop", "/g", nullptr, nullptr, nullptr).f_random); // an unknown word turns all of it off
    }
    { // ranges
        Ranges r;
        auto   f = r.add(10, 20);
        CHECK(f.size() == 1 && f[0] == std::make_pair<uint64_t, uint64_t>(10, 20) && r.bytes == 10);
        f = r.add(10, 20);
        CHECK(f.empty() && r.bytes == 10 && r.m.size() == 1); // the same range again (a device reopen re-imports)
        f = r.add(30, 40);
        CHECK(f.size() == 1 && r.bytes == 20 && r.m.size() == 2);
        f = r.add(5, 35); // bridges both: fresh parts are 5-10 and 20-30
        CHECK(f.size() == 2 && f[0].first == 5 && f[0].second == 10 && f[1].first == 20 && f[1].second == 30);
        CHECK(r.bytes == 35 && r.m.size() == 1 && r.m.begin()->first == 5 && r.m.begin()->second == 40);
        f = r.add(40, 50); // touching joins
        CHECK(f.size() == 1 && r.m.size() == 1 && r.m.begin()->second == 50 && r.bytes == 45);
        f = r.add(0, 5);
        CHECK(f.size() == 1 && r.m.size() == 1 && r.m.begin()->first == 0 && r.bytes == 50);
        CHECK(r.add(7, 7).empty() && r.add(9, 3).empty() && r.bytes == 50);
        f = r.add(100, 110);
        CHECK(r.overlap(0, 200) == 60 && r.overlap(45, 105) == 10 && r.overlap(50, 100) == 0 && r.overlap(60, 70) == 0 && r.overlap(105, 106) == 1);
        f = r.add(20, 30); // inside
        CHECK(f.empty() && r.bytes == 60);
    }
    { // the ledger: two heaps, one view pair sharing a file range, one pinned range under no view
        Ranges pin;
        pin.add(0, 100 * M);        // heap A, whole
        pin.add(200 * M, 220 * M);  // 20 of heap B's 50
        pin.add(500 * M, 530 * M);  // an orphan: no view
        const std::string a = "A", b = "B", u;
        const std::vector<VIn> v = {{0, 100 * M, &a, true, false}, {200 * M, 50 * M, &b, false, true}, {200 * M, 10 * M, &b, false, true}, {300 * M, 4 * M, &u, false, false},
                                    {0, 0, &a, true, false}};
        const Ledger L = ledger(v, pin);
        CHECK(L.pinned == 150 * M && L.pinned_under == 120 * M && L.orphans == 30 * M && L.reserved_union == 154 * M && L.views == 4);
        CHECK(L.rows.size() == 3 && L.rows[0].name == "A" && L.rows[0].cls == 'E' && L.rows[0].pinned == 100 * M && L.rows[0].reserved == 100 * M && L.rows[0].views == 1);
        CHECK(L.rows[1].name == "B" && L.rows[1].cls == 'L' && L.rows[1].pinned == 30 * M && L.rows[1].reserved == 60 * M && L.rows[1].views == 2); // the shared range counts twice
        CHECK(L.rows[2].name == "(unnamed)" && L.rows[2].cls == 'D' && L.rows[2].pinned == 0);
        CHECK(heaps_text(L, 12, 760) == "A[E] 100/100, B[L] 30/60, (unnamed)[D] 0/4");
        CHECK(heaps_text(L, 1, 760) == "A[E] 100/100, 2 more 30/64");
        CHECK(heaps_text(L, 12, 10) == "3 more 130/164"); // no room: everything goes to the rest
        const Ledger E = ledger({}, pin);
        CHECK(E.rows.empty() && E.orphans == 150 * M && heaps_text(E, 12, 760).empty());
        // the same name, eager and not: two rows
        const std::vector<VIn> w = {{0, 10 * M, &a, true, false}, {10 * M, 10 * M, &a, false, false}};
        CHECK(ledger(w, pin).rows.size() == 2);
    }
    { // PSI
        double s = -1, f = -1;
        CHECK(psi_parse("some avg10=3.90 avg60=1.00 avg300=0.50 total=123\nfull avg10=0.25 avg60=0.10 avg300=0.00 total=45\n", &s, &f) && s == 3.90 && f == 0.25);
        CHECK(!psi_parse("some avg10=3.90 avg60=1.00\n", &s, &f) && !psi_parse(nullptr, &s, &f) && !psi_parse("some avg10=x\nfull avg10=y\n", &s, &f));
    }
    { // meminfo and status keys: a missing key is -1, never 0
        const char* mi = "MemTotal:       15556000 kB\nMemAvailable:    1048576 kB\nUnevictable:     2048 kB\nSwapTotal:       8388608 kB\nSwapFree:        6291456 kB\n";
        CHECK(kv_mib(mi, "MemAvailable") == 1024 && kv_mib(mi, "Unevictable") == 2 && kv_mib(mi, "SwapTotal") == 8192 && kv_mib(mi, "MemTotal") == 15191);
        CHECK(kv_mib(mi, "Mlocked") == -1 && kv_mib(mi, "Swap") == -1 && kv_mib(nullptr, "MemTotal") == -1 && kv_mib("MemAvailable: kB\n", "MemAvailable") == -1);
        CHECK(kv_mib("VmRSS:\t  5120 kB\n", "VmRSS") == 5);
    }
    { // /proc/self/stat: a process name with spaces and parentheses
        unsigned long long mn = 0, mj = 0;
        CHECK(stat_faults("1234 (kyty (emu) x) S 1 1234 1234 0 -1 4194560 777 0 55 0 100 200 0 0 20 0 9 0 12345", &mn, &mj) && mn == 777 && mj == 55);
        CHECK(!stat_faults("1234 (x) S 1 2 3", &mn, &mj) && !stat_faults("no paren", &mn, &mj) && !stat_faults(nullptr, &mn, &mj));
    }
    { // the put-off of learned_apply
        Defer          d;
        const uint64_t ms = 1'000'000ull, min = 50 * ms;
        CHECK(!defer(d, 0, 1, 0, 0) && !d.seen);             // off: never
        CHECK(!defer(d, min, 1, 1000 * ms, 0));               // the first call runs
        CHECK(!defer(d, min, 1, 1001 * ms, 0) && d.deferred == 0); // same layout: learned_apply returns by itself
        CHECK(defer(d, min, 2, 1010 * ms, 0) && d.deferred == 1);  // changed 10 ms after a run: put off
        CHECK(defer(d, min, 3, 1049 * ms, 0) && d.deferred == 2);
        CHECK(!defer(d, min, 3, 1050 * ms, 0) && d.last_gen == 3); // 50 ms after the last run: runs
        CHECK(defer(d, min, 4, 1060 * ms, 0));
        CHECK(!defer(d, min, 4, 1061 * ms, 1) && d.last_reopens == 1); // a device reopen: never put off
        CHECK(!defer(d, min, 4, 1062 * ms, 1));
        CHECK(defer(d, min, 5, 1063 * ms, 1) && !defer(d, min, 5, 1111 * ms, 1) && d.deferred == 4);
    }
    std::printf("test0412: %d of %d; end\n", g_ok, g_n);
    return g_ok == g_n ? 0 : 1;
}
