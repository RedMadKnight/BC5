#!/usr/bin/env python3
"""BC5 experiment 0385: compiles the real experiment 0385 lines of backend/src/direct.cpp on the laptop, under the backend's own
warning flags. direct.cpp as a whole needs libdrm and Linux headers, so this cuts those lines out of the file, by their text, into a
unit with stand-in declarations of the libdrm calls they use. It proves the lines compile against the real lake_probe.hpp and
policy.hpp; it says nothing about the calls at run time, and the whole file is first compiled by the box's private build.
usage: python check_wiring.py <work dir>"""
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
LLVM = pathlib.Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\Llvm\x64")
src = (REPO / "backend/src/direct.cpp").read_text(encoding="utf-8")


def between(a, b):
    i = src.index(a)
    return src[i:src.index(b, i)]


fields = between("    // Experiment 0385: BC5_DIRECT_LAKE_CTL=<file>", "    void *shadow_cpu = nullptr;\n")
opening = between('    if (const char *e = std::getenv("BC5_DIRECT_LAKE_CTL"); env_on(e)) { // experiment 0385',
                  "    if (d->impl_->env_args_copy) {")
closing = between("    if (impl_->lake_bo) { // experiment 0385", "    if (impl_->args_slot) { // experiment 0380 (F574)\n")
submit = between("    if (impl_->lake && !comp) { // experiment 0385", "    r.prep_tracker_ms = now_ms() - t_phase;")
listing = between("    if (impl_->lake_bo) bos.push_back(impl_->lake_bo);", "    bool draws = !short_possible;")

unit = """#include "bc5/env_flag.hpp"
#include "bc5/lake_probe.hpp"
#include "bc5/policy.hpp"
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <vector>
using namespace bc5;
// stand-ins for libdrm's amdgpu.h and amdgpu_drm.h, only what these lines call
struct bo_s; struct va_s; struct dev_s;
using amdgpu_bo_handle = bo_s *; using amdgpu_va_handle = va_s *; using amdgpu_device_handle = dev_s *;
struct amdgpu_bo_alloc_request { std::uint64_t alloc_size, phys_alignment; std::uint32_t preferred_heap; };
enum amdgpu_gpu_va_range { amdgpu_gpu_va_range_general };
#define AMDGPU_GEM_DOMAIN_GTT 2u
#define AMDGPU_VA_RANGE_32_BIT 1ull
#define AMDGPU_VM_PAGE_READABLE 2ull
#define AMDGPU_VM_PAGE_WRITEABLE 4ull
#define AMDGPU_VA_OP_MAP 1u
#define AMDGPU_VA_OP_UNMAP 2u
int amdgpu_bo_alloc(amdgpu_device_handle, amdgpu_bo_alloc_request *, amdgpu_bo_handle *);
int amdgpu_bo_cpu_map(amdgpu_bo_handle, void **);
int amdgpu_bo_cpu_unmap(amdgpu_bo_handle);
int amdgpu_bo_free(amdgpu_bo_handle);
int amdgpu_va_range_alloc(amdgpu_device_handle, amdgpu_gpu_va_range, std::uint64_t, std::uint64_t, std::uint64_t, std::uint64_t *, amdgpu_va_handle *, std::uint64_t);
int amdgpu_va_range_free(amdgpu_va_handle);
int amdgpu_bo_va_op_raw(amdgpu_device_handle, amdgpu_bo_handle, std::uint64_t, std::uint64_t, std::uint64_t, std::uint64_t, std::uint32_t);
struct Impl {
    amdgpu_device_handle dev = nullptr;
""" + fields + """};
struct Dev { std::unique_ptr<Impl> impl_; };
void opening(Dev *d) {
""" + opening + """}
void closing(Dev &self) {
    auto &impl_ = self.impl_;
""" + closing + """}
void submit(Dev &self, std::vector<std::uint32_t> &main_out, const policy::FilterOptions &opt, bool comp, std::vector<amdgpu_bo_handle> &bos) {
    auto &impl_ = self.impl_;
""" + submit + listing + """}
"""
out = pathlib.Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=True)
tu = out / "direct_wiring.cpp"
tu.write_text(unit, encoding="utf-8")
os.environ["PATH"] = str(LLVM / "lib" / "clang" / "22" / "lib" / "windows") + os.pathsep + os.environ["PATH"]
r = subprocess.run([str(LLVM / "bin" / "clang++.exe"), "-std=c++20", "-fsyntax-only", "-Wall", "-Wextra", "-Wpedantic", "-Wshadow", "-Wconversion",
                    "-Wsign-conversion", "-Werror", "-Wno-deprecated-declarations", "-Wno-missing-field-initializers", "-D_CRT_SECURE_NO_WARNINGS",
                    "-I", str(REPO / "backend/include"), str(tu)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
print(r.stdout[-3000:])
print(f"wiring compile rc {r.returncode}; {len(unit.splitlines())} lines, the real lines from direct.cpp between the stand-ins")
sys.exit(r.returncode)
