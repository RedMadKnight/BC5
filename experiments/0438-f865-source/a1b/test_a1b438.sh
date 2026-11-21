#!/bin/bash
# BC5 exp 0438 A1b (tag a1b438): build memory.cpp with mka1.py then mka1b.py, extract today's and A1b's real code, run
# the differential test in both dispatcher modes, with the default (chunk 512, ring 4096) and a small (chunk 8,
# ring 64) geometry, the lean build, a journal replay, then show that each planted bug (b1..b4) makes it FAIL.
#   bash test_a1b438.sh [IN_memory.cpp] [ops_per_seed] [seeds]
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
a1=$(cd "$here/../a1" && pwd)
src=${1:-/c/Users/kjani/Documents/bc5-private-0438/kyty-src/src/kernel/memory.cpp}
ops=${2:-25000}
seeds=${3:-12}
cxx=${CXX:-"/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe"}
py=${PYTHON:-python}
out="$here/build"
mkdir -p "$out"
w() { if command -v cygpath > /dev/null; then cygpath -w "$1"; else echo "$1"; fi; }

"$py" -I "$(w "$a1/mka1.py")" "$(w "$src")" "$(w "$out/memory_a1.cpp")" | tr -d '\r'
"$py" -I "$(w "$here/mka1b.py")" "$(w "$out/memory_a1.cpp")" "$(w "$out/memory_a1b.cpp")" | tr -d '\r'
mkdir -p "$out/today" && "$py" -I "$(w "$here/mka1b.py")" --extract-today "$(w "$out/memory_a1.cpp")" "$(w "$out/today")" | tr -d '\r'
build() { # $1 header dir, $2 exe name, $3.. extra flags
	local dir=$1 exe=$2
	shift 2
	"$cxx" -std=c++20 -O2 -D_CRT_SECURE_NO_WARNINGS -Wall -Wextra -Wno-unused-function -Werror "$@" -I "$(w "$out/$dir")" -I "$(w "$out/today")" \
		-I "$(w "$here/stub")" -I "$(w "$a1/stub")" "$(w "$here/test_a1b438.cpp")" -o "$(w "$out/$exe")"
}
small=(-DKYTY_BC5_0438_A1B_CHUNK=8 -DKYTY_BC5_0438_A1B_RING=64)
mkdir -p "$out/real" && "$py" -I "$(w "$here/mka1b.py")" --extract "$(w "$out/memory_a1b.cpp")" "$(w "$out/real")" | tr -d '\r'
build real test_a1b438.exe
build real test_a1b438_small.exe "${small[@]}"
build real test_a1b438_lean.exe -DBC5_LEAN

rc=0
run() { # $1 label, then env assignments and the command
	local label=$1
	shift
	echo "== $label"
	env "$@" | tr -d '\r' || rc=1
}
for d in j1 j0 js jl; do rm -rf "$out/$d" && mkdir -p "$out/$d"; done
run "default geometry, KYTY_BC5_0438_A1=1, journal on" KYTY_BC5_0438_A1=1 "$out/test_a1b438.exe" "$ops" "$seeds" "$(w "$out/j1")"
run "default geometry, KYTY_BC5_0438_A1 unset (no journal file may appear)" -u KYTY_BC5_0438_A1 "$out/test_a1b438.exe" "$ops" "$seeds" "$(w "$out/j0")"
run "default geometry, KYTY_BC5_0438_A1=0" KYTY_BC5_0438_A1=0 "$out/test_a1b438.exe" "$ops" "$seeds"
run "small geometry, KYTY_BC5_0438_A1=1, journal on" KYTY_BC5_0438_A1=1 "$out/test_a1b438_small.exe" "$ops" "$seeds" "$(w "$out/js")"
run "small geometry, KYTY_BC5_0438_A1 unset" -u KYTY_BC5_0438_A1 "$out/test_a1b438_small.exe" "$ops" "$seeds"
run "lean build, KYTY_BC5_0438_A1=1 (journal compiled out: no file may appear)" KYTY_BC5_0438_A1=1 "$out/test_a1b438_lean.exe" "$ops" "$seeds" "$(w "$out/jl")"
run "replay of seed 1's journal, map" KYTY_BC5_0438_A1=1 "$out/test_a1b438.exe" --replay "$(w "$out/j1/seed1.a1j")"
run "replay of seed 1's journal, vec" -u KYTY_BC5_0438_A1 "$out/test_a1b438.exe" --replay "$(w "$out/j1/seed1.a1j")"
echo "journal files: j1 $(ls "$out/j1" | wc -l), j0 $(ls "$out/j0" | wc -l), js $(ls "$out/js" | wc -l), jl $(ls "$out/jl" | wc -l); seed1.a1j $(wc -c < "$out/j1/seed1.a1j") bytes"
[ "$(ls "$out/j0" | wc -l)" = 0 ] && [ "$(ls "$out/jl" | wc -l)" = 0 ] || { echo "journal files where none may be"; rc=1; }

caught=0
for m in b1 b2 b3 b4; do
	mkdir -p "$out/$m" && "$py" -I "$(w "$here/mka1b.py")" --extract "$(w "$out/memory_a1b.cpp")" "$(w "$out/$m")" "$m" | tr -d '\r'
	build "$m" "test_a1b438_$m.exe" "${small[@]}"
	rm -rf "$out/j$m" && mkdir -p "$out/j$m"
	echo "== mutant $m (must FAIL)"
	if KYTY_BC5_0438_A1=1 "$out/test_a1b438_$m.exe" "$ops" "$seeds" "$(w "$out/j$m")" | tr -d '\r'; then
		echo "mutant $m NOT caught"
		rc=1
	else
		caught=$((caught + 1))
	fi
done
echo "mutants caught: $caught/4"
echo "== bench (KYTY_BC5_0438_A1=1)"
KYTY_BC5_0438_A1=1 "$out/test_a1b438.exe" --bench | tr -d '\r'
[ "$rc" = 0 ] && echo "test_a1b438: ALL PASS" || echo "test_a1b438: FAILED"
exit "$rc"
