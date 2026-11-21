#!/bin/bash
# BC5 exp 0438 A1 (tag a1438): build memory.cpp with mka1.py, extract the range classes, run the differential test
# with the dispatcher in both modes, then show that each planted bug (m1..m4) makes it FAIL.
#   bash test_a1438.sh [IN_memory.cpp] [ops_per_seed] [seeds]
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
src=${1:-/c/Users/kjani/Documents/bc5-private-0438/kyty-src/src/kernel/memory.cpp}
ops=${2:-25000}
seeds=${3:-12}
cxx=${CXX:-"/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe"}
py=${PYTHON:-python}
out="$here/build"
mkdir -p "$out"
w() { if command -v cygpath > /dev/null; then cygpath -w "$1"; else echo "$1"; fi; }

"$py" -I "$(w "$here/mka1.py")" "$(w "$src")" "$(w "$out/memory_a1.cpp")" | tr -d '\r'
build() { # $1 header name, $2 exe name
	"$cxx" -std=c++20 -O2 -D_CRT_SECURE_NO_WARNINGS -Wall -Wextra -Wno-unused-function -Werror -I "$(w "$out/$3")" -I "$(w "$here/stub")" \
		"$(w "$here/test_a1438.cpp")" -o "$(w "$out/$2")"
}
mkdir -p "$out/real" && "$py" -I "$(w "$here/mka1.py")" --extract "$(w "$out/memory_a1.cpp")" "$(w "$out/real/a1_real.h")" | tr -d '\r'
build a1_real.h test_a1438.exe real

rc=0
echo "== real, KYTY_BC5_0438_A1=1"
KYTY_BC5_0438_A1=1 "$out/test_a1438.exe" "$ops" "$seeds" | tr -d '\r' || rc=1
echo "== real, KYTY_BC5_0438_A1 unset"
env -u KYTY_BC5_0438_A1 "$out/test_a1438.exe" "$ops" "$seeds" | tr -d '\r' || rc=1
echo "== real, KYTY_BC5_0438_A1=0"
KYTY_BC5_0438_A1=0 "$out/test_a1438.exe" "$ops" "$seeds" | tr -d '\r' || rc=1
echo "== real, KYTY_BC5_0438_A1=1 KYTY_BC5_RANGES_FAST=0 (QuerySpan's slow walk in both classes)"
KYTY_BC5_0438_A1=1 KYTY_BC5_RANGES_FAST=0 "$out/test_a1438.exe" "$ops" "$seeds" | tr -d '\r' || rc=1

caught=0
for m in m1 m2 m3 m4; do
	mkdir -p "$out/$m" && "$py" -I "$(w "$here/mka1.py")" --extract "$(w "$out/memory_a1.cpp")" "$(w "$out/$m/a1_real.h")" "$m" | tr -d '\r'
	build a1_real.h "test_a1438_$m.exe" "$m"
	echo "== mutant $m (must FAIL)"
	if KYTY_BC5_0438_A1=1 "$out/test_a1438_$m.exe" "$ops" "$seeds" | tr -d '\r'; then
		echo "mutant $m NOT caught"
		rc=1
	else
		caught=$((caught + 1))
	fi
done
echo "mutants caught: $caught/4"
echo "== bench"
"$out/test_a1438.exe" --bench | tr -d '\r'
[ "$rc" = 0 ] && echo "test_a1438: ALL PASS" || echo "test_a1438: FAILED"
exit "$rc"
