// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0439 (tag ms439 v2): stand-in dry run of the pre-spawned wave scanner. Starts the host shell exactly as
// the generated umr_watchdog_start does (mkpa439.py), with the umr call swapped for an echo (no GPU access), through the
// real distrobox-host-exec from inside the container; after 2 s writes the trigger as umr_on_timeout does; then checks
// the file: the trigger time, the scanner's wake-up, n scans ~100 ms apart. Then the process exits, and a second
// scanner started without a trigger must end on its own when this process is gone (kill -0).
//   test_ms0439 <n> <dir>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <thread>
#include <unistd.h>

int main(int argc, char **argv) {
    const char n = argc > 1 ? argv[1][0] : '5';
    const std::string dir = argc > 2 ? argv[2] : ".";
    char pre[1400];
    std::snprintf(pre, sizeof(pre),
                  "rm -f %s/ms439-trigger; (distrobox-host-exec sh -c 'T=%s/ms439-trigger; while [ ! -e $T ] && kill -0 %d 2>/dev/null; do sleep 0.01; done; [ -e $T ] || exit 0; "
                  "echo \"=== ms439 trigger $(cat $T), scanner awake $(date +%%T.%%N)\"; for s in $(seq 1 %c); do echo \"=== ms439 scan $s at $(date +%%T.%%N)\"; "
                  "sudo -n /usr/bin/umr -O halt_waves -wa none; sleep 0.1; done' > %s/umr-waves-0.txt 2>&1 &)",
                  dir.c_str(), dir.c_str(), static_cast<int>(getpid()), n, dir.c_str());
    std::string c = pre;
    const std::string real = "sudo -n /usr/bin/umr -O halt_waves -wa none";
    const auto at = c.find(real);
    if (at == std::string::npos) {
        std::printf("FAIL: the umr call is not in the command\n");
        return 1;
    }
    c.replace(at, real.size(), "echo STAND-IN-UMR-SCAN");
    std::printf("rc %d (scanner started)\n", std::system(c.c_str()));
    std::this_thread::sleep_for(std::chrono::seconds(2));
    char cmd[512];
    std::snprintf(cmd, sizeof(cmd), "date +%%T.%%N > %s/ms439-trigger; sync", dir.c_str());
    std::printf("rc %d (trigger written)\n", std::system(cmd));
    std::this_thread::sleep_for(std::chrono::seconds(2));
    return 0;
}
