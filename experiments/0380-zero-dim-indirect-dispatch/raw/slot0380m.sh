#!/usr/bin/env bash
# BC5 experiment 0380: the int-check of slot0380.sh alone, on a main tree: the backend of the archive main-backend.tar
# (git archive of main, md5 pinned) configured as the shared archive with its Catch2 tests, in
# ~/bc5-work/exp0380/main-check/, the suite and its subsets run, and direct-selftest run without --submit (it does nothing
# on the GPU then). CPU only, no emulator. Any failure ends the script non-zero (Codex's check of 2026-10-30: the first
# version only echoed the rcs): a run's rc must be 0, a Catch2 run must report at least one test case passed, and a
# selftest must say it did nothing. test-slot0380m.sh tests this with a mock distrobox.
# usage: bash ~/bc5-work/exp0380/slot0380m.sh <md5 of main-backend.tar> [directory under exp0380, main-check] [subset tags]
#        (with main-backend.tar, the archive of the tree under test, in that directory)
set -u -o pipefail
WANT=${1:?the md5 of main-backend.tar}; DIR=${2:-main-check}; shift; [ $# -gt 0 ] && shift
[ $# -gt 0 ] || set -- indirect_check zero_skip
W=$HOME/bc5-work; E=$W/exp0380; I=$E/$DIR; LOCK=$W/BOX-LOCK
fail() { echo "FAIL: $*"; exit 1; }
box() { distrobox enter ubuntu -- sh -c "$1"; }
# catch2 <log name> [filter]: the rc, then the summary line; "No tests ran" has no such line
catch2() {
  local out=$I/$1.out rc sum
  box "cd '$I/build' && nice -n 19 ./bc5_backend_tests ${2:+'$2'}" > "$out" 2>&1; rc=$?
  sum=$(grep -E '^All tests passed \([0-9]+ assertions? in [1-9][0-9]* test cases?\)' "$out" | tail -1)
  echo "$1 rc $rc: ${sum:-no passing summary: $(tail -3 "$out" | tr '\n' ' ')}"
  [ "$rc" = 0 ] || fail "$1 rc $rc"
  [ -n "$sum" ] || fail "$1 ran no tests or reported no pass"
}
# selftest <log name> [options]: never --submit
selftest() {
  local out=$I/$1.out rc
  box "cd '$I/build' && ./direct-selftest $2" > "$out" 2>&1; rc=$?
  echo "$1 rc $rc: $(tail -1 "$out")"
  [ "$rc" = 0 ] || fail "$1 rc $rc"
  grep -q '^direct-selftest: nothing done without --submit' "$out" || fail "$1 did not report doing nothing"
}
pgrep '^kyty_emulator' > /dev/null && fail "an emulator runs"
grep -q '^top exp 0380 |' "$LOCK" || fail "the lock line is not this session's: $(cat "$LOCK")"
GOT=$(md5sum < "$I/main-backend.tar" | cut -d' ' -f1)
[ "$GOT" = "$WANT" ] || fail "main-backend.tar is md5 $GOT, not $WANT"
echo "== $(date +%T) main backend (tar md5 $GOT): Catch2 and direct-selftest"
rm -rf "$I/src" "$I/build"
mkdir -p "$I/src" && tar -xf "$I/main-backend.tar" -C "$I/src" || fail "the archive did not extract"
CATCH=$(ls -d "$W"/exp03*/backend-tests/_deps/catch2-src "$W"/exp03*/backend-build/_deps/catch2-src 2> /dev/null | head -1)
CATCH_ARG=""; [ -n "$CATCH" ] && CATCH_ARG="-DFETCHCONTENT_SOURCE_DIR_CATCH2=$CATCH" && echo "Catch2 from $CATCH"
box "nice -n 19 cmake -S '$I/src/backend' -B '$I/build' -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=ON $CATCH_ARG && nice -n 19 cmake --build '$I/build' -j8" > "$I/build.out" 2>&1
rc=$?; echo "build rc $rc; errors $(grep -c 'error:' "$I/build.out"), warnings $(grep -c 'warning:' "$I/build.out")"
[ "$rc" = 0 ] || { tail -20 "$I/build.out"; fail "build rc $rc"; }
catch2 tests
for tg in "$@"; do catch2 "$tg" "[$tg]"; done
selftest selftest-plain ""
selftest selftest-checks "--cp-check --zero-check"
echo "== $(date +%T) done: all passed"
