#!/usr/bin/env bash
# BC5 exp 0388, the integration (the maintainer, 2026-11-01: "Ramię J ma być wbudowane", "dla wszystkich tytułów", "arena fix ma
# zniknąć z opcji i z kodu", "Usuń A oraz B, wbuduj J"; D19): the job push wait in, the job-arena fix and classes A and B out, in
# the shared host tree, the backend, the mount and all shared builds, in the way of exp 0361's int0361.sh.
#   1. checks: no emulator, the shared binaries, the archive, the tree's patch, every file of the manifest
#   2. the lock, then copies of the outputs and of every file, then the kit's files over the sources
#   3. archive, normal, lean, mount; F414: the archive and the host go together. The backend's tests run if that tree built them
#   4. the tree's diff against f266548 must be the candidate patch 0001, index lines apart
# play-pkg.sh, input.cfg, the learned list and the saves are not touched. A failure after step 2 restores everything from the
# copies. No emulator, no GPU work. Copies and the undo are under ~/bc5-work/exp0388/integration/.
# usage: int0388j.sh   (on the box, in the slot, with box0388.sh, 0001-new.patch and kit/ beside it)
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0388; I=$E/integration; K=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd)
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
MB=$W/bc5-tools-ubuntu/release/bc5-mount; TOOLS=$HOME/src/bc5/tools; NEWHDR=src/bc5/job_push_wait.hpp
EXPECT_NORMAL=78f25172; EXPECT_LEAN=7b246487; EXPECT_ARCHIVE=3292bdaf; EXPECT_PATCH=476e1b3a; EXPECT_NEW=4e559f47; EXPECT_KIT=319dba66
m() { md5sum < "$1" | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color f266548 | grep -av '^index ' | md5sum | cut -c1-8; }
stop() { echo "int0388j STOP: $*"; exit 1; }
root_of() { case "$1" in H) echo "$K" ;; B) echo "$BS" ;; T) echo "$TOOLS" ;; esac; }
restore() {
    echo "restoring from $I"
    cp -p "$I/kyty_emulator.before-j" "$NB"; cp -p "$I/kyty_emulator-lean.before-j" "$LB"; cp -p "$I/libbc5_backend.a.before-j" "$ARCH"; cp -p "$I/bc5-mount.before-j" "$MB"
    while read -r r f old new; do
        t=$(root_of "$r")/$f
        if [ "$old" = - ]; then rm -f "$t"; else mkdir -p "$(dirname "$t")"; cp -p "$I/tree-before/$r/$f" "$t"; fi
    done < "$HERE/kit/manifest.txt"
    git -C "$K" rm -q --cached --ignore-unmatch "$NEWHDR" 2> /dev/null
    [ "$(m "$NB")" = "$EXPECT_NORMAL" ] && [ "$(m "$LB")" = "$EXPECT_LEAN" ] && [ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] && echo "outputs restored; the build directories' objects are the new ones: rebuild before the next change"
    bash "$HERE/box0388.sh" release
    exit 1
}
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
[ "$(m "$NB")" = "$EXPECT_NORMAL" ] && [ "$(m "$LB")" = "$EXPECT_LEAN" ] && [ "$(m "$ARCH")" = "$EXPECT_ARCHIVE" ] || stop "shared binaries or archive are not the pins: $(m "$NB") $(m "$LB") $(m "$ARCH")"
[ -f "$MB" ] || stop "no $MB"
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
bash "$HERE/box0388.sh" claim "exp 0388: J in, A and B out, all shared builds, CPU only" 60 || exit 1
mkdir -p "$I/tree-before" || stop "no $I"
echo "$(date '+%F %T') before: normal $(m "$NB"), lean $(m "$LB"), archive $(m "$ARCH"), mount $(m "$MB"), backend source $BS" | tee "$I/before.txt"
cp -p "$NB" "$I/kyty_emulator.before-j" && cp -p "$LB" "$I/kyty_emulator-lean.before-j" && cp -p "$ARCH" "$I/libbc5_backend.a.before-j" && cp -p "$MB" "$I/bc5-mount.before-j" || { bash "$HERE/box0388.sh" release; stop "output copy failed"; }
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
if [ -x "$W/backend-ubuntu/bc5_backend_tests" ]; then build backend-tests "cd '$W/backend-ubuntu' && nice -n 19 ./bc5_backend_tests"; else echo "the backend tree has no tests target: not run"; fi
build normal "cd '$W/kytyplus-build' && nice -n 19 ninja kyty_emulator"
build lean "cd '$W/kytyplus-build-lean' && nice -n 19 ninja kyty_emulator"
build mount "cd '$TOOLS' && CARGO_TARGET_DIR='$W/bc5-tools-ubuntu' nice -n 19 cargo build --release --locked -p bc5-mount"
NM=$(m "$NB"); LM=$(m "$LB"); AM=$(m "$ARCH")
[ "$NM" != "$EXPECT_NORMAL" ] && [ "$LM" != "$EXPECT_LEAN" ] && [ "$AM" != "$EXPECT_ARCHIVE" ] || { echo "an output did not change: $NM $LM $AM"; restore; }
[ "$(strings "$NB" | grep -c 'job push wait: pushes')" = 1 ] && [ "$(strings "$LB" | grep -c 'job push wait: pushes')" = 0 ] || { echo "the trace is not as it should be"; restore; }
for b in "$NB" "$LB"; do [ "$(strings "$b" | grep -c 'job push wait %s')" = 1 ] && [ "$(strings "$b" | grep -c 'KYTY_BC5_JOB_PUSH_WAIT')" -ge 1 ] && [ "$(strings "$b" | grep -c 'job-arena')" = 0 ] || { echo "$b lacks the wait or still has the fix"; restore; }; done
for b in "$NB" "$LB"; do echo "removed names still in $b: $(strings "$b" | grep -c -w -F -f "$HERE/kit/removed-names.txt")"; done
git -C "$K" add -N "$NEWHDR" || restore
[ "$(tdiff)" = "$(grep -av '^index ' "$HERE/0001-new.patch" | md5sum | cut -c1-8)" ] || { echo "the tree's diff is not the candidate patch 0001"; restore; }
echo "$(date '+%F %T') after: normal $NM, lean $LM, archive $AM, mount $(m "$MB"), warnings normal $(grep -c 'warning:' "$I/build-normal.out"), lean $(grep -c 'warning:' "$I/build-lean.out")" | tee "$I/after.txt"
echo "undo: the four outputs from $I/*.before-j, the files from $I/tree-before"
bash "$HERE/box0388.sh" release
