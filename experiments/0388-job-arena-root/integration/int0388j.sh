#!/usr/bin/env bash
# BC5 exp 0389, the swap (the maintainer, 2026-11-02: "Jak już, to bez J. Do wyrzucenia.", "Zbuduj już właściwie wersję lean i
# zwykła."; D19): J out, the second switch cleanup in, the job-arena fix as it stands, in the host tree, the backend and both
# emulators, and the dead lines out of play-pkg.sh and bc5-run.env. The mount and input.cfg are not touched.
#   1. checks: no emulator, the shared binaries, the archive, the tree's patch, every file of the manifest
#   2. the lock, then copies of the outputs and of every file, then the kit's files over the sources
#   3. archive, normal, lean
#   4. the tree's diff against f266548 must be the candidate patch 0001, index lines apart
# A failure after step 2 restores everything from the copies. No emulator, no GPU work. Copies and the undo are under
# ~/bc5-work/exp0388/integration3/; the old binaries need the old settings files back too.
# usage: int0388j.sh   (on the box, in the slot, with box0388.sh, 0001-new.patch and kit/ beside it)
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0388; I=$E/integration3; K=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd)
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
MB=$W/bc5-tools-ubuntu/release/bc5-mount; TOOLS=$HOME/src/bc5/tools; NEWHDR=src/bc5/job_push_wait.hpp
EXPECT_NORMAL=f4e1a52e; EXPECT_LEAN=206aa65d; EXPECT_ARCHIVE=75e30335; EXPECT_PATCH=40d68bdb; EXPECT_NEW=728f2a77; EXPECT_KIT=0fcdd4ac
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
bash "$HERE/box0388.sh" claim "exp 0389: J out, the switch cleanup, normal and lean, CPU only" 30 || exit 1
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
[ "$NM" != "$EXPECT_NORMAL" ] && [ "$LM" != "$EXPECT_LEAN" ] || { echo "an output did not change: $NM $LM $AM"; restore; }
for b in "$NB" "$LB"; do [ "$(strings "$b" | grep -c 'job push wait')" = 0 ] && [ "$(strings "$b" | grep -c 'job-arena fix APPLIED')" = 1 ] || { echo "$b still has the wait or lacks the fix"; restore; }; done
[ "$(tdiff)" = "$(grep -av '^index ' "$HERE/0001-new.patch" | md5sum | cut -c1-8)" ] || { echo "the tree's diff is not the candidate patch 0001"; restore; }
echo "$(date '+%F %T') after: normal $NM, lean $LM, archive $AM, warnings normal $(grep -c 'warning:' "$I/build-normal.out"), lean $(grep -c 'warning:' "$I/build-lean.out")" | tee "$I/after.txt"
echo "undo: the three outputs from $I/*.before-j, the files from $I/tree-before"
bash "$HERE/box0388.sh" release
