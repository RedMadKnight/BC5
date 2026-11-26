#!/bin/bash
# SPDX-License-Identifier: GPL-2.0
# BC5 exp 0438 (tag bake438b): A1 + A1b + A1P (+ a1c's counters) on the BAKED memory.cpp (mkbake438b.py's output,
# the defaults flipped to "on unless 0"). The steps of a1/test_a1c438.sh, run on the baked file instead of a fresh
# chain: mka1b.py --extract and mka1p.py --extract of the baked file (the dispatcher with its A1On, Bc5A1pOn and the
# counters), today's readers from mka1.py's output of the tree's file; test_a1b438.cpp (normal and lean) and
# test_a1p438.cpp with the switches unset (now ON), "0" (off) and "1". Each run checks the switch's stderr line.
# The existing tests (a1/test_a1438.sh, a1b/test_a1b438.sh, a1p/test_a1p438.sh, a1/test_a1c438.sh) run separately.
#   bash test_mem438b.sh BAKED_memory.cpp [TREE_memory.cpp]
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd); exp=$(cd "$here/.." && pwd)
baked=$1; src=${2:-$HOME/Documents/bc5-private-0438/kyty-src/src/kernel/memory.cpp}
a1=$exp/a1; b=$exp/a1b; p=$exp/a1p
cxx=${CXX:-"/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe"}
py=${PYTHON:-python}
out=$(mktemp -d); mkdir -p "$out/b" "$out/p" "$out/today" "$out/j1" "$out/ju" "$out/j0"
w() { if command -v cygpath > /dev/null; then cygpath -w "$1"; else echo "$1"; fi; }
q() { tr -d '\r'; }
echo "== baked memory.cpp $(md5sum < "$baked" | cut -c1-32)"
"$py" -I "$(w "$a1/mka1.py")" "$(w "$src")" "$(w "$out/m1.cpp")" | q
"$py" -I "$(w "$b/mka1b.py")" --extract-today "$(w "$out/m1.cpp")" "$(w "$out/today")" | q
"$py" -I "$(w "$b/mka1b.py")" --extract "$(w "$baked")" "$(w "$out/b")" | q
"$py" -I "$(w "$p/mka1p.py")" --extract "$(w "$baked")" "$(w "$out/p/a1p_real.h")" | q
"$py" -I -c '
import sys
m = open(sys.argv[1], "rb").read(); h = open(sys.argv[2], "rb").read()
i = m.index(b"// exp 0438 (tag a1c438): counters"); e = b"} // namespace a1c\n#endif\n"; j = m.index(e, i) + len(e)
ns = b"namespace Libs::LibKernel::Memory {\n"
assert h.count(ns) == 1 and b"a1c::count_a1p" in h
open(sys.argv[2], "wb").write(h.replace(ns, ns + m[i:j]))
' "$(w "$baked")" "$(w "$out/p/a1p_real.h")"
grep -c 'strcmp(e, "0") == 0); // exp 0438 (bake438b)' "$out/b/a1b_real.h" "$out/p/a1p_real.h" | q | sed 's/^/   flipped default in the extract: /'
inc=(-include atomic -include thread -include chrono -include mutex -include cstdio)
flags=(-std=c++20 -O2 -D_CRT_SECURE_NO_WARNINGS -Wall -Wextra -Wno-unused-function -Werror "${inc[@]}" -DBC5_0438_A1C_TEST -DKYTY_BC5_0438_A1C_PERIOD_S=1)
"$cxx" "${flags[@]}" -I "$(w "$out/b")" -I "$(w "$out/today")" -I "$(w "$b/stub")" -I "$(w "$a1/stub")" "$(w "$b/test_a1b438.cpp")" -o "$(w "$out/tb.exe")"
"$cxx" "${flags[@]}" -DBC5_LEAN -I "$(w "$out/b")" -I "$(w "$out/today")" -I "$(w "$b/stub")" -I "$(w "$a1/stub")" "$(w "$b/test_a1b438.cpp")" -o "$(w "$out/tbl.exe")"
# test_a1p438.cpp's switch check expects today's default (on only when "1"): a copy expects the bake's (on unless "0")
"$py" -I -c '
import sys
s = open(sys.argv[1], "rb").read()
o = b"const bool     on = e != nullptr && std::strcmp(e, \x221\x22) == 0;"
n = b"const bool     on = !(e != nullptr && std::strcmp(e, \x220\x22) == 0); // bake438b: on unless \x220\x22"
assert s.count(o) == 1, "test_a1p438.cpp switch check"
open(sys.argv[2], "wb").write(s.replace(o, n))
' "$(w "$p/test_a1p438.cpp")" "$(w "$out/p/test_a1p438b.cpp")"
"$cxx" "${flags[@]}" -I "$(w "$out/p")" -I "$(w "$p/stub")" "$(w "$out/p/test_a1p438b.cpp")" -o "$(w "$out/tp.exe")"
rc=0
one() { # one LABEL WANT(on|off) SWITCHLINE EXE ARGS... (env set by the caller through env)
	local label=$1 want=$2 pat=$3; shift 3
	echo "== $label"
	if "$@" 2> "$out/$label.err" | q | tail -1 | sed 's/^/   /'; then :; else rc=1; fi
	local line; line=$(grep -a -m1 "$pat" "$out/$label.err" | q || true)
	echo "   switch line: ${line:-none}"
	case "$line" in *": $want "*|*": $want") ;; *) echo "   FAIL: want $want"; rc=1 ;; esac
}
A1="exp 0438 A1 ranges map"; AP="exp 0438 A1P memory tables in maps"
one a1-unset on "$A1" env -u KYTY_BC5_0438_A1 "$out/tb.exe" 25000 12 "$(w "$out/ju")"
one a1-0 off "$A1" env KYTY_BC5_0438_A1=0 "$out/tb.exe" 25000 4 "$(w "$out/j0")"
one a1-1 on "$A1" env KYTY_BC5_0438_A1=1 "$out/tb.exe" 25000 4 "$(w "$out/j1")"
one a1-lean-unset on "$A1" env -u KYTY_BC5_0438_A1 "$out/tbl.exe" 25000 3
one a1p-unset on "$AP" env -u KYTY_BC5_0438_A1P "$out/tp.exe" 20000 12
one a1p-0 off "$AP" env KYTY_BC5_0438_A1P=0 "$out/tp.exe" 20000 3
one a1p-1 on "$AP" env KYTY_BC5_0438_A1P=1 "$out/tp.exe" 20000 3
echo "journal files: unset $(ls "$out/ju" | wc -l), 0 $(ls "$out/j0" | wc -l), 1 $(ls "$out/j1" | wc -l)"
[ "$(ls "$out/j0" | wc -l)" = 0 ] || { echo "FAIL: a journal with A1=0"; rc=1; }
[ "$(grep -ac 'tag a1c438' "$out/a1-lean-unset.err")" = 0 ] || { echo "FAIL: lean printed a counter line"; rc=1; }
echo "a1c lines: a1-unset $(grep -ac 'tag a1c438' "$out/a1-unset.err"), a1p-unset $(grep -ac 'tag a1c438' "$out/a1p-unset.err"), lean $(grep -ac 'tag a1c438' "$out/a1-lean-unset.err")"
[ "$rc" = 0 ] && echo "test_mem438b: ALL PASS" || echo "test_mem438b: FAILED"
exit "$rc"
