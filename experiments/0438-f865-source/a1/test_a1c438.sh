#!/bin/bash
# BC5 exp 0438 (tag a1c438): the counters of mka1c.py. Builds the chain mka1 -> mka1b -> mka1p -> mka1c, extracts the
# A1b classes and the A1P classes from the counter output, and runs test_a1b438 and test_a1p438 against them (normal,
# with a 1-s printer period and the test's exit line; and lean, where no counter line may appear). PASS when both
# differential tests pass, the exit line shows non-zero range edits / A1P ops / journal records, the 1-s line appears
# in the A1b run, and the lean run prints no a1c438 line.
#   bash test_a1c438.sh [IN_memory.cpp]
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
b=$(cd "$here/../a1b" && pwd); p=$(cd "$here/../a1p" && pwd)
src=${1:-/c/Users/kjani/Documents/bc5-private-0438/kyty-src/src/kernel/memory.cpp}
cxx=${CXX:-"/c/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/Llvm/x64/bin/clang++.exe"}
py=${PYTHON:-python}
out="$here/build-a1c"
rm -rf "$out"; mkdir -p "$out/b" "$out/p" "$out/today" "$out/j"
w() { if command -v cygpath > /dev/null; then cygpath -w "$1"; else echo "$1"; fi; }
q() { tr -d '\r'; }
"$py" -I "$(w "$here/mka1.py")" "$(w "$src")" "$(w "$out/m1.cpp")" | q
"$py" -I "$(w "$b/mka1b.py")" "$(w "$out/m1.cpp")" "$(w "$out/m2.cpp")" | q
"$py" -I "$(w "$p/mka1p.py")" "$(w "$out/m2.cpp")" "$(w "$out/m3.cpp")" | q
"$py" -I "$(w "$here/mka1c.py")" "$(w "$out/m3.cpp")" "$(w "$out/m4.cpp")" | q
"$py" -I "$(w "$b/mka1b.py")" --extract-today "$(w "$out/m1.cpp")" "$(w "$out/today")" | q
"$py" -I "$(w "$b/mka1b.py")" --extract "$(w "$out/m4.cpp")" "$(w "$out/b")" | q
"$py" -I "$(w "$p/mka1p.py")" --extract "$(w "$out/m4.cpp")" "$(w "$out/p/a1p_real.h")" | q
# the A1P extract does not reach the counters' namespace: put it in after the namespace line
"$py" -I - "$(w "$out/m4.cpp")" "$(w "$out/p/a1p_real.h")" << 'EOF'
import sys
m = open(sys.argv[1], 'rb').read(); h = open(sys.argv[2], 'rb').read()
i = m.index(b'// exp 0438 (tag a1c438): counters'); j = m.index(b'} // namespace a1c\n#endif\n', i) + len(b'} // namespace a1c\n#endif\n')
ns = b'namespace Libs::LibKernel::Memory {\n'
assert h.count(ns) == 1 and b'a1c::count_a1p' in h
open(sys.argv[2], 'wb').write(h.replace(ns, ns + m[i:j]))
EOF
inc=(-include atomic -include thread -include chrono -include mutex -include cstdio)
flags=(-std=c++20 -O2 -D_CRT_SECURE_NO_WARNINGS -Wall -Wextra -Wno-unused-function -Werror "${inc[@]}" -DBC5_0438_A1C_TEST -DKYTY_BC5_0438_A1C_PERIOD_S=1)
"$cxx" "${flags[@]}" -I "$(w "$out/b")" -I "$(w "$out/today")" -I "$(w "$b/stub")" -I "$(w "$here/stub")" "$(w "$b/test_a1b438.cpp")" -o "$(w "$out/tb.exe")"
"$cxx" "${flags[@]}" -DBC5_LEAN -I "$(w "$out/b")" -I "$(w "$out/today")" -I "$(w "$b/stub")" -I "$(w "$here/stub")" "$(w "$b/test_a1b438.cpp")" -o "$(w "$out/tbl.exe")"
"$cxx" "${flags[@]}" -I "$(w "$out/p")" -I "$(w "$p/stub")" "$(w "$p/test_a1p438.cpp")" -o "$(w "$out/tp.exe")"
rc=0
echo "== A1b test on the counter build (journal on)"
KYTY_BC5_0438_A1=1 "$out/tb.exe" 25000 12 "$(w "$out/j")" 2> "$out/tb.err" | q | tail -2 || rc=1
echo "== A1b lean"
KYTY_BC5_0438_A1=1 "$out/tbl.exe" 25000 3 2> "$out/tbl.err" | q | tail -1 || rc=1
echo "== A1P test on the counter build"
KYTY_BC5_0438_A1P=1 "$out/tp.exe" 20000 12 2> "$out/tp.err" | q | tail -1 || rc=1
for f in tb tbl tp; do echo "$f: $(grep -ac 'tag a1c438' "$out/$f.err") counter lines; last: $(grep -a 'tag a1c438' "$out/$f.err" | tail -1 | q)"; done
num() { grep -a 't -1 s' "$out/$1.err" | q | sed -n "s/.*$2 \([0-9]*\).*/\1/p"; }
[ "$(num tb add)" -gt 0 ] && [ "$(num tb remove)" -gt 0 ] && [ "$(num tb records)" -gt 0 ] || { echo "A1b: zero counts"; rc=1; }
[ "$(grep -ac 'tag a1c438): t [1-9]' "$out/tb.err")" -gt 0 ] || { echo "A1b: no periodic line"; rc=1; }
[ "$(num tp physical)" -gt 0 ] && [ "$(num tp flexible)" -gt 0 ] && [ "$(num tp pooled)" -gt 0 ] || { echo "A1P: zero counts"; rc=1; }
[ "$(grep -ac 'tag a1c438' "$out/tbl.err")" = 0 ] || { echo "lean printed a counter line"; rc=1; }
echo "journal bytes $(cat "$out"/j/* | wc -c)"
[ "$rc" = 0 ] && echo "test_a1c438: ALL PASS" || echo "test_a1c438: FAILED"
exit "$rc"
