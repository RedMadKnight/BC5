#!/usr/bin/env bash
# BC5 experiment 0361, the integration (the maintainer, 2026-10-28: "Tak, wbuduj"), after his 514-s play through the
# fight on exp 0359's test shortcut (F457): the job-arena fix (a TEMPORARY game-code workaround, HANDOFF Q24) goes into
# both shared builds exactly as the test binary 89b95e4e was built:
#   1. the host: exp 0359's private tree ~/bc5-work/exp0359/src — six patched files (gamePatch.cpp/.h, runtimeLinker.cpp,
#      hostInput.cpp/.h, hostMenu.cpp) and the new src/bc5/job_arena_fix.hpp — md5-checked, over ~/src/KytyPlus, each
#      original checked to be the one exp 0359 patched;
#   2. the backend checkout ~/src/bc5/backend: the same header and its Catch2 test, and the test in CMakeLists.txt (from
#      main; header-only, the archive is not rebuilt: no new object);
#   3. both shared emulators rebuilt in place (ninja);
#   4. the host tree's diff against f266548 written out as the candidate for backend/kytyplus-patches/0001 (D19).
# play-pkg.sh and input.cfg are not touched: the fix is on by default for PPSA03671 when input.cfg does not set
# JobArenaFix.PPSA03671. Backups and the undo are under ~/bc5-work/exp0361/integration/.
# usage: int0361.sh   (on the box, with backend-files/ beside it; CPU only, nice 19, under the BOX-LOCK; no emulator)
set -u
W=$HOME/bc5-work; E=$W/exp0361; I=$E/integration; LOCK=$W/BOX-LOCK; K=$HOME/src/KytyPlus; S=$HOME/src/bc5
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
EXPECT_NORMAL=${EXPECT_NORMAL:-affa0c22}; EXPECT_LEAN=${EXPECT_LEAN:-cd7ea936}; EXPECT_ARCHIVE=bb50b2e0; EXPECT_PATCH=6ac6cc16
P=$W/exp0359/src; HERE=$(cd "$(dirname "$0")" && pwd); BF=$HERE/backend-files
# file  original-md5  patched-md5 (exp 0359's private tree, as built into 89b95e4e)
FILES="src/loader/gamePatch.cpp:8c1cd621:eb8cce4c src/loader/gamePatch.h:d6c79fb7:7da6a067 src/loader/runtimeLinker.cpp:e37ed5cd:96e03695 src/graphics/presentation/window/hostInput.cpp:a8317e02:92cfcee8 src/graphics/presentation/window/hostInput.h:8fc3edb9:4f6178db src/graphics/presentation/hostMenu.cpp:cb35096f:85575cae"
NEWHDR=src/bc5/job_arena_fix.hpp; EXPECT_HDR=22a78051
BFILES="include/bc5/job_arena_fix.hpp:22a78051 tests/job_arena_fix_test.cpp:a65221ca CMakeLists.txt:6b17f03c"
m() { md5sum < "$1" | cut -c1-8; }
mkdir -p "$I/tree-before" "$I/backend-before"
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
[ "$(m "$NB")" = "$EXPECT_NORMAL" ] && [ "$(m "$LB")" = "$EXPECT_LEAN" ] && [ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] || { echo "shared binaries/archive not affa0c22/cd7ea936/bb50b2e0: stop"; exit 1; }
[ "$(cd "$K" && git diff --no-color f266548 | md5sum | cut -c1-8)" = "$EXPECT_PATCH" ] || { echo "the host tree's diff is not main's patch 0001 $EXPECT_PATCH: stop"; exit 1; }
for e in $FILES; do f=${e%%:*}; r=${e#*:}; o=${r%%:*}; n=${r#*:}
  [ "$(m "$K/$f")" = "$o" ] || { echo "$K/$f is $(m "$K/$f"), not the original $o: stop"; exit 1; }
  [ "$(m "$P/$f")" = "$n" ] || { echo "$P/$f is $(m "$P/$f"), not the tested $n: stop"; exit 1; }; done
[ ! -e "$K/$NEWHDR" ] && [ "$(m "$P/$NEWHDR")" = "$EXPECT_HDR" ] || { echo "$K/$NEWHDR exists or $P/$NEWHDR is not $EXPECT_HDR: stop"; exit 1; }
for e in $BFILES; do f=${e%%:*}; w=${e#*:}; [ "$(m "$BF/$f")" = "$w" ] || { echo "$BF/$f is not $w: stop"; exit 1; }; done
[ "$(git -C "$S" status --porcelain -- backend | wc -l)" -ge 0 ] || exit 1
echo "exp 0361 | integration: exp 0359's job-arena fix (temporary, menu switch, on by default for PPSA03671) into the shared host tree and the backend checkout, both shared emulators rebuilt (ninja, CPU only, nice 19, no emulator) | start $(date +%H:%M) | until ~$(date -d +15min +%H:%M)" > "$LOCK"
trap 'grep -q "^exp 0361 | integration" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
{ echo "$(date '+%F %T') before: normal $(m "$NB"), lean $(m "$LB"), archive $(m "$ARCH"), tree diff $EXPECT_PATCH, $S $(git -C "$S" log -1 --format=%h)"; } | tee "$I/before.txt"
cp -p "$NB" "$I/kyty_emulator.before-0361" && cp -p "$LB" "$I/kyty_emulator-lean.before-0361" || { echo "binary backup failed"; exit 1; }
for e in $FILES; do f=${e%%:*}; mkdir -p "$I/tree-before/$(dirname "$f")" && cp -p "$K/$f" "$I/tree-before/$f" || { echo "backup failed at $f"; exit 1; }; done
cp -p "$S/backend/CMakeLists.txt" "$I/backend-before/CMakeLists.txt" || exit 1
UNDO="cp -p $I/kyty_emulator.before-0361 $NB; cp -p $I/kyty_emulator-lean.before-0361 $LB; for f in $(for e in $FILES; do printf '%s ' "${e%%:*}"; done); do cp -p $I/tree-before/\$f $K/\$f; done; rm -f $K/$NEWHDR; cp -p $I/backend-before/CMakeLists.txt $S/backend/CMakeLists.txt; rm -f $S/backend/include/bc5/job_arena_fix.hpp $S/backend/tests/job_arena_fix_test.cpp"
echo "== $(date +%T) 1. host files into $K"
for e in $FILES; do f=${e%%:*}; cp "$P/$f" "$K/$f" || { echo "copy failed at $f; undo: $UNDO"; exit 1; }; done
mkdir -p "$K/src/bc5" && cp "$P/$NEWHDR" "$K/$NEWHDR" || { echo "header copy failed; undo: $UNDO"; exit 1; }
echo "== $(date +%T) 2. backend files into $S/backend"
for e in $BFILES; do f=${e%%:*}; mkdir -p "$S/backend/$(dirname "$f")" && cp "$BF/$f" "$S/backend/$f" || { echo "backend copy failed at $f; undo: $UNDO"; exit 1; }; done
echo "== $(date +%T) 3a. normal build"
distrobox enter ubuntu -- sh -c "cd '$W/kytyplus-build' && nice -n 19 ninja kyty_emulator" > "$I/build-normal.out" 2>&1 || { tail -30 "$I/build-normal.out"; echo "normal build FAILED; undo: $UNDO; then ninja both"; exit 1; }
echo "== $(date +%T) 3b. lean build"
distrobox enter ubuntu -- sh -c "cd '$W/kytyplus-build-lean' && nice -n 19 ninja kyty_emulator" > "$I/build-lean.out" 2>&1 || { tail -30 "$I/build-lean.out"; echo "lean build FAILED (the normal one is rebuilt); undo: $UNDO; then ninja both"; exit 1; }
NM=$(m "$NB"); LM=$(m "$LB")
[ "$NM" != "$EXPECT_NORMAL" ] && [ "$LM" != "$EXPECT_LEAN" ] || { echo "a binary did not change (normal $NM, lean $LM); undo: $UNDO"; exit 1; }
for b in "$NB" "$LB"; do echo "strings $b: job-arena APPLIED $(strings "$b" | grep -c 'job-arena fix APPLIED'), menu item $(strings "$b" | grep -c 'Job-arena fix'), JobArenaFix key $(strings "$b" | grep -c 'JobArenaFix'), 0349 cut $(strings "$b" | grep -c 'experiment 0349: a job')"; done
echo "warnings: normal $(grep -c 'warning:' "$I/build-normal.out"), lean $(grep -c 'warning:' "$I/build-lean.out"); recompiled: normal $(grep -c '^\[[0-9]*/[0-9]*\] Building' "$I/build-normal.out"), lean $(grep -c '^\[[0-9]*/[0-9]*\] Building' "$I/build-lean.out")"
[ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] || echo "NOTE: the archive changed ($(m "$ARCH"))"
echo "== $(date +%T) 4. the candidate patch 0001"
(cd "$K" && git add -N "$NEWHDR" 2> /dev/null; git diff --no-color f266548) > "$I/0001-bc5-lle-agc.patch.0361"
echo "candidate patch 0001: $(wc -l < "$I/0001-bc5-lle-agc.patch.0361") lines, md5 $(m "$I/0001-bc5-lle-agc.patch.0361"); new header in it: $(grep -c "^+++ b/$NEWHDR" "$I/0001-bc5-lle-agc.patch.0361")"
{ echo "$(date '+%F %T') after: normal $NM, lean $LM, archive $(m "$ARCH")"; } | tee "$I/new-md5.txt"
echo "normal=$NM lean=$LM archive=$(m "$ARCH") launcher=$(m "$W/play-pkg.sh")" > "$I/new-md5.env"
echo "== $(date +%T) done; undo: $UNDO; then ninja kyty_emulator in both builds (or keep the restored binaries)"
