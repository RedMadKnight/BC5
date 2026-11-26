#!/usr/bin/env python3
"""BC5 exp 0388, the integration: ApplyJobPushWait from the patched loader/gamePatch.cpp, built against stand-ins and run on a
fake image: on by default where the code is the known one, whatever the title, off otherwise, and a small image is not read.
usage: test_apply.py <patched tree> <clang++> <backend include dir>"""
import os, subprocess, sys, tempfile

TREE, CLANG, INCLUDE = sys.argv[1:4]
text = open(f"{TREE}/src/loader/gamePatch.cpp", encoding="utf-8", newline="").read()
a = text.index("// BC5 (experiment 0388): the job push wait, arm J")
block = text[a:text.index("bool Apply(const std::filesystem::path& plan_path, Program* program) {")]

SRC = r'''
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include "bc5/job_push_wait.hpp"
#ifdef _WIN32
static int setenv(const char* k, const char* v, int) { return _putenv_s(k, v); }
static int unsetenv(const char* k) { return _putenv_s(k, ""); }
#endif
struct Program { const void* elf; uint64_t base_vaddr; uint64_t base_size; };
static uint64_t g_enabled = 0;
extern "C" void bc5_job_push_wait_enable(uint64_t base) { g_enabled = base; }
''' + block + r'''
int main() {
    using namespace bc5::job_push_wait;
    static std::vector<uint8_t> image(kJobTable + 0x4000);
    Program p {&image, reinterpret_cast<uint64_t>(image.data()), image.size()};
    auto check = [&](bool code, const char* sw, Program* prog, bool want) {
        g_enabled = 0;
        std::memcpy(image.data() + kSiteOffset, kSiteExpected.data(), kSiteExpected.size());
        if (!code) image[kSiteOffset] = 0;
        if (sw != nullptr) setenv("KYTY_BC5_JOB_PUSH_WAIT", sw, 1); else unsetenv("KYTY_BC5_JOB_PUSH_WAIT");
        const bool on = ApplyJobPushWait(prog);
        return on == want && (g_enabled == p.base_vaddr) == want;
    };
    Program none {nullptr, 0, 0};
    Program small {&image, reinterpret_cast<uint64_t>(image.data()), 0x100000}; // another executable: its size stops the look
    if (!check(true, nullptr, &p, true)) return 2;     // on by default, whatever the title is
    if (!check(true, "0", &p, false)) return 3;        // the off switch
    if (!check(false, nullptr, &p, false)) return 4;   // other code
    if (!check(true, nullptr, &small, false)) return 5; // too small to read
    if (!check(true, nullptr, &none, false)) return 6; // nothing loaded
    if (!check(true, nullptr, nullptr, false)) return 7;
    std::printf("LIVED\\n");
    return 0;
}
'''

with tempfile.TemporaryDirectory() as d:
    c, exe = os.path.join(d, "t.cpp"), os.path.join(d, "t.exe")
    open(c, "w", encoding="utf-8").write(SRC)
    r = subprocess.run([CLANG, "-std=c++20", "-O1", "-Wall", "-Wno-deprecated-declarations", "-I" + INCLUDE, c, "-o", exe], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[:1500])
        sys.exit(1)
    p = subprocess.run([exe], capture_output=True, text=True, timeout=30)
    print(p.stderr, end="")
    print("rc", p.returncode, p.stdout.strip())
    sys.exit(0 if p.returncode == 0 and "LIVED" in p.stdout else 1)
