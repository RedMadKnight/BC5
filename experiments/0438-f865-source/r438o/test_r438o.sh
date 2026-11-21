#!/bin/bash
# SPDX-License-Identifier: GPL-2.0
# BC5 exp 0438 (tag r438o): cut r438's pieces, unchanged, from a unit and run test_r438o.cpp.
#   bash test_r438o.sh UNIT [MODE]     MODE: order (default), trim, lwm (a mkq438x.py unit, BC5_0438_R438_LWM=1), lwmid or identity; the caller sets BC5_0438_EARLYREG.
# Builds into a fresh mktemp directory; one foreground run, no loop. VS clang++ on the laptop (the slice's
# INDIRECT_BUFFER carries a 40-bit address: a fixed low image base).
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd); unit=$1; mode=${2:-order}; out=$(mktemp -d)
lineof() { grep -n -m1 -F -- "$1" "$unit" | cut -d: -f1; }
endf() { awk -v s="$1" 'NR > s && /^}/ {print NR; exit}' "$unit"; }
piece() { sed -n "${1},${2}p" "$unit" | tr -d '\r' > "$out/$3"; }
a=$(lineof 'kR438Early = 1ull << 63u'); b=$(lineof 'static std::atomic<uint64_t> g_r438_slices'); piece "$a" "$b" r_state.inc
a=$(lineof 'struct PendingLabelWrite {'); b=$(lineof 'static std::condition_variable             g_plw_cv;'); piece "$a" "$b" r_plw.inc
a=$(lineof 'static void register_label_writes(const uint32_t* ib'); piece "$a" "$(endf "$a")" r_reg.inc
a=$(lineof 'static thread_local uint64_t t_r438_slice'); b=$(lineof 'static void forget_label_writes(uint64_t seq'); piece "$a" "$((b - 1))" r_r438.inc
a=$(lineof 'static bool ring_will_satisfy(const uint32_t* p, bool is64, int ring) {'); piece "$a" "$(endf "$a")" r_rws.inc
X=""
if grep -q -F '// ---- BC5 experiment 0438 (tag labelmap)' "$unit"; then # q438/mkq438x.py: the filter's check, cut for the scan
	a=$(lineof 'static bool covered_sorted(const bc5::direct::MappingIndex& maps, uint64_t a, uint64_t bytes) {'); piece "$a" "$(endf "$a")" r_cov.inc
	a=$(lineof '// ---- BC5 experiment 0438 (tag labelmap)'); b=$(lineof '// ---- end of exp 0438 (tag labelmap)'); piece "$a" "$b" r_lwm.inc
	X="-DR438O_X"
fi
cp "$here/test_r438o.cpp" "$out/"
if [ -n "${R438O_PLANT:-}" ]; then # a planted bug: python -I replaces one exact string in the cut register_label_writes
	python -I -c 'import sys; p,o,n=sys.argv[1:4]; s=open(p,"rb").read().decode(); assert s.count(o)==1, o; open(p,"wb").write(s.replace(o,n).encode())' "$out/${R438O_PLANT_FILE:-r_reg.inc}" "$R438O_PLANT" "${R438O_PLANT_TO:-if (false) {}"
fi
LOW="-no-pie"
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) LOW="-Wl,/DYNAMICBASE:NO -Wl,/BASE:0x10000000" ;; esac
cxx=${CXX:-g++}
[ -z "${CXX:-}" ] && [ -x "/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe" ] && cxx="/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe"
CNT=""; grep -q "g_r438o_trims" "$out/r_state.inc" && CNT="-DR438O_COUNTERS"
(cd "$out" && "$cxx" $CNT $X -std=c++20 -O1 -Wall -Wextra -Werror -Wno-unused-function -Wno-unused-variable -D_CRT_SECURE_NO_WARNINGS $LOW -o tr.exe test_r438o.cpp)
"$out/tr.exe" "$mode"
