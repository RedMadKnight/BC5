#!/usr/bin/env python3
"""BC5 exp 0388, the integration: ApplyJobPushWait from the patched loader/gamePatch.cpp, built against stand-ins and run on a
fake image: on by default for the title with its known code, off otherwise, and the site is read before the fix writes.
usage: test_apply.py <patched tree> <clang++> <backend include dir>"""
import os, subprocess, sys, tempfile

TREE, CLANG, INCLUDE = sys.argv[1:4]
text = open(f"{TREE}/src/loader/gamePatch.cpp", encoding="utf-8", newline="").read()
a = text.index("// BC5 (experiment 0388): the job push wait, arm J")
block = text[a:text.index("bool Apply(const std::filesystem::path& plan_path, Program* program) {")]

SRC = r'''
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>
#include "bc5/job_arena_fix.hpp"
#include "bc5/job_push_wait.hpp"
#ifdef _WIN32
static int setenv(const char* k, const char* v, int) { return _putenv_s(k, v); }
static int unsetenv(const char* k) { return _putenv_s(k, ""); }
#endif
struct Program { const void* elf; uint64_t base_vaddr; };
static std::string g_title;
static void SystemContentParamSfoGetString(const char*, std::string* s) { *s = g_title; }
namespace Common { static bool EqualNoCase(const std::string& a, const char* b) { return a == b; } }
static uint64_t g_enabled = 0;
extern "C" void bc5_job_push_wait_enable(uint64_t base) { g_enabled = base; }
''' + block + r'''
int main() {
    using namespace bc5::job_arena_fix;
    static std::vector<uint8_t> image(kSiteOffset + 16);
    Program p {&image, reinterpret_cast<uint64_t>(image.data())};
    auto check = [&](const char* title, bool code, const char* sw, Program* prog, bool want) {
        g_title = title;
        g_enabled = 0;
        std::memcpy(image.data() + kSiteOffset, kSiteExpected.data(), kSiteExpected.size());
        if (!code) image[kSiteOffset] = 0;
        if (sw != nullptr) setenv("KYTY_BC5_JOB_PUSH_WAIT", sw, 1); else unsetenv("KYTY_BC5_JOB_PUSH_WAIT");
        const bool on = ApplyJobPushWait(prog);
        return on == want && (g_enabled == p.base_vaddr) == want;
    };
    Program none {nullptr, 0};
    if (!check("PPSA03671", true, nullptr, &p, true)) return 2;  // on by default
    if (!check("PPSA03671", true, "0", &p, false)) return 3;     // the off switch
    if (!check("PPSA03671", false, nullptr, &p, false)) return 4; // another build of the title
    if (!check("PPSA01234", true, nullptr, &p, false)) return 5; // another title
    if (!check("PPSA03671", true, nullptr, &none, false)) return 6; // nothing loaded
    if (!check("PPSA03671", true, nullptr, nullptr, false)) return 7;
    std::printf("LIVED\n");
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
