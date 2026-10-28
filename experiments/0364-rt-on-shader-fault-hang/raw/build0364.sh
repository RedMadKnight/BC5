#!/usr/bin/env bash
# BC5 experiment 0364 (exp 0359's pattern): one private emulator, ~/bc5-work/exp0364/kyty_emulator, with the fault-view
# trap and the compute user-data hint (backend/include/bc5/user_data_hint.hpp) — the shared host tree's
# src/libs/bc5LleAgc.cpp copied into a PRIVATE source tree with its sibling headers and the backend header,
# patch0364.pl applied there, the unit compiled with the shared normal build's compdb command into a private object,
# the shared link command run with that object (the shared backend archive as it is: the header is header-only).
# Before that, this experiment's backend/ (beside the script) is configured and built privately and its Catch2 tests
# run; the emulator is linked only when they pass. ~/src/KytyPlus, the shared builds and the archive are only read;
# a previous private binary is kept beside the new one as kyty_emulator.<md5>.
# usage: build0364.sh   (on the box, with patch0364.pl, build0364.py and backend/ beside it; CPU only, nice 19, ~5 min)
set -u
E=$HOME/bc5-work/exp0364; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
B=$HOME/bc5-work/kytyplus-build; ARCH=$HOME/bc5-work/backend-ubuntu/libbc5_backend.a
EXPECT_ARCHIVE=${EXPECT_ARCHIVE:-bb50b2e0}; EXPECT_NORMAL=${EXPECT_NORMAL:-affa0c22}; EXPECT_AGC=${EXPECT_AGC:-e7cc2f60}
HERE=$(cd "$(dirname "$0")" && pwd)
TREE=$HOME/src/KytyPlus; SRC=$E/src; BSRC=$HERE/backend; BB=$E/backend-build
UNIT=src/libs/bc5LleAgc.cpp
mkdir -p "$R"
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
grep -q "MAINTAINER PLAYING" "$LOCK" && { echo "the maintainer plays: stop"; exit 1; }
[ -s "$LOCK" ] && ! grep -q "^bvh exp 0364 |" "$LOCK" && { echo "box locked: $(cat "$LOCK")"; exit 1; }
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$B/src/kyty_emulator")" = "$EXPECT_NORMAL" ] || { echo "the shared normal binary is $(m "$B/src/kyty_emulator"), not $EXPECT_NORMAL: stop"; exit 1; }
[ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] || { echo "the shared archive is $(m "$ARCH"), not $EXPECT_ARCHIVE: stop"; exit 1; }
[ "$(m "$TREE/$UNIT")" = "$EXPECT_AGC" ] || { echo "bc5LleAgc.cpp is $(m "$TREE/$UNIT"), not $EXPECT_AGC: stop"; exit 1; }
for f in patch0364.pl build0364.py; do [ -f "$HERE/$f" ] || { echo "no $f beside this script"; exit 1; }; done
[ -f "$BSRC/CMakeLists.txt" ] && [ -f "$BSRC/include/bc5/user_data_hint.hpp" ] && [ -f "$BSRC/tests/user_data_hint_test.cpp" ] || { echo "no backend/ with the user-data hint beside this script"; exit 1; }
echo "bvh exp 0364 | build of ~/bc5-work/exp0364/kyty_emulator (the backend's Catch2 tests, then one host unit patched in a private copy, compiled, relinked; CPU only, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +12min +%H:%M)" > "$LOCK"
trap 'grep -q "^bvh exp 0364 | build" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
{ echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(m "$B/src/kyty_emulator"); shared archive $(m "$ARCH"); unit bc5LleAgc $(m "$TREE/$UNIT"); patch0364.pl $(m "$HERE/patch0364.pl"); backend header $(m "$BSRC/include/bc5/user_data_hint.hpp") test $(m "$BSRC/tests/user_data_hint_test.cpp")"; } > "$R/build-inputs.txt"; cat "$R/build-inputs.txt"
# 1. The backend's Catch2 tests (the archive itself is not used: the hint's header is header-only).
CATCH=$(ls -d "$HOME"/bc5-work/exp03*/backend-tests/_deps/catch2-src "$HOME"/bc5-work/exp03*/backend-build/_deps/catch2-src 2> /dev/null | head -1)
CATCH_ARG=""; [ -n "$CATCH" ] && CATCH_ARG="-DFETCHCONTENT_SOURCE_DIR_CATCH2=$CATCH" && echo "Catch2 from $CATCH"
echo "== $(date +%T) backend configure + build (tests)"
distrobox enter ubuntu -- sh -c "cd '$E' && nice -n 19 cmake -S '$BSRC' -B '$BB' -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=ON $CATCH_ARG && nice -n 19 cmake --build '$BB' --target bc5_backend_tests -j8" > "$R/backend-build.out" 2>&1
rc=$?; echo "== $(date +%T) backend build rc $rc; errors $(grep -c 'error:' "$R/backend-build.out"), warnings $(grep -c 'warning:' "$R/backend-build.out")"
grep -n "error:" "$R/backend-build.out" | head -10
[ $rc = 0 ] && [ -x "$BB/bc5_backend_tests" ] || { echo "backend tests did not build: see $R/backend-build.out"; exit 1; }
distrobox enter ubuntu -- sh -c "cd '$BB' && nice -n 19 ./bc5_backend_tests" > "$R/backend-tests.out" 2>&1
trc=$?; tail -3 "$R/backend-tests.out"; echo "== tests rc $trc"
distrobox enter ubuntu -- sh -c "cd '$BB' && ./bc5_backend_tests '[user_data_hint]'" > "$R/backend-tests-user_data_hint.out" 2>&1; tail -3 "$R/backend-tests-user_data_hint.out"
[ $trc = 0 ] || { echo "backend tests FAILED (rc $trc): see $R/backend-tests.out; no emulator linked"; exit 2; }
# 2. The private host unit.
rm -rf "$SRC" "$E/obj"; mkdir -p "$SRC/src/libs" "$SRC/src/bc5"
cp "$TREE/$UNIT" "$SRC/$UNIT" || exit 1
for f in "$TREE"/src/libs/*.inc "$TREE"/src/libs/*.h; do [ -e "$f" ] && cp "$f" "$SRC/src/libs/"; done  # the unit's sibling includes
cp "$BSRC/include/bc5/user_data_hint.hpp" "$SRC/src/bc5/" || exit 1
perl "$HERE/patch0364.pl" "$SRC" > "$R/patch.out" 2>&1 || { echo "patch0364.pl failed:"; cat "$R/patch.out"; exit 1; }
cat "$R/patch.out"
diff -u "$TREE/$UNIT" "$SRC/$UNIT" > "$R/bc5LleAgc.cpp-0364.diff"; echo "$UNIT: $(grep -c '^[-+][^-+]' "$R/bc5LleAgc.cpp-0364.diff") lines changed, $(grep -c 'experiment 0364' "$SRC/$UNIT") marks"
grep -h 'hint user data: on\|fault view: 0x' "$SRC/$UNIT" | cat -A | grep -c '\\n"' | { read n; echo "C newline escapes intact in $n of 3 new format lines"; }
echo "== $(date +%T) compdb"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
BIN=$E/kyty_emulator
if [ -f "$BIN" ]; then OLD=$BIN.$(m "$BIN"); [ -e "$OLD" ] || mv "$BIN" "$OLD"; echo "previous binary kept as $OLD"; fi
echo "== $(date +%T) compile + relink"
distrobox enter ubuntu -- python3 -I "$HERE/build0364.py" "$E/compdb.json" "$SRC" "$E" "$B" "$BIN" > "$R/build.out" 2>&1
rc=$?; echo "== $(date +%T) rc $rc; errors $(grep -c 'error:' "$R/build.out"), warnings $(grep -c 'warning:' "$R/build.out")"
grep -n "error:\|undefined\|COMPILE FAILED" "$R/build.out" | head -20
[ $rc = 0 ] && [ -x "$BIN" ] || { echo "build failed: see $R/build.out"; exit 1; }
m "$BIN" > "$E/binary.md5"; echo "md5 $(cat "$E/binary.md5") (shared $EXPECT_NORMAL)"
[ "$(cat "$E/binary.md5")" != "$EXPECT_NORMAL" ] || { echo "the binary equals the shared one"; exit 1; }
echo "strings: hint lines $(strings "$BIN" | grep -c 'hint user data'), fault view $(strings "$BIN" | grep -c 'fault view:'), 0349 switch $(strings "$BIN" | grep -c 'experiment 0349: a job')"
echo "$(date '+%F %T') $(cat "$E/binary.md5") kyty_emulator: the shared objects ($EXPECT_NORMAL) with bc5LleAgc of patch0364.pl + the shared archive $EXPECT_ARCHIVE; Catch2 rc $trc; rc $rc" >> "$R/binaries.txt"
echo "shared binary after: $(m "$B/src/kyty_emulator") (want $EXPECT_NORMAL); shared archive after: $(m "$ARCH") (want $EXPECT_ARCHIVE); tree unit after: $(m "$TREE/$UNIT")"
