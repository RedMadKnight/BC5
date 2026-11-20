#!/bin/bash
# BC5 exp 0438 (tag e438): cut e438's pieces from the generated unit, unchanged, and run test_e438.cpp (e438_maps
# against the full rebuild on random view and BO lists). Laptop: VS clang++ or g++.
#   bash test_e438.sh [unit]
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd); unit=${1:-$here/e438.cpp}; out=$(mktemp -d)
piece() { sed -n "${1},${2}p" "$unit" | tr -d '\r' > "$out/$3"; }
lineof() { grep -n -m1 -F -- "$1" "$unit" | cut -d: -f1; }
endf() { awk -v s="$1" 'NR > s && /^}/ {print NR; exit}' "$unit"; }
a=$(lineof 'struct DView {'); b=$(lineof 'struct DState {'); piece "$a" "$(endf "$b")" e438_types.inc
a=$(lineof 'struct DViews {'); b=$(lineof '} // namespace e438'); piece "$a" "$b" e438_ns.inc
a=$(lineof 'namespace k1r412 {'); b=$(lineof '} // namespace k1r412'); piece "$a" "$b" e438_k1r.inc
a=$(lineof 'namespace kl412 {'); b=$(lineof '} // namespace kl412'); piece "$a" "$b" e438_kl.inc
a=$(lineof 'static bool e438_g412_any(); // defined after g_g412_off'); b=$(lineof 'static bool e438_maps(DState& S'); piece "$a" "$(endf "$b")" e438_maps.inc
cp "$here/test_e438.cpp" "$out/"
cxx=${CXX:-g++}
[ -z "${CXX:-}" ] && [ -x "/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe" ] && cxx="/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe"
(cd "$out" && "$cxx" -std=c++20 -O1 -Wall -Wextra -Werror -Wno-unused-function -Wno-unused-variable -Wno-unused-parameter -D_CRT_SECURE_NO_WARNINGS -o t438e.exe test_e438.cpp)
"$out/t438e.exe"
