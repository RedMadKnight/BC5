#!/usr/bin/env bash
# BC5 experiment 0379 (exp 0372's build0372.sh): one private emulator, ~/bc5-work/exp0379/kyty_emulator, whose
# src/libs/bc5LleAgc.cpp is the tree's file (patch 0001 9420cfa0) with patch0379-bc5LleAgc.diff applied (the zero scan
# and the zero skip; the header src/bc5/zero_skip.hpp beside it). A PRIVATE source tree under ~/bc5-work/exp0379/src
# holds the two files; the unit is compiled with the shared normal build's compdb command (the private tree's src/ first
# on the include path) into a private object, and the shared link command is run with that object (the shared backend
# archive as it is: the header is header-only). Before that, the backend copied beside this experiment is configured
# and built privately and its Catch2 tests run; the emulator is linked only when they pass. ~/src/KytyPlus, the shared
# builds and the archive are only read; a previous private binary is kept beside the new one as kyty_emulator.<md5>.
# Layout on the box: the committed experiment directory in ~/bc5-work/exp0379/in/ (src/, raw/, the diff) and the
# repository's backend/ in ~/bc5-work/exp0379/in/backend/.
# usage: bash ~/bc5-work/exp0379/in/raw/build0379.sh   (CPU only, nice 19, ~5 min, no emulator)
set -u
E=$HOME/bc5-work/exp0379; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
B=$HOME/bc5-work/kytyplus-build; ARCH=$HOME/bc5-work/backend-ubuntu/libbc5_backend.a
EXPECT_ARCHIVE=${EXPECT_ARCHIVE:-bb50b2e0}; EXPECT_NORMAL=${EXPECT_NORMAL:-58c4a627}
EXPECT_TREE_UNIT=${EXPECT_TREE_UNIT:-e7cc2f60}  # the tree's bc5LleAgc.cpp = patch 0001's (git blob 8d2f498)
EXPECT_UNIT=${EXPECT_UNIT:-e62113a5}; EXPECT_HDR=${EXPECT_HDR:-782ca0e9}; EXPECT_DIFF=${EXPECT_DIFF:-6f0c7c16}  # this experiment's
HERE=$(cd "$(dirname "$0")" && pwd); IN=$(cd "$HERE/.." && pwd)
TREE=$HOME/src/KytyPlus; SRC=$E/src; BSRC=$IN/backend; BB=$E/backend-build
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
[ "$(m "$IN/src/bc5/zero_skip.hpp")" = "$EXPECT_HDR" ] || { echo "in/src/bc5/zero_skip.hpp is $(m "$IN/src/bc5/zero_skip.hpp"), not $EXPECT_HDR: stop"; exit 1; }
[ -f "$HERE/build0379.py" ] || { echo "no build0379.py beside this script"; exit 1; }
[ -f "$BSRC/CMakeLists.txt" ] && cmp -s "$BSRC/include/bc5/zero_skip.hpp" "$IN/src/bc5/zero_skip.hpp" && [ -f "$BSRC/tests/zero_skip_test.cpp" ] || { echo "no backend/ with the same zero_skip.hpp and its test in $IN"; exit 1; }
echo "top exp 0379 | build of ~/bc5-work/exp0379/kyty_emulator (the backend's Catch2 tests, then bc5LleAgc.cpp + the exp 0379 diff compiled in a private tree, relinked; CPU only, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +12min +%H:%M)" > "$LOCK"
trap 'grep -q "^top exp 0379 | build" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
{ echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(m "$B/src/kyty_emulator"); shared archive $(m "$ARCH"); tree bc5LleAgc.cpp $(m "$TREE/src/libs/bc5LleAgc.cpp"); diff $(m "$IN/patch0379-bc5LleAgc.diff") header $(m "$IN/src/bc5/zero_skip.hpp") test $(m "$BSRC/tests/zero_skip_test.cpp")"; } > "$R/build-inputs.txt"; cat "$R/build-inputs.txt"
# 1. The backend's Catch2 tests (the archive itself is not used: the header is header-only).
CATCH=$(ls -d "$HOME"/bc5-work/exp03*/backend-tests/_deps/catch2-src "$HOME"/bc5-work/exp03*/backend-build/_deps/catch2-src 2> /dev/null | head -1)
CATCH_ARG=""; [ -n "$CATCH" ] && CATCH_ARG="-DFETCHCONTENT_SOURCE_DIR_CATCH2=$CATCH" && echo "Catch2 from $CATCH"
echo "== $(date +%T) backend configure + build (tests)"
distrobox enter ubuntu -- sh -c "cd '$E' && nice -n 19 cmake -S '$BSRC' -B '$BB' -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=ON $CATCH_ARG && nice -n 19 cmake --build '$BB' --target bc5_backend_tests -j8" > "$R/backend-build.out" 2>&1
rc=$?; echo "== $(date +%T) backend build rc $rc; errors $(grep -c 'error:' "$R/backend-build.out"), warnings $(grep -c 'warning:' "$R/backend-build.out")"
grep -n "error:" "$R/backend-build.out" | head -10
[ $rc = 0 ] && [ -x "$BB/bc5_backend_tests" ] || { echo "backend tests did not build: see $R/backend-build.out"; exit 1; }
distrobox enter ubuntu -- sh -c "cd '$BB' && nice -n 19 ./bc5_backend_tests" > "$R/backend-tests.out" 2>&1
trc=$?; tail -3 "$R/backend-tests.out"; echo "== tests rc $trc"
distrobox enter ubuntu -- sh -c "cd '$BB' && ./bc5_backend_tests '[zero_skip]'" > "$R/backend-tests-zero_skip.out" 2>&1; tail -3 "$R/backend-tests-zero_skip.out"
[ $trc = 0 ] || { echo "backend tests FAILED (rc $trc): see $R/backend-tests.out; no emulator linked"; exit 2; }
# 2. The private tree: the tree's bc5LleAgc.cpp with the experiment's diff, and the header (every other include comes
#    from the shared tree). patch(1) is in the ubuntu container, not on the host.
rm -rf "$SRC" "$E/obj"; mkdir -p "$SRC/src/libs" "$SRC/src/bc5"
cp "$TREE/src/libs/bc5LleAgc.cpp" "$SRC/src/libs/bc5LleAgc.cpp" || exit 1
cp "$IN/src/bc5/zero_skip.hpp" "$SRC/src/bc5/zero_skip.hpp" || exit 1
distrobox enter ubuntu -- sh -c "cd '$SRC' && patch -p1 --no-backup-if-mismatch < '$IN/patch0379-bc5LleAgc.diff'" > "$R/patch.out" 2>&1 || { cat "$R/patch.out"; echo "the diff did not apply"; exit 1; }
[ "$(m "$SRC/src/libs/bc5LleAgc.cpp")" = "$EXPECT_UNIT" ] || { echo "the patched unit is $(m "$SRC/src/libs/bc5LleAgc.cpp"), not $EXPECT_UNIT: stop"; exit 1; }
echo "bc5LleAgc.cpp: $(grep -c 'experiment 0379' "$SRC/src/libs/bc5LleAgc.cpp") marks"
echo "== $(date +%T) compdb"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
BIN=$E/kyty_emulator
if [ -f "$BIN" ]; then OLD=$BIN.$(m "$BIN"); [ -e "$OLD" ] || mv "$BIN" "$OLD"; echo "previous binary kept as $OLD"; fi
echo "== $(date +%T) compile + relink"
distrobox enter ubuntu -- python3 -I "$HERE/build0379.py" "$E/compdb.json" "$SRC" "$E" "$B" "$BIN" > "$R/build.out" 2>&1
rc=$?; echo "== $(date +%T) rc $rc; errors $(grep -c 'error:' "$R/build.out"), warnings $(grep -c 'warning:' "$R/build.out")"
grep -n "error:\|undefined\|COMPILE FAILED" "$R/build.out" | head -20
[ $rc = 0 ] && [ -x "$BIN" ] || { echo "build failed: see $R/build.out"; exit 1; }
m "$BIN" > "$E/binary.md5"; echo "md5 $(cat "$E/binary.md5") (shared $EXPECT_NORMAL)"
[ "$(cat "$E/binary.md5")" != "$EXPECT_NORMAL" ] || { echo "the binary equals the shared one"; exit 1; }
echo "strings: zero skip $(strings "$BIN" | grep -c '^zero skip: '), zero scan $(strings "$BIN" | grep -c '^zero scan %u'), switches $(strings "$BIN" | grep -c '^BC5_DIRECT_ZERO')"
echo "$(date '+%F %T') $(cat "$E/binary.md5") kyty_emulator: the shared objects ($EXPECT_NORMAL) with bc5LleAgc.cpp of exp 0379 ($EXPECT_UNIT) + the shared archive $EXPECT_ARCHIVE; Catch2 rc $trc; rc $rc" >> "$R/binaries.txt"
echo "shared binary after: $(m "$B/src/kyty_emulator") (want $EXPECT_NORMAL); shared archive after: $(m "$ARCH") (want $EXPECT_ARCHIVE); tree bc5LleAgc.cpp after: $(m "$TREE/src/libs/bc5LleAgc.cpp") (want $EXPECT_TREE_UNIT)"
