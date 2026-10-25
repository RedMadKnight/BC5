#!/usr/bin/env bash
# BC5 experiment 0329, the integration (the maintainer, 2026-10-25: "po skompilowaniu i zbudowaniu - przekaż mi do testów
# - od razu do wersji zwykłej i lean"): the patched files of patch0329.py (exp 0327's twelve imports + exp 0328's
# NpCppWebApi port + exp 0329's 61) copied from the private build's source copy over the shared tree ~/src/KytyPlus
# (f266548 + patch 0001), the five new units added beside them, both shared emulators rebuilt in place (ninja; the
# CONFIGURE_DEPENDS glob of src/CMakeLists.txt picks the new units up), the tree's diff against f266548 written out as
# the candidate for backend/kytyplus-patches/0001-bc5-lle-agc.patch (D19: the copy on main must match what the shared
# builds were built from — the top session takes it to main). Every replaced file and both binaries are backed up
# under ~/bc5-work/exp0329/integration/; the undo is printed at the end. Nothing else shared is written.
# usage: int0329.sh   (on the box, after build0329.sh passed; CPU only, nice 19, under the BOX-LOCK; no emulator runs)
set -u
W=$HOME/bc5-work; E=$W/exp0329; I=$E/integration; LOCK=$W/BOX-LOCK; K=$HOME/src/KytyPlus
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator
EXPECT_NORMAL=${EXPECT_NORMAL:-5dd77a82}; EXPECT_LEAN=${EXPECT_LEAN:-47e4a31a}
HERE=$(cd "$(dirname "$0")" && pwd)
NEW_UNITS="libNpCppWebApi.cpp libPngEnc.cpp libPlayGoDialog.cpp libNpCommerceDialog.cpp libPlayerInvitationDialog.cpp"
FILES="src/kernel/syncOnAddress.h src/kernel/syncOnAddress.cpp src/libs/libKernel.cpp src/kernel/fileSystem.h src/kernel/fileSystem.cpp src/libs/libC.cpp src/loader/runtimeLinker.cpp src/libs/libs.cpp src/kernel/memory.h src/kernel/memory.cpp src/libs/network.h src/libs/network.cpp src/libs/libNet.cpp src/libs/libSaveData.cpp src/libs/audio.h src/libs/audio.cpp src/libs/libAudio.cpp src/libs/controller.h src/libs/controller.cpp src/libs/libPad.cpp src/graphics/presentation/videoOut.h src/graphics/presentation/videoOut.cpp src/libs/libVideoOut.cpp"
m() { md5sum < "$1" | cut -c1-8; }
mkdir -p "$I/tree-before"
pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
[ "$(m "$K/src/libs/bc5LleAgc.cpp")" = 5bccbb80 ] || { echo "the tree's bc5LleAgc.cpp is not 5bccbb80: stop"; exit 1; }
[ "$(m "$NB")" = "$EXPECT_NORMAL" ] || { echo "the shared normal binary is $(m "$NB"), not $EXPECT_NORMAL: stop (EXPECT_NORMAL=... to accept)"; exit 1; }
[ "$(m "$LB")" = "$EXPECT_LEAN" ] || { echo "the shared lean binary is $(m "$LB"), not $EXPECT_LEAN: stop (EXPECT_LEAN=... to accept)"; exit 1; }
[ -s "$E/binary.md5" ] && tail -1 "$E/raw/binaries.txt" | grep -q "tests rc 0" || { echo "no passed private build of 0329 (binary.md5 / binaries.txt 'tests rc 0'): stop"; exit 1; }
for f in $FILES; do [ -s "$E/src/$f" ] || { echo "no patched $f under $E/src: stop"; exit 1; }; [ -s "$K/$f" ] || { echo "no $f in the tree: stop"; exit 1; }; done
for f in $NEW_UNITS; do [ -s "$HERE/$f" ] || { echo "no $f beside this script"; exit 1; }; [ -e "$K/src/libs/$f" ] && { echo "$K/src/libs/$f exists already: stop"; exit 1; }; done
for f in $FILES; do cmp -s "$E/src/$f" "$K/$f" && { echo "$f: the patched copy equals the tree's (already integrated?): stop"; exit 1; }; done
echo "exp 0329 | integration: the three experiments' files into ~/src/KytyPlus, both shared emulators rebuilt (ninja, CPU only, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +25min +%H:%M)" > "$LOCK"
trap 'grep -q "^exp 0329 | integration" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
{ echo "$(date '+%F %T') before: normal $(m "$NB"), lean $(m "$LB"), tree $(cd "$K" && git log -1 --format=%h), $(cd "$K" && git status --short | wc -l) changed entries"
  for f in $FILES; do echo "  $f tree $(m "$K/$f") -> patched $(m "$E/src/$f")"; done
  for f in $NEW_UNITS; do echo "  $f (new) $(m "$HERE/$f")"; done; } | tee "$I/before.txt"
cp -p "$NB" "$I/kyty_emulator.before-0329" && cp -p "$LB" "$I/kyty_emulator-lean.before-0329" || { echo "binary backup failed"; exit 1; }
for f in $FILES; do mkdir -p "$I/tree-before/$(dirname "$f")" && cp -p "$K/$f" "$I/tree-before/$f" || { echo "tree backup failed at $f"; exit 1; }; done
echo "== $(date +%T) files into the tree"
for f in $FILES; do cp "$E/src/$f" "$K/$f" || { echo "copy failed at $f: restore from $I/tree-before"; exit 1; }; done
for f in $NEW_UNITS; do cp "$HERE/$f" "$K/src/libs/$f" || { echo "copy failed at $f"; exit 1; }; done
echo "== $(date +%T) normal build"
distrobox enter ubuntu -- sh -c "cd '$W/kytyplus-build' && nice -n 19 ninja kyty_emulator" > "$I/build-normal.out" 2>&1 || { tail -30 "$I/build-normal.out"; echo "normal build FAILED: the tree holds the new files; undo: for f in $FILES; do cp -p $I/tree-before/\$f $K/\$f; done; rm $K/src/libs/{$(echo $NEW_UNITS | tr ' ' ',')}; then ninja both"; exit 1; }
echo "== $(date +%T) lean build"
distrobox enter ubuntu -- sh -c "cd '$W/kytyplus-build-lean' && nice -n 19 ninja kyty_emulator" > "$I/build-lean.out" 2>&1 || { tail -30 "$I/build-lean.out"; echo "lean build FAILED (the normal one is rebuilt): see $I/build-lean.out"; exit 1; }
NM=$(m "$NB"); LM=$(m "$LB")
[ "$NM" != "$EXPECT_NORMAL" ] || { echo "the normal binary did not change: stop"; exit 1; }
[ "$LM" != "$EXPECT_LEAN" ] || { echo "the lean binary did not change: stop"; exit 1; }
echo "strings: normal stub lines $(strings "$NB" | grep -c 'stubbed import') NpCppWebApi $(strings "$NB" | grep -c 'NpCppWebApi: not reachable'); lean stub lines $(strings "$LB" | grep -c 'stubbed import') NpCppWebApi $(strings "$LB" | grep -c 'NpCppWebApi: not reachable')"
echo "warnings: normal $(grep -c 'warning:' "$I/build-normal.out"), lean $(grep -c 'warning:' "$I/build-lean.out"); errors: $(grep -c 'error:' "$I/build-normal.out" "$I/build-lean.out" | tr '\n' ' ')"
# the candidate patch 0001 (D19): the tree's whole diff against f266548, the new units included
(cd "$K" && git add -N src/libs/libNpCppWebApi.cpp src/libs/libPngEnc.cpp src/libs/libPlayGoDialog.cpp src/libs/libNpCommerceDialog.cpp src/libs/libPlayerInvitationDialog.cpp && git diff --no-color f266548 > "$I/0001-bc5-lle-agc.patch.0329" && echo "candidate patch 0001: $(wc -l < "$I/0001-bc5-lle-agc.patch.0329") lines, md5 $(m "$I/0001-bc5-lle-agc.patch.0329"), bc5LleAgc.cpp $(m "$K/src/libs/bc5LleAgc.cpp")")
{ echo "$(date '+%F %T') after: normal $NM, lean $LM, tree $(cd "$K" && git status --short | wc -l) changed entries"; } | tee "$I/new-md5.txt"
echo "normal=$NM lean=$LM" > "$I/new-md5.env"
echo "== $(date +%T) done; undo: cp -p $I/kyty_emulator.before-0329 $NB; cp -p $I/kyty_emulator-lean.before-0329 $LB; for f in $FILES; do cp -p $I/tree-before/\$f $K/\$f; done; rm $K/src/libs/{$(echo $NEW_UNITS | tr ' ' ',')}"
