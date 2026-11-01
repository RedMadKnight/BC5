#!/usr/bin/env bash
# BC5 exp 0388, the integration, second swap (the maintainer, 2026-11-01: "B: fix wraca"; D19): the job-arena fix back in the
# shared host tree and both emulators, beside the wait, over the first swap. The archive's code, the mount and play-pkg.sh do
# not change; the archive build runs and must leave it as it is.
#   1. checks: no emulator, the shared binaries, the archive, the tree's patch, every file of the manifest
#   2. the lock, then copies of the outputs and of every file, then the kit's files over the sources
#   3. archive, normal, lean
#   4. the tree's diff against f266548 must be the candidate patch 0001, index lines apart
# input.cfg, the learned list and the saves are not touched. A failure after step 2 restores everything from the copies. No
# emulator, no GPU work. Copies and the undo are under ~/bc5-work/exp0388/integration2/.
# usage: int0388j.sh   (on the box, in the slot, with box0388.sh, 0001-new.patch and kit/ beside it)
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0388; I=$E/integration2; K=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd)
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
MB=$W/bc5-tools-ubuntu/release/bc5-mount; TOOLS=$HOME/src/bc5/tools; NEWHDR=src/bc5/job_push_wait.hpp
EXPECT_NORMAL=7c0efa36; EXPECT_LEAN=@LEAN@; EXPECT_ARCHIVE=@ARCHIVE@; EXPECT_PATCH=476e1b3a; EXPECT_NEW=f3022900; EXPECT_KIT=dc2cf334
m() { md5sum < "$1" | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color f266548 | grep -av '^index ' | md5sum | cut -c1-8; }
stop() { echo "int0388j STOP: $*"; exit 1; }
root_of() { case "$1" in H) echo "$K" ;; B) echo "$BS" ;; T) echo "$TOOLS" ;; W) echo "$W" ;; esac; }
restore() {
    echo "restoring from $I"
    cp -p "$I/kyty_emulator.before-j" "$NB"; cp -p "$I/kyty_emulator-lean.before-j" "$LB"; cp -p "$I/libbc5_backend.a.before-j" "$ARCH"
    while read -r r f old new; do
        t=$(root_of "$r")/$f
        if [ "$old" = - ]; then rm -f "$t"; else mkdir -p "$(dirname "$t")"; cp -p "$I/tree-before/$r/$f" "$t"; fi
    done < "$HERE/kit/manifest.txt"
    [ "$(m "$NB")" = "$EXPECT_NORMAL" ] && [ "$(m "$LB")" = "$EXPECT_LEAN" ] && [ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] && echo "outputs restored; the build directories' objects are the new ones: rebuild before the next change"
    bash "$HERE/box0388.sh" release
    exit 1
}
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
[ "$(m "$NB")" = "$EXPECT_NORMAL" ] && [ "$(m "$LB")" = "$EXPECT_LEAN" ] && [ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] || stop "shared binaries or archive are not the pins: $(m "$NB") $(m "$LB") $(m "$ARCH")"
BS=$(sed -n 's/^KYTY_BC5_BACKEND_SRC:[A-Z]*=//p' "$W/kytyplus-build/CMakeCache.txt")
[ -f "$BS/CMakeLists.txt" ] || stop "the backend source [$BS] is not there"
[ "$(tdiff)" = "$EXPECT_PATCH" ] || stop "the tree's diff is not main's patch 0001: $(tdiff)"
[ "$(m "$HERE/0001-new.patch")" = "$EXPECT_NEW" ] && [ "$(m "$HERE/kit/manifest.txt")" = "$EXPECT_KIT" ] || stop "the kit is not the pins"
[ "$(grep -c 'exp 0372' "$HERE/0001-new.patch")" = 5 ] && grep -q '^+++ b/src/bc5/pad_audio_route.hpp' "$HERE/0001-new.patch" || stop "the candidate patch lacks exp 0372's route"
while read -r r f old new; do
    t=$(root_of "$r")/$f
    if [ "$old" = - ]; then [ ! -e "$t" ] || stop "$r $f exists"; else [ "$(m "$t")" = "$old" ] || stop "$r $f is $(m "$t"), not $old"; fi
    [ "$new" = - ] || [ "$(m "$HERE/kit/$r/$f")" = "$new" ] || stop "the kit's $r $f is not $new"
done < "$HERE/kit/manifest.txt"
bash "$HERE/box0388.sh" claim "exp 0388: the fix back, normal and lean, CPU only" 30 || exit 1
mkdir -p "$I/tree-before" || stop "no $I"
echo "$(date '+%F %T') before: normal $(m "$NB"), lean $(m "$LB"), archive $(m "$ARCH"), backend source $BS" | tee "$I/before.txt"
cp -p "$NB" "$I/kyty_emulator.before-j" && cp -p "$LB" "$I/kyty_emulator-lean.before-j" && cp -p "$ARCH" "$I/libbc5_backend.a.before-j" || { bash "$HERE/box0388.sh" release; stop "output copy failed"; }
while read -r r f old new; do
    [ "$old" = - ] && continue
    mkdir -p "$I/tree-before/$r/$(dirname "$f")" && cp -p "$(root_of "$r")/$f" "$I/tree-before/$r/$f" || { bash "$HERE/box0388.sh" release; stop "copy failed at $f"; }
done < "$HERE/kit/manifest.txt"
[ "$(m "$I/kyty_emulator.before-j")" = "$EXPECT_NORMAL" ] && [ "$(m "$I/kyty_emulator-lean.before-j")" = "$EXPECT_LEAN" ] && [ "$(m "$I/libbc5_backend.a.before-j")" = "$EXPECT_ARCHIVE" ] || { bash "$HERE/box0388.sh" release; stop "the copies do not read back"; }
while read -r r f old new; do
    t=$(root_of "$r")/$f
    if [ "$new" = - ]; then rm -f "$t" || restore; else mkdir -p "$(dirname "$t")" && cp "$HERE/kit/$r/$f" "$t" || restore; fi
done < "$HERE/kit/manifest.txt"
build() {  # name, command
    echo "== $(date +%T) $1"
    distrobox enter ubuntu -- sh -c "$2" > "$I/build-$1.out" 2>&1 || { tail -20 "$I/build-$1.out"; restore; }
}
build archive "nice -n 19 cmake --build '$W/backend-ubuntu' -j8"
build normal "cd '$W/kytyplus-build' && nice -n 19 ninja kyty_emulator"
build lean "cd '$W/kytyplus-build-lean' && nice -n 19 ninja kyty_emulator"
NM=$(m "$NB"); LM=$(m "$LB"); AM=$(m "$ARCH")
[ "$NM" != "$EXPECT_NORMAL" ] && [ "$LM" != "$EXPECT_LEAN" ] && [ "$AM" = "$EXPECT_ARCHIVE" ] || { echo "an output did not change: $NM $LM $AM"; restore; }
[ "$(strings "$NB" | grep -c 'job push wait: pushes')" = 1 ] && [ "$(strings "$LB" | grep -c 'job push wait: pushes')" = 0 ] || { echo "the trace is not as it should be"; restore; }
for b in "$NB" "$LB"; do [ "$(strings "$b" | grep -c 'job push wait %s')" = 1 ] && [ "$(strings "$b" | grep -c 'KYTY_BC5_JOB_PUSH_WAIT')" -ge 1 ] && [ "$(strings "$b" | grep -c 'job-arena fix APPLIED')" = 1 ] || { echo "$b lacks the wait or the fix"; restore; }; done
[ "$(tdiff)" = "$(grep -av '^index ' "$HERE/0001-new.patch" | md5sum | cut -c1-8)" ] || { echo "the tree's diff is not the candidate patch 0001"; restore; }
echo "$(date '+%F %T') after: normal $NM, lean $LM, archive $AM, warnings normal $(grep -c 'warning:' "$I/build-normal.out"), lean $(grep -c 'warning:' "$I/build-lean.out")" | tee "$I/after.txt"
echo "undo: the three outputs from $I/*.before-j, the files from $I/tree-before"
bash "$HERE/box0388.sh" release
