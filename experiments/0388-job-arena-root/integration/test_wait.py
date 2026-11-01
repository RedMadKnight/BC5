#!/usr/bin/env python3
"""BC5 exp 0388, the integration: the job push wait in the patched kernel/semaphore.cpp, on the laptop.
Text checks with mutants, then the unit's own code built against the stand-ins of test_sem0388.py, run on a fake job table
in a buffer. Normal and lean both: lean must not hold the trace. usage: test_wait.py <patched tree> <clang++> <backend include dir>"""
import os, re, subprocess, sys, tempfile

TREE, CLANG, INCLUDE = sys.argv[1:4]
HERE = os.path.dirname(os.path.abspath(__file__))
good = bad = 0


def ok(what, passed):
    global good, bad
    good, bad = good + (1 if passed else 0), bad + (0 if passed else 1)
    print(("ok   " if passed else "FAIL ") + what)


def called_after_signal(t):
    return re.search(r"auto result = sem->Signal\(count\);\n\n\tBc5JobPushWait\(sem\);\n", t) is not None


def gated(t):
    body = t[t.index("static void Bc5JobPushWait"):]
    gate = body.find("base == 0 || !sem->Bc5Job()")
    return 0 <= gate < body.index("target_job_open")


def trace_in_lean_guard(t):
    i = t.index('BC5_DIAG_ENV("KYTY_BC5_JOB_PUSH_TRACE")')
    return t.rfind("#ifndef BC5_LEAN", 0, i) > t.rfind("#endif", 0, i)


text = open(f"{TREE}/src/kernel/semaphore.cpp", encoding="utf-8", newline="").read().replace("\r\n", "\n")
ok("the wait follows the signal", called_after_signal(text))
ok("mutant: a dropped call is caught", not called_after_signal(text.replace("\tBc5JobPushWait(sem);\n", "")))
ok("the table is read only after the gate", gated(text))
ok("mutant: a dropped gate is caught", not gated(text.replace("base == 0 || !sem->Bc5Job()", "base == 0")))
ok("the trace is inside the lean guard", trace_in_lean_guard(text))
ok("mutant: a trace outside it is caught", not trace_in_lean_guard(text.replace("#ifndef BC5_LEAN\n\tstatic const bool trace", "\tstatic const bool trace")))
g = open(f"{TREE}/src/loader/runtimeLinker.cpp", encoding="utf-8", newline="").read()
ok("the loader calls the wait, and no fix", "GamePatch::ApplyJobPushWait(" in g and "ApplyJobArenaFix" not in g)

STUB = re.search(r"STUB = r'''(.*?)'''", open(f"{HERE}/../test_sem0388.py", encoding="utf-8").read(), re.S).group(1)
STUB = STUB.replace("#define BC5_DIAG_ENV(x) nullptr\n", "#include <cinttypes>\n#include <cstdlib>\n#include <cstring>\n#ifdef BC5_LEAN\n#define BC5_DIAG_ENV(x) static_cast<const char*>(nullptr)\n#else\n#define BC5_DIAG_ENV(x) std::getenv(x)\n#endif\n")

MAIN = r'''
}
#include <thread>
#include <vector>
using namespace Libs::LibKernel::Semaphore;
namespace jw = bc5::job_push_wait;
static std::vector<unsigned char> g_image(jw::kJobTable + 0x2000);
static std::vector<uint64_t> g_list(8), g_jobs(64);
static uint64_t base() { return reinterpret_cast<uint64_t>(g_image.data()); }
template <class T> static void put(uint64_t a, T v) { *reinterpret_cast<T*>(a) = v; }
static void open_job(const KernelSemaPrivate* sem, int started) {
    const uint64_t e = base() + jw::kJobTable;
    put<uint64_t>(e + jw::kJobSema, reinterpret_cast<uint64_t>(sem));
    put<int>(e + jw::kJobPendingN, 1);
    put<uint64_t>(e + jw::kJobPending, reinterpret_cast<uint64_t>(g_list.data()));
    put<uint32_t>(e + jw::kJobGeneration, 7);
    put<int>(e + jw::kJobLive, 1);
    put<uint64_t>(e + jw::kJobObjects, reinterpret_cast<uint64_t>(g_jobs.data()));
    g_list[0] = 7ull << 32u;
    const uint64_t job = reinterpret_cast<uint64_t>(g_jobs.data());
    put<uint64_t>(job + 0x10, base() + jw::kCrashJobFn);
    put<int>(job + jw::kJobStarted, started);
    put<int>(job + jw::kJobTotal, 4);
}
static double wait_us(KernelSemaPrivate* sem) {
    const int64_t t = Bc5NowNs();
    Bc5JobPushWait(sem);
    return static_cast<double>(Bc5NowNs() - t) / 1000.0;
}
int main() {
    KernelSemaPrivate sem("JobLoaderSema", true, 0, 1000), other("OtherSema", true, 0, 1000);
    open_job(&sem, 0);
    if (wait_us(&sem) > 500) return 2;            // off until enabled: the table is not read
    bc5_job_push_wait_enable(base());
    if (wait_us(&other) > 500) return 3;          // another semaphore
    const double full = wait_us(&sem);
    if (full < 1900 || full > 20000) return 4;    // an open job: the bound
    open_job(&sem, 4);
    if (wait_us(&sem) > 500) return 5;            // nothing left to do
    open_job(&sem, 0);
    std::atomic<bool> go {false}, ready {false};
    std::thread closer([&go, &ready] { // spins: a sleep and a thread's start are too coarse on the laptop
        ready = true;
        while (!go.load()) {}
        const int64_t t = Bc5NowNs();
        while (Bc5NowNs() - t < 300000) {}
        put<int>(reinterpret_cast<uint64_t>(g_jobs.data()) + jw::kJobStarted, 4);
    });
    while (!ready.load()) {}
    go = true;
    const double early = wait_us(&sem);
    closer.join();
    if (early > 1900) return 6;                   // the job closed: the wait ends
    std::printf("LIVED %.0f %.0f\n", full, early);
    return 0;
}
'''

src = re.sub(r'#include "(kernel|common|libs)/[^"]+"[^\n]*\n', "", text)
src = src[:src.index("class PosixSemPrivate")].replace("#include <pthread.h>\n", "")
src = src[:src.index("int KYTY_SYSV_ABI KernelWaitSema")]
with tempfile.TemporaryDirectory() as d:
    c = os.path.join(d, "t.cpp")
    with open(c, "w", encoding="utf-8") as f:
        f.write(STUB + src + MAIN)
    for name, flags in (("normal", []), ("lean", ["-DBC5_LEAN=1"])):
        exe = os.path.join(d, name + ".exe")
        r = subprocess.run([CLANG, "-std=c++20", "-O1", "-Wall", "-Wno-unused-function", "-Wno-unused-parameter", "-Wno-deprecated-declarations", "-I" + INCLUDE] + flags + [c, "-o", exe], capture_output=True, text=True)
        ok(f"{name}: the unit's code builds against the stand-ins", r.returncode == 0)
        if r.returncode != 0:
            print(r.stderr[:1500])
            continue
        p = subprocess.run([exe], capture_output=True, text=True, timeout=30)
        ok(f"{name}: off, other semaphore, the bound, nothing to do, closed early (rc {p.returncode}, {p.stdout.strip()})", p.returncode == 0 and "LIVED" in p.stdout)
        has = b"job push wait: pushes" in open(exe, "rb").read()
        ok(f"{name}: the trace is {'absent' if name == 'lean' else 'present'}", has == (name == "normal"))
print(f"== {good} passed, {bad} failed")
sys.exit(1 if bad else 0)
