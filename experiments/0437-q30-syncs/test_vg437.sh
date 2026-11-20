#!/bin/bash
# BC5 exp 0437 (tag vg437): build and run test_vg437.cpp against a KytyPlus tree with mkvg437.py applied.
#   bash test_vg437.sh <KytyPlus tree> [seeds]
# Laptop: VS clang++ (msvc target); the box's ubuntu distrobox: g++. Writes nothing into the tree.
set -euo pipefail
tree=$1
seeds=${2:-200}
here=$(cd "$(dirname "$0")" && pwd)
out=$(mktemp -d)
mem="$tree/src/kernel/memory.cpp"
# the helpers from CopyVirtualRangeName to the end of class VirtualRanges, without the address-space include
a=$(grep -n '^static void CopyVirtualRangeName' "$mem" | cut -d: -f1)
c=$(grep -n '^class VirtualRanges {' "$mem" | cut -d: -f1)
e=$(awk -v c="$c" 'NR > c && /^};/ { print NR; exit }' "$mem")
sed -n "${a},${e}p" "$mem" | grep -v '^#include "memoryAddressSpace.inc"' | tr -d '\r' > "$out/vr437.inc"
cp "$here/test_vg437.cpp" "$out/"
mkdir -p "$out/bc5"
for h in map_records.hpp env_rule.hpp; do tr -d '\r' < "$tree/src/bc5/$h" > "$out/bc5/$h"; done
cxx=${CXX:-}
if [ -z "$cxx" ]; then
	if [ -x "/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe" ]; then
		cxx="/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe"
	else
		cxx=g++
	fi
fi
(cd "$out" && "$cxx" -std=c++20 -O1 -Wall -Wextra -Werror -Wno-unused-function -Wno-deprecated-declarations -D_CRT_SECURE_NO_WARNINGS -o t437.exe test_vg437.cpp)
"$out/t437.exe" "$seeds"
