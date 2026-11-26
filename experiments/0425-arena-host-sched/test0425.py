#!/usr/bin/env python3
"""BC5 exp 0425: laptop tests of the patched units' new code (after test_sem0388.py's scheme).
1. Text checks on the patched semaphore.cpp, each with a mutant that must fail.
2. The patched KernelSemaPrivate built against stand-ins for the project's headers, with its Linux paths on (a futex
   stand-in on a mutex and a condition variable, which may wake spuriously as a futex may), and run in every switch
   combination: ping-pong, timeouts racing signals (the count is conserved), Cancel and delete with blocked waiters,
   the catcher's count back at 0. Each case under a 60 s cap: a hang is a failure.
3. C1's block from the patched pthread.cpp, built with a stand-in syscall that records sched_getattr/sched_setattr.
4. The catcher's block from the patched gamePatch.cpp, built with stand-ins and called.
Not covered: the kernel's own futex and sched_setattr (only on the box), ThreadSanitizer (none on this laptop), the
real hook in the title.
usage: test0425.py <patched tree> <clang++> [<repetitions>]"""
import os, re, subprocess, sys, tempfile

TREE, CLANG = sys.argv[1:3]
REPS = int(sys.argv[3]) if len(sys.argv) > 3 else 3
good = bad = 0


def ok(what, passed, detail=""):
    global good, bad
    good, bad = good + (1 if passed else 0), bad + (0 if passed else 1)
    print(("ok   " if passed else "FAIL ") + what + ("" if passed or not detail else "\n     " + detail[:1500]))


def read(rel):
    return open(os.path.join(TREE, rel), encoding="utf-8", newline="").read().replace("\r\n", "\n")


def body(text, head):
    i = text.index(head)
    return text[i:text.index("\n}\n", i)]


# ------------------------------------------------------------------------------------------------ 1. text checks
sema = read("src/kernel/semaphore.cpp")


def one_ready_place(t):
    # every "ready = true" is inside Bc5Ready
    sets = [m.start() for m in re.finditer(r"ready\s*=\s*true", t)]
    b = t.index("void KernelSemaPrivate::Bc5Ready")
    e = t.index("\n}\n", b)
    return len(sets) == 1 and b < sets[0] < e


def wake_after_lock(t):
    for fn in ("Signal", "Cancel"):
        f = body(t, "KernelSemaPrivate::Result KernelSemaPrivate::" + fn)
        # the lock lives in an inner block; the wake comes after the block's closing brace
        inner_end = f.index("\n\t}\n")
        if f.find("Bc5WakeList(&wake)") < inner_end:
            return False
    return True


def waits_for_waker(t):
    w = body(t, "KernelSemaPrivate::Result KernelSemaPrivate::Wait")
    return "bc5_waking.load(std::memory_order_acquire) != 0" in w and w.index("bc5_waking.load") > w.index("Bc5Resumed(&waiter)")


ok("every ready goes through Bc5Ready", one_ready_place(sema))
ok("mutant: a raw ready in WakeWaiters is caught",
   not one_ready_place(sema.replace("Bc5Ready(waiter, Result::Ok); // exp 0425", "waiter->result = Result::Ok; waiter->ready = true;")))
ok("C3's wake is after the lock in Signal and Cancel", wake_after_lock(sema))
mut = sema.replace("\t\twake.swap(m_bc5_wake);\n\t\tif (m_bc5_readied", "\t\twake.swap(m_bc5_wake);\n\t\tBc5WakeList(&wake);\n\t\tif (m_bc5_readied")
ok("mutant: a wake under the lock is caught", not wake_after_lock(mut))
ok("a waiter waits for its waker before it leaves", waits_for_waker(sema))
ok("mutant: no wait for the waker is caught", not waits_for_waker(sema.replace("bc5_waking.load(std::memory_order_acquire) != 0", "false")))
ok("the catcher is out of the lean build", all(s in sema for s in ("#ifndef BC5_LEAN\nstatic std::atomic<int>      g_hi_pending",
                                                                   "#ifndef BC5_LEAN\n// Experiment 0425's catcher, read by")))

# ------------------------------------------------------------------------------------------------ 2. semaphore
STUB = r'''
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include <time.h>
// --- futex, sched_yield, pthread names: stand-ins
#define SYS_futex 202
#define FUTEX_WAIT_PRIVATE 128
#define FUTEX_WAKE_PRIVATE 129
static std::mutex              g_fx_m;
static std::condition_variable g_fx_c;
static std::atomic<uint64_t>   g_fx_wakes {0};
static long syscall(long nr, ...) {
    va_list a; va_start(a, nr);
    auto* addr = va_arg(a, uint32_t*); int op = va_arg(a, int); unsigned val = va_arg(a, unsigned);
    const timespec* ts = va_arg(a, const timespec*); va_end(a);
    if (nr != SYS_futex) return -1;
    if (op == FUTEX_WAKE_PRIVATE) { g_fx_wakes++; std::lock_guard l(g_fx_m); g_fx_c.notify_all(); return 0; }
    std::unique_lock l(g_fx_m);
    if (reinterpret_cast<std::atomic<uint32_t>*>(addr)->load() != val) return -1;
    auto d = std::chrono::seconds(ts->tv_sec) + std::chrono::nanoseconds(ts->tv_nsec);
    g_fx_c.wait_for(l, d);
    return 0;
}
static int sched_yield() { std::this_thread::yield(); return 0; }
thread_local char g_name[16] = "main";
#define pthread_getname_np(a, b, c) (std::strncpy(b, g_name, c), 0)
#define pthread_self() 0
// --- the project's bits
#define KYTY_SYSV_ABI
#define KYTY_CLASS_NO_COPY(x) x(const x&) = delete
#define LIB_NAME(a, b)
#define PRINT_NAME()
#define LOGF(...)
namespace Common {
struct Mutex { std::recursive_mutex m; void Lock() { m.lock(); } void Unlock() { m.unlock(); } };
struct CondVar {
    std::condition_variable_any c;
    bool WaitFor(Mutex* x, unsigned us) { return c.wait_for(x->m, std::chrono::microseconds(us)) == std::cv_status::no_timeout; }
    void Signal() { c.notify_one(); }
    void SignalAll() { c.notify_all(); }
};
struct LockGuard { Mutex& m; explicit LockGuard(Mutex& x): m(x) { m.Lock(); } ~LockGuard() { m.Unlock(); } };
struct Timer {
    std::chrono::steady_clock::time_point s;
    void Start() { s = std::chrono::steady_clock::now(); }
    double GetTimeS() { return std::chrono::duration<double>(std::chrono::steady_clock::now() - s).count(); }
};
struct Thread { static int GetThreadIdUnique() { return 1; } static void SleepMicro(int us) { std::this_thread::sleep_for(std::chrono::microseconds(us)); } };
}
namespace bc5 { namespace load_stat { enum { kSemaSignal, kSemaWait }; inline void count(int, size_t) {} struct Scope { explicit Scope(int) {} }; } }
namespace Libs { namespace LibKernel {
inline int PthreadGetCurrentPriorityForKernel() { return 700; }
inline void KernelDispatchPendingSignalForCurrentThread() {}
} }
namespace LibKernel = Libs::LibKernel;
'''

MAIN = r'''
} // namespace Libs::LibKernel::Semaphore
using namespace Libs::LibKernel::Semaphore;
using R = KernelSemaPrivate::Result;
static int fail(int code, const char* what) { std::printf("FAILED %d %s\n", code, what); return code; }
int main(int argc, char** argv) {
    const std::string mode = argc > 1 ? argv[1] : "pingpong";
    if (mode == "pingpong") {
        // 4 "Job Hi" waiters with an 8 ms timeout loop (as the title's workers), one signaller, 20000 signals of 1.
        auto* sem = new KernelSemaPrivate("JobLoaderSema", true, 0, 1000000);
        std::atomic<int> got {0}; std::atomic<bool> stop {false};
        std::vector<std::thread> ws;
        for (int i = 0; i < 4; i++) ws.emplace_back([&, i] {
            std::snprintf(g_name, sizeof(g_name), "Job Hi %d", i);
            while (!stop) { uint32_t us = 8000; if (sem->Wait(1, &us) == R::Ok) got++; }
        });
        const int N = 20000;
        for (int i = 0; i < N; i++) { if (sem->Signal(1) != R::Ok) return fail(2, "signal"); while (got < i - 2) std::this_thread::yield(); } // paced: the waiters drain and sleep
        auto t0 = std::chrono::steady_clock::now();
        while (got < N && std::chrono::steady_clock::now() - t0 < std::chrono::seconds(20)) std::this_thread::sleep_for(std::chrono::milliseconds(1));
        stop = true; for (auto& t: ws) t.join();
        if (got != N) { std::printf("got %d of %d\n", got.load(), N); return fail(3, "count"); }
#ifndef BC5_LEAN
        if (bc5_0425_hi_pending() != 0) return fail(4, "hi pending not back at 0");
        std::printf("hi marked %llu\n", bc5_0425_hi_marked());
#endif
        delete sem;
    } else if (mode == "timeouts") {
        // waiters with 0-300 us timeouts racing signals; afterwards: signals == Ok returns + what Poll drains
        auto* sem = new KernelSemaPrivate("t", false, 0, 1000000);
        std::atomic<int> got {0}; std::atomic<bool> stop {false};
        std::vector<std::thread> ws;
        for (int i = 0; i < 6; i++) ws.emplace_back([&, i] {
            std::snprintf(g_name, sizeof(g_name), i % 2 ? "Job Hi %d" : "Job Lo %d", i);
            unsigned k = i;
            while (!stop) { uint32_t us = (k++ * 37) % 300; if (sem->Wait(1 + (k % 2), &us) == R::Ok) got += 1 + (k % 2); }
        });
        const int N = 30000;
        for (int i = 0; i < N; i++) sem->Signal(1);
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        stop = true; for (auto& t: ws) t.join();
        int drained = 0; while (sem->Poll(1) == R::Ok) drained++;
        if (got + drained != N) { std::printf("got %d drained %d of %d\n", got.load(), drained, N); return fail(5, "conservation"); }
#ifndef BC5_LEAN
        if (bc5_0425_hi_pending() != 0) return fail(6, "hi pending not back at 0");
#endif
        delete sem;
    } else if (mode == "cancel") {
        auto* sem = new KernelSemaPrivate("c", true, 0, 100);
        std::atomic<int> canceled {0};
        std::vector<std::thread> ws;
        for (int i = 0; i < 5; i++) ws.emplace_back([&] { if (sem->Wait(1, nullptr) == R::Canceled) canceled++; });
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
        int n = -1; if (sem->Cancel(-1, &n) != R::Ok) return fail(7, "cancel");
        for (auto& t: ws) t.join();
        if (n != 5 || canceled != 5) { std::printf("n %d canceled %d\n", n, canceled.load()); return fail(8, "cancel count"); }
        delete sem;
    } else if (mode == "delete") {
        auto* sem = new KernelSemaPrivate("d", true, 0, 100);
        std::atomic<int> deleted {0};
        std::vector<std::thread> ws;
        for (int i = 0; i < 5; i++) ws.emplace_back([&] { uint32_t us = 5000000; if (sem->Wait(1, &us) == R::Deleted) deleted++; });
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
        delete sem; // returns once every waiter has left
        for (auto& t: ws) t.join();
        if (deleted != 5) { std::printf("deleted %d\n", deleted.load()); return fail(9, "delete count"); }
    }
    std::printf("fx wakes %llu\nLIVED\n", static_cast<unsigned long long>(g_fx_wakes.load()));
    return 0;
}
'''

src = re.sub(r'#include "(kernel|common|libs)/[^"]+"[^\n]*\n', "", sema)
src = src.replace('#include "bc5/load_stat.hpp" // experiment 0415 (ls415)\n', "")
for h in ("linux/futex.h", "pthread.h", "sched.h", "sys/syscall.h", "unistd.h"):
    src = re.sub(r"#include <%s>[^\n]*\n" % re.escape(h), "", src)
src = src.replace("#ifdef __linux__", "#if 1")
src = src[:src.index("int KYTY_SYSV_ABI KernelCreateSema")]
bc5inc = os.path.join(TREE, "src")
ENVS = {
    "off": {},
    "C2": {"KYTY_BC5_0425_HANDOFF_US": "300"},
    "C3": {"KYTY_BC5_0425_DIRECT_WAKE": "1"},
    "C2+C3": {"KYTY_BC5_0425_HANDOFF_US": "300", "KYTY_BC5_0425_DIRECT_WAKE": "1"},
}
with tempfile.TemporaryDirectory() as d:
    c = os.path.join(d, "t.cpp")
    with open(c, "w", encoding="utf-8") as f:
        f.write(STUB + src + MAIN)
    for variant, defs in (("normal", []), ("lean", ["-DBC5_LEAN=1"])):
        exe = os.path.join(d, "t-%s.exe" % variant)
        r = subprocess.run([CLANG, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", "-Wno-unused-parameter",
                            "-Wno-deprecated-declarations", "-D_CRT_SECURE_NO_WARNINGS", "-I" + bc5inc] + defs + [c, "-o", exe],
                           capture_output=True, text=True)
        ok("semaphore (%s) builds against the stand-ins, -Wall -Wextra -Werror" % variant, r.returncode == 0, r.stderr)
        if r.returncode != 0:
            continue
        base = {k: v for k, v in os.environ.items() if not k.startswith("KYTY_BC5_0425_")}
        for name, env in ENVS.items():
            for case in ("pingpong", "timeouts", "cancel", "delete"):
                env2 = dict(env)
                if variant == "normal":
                    env2["KYTY_BC5_0425_CATCH"] = "1"
                passed, detail = True, ""
                for rep in range(REPS):
                    try:
                        p = subprocess.run([exe, case], env={**base, **env2}, capture_output=True, text=True, timeout=60)
                        if p.returncode != 0 or "LIVED" not in p.stdout:
                            passed, detail = False, "rc %d\n%s\n%s" % (p.returncode, p.stdout[-600:], p.stderr[-600:])
                            break
                        lines = p.stderr
                        if variant == "normal" and "C3" in name and "direct wake ON" not in lines:
                            passed, detail = False, "no 'direct wake ON' line"
                            break
                        if variant == "normal" and "C2" in name and case == "pingpong" and "exp 0425 handoff:" not in lines:
                            passed, detail = False, "no handoff line"
                            break
                        if variant == "lean" and "exp 0425" in lines:
                            passed, detail = False, "a lean build printed: " + lines[:300]
                            break
                    except subprocess.TimeoutExpired:
                        passed, detail = False, "HANG (60 s cap)"
                        break
                ok("semaphore %s %s %s x%d" % (variant, name, case, REPS), passed, detail)

# ------------------------------------------------------------------------------------------------ 3. C1 block
pth = read("src/kernel/pthread.cpp")
c1 = pth[pth.index("// ---- experiment 0425 C1"):pth.index("// ---- end of experiment 0425 C1")]
C1STUB = r'''
#include <algorithm>
#include <atomic>
#include <cerrno>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include "bc5/env_rule.hpp"
#define SYS_sched_setattr 314
#define SYS_sched_getattr 315
#define SCHED_OTHER 0
#define SCHED_FIFO 1
#define SCHED_BATCH 3
using pid_t = int;
struct Attr { int guest_priority; };
struct PthreadPrivate { Attr* attr; uint64_t host_thread_id; std::string name; };
using Pthread = PthreadPrivate*;
static uint32_t g_policy = SCHED_OTHER; static int32_t g_nice = -15; static uint64_t g_runtime = 3000000; static int g_sets = 0;
static long syscall(long nr, ...) {
    va_list a; va_start(a, nr); int tid = va_arg(a, int); (void)tid; void* p = va_arg(a, void*); va_end(a);
    struct A { uint32_t size, sched_policy; uint64_t sched_flags; int32_t sched_nice; uint32_t sched_priority; uint64_t sched_runtime, sched_deadline, sched_period; };
    auto* at = static_cast<A*>(p);
    if (nr == SYS_sched_getattr) { std::memset(at, 0, sizeof(A)); at->size = 48; at->sched_policy = g_policy; at->sched_nice = g_nice; at->sched_runtime = g_runtime; return 0; }
    if (nr == SYS_sched_setattr) { g_sets++; if (at->size != 48 || at->sched_flags != 0) return -1; g_policy = at->sched_policy; g_nice = at->sched_nice; g_runtime = at->sched_runtime; return 0; }
    return -1;
}
'''
C1MAIN = r'''
int main(int argc, char** argv) {
    const std::string c = argv[1];
    Attr at {argc > 2 ? std::atoi(argv[2]) : 500};
    if (argc > 3) g_policy = static_cast<uint32_t>(std::atoi(argv[3]));
    PthreadPrivate t {&at, 1234, "Job Hi 0"};
    Bc5ApplyWakeSlice(&t, "start");
    std::printf("sets %d runtime %llu nice %d policy %u\n", g_sets, static_cast<unsigned long long>(g_runtime), g_nice, g_policy);
    return 0;
}
'''
with tempfile.TemporaryDirectory() as d:
    cc = os.path.join(d, "c1.cpp")
    with open(cc, "w", encoding="utf-8") as f:
        f.write(C1STUB + c1 + C1MAIN)
    for variant, defs in (("normal", []), ("lean", ["-DBC5_LEAN=1"])):
        exe = os.path.join(d, "c1-%s.exe" % variant)
        r = subprocess.run([CLANG, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", "-D_CRT_SECURE_NO_WARNINGS",
                            "-I" + bc5inc] + defs + [cc, "-o", exe], capture_output=True, text=True)
        ok("C1 block (%s) builds, -Wall -Wextra -Werror" % variant, r.returncode == 0, r.stderr)
        if r.returncode != 0:
            continue
        base = {k: v for k, v in os.environ.items() if not k.startswith("KYTY_BC5_0425_")}
        for name, env, args, want in [
            ("unset: no syscall", {}, ["500"], "sets 0 runtime 3000000 nice -15"),
            ("0: off", {"KYTY_BC5_0425_WAKE_SLICE_US": "0"}, ["500"], "sets 0 "),
            ("abc: off", {"KYTY_BC5_0425_WAKE_SLICE_US": "abc"}, ["500"], "sets 0 "),
            ("300 on a Hi worker: 300 us, nice kept", {"KYTY_BC5_0425_WAKE_SLICE_US": "300"}, ["500"], "sets 1 runtime 300000 nice -15 policy 0"),
            ("50 clamps to 100 us", {"KYTY_BC5_0425_WAKE_SLICE_US": "50"}, ["500"], "sets 1 runtime 100000"),
            ("9999 clamps to 3000 us", {"KYTY_BC5_0425_WAKE_SLICE_US": "9999"}, ["300"], "sets 1 runtime 3000000"),
            ("background band 733 untouched", {"KYTY_BC5_0425_WAKE_SLICE_US": "300"}, ["733"], "sets 0 "),
            ("a FIFO thread untouched", {"KYTY_BC5_0425_WAKE_SLICE_US": "300"}, ["500", "1"], "sets 0 "),
            ("a BATCH thread keeps BATCH", {"KYTY_BC5_0425_WAKE_SLICE_US": "300"}, ["500", "3"], "sets 1 runtime 300000 nice -15 policy 3"),
        ]:
            p = subprocess.run([exe, "x"] + args, env={**base, **env}, capture_output=True, text=True, timeout=30)
            passed = p.returncode == 0 and want in p.stdout
            if passed and variant == "normal" and "sets 1" in want:
                passed = "exp 0425 slice: start tid 1234 'Job Hi 0'" in p.stderr
            if passed and variant == "lean":
                passed = "exp 0425" not in p.stderr
            ok("C1 %s: %s" % (variant, name), passed, p.stdout + p.stderr)

# ------------------------------------------------------------------------------------------------ 4. catcher block
gp = read("src/loader/gamePatch.cpp")
cat = gp[gp.index("// ---- experiment 0425's catcher"):gp.index("// ---- end of experiment 0425's catcher")]
CSTUB = r'''
#include <atomic>
#include <cstdint>
#include <cstdio>
#define KYTY_SYSV_ABI
using bc5_guest_block_fn = void (KYTY_SYSV_ABI*)(void* job, void* block, uint64_t size, uint32_t n1);
static int g_pending = 0;
extern "C" int bc5_0425_hi_pending() { return g_pending; }
extern "C" unsigned long long bc5_0425_hi_marked() { return 7; }
'''
CMAIN = r'''
int main() {
    const uint64_t base = 0x900000000ull;
    auto tgt = reinterpret_cast<bc5_guest_block_fn>(base + 0x4661e50);
    auto other = reinterpret_cast<bc5_guest_block_fn>(base + 0x1000);
    Bc5CatchOwnerCall(base, tgt, 3);      // a registered worker: not counted
    Bc5CatchOwnerCall(base, other, -1);   // owner, other job, no Hi pending
    g_pending = 1;
    Bc5CatchOwnerCall(base, other, -1);   // owner, other job, Hi pending
    Bc5CatchOwnerCall(base, tgt, -1);     // owner, crash-type job, Hi pending
    g_pending = 0;
    Bc5CatchOwnerCall(base, tgt, -1);     // owner, crash-type job, none pending
    std::printf("owner %llu owner_hi %llu target %llu target_hi %llu\n", (unsigned long long)g_bc5_0425_owner.load(),
                (unsigned long long)g_bc5_0425_owner_hi.load(), (unsigned long long)g_bc5_0425_target.load(),
                (unsigned long long)g_bc5_0425_target_hi.load());
    return 0;
}
'''
with tempfile.TemporaryDirectory() as d:
    cc = os.path.join(d, "cat.cpp")
    with open(cc, "w", encoding="utf-8") as f:
        f.write(CSTUB + cat + CMAIN)
    exe = os.path.join(d, "cat.exe")
    r = subprocess.run([CLANG, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", "-Wno-unused-variable", "-D_CRT_SECURE_NO_WARNINGS", cc, "-o", exe],
                       capture_output=True, text=True)
    ok("catcher block builds, -Wall -Wextra -Werror", r.returncode == 0, r.stderr)
    if r.returncode == 0:
        p = subprocess.run([exe], capture_output=True, text=True, timeout=30)
        ok("catcher counts: 4 owner calls, 2 with Hi pending, 2 crash-type, 1 with Hi pending",
           "owner 4 owner_hi 2 target 2 target_hi 1" in p.stdout, p.stdout + p.stderr)
        ok("catcher prints the crash-type lines", p.stderr.count("exp 0425 catch: owner takes crash-type job") == 2, p.stderr)
ok("the hook keeps the title's call and skips the window in pass-through",
   "const bool     wrap      = !g_bc5_jaf_passthrough && wrap_needed(old_index);" in gp and gp.count("fn(job, block, size, n1);") == 1)
ok("lean: pass-through is a constant false and the catcher is compiled out",
   "#else\nstatic constexpr bool g_bc5_jaf_passthrough = false;\n#endif" in gp)
# ------------------------------------------------------------------------------------------------ 5. the PlayGo block
pg = read("src/libs/libPlayGo.cpp")
ok("PlayGo: every one of the 18 entries counts and pays P3's cost", pg.count("BC5_0425_PG_ENTER(__func__); // experiment 0425") == 18)
ok("PlayGo: GetLocus answers through P1", "out_loci[i] = bc5_0425pg::LocusSlow() ? PLAYGO_LOCUS_LOCAL_SLOW : PLAYGO_LOCUS_LOCAL_FAST;" in pg)
pre = body(pg, "int KYTY_SYSV_ABI PlayGoPrefetch(")
ok("PlayGo: P2's delay sits in Prefetch after its checks, before its OK",
   "bc5_0425pg::PrefetchMs()" in pre and pre.index("PrefetchMs") > pre.index("BAD_CHUNK_ID") and "PrefetchMs" not in body(pg, "int KYTY_SYSV_ABI PlayGoGetEta("))
blk = pg[pg.index("// ---- experiment 0425: the PlayGo answers"):pg.index("// ---- end of experiment 0425's PlayGo block")]
PGMAIN = r'''
int main(int argc, char** argv) {
    const auto t0 = std::chrono::steady_clock::now();
    for (int i = 0; i < 3; i++) BC5_0425_PG_ENTER("PlayGoGetLocus");
    const long us = (long)std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now() - t0).count();
    std::printf("slow %d prefetch %ld call %ld waited %ld\n", bc5_0425pg::LocusSlow() ? 1 : 0, bc5_0425pg::PrefetchMs(), bc5_0425pg::CallUs(), us);
    (void)argc; (void)argv;
    return 0;
}
'''
with tempfile.TemporaryDirectory() as d:
    cc = os.path.join(d, "pg.cpp")
    with open(cc, "w", encoding="utf-8") as f:
        f.write("#include <algorithm>\n#include <atomic>\n#include <chrono>\n#include <cstdint>\n#include <cstdio>\n#include <cstdlib>\n#include <cstring>\n#include <thread>\n#include \"bc5/env_rule.hpp\"\n" + blk + PGMAIN)
    for variant, defs in (("normal", []), ("lean", ["-DBC5_LEAN=1"])):
        exe = os.path.join(d, "pg-%s.exe" % variant)
        r = subprocess.run([CLANG, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", "-D_CRT_SECURE_NO_WARNINGS", "-I" + bc5inc] + defs + [cc, "-o", exe],
                           capture_output=True, text=True)
        ok("PlayGo block (%s) builds, -Wall -Wextra -Werror" % variant, r.returncode == 0, r.stderr)
        if r.returncode != 0:
            continue
        base = {k: v for k, v in os.environ.items() if not k.startswith("KYTY_BC5_0425_")}
        for name, env, want, lines in [
            ("unset: exp 0298's answers", {}, "slow 0 prefetch 0 call 0", 0),
            ("LOCUS=slow", {"KYTY_BC5_0425_PLAYGO_LOCUS": "slow"}, "slow 1 prefetch 0 call 0", 0),
            ("LOCUS=fast is not slow", {"KYTY_BC5_0425_PLAYGO_LOCUS": "fast"}, "slow 0 ", 0),
            ("PREFETCH_MS=500", {"KYTY_BC5_0425_PLAYGO_PREFETCH_MS": "500"}, "prefetch 500 ", 0),
            ("PREFETCH_MS=99999 clamps to 5000", {"KYTY_BC5_0425_PLAYGO_PREFETCH_MS": "99999"}, "prefetch 5000 ", 0),
            ("CALL_US=200: three calls wait", {"KYTY_BC5_0425_PLAYGO_CALL_US": "200"}, "call 200 ", 0),
            ("CATCH=1: the first call is counted", {"KYTY_BC5_0425_CATCH": "1"}, "slow 0 ", 1),
        ]:
            p = subprocess.run([exe], env={**base, **env}, capture_output=True, text=True, timeout=30)
            passed = p.returncode == 0 and want in p.stdout
            if passed and name.startswith("CALL_US"):
                passed = int(p.stdout.split("waited ")[1]) >= 600
            if passed and variant == "normal":
                passed = p.stderr.count("exp 0425 playgo: PlayGoGetLocus call #1 on") == lines
            if passed and variant == "lean":
                passed = "exp 0425" not in p.stderr
            ok("PlayGo %s: %s" % (variant, name), passed, p.stdout + p.stderr)
print(f"== {good} passed, {bad} failed")
sys.exit(1 if bad else 0)
