#!/usr/bin/env bash
# BC5 experiment 0382 (exp 0372's build0372.sh): one private emulator, ~/bc5-work/exp0382/rt/kyty_emulator, the shared
# normal build with src/libs/controller.cpp carrying patch0382-input-rt.diff (the scripted input's "rt on|off" line,
# which calls the Emulation menu's SetRayTracing, for MODE=acs's A -> C -> A in one scene). A PRIVATE source tree under
# ~/bc5-work/exp0382/src holds the one file: the shared tree's controller.cpp (git blob 5cdb29a, patch 0001's) is
# copied there and the diff applied (git apply, LF), checked by git blob before (5cdb29a) and after (44daf5b, the
# diff's index line). The unit is compiled with the shared normal build's compdb command into a private object and the
# shared link command is run with that object (the shared objects and the shared backend archive as they are: the
# backend is untouched, so no backend tests). ~/src/KytyPlus, the shared builds, the archive and play-pkg.sh are only
# read; a previous private binary is kept beside the new one as kyty_emulator.<md5>. The file keeps the name
# kyty_emulator in its own directory (the box's pgrep guards).
# Layout on the box: this script, build0382.py and patch0382-input-rt.diff in ~/bc5-work/exp0382/in/.
# usage: bash ~/bc5-work/exp0382/in/build0382.sh   (CPU only, nice 19, ~3 min, no emulator)
set -u
E=$HOME/bc5-work/exp0382; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
B=$HOME/bc5-work/kytyplus-build; ARCH=$HOME/bc5-work/backend-ubuntu/libbc5_backend.a
EXPECT_ARCHIVE=${EXPECT_ARCHIVE:-bb50b2e0}; EXPECT_NORMAL=${EXPECT_NORMAL:-58c4a627}   # as pinned by exp 0379 and read 2026-10-29
EXPECT_TREE_BLOB=5cdb29a11a0d0f13fde24b97025fb5caa7f46243   # controller.cpp of patch 0001 on main (49f1116), md5 40a0e7b6
EXPECT_NEW_BLOB=44daf5b8d9c01b7c723683d2d1e3dd1b3b90a614    # with patch0382-input-rt.diff, md5 7d3c26f9
EXPECT_DIFF=${EXPECT_DIFF:-543a6f9c}
HERE=$(cd "$(dirname "$0")" && pwd)
TREE=$HOME/src/KytyPlus; SRC=$E/src; V=$E/rt; ME="white-dots exp 0382 | build"
mkdir -p "$R" "$V"
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
grep -q "MAINTAINER PLAYING" "$LOCK" && { echo "the maintainer plays: stop"; exit 1; }
[ -s "$LOCK" ] && grep -qv "^white-dots exp 0382 |" "$LOCK" && { echo "box locked: $(cat "$LOCK")"; exit 1; }
m() { md5sum < "$1" | cut -c1-8; }
blob() { distrobox enter ubuntu -- git hash-object --no-filters "$1" 2> /dev/null | tail -1; }
[ "$(m "$B/src/kyty_emulator")" = "$EXPECT_NORMAL" ] || { echo "the shared normal binary is $(m "$B/src/kyty_emulator"), not $EXPECT_NORMAL: stop"; exit 1; }
[ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] || { echo "the shared archive is $(m "$ARCH"), not $EXPECT_ARCHIVE: stop"; exit 1; }
[ -f "$HERE/build0382.py" ] && [ -f "$HERE/patch0382-input-rt.diff" ] || { echo "no build0382.py or patch0382-input-rt.diff beside this script"; exit 1; }
[ "$(m "$HERE/patch0382-input-rt.diff")" = "$EXPECT_DIFF" ] || { echo "patch0382-input-rt.diff is $(m "$HERE/patch0382-input-rt.diff"), not $EXPECT_DIFF: stop"; exit 1; }
TB=$(blob "$TREE/src/libs/controller.cpp")
[ "$TB" = "$EXPECT_TREE_BLOB" ] || { echo "the tree's controller.cpp is blob ${TB:-?}, not $EXPECT_TREE_BLOB (patch 0001's): stop"; exit 1; }
echo "$ME of ~/bc5-work/exp0382/rt/kyty_emulator (controller.cpp with the rt input line compiled in a private tree, relinked; CPU only, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +8min +%H:%M)" >> "$LOCK"
trap 'sed -i "/^white-dots exp 0382 | build /d" "$LOCK" 2> /dev/null' EXIT
{ echo "$(date '+%F %T') shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $(m "$B/src/kyty_emulator"); shared archive $(m "$ARCH"); tree controller.cpp blob $TB md5 $(m "$TREE/src/libs/controller.cpp"); diff $(m "$HERE/patch0382-input-rt.diff")"; } > "$R/build-inputs.txt"; cat "$R/build-inputs.txt"
# 1. The private tree: the shared tree's controller.cpp with the diff (every include comes from the shared tree).
rm -rf "$SRC" "$V/obj"; mkdir -p "$SRC/src/libs"
cp "$TREE/src/libs/controller.cpp" "$SRC/src/libs/controller.cpp" || exit 1
distrobox enter ubuntu -- sh -c "cd '$SRC' && git rev-parse --is-inside-work-tree > /dev/null 2>&1 && { echo 'the private tree is inside a git work tree: stop'; exit 1; }; git -c core.autocrlf=false apply --verbose '$HERE/patch0382-input-rt.diff'" > "$R/apply.out" 2>&1 || { echo "the diff did not apply:"; cat "$R/apply.out"; exit 1; }
cat "$R/apply.out"
NB=$(blob "$SRC/src/libs/controller.cpp")
[ "$NB" = "$EXPECT_NEW_BLOB" ] || { echo "the patched controller.cpp is blob ${NB:-?}, not $EXPECT_NEW_BLOB: stop"; exit 1; }
diff -u "$TREE/src/libs/controller.cpp" "$SRC/src/libs/controller.cpp" > "$R/controller.cpp-0382.diff"
echo "controller.cpp: $(grep -c '^+[^+]' "$R/controller.cpp-0382.diff") lines added, $(grep -c '^-[^-]' "$R/controller.cpp-0382.diff") removed, $(grep -c 'experiment 0382' "$SRC/src/libs/controller.cpp") marks"
echo "== $(date +%T) compdb"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || { echo "compdb failed"; exit 1; }
BIN=$V/kyty_emulator
if [ -f "$BIN" ]; then OLD=$BIN.$(m "$BIN"); [ -e "$OLD" ] || mv "$BIN" "$OLD"; echo "previous binary kept as $OLD"; fi
echo "== $(date +%T) compile + relink"
distrobox enter ubuntu -- python3 -I "$HERE/build0382.py" "$E/compdb.json" "$SRC" "$V" "$B" "$BIN" > "$R/build.out" 2>&1
rc=$?; echo "== $(date +%T) rc $rc; errors $(grep -c 'error:' "$R/build.out"), warnings $(grep -c 'warning:' "$R/build.out")"
grep -n "error:\|undefined\|COMPILE FAILED" "$R/build.out" | head -20
grep -n "warning:" "$R/build.out" | sed 's/\x1b\[[0-9;]*m//g' | cut -c1-200 | head -10
[ $rc = 0 ] && [ -x "$BIN" ] || { echo "build failed: see $R/build.out"; exit 1; }
m "$BIN" > "$V/binary.md5"; echo "md5 $(cat "$V/binary.md5") (shared $EXPECT_NORMAL)"
[ "$(cat "$V/binary.md5")" != "$EXPECT_NORMAL" ] || { echo "the binary equals the shared one"; exit 1; }
echo "strings: rt line $(strings "$BIN" | grep -c 'input-cmd: ray tracing %s requested'), the flip's switch line $(strings "$BIN" | grep -c 'ray tracing %s at the flip'), exp 0372 audio $(strings "$BIN" | grep -c 'AudioOut (exp 0372)')"
echo "$(date '+%F %T') $(cat "$V/binary.md5") rt/kyty_emulator: the shared objects ($EXPECT_NORMAL) with controller.cpp + patch0382-input-rt.diff ($EXPECT_DIFF, blob $NB) + the shared archive $EXPECT_ARCHIVE; rc $rc" >> "$R/binaries.txt"
echo "shared binary after: $(m "$B/src/kyty_emulator") (want $EXPECT_NORMAL); shared archive after: $(m "$ARCH") (want $EXPECT_ARCHIVE); tree controller.cpp after: blob $(blob "$TREE/src/libs/controller.cpp")"
