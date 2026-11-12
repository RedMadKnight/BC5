#!/usr/bin/env bash
# BC5 exp 0413, the second swap (the maintainer, 2026-11-12: "przepisuj po kolei to co bylo zrobione u nas i merge do
# main"; D19; released by the top session after the private checks): the integration's patch 0001 (S_NEW, branch
# int/0413-tested-into-shared) into the shared host tree, and both shared emulators rebuilt in place.
#   1. checks: no emulator; the shared binaries, the archive and the tree's diff are the pins (the NP V2 swap's state);
#      the kit (0001-old.patch 2dbed49a, 0001-new7.patch S_NEW, tree7.md5); exp 0372's route in the new patch
#   2. the lock; copies of both binaries under ~/bc5-work/exp0413/swap (*.before-0413b), read back
#   3. the tree: 0001-old reversed, 0001-new7 applied, new files added to the index with intent-to-add, as the tree has them now; every patched file checked
#      against tree7.md5 and the tree's diff against the patch
#   4. normal and lean (ninja kyty_emulator, nice 19); the archive is not rebuilt and must stay the same
#   5. the binaries changed and carry the marks; the result line says whether they equal the private builds
# A failure after step 2 restores both binaries and the tree, and CHECKS the restore (Codex's review, point 2): each
# binary by md5, the tree by its diff. If the restore does not read back, the lock is KEPT and the state is printed.
# No emulator, no GPU work.
# usage (on the box, detached, beside the kit): S_NEW=<patch md5> S_PRIV_N=<private normal md5> S_PRIV_L=<private lean md5> int0413b.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0413; I=$E/swap; K=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd)
LOCK=$W/BOX-LOCK; ID=$E/lock.line
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
PIN_NORMAL=f6445dc6b37634ddd06366bb4b30753b; PIN_LEAN=30ee854b1dff4ae436720ab78f7ba229; PIN_ARCHIVE=75e30335; PIN_OLD=2dbed49a
: "${S_NEW:?the new patch md5}" "${S_PRIV_N:?}" "${S_PRIV_L:?}"
m() { md5sum < "$1" | cut -d' ' -f1; }
m8() { md5sum < "$1" | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8; }
stop() { echo "int0413b STOP: $*"; exit 1; }
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
    if own; then : > "$LOCK" && [ ! -s "$LOCK" ] && { rm -f "$ID"; echo "lock released"; return 0; }; echo "int0413b: the lock could not be released"; return 1; fi
    echo "int0413b: the lock is not ours, left as it is: $(cat "$LOCK" 2> /dev/null)"; return 1
}
TREE_TOUCHED=0
restore() {
    echo "int0413b: FAILED ($*); restoring from $I"
    local ok=1
    cp -p "$I/kyty_emulator.before-0413b" "$NB" || ok=0
    cp -p "$I/kyty_emulator-lean.before-0413b" "$LB" || ok=0
    [ "$(m "$NB")" = "$PIN_NORMAL" ] || { echo "restore: the normal binary reads $(m "$NB"), not $PIN_NORMAL"; ok=0; }
    [ "$(m "$LB")" = "$PIN_LEAN" ] || { echo "restore: the lean binary reads $(m "$LB"), not $PIN_LEAN"; ok=0; }
    if [ "$TREE_TOUCHED" = 1 ]; then
        (cd "$K" && git reset -q && git apply -R --whitespace=nowarn "$HERE/0001-new7.patch" && git apply --whitespace=nowarn "$HERE/0001-old.patch" && git add -N .) || { echo "restore: the tree could not be put back by the two patches"; ok=0; }
    fi
    [ "$(tdiff)" = "$PIN_OLD" ] || { echo "restore: the tree's diff reads $(tdiff), not $PIN_OLD"; ok=0; }
    [ "$(m8 "$ARCH")" = "$PIN_ARCHIVE" ] || { echo "restore: the archive reads $(m8 "$ARCH")"; ok=0; }
    if [ "$ok" = 1 ]; then
        echo "restored and read back: normal $PIN_NORMAL, lean $PIN_LEAN, tree $PIN_OLD; the build directories' objects are newer than the tree: rebuild before the next change"
        release
        exit 1
    fi
    echo "int0413b: THE RESTORE IS INCOMPLETE. The lock is KEPT: $(cat "$LOCK" 2> /dev/null)"
    echo "state: normal $(m "$NB"), lean $(m "$LB"), tree diff $(tdiff), archive $(m8 "$ARCH"); copies in $I/*.before-0413b"
    exit 2
}
[ "${1:-}" = release ] && { release; exit $?; }
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
[ "$(m "$NB")" = "$PIN_NORMAL" ] && [ "$(m "$LB")" = "$PIN_LEAN" ] && [ "$(m8 "$ARCH")" = "$PIN_ARCHIVE" ] || stop "shared binaries or archive are not the pins: $(m "$NB") $(m "$LB") $(m8 "$ARCH")"
[ "$(tdiff)" = "$PIN_OLD" ] || stop "the tree's diff is not patch $PIN_OLD: $(tdiff)"
[ "$(m8 "$HERE/0001-old.patch")" = "$PIN_OLD" ] && [ "$(m8 "$HERE/0001-new7.patch")" = "$S_NEW" ] && [ -s "$HERE/tree7.md5" ] || stop "the kit is not the pins"
[ "$(grep -c 'exp 0372' "$HERE/0001-new7.patch")" = 5 ] && grep -q '^+++ b/src/bc5/pad_audio_route.hpp' "$HERE/0001-new7.patch" || stop "the new patch lacks exp 0372's route"
[ "$(m "$E/p/build-normal/src/kyty_emulator")" = "$S_PRIV_N" ] && [ "$(m "$E/p/build-lean/src/kyty_emulator")" = "$S_PRIV_L" ] || stop "the private builds are not the checked ones"
(cd "$K" && git apply -R --check --whitespace=nowarn "$HERE/0001-old.patch") || stop "0001-old does not reverse on the shared tree"
claim "exp 0413: the integration's patch 0001 $S_NEW into normal and lean, CPU only" 40
mkdir -p "$I" || { release; stop "no $I"; }
echo "$(date '+%F %T') before: normal $(m "$NB"), lean $(m "$LB"), archive $(m8 "$ARCH"), tree diff $(tdiff)" | tee "$I/before-0413b.txt"
cp -p "$NB" "$I/kyty_emulator.before-0413b" && cp -p "$LB" "$I/kyty_emulator-lean.before-0413b" || { release; stop "copy failed"; }
[ "$(m "$I/kyty_emulator.before-0413b")" = "$PIN_NORMAL" ] && [ "$(m "$I/kyty_emulator-lean.before-0413b")" = "$PIN_LEAN" ] || { release; stop "the copies do not read back"; }
TREE_TOUCHED=1
(cd "$K" && git apply -R --whitespace=nowarn "$HERE/0001-old.patch" && git apply --whitespace=nowarn "$HERE/0001-new7.patch" && git add -N .) || restore "applying the patch"
bad=0
while read -r sum f; do [ "$(md5sum < "$K/$f" | cut -d' ' -f1)" = "$sum" ] || { echo "differs: $f"; bad=$((bad + 1)); }; done < "$HERE/tree7.md5"
[ "$bad" = 0 ] || restore "$bad files differ from the laptop's tree"
[ "$(tdiff)" = "$S_NEW" ] || restore "the tree's diff is $(tdiff), not $S_NEW"
echo "tree: $(wc -l < "$HERE/tree7.md5") patched files match; diff $S_NEW"
build() {  # name, build directory
    pgrep '^kyty_emulator' > /dev/null && restore "an emulator started before $1"
    echo "== $(date +%T) $1"
    distrobox enter ubuntu -- sh -c "cd '$2' && nice -n 19 ninja kyty_emulator" < /dev/null > "$I/build-$1-0413b.out" 2>&1 || { grep -m5 "error:" "$I/build-$1-0413b.out"; restore "build $1"; }
}
build normal "$W/kytyplus-build"
build lean "$W/kytyplus-build-lean"
NM=$(m "$NB"); LM=$(m "$LB")
[ "$NM" != "$PIN_NORMAL" ] && [ "$LM" != "$PIN_LEAN" ] || restore "a binary did not change: $NM $LM"
[ "$(m8 "$ARCH")" = "$PIN_ARCHIVE" ] || restore "the archive changed"
for b in "$NB" "$LB"; do
    for s in "NpCppWebApi SessionManager V2 on (10 exports registered)" KYTY_BC5_SWITCH_DEFAULTS KYTY_BC5_AMM_SETBUFFER_GUARD KYTY_BC5_EVENT_PENDING_CAP KYTY_BC5_RANGES_FAST KYTY_BC5_PHYSMAP_SORTED KYTY_BC5_FW_NET; do
        grep -aqF -- "$s" "$b" || restore "$b lacks [$s]"
    done
done
[ "$(tdiff)" = "$S_NEW" ] || restore "the tree's diff changed during the build"
same="DIFFERENT from the private builds (normal $S_PRIV_N, lean $S_PRIV_L)"
[ "$NM" = "$S_PRIV_N" ] && [ "$LM" = "$S_PRIV_L" ] && same="byte-identical to the private builds"
echo "$(date '+%F %T') after: normal $NM, lean $LM, archive $(m8 "$ARCH"), tree diff $S_NEW; $same" | tee "$I/after-0413b.txt"
echo "undo: both binaries from $I/*.before-0413b, the tree by reversing 0001-new7 and applying 0001-old (then rebuild)"
release
