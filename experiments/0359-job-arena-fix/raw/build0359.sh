#!/usr/bin/env bash
# BC5 experiment 0359 (exp 0349's and 0358's patterns): one private emulator, ~/bc5-work/exp0359/kyty_emulator, with the
# job-arena fix (a TEMPORARY game-code workaround, backend/include/bc5/job_arena_fix.hpp) — the shared host tree's
# src/loader/gamePatch.cpp, src/loader/runtimeLinker.cpp, src/graphics/presentation/window/hostInput.cpp and
# src/graphics/presentation/hostMenu.cpp copied into a PRIVATE source tree with their sibling headers and the backend
# header, patch0359.pl applied there, the four units compiled with the shared normal build's compdb commands into
# private objects, the shared link command run with those objects (the shared backend archive as it is: the header is
# header-only). Before that, this experiment's backend/ (beside the script) is configured and built privately and its
# Catch2 tests run; the emulator is linked only when they pass. ~/src/KytyPlus, the shared builds and the archive are
# only read; a previous private binary is kept beside the new one as kyty_emulator.<md5>.
# usage: build0359.sh   (on the box, with patch0359.pl, build0359.py and backend/ beside it; CPU only, nice 19, ~5 min)
set -u
E=$HOME/bc5-work/exp0359; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
B=$HOME/bc5-work/kytyplus-build; ARCH=$HOME/bc5-work/backend-ubuntu/libbc5_backend.a
EXPECT_ARCHIVE=${EXPECT_ARCHIVE:-bb50b2e0}; EXPECT_NORMAL=${EXPECT_NORMAL:-affa0c22}
EXPECT_GP=${EXPECT_GP:-8c1cd621}; EXPECT_RTL=${EXPECT_RTL:-e37ed5cd}; EXPECT_HI=${EXPECT_HI:-a8317e02}; EXPECT_HM=${EXPECT_HM:-cb35096f}
HERE=$(cd "$(dirname "$0")" && pwd)
TREE=$HOME/src/KytyPlus; SRC=$E/src; BSRC=$HERE/backend; BB=$E/backend-build
UNITS="src/loader/gamePatch.cpp src/loader/runtimeLinker.cpp src/graphics/presentation/window/hostInput.cpp src/graphics/presentation/hostMenu.cpp"
mkdir -p "$R"
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
grep -q "MAINTAINER PLAYING" "$LOCK" && { echo "the maintainer plays: stop"; exit 1; }
[ -s "$LOCK" ] && ! grep -q "^bvh exp 0359 |" "$LOCK" && { echo "box locked: $(cat "$LOCK")"; exit 1; }
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$B/src/kyty_emulator")" = "$EXPECT_NORMAL" ] || { echo "the shared normal binary is $(m "$B/src/kyty_emulator"), not $EXPECT_NORMAL: stop"; exit 1; }
[ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] || { echo "the shared archive is $(m "$ARCH"), not $EXPECT_ARCHIVE: stop"; exit 1; }
[ "$(m "$TREE/src/loader/gamePatch.cpp")" = "$EXPECT_GP" ] || { echo "gamePatch.cpp is $(m "$TREE/src/loader/gamePatch.cpp"), not $EXPECT_GP: stop"; exit 1; }
[ "$(m "$TREE/src/loader/runtimeLinker.cpp")" = "$EXPECT_RTL" ] || { echo "runtimeLinker.cpp is $(m "$TREE/src/loader/runtimeLinker.cpp"), not $EXPECT_RTL: stop"; exit 1; }
[ "$(m "$TREE/src/graphics/presentation/window/hostInput.cpp")" = "$EXPECT_HI" ] || { echo "hostInput.cpp is $(m "$TREE/src/graphics/presentation/window/hostInput.cpp"), not $EXPECT_HI: stop"; exit 1; }
[ "$(m "$TREE/src/graphics/presentation/hostMenu.cpp")" = "$EXPECT_HM" ] || { echo "hostMenu.cpp is $(m "$TREE/src/graphics/presentation/hostMenu.cpp"), not $EXPECT_HM: stop"; exit 1; }
for f in patch0359.pl build0359.py; do [ -f "$HERE/$f" ] || { echo "no $f beside this script"; exit 1; }; done
[ -f "$BSRC/CMakeLists.txt" ] && [ -f "$BSRC/include/bc5/job_arena_fix.hpp" ] && [ -f "$BSRC/tests/job_arena_fix_test.cpp" ] || { echo "no backend/ with the job-arena fix beside this script"; exit 1; }
echo "bvh exp 0359 | build of ~/bc5-work/exp0359/kyty_emulator (the backend's Catch2 tests, then four host units patched in a private copy, compiled, relinked; CPU only, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +12min +%H:%M)" > "$LOCK"
trap 'grep -q "^bvh exp 0359 | build" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
{ echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(m "$B/src/kyty_emulator"); shared archive $(m "$ARCH"); units gamePatch $(m "$TREE/src/loader/gamePatch.cpp") runtimeLinker $(m "$TREE/src/loader/runtimeLinker.cpp") hostInput $(m "$TREE/src/graphics/presentation/window/hostInput.cpp") hostMenu $(m "$TREE/src/graphics/presentation/hostMenu.cpp"); patch0359.pl $(m "$HERE/patch0359.pl"); backend header $(m "$BSRC/include/bc5/job_arena_fix.hpp") test $(m "$BSRC/tests/job_arena_fix_test.cpp")"; } > "$R/build-inputs.txt"; cat "$R/build-inputs.txt"
# 1. The backend's Catch2 tests (the archive itself is not used: the fix's header is header-only).
CATCH=$(ls -d "$HOME"/bc5-work/exp03*/backend-tests/_deps/catch2-src "$HOME"/bc5-work/exp03*/backend-build/_deps/catch2-src 2> /dev/null | head -1)
CATCH_ARG=""; [ -n "$CATCH" ] && CATCH_ARG="-DFETCHCONTENT_SOURCE_DIR_CATCH2=$CATCH" && echo "Catch2 from $CATCH"
echo "== $(date +%T) backend configure + build (tests)"
distrobox enter ubuntu -- sh -c "cd '$E' && nice -n 19 cmake -S '$BSRC' -B '$BB' -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=ON $CATCH_ARG && nice -n 19 cmake --build '$BB' --target bc5_backend_tests -j8" > "$R/backend-build.out" 2>&1
rc=$?; echo "== $(date +%T) backend build rc $rc; errors $(grep -c 'error:' "$R/backend-build.out"), warnings $(grep -c 'warning:' "$R/backend-build.out")"
grep -n "error:" "$R/backend-build.out" | head -10
[ $rc = 0 ] && [ -x "$BB/bc5_backend_tests" ] || { echo "backend tests did not build: see $R/backend-build.out"; exit 1; }
distrobox enter ubuntu -- sh -c "cd '$BB' && nice -n 19 ./bc5_backend_tests" > "$R/backend-tests.out" 2>&1
trc=$?; tail -3 "$R/backend-tests.out"; echo "== tests rc $trc"
distrobox enter ubuntu -- sh -c "cd '$BB' && ./bc5_backend_tests '[job_arena_fix]'" > "$R/backend-tests-job_arena_fix.out" 2>&1; tail -3 "$R/backend-tests-job_arena_fix.out"
[ $trc = 0 ] || { echo "backend tests FAILED (rc $trc): see $R/backend-tests.out; no emulator linked"; exit 2; }
# 2. The private host units.
rm -rf "$SRC" "$E/obj"; mkdir -p "$SRC/src/loader" "$SRC/src/graphics/presentation/window" "$SRC/src/bc5"
for u in $UNITS; do cp "$TREE/$u" "$SRC/$u" || exit 1; done
for d in loader graphics/presentation graphics/presentation/window; do for f in "$TREE"/src/$d/*.inc "$TREE"/src/$d/*.h; do [ -e "$f" ] && cp "$f" "$SRC/src/$d/"; done; done  # the units' sibling includes
cp "$BSRC/include/bc5/job_arena_fix.hpp" "$SRC/src/bc5/" || exit 1
perl "$HERE/patch0359.pl" "$SRC" > "$R/patch.out" 2>&1 || { echo "patch0359.pl failed:"; cat "$R/patch.out"; exit 1; }
cat "$R/patch.out"
for u in $UNITS src/loader/gamePatch.h src/graphics/presentation/window/hostInput.h; do diff -u "$TREE/$u" "$SRC/$u" > "$R/$(basename "$u")-0359.diff"; echo "$u: $(grep -c '^[-+][^-+]' "$R/$(basename "$u")-0359.diff") lines changed, $(grep -c 'experiment 0359' "$SRC/$u") marks"; done
grep -h 'job-arena fix APPLIED\|job-arena hook call' "$SRC/src/loader/gamePatch.cpp" | cat -A | grep -c '\\n"' | { read n; echo "C newline escapes intact in $n of 2 new format lines"; }
echo "== $(date +%T) compdb"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
BIN=$E/kyty_emulator
if [ -f "$BIN" ]; then OLD=$BIN.$(m "$BIN"); [ -e "$OLD" ] || mv "$BIN" "$OLD"; echo "previous binary kept as $OLD"; fi
echo "== $(date +%T) compile + relink"
distrobox enter ubuntu -- python3 -I "$HERE/build0359.py" "$E/compdb.json" "$SRC" "$E" "$B" "$BIN" > "$R/build.out" 2>&1
rc=$?; echo "== $(date +%T) rc $rc; errors $(grep -c 'error:' "$R/build.out"), warnings $(grep -c 'warning:' "$R/build.out")"
grep -n "error:\|undefined\|COMPILE FAILED" "$R/build.out" | head -20
[ $rc = 0 ] && [ -x "$BIN" ] || { echo "build failed: see $R/build.out"; exit 1; }
m "$BIN" > "$E/binary.md5"; echo "md5 $(cat "$E/binary.md5") (shared $EXPECT_NORMAL)"
[ "$(cat "$E/binary.md5")" != "$EXPECT_NORMAL" ] || { echo "the binary equals the shared one"; exit 1; }
echo "strings: game fix lines $(strings "$BIN" | grep -c 'game fix'), JobArenaFix $(strings "$BIN" | grep -c 'JobArenaFix'), menu item $(strings "$BIN" | grep -c 'Job-arena fix'), 0349 switch $(strings "$BIN" | grep -c 'experiment 0349: a job')"
echo "$(date '+%F %T') $(cat "$E/binary.md5") kyty_emulator: the shared objects ($EXPECT_NORMAL) with gamePatch/runtimeLinker/hostInput/hostMenu of patch0359.pl + the shared archive $EXPECT_ARCHIVE; Catch2 rc $trc; rc $rc" >> "$R/binaries.txt"
echo "shared binary after: $(m "$B/src/kyty_emulator") (want $EXPECT_NORMAL); shared archive after: $(m "$ARCH") (want $EXPECT_ARCHIVE); tree units after: $(m "$TREE/src/loader/gamePatch.cpp") $(m "$TREE/src/loader/runtimeLinker.cpp") $(m "$TREE/src/graphics/presentation/window/hostInput.cpp") $(m "$TREE/src/graphics/presentation/hostMenu.cpp")"
