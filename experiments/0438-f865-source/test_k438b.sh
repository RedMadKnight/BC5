#!/bin/bash
# BC5 exp 0438 (tag k438b): cut HoldCond, the switch and hold_release from the generated unit, unchanged, and run
# test_k438b.cpp with BC5_0438_HOLD unset (on) and =0 (off). Laptop: VS clang++; box: g++.   bash test_k438b.sh [unit]
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd); unit=${1:-$here/bc5LleAgc.cpp}; out=$(mktemp -d)
a=$(grep -n '^struct HoldCond {' "$unit" | cut -d: -f1); b=$(awk -v a="$a" 'NR > a && /^};/ {print NR; exit}' "$unit")
sed -n "${a},${b}p" "$unit" | tr -d '\r' > "$out/k438b_cut_holdcond.inc"
c=$(grep -n '^static uint64_t hold_ns() {' "$unit" | cut -d: -f1); d=$(grep -n '^static void                    chain_submit(ChainSlot& s, int why, bool foreign);' "$unit" | cut -d: -f1)
e=$(grep -n '^static bool hold_release(ChainSlot& s, bool block) {' "$unit" | cut -d: -f1); f=$(awk -v e="$e" 'NR > e && /^}/ {print NR; exit}' "$unit")
{ sed -n "${c},$((d - 1))p" "$unit"; sed -n "${e},${f}p" "$unit"; } | tr -d '\r' > "$out/k438b_cut_release.inc"
cp "$here/test_k438b.cpp" "$out/"
cxx=${CXX:-}
if [ -z "$cxx" ]; then
	cxx=g++
	[ -x "/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe" ] && cxx="/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe"
fi
(cd "$out" && "$cxx" -std=c++20 -O1 -Wall -Wextra -Werror -Wno-unused-function -Wno-unused-variable -D_CRT_SECURE_NO_WARNINGS -o t438.exe test_k438b.cpp)
echo "== BC5_0438_HOLD unset"; (unset BC5_0438_HOLD; "$out/t438.exe")
echo "== BC5_0438_HOLD=0"; BC5_0438_HOLD=0 "$out/t438.exe"
