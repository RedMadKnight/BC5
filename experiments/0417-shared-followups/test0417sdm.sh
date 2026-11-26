#!/usr/bin/env bash
# BC5 exp 0417 (tag sdm417): builds test0417sdm.cpp (which includes sdm0417.inc as it is) and runs its cases, each
# one process in a work directory. usage: test0417sdm.sh <c++ compiler> <work dir>
set -u
CXX=$1; D=$2; HERE=$(cd "$(dirname "$0")" && pwd)
rm -rf "$D"; mkdir -p "$D" || exit 1
"$CXX" -std=c++20 -Wall -Wextra -Wno-unused-function -Wno-unused-variable -Wno-unused-const-variable -I"$HERE" "$HERE/test0417sdm.cpp" -o "$D/t.exe" 2> "$D/build.txt" || { head -30 "$D/build.txt"; echo "test0417sdm: the build FAILED"; exit 1; }
echo "build: $(grep -c 'warning:' "$D/build.txt") warnings"
bad=0
run() {  # directory, case, switches...
    local d=$D/$1 c=$2; shift 2; mkdir -p "$d"
    (cd "$d" && env "$@" "$D/t.exe" "$c" 2> "$D/$c.err") || bad=$((bad + 1))
}
run a write                                          # all off: one store
run a read-old
run b write KYTY_BC5_SAVEDATA_MEMORY_SLOTS=1
run b read-slots KYTY_BC5_SAVEDATA_MEMORY_SLOTS=1 KYTY_BC5_SAVEDATA_MEMORY_LOG=1
run b existed KYTY_BC5_SAVEDATA_MEMORY_SLOTS=1 TEST_EXISTED=1
run c param-write KYTY_BC5_SAVEDATA_MEMORY_PARAM=1
run c param-read KYTY_BC5_SAVEDATA_MEMORY_PARAM=1
run c param-off
echo "log lines of read-slots: $(grep -c 'sdm417' "$D/read-slots.err"); switch lines without the log: $(grep -c 'exp 0417' "$D/read-old.err")"
grep -m3 'sdm417 get' "$D/read-slots.err" | cut -c1-200
echo "test0417sdm: $([ "$bad" = 0 ] && echo "8 of 8 cases ok" || echo "$bad cases FAILED")"
[ "$bad" = 0 ]
