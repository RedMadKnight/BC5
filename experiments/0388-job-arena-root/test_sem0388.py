#!/usr/bin/env python3
"""BC5 exp 0388: targeted regressions for the job-table read and the count snapshot, on the laptop.
Text checks on the patched semaphore.cpp, each with a mutant that must fail, then the patched code built against small
stand-ins for the project's headers and run. The job table is unmapped on the laptop, so a read of it kills the process:
TRACE and the unpaired wait must live, and the two switches that read the table must die.
usage: test_sem0388.py <patched tree> <clang++> <backend include dir>"""
import os, re, subprocess, sys, tempfile

TREE, CLANG, INCLUDE = sys.argv[1:4]
good = bad = 0


def ok(what, passed):
    global good, bad
    good, bad = good + (1 if passed else 0), bad + (0 if passed else 1)
    print(("ok   " if passed else "FAIL ") + what)


def body(text, head):
    i = text.index(head)
    return text[i:text.index("\n}\n", i)]


def table_guarded(t):
    calls = re.findall(r".*Bc5TargetJobOpen\(sem\).*", body(t, "static void Bc5OwnerPushSpin"))
    return len(calls) == 2 and "(by_target || tgt_trace) && Bc5TargetJobOpen(sem)" in calls[0] and "done = !Bc5TargetJobOpen(sem)" in calls[1]


def count_safe(t):
    if "__atomic_load_n" in t or "m_bc5_count.load" not in body(t, "KernelSemaPrivate::Result KernelSemaPrivate::Wait"):
        return False
    store = "m_bc5_count.store(m_count"
    signal, cancel, wait = (body(t, "KernelSemaPrivate::Result KernelSemaPrivate::" + n) for n in ("Signal", "Cancel", "Wait"))
    spin_end = wait.index("Common::LockGuard lock(m_mutex)")
    return signal.index(store) > signal.index("WakeWaiters();") and store in cancel and store in wait[spin_end:]


text = open(f"{TREE}/src/kernel/semaphore.cpp", encoding="utf-8", newline="").read().replace("\r\n", "\n")
ok("the table read is guarded", table_guarded(text))
ok("mutant: an unguarded read is caught", not table_guarded(text.replace("(by_target || tgt_trace) && Bc5TargetJobOpen(sem)", "Bc5TargetJobOpen(sem)")))
ok("the count is read through the snapshot only", count_safe(text))
ok("mutant: an atomic load of m_count is caught", not count_safe(text.replace("m_bc5_count.load(std::memory_order_relaxed)", "__atomic_load_n(&m_count, __ATOMIC_RELAXED)")))
first = "\tm_count = (set_count < 0 ? m_init_count : set_count);\n\tm_bc5_count.store(m_count, std::memory_order_relaxed);\n"
ok("mutant: a write with no snapshot is caught", not count_safe(text.replace(first, first.split("\n")[0] + "\n")))

STUB = r'''
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <cstdio>
#include <mutex>
#include <string>
#include <thread>
#include <time.h>
#define CLOCK_MONOTONIC 1
static int bc5_clock(int, struct timespec* t) {
    auto n = std::chrono::steady_clock::now().time_since_epoch();
    t->tv_sec = static_cast<time_t>(std::chrono::duration_cast<std::chrono::seconds>(n).count());
    t->tv_nsec = static_cast<long>(std::chrono::duration_cast<std::chrono::nanoseconds>(n).count() % 1000000000);
    return 0;
}
#define clock_gettime bc5_clock
#define pthread_getname_np(a, b, c) std::strcpy(b, "game-main")
#define pthread_self() 0
#define KYTY_SYSV_ABI
#define KYTY_CLASS_NO_COPY(x) x(const x&) = delete
#define LIB_NAME(a, b)
#define PRINT_NAME()
#define BC5_DIAG_ENV(x) nullptr
#define LOGF(...)
#define OK 0
#define KERNEL_ERROR_EINVAL 1
#define KERNEL_ERROR_ETIMEDOUT 2
#define KERNEL_ERROR_ECANCELED 3
#define KERNEL_ERROR_EACCES 4
#define KERNEL_ERROR_ENOMEM 5
#define KERNEL_ERROR_ENOENT 6
#define KERNEL_ERROR_ESRCH 7
#define KERNEL_ERROR_EBUSY 8
#define EXIT_NOT_IMPLEMENTED(x)
using KernelUseconds = unsigned;
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
struct Thread { static int GetThreadIdUnique() { return 1; } static void SleepMicro(int) {} };
}
namespace Libs { namespace LibKernel {
inline int PthreadGetCurrentPriorityForKernel() { return 700; }
inline void KernelDispatchPendingSignalForCurrentThread() {}
namespace Semaphore { class KernelSemaPrivate; using KernelSema = KernelSemaPrivate*; }
} }
namespace LibKernel = Libs::LibKernel;
'''

MAIN = r'''
}
using namespace Libs::LibKernel::Semaphore;
int main() {
    KernelSemaPrivate sem("JobLoaderSema", true, 0, 1000);
    // a blocked waiter, marked by the signal; then one that finds the snapshot raised
    std::thread waiter([&] {
        uint32_t us = 2000000;
        auto r = sem.Wait(1, &us);
        std::printf("blocked wait %d\n", r == KernelSemaPrivate::Result::Ok);
    });
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
    const uint64_t before = g_bc5_wait_returns.load();
    if (sem.Signal(1) != KernelSemaPrivate::Result::Ok) return 2;
    Bc5OwnerPushSpin(&sem, before);
    waiter.join();
    if (sem.Bc5Marked() != 1 || sem.Bc5Returned() != 1) return 3;
    sem.Signal(1);
    uint32_t us = 100000;
    if (sem.Wait(1, &us) != KernelSemaPrivate::Result::Ok) return 4;
    us = 0;
    if (sem.Poll(1) != KernelSemaPrivate::Result::TimedOut) return 5;
    std::printf("LIVED\n");
    return 0;
}
'''

src = re.sub(r'#include "(kernel|common|libs)/[^"]+"[^\n]*\n', "", text)
src = src[:src.index("class PosixSemPrivate")].replace('#include <pthread.h>\n', "")
cut = src.index("int KYTY_SYSV_ABI KernelWaitSema")
src = src[:cut]
with tempfile.TemporaryDirectory() as d:
    c = os.path.join(d, "t.cpp")
    exe = os.path.join(d, "t.exe")
    with open(c, "w", encoding="utf-8") as f:
        f.write(STUB + src + MAIN)
    r = subprocess.run([CLANG, "-std=c++20", "-O1", "-Wall", "-Wno-unused-function", "-Wno-unused-parameter", "-Wno-deprecated-declarations", "-I" + INCLUDE, c, "-o", exe], capture_output=True, text=True)
    ok("the patched code builds against the stand-ins", r.returncode == 0)
    if r.returncode != 0:
        print(r.stderr[:1500])
    else:
        BASE = {k: v for k, v in os.environ.items() if not k.startswith("KYTY_BC5_0388_")}

        def run(**env):
            p = subprocess.run([exe], env={**BASE, **env}, capture_output=True, text=True, timeout=30)
            return p.returncode, p.stdout

        for name, env, lives in [
            ("no switch", {}, True),
            ("TRACE alone", {"KYTY_BC5_0388_TRACE": "1"}, True),
            ("the unpaired wait with TRACE", {"KYTY_BC5_0388_PUSH_UNTIL_RETURN_US": "500", "KYTY_BC5_0388_TRACE": "1"}, True),
            ("the unpaired wait, TRACE off", {"KYTY_BC5_0388_PUSH_UNTIL_RETURN_US": "500"}, True),
            ("the paired wait", {"KYTY_BC5_0388_PUSH_UNTIL_PAIRED_US": "500"}, True),
            ("the waiter's spin", {"KYTY_BC5_0388_WAIT_SPIN_US": "50"}, True),
            ("the targeted wake", {"KYTY_BC5_0388_TARGETED_WAKE": "1"}, True),
            ("the target wait reads the table", {"KYTY_BC5_0388_PUSH_UNTIL_TARGET_US": "500"}, False),
            ("TARGET_TRACE reads the table", {"KYTY_BC5_0388_TARGET_TRACE": "1"}, False),
        ]:
            rc, out = run(**env)
            ok(f"{name}: {'lives' if lives else 'dies on the unmapped table'} (rc {rc})", (rc == 0 and "LIVED" in out) if lives else (rc != 0 and "LIVED" not in out))
print(f"== {good} passed, {bad} failed")
sys.exit(1 if bad else 0)
