// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0439 (tag gt439): det test of the journal-gap trigger on a stand-in journal. The wait loop is built as
// the generated umr_watchdog_start builds it (mkpa439.py, BC5_0439_GAP_MS=1000) and runs in sh as the scanner's first
// part. A writer appends lines every 100 ms: first plain lines (not armed: a 1.5-s pause there must not fire), then a
// "frame profile" line (armed), steady lines, a 0.85-s pause (no fire), steady lines, then a stop. The trigger must
// appear once, ~1.0 s after the stop, and not before. BC5_GT439_PLANT_NOARM (armed from the start) must FAIL.
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <sys/stat.h>
#include <thread>
#include <unistd.h>

using clk = std::chrono::steady_clock;
static bool exists(const std::string& p) {
    struct stat st;
    return ::stat(p.c_str(), &st) == 0;
}

int main(int argc, char** argv) {
    const std::string dir = argc > 1 ? argv[1] : ".";
    const std::string J = dir + "/direct.log", T = dir + "/ms439-trigger";
    std::remove(J.c_str());
    std::remove(T.c_str());
    const char* g = "1000";
    std::string wait_loop = "A=0; Z=0; L=$(date +%s%N); while [ ! -e $T ] && kill -0 " + std::to_string(getpid()) + " 2>/dev/null; do "
                            "if [ $A = 0 ]; then grep -q \"^frame profile\" " + J + " 2>/dev/null && { A=1; Z=$(stat -c %s " + J + "); L=$(date +%s%N); echo \"=== gt439 armed at $(date +%T.%N)\"; }; sleep 0.2; continue; fi; "
                            "S=$(stat -c %s " + J + " 2>/dev/null); N=$(date +%s%N); if [ \"$S\" != \"$Z\" ]; then Z=$S; L=$N; "
                            "elif [ $(( (N - L) / 1000000 )) -ge " + std::string(g) + " ]; then echo \"journal gap $(( (N - L) / 1000000 )) ms\" > $T; echo \"=== gt439 fired: no journal growth for $(( (N - L) / 1000000 )) ms at $(date +%T.%N)\"; break; fi; sleep 0.02; done";
#ifdef BC5_GT439_PLANT_NOARM
    wait_loop.replace(wait_loop.find("A=0;"), 4, "A=1;");
#endif
    const std::string cmd = "(sh -c 'T=" + T + "; " + wait_loop + "; echo \"=== loop ended $(date +%T.%N)\"' > " + dir + "/gt.out 2>&1 &)";
    if (std::system(cmd.c_str()) != 0) {
        std::printf("FAIL: the shell did not start\n");
        return 1;
    }
    FILE* f = std::fopen(J.c_str(), "a");
    clk::time_point last_write = clk::now();
    auto put = [&](const char* l) { std::fputs(l, f), std::fflush(f), last_write = clk::now(); };
    auto steady = [&](int n) { for (int i = 0; i < n; i++) put("timing: x\n"), std::this_thread::sleep_for(std::chrono::milliseconds(100)); };
    int fail = 0;
    steady(5);
    std::this_thread::sleep_for(std::chrono::milliseconds(1500)); // not armed yet: no fire
    if (exists(T)) std::printf("FAIL: fired before the first frame-profile line\n"), fail++;
    put("frame profile: t 1.0 s\n");
    steady(10);
    std::this_thread::sleep_for(std::chrono::milliseconds(850)); // a 0.85-s pause: no fire
    if (exists(T)) std::printf("FAIL: fired at a 0.85-s pause\n"), fail++;
    steady(10);
    const auto stop = last_write; // the stop: the last growth of the journal
    double fired_ms = -1;
    while (clk::now() - stop < std::chrono::milliseconds(3000)) {
        if (fired_ms < 0 && exists(T)) fired_ms = std::chrono::duration<double, std::milli>(clk::now() - stop).count();
        std::this_thread::sleep_for(std::chrono::milliseconds(5));
    }
    std::fclose(f);
    std::printf("fired %.0f ms after the stop\n", fired_ms);
    if (fired_ms < 950 || fired_ms > 1300) std::printf("FAIL: not ~1.0 s after the stop\n"), fail++;
    (void)!std::system(("cat " + dir + "/gt.out; echo \"fires: $(grep -c 'gt439 fired' " + dir + "/gt.out)\"").c_str());
    std::printf("%s (%d failures)\n", fail == 0 ? "PASS" : "FAIL", fail);
    return fail == 0 ? 0 : 1;
}
