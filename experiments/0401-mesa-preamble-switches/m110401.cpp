// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e11, tag m11: the CPU test of mkm110401.py's src/libs/bc5LleAgc.cpp, the switches
// BC5_DIRECT_RESET_REPLAY_ACB, BC5_DIRECT_RESET_LABELS, BC5_DIRECT_LEARN_GUEST_ONLY and BC5_DIRECT_RESET_LABEL_JOURNAL. It
// calls the unit through its seams (bc5_m11_0401_*, and cap's bc5_cap0401_journal_* for the journal):
//   - the switches as the unit reads them;
//   - the learned decision for a fault whose window holds the test's "guest memory" and for one whose window does not;
//   - an acb head's marks made at the current reopen count and at an older one;
//   - the lost label writes: five pending writes (one superseded, one already held, one outside guest memory), the
//     completion thread's two calls at a timed-out job, the reopen; the test's memory and the journal lines after it;
//     a second reopen with nothing kept for it; with the journal switch, the lines 5 s and 30 s after the reopen.
// "Guest memory" is a static buffer of the test's own (bc5_m11_0401_guest replaces the unit's guest-range test). No game,
// no GPU, no window, no sound device, no network: the direct path is never opened, nothing is submitted anywhere.
// Modes. "on" and "off" take the four switches from the environment as the box sets them (on: each on; off: each =0 or
// unset) and refuse a mismatch (rc 2).
// Output: one line per failed check, then "m110401: <mode> N of N; end"; without "; end" something failed. Exit 0 only
// after the end line. A watchdog ends a hang after 60 s with a FAIL line (exit 3). Run each mode in a fresh directory (it
// writes ./m110401-j there).
// Build: link0411.py ... --gate m110401.cpp <out> (compiled with the main unit's command, linked with every emulator
//        object but main.cpp.o).
// usage: m110401 on | off

#include <atomic>
#include <chrono>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

extern "C" int      bc5_cap0401_journal_open(const char* dir);
extern "C" void     bc5_cap0401_journal_flush();
extern "C" int      bc5_m11_0401_switch(int k);
extern "C" void     bc5_m11_0401_guest(uint64_t lo, uint64_t hi);
extern "C" int      bc5_m11_0401_learn_refused(uint64_t fault_addr);
extern "C" void     bc5_m11_0401_plw_add(uint64_t label, uint64_t value, int is64, uint64_t seq);
extern "C" uint64_t bc5_m11_0401_timeout(uint64_t seq);
extern "C" void     bc5_m11_0401_reopen(int ok);
extern "C" uint64_t bc5_m11_0401_reopens();
extern "C" uint64_t bc5_m11_0401_head(uint64_t head_reopens);

namespace {

const char* const kNames[4] = {"BC5_DIRECT_RESET_REPLAY_ACB", "BC5_DIRECT_RESET_LABELS", "BC5_DIRECT_LEARN_GUEST_ONLY", "BC5_DIRECT_RESET_LABEL_JOURNAL"};
std::atomic<const char*> g_case {"start"};
int                      g_pass = 0, g_total = 0;

void Check(bool ok, const char* what, int line, const std::string& got = "") {
    g_total++;
    if (ok) {
        g_pass++;
        return;
    }
    std::printf("m110401: FAIL [%s] line %d: %s%s%s\n", g_case.load(), line, what, got.empty() ? "" : " -- got: ", got.c_str());
}
#define CHECK(c)     Check((c), #c, __LINE__)
#define CHECKW(c, g) Check((c), #c, __LINE__, (g))

bool EnvOn(const char* e) {
    return e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
}

// The journal's lines that contain "e11: ", read back from the file after a flush.
std::vector<std::string> E11Lines(const std::filesystem::path& file) {
    bc5_cap0401_journal_flush();
    std::ifstream            f(file);
    std::vector<std::string> out;
    for (std::string l; std::getline(f, l);) {
        if (l.find("e11: ") != std::string::npos) out.push_back(l);
    }
    return out;
}
size_t Count(const std::vector<std::string>& lines, const std::string& part) {
    size_t n = 0;
    for (const auto& l: lines) n += l.find(part) != std::string::npos ? 1 : 0;
    return n;
}
std::string Hex(uint64_t v) {
    char b[32];
    std::snprintf(b, sizeof(b), "0x%" PRIx64, v);
    return b;
}

alignas(8) uint64_t g_mem[4] = {0, 0, 9, 0}; // the test's guest memory; g_mem[2] holds 9 already

} // namespace

int main(int argc, char** argv) {
    if (argc != 2 || (std::strcmp(argv[1], "on") != 0 && std::strcmp(argv[1], "off") != 0)) {
        std::printf("m110401: usage: m110401 on | off (in a fresh directory)\n");
        return 2;
    }
    const bool on = std::strcmp(argv[1], "on") == 0;
    for (const char* n: kNames) {
        if (EnvOn(std::getenv(n)) != on) {
            std::printf("m110401: the argument says %s but %s is %s\n", argv[1], n, std::getenv(n) ? std::getenv(n) : "unset");
            return 2;
        }
    }
    std::thread([] {
        std::this_thread::sleep_for(std::chrono::seconds(60));
        std::printf("m110401: FAIL watchdog: case \"%s\" still running after 60 s\n", g_case.load());
        std::fflush(stdout);
        std::_Exit(3);
    }).detach();
    setenv("BC5_DIRECT_JOURNAL_QUIET", "0", 1);
    std::error_code             ec;
    const std::filesystem::path dir = std::filesystem::current_path() / "m110401-j";
    std::filesystem::create_directories(dir, ec);
    std::filesystem::remove(dir / "direct.log", ec);
    CHECK(bc5_cap0401_journal_open(dir.string().c_str()) == 1);
    const auto log = dir / "direct.log";

    g_case = "switches";
    for (int k = 0; k < 4; k++) CHECK(bc5_m11_0401_switch(k) == (on ? 1 : 0));
    CHECK(bc5_m11_0401_switch(4) == -1);

    g_case = "learned";
    const uint64_t G = reinterpret_cast<uintptr_t>(&g_mem[0]);
    bc5_m11_0401_guest(G, G + sizeof(g_mem));
    const uint64_t F = 0x706ab000ull; // the 22:42 fault's page; its window is 0x6e000000+0x6000000
    CHECK(G + sizeof(g_mem) <= 0x6e000000ull || G >= 0x74000000ull);
    CHECK(bc5_m11_0401_learn_refused(G) == 0);
    CHECK(bc5_m11_0401_learn_refused(F) == (on ? 1 : 0));

    g_case = "head";
    CHECK(bc5_m11_0401_reopens() == 0);
    CHECK(bc5_m11_0401_head(0) == 2);
    CHECK(bc5_m11_0401_head(1) == (on ? 0u : 2u));

    g_case = "lost writes";
    bc5_m11_0401_plw_add(G, 1, 0, 10);                      // superseded by the next one
    bc5_m11_0401_plw_add(G, 2, 0, 11);                      // written
    bc5_m11_0401_plw_add(G + 8, 0x1122334455667788ull, 1, 11); // written (64-bit)
    bc5_m11_0401_plw_add(F, 7, 0, 12);                      // not in guest memory
    bc5_m11_0401_plw_add(G + 16, 9, 1, 12);                 // held already
    CHECK(bc5_m11_0401_timeout(11) == 0);                   // forget_label_writes cleared the list, in both modes
    bc5_m11_0401_reopen(1);
    CHECK(bc5_m11_0401_reopens() == 1);
    CHECKW(g_mem[0] == (on ? 2u : 0u), Hex(g_mem[0]));
    CHECKW(g_mem[1] == (on ? 0x1122334455667788ull : 0u), Hex(g_mem[1]));
    CHECKW(g_mem[2] == 9u, Hex(g_mem[2]));
    auto l1 = E11Lines(log);
    if (on) {
        CHECKW(Count(l1, "e11: switches: BC5_DIRECT_RESET_REPLAY_ACB on, BC5_DIRECT_RESET_LABELS on, BC5_DIRECT_LEARN_GUEST_ONLY on, BC5_DIRECT_RESET_LABEL_JOURNAL on") == 1,
               l1.empty() ? "" : l1[0]);
        CHECK(Count(l1, "e11: fault 0x706ab000: no guest range in its window 0x6e000000+0x6000000, not learned") == 1);
        CHECK(Count(l1, "e11: acb head (m110401): 2 GPU marks from before reopen 0 dropped") == 1);
        CHECK(Count(l1, "e11: lost write ") == 5);
        CHECK(Count(l1, ", superseded; memory holds 0x0") == 1);
        CHECK(Count(l1, "value 0x7 (32-bit), seq 12 ring ") == 1 && Count(l1, "; not in guest memory, read 0x0") == 1);
        CHECKW(Count(l1, "e11: reopen 1 (ok): 5 label writes of the lost jobs: 1 held already, 1 not in guest memory, 1 superseded, 2 written (BC5_DIRECT_RESET_LABELS on)") == 1,
               l1.empty() ? "" : l1.back());
    } else {
        CHECKW(l1.empty(), l1.empty() ? "" : l1[0]);
    }

    g_case = "reopen with nothing kept";
    bc5_m11_0401_reopen(1);
    CHECK(bc5_m11_0401_reopens() == 2);
    CHECK(bc5_m11_0401_head(0) == (on ? 0u : 2u));
    CHECK(bc5_m11_0401_head(2) == 2);
    auto l2 = E11Lines(log);
    if (on) {
        CHECK(Count(l2, "e11: reopen 2: no lost label writes kept for it (0 kept for reopen 1, dropped)") == 1);
    } else {
        CHECKW(l2.empty(), l2.empty() ? "" : l2[0]);
    }

    g_case = "5 s and 30 s";
    if (on) {
        std::this_thread::sleep_for(std::chrono::seconds(32));
        auto l3 = E11Lines(log);
        CHECK(Count(l3, "e11: 5 s after reopen 1: 3 of 5 lost label writes held") == 1);
        CHECK(Count(l3, "e11: 30 s after reopen 1: 3 of 5 lost label writes held") == 1);
        CHECK(Count(l3, " s after reopen 1: label ") == 10);
        CHECK(Count(l3, "e11: 5 s after reopen 1: label " + Hex(G + 8) + " holds 0x1122334455667788 (the lost value 0x1122334455667788)") == 1);
    }

    std::fflush(stderr);
    std::printf("m110401: %s %d of %d%s\n", argv[1], g_pass, g_total, g_pass == g_total ? "; end" : "");
    std::fflush(stdout);
    std::_Exit(g_pass == g_total ? 0 : 1); // the unit's journal thread may still be detached: no static destructors under it
}
