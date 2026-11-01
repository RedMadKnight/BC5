#!/usr/bin/env bash
# BC5 exp 0388, the integration (the maintainer, 2026-11-01: "Ramię J ma być wbudowane", "dla wszystkich tytułów", "arena fix
# ma zniknąć z opcji i z kodu"; D19): the job push wait into the shared host tree and both shared emulators, and the job-arena
# fix out of them, in the way of exp 0361's int0361.sh.
#   1. checks: no emulator, an empty lock taken atomically, the shared binaries, the archive, the tree's patch and the files
#   2. copies of both binaries and the files, then mkhost.py on ~/src/KytyPlus, each result against the laptop's md5
#   3. ninja kyty_emulator in the normal and the lean build, nice 19
#   4. the tree's diff against f266548 must be the candidate patch 0001 byte for byte
# The archive, play-pkg.sh, input.cfg, the learned list and the saves are not touched. A failure after step 2 restores
# everything from the copies. No emulator, no GPU work. Backups and the undo are under ~/bc5-work/exp0388/integration/.
# usage: int0388j.sh   (on the box, in the slot, with mkhost.py, job_push_wait.hpp and 0001-new.patch beside it)
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0388; I=$E/integration; K=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd)
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
EXPECT_NORMAL=78f25172; EXPECT_LEAN=7b246487; EXPECT_ARCHIVE=3292bdaf; EXPECT_PATCH=716dcaf6; EXPECT_NEW=e5bb3acd; EXPECT_HDR=0c75c26d
# file  original-md5  patched-md5
FILES="src/kernel/semaphore.cpp:8a9ddbc4:9b3b1e1e src/loader/gamePatch.cpp:eb8cce4c:9185b0e1 src/loader/gamePatch.h:7da6a067:4df79c77 src/loader/runtimeLinker.cpp:96e03695:938ed47b src/graphics/presentation/hostMenu.cpp:85575cae:cb35096f src/graphics/presentation/window/hostInput.cpp:92cfcee8:1b2d3665 src/graphics/presentation/window/hostInput.h:4f6178db:8fc3edb9"
NEWHDR=src/bc5/job_push_wait.hpp; OLDHDR=src/bc5/job_arena_fix.hpp
m() { md5sum < "$1" | cut -c1-8; }
stop() { echo "int0388j STOP: $*"; exit 1; }
restore() {
    echo "restoring from $I"
    cp -p "$I/kyty_emulator.before-j" "$NB"; cp -p "$I/kyty_emulator-lean.before-j" "$LB"
    for e in $FILES; do cp -p "$I/tree-before/${e%%:*}" "$K/${e%%:*}"; done
    cp -p "$I/tree-before/$OLDHDR" "$K/$OLDHDR"; rm -f "$K/$NEWHDR"
    git -C "$K" reset -q -- "$NEWHDR" 2> /dev/null
    [ "$(m "$NB")" = "$EXPECT_NORMAL" ] && [ "$(m "$LB")" = "$EXPECT_LEAN" ] && echo "binaries restored; the build directories' objects are the new ones: ninja kyty_emulator in both before the next change"
    bash "$HERE/box0388.sh" release
    exit 1
}
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
[ "$(m "$NB")" = "$EXPECT_NORMAL" ] && [ "$(m "$LB")" = "$EXPECT_LEAN" ] && [ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] || stop "shared binaries or archive are not the pins: $(m "$NB") $(m "$LB") $(m "$ARCH")"
[ "$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)" = "$EXPECT_PATCH" ] || stop "the tree's diff is not main's patch 0001"
[ ! -e "$K/$NEWHDR" ] && [ "$(m "$K/$OLDHDR")" = 22a78051 ] || stop "$NEWHDR exists, or $OLDHDR is not the known one"
[ "$(m "$HERE/job_push_wait.hpp")" = "$EXPECT_HDR" ] && [ "$(m "$HERE/0001-new.patch")" = "$EXPECT_NEW" ] || stop "the kit is not the pins"
grep -c 'exp 0372' "$HERE/0001-new.patch" | grep -qx 5 && grep -q '^+++ b/src/bc5/pad_audio_route.hpp' "$HERE/0001-new.patch" || stop "the candidate patch lacks exp 0372's route"
for e in $FILES; do f=${e%%:*}; r=${e#*:}; [ "$(m "$K/$f")" = "${r%%:*}" ] || stop "$f is $(m "$K/$f"), not the original"; done
bash "$HERE/box0388.sh" claim "exp 0388: J into both shared builds, CPU only, no emulator" 30 || exit 1
mkdir -p "$I/tree-before" || stop "no $I"
echo "$(date '+%F %T') before: normal $(m "$NB"), lean $(m "$LB"), archive $(m "$ARCH"), tree diff $EXPECT_PATCH" | tee "$I/before.txt"
cp -p "$NB" "$I/kyty_emulator.before-j" && cp -p "$LB" "$I/kyty_emulator-lean.before-j" || { bash "$HERE/box0388.sh" release; stop "binary copy failed"; }
for e in $FILES; do f=${e%%:*}; mkdir -p "$I/tree-before/$(dirname "$f")" && cp -p "$K/$f" "$I/tree-before/$f" || { bash "$HERE/box0388.sh" release; stop "copy failed at $f"; }; done
mkdir -p "$I/tree-before/src/bc5" && cp -p "$K/$OLDHDR" "$I/tree-before/$OLDHDR" || { bash "$HERE/box0388.sh" release; stop "copy failed at $OLDHDR"; }
[ "$(m "$I/kyty_emulator.before-j")" = "$EXPECT_NORMAL" ] && [ "$(m "$I/kyty_emulator-lean.before-j")" = "$EXPECT_LEAN" ] || { bash "$HERE/box0388.sh" release; stop "the copies do not read back"; }
python3 -I "$HERE/mkhost.py" "$K" "$HERE/job_push_wait.hpp" || restore
for e in $FILES; do f=${e%%:*}; r=${e#*:}; [ "$(m "$K/$f")" = "${r#*:}" ] || { echo "$f is $(m "$K/$f"), not the laptop's"; restore; }; done
echo "== $(date +%T) normal build"
distrobox enter ubuntu -- sh -c "cd '$W/kytyplus-build' && nice -n 19 ninja kyty_emulator" > "$I/build-normal.out" 2>&1 || { tail -20 "$I/build-normal.out"; restore; }
echo "== $(date +%T) lean build"
distrobox enter ubuntu -- sh -c "cd '$W/kytyplus-build-lean' && nice -n 19 ninja kyty_emulator" > "$I/build-lean.out" 2>&1 || { tail -20 "$I/build-lean.out"; restore; }
NM=$(m "$NB"); LM=$(m "$LB")
[ "$NM" != "$EXPECT_NORMAL" ] && [ "$LM" != "$EXPECT_LEAN" ] || { echo "a binary did not change: $NM $LM"; restore; }
[ "$(strings "$NB" | grep -c 'job push wait: pushes')" = 1 ] && [ "$(strings "$LB" | grep -c 'job push wait: pushes')" = 0 ] || { echo "the trace is not as it should be"; restore; }
for b in "$NB" "$LB"; do [ "$(strings "$b" | grep -c 'job push wait %s')" = 1 ] && [ "$(strings "$b" | grep -c 'KYTY_BC5_JOB_PUSH_WAIT')" -ge 1 ] && [ "$(strings "$b" | grep -c 'job-arena')" = 0 ] || { echo "$b lacks the wait or still has the fix"; restore; }; done
git -C "$K" add -N "$NEWHDR" || restore
git -C "$K" diff --no-color f266548 > "$I/0001-bc5-lle-agc.patch.j"
cmp -s "$I/0001-bc5-lle-agc.patch.j" "$HERE/0001-new.patch" || { echo "the tree's diff is not the candidate patch 0001"; restore; }
[ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] || echo "NOTE: the archive changed: $(m "$ARCH")"
echo "$(date '+%F %T') after: normal $NM, lean $LM, archive $(m "$ARCH"), recompiled normal $(grep -c '^\[[0-9]*/[0-9]*\] Building' "$I/build-normal.out"), warnings normal $(grep -c 'warning:' "$I/build-normal.out"), lean $(grep -c 'warning:' "$I/build-lean.out")" | tee "$I/after.txt"
echo "undo: cp -p $I/kyty_emulator.before-j $NB; cp -p $I/kyty_emulator-lean.before-j $LB; then the files from $I/tree-before and rm $K/$NEWHDR"
bash "$HERE/box0388.sh" release
