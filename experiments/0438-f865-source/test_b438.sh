#!/bin/bash
# BC5 exp 0438 (tag b438): cut b438's pieces from the generated unit, unchanged, and run test_b438.cpp with
# BC5_0438_EARLYREG unset (on) and =0 (off). Laptop: VS clang++ (the IBs' 40-bit address needs the Windows image base).
#   bash test_r438.sh [unit]
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd); unit=${1:-$here/b438.cpp}; out=$(mktemp -d)
piece() { sed -n "${1},${2}p" "$unit" | tr -d '\r' > "$out/$3"; }
lineof() { grep -n -m1 -F -- "$1" "$unit" | cut -d: -f1; }
endf() { awk -v s="$1" 'NR > s && /^}/ {print NR; exit}' "$unit"; }
a=$(lineof 'static constexpr uint64_t                 kR438Early'); b=$(lineof 'static std::atomic<uint64_t> g_r438_slices {0};'); piece "$a" "$b" b438_cut_state.inc
a=$(lineof 'struct PendingLabelWrite {'); b=$(lineof 'static std::vector<PendingLabelWrite>      g_plw;'); piece "$a" "$b" b438_cut_plw.inc
a=$(lineof 'static void register_label_writes(const uint32_t* ib'); piece "$a" "$(endf "$a")" b438_cut_register.inc
a=$(lineof 'static thread_local uint64_t t_r438_slice'); b=$(lineof 'static void forget_label_writes(uint64_t seq'); piece "$a" "$((b - 1))" b438_cut_r438.inc
a=$(lineof 'static bool ring_will_satisfy(const uint32_t* p, bool is64, int ring) {'); piece "$a" "$(endf "$a")" b438_cut_rws.inc
cp "$here/test_b438.cpp" "$out/"
LOW="-no-pie"  # the IBs' address must fit 40 bits: a fixed low image base
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) LOW="-Wl,/DYNAMICBASE:NO -Wl,/BASE:0x10000000" ;; esac
cxx=${CXX:-g++}
[ -z "${CXX:-}" ] && [ -x "/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe" ] && cxx="/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe"
(cd "$out" && "$cxx" -std=c++20 -O1 -Wall -Wextra -Werror -Wno-unused-function -Wno-unused-variable -D_CRT_SECURE_NO_WARNINGS $LOW -o t438b.exe test_b438.cpp)
(cd "$out" && "$cxx" -std=c++20 -O1 -Wall -Wextra -Werror -Wno-unused-function -Wno-unused-variable -D_CRT_SECURE_NO_WARNINGS -DBC5_LEAN $LOW -o t438bl.exe test_b438.cpp)
echo "== BC5_0438_EARLYREG unset"; (unset BC5_0438_EARLYREG; "$out/t438b.exe")
echo "== BC5_0438_EARLYREG=1"; BC5_0438_EARLYREG=1 "$out/t438b.exe"
echo "== BC5_0438_EARLYREG=0"; BC5_0438_EARLYREG=0 "$out/t438b.exe"
echo "== lean, BC5_0438_EARLYREG unset"; (unset BC5_0438_EARLYREG; "$out/t438bl.exe")
echo "== lean, BC5_0438_EARLYREG=0"; BC5_0438_EARLYREG=0 "$out/t438bl.exe"
