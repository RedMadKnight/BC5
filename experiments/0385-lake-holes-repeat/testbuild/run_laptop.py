#!/usr/bin/env python3
"""BC5 experiment 0385: the lake module's unit tests on the laptop, with VS's clang, ASan and UBSan off the box.
usage: python run_laptop.py <work dir>
Runs lake_probe_test.cpp on the real lake_probe.cpp, full_state.cpp and indirect_check.cpp. direct.cpp needs libdrm and is
only compiled on the box."""
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
LLVM = pathlib.Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\Llvm\x64")
os.environ["PATH"] = str(LLVM / "lib" / "clang" / "22" / "lib" / "windows") + os.pathsep + os.environ["PATH"]
out = pathlib.Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=True)
B = REPO / "backend"
srcs = [B / "tests" / "lake_probe_test.cpp", B / "src" / "lake_probe.cpp", B / "src" / "full_state.cpp",
        B / "src" / "indirect_check.cpp", HERE / "shim_main.cpp"]
exe = out / "lake_probe_test.exe"
cmd = [str(LLVM / "bin" / "clang++.exe"), "-std=c++20", "-O1", "-g", "-fsanitize=address", "-Wall", "-Wextra", "-Wshadow",
       "-Wno-deprecated-declarations", "-D_CRT_SECURE_NO_WARNINGS", "-I", str(B / "include"), "-I", str(HERE / "laptop-shim"),
       *map(str, srcs), "-o", str(exe)]
r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
print(r.stdout[-4000:])
if r.returncode != 0:
    print("compile failed", r.returncode)
    sys.exit(r.returncode)
r = subprocess.run([str(exe)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
print(r.stdout[-4000:])
sys.exit(r.returncode)
