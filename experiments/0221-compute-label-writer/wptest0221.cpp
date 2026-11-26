// BC5 experiment 0221: self-test of the hardware write breakpoints the diagnostic uses, run where the emulator runs
// (the ubuntu distrobox). One process, three threads: the main thread arms counting-only write breakpoints
// (perf_event_open, PERF_TYPE_BREAKPOINT, user space only) on two 8-byte words in every thread of the process,
// then thread A writes word 0 three times and thread B writes word 1 once; the counts must be 3 on A for word 0,
// 1 on B for word 1 and 0 elsewhere. Nothing else is touched; no GPU.
// build: g++ -O1 -pthread -o wptest0221 wptest0221.cpp   run: ./wptest0221
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dirent.h>
#include <linux/hw_breakpoint.h>
#include <linux/perf_event.h>
#include <pthread.h>
#include <sys/syscall.h>
#include <thread>
#include <unistd.h>
#include <vector>
#include <atomic>
#include <chrono>

alignas(8) static volatile unsigned long long g_word[2];
static std::atomic<int> g_go {0}, g_tid[2] {};

struct Wp {
    int fd, tid, which;
};

int main() {
    std::thread ta([] {
        g_tid[0] = static_cast<int>(syscall(SYS_gettid));
        while (g_go.load() == 0) std::this_thread::sleep_for(std::chrono::milliseconds(1));
        for (int k = 0; k < 3; k++) g_word[0] = 0x100 + k;
    });
    std::thread tb([] {
        g_tid[1] = static_cast<int>(syscall(SYS_gettid));
        while (g_go.load() == 0) std::this_thread::sleep_for(std::chrono::milliseconds(1));
        g_word[1] = 0x200;
    });
    while (g_tid[0].load() == 0 || g_tid[1].load() == 0) std::this_thread::sleep_for(std::chrono::milliseconds(1));
    std::vector<Wp> wps;
    int failed = 0, err = 0;
    const auto t1 = std::chrono::steady_clock::now();
    for (int which = 0; which < 2; which++) {
        DIR* d = opendir("/proc/self/task");
        if (d == nullptr) { std::printf("opendir: %s\n", std::strerror(errno)); return 1; }
        while (dirent* e = readdir(d)) {
            const int tid = std::atoi(e->d_name);
            if (tid <= 0) continue;
            perf_event_attr a {};
            a.type           = PERF_TYPE_BREAKPOINT;
            a.size           = sizeof(a);
            a.bp_type        = HW_BREAKPOINT_W;
            a.bp_addr        = reinterpret_cast<unsigned long long>(&g_word[which]);
            a.bp_len         = HW_BREAKPOINT_LEN_8;
            a.exclude_kernel = 1;
            a.exclude_hv     = 1;
            const int fd     = static_cast<int>(syscall(SYS_perf_event_open, &a, tid, -1, -1, PERF_FLAG_FD_CLOEXEC));
            if (fd < 0) { failed++; err = errno; continue; }
            wps.push_back({fd, tid, which});
        }
        closedir(d);
    }
    const double arm_ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t1).count();
    std::printf("armed %zu breakpoints in %.3f ms, %d failed (errno %d: %s)\n", wps.size(), arm_ms, failed, err, err ? std::strerror(err) : "-");
    g_go = 1;
    ta.join();
    tb.join();
    int bad = 0;
    for (const auto& w: wps) {
        unsigned long long c = 0;
        if (read(w.fd, &c, sizeof(c)) != static_cast<ssize_t>(sizeof(c))) { std::printf("read: %s\n", std::strerror(errno)); bad++; continue; }
        const unsigned long long want = (w.which == 0 && w.tid == g_tid[0].load()) ? 3 : (w.which == 1 && w.tid == g_tid[1].load()) ? 1 : 0;
        if (c != 0 || want != 0) std::printf("word %d thread %d: %llu writes (want %llu)\n", w.which, w.tid, c, want);
        if (c != want) bad++;
        close(w.fd);
    }
    std::printf("%s\n", (bad == 0 && !wps.empty()) ? "PASS" : "FAIL");
    return bad == 0 && !wps.empty() ? 0 : 1;
}
