#!/usr/bin/env bash
# BC5 experiment 0379, test shortcut (build0379.sh; the maintainer's yes "Tak, przygotuj", 2026-10-29): one private
# emulator, ~/bc5-work/exp0379t/kyty_emulator =
#   the shared normal build's objects (58c4a627)
#   + src/libs/bc5LleAgc.cpp with exp 0379's zero skip (patch0379-bc5LleAgc.diff, header src/bc5/zero_skip.hpp)
#   + a PRIVATE backend archive built from main's backend with exp 0379's header and tests and exp 0380's backend
#     change (origin/exp/0380-zero-dim-dispatch ed68b12: BC5_DIRECT_FORCE_START_000, BC5_DIRECT_GPU_CHECK_ZERO, both
#     default off; test0379t/0380-backend-ed68b12.diff on the merge base 0c13576, whose backend equals main's).
# The archive is configured as the shared one (clang, Release, BC5_WITH_AMDGPU=ON) and its Catch2 tests run in a
# second build directory; the emulator is linked only when they pass. The host never includes the header 0380 changes
# (bc5/indirect_check.hpp) and bc5/direct.hpp is unchanged, so the shared objects link with the private archive.
# ~/src/KytyPlus, the shared builds, ~/bc5-work/backend-ubuntu and play-pkg.sh are only read.
# Layout on the box: the experiment directory in ~/bc5-work/exp0379t/in/ (raw/, src/, test0379t/, the diff) and the
# branch's backend/ in ~/bc5-work/exp0379t/in/backend/.
# usage: bash ~/bc5-work/exp0379t/in/test0379t/build0379t.sh   (CPU only, nice 19, ~10 min, no emulator)
set -u
E=$HOME/bc5-work/exp0379t; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
B=$HOME/bc5-work/kytyplus-build; ARCH=$HOME/bc5-work/backend-ubuntu/libbc5_backend.a
EXPECT_ARCHIVE=${EXPECT_ARCHIVE:-bb50b2e0}; EXPECT_NORMAL=${EXPECT_NORMAL:-58c4a627}
EXPECT_TREE_UNIT=${EXPECT_TREE_UNIT:-e7cc2f60}  # the tree's bc5LleAgc.cpp = patch 0001's (git blob 8d2f498)
EXPECT_UNIT=${EXPECT_UNIT:-e62113a5}; EXPECT_HDR=${EXPECT_HDR:-782ca0e9}; EXPECT_DIFF=${EXPECT_DIFF:-6f0c7c16}  # exp 0379's
EXPECT_0380=${EXPECT_0380:-c14097de}  # exp 0380's backend diff
HERE=$(cd "$(dirname "$0")" && pwd); IN=$(cd "$HERE/.." && pwd)
TREE=$HOME/src/KytyPlus; SRC=$E/src; BM=$E/backend-merged; BA=$E/backend-archive; BT=$E/backend-tests
mkdir -p "$R"
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
grep -q "MAINTAINER PLAYING" "$LOCK" && { echo "the maintainer plays: stop"; exit 1; }
[ -s "$LOCK" ] && ! grep -q "^top exp 0379 |" "$LOCK" && { echo "box locked: $(cat "$LOCK")"; exit 1; }
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$B/src/kyty_emulator")" = "$EXPECT_NORMAL" ] || { echo "the shared normal binary is $(m "$B/src/kyty_emulator"), not $EXPECT_NORMAL: stop"; exit 1; }
[ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] || { echo "the shared archive is $(m "$ARCH"), not $EXPECT_ARCHIVE: stop"; exit 1; }
[ "$(m "$TREE/src/libs/bc5LleAgc.cpp")" = "$EXPECT_TREE_UNIT" ] || { echo "the tree's bc5LleAgc.cpp is $(m "$TREE/src/libs/bc5LleAgc.cpp"), not $EXPECT_TREE_UNIT: stop"; exit 1; }
[ "$(m "$IN/patch0379-bc5LleAgc.diff")" = "$EXPECT_DIFF" ] || { echo "the diff is $(m "$IN/patch0379-bc5LleAgc.diff"), not $EXPECT_DIFF: stop"; exit 1; }
[ "$(m "$IN/src/bc5/zero_skip.hpp")" = "$EXPECT_HDR" ] || { echo "zero_skip.hpp is $(m "$IN/src/bc5/zero_skip.hpp"), not $EXPECT_HDR: stop"; exit 1; }
[ "$(m "$HERE/0380-backend-ed68b12.diff")" = "$EXPECT_0380" ] || { echo "the 0380 diff is $(m "$HERE/0380-backend-ed68b12.diff"), not $EXPECT_0380: stop"; exit 1; }
[ -f "$HERE/build0379t.py" ] && [ -f "$IN/backend/CMakeLists.txt" ] && cmp -s "$IN/backend/include/bc5/zero_skip.hpp" "$IN/src/bc5/zero_skip.hpp" || { echo "no build0379t.py or no backend/ with the same zero_skip.hpp in $IN"; exit 1; }
echo "top exp 0379 | build of ~/bc5-work/exp0379t/kyty_emulator (a private backend archive with exp 0380, its Catch2 tests, bc5LleAgc.cpp with exp 0379's diff, relinked; CPU only, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +15min +%H:%M)" > "$LOCK"
trap 'grep -q "^top exp 0379 | build" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
{ echo "shared binary md5 $(m "$B/src/kyty_emulator"); shared archive $(m "$ARCH"); tree bc5LleAgc.cpp $(m "$TREE/src/libs/bc5LleAgc.cpp"); 0379 diff $(m "$IN/patch0379-bc5LleAgc.diff") header $(m "$IN/src/bc5/zero_skip.hpp"); 0380 diff $(m "$HERE/0380-backend-ed68b12.diff")"; } > "$R/build-inputs.txt"; cat "$R/build-inputs.txt"
# 1. The merged backend: the branch's backend/ (main's + exp 0379's header and test) with exp 0380's backend diff.
rm -rf "$BM"; mkdir -p "$BM"; cp -a "$IN/backend" "$BM/backend" || exit 1
distrobox enter ubuntu -- sh -c "cd '$BM' && patch -p1 --no-backup-if-mismatch < '$HERE/0380-backend-ed68b12.diff'" > "$R/patch0380.out" 2>&1 || { cat "$R/patch0380.out"; echo "exp 0380's diff did not apply"; exit 1; }
echo "merged backend: exp 0380 marks $(grep -c 'experiment 0380' "$BM/backend/src/direct.cpp") in direct.cpp, $(grep -c 'experiment 0380' "$BM/backend/src/indirect_check.cpp") in indirect_check.cpp; zero_skip.hpp $(m "$BM/backend/include/bc5/zero_skip.hpp")"
CATCH=$(ls -d "$HOME"/bc5-work/exp03*/backend-tests/_deps/catch2-src "$HOME"/bc5-work/exp03*/backend-build/_deps/catch2-src 2> /dev/null | head -1)
CATCH_ARG=""; [ -n "$CATCH" ] && CATCH_ARG="-DFETCHCONTENT_SOURCE_DIR_CATCH2=$CATCH" && echo "Catch2 from $CATCH"
echo "== $(date +%T) the private archive (as the shared one: clang, Release, BC5_WITH_AMDGPU=ON, no tests)"
distrobox enter ubuntu -- sh -c "nice -n 19 cmake -S '$BM/backend' -B '$BA' -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=OFF && nice -n 19 cmake --build '$BA' --target bc5_backend -j8" > "$R/archive-build.out" 2>&1
rc=$?; echo "== $(date +%T) archive rc $rc; errors $(grep -c 'error:' "$R/archive-build.out"), warnings $(grep -c 'warning:' "$R/archive-build.out")"
PARCH=$BA/libbc5_backend.a
[ $rc = 0 ] && [ -f "$PARCH" ] || { echo "the private archive did not build: see $R/archive-build.out"; exit 1; }
echo "== $(date +%T) the merged backend's Catch2 tests"
distrobox enter ubuntu -- sh -c "nice -n 19 cmake -S '$BM/backend' -B '$BT' -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=ON $CATCH_ARG && nice -n 19 cmake --build '$BT' --target bc5_backend_tests -j8" > "$R/backend-build.out" 2>&1
rc=$?; echo "== $(date +%T) tests build rc $rc; errors $(grep -c 'error:' "$R/backend-build.out"), warnings $(grep -c 'warning:' "$R/backend-build.out")"
[ $rc = 0 ] && [ -x "$BT/bc5_backend_tests" ] || { echo "the tests did not build: see $R/backend-build.out"; exit 1; }
distrobox enter ubuntu -- sh -c "cd '$BT' && nice -n 19 ./bc5_backend_tests" > "$R/backend-tests.out" 2>&1
trc=$?; tail -2 "$R/backend-tests.out"; echo "== tests rc $trc"
for tg in zero_skip indirect_check; do distrobox enter ubuntu -- sh -c "cd '$BT' && ./bc5_backend_tests '[$tg]'" > "$R/backend-tests-$tg.out" 2>&1; echo "[$tg] $(tail -2 "$R/backend-tests-$tg.out" | tr '\n' ' ')"; done
[ $trc = 0 ] || { echo "backend tests FAILED (rc $trc); no emulator linked"; exit 2; }
# 2. The private tree: the tree's bc5LleAgc.cpp with exp 0379's diff, and the header.
rm -rf "$SRC" "$E/obj"; mkdir -p "$SRC/src/libs" "$SRC/src/bc5"
cp "$TREE/src/libs/bc5LleAgc.cpp" "$SRC/src/libs/bc5LleAgc.cpp" || exit 1
cp "$IN/src/bc5/zero_skip.hpp" "$SRC/src/bc5/zero_skip.hpp" || exit 1
distrobox enter ubuntu -- sh -c "cd '$SRC' && patch -p1 --no-backup-if-mismatch < '$IN/patch0379-bc5LleAgc.diff'" > "$R/patch.out" 2>&1 || { cat "$R/patch.out"; echo "the diff did not apply"; exit 1; }
[ "$(m "$SRC/src/libs/bc5LleAgc.cpp")" = "$EXPECT_UNIT" ] || { echo "the patched unit is $(m "$SRC/src/libs/bc5LleAgc.cpp"), not $EXPECT_UNIT: stop"; exit 1; }
echo "== $(date +%T) compdb"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
BIN=$E/kyty_emulator
if [ -f "$BIN" ]; then OLD=$BIN.$(m "$BIN"); [ -e "$OLD" ] || mv "$BIN" "$OLD"; echo "previous binary kept as $OLD"; fi
echo "== $(date +%T) compile + relink with the private archive $(m "$PARCH")"
distrobox enter ubuntu -- python3 -I "$HERE/build0379t.py" "$E/compdb.json" "$SRC" "$E" "$B" "$BIN" "$PARCH" > "$R/build.out" 2>&1
rc=$?; echo "== $(date +%T) rc $rc; errors $(grep -c 'error:' "$R/build.out"), warnings $(grep -c 'warning:' "$R/build.out")"
grep -n "error:\|undefined\|COMPILE FAILED\|Assertion" "$R/build.out" | head -20
[ $rc = 0 ] && [ -x "$BIN" ] || { echo "build failed: see $R/build.out"; exit 1; }
m "$BIN" > "$E/binary.md5"; m "$PARCH" > "$E/archive.md5"
echo "md5 $(cat "$E/binary.md5") (shared $EXPECT_NORMAL), private archive $(cat "$E/archive.md5")"
echo "strings: zero skip $(strings "$BIN" | grep -c '^zero skip: '), zero scan $(strings "$BIN" | grep -c '^zero scan %u'), exp 0380 switch lines $(strings "$BIN" | grep -c 'experiment 0380 switch'), FORCE_START env $(strings "$BIN" | grep -c '^BC5_DIRECT_FORCE_START_000$')"
echo "$(date '+%F %T') $(cat "$E/binary.md5") kyty_emulator: the shared objects ($EXPECT_NORMAL) + bc5LleAgc.cpp of exp 0379 ($EXPECT_UNIT) + the private archive $(cat "$E/archive.md5") (main + 0379 header + 0380 ed68b12); Catch2 rc $trc; rc $rc" >> "$R/binaries.txt"
echo "shared binary after: $(m "$B/src/kyty_emulator") (want $EXPECT_NORMAL); shared archive after: $(m "$ARCH") (want $EXPECT_ARCHIVE); tree bc5LleAgc.cpp after: $(m "$TREE/src/libs/bc5LleAgc.cpp") (want $EXPECT_TREE_UNIT)"
