#!/usr/bin/env bash
# BC5 exp 0413, the swap (the maintainer, 2026-11-12: "tak przenies i zbuduj"; D19): exp 0401 series e's NpCppWebApi
# SessionManager V2 (the ten NIDs, mknp0413.py) into the host tree, on by default, and both shared emulators rebuilt.
# One host file changes (src/libs/libNpCppWebApi.cpp); the backend, the archive, the launchers and the mount do not.
#   1. checks: no emulator, the shared binaries and archive are pins0413.env's, the tree's diff is main's patch 0001,
#      the unit is exp 0328's, the kit and the candidate are the pins, exp 0372 in the candidate
#   2. the lock (hard link, as coordination/d19/d19box.sh), copies of both binaries and of the unit, the kit's unit in
#   3. normal and lean (ninja kyty_emulator, nice 19); the archive is not rebuilt and must stay the same
#   4. both binaries carry the new on/off lines and the ten NIDs; the tree's diff is the candidate, index lines apart
# A failure after step 2 restores the unit and both binaries. No emulator, no GPU work. Copies under
# ~/bc5-work/exp0413/swap/.
# usage: int0413.sh   (on the box, in the slot, with pins0413.env, 0001-new.patch and libNpCppWebApi.cpp beside it)
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0413; I=$E/swap; K=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd)
LOCK=$W/BOX-LOCK; ID=$E/lock.line; UNIT=src/libs/libNpCppWebApi.cpp
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
. "$HERE/pins0413.env" || { echo "int0413 STOP: no pins0413.env"; exit 1; }
m() { md5sum < "$1" | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color f266548 | grep -av '^index ' | md5sum | cut -c1-8; }
stop() { echo "int0413 STOP: $*"; exit 1; }
own() { [ -s "$ID" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$(cat "$ID")" ]; }
claim() {
    local c=$LOCK.d19-claim t=$LOCK.0413-$$.new a=$LOCK.0413-$$.aside line
    pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
    mkdir -p "$E" || stop "cannot make $E"
    line="exp 0413 | token $(date +%s)$$ | $1, no emulator, until $(date -d +"$2"min +%H:%M) | $(date '+%F %T')"
    mkdir "$c" 2> /dev/null || stop "another claim runs, or $c was left behind"
    fail() { rm -f "$t"; rmdir "$c"; stop "$1"; }
    printf '%s\n' "$line" > "$t" || fail "cannot write $t"
    if [ -e "$LOCK" ] || [ -L "$LOCK" ]; then
        { [ -L "$LOCK" ] || [ ! -f "$LOCK" ]; } && fail "$LOCK is not a plain file"
        [ -s "$LOCK" ] && fail "foreign lock: $(cat "$LOCK")"
        mv -T "$LOCK" "$a" || fail "the lock moved under us"
    fi
    if ! ln "$t" "$LOCK" 2> /dev/null; then
        [ -s "$a" ] || rm -f "$a"
        fail "lost the claim to: $(cat "$LOCK" 2> /dev/null)"
    fi
    if [ -s "$a" ]; then
        local w; w=$(cat "$a"); mv -fT "$a" "$LOCK"; fail "a foreign lock arrived during the claim: $w"
    fi
    rm -f "$a" "$t"; rmdir "$c" || stop "cannot remove $c"
    printf '%s\n' "$line" > "$ID" || stop "cannot record the line; the lock is held: $line"
    own || stop "the lock does not read back as ours"
    echo "claimed: $line"
}
release() {
    if own; then : > "$LOCK" && [ ! -s "$LOCK" ] && { rm -f "$ID"; echo "lock released"; return 0; }; echo "int0413: the lock could not be released"; return 1; fi
    echo "int0413: the lock is not ours, left as it is: $(cat "$LOCK" 2> /dev/null)"; return 1
}
restore() {
    echo "restoring from $I"
    cp -p "$I/kyty_emulator.before-0413" "$NB"; cp -p "$I/kyty_emulator-lean.before-0413" "$LB"; cp -p "$I/libNpCppWebApi.cpp.before-0413" "$K/$UNIT"
    [ "$(m "$NB")" = "$PIN_NORMAL" ] && [ "$(m "$LB")" = "$PIN_LEAN" ] && [ "$(m "$K/$UNIT")" = "$PIN_UNIT_OLD" ] && echo "binaries and the unit restored; the build directories' objects are the new ones: rebuild before the next change"
    release
    exit 1
}
[ "${1:-}" = release ] && { release; exit $?; }
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
[ "$(m "$NB")" = "$PIN_NORMAL" ] && [ "$(m "$LB")" = "$PIN_LEAN" ] && [ "$(m "$ARCH")" = "$PIN_ARCHIVE" ] || stop "shared binaries or archive are not the pins: $(m "$NB") $(m "$LB") $(m "$ARCH")"
[ "$(tdiff)" = "$PIN_TREE_DIFF" ] || stop "the tree's diff is not main's patch 0001: $(tdiff)"
[ "$(m "$K/$UNIT")" = "$PIN_UNIT_OLD" ] || stop "the tree's unit is $(m "$K/$UNIT"), not exp 0328's"
[ "$(m "$HERE/libNpCppWebApi.cpp")" = "$PIN_UNIT_NEW" ] && [ "$(m "$HERE/0001-new.patch")" = "$PIN_PATCH_NEW" ] || stop "the kit is not the pins"
[ "$(grep -c 'exp 0372' "$HERE/0001-new.patch")" = 5 ] && grep -q '^+++ b/src/bc5/pad_audio_route.hpp' "$HERE/0001-new.patch" || stop "the candidate patch lacks exp 0372's route"
claim "exp 0413: NpCppWebApi V2 into normal and lean, CPU only" 30
mkdir -p "$I" || { release; stop "no $I"; }
echo "$(date '+%F %T') before: normal $(m "$NB"), lean $(m "$LB"), archive $(m "$ARCH"), unit $(m "$K/$UNIT")" | tee "$I/before.txt"
cp -p "$NB" "$I/kyty_emulator.before-0413" && cp -p "$LB" "$I/kyty_emulator-lean.before-0413" && cp -p "$K/$UNIT" "$I/libNpCppWebApi.cpp.before-0413" || { release; stop "copy failed"; }
[ "$(m "$I/kyty_emulator.before-0413")" = "$PIN_NORMAL" ] && [ "$(m "$I/kyty_emulator-lean.before-0413")" = "$PIN_LEAN" ] && [ "$(m "$I/libNpCppWebApi.cpp.before-0413")" = "$PIN_UNIT_OLD" ] || { release; stop "the copies do not read back"; }
cp "$HERE/libNpCppWebApi.cpp" "$K/$UNIT" || restore
build() {  # name, build directory
    echo "== $(date +%T) $1"
    distrobox enter ubuntu -- sh -c "cd '$2' && nice -n 19 ninja kyty_emulator" > "$I/build-$1.out" 2>&1 || { tail -20 "$I/build-$1.out"; restore; }
}
build normal "$W/kytyplus-build"
build lean "$W/kytyplus-build-lean"
NM=$(m "$NB"); LM=$(m "$LB"); AM=$(m "$ARCH")
[ "$NM" != "$PIN_NORMAL" ] && [ "$LM" != "$PIN_LEAN" ] || { echo "a binary did not change: $NM $LM"; restore; }
[ "$AM" = "$PIN_ARCHIVE" ] || { echo "the archive changed: $AM"; restore; }
for b in "$NB" "$LB"; do
    [ "$(strings "$b" | grep -c 'NpCppWebApi SessionManager V2 on (10 exports registered)')" = 1 ] || { echo "$b lacks the on line"; restore; }
    for n in eVU3cXIJz0w BY1jyWLZrcA JiY4sfHkV34 LbhH9NeB93I XuVY56j7GM0 fIzsqjyD5oY sRn6qePT54Q -0Vv7HKZaBM yl3T9brJay4 xjVhrq2KPJA; do
        strings "$b" | grep -qx -- "$n" || { echo "$b lacks the NID $n"; restore; }
    done
done
[ "$(tdiff)" = "$(grep -av '^index ' "$HERE/0001-new.patch" | md5sum | cut -c1-8)" ] || { echo "the tree's diff is not the candidate patch 0001"; restore; }
echo "$(date '+%F %T') after: normal $NM, lean $LM, archive $AM, warnings normal $(grep -c 'warning:' "$I/build-normal.out"), lean $(grep -c 'warning:' "$I/build-lean.out")" | tee "$I/after.txt"
echo "undo: both binaries and the unit from $I/*.before-0413 (then rebuild before the next change)"
release
