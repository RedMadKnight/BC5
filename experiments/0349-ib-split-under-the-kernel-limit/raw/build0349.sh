#!/usr/bin/env bash
# BC5 experiment 0349 (exp 0346's build0346.sh + exp 0343's host unit): one private emulator, ~/bc5-work/exp0349/kyty_emulator —
# this experiment's backend (bc5/ib_split: a job's IB over the kernel's 0xfffff-dword limit cut into up to four IBs of one
# submit; exp 0348's carried register committed only after a successful submit) built as a private archive from the copy of
# backend/ beside this script, its unit tests (Catch2) built and run, then exp 0343's build0343.py: the shared normal build's
# compile command run on exp 0343's patched copy of src/libs/bc5LleAgc.cpp (the soft-CP replay polls bounded and journaled)
# and the shared link command run with that object and this archive in place of the shared ones. ~/src/KytyPlus, the shared
# builds, the shared archive and ~/bc5-work/exp0343 are only read. Catch2 comes from an earlier test build's FetchContent
# cache when one exists. usage: build0349.sh   (on the box, with backend/ beside it; CPU only, nice 19, ~5 min; no emulator)
set -u
E=$HOME/bc5-work/exp0349; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
B=$HOME/bc5-work/kytyplus-build; ARCH=$HOME/bc5-work/backend-ubuntu/libbc5_backend.a
E43=$HOME/bc5-work/exp0343; UNIT=src/libs/bc5LleAgc.cpp
EXPECT_ARCHIVE=${EXPECT_ARCHIVE:-44ba4435}; EXPECT_NORMAL=${EXPECT_NORMAL:-ddfb9456}; EXPECT_0343_UNIT=${EXPECT_0343_UNIT:-e7cc2f60}; EXPECT_0343_PY=${EXPECT_0343_PY:-}
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$HERE/backend; BB=$E/backend-build
mkdir -p "$R"
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
grep -q "^bvh exp 0349 |" "$LOCK" || { echo "the lock is not this experiment's: $(cat "$LOCK")"; exit 1; }
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$B/src/kyty_emulator")" = "$EXPECT_NORMAL" ] || { echo "the shared normal binary is $(m "$B/src/kyty_emulator"), not $EXPECT_NORMAL: stop"; exit 1; }
[ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] || { echo "the shared archive is $(m "$ARCH"), not $EXPECT_ARCHIVE: stop"; exit 1; }
[ "$(m "$E43/src/$UNIT")" = "$EXPECT_0343_UNIT" ] || { echo "exp 0343's patched unit is $(m "$E43/src/$UNIT"), not $EXPECT_0343_UNIT: stop"; exit 1; }
[ -f "$E43/build0343.py" ] || { echo "no $E43/build0343.py"; exit 1; }
[ -f "$SRC/CMakeLists.txt" ] && [ -f "$SRC/src/ib_split.cpp" ] || { echo "no backend/ with ib_split.cpp beside this script"; exit 1; }
{ echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(m "$B/src/kyty_emulator"); archive $(m "$ARCH"); 0343 unit $(m "$E43/src/$UNIT"); build0343.py $(m "$E43/build0343.py")"
  for f in src/direct.cpp src/ib_split.cpp include/bc5/ib_split.hpp tests/ib_split_test.cpp src/host_indirect.cpp include/bc5/host_indirect.hpp src/indirect_check.cpp src/shadow_labels.cpp src/policy.cpp include/bc5/direct.hpp CMakeLists.txt; do echo "  backend/$f $(m "$SRC/$f")"; done; } > "$R/build-inputs.txt"
cat "$R/build-inputs.txt"
CATCH=$(ls -d "$HOME"/bc5-work/exp03*/backend-tests/_deps/catch2-src 2> /dev/null | head -1)
CATCH_ARG=""; [ -n "$CATCH" ] && CATCH_ARG="-DFETCHCONTENT_SOURCE_DIR_CATCH2=$CATCH" && echo "Catch2 from $CATCH"
echo "== $(date +%T) backend configure + build"
distrobox enter ubuntu -- sh -c "cd '$E' && nice -n 19 cmake -S '$SRC' -B '$BB' -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=ON $CATCH_ARG && nice -n 19 cmake --build '$BB' --target bc5_backend bc5_backend_tests -j8" > "$R/backend-build.out" 2>&1
rc=$?; echo "== $(date +%T) backend build rc $rc; errors $(grep -c 'error:' "$R/backend-build.out"), warnings $(grep -c 'warning:' "$R/backend-build.out")"
grep -n "error:" "$R/backend-build.out" | head -20
[ $rc = 0 ] && [ -f "$BB/libbc5_backend.a" ] || { echo "backend build failed: see $R/backend-build.out"; exit 1; }
echo "private archive $(m "$BB/libbc5_backend.a") (shared $(m "$ARCH"))"
echo "== $(date +%T) backend tests"
distrobox enter ubuntu -- sh -c "cd '$BB' && nice -n 19 ./bc5_backend_tests" > "$R/backend-tests.out" 2>&1
trc=$?; tail -4 "$R/backend-tests.out"; echo "== tests rc $trc"
distrobox enter ubuntu -- sh -c "cd '$BB' && ./bc5_backend_tests '[ib_split]'" > "$R/backend-tests-ib_split.out" 2>&1; tail -3 "$R/backend-tests-ib_split.out"
[ $trc = 0 ] || { echo "backend tests FAILED (rc $trc): see $R/backend-tests.out; no emulator linked"; exit 2; }
echo "== $(date +%T) compdb + compile exp 0343's unit + relink"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
BIN=$E/kyty_emulator
if [ -f "$BIN" ]; then OLD=$BIN.$(m "$BIN"); [ -e "$OLD" ] || mv "$BIN" "$OLD"; echo "previous binary kept as $OLD"; fi
distrobox enter ubuntu -- python3 -I "$E43/build0343.py" "$E/compdb.json" "$E43/src" "$E" "$B" "$ARCH" "$BB/libbc5_backend.a" "$BIN" > "$R/build.out" 2>&1
lrc=$?; echo "== $(date +%T) rc $lrc; errors $(grep -c 'error:' "$R/build.out"), warnings $(grep -c 'warning:' "$R/build.out")"
grep -n "error:\|undefined\|COMPILE FAILED" "$R/build.out" | head -20
[ $lrc = 0 ] && [ -x "$BIN" ] || { echo "build failed: see $R/build.out"; exit 1; }
m "$BIN" > "$E/binary.md5"; echo "md5 $(cat "$E/binary.md5") (shared $EXPECT_NORMAL, 0343+0346 ecbb95ce)"
[ "$(cat "$E/binary.md5")" != "$EXPECT_NORMAL" ] || { echo "the binary equals the shared one"; exit 1; }
echo "strings: 0349 switch line $(strings "$BIN" | grep -c 'experiment 0349: a job'), 0349 split line $(strings "$BIN" | grep -c 'experiment 0349 split'), cs refused line $(strings "$BIN" | grep -c 'cs refused rc'), 0346 switch line $(strings "$BIN" | grep -c 'experiment 0346 switch'), soft-cp wait line $(strings "$BIN" | grep -c 'soft-cp wait: t')"
echo "$(date '+%F %T') $(cat "$E/binary.md5") kyty_emulator: the shared objects ($EXPECT_NORMAL) with exp 0343's bc5LleAgc.cpp.o + this experiment's archive $(m "$BB/libbc5_backend.a") (0349 IB split + 0348 carried register + 0346 v3); tests rc $trc" >> "$R/binaries.txt"
echo "shared binary after: $(m "$B/src/kyty_emulator") (want $EXPECT_NORMAL); shared archive after: $(m "$ARCH") (want $EXPECT_ARCHIVE); 0343 unit after: $(m "$E43/src/$UNIT") (want $EXPECT_0343_UNIT)"
