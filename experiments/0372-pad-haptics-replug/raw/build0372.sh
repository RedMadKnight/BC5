#!/usr/bin/env bash
# BC5 experiment 0372 (exp 0359's private-build pattern): one private emulator, ~/bc5-work/exp0372/kyty_emulator, whose
# src/libs/audio.cpp is this experiment's full copy (the pad ports follow the controller's audio device; the header
# src/bc5/pad_audio_route.hpp beside it). A PRIVATE source tree under ~/bc5-work/exp0372/src holds the two files; the
# unit is compiled with the shared normal build's compdb command (the private tree's src/ first on the include path)
# into a private object, and the shared link command is run with that object (the shared backend archive as it is:
# the header is header-only). Before that, the backend copied beside this experiment is configured and built
# privately and its Catch2 tests run; the emulator is linked only when they pass. ~/src/KytyPlus, the shared builds
# and the archive are only read; a previous private binary is kept beside the new one as kyty_emulator.<md5>.
# Layout on the box: the committed experiment directory copied to ~/bc5-work/exp0372/in/ (src/, raw/) and the
# repository's backend/ to ~/bc5-work/exp0372/in/backend/.
# usage: bash ~/bc5-work/exp0372/in/raw/build0372.sh   (CPU only, nice 19, ~5 min, no emulator)
set -u
E=$HOME/bc5-work/exp0372; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
B=$HOME/bc5-work/kytyplus-build; ARCH=$HOME/bc5-work/backend-ubuntu/libbc5_backend.a
EXPECT_ARCHIVE=${EXPECT_ARCHIVE:-bb50b2e0}; EXPECT_NORMAL=${EXPECT_NORMAL:-1000ad2a}
EXPECT_TREE_AUDIO=${EXPECT_TREE_AUDIO:-fa06c494}  # the tree's audio.cpp = patch 0001's (git blob 1bd9e82)
EXPECT_AUDIO=${EXPECT_AUDIO:-06d21dba}; EXPECT_HDR=${EXPECT_HDR:-51131854}  # this experiment's copies
HERE=$(cd "$(dirname "$0")" && pwd); IN=$(cd "$HERE/.." && pwd)
TREE=$HOME/src/KytyPlus; SRC=$E/src; BSRC=$IN/backend; BB=$E/backend-build
mkdir -p "$R"
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
grep -q "MAINTAINER PLAYING" "$LOCK" && { echo "the maintainer plays: stop"; exit 1; }
[ -s "$LOCK" ] && ! grep -q "^pad exp 0372 |" "$LOCK" && { echo "box locked: $(cat "$LOCK")"; exit 1; }
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$B/src/kyty_emulator")" = "$EXPECT_NORMAL" ] || { echo "the shared normal binary is $(m "$B/src/kyty_emulator"), not $EXPECT_NORMAL: stop"; exit 1; }
[ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] || { echo "the shared archive is $(m "$ARCH"), not $EXPECT_ARCHIVE: stop"; exit 1; }
[ "$(m "$TREE/src/libs/audio.cpp")" = "$EXPECT_TREE_AUDIO" ] || { echo "the tree's audio.cpp is $(m "$TREE/src/libs/audio.cpp"), not $EXPECT_TREE_AUDIO: stop"; exit 1; }
[ "$(m "$IN/src/libs/audio.cpp")" = "$EXPECT_AUDIO" ] || { echo "in/src/libs/audio.cpp is $(m "$IN/src/libs/audio.cpp"), not $EXPECT_AUDIO: stop"; exit 1; }
[ "$(m "$IN/src/bc5/pad_audio_route.hpp")" = "$EXPECT_HDR" ] || { echo "in/src/bc5/pad_audio_route.hpp is $(m "$IN/src/bc5/pad_audio_route.hpp"), not $EXPECT_HDR: stop"; exit 1; }
[ -f "$HERE/build0372.py" ] || { echo "no build0372.py beside this script"; exit 1; }
[ -f "$BSRC/CMakeLists.txt" ] && cmp -s "$BSRC/include/bc5/pad_audio_route.hpp" "$IN/src/bc5/pad_audio_route.hpp" && [ -f "$BSRC/tests/pad_audio_route_test.cpp" ] || { echo "no backend/ with the same pad_audio_route.hpp and its test in $IN"; exit 1; }
echo "pad exp 0372 | build of ~/bc5-work/exp0372/kyty_emulator (the backend's Catch2 tests, then audio.cpp from the experiment compiled in a private tree, relinked; CPU only, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +10min +%H:%M)" > "$LOCK"
trap 'grep -q "^pad exp 0372 | build" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
{ echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(m "$B/src/kyty_emulator"); shared archive $(m "$ARCH"); tree audio.cpp $(m "$TREE/src/libs/audio.cpp"); exp audio.cpp $(m "$IN/src/libs/audio.cpp") header $(m "$IN/src/bc5/pad_audio_route.hpp") test $(m "$BSRC/tests/pad_audio_route_test.cpp")"; } > "$R/build-inputs.txt"; cat "$R/build-inputs.txt"
# 1. The backend's Catch2 tests (the archive itself is not used: the route's header is header-only).
CATCH=$(ls -d "$HOME"/bc5-work/exp03*/backend-tests/_deps/catch2-src "$HOME"/bc5-work/exp03*/backend-build/_deps/catch2-src 2> /dev/null | head -1)
CATCH_ARG=""; [ -n "$CATCH" ] && CATCH_ARG="-DFETCHCONTENT_SOURCE_DIR_CATCH2=$CATCH" && echo "Catch2 from $CATCH"
echo "== $(date +%T) backend configure + build (tests)"
distrobox enter ubuntu -- sh -c "cd '$E' && nice -n 19 cmake -S '$BSRC' -B '$BB' -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=ON $CATCH_ARG && nice -n 19 cmake --build '$BB' --target bc5_backend_tests -j8" > "$R/backend-build.out" 2>&1
rc=$?; echo "== $(date +%T) backend build rc $rc; errors $(grep -c 'error:' "$R/backend-build.out"), warnings $(grep -c 'warning:' "$R/backend-build.out")"
grep -n "error:" "$R/backend-build.out" | head -10
[ $rc = 0 ] && [ -x "$BB/bc5_backend_tests" ] || { echo "backend tests did not build: see $R/backend-build.out"; exit 1; }
distrobox enter ubuntu -- sh -c "cd '$BB' && nice -n 19 ./bc5_backend_tests" > "$R/backend-tests.out" 2>&1
trc=$?; tail -3 "$R/backend-tests.out"; echo "== tests rc $trc"
distrobox enter ubuntu -- sh -c "cd '$BB' && ./bc5_backend_tests '[pad_audio_route]'" > "$R/backend-tests-pad_audio_route.out" 2>&1; tail -3 "$R/backend-tests-pad_audio_route.out"
[ $trc = 0 ] || { echo "backend tests FAILED (rc $trc): see $R/backend-tests.out; no emulator linked"; exit 2; }
# 2. The private tree: the experiment's audio.cpp and the header (every other include comes from the shared tree).
rm -rf "$SRC" "$E/obj"; mkdir -p "$SRC/src/libs" "$SRC/src/bc5"
cp "$IN/src/libs/audio.cpp" "$SRC/src/libs/audio.cpp" || exit 1
cp "$IN/src/bc5/pad_audio_route.hpp" "$SRC/src/bc5/pad_audio_route.hpp" || exit 1
diff -u "$TREE/src/libs/audio.cpp" "$SRC/src/libs/audio.cpp" > "$R/audio.cpp-0372.diff"
echo "audio.cpp: $(grep -c '^[-+][^-+]' "$R/audio.cpp-0372.diff") lines changed, $(grep -c 'experiment 0372\|exp 0372' "$SRC/src/libs/audio.cpp") marks"
echo "== $(date +%T) compdb"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
BIN=$E/kyty_emulator
if [ -f "$BIN" ]; then OLD=$BIN.$(m "$BIN"); [ -e "$OLD" ] || mv "$BIN" "$OLD"; echo "previous binary kept as $OLD"; fi
echo "== $(date +%T) compile + relink"
distrobox enter ubuntu -- python3 -I "$HERE/build0372.py" "$E/compdb.json" "$SRC" "$E" "$B" "$BIN" > "$R/build.out" 2>&1
rc=$?; echo "== $(date +%T) rc $rc; errors $(grep -c 'error:' "$R/build.out"), warnings $(grep -c 'warning:' "$R/build.out")"
grep -n "error:\|undefined\|COMPILE FAILED" "$R/build.out" | head -20
[ $rc = 0 ] && [ -x "$BIN" ] || { echo "build failed: see $R/build.out"; exit 1; }
m "$BIN" > "$E/binary.md5"; echo "md5 $(cat "$E/binary.md5") (shared $EXPECT_NORMAL)"
[ "$(cat "$E/binary.md5")" != "$EXPECT_NORMAL" ] || { echo "the binary equals the shared one"; exit 1; }
echo "strings: exp 0372 lines $(strings "$BIN" | grep -c 'AudioOut (exp 0372)'), pad route $(strings "$BIN" | grep -c '^pad route: t'), PIPEWIRE_PROPS pad keys $(strings "$BIN" | grep -c 'node.dont-reconnect = true node.dont-fallback = true')"
echo "$(date '+%F %T') $(cat "$E/binary.md5") kyty_emulator: the shared objects ($EXPECT_NORMAL) with audio.cpp of exp 0372 ($EXPECT_AUDIO) + the shared archive $EXPECT_ARCHIVE; Catch2 rc $trc; rc $rc" >> "$R/binaries.txt"
echo "shared binary after: $(m "$B/src/kyty_emulator") (want $EXPECT_NORMAL); shared archive after: $(m "$ARCH") (want $EXPECT_ARCHIVE); tree audio.cpp after: $(m "$TREE/src/libs/audio.cpp") (want $EXPECT_TREE_AUDIO)"
