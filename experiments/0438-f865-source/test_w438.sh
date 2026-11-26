#!/bin/bash
# BC5 exp 0438 (tag w438): cut namespace w438 from the generated unit, unchanged, and run test_w438.cpp with the
# switches unset (on), BC5_0438_KICK=0 and BC5_0438_WATCHER=0.   bash test_w438.sh [unit]
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd); unit=${1:-$here/w438.cpp}; out=$(mktemp -d)
a=$(grep -n -m1 '^namespace w438 {' "$unit" | cut -d: -f1); b=$(grep -n -m1 '^} // namespace w438' "$unit" | cut -d: -f1)
sed -n "${a},${b}p" "$unit" | tr -d '\r' > "$out/w438_cut.inc"
cp "$here/test_w438.cpp" "$out/"
cxx=${CXX:-g++}
[ -z "${CXX:-}" ] && [ -x "/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe" ] && cxx="/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe"
(cd "$out" && "$cxx" -std=c++20 -O1 -Wall -Wextra -Werror -D_CRT_SECURE_NO_WARNINGS -o t438w.exe test_w438.cpp)
echo "== unset"; (unset BC5_0438_WATCHER BC5_0438_KICK; "$out/t438w.exe")
echo "== BC5_0438_KICK=0"; (unset BC5_0438_WATCHER; BC5_0438_KICK=0 "$out/t438w.exe") || true
echo "== BC5_0438_WATCHER=0"; BC5_0438_WATCHER=0 "$out/t438w.exe"
