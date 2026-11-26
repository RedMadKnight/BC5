#!/usr/bin/env bash
# BC5 experiment 0323, parts 1 and 2 — the integration of the ring ordering (exps 0320-0322, F385) into the shared
# builds and the second title's launchers. Run by the top session on the box (CPU only, under its own lock line, no
# emulator running):
#   1. the backend: ~/src/bc5 must carry exp 0290's refusal (backend/src/policy.cpp with kMecIndirectCheckVerified —
#      the commit on main from exp 0323's branch); the shared archive ~/bc5-work/backend-ubuntu/libbc5_backend.a is
#      rebuilt in place (cmake --build, as tools/scripts/bc5-build.sh built it), the backend tests built and run in a
#      separate directory (exp0323/backend-tests; a failure stops before the relink), then both shared emulators are
#      relinked (ninja kyty_emulator in kytyplus-build and kytyplus-build-lean). Backups of the archive and both
#      binaries go to ~/bc5-work/exp0323/integration/ with their md5s; the new md5s are printed and written to
#      ~/bc5-work/exp0323/integration/new-md5.txt. The new normal binary must carry the refusal's string.
#   2. the launchers: launchers0323.pl on play-pkg.sh, play-pkg-log.sh and play-pkg-quiet.sh (anchored edits, backups
#      beside the binaries' in integration/, md5s printed).
# Guards: the lock empty and no emulator; the archive 549892e8, the normal binary d02f4696 and the lean 759cd455 as
# expected on 2026-10-25 19:30 (pass EXPECT_ARCHIVE / EXPECT_NORMAL / EXPECT_LEAN to accept others); ~/src/bc5 clean.
# usage: int0323.sh   (on the box; ~10 min)
set -u
W=$HOME/bc5-work; E=$W/exp0323; I=$E/integration; LOCK=$W/BOX-LOCK; SRC=$HOME/src/bc5
A=$W/backend-ubuntu/libbc5_backend.a; NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator
EXPECT_ARCHIVE=${EXPECT_ARCHIVE:-549892e8}; EXPECT_NORMAL=${EXPECT_NORMAL:-d02f4696}; EXPECT_LEAN=${EXPECT_LEAN:-759cd455}
HERE=$(cd "$(dirname "$0")" && pwd)
m() { md5sum < "$1" | cut -c1-8; }
mkdir -p "$I"
pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
[ -s "$HERE/launchers0323.pl" ] || { echo "no launchers0323.pl beside this script"; exit 1; }
grep -q "kMecIndirectCheckVerified" "$SRC/backend/src/policy.cpp" || { echo "$SRC/backend/src/policy.cpp lacks exp 0290's refusal (kMecIndirectCheckVerified): pull main first"; exit 1; }
[ -z "$(cd "$SRC" && git status --short)" ] || { echo "$SRC is not clean: stop"; (cd "$SRC" && git status --short | head); exit 1; }
[ "$(m "$A")" = "$EXPECT_ARCHIVE" ] || { echo "the shared archive is $(m "$A"), not $EXPECT_ARCHIVE: stop (EXPECT_ARCHIVE=... to accept)"; exit 1; }
[ "$(m "$NB")" = "$EXPECT_NORMAL" ] || { echo "the shared normal binary is $(m "$NB"), not $EXPECT_NORMAL: stop"; exit 1; }
[ "$(m "$LB")" = "$EXPECT_LEAN" ] || { echo "the shared lean binary is $(m "$LB"), not $EXPECT_LEAN: stop"; exit 1; }
for f in play-pkg.sh play-pkg-log.sh play-pkg-quiet.sh; do [ -s "$W/$f" ] || { echo "no $W/$f"; exit 1; }; done
echo "exp 0323 | integration: the backend refusal into the shared archive, both shared emulators relinked, the three launchers edited (CPU only, no emulator) | start $(date +%H:%M) | until ~$(date -d +15min +%H:%M)" > "$LOCK"
trap 'grep -q "^exp 0323 | integration" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
{ echo "$(date '+%F %T') before: archive $(m "$A"), normal $(m "$NB"), lean $(m "$LB"), src/bc5 $(cd "$SRC" && git log -1 --format=%h)"
  for f in play-pkg.sh play-pkg-log.sh play-pkg-quiet.sh; do echo "  $f $(m "$W/$f")"; done; } | tee "$I/before.txt"
cp -p "$A" "$I/libbc5_backend.a.before-0323" && cp -p "$NB" "$I/kyty_emulator.before-0323" && cp -p "$LB" "$I/kyty_emulator-lean.before-0323" || { echo "backup failed"; exit 1; }
echo "== $(date +%T) backend archive"
distrobox enter ubuntu -- sh -c "cd '$W/backend-ubuntu' && nice -n 19 cmake --build . -j8" > "$I/backend-build.out" 2>&1 || { tail -20 "$I/backend-build.out"; echo "backend build failed"; exit 1; }
echo "archive now $(m "$A")"
[ "$(m "$A")" != "$EXPECT_ARCHIVE" ] || { echo "the archive did not change: stop"; exit 1; }
echo "== $(date +%T) backend tests (a separate build directory)"
mkdir -p "$E/backend-tests"
distrobox enter ubuntu -- sh -c "cd '$E/backend-tests' && nice -n 19 cmake -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=ON '$SRC/backend' && nice -n 19 cmake --build . -j8 && ctest --output-on-failure" > "$I/backend-tests.out" 2>&1
trc=$?
tail -5 "$I/backend-tests.out"
[ $trc = 0 ] || { echo "backend tests failed (rc $trc): the archive is rebuilt but the emulators are NOT relinked; restore with: cp -p $I/libbc5_backend.a.before-0323 $A"; exit 1; }
echo "== $(date +%T) relink the shared emulators"
distrobox enter ubuntu -- sh -c "cd '$W/kytyplus-build' && nice -n 19 ninja kyty_emulator" > "$I/relink-normal.out" 2>&1 || { tail -20 "$I/relink-normal.out"; echo "normal relink failed"; exit 1; }
distrobox enter ubuntu -- sh -c "cd '$W/kytyplus-build-lean' && nice -n 19 ninja kyty_emulator" > "$I/relink-lean.out" 2>&1 || { tail -20 "$I/relink-lean.out"; echo "lean relink failed"; exit 1; }
NM=$(m "$NB"); LM=$(m "$LB")
[ "$NM" != "$EXPECT_NORMAL" ] || { echo "the normal binary did not change: stop"; exit 1; }
[ "$LM" != "$EXPECT_LEAN" ] || { echo "the lean binary did not change: stop"; exit 1; }
strings "$NB" | grep -q "MEC check unverified" || { echo "the new normal binary lacks the refusal's string: stop"; exit 1; }
echo "== $(date +%T) launchers"
perl "$HERE/launchers0323.pl" "$I" "$W/play-pkg.sh" "$W/play-pkg-log.sh" "$W/play-pkg-quiet.sh" || { echo "launcher edit failed (the files are untouched or restorable from $I/*.before-0323)"; exit 1; }
bash -n "$W/play-pkg.sh" && bash -n "$W/play-pkg-log.sh" && bash -n "$W/play-pkg-quiet.sh" || { echo "a launcher no longer parses: restore from $I/*.before-0323"; exit 1; }
{ echo "$(date '+%F %T') after: archive $(m "$A"), normal $NM, lean $LM"
  for f in play-pkg.sh play-pkg-log.sh play-pkg-quiet.sh; do echo "  $f $(m "$W/$f")"; done; } | tee "$I/new-md5.txt"
echo "archive=$(m "$A") normal=$NM lean=$LM play_pkg=$(m "$W/play-pkg.sh")" > "$I/new-md5.env"
echo "== $(date +%T) done; undo: cp -p $I/libbc5_backend.a.before-0323 $A; cp -p $I/kyty_emulator.before-0323 $NB; cp -p $I/kyty_emulator-lean.before-0323 $LB; cp -p $I/play-pkg*.before-0323 back to $W (names without the suffix)"
