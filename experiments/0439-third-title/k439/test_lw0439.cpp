// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0439 (tag lw439): stand-in dry run of the scanner with later dumps (BC5_0439_DUMP_AT_MS). The command
// is built as the generated umr_watchdog_start builds it (mkpa439.py, ms439 v2 + lw439), then the hang dump and the umr
// scan are swapped for echoes (no GPU access), and it runs through the real distrobox-host-exec from the container.
//   test_lw0439 <dir> <mode>
//   mode stuck: the trigger is written at 1 s and stays; the dumps at +300 and +700 ms must both be in their files,
//               each with one stand-in scan, in that order, ~300/700 ms after the wake.
//   mode done:  the trigger is removed at +450 ms (the finisher saw the job end): the +300 file must exist, the +700
//               file must not.
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <unistd.h>

static void swap_all(std::string& c, const std::string& a, const std::string& b) {
    for (size_t at = c.find(a); at != std::string::npos; at = c.find(a, at + b.size())) c.replace(at, a.size(), b);
}

int main(int argc, char** argv) {
    const std::string dir  = argc > 1 ? argv[1] : ".";
    const std::string mode = argc > 2 ? argv[2] : "stuck";
    const char        n    = '1';
    std::string       later;
    {
        std::string l = "300,700";
        for (auto& c : l)
            if (c == ',') c = ' ';
        later = "; for d in " + l + "; do while [ -e $T ] && [ $(( ($(date +%s%N) - W) / 1000000 )) -lt $d ]; do sleep 0.05; done; [ -e $T ] || break; "
                "{ echo \"=== lw439 dump at +${d} ms after the wake, $(date +%T.%N)\"; sudo -n /usr/local/bin/bc5-gpu-hang-dump; echo \"=== lw439 scan at $(date +%T.%N)\"; "
                "sudo -n /usr/bin/umr -O halt_waves -wa none; echo \"=== lw439 done at $(date +%T.%N)\"; } > " + dir + "/umr-waves-0-d$d.txt 2>&1; done";
    }
    char pre[3000];
    std::snprintf(pre, sizeof(pre),
                  "rm -f %s/ms439-trigger; (distrobox-host-exec sh -c 'T=%s/ms439-trigger; while [ ! -e $T ] && kill -0 %d 2>/dev/null; do sleep 0.01; done; [ -e $T ] || exit 0; W=$(date +%%s%%N); "
                  "echo \"=== ms439 trigger $(cat $T), scanner awake $(date +%%T.%%N)\"; echo \"=== ms439 hang dump at $(date +%%T.%%N)\"; sudo -n /usr/local/bin/bc5-gpu-hang-dump; "
                  "echo \"=== ms439 hang dump done at $(date +%%T.%%N)\"; for s in $(seq 1 %c); do echo \"=== ms439 scan $s at $(date +%%T.%%N)\"; "
                  "sudo -n /usr/bin/umr -O halt_waves -wa none; sleep 0.1; done%s' > %s/umr-waves-0.txt 2>&1 &)",
                  dir.c_str(), dir.c_str(), static_cast<int>(getpid()), n, later.c_str(), dir.c_str());
    std::string c = pre;
    const size_t umr_n = std::string(c).find("sudo -n /usr/bin/umr -O halt_waves -wa none") != std::string::npos ? 1 : 0;
    swap_all(c, "sudo -n /usr/bin/umr -O halt_waves -wa none", "echo STAND-IN-UMR-SCAN");
    swap_all(c, "sudo -n /usr/local/bin/bc5-gpu-hang-dump", "echo STAND-IN-HANG-DUMP");
    if (umr_n == 0 || c.find("sudo") != std::string::npos) {
        std::printf("FAIL: the stand-ins did not replace every privileged call\n");
        return 1;
    }
    std::printf("rc %d (scanner started)\n", std::system(c.c_str()));
    std::this_thread::sleep_for(std::chrono::seconds(1));
    char cmd[512];
    std::snprintf(cmd, sizeof(cmd), "date +%%T.%%N > %s/ms439-trigger; sync", dir.c_str());
    std::printf("rc %d (trigger written)\n", std::system(cmd));
    if (mode == "done") {
        std::this_thread::sleep_for(std::chrono::milliseconds(450));
        std::remove((dir + "/ms439-trigger").c_str());
        std::printf("trigger removed at +450 ms\n");
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(1800));
    return 0;
}
