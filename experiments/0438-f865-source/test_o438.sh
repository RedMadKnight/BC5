#!/bin/bash
# BC5 exp 0438 (tag o438): test o438.hpp's bookkeeping with stub POSIX headers (the laptop has no pthread.h for its VS
# clang++): a thread's name and tid come from the test, the output is captured. Runs with BC5_0438_OUTSIDE=1 and
# unset, then compiles and runs the lean variant (-DBC5_LEAN: empty macros).
#   bash test_o438.sh
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd); out=$(mktemp -d)
mkdir -p "$out/stub/sys"
cat > "$out/stub/pthread.h" << 'EOF'
#pragma once
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <map>
#include <mutex>
#include <string>
using pthread_t = uintptr_t;
inline thread_local std::string g_stub_name;
inline thread_local uint32_t    g_stub_tid = 1;
inline pthread_t                pthread_self() { return 0; }
inline int pthread_getname_np(pthread_t, char* b, size_t n) { std::snprintf(b, n, "%s", g_stub_name.c_str()); return 0; }
inline std::mutex                      g_stub_m;
inline std::map<uint32_t, std::string> g_stub_names;
inline bool                            g_stub_cap = false;
inline std::string                     g_stub_out;
inline void stub_set_name(const char* n, uint32_t tid) { g_stub_name = n; g_stub_tid = tid; std::lock_guard l(g_stub_m); g_stub_names[tid] = n; }
inline std::string stub_comm(uint32_t t) { std::lock_guard l(g_stub_m); auto it = g_stub_names.find(t); return it == g_stub_names.end() ? std::string("?") : it->second; }
inline void stub_printf(const char* f, ...) {
	char    b[16384];
	va_list ap;
	va_start(ap, f);
	std::vsnprintf(b, sizeof(b), f, ap);
	va_end(ap);
	if (g_stub_cap) g_stub_out += b; else std::fputs(b, stderr);
}
inline void        stub_capture(bool on) { g_stub_cap = on; if (on) g_stub_out.clear(); }
inline std::string stub_captured() { return g_stub_out; }
#define BC5_O438_PRINTF(...)  stub_printf(__VA_ARGS__)
#define BC5_O438_COMM_STUB(t) stub_comm(t)
EOF
printf '#pragma once\n#define SYS_gettid 186\n' > "$out/stub/sys/syscall.h"
printf '#pragma once\ninline long syscall(long, ...) { return static_cast<long>(g_stub_tid); }\n' > "$out/stub/unistd.h"
cp "$here/o438.hpp" "$here/test_o438.cpp" "$out/"
cxx=${CXX:-g++}
[ -z "${CXX:-}" ] && [ -x "/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe" ] && cxx="/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe"
F="-std=c++20 -O1 -Wall -Wextra -Werror -Wno-unused-function -D_CRT_SECURE_NO_WARNINGS"
(cd "$out" && "$cxx" $F -I stub -o to438.exe test_o438.cpp && "$cxx" $F -DBC5_LEAN -I stub -o to438l.exe test_o438.cpp)
echo "== BC5_0438_OUTSIDE=1"; BC5_0438_OUTSIDE=1 "$out/to438.exe"
echo "== BC5_0438_OUTSIDE unset"; (unset BC5_0438_OUTSIDE; "$out/to438.exe")
echo "== lean"; "$out/to438l.exe"
