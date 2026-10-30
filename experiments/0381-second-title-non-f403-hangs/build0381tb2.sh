#!/usr/bin/env bash
# BC5 exp 0381: test build 2 ("wszystkie zmiany na raz"): ~/bc5-work/exp0381/tb2/bin/kyty_emulator =
#   test build 1's parts (the shared objects and archive, the r1 unit with the restore, runtimeLinker.cpp with crash frames)
#   + acb_restore.hpp at main d6fa368 (the final_value fix)
#   + libC.cpp and libNpCppWebApi.cpp of exp 0383's patch (PORT-NP, PORT-LIBC), rebuilt from KytyPlus f266548 + that patch and
#     proved by its src tree. F761's shadow prototype is not in it: it is not runtime code.
# That is the fallback, pins0381tb2.env. With pins0381tb2r.env (PIN_MODE=rebased) the shared builds already carry main's backend
# and the NP and libc fixes, so only bc5LleAgc.cpp and runtimeLinker.cpp are private, as in test build 1.
# Then the private launcher tb2/play-pkg-0381tb2.sh and the smoke variant tb2/play-pkg-0381tb2s.sh.
# Only private files are written. The shared builds, the archive, play-pkg.sh, patch 0001 and the shortcuts are only read.
# CPU only, nice 19, no emulator. It holds the queue record: the outcome line comes from the EXIT trap, only after the lock
# line was seen to be this build's, and it says done only when every step passed.
# usage (tb2run0381.sh does this): bash ~/bc5-work/exp0381/in-tb2/experiments/0381-second-title-non-f403-hangs/build0381tb2.sh
set -u
export LC_ALL=C
HERE=$(cd "$(dirname "$0")" && pwd)
. "${TB2_PINS:-$HERE/pins0381tb2.env}"
MODE=${PIN_MODE:-fallback}
W=$HOME/bc5-work; E=$W/exp0381; IN=$E/in-tb2; TB=$E/tb2; R=$TB/raw; LOCK=$W/BOX-LOCK; B=$W/kytyplus-build; K=$HOME/src/KytyPlus
ARCH=$W/backend-ubuntu/libbc5_backend.a; R1=$W/exp0380r1; BB=$E/backend-build-tb2; T=$TB/tree
TAG='top exp 0381 | test build 2'
m() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "GUARD: an emulator runs"; exit 3; }
grep -q "^$TAG" "$LOCK" 2> /dev/null || { echo "GUARD: the lock is not this build's: $(cat "$LOCK" 2> /dev/null)"; exit 4; }
ok=0
finish() {
    if [ "$ok" = 1 ]; then echo "$TAG build done: all steps passed, no GPU | $(date '+%F %T')" >> "$W/BOX-QUEUE"
    else
        echo "$TAG build FAILED, see ~/bc5-work/exp0381/tb2; no GPU; lock cleared | $(date '+%F %T')" >> "$W/BOX-QUEUE"
        grep -q "^$TAG" "$LOCK" 2> /dev/null && : > "$LOCK"
    fi
}
trap finish EXIT
fail() { echo "FAIL: $1"; exit 1; }
grep -q '=FILL$' "${TB2_PINS:-$HERE/pins0381tb2.env}" && fail "these pins are not filled in"
box() { distrobox enter ubuntu -- sh -c "$1" < /dev/null; }
pins() { echo "shared normal $(m "$B/src/kyty_emulator") lean $(m "$W/kytyplus-build-lean/src/kyty_emulator") archive $(m "$ARCH") tree unit $(m "$K/src/libs/bc5LleAgc.cpp") play-pkg.sh $(m "$W/play-pkg.sh")"; }
P0=$(pins); echo "before: $P0"
[ "$P0" = "shared normal $PIN_SHARED lean $PIN_LEAN archive $PIN_ARCHIVE tree unit $PIN_TREE_UNIT play-pkg.sh $PIN_PLAY_PKG" ] || fail "a shared pin differs"
[ "$(m "$R1/bin/kyty_emulator")" = "$PIN_R1_BIN" ] || fail "r1's binary"
[ "$(m "$R1/src/libs/bc5LleAgc.cpp")" = "$PIN_R1_UNIT" ] && [ "$(m "$R1/src/loader/runtimeLinker.cpp")" = "$PIN_R1_LINKER" ] && [ "$(m "$R1/src/libs/bc5/zero_skip.hpp")" = "$PIN_R1_ZERO" ] || fail "r1's sources"
[ "$(m "$R1/play-pkg-0380r1.sh")" = "$PIN_R1_LAUNCHER" ] || fail "r1's launcher"
[ "$(m "$IN/backend/include/bc5/acb_restore.hpp")" = "$PIN_HEADER" ] || fail "the header is not main's"
[ "$(md5sum < "$IN/patch0001-np.patch" | cut -d' ' -f1)" = "$PIN_PATCH" ] || fail "the patch is not the pinned one"
[ -f "$R1/build0380y.py" ] || fail "no build0380y.py in $R1"
[ -e "$TB/bin/kyty_emulator" ] && fail "$TB/bin/kyty_emulator exists"
mkdir -p "$R" "$TB/src/libs/bc5" "$TB/src/loader" "$TB/bin" "$TB/obj" "$TB/play"
# 1. The backend's Catch2 tests at main, with the final_value fix.
CATCH=$(ls -d "$W"/exp03*/backend-build/_deps/catch2-src 2> /dev/null | head -1)
echo "== $(date +%T) backend tests"
box "cd '$E' && nice -n 19 cmake -S '$IN/backend' -B '$BB' -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=ON -DFETCHCONTENT_SOURCE_DIR_CATCH2='$CATCH' && nice -n 19 cmake --build '$BB' --target bc5_backend_tests -j8" > "$R/backend-build.out" 2>&1 || { grep -n "error:" "$R/backend-build.out" | head; fail "backend build"; }
box "cd '$BB' && nice -n 19 ./bc5_backend_tests" > "$R/backend-tests.out" 2>&1 || fail "backend tests"
grep -q 'All tests passed' "$R/backend-tests.out" || fail "no pass line from the tests"
tail -2 "$R/backend-tests.out" | head -1
if [ "$MODE" = rebased ]; then
    # 2. The shared tree already is the patched tree: prove it, and take the two fixes from the shared objects.
    [ "$(m "$K/src/libs/libC.cpp")" = "$PIN_LIBC" ] && [ "$(m "$K/src/libs/libNpCppWebApi.cpp")" = "$PIN_NP" ] || fail "the shared tree does not hold the NP and libc fixes"
    n=$(grep -rl 'exp 0372' "$K/src" 2> /dev/null | xargs cat 2> /dev/null | grep -c 'exp 0372'); echo "exp 0372: $n lines, pad_audio_route.hpp $([ -f "$K/src/bc5/pad_audio_route.hpp" ] && echo present || echo MISSING)"
    [ "$n" = "$PIN_0372_LINES" ] && [ -f "$K/src/bc5/pad_audio_route.hpp" ] || fail "exp 0372's pieces"
else
# 2. The patched tree, as exp 0383: f266548 + the patch, proved by its src tree.
echo "== $(date +%T) tree"
rm -rf "$T"; mkdir -p "$T"
git -C "$K" -c core.autocrlf=false archive "$PIN_BASE_COMMIT" | tar -x -C "$T" || fail "archive"
git -C "$T" init -q; git -C "$T" config core.filemode false; git -C "$T" config core.autocrlf false; git -C "$T" config core.safecrlf false
git -C "$T" apply --whitespace=nowarn "$IN/patch0001-np.patch" || fail "the patch did not apply"
git -C "$T" add -A src 2> /dev/null
TREE=$(git -C "$T" write-tree --prefix=src/); echo "src tree $TREE"
[ "$TREE" = "$PIN_SRC_TREE" ] || fail "not the pinned src tree"
n=$(grep -rl 'exp 0372' "$T/src" 2> /dev/null | xargs cat 2> /dev/null | grep -c 'exp 0372'); echo "exp 0372: $n lines, pad_audio_route.hpp $([ -f "$T/src/bc5/pad_audio_route.hpp" ] && echo present || echo MISSING)"
[ "$n" = "$PIN_0372_LINES" ] && [ -f "$T/src/bc5/pad_audio_route.hpp" ] || fail "exp 0372's pieces"
diff -rq "$K/src" "$T/src" > "$R/tree-diff.txt" 2>&1
{ echo "Files $K/src/libs/libC.cpp and $T/src/libs/libC.cpp differ"; echo "Files $K/src/libs/libNpCppWebApi.cpp and $T/src/libs/libNpCppWebApi.cpp differ"; } > "$R/tree-diff-allowed.txt"
cmp -s "$R/tree-diff.txt" "$R/tree-diff-allowed.txt" || fail "the shared tree differs beyond the two approved files"
fi
# 3. The private sources: four units, or two on the rebased shared build.
cp "$R1/src/libs/bc5/zero_skip.hpp" "$IN/backend/include/bc5/acb_restore.hpp" "$TB/src/libs/bc5/" || fail copy
cp "$R1/src/loader/runtimeLinker.cpp" "$TB/src/loader/" || fail copy
[ "$MODE" = rebased ] || cp "$T/src/libs/libC.cpp" "$T/src/libs/libNpCppWebApi.cpp" "$TB/src/libs/" || fail copy
python3 -I "$HERE/mkpatch0381.py" "$R1/src/libs/bc5LleAgc.cpp" "$TB/src/libs/bc5LleAgc.cpp" || fail "the restore's edits did not apply"
[ "$(m "$TB/src/libs/bc5LleAgc.cpp")" = "$PIN_UNIT" ] || fail "the unit is $(m "$TB/src/libs/bc5LleAgc.cpp"), not $PIN_UNIT"
box "cd '$B' && ninja -t compdb -x" > "$TB/compdb.json" 2> "$R/compdb.err" || fail compdb
BIN=$TB/bin/kyty_emulator
echo "== $(date +%T) compile, link ($MODE)"
UNITS=("libs/bc5LleAgc.cpp.o=$TB/src/libs/bc5LleAgc.cpp=$K/src/libs" "loader/runtimeLinker.cpp.o=$TB/src/loader/runtimeLinker.cpp=$K/src/loader")
[ "$MODE" = rebased ] || UNITS+=("libs/libC.cpp.o=$TB/src/libs/libC.cpp=$T/src/libs" "libs/libNpCppWebApi.cpp.o=$TB/src/libs/libNpCppWebApi.cpp=$T/src/libs")
distrobox enter ubuntu -- python3 -I "$R1/build0380y.py" "$TB/compdb.json" "$B" "$TB/obj" "$BIN" "${UNITS[@]}" < /dev/null > "$R/build.out" 2>&1 || { grep -n "error:\|undefined\|COMPILE FAILED" "$R/build.out" | head -20; fail build; }
[ -x "$BIN" ] || fail "no binary"
# The shared flags colour the compiler's lines: strip the codes before counting (exp 0383's lesson).
sed 's/\x1b\[[0-9;]*m//g' "$R/build.out" > "$R/build-plain.out"
echo "errors $(grep -c 'error:' "$R/build-plain.out"), warnings $(grep -c 'warning:' "$R/build-plain.out")"
echo "binary $(md5sum < "$BIN" | cut -d' ' -f1); switch $(strings "$BIN" | grep -c '^BC5_DIRECT_ACB_STATE_RESTORE$'), zero skip $(strings "$BIN" | grep -c '^zero skip: '), rec0380 $(strings "$BIN" | grep -c 'rec0380: '), crash frames $(strings "$BIN" | grep -c 'BC5_CRASH_FRAMES')"
# 4. The launchers: r1's with its paths moved and the switch set; the smoke variant on private saves, config and learned file.
L=$TB/play-pkg-0381tb2.sh; S=$TB/play-pkg-0381tb2s.sh
sed -e 's#exp0380r1#exp0381/tb2#g' -e 's#exp 0380r1#exp 0381 test build 2#g' "$R1/play-pkg-0380r1.sh" > "$L" || fail launcher
[ "$(grep -c '^export BC5_CRASH_FRAMES=1 ' "$L")" = 1 ] || fail "the switch line is not there once"
sed -i 's/^export BC5_CRASH_FRAMES=1 /export BC5_DIRECT_ACB_STATE_RESTORE=1 BC5_CRASH_FRAMES=1 /' "$L"
cp "$R1/zero-list-20261029-120000.txt" "$R1/play-sample0379t.sh" "$TB/" || fail copy
bash -n "$L" || fail "the launcher does not parse"
chmod +x "$L"
diff "$R1/play-pkg-0380r1.sh" "$L" > "$R/launcher-vs-r1.diff"
echo "launcher $L $(m "$L"); still names r1: $(grep -c 'exp0380r1' "$L")"
for a in 'cd ~/bc5-work' 'done < "$ENVF"' 'export BC5_DIRECT_LEARNED=$HOME/bc5-work/direct-learned-pkg.txt' 'export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play'; do
    [ "$(grep -cxF -- "$a" "$L")" = 1 ] || fail "anchor [$a] is not there once"
done
sed -e 's#^cd ~/bc5-work$#cd ~/bc5-work/exp0381/wd#' \
    -e 's#^export BC5_DIRECT_LEARNED=.*$#export BC5_DIRECT_LEARNED=$HOME/bc5-work/exp0381/direct-learned-pkg.txt#' \
    -e 's#^export KYTY_BC5_SAVEDATA_DIR=.*$#export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/exp0381/wd/_SaveData-pkg-play#' \
    -e '/^done < "\$ENVF"$/a export KYTY_BC5_INPUT_CONFIG=$HOME/bc5-work/exp0381/input-rton.cfg' "$L" > "$S" || fail "smoke launcher"
bash -n "$S" || fail "the smoke launcher does not parse"
chmod +x "$S"
diff "$L" "$S" > "$R/smoke-vs-launcher.diff"
echo "smoke launcher $(m "$S"), $(grep -c '^>' "$R/smoke-vs-launcher.diff") lines against the launcher"
P1=$(pins); echo "after: $P1"
[ "$P1" = "$P0" ] || fail "A SHARED PIN CHANGED"
ok=1
echo "BUILD PASS $(date +%T)"
