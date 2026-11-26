#!/bin/bash
# BC5 exp 0438 A1P (tag a1p438): build memory.cpp with mka1p.py (on the tree's memory.cpp and on A1's output), extract
# the real classes, run the differential test in the switch's modes, show that each planted bug (m1..m6) makes it FAIL,
# then the bench.
#   bash test_a1p438.sh [IN_memory.cpp] [ops_per_seed] [seeds]
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
src=${1:-$HOME/Documents/bc5-private-0438/kyty-src/src/kernel/memory.cpp}
ops=${2:-20000}
seeds=${3:-12}
cxx=${CXX:-"/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe"}
py=${PYTHON:-python}
out="$here/build"
mkdir -p "$out"
w() { if command -v cygpath > /dev/null; then cygpath -w "$1"; else echo "$1"; fi; }
q() { tr -d '\r'; }

echo "== mka1p.py on the input and on A1's output of it"
"$py" -I "$(w "$here/mka1p.py")" "$(w "$src")" "$(w "$out/memory_a1p.cpp")" | q
"$py" -I "$(w "$here/../a1/mka1.py")" "$(w "$src")" "$(w "$out/memory_a1.cpp")" | q
"$py" -I "$(w "$here/mka1p.py")" "$(w "$out/memory_a1.cpp")" "$(w "$out/memory_a1_a1p.cpp")" | q

build() { # $1 dir under build/, $2 exe name
	"$cxx" -std=c++20 -O2 -D_CRT_SECURE_NO_WARNINGS -Wall -Wextra -Wno-unused-function -Werror -I "$(w "$out/$1")" -I "$(w "$here/stub")" \
		"$(w "$here/test_a1p438.cpp")" -o "$(w "$out/$2")"
}
mkdir -p "$out/real" "$out/real_a1"
"$py" -I "$(w "$here/mka1p.py")" --extract "$(w "$out/memory_a1p.cpp")" "$(w "$out/real/a1p_real.h")" | q
"$py" -I "$(w "$here/mka1p.py")" --extract "$(w "$out/memory_a1_a1p.cpp")" "$(w "$out/real_a1/a1p_real.h")" | q
cmp "$out/real/a1p_real.h" "$out/real_a1/a1p_real.h" > /dev/null && echo "extracted code from both outputs: identical apart from the source md5 line" ||
	{ diff <(tail -n +2 "$out/real/a1p_real.h") <(tail -n +2 "$out/real_a1/a1p_real.h") > /dev/null && echo "extracted code from both outputs: identical apart from the source md5 line"; }
build real test_a1p438.exe

rc=0
run() { # $1 label, $2 seeds, then env assignments
	local label=$1 n=$2
	shift 2
	echo "== $label ($ops ops x $n seeds)"
	if env "$@" "$out/test_a1p438.exe" "$ops" "$n" 2> "$out/stderr-$label.log" | q; then :; else rc=1; fi
	grep -a '^FAIL' "$out/stderr-$label.log" | q | head -5 || true
}
# the main run; then the switch read by the default constructors (unset, "0") and exp 0412's other modes, fewer seeds
run a1p1 "$seeds" KYTY_BC5_0438_A1P=1
run a1p-unset 3 -u KYTY_BC5_0438_A1P
run a1p0 3 KYTY_BC5_0438_A1P=0
run a1p1-sorted0 3 KYTY_BC5_0438_A1P=1 KYTY_BC5_PHYSMAP_SORTED=0
run a1p1-sortedverify 3 KYTY_BC5_0438_A1P=1 KYTY_BC5_PHYSMAP_SORTED=verify

caught=0
for m in m1 m2 m3 m4 m5 m6; do
	mkdir -p "$out/$m" && "$py" -I "$(w "$here/mka1p.py")" --extract "$(w "$out/memory_a1p.cpp")" "$(w "$out/$m/a1p_real.h")" "$m" | q
	build "$m" "test_a1p438_$m.exe"
	echo "== mutant $m (must FAIL)"
	if "$out/test_a1p438_$m.exe" "$ops" "$seeds" 2> "$out/stderr-$m.log" | q; then
		echo "mutant $m NOT caught"
		rc=1
	else
		grep -a '^FAIL' "$out/stderr-$m.log" | q | head -2 || true
		caught=$((caught + 1))
	fi
done
echo "mutants caught: $caught/6"
echo "== bench"
"$out/test_a1p438.exe" --bench 2> /dev/null | q || rc=1
[ "$rc" = 0 ] && echo "test_a1p438: ALL PASS" || echo "test_a1p438: FAILED"
exit "$rc"
