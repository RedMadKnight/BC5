#!/bin/bash
# BC5 exp 0438 (tag p438): cut p438's block from the generated unit, unchanged, and run test_p438.cpp against it.
#   bash test_p438.sh [unit]
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd); unit=${1:-$here/b438.cpp}; out=$(mktemp -d)
a=$(grep -n -m1 -F 'namespace p438 {' "$unit" | cut -d: -f1)
b=$(grep -n -m1 -F '// Returns 0 on success or a positive errno' "$unit" | cut -d: -f1)
sed -n "${a},$((b - 1))p" "$unit" | tr -d '\r' > "$out/p438_cut.inc"
cp "$here/test_p438.cpp" "$out/"
cxx=${CXX:-g++}
[ -z "${CXX:-}" ] && [ -x "/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe" ] && cxx="/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe"
(cd "$out" && "$cxx" -std=c++20 -O1 -Wall -Wextra -Werror -Wno-unused-function -D_CRT_SECURE_NO_WARNINGS -o tp438.exe test_p438.cpp)
echo "== BC5_0438_PROLMERGE unset"; (unset BC5_0438_PROLMERGE; "$out/tp438.exe")
