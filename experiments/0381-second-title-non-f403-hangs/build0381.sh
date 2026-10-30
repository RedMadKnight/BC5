#!/usr/bin/env bash
# BC5 exp 0381 (exp 0379's build0379.sh): one private emulator, ~/bc5-work/exp0381/kyty_emulator: J1's binary e1cc0c92
# (the shared objects + bc5LleAgc.cpp with exp 0379's diff) with patch0381-bc5LleAgc.diff on top, so it differs from J1's
# binary by BC5_DIRECT_ACB_STATE_RESTORE alone. A private tree under ~/bc5-work/exp0381/src holds the unit and the two
# headers; the compile and link are exp 0379's. The backend beside it is built privately and its Catch2 tests run first;
# the emulator is linked only when they pass. ~/src/KytyPlus, the shared builds and the archive are only read.
# Layout: `git archive HEAD backend experiments/0381-second-title-non-f403-hangs` extracted in ~/bc5-work/exp0381/in/.
# usage (under the top session's GO): bash ~/bc5-work/exp0381/in/experiments/0381-second-title-non-f403-hangs/build0381.sh
# CPU only, nice 19, ~5 min, no emulator.
set -u
E=$HOME/bc5-work/exp0381; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK; S79=$HOME/bc5-work/exp0379/src
B=$HOME/bc5-work/kytyplus-build; ARCH=$HOME/bc5-work/backend-ubuntu/libbc5_backend.a
EXPECT_ARCHIVE=${EXPECT_ARCHIVE:-bb50b2e0}; EXPECT_NORMAL=${EXPECT_NORMAL:-58c4a627}
EXPECT_BASE=e62113a5; EXPECT_UNIT=637f964c; EXPECT_DIFF=d36d6fb7  # the 0379 unit, the patched unit, this experiment's diff
HERE=$(cd "$(dirname "$0")" && pwd); IN=$E/in; SRC=$E/src; BB=$E/backend-build
mkdir -p "$R"
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
grep -q "MAINTAINER PLAYING" "$LOCK" && { echo "the maintainer plays: stop"; exit 1; }
[ -s "$LOCK" ] && ! grep -q "^top exp 0381 |" "$LOCK" && { echo "box locked: $(cat "$LOCK")"; exit 1; }
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$B/src/kyty_emulator")" = "$EXPECT_NORMAL" ] || { echo "the shared normal binary is $(m "$B/src/kyty_emulator"), not $EXPECT_NORMAL: stop"; exit 1; }
[ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] || { echo "the shared archive is $(m "$ARCH"), not $EXPECT_ARCHIVE: stop"; exit 1; }
[ "$(m "$S79/src/libs/bc5LleAgc.cpp")" = "$EXPECT_BASE" ] || { echo "exp 0379's unit is $(m "$S79/src/libs/bc5LleAgc.cpp"), not $EXPECT_BASE: stop"; exit 1; }
[ "$(m "$HERE/patch0381-bc5LleAgc.diff")" = "$EXPECT_DIFF" ] || { echo "the diff is $(m "$HERE/patch0381-bc5LleAgc.diff"), not $EXPECT_DIFF: stop"; exit 1; }
echo "top exp 0381 | build of ~/bc5-work/exp0381/kyty_emulator (backend Catch2 tests, then bc5LleAgc.cpp + exp 0381's diff, relinked; CPU only, nice 19, no emulator) | start $(date +%H:%M)" > "$LOCK"
trap 'grep -q "^top exp 0381 | build" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
# 1. The backend's Catch2 tests (the archive itself is not used: the header is header-only).
CATCH=$(ls -d "$HOME"/bc5-work/exp03*/backend-build/_deps/catch2-src 2> /dev/null | grep -v exp0381 | head -1)
CATCH_ARG=""; [ -n "$CATCH" ] && CATCH_ARG="-DFETCHCONTENT_SOURCE_DIR_CATCH2=$CATCH" && echo "Catch2 from $CATCH"
echo "== $(date +%T) backend configure + build (tests)"
distrobox enter ubuntu -- sh -c "cd '$E' && nice -n 19 cmake -S '$IN/backend' -B '$BB' -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=ON $CATCH_ARG && nice -n 19 cmake --build '$BB' --target bc5_backend_tests -j8" < /dev/null > "$R/backend-build.out" 2>&1
rc=$?; echo "== $(date +%T) backend build rc $rc; errors $(grep -c 'error:' "$R/backend-build.out"), warnings $(grep -c 'warning:' "$R/backend-build.out")"
grep -n "error:" "$R/backend-build.out" | head -10
[ $rc = 0 ] && [ -x "$BB/bc5_backend_tests" ] || { echo "backend tests did not build"; exit 1; }
distrobox enter ubuntu -- sh -c "cd '$BB' && nice -n 19 ./bc5_backend_tests" < /dev/null > "$R/backend-tests.out" 2>&1
trc=$?; tail -3 "$R/backend-tests.out"; echo "== tests rc $trc"
[ $trc = 0 ] || { echo "backend tests FAILED: no emulator linked"; exit 2; }
# 2. The private tree.
rm -rf "$SRC" "$E/obj"; mkdir -p "$SRC/src/libs" "$SRC/src/bc5"
cp "$S79/src/libs/bc5LleAgc.cpp" "$SRC/src/libs/bc5LleAgc.cpp" || exit 1
cp "$S79/src/bc5/zero_skip.hpp" "$IN/backend/include/bc5/acb_restore.hpp" "$SRC/src/bc5/" || exit 1
distrobox enter ubuntu -- sh -c "cd '$SRC' && patch -p1 --no-backup-if-mismatch < '$HERE/patch0381-bc5LleAgc.diff'" < /dev/null > "$R/patch.out" 2>&1 || { cat "$R/patch.out"; echo "the diff did not apply"; exit 1; }
[ "$(m "$SRC/src/libs/bc5LleAgc.cpp")" = "$EXPECT_UNIT" ] || { echo "the patched unit is $(m "$SRC/src/libs/bc5LleAgc.cpp"), not $EXPECT_UNIT: stop"; exit 1; }
echo "bc5LleAgc.cpp: $(grep -c -i 'experiment 0381\|exp 0381' "$SRC/src/libs/bc5LleAgc.cpp") marks"
echo "== $(date +%T) compdb"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" < /dev/null > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
BIN=$E/kyty_emulator
if [ -f "$BIN" ]; then OLD=$BIN.$(m "$BIN"); [ -e "$OLD" ] || mv "$BIN" "$OLD"; echo "previous binary kept as $OLD"; fi
echo "== $(date +%T) compile + relink"
distrobox enter ubuntu -- python3 -I "$HERE/build0381.py" "$E/compdb.json" "$SRC" "$E" "$B" "$BIN" < /dev/null > "$R/build.out" 2>&1
rc=$?; echo "== $(date +%T) rc $rc; errors $(grep -c 'error:' "$R/build.out"), warnings $(grep -c 'warning:' "$R/build.out")"
grep -n "error:\|undefined\|COMPILE FAILED" "$R/build.out" | head -20
[ $rc = 0 ] && [ -x "$BIN" ] || { echo "build failed: see $R/build.out"; exit 1; }
echo "md5 $(m "$BIN") (J1's e1cc0c92, shared $EXPECT_NORMAL)"
echo "strings: switch $(strings "$BIN" | grep -c '^BC5_DIRECT_ACB_STATE_RESTORE$'), journal line $(strings "$BIN" | grep -c '^acb state restore (exp 0381)')"
echo "$(date '+%F %T') $(m "$BIN") kyty_emulator: the shared objects ($EXPECT_NORMAL) with bc5LleAgc.cpp $EXPECT_UNIT + the shared archive $EXPECT_ARCHIVE; Catch2 rc $trc; rc $rc" >> "$R/binaries.txt"
echo "shared binary after: $(m "$B/src/kyty_emulator") (want $EXPECT_NORMAL); shared archive after: $(m "$ARCH") (want $EXPECT_ARCHIVE)"
