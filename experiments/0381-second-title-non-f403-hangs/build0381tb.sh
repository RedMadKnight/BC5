#!/usr/bin/env bash
# BC5 exp 0381: the test build (the maintainer's "Yes, test build"): ~/bc5-work/exp0381/tb/bin/kyty_emulator =
#   the binary he plays now, exp 0380's r1 (44417414: shared objects 58c4a627, archive bb50b2e0, unit c46144c4 = exp 0379's
#   unit + recorder, runtimeLinker.cpp 5f2bc982 with crash frames)
#   + this experiment's restore on that unit (mkpatch0381.py; unit c743bb76), with the current acb_restore.hpp.
# Then the private launcher copy tb/play-pkg-0381tb.sh (r1's launcher, with its paths moved and the switch set) and the
# smoke variant tb/play-pkg-0381tbs.sh (the same, on private saves, config and learned file; it only differs there).
# Only private files are written. The shared builds, the archive, play-pkg.sh, patch 0001 and the shortcuts are only read.
# CPU only, nice 19, no emulator. Layout: `git archive HEAD backend experiments/0381-second-title-non-f403-hangs` in
# ~/bc5-work/exp0381/in/. usage: bash ~/bc5-work/exp0381/in/experiments/0381-second-title-non-f403-hangs/build0381tb.sh
set -u
W=$HOME/bc5-work; E=$W/exp0381; TB=$E/tb; R=$TB/raw; LOCK=$W/BOX-LOCK; B=$W/kytyplus-build; TREE=$HOME/src/KytyPlus
ARCH=$W/backend-ubuntu/libbc5_backend.a; R1=$W/exp0380r1; HERE=$(cd "$(dirname "$0")" && pwd); IN=$E/in; BB=$E/backend-build
EXPECT_UNIT=c743bb76
m() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
grep -q "MAINTAINER PLAYING" "$LOCK" && { echo "the maintainer plays: stop"; exit 1; }
[ -s "$LOCK" ] && ! grep -q "^top exp 0381 |" "$LOCK" && { echo "box locked: $(cat "$LOCK")"; exit 1; }
pins() { echo "shared normal $(m "$B/src/kyty_emulator") lean $(m "$W/kytyplus-build-lean/src/kyty_emulator") archive $(m "$ARCH") tree unit $(m "$TREE/src/libs/bc5LleAgc.cpp") play-pkg.sh $(m "$W/play-pkg.sh")"; }
P0=$(pins); echo "before: $P0"
[ "$P0" = "shared normal 58c4a627 lean dcbeb440 archive bb50b2e0 tree unit e7cc2f60 play-pkg.sh 55531ab6" ] || { echo "a shared pin differs: stop"; exit 1; }
[ "$(m "$R1/bin/kyty_emulator")" = 44417414 ] || { echo "r1's binary is not 44417414: stop"; exit 1; }
[ "$(m "$R1/src/libs/bc5LleAgc.cpp")" = c46144c4 ] && [ "$(m "$R1/src/loader/runtimeLinker.cpp")" = 5f2bc982 ] && [ "$(m "$R1/src/libs/bc5/zero_skip.hpp")" = 782ca0e9 ] || { echo "r1's sources are not c46144c4 / 5f2bc982 / 782ca0e9: stop"; exit 1; }
[ "$(m "$R1/play-pkg-0380r1.sh")" = 299a2519 ] || { echo "r1's launcher is not 299a2519: stop"; exit 1; }
[ -f "$R1/build0380y.py" ] || { echo "no build0380y.py in $R1: stop"; exit 1; }
[ -e "$TB/bin/kyty_emulator" ] && { echo "$TB/bin/kyty_emulator exists: stop"; exit 1; }
echo "top exp 0381 | build of the test binary exp0381/tb (Catch2, then the r1 unit + the restore, relinked; CPU only, nice 19) | start $(date +%H:%M)" > "$LOCK"
trap 'grep -q "^top exp 0381 | build" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
mkdir -p "$R" "$TB/src/libs/bc5" "$TB/src/loader" "$TB/bin" "$TB/obj" "$TB/play"
# 1. The backend's Catch2 tests, with the current final_value.
CATCH=$(ls -d "$HOME"/bc5-work/exp03*/backend-build/_deps/catch2-src 2> /dev/null | grep -v exp0381 | head -1)
CATCH_ARG=""; [ -n "$CATCH" ] && CATCH_ARG="-DFETCHCONTENT_SOURCE_DIR_CATCH2=$CATCH"
echo "== $(date +%T) backend tests"
distrobox enter ubuntu -- sh -c "cd '$E' && nice -n 19 cmake -S '$IN/backend' -B '$BB' -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=ON $CATCH_ARG && nice -n 19 cmake --build '$BB' --target bc5_backend_tests -j8" < /dev/null > "$R/backend-build.out" 2>&1
rc=$?; echo "backend build rc $rc, warnings $(grep -c 'warning:' "$R/backend-build.out")"
[ $rc = 0 ] || { grep -n "error:" "$R/backend-build.out" | head; exit 1; }
distrobox enter ubuntu -- sh -c "cd '$BB' && nice -n 19 ./bc5_backend_tests" < /dev/null > "$R/backend-tests.out" 2>&1
trc=$?; tail -2 "$R/backend-tests.out"; [ $trc = 0 ] || { echo "tests FAILED: no emulator linked"; exit 2; }
# 2. The private sources.
cp "$R1/src/libs/bc5/zero_skip.hpp" "$IN/backend/include/bc5/acb_restore.hpp" "$TB/src/libs/bc5/" || exit 1
cp "$R1/src/loader/runtimeLinker.cpp" "$TB/src/loader/runtimeLinker.cpp" || exit 1
python3 -I "$HERE/mkpatch0381.py" "$R1/src/libs/bc5LleAgc.cpp" "$TB/src/libs/bc5LleAgc.cpp" || { echo "the restore's edits did not apply: stop"; exit 1; }
[ "$(m "$TB/src/libs/bc5LleAgc.cpp")" = "$EXPECT_UNIT" ] || { echo "the unit is $(m "$TB/src/libs/bc5LleAgc.cpp"), not $EXPECT_UNIT: stop"; exit 1; }
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" < /dev/null > "$TB/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
BIN=$TB/bin/kyty_emulator
echo "== $(date +%T) compile + relink"
distrobox enter ubuntu -- python3 -I "$R1/build0380y.py" "$TB/compdb.json" "$B" "$TB/obj" "$BIN" "libs/bc5LleAgc.cpp.o=$TB/src/libs/bc5LleAgc.cpp=$TREE/src/libs" "loader/runtimeLinker.cpp.o=$TB/src/loader/runtimeLinker.cpp=$TREE/src/loader" < /dev/null > "$R/build.out" 2>&1
rc=$?; echo "rc $rc; errors $(grep -c 'error:' "$R/build.out"), warnings $(grep -c 'warning:' "$R/build.out")"
grep -n "error:\|undefined\|COMPILE FAILED" "$R/build.out" | head -20
[ $rc = 0 ] && [ -x "$BIN" ] || { echo "build failed"; exit 1; }
echo "binary $(md5sum < "$BIN"); switch $(strings "$BIN" | grep -c '^BC5_DIRECT_ACB_STATE_RESTORE$'), zero skip $(strings "$BIN" | grep -c '^zero skip: '), rec0380 $(strings "$BIN" | grep -c 'rec0380: '), crash frames $(strings "$BIN" | grep -c 'BC5_CRASH_FRAMES')"
# 3. The launchers.
L=$TB/play-pkg-0381tb.sh; S=$TB/play-pkg-0381tbs.sh
sed -e 's#exp0380r1#exp0381/tb#g' -e 's#exp 0380r1#exp 0381 test build#g' "$R1/play-pkg-0380r1.sh" > "$L" || exit 1
[ "$(grep -c '^export BC5_CRASH_FRAMES=1 ' "$L")" = 1 ] || { echo "the switch line is not there once: stop"; exit 1; }
sed -i 's/^export BC5_CRASH_FRAMES=1 /export BC5_DIRECT_ACB_STATE_RESTORE=1 BC5_CRASH_FRAMES=1 /' "$L"
cp "$R1/zero-list-20261029-120000.txt" "$R1/play-sample0379t.sh" "$TB/" || exit 1
bash -n "$L" || { echo "the launcher does not parse"; exit 1; }
chmod +x "$L"
diff "$R1/play-pkg-0380r1.sh" "$L" > "$R/launcher-vs-r1.diff"
echo "launcher $L $(m "$L"), $(grep -c '^>' "$R/launcher-vs-r1.diff") lines changed against r1; still names r1: $(grep -c 'exp0380r1' "$L")"
chk() { [ "$(grep -cxF -- "$1" "$L")" = 1 ] || { echo "anchor [$1] is not there once: stop"; exit 1; }; }
chk 'cd ~/bc5-work'; chk 'done < "$ENVF"'; chk 'export BC5_DIRECT_LEARNED=$HOME/bc5-work/direct-learned-pkg.txt'; chk 'export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play'
sed -e 's#^cd ~/bc5-work$#cd ~/bc5-work/exp0381/wd#' \
    -e 's#^export BC5_DIRECT_LEARNED=.*$#export BC5_DIRECT_LEARNED=$HOME/bc5-work/exp0381/direct-learned-pkg.txt#' \
    -e 's#^export KYTY_BC5_SAVEDATA_DIR=.*$#export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/exp0381/wd/_SaveData-pkg-play#' \
    -e '/^done < "\$ENVF"$/a export KYTY_BC5_INPUT_CONFIG=$HOME/bc5-work/exp0381/input-rton.cfg' "$L" > "$S" || exit 1
bash -n "$S" || { echo "the smoke launcher does not parse"; exit 1; }
chmod +x "$S"
diff "$L" "$S" > "$R/smoke-vs-launcher.diff"
echo "smoke launcher $(m "$S"), $(grep -c '^>' "$R/smoke-vs-launcher.diff") lines against the launcher"
P1=$(pins); echo "after: $P1"
[ "$P1" = "$P0" ] || { echo "A SHARED PIN CHANGED"; exit 1; }
