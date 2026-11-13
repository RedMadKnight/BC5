#!/usr/bin/env bash
# BC5 exp 0419, candidate E: patch 0001 27b6416f -> S_NEW AND the shared backend archive 75e30335 -> d4c4882e (exp
# 0412's two backend files). Made from the integration's swap script by mkswap0419e.py (through exp 0417's mkswap0417.py); see those files.
# NOT to be run on a general release: the top session puts this swap to the maintainer first.
# usage: S_NEW=<patch md5> S_PRIV_N=<private normal md5> S_PRIV_L=<private lean md5> int0419e.sh
# BC5 integration of 2026-11-13 (the maintainer through the top session: "jest zgoda na scalenie wszystkiego i twoje
# testy"): exp 0416 + 0415 + 0412, patch 0001 01abfc0c -> S_NEW (0001-new17.patch, tree17.md5), both shared builds.
# Made from exp 0413's second swap script by mkkit0416.py; the text below is that script's, with the pins, the patch
# names and the marks changed. usage: S_NEW=<patch md5> S_PRIV_N=<private normal md5> S_PRIV_L=<private lean md5> int0419e.sh
# BC5 exp 0413, the second swap (the maintainer, 2026-11-12: "przepisuj po kolei to co bylo zrobione u nas i merge do
# main"; D19; released by the top session after the private checks): the integration's patch 0001 (S_NEW, branch
# int/0413-tested-into-shared) into the shared host tree, and both shared emulators rebuilt in place.
#   1. checks: no emulator; the shared binaries, the archive and the tree's diff are the pins (the NP V2 swap's state);
#      the kit (0001-new14.patch 01abfc0c, 0001-new17.patch S_NEW, tree17.md5); exp 0372's route in the new patch
#   2. the lock; copies of both binaries under ~/bc5-work/exp0413/swap (*.before-0419), read back
#   3. the tree: 0001-old reversed, 0001-new14 applied, new files added to the index with intent-to-add, as the tree has them now; every patched file checked
#      against tree17.md5 and the tree's diff against the patch
#   4. normal and lean (ninja kyty_emulator, nice 19); the archive is not rebuilt and must stay the same
#   5. the binaries changed and carry the marks; the result line says whether they equal the private builds
# A failure after step 2 restores both binaries and the tree, and CHECKS the restore (Codex's review, point 2): each
# binary by md5, the tree by its diff. If the restore does not read back, the lock is KEPT and the state is printed.
# No emulator, no GPU work.
# usage (on the box, detached, beside the kit): S_NEW=<patch md5> S_PRIV_N=<private normal md5> S_PRIV_L=<private lean md5> int0419e.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0413; I=$E/swap; K=$HOME/src/KytyPlus; HERE=$(cd "$(dirname "$0")" && pwd)
LOCK=$W/BOX-LOCK; ID=$E/lock.line
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
PIN_NORMAL=51af1ed78e84291caf5ee042ea82c46d; PIN_LEAN=59894428d98ed94918d09a31002c1e3b; PIN_ARCHIVE=75e30335; PIN_OLD=27b6416f
PIN_ARCH_FULL=75e303357610fee8d1d205bdc88c031c; NEW_ARCHIVE=d4c4882e   # the archive before, in full; after, as the private build gave it
BSRC=$W/d19/export/backend; BBLD=$W/backend-ubuntu; H=$BSRC/include/bc5/direct.hpp; C=$BSRC/src/direct.cpp
H_OLD=a9fcb26b; C_OLD=51279eae; H_NEW=e96e5c73; C_NEW=28100ce5; ARCH_TOUCHED=0
: "${S_NEW:?the new patch md5}" "${S_PRIV_N:?}" "${S_PRIV_L:?}"
m() { md5sum < "$1" | cut -d' ' -f1; }
m8() { md5sum < "$1" | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8; }
stop() { echo "int0419e STOP: $*"; exit 1; }
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
    if own; then : > "$LOCK" && [ ! -s "$LOCK" ] && { rm -f "$ID"; echo "lock released"; return 0; }; echo "int0419e: the lock could not be released"; return 1; fi
    echo "int0419e: the lock is not ours, left as it is: $(cat "$LOCK" 2> /dev/null)"; return 1
}
TREE_TOUCHED=0
restore() {
    echo "int0419e: FAILED ($*); restoring from $I"
    local ok=1
    if [ "$ARCH_TOUCHED" = 1 ]; then   # exp 0417: the backend source and the archive first
        cp -p "$I/direct.hpp.before-0419" "$H" || ok=0; cp -p "$I/direct.cpp.before-0419" "$C" || ok=0
        cp -p "$I/libbc5_backend.a.before-0419" "$ARCH" || ok=0
        [ "$(m8 "$H")" = "$H_OLD" ] && [ "$(m8 "$C")" = "$C_OLD" ] || { echo "restore: the backend source reads $(m8 "$H") $(m8 "$C"), not $H_OLD $C_OLD"; ok=0; }
        [ "$(m "$ARCH")" = "$PIN_ARCH_FULL" ] || { echo "restore: the archive reads $(m "$ARCH"), not $PIN_ARCH_FULL"; ok=0; }
    fi
    cp -p "$I/kyty_emulator.before-0419" "$NB" || ok=0
    cp -p "$I/kyty_emulator-lean.before-0419" "$LB" || ok=0
    [ "$(m "$NB")" = "$PIN_NORMAL" ] || { echo "restore: the normal binary reads $(m "$NB"), not $PIN_NORMAL"; ok=0; }
    [ "$(m "$LB")" = "$PIN_LEAN" ] || { echo "restore: the lean binary reads $(m "$LB"), not $PIN_LEAN"; ok=0; }
    if [ "$TREE_TOUCHED" = 1 ]; then
        (cd "$K" && git reset -q && git apply -R --whitespace=nowarn "$HERE/0001-new17.patch" && git apply --whitespace=nowarn "$HERE/0001-new14.patch" && git add -N .) || { echo "restore: the tree could not be put back by the two patches"; ok=0; }
    fi
    [ "$(tdiff)" = "$PIN_OLD" ] || { echo "restore: the tree's diff reads $(tdiff), not $PIN_OLD"; ok=0; }
    [ "$(m8 "$ARCH")" = "$PIN_ARCHIVE" ] || { echo "restore: the archive reads $(m8 "$ARCH")"; ok=0; }
    if [ "$ok" = 1 ]; then
        echo "restored and read back: normal $PIN_NORMAL, lean $PIN_LEAN, tree $PIN_OLD; the build directories' objects are newer than the tree: rebuild before the next change"
        release
        exit 1
    fi
    echo "int0419e: THE RESTORE IS INCOMPLETE. The lock is KEPT: $(cat "$LOCK" 2> /dev/null)"
    echo "state: normal $(m "$NB"), lean $(m "$LB"), tree diff $(tdiff), archive $(m8 "$ARCH"); copies in $I/*.before-0419"
    exit 2
}
[ "${1:-}" = release ] && { release; exit $?; }
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
[ "$(m "$ARCH")" = "$PIN_ARCH_FULL" ] && [ "$(m8 "$H")" = "$H_OLD" ] && [ "$(m8 "$C")" = "$C_OLD" ] || stop "the shared archive or backend source is not the pins: $(m "$ARCH") $(m8 "$H") $(m8 "$C")"
[ "$(m8 "$HERE/backend-direct.hpp")" = "$H_NEW" ] && [ "$(m8 "$HERE/backend-direct.cpp")" = "$C_NEW" ] && [ -f "$BBLD/build.ninja" ] || stop "the kit's backend files are not $H_NEW / $C_NEW, or $BBLD has no build.ninja"
[ "$(m "$NB")" = "$PIN_NORMAL" ] && [ "$(m "$LB")" = "$PIN_LEAN" ] && [ "$(m8 "$ARCH")" = "$PIN_ARCHIVE" ] || stop "shared binaries or archive are not the pins: $(m "$NB") $(m "$LB") $(m8 "$ARCH")"
[ "$(tdiff)" = "$PIN_OLD" ] || stop "the tree's diff is not patch $PIN_OLD: $(tdiff)"
[ "$(m8 "$HERE/0001-new14.patch")" = "$PIN_OLD" ] && [ "$(m8 "$HERE/0001-new17.patch")" = "$S_NEW" ] && [ -s "$HERE/tree17.md5" ] || stop "the kit is not the pins"
[ "$(grep -c 'exp 0372' "$HERE/0001-new17.patch")" = 5 ] && grep -q '^+++ b/src/bc5/pad_audio_route.hpp' "$HERE/0001-new17.patch" || stop "the new patch lacks exp 0372's route"
[ "$(m "$E/p/build-normal/src/kyty_emulator")" = "$S_PRIV_N" ] && [ "$(m "$E/p/build-lean/src/kyty_emulator")" = "$S_PRIV_L" ] || stop "the private builds are not the checked ones"
(cd "$K" && git apply -R --check --whitespace=nowarn "$HERE/0001-new14.patch") || stop "0001-old does not reverse on the shared tree"
claim "exp 0419 candidate E: patch 0001 $S_NEW and the backend archive into the shared builds, CPU only" 45
mkdir -p "$I" || { release; stop "no $I"; }
echo "$(date '+%F %T') before: normal $(m "$NB"), lean $(m "$LB"), archive $(m8 "$ARCH"), tree diff $(tdiff)" | tee "$I/before-0419.txt"
cp -p "$NB" "$I/kyty_emulator.before-0419" && cp -p "$LB" "$I/kyty_emulator-lean.before-0419" || { release; stop "copy failed"; }
# exp 0417: the archive (twice: in the swap directory and beside itself) and the two backend source files
cp -p "$ARCH" "$I/libbc5_backend.a.before-0419" && cp -p "$ARCH" "$ARCH.before-0419" && cp -p "$H" "$I/direct.hpp.before-0419" && cp -p "$C" "$I/direct.cpp.before-0419" || { release; stop "copying the archive or the backend source failed"; }
[ "$(m "$I/libbc5_backend.a.before-0419")" = "$PIN_ARCH_FULL" ] && [ "$(m "$ARCH.before-0419")" = "$PIN_ARCH_FULL" ] && [ "$(m8 "$I/direct.hpp.before-0419")" = "$H_OLD" ] && [ "$(m8 "$I/direct.cpp.before-0419")" = "$C_OLD" ] || { release; stop "the archive or source copies do not read back"; }
[ "$(m "$I/kyty_emulator.before-0419")" = "$PIN_NORMAL" ] && [ "$(m "$I/kyty_emulator-lean.before-0419")" = "$PIN_LEAN" ] || { release; stop "the copies do not read back"; }
TREE_TOUCHED=1
(cd "$K" && git apply -R --whitespace=nowarn "$HERE/0001-new14.patch" && git apply --whitespace=nowarn "$HERE/0001-new17.patch" && git add -N .) || restore "applying the patch"
bad=0
while read -r sum f; do [ "$(md5sum < "$K/$f" | cut -d' ' -f1)" = "$sum" ] || { echo "differs: $f"; bad=$((bad + 1)); }; done < "$HERE/tree17.md5"
[ "$bad" = 0 ] || restore "$bad files differ from the laptop's tree"
[ "$(tdiff)" = "$S_NEW" ] || restore "the tree's diff is $(tdiff), not $S_NEW"
echo "tree: $(wc -l < "$HERE/tree17.md5") patched files match; diff $S_NEW"
build() {  # name, build directory
    pgrep '^kyty_emulator' > /dev/null && restore "an emulator started before $1"
    echo "== $(date +%T) $1"
    distrobox enter ubuntu -- sh -c "cd '$2' && nice -n 19 ninja kyty_emulator" < /dev/null > "$I/build-$1-0419.out" 2>&1 || { grep -m5 "error:" "$I/build-$1-0419.out"; restore "build $1"; }
}
# exp 0417: the backend first. The two files, then the archive in its own build directory.
ARCH_TOUCHED=1
cp "$HERE/backend-direct.hpp" "$H" && cp "$HERE/backend-direct.cpp" "$C" || restore "putting the backend files in"
[ "$(m8 "$H")" = "$H_NEW" ] && [ "$(m8 "$C")" = "$C_NEW" ] || restore "the backend files do not read back"
pgrep '^kyty_emulator' > /dev/null && restore "an emulator started before the backend build"
echo "== $(date +%T) backend"
distrobox enter ubuntu -- sh -c "cd '$BBLD' && nice -n 19 ninja" < /dev/null > "$I/build-backend-0419.out" 2>&1 || { grep -m5 "error:" "$I/build-backend-0419.out"; restore "the backend build"; }
[ "$(m8 "$ARCH")" = "$NEW_ARCHIVE" ] || restore "the rebuilt archive is $(m8 "$ARCH"), not $NEW_ARCHIVE (the private build's)"
echo "backend archive: $(m "$ARCH") (was $PIN_ARCH_FULL, kept as $ARCH.before-0419)"
build normal "$W/kytyplus-build"
build lean "$W/kytyplus-build-lean"
NM=$(m "$NB"); LM=$(m "$LB")
[ "$NM" != "$PIN_NORMAL" ] && [ "$LM" != "$PIN_LEAN" ] || restore "a binary did not change: $NM $LM"
[ "$(m8 "$ARCH")" = "$NEW_ARCHIVE" ] || restore "the archive changed during the emulator builds"
for b in "$NB" "$LB"; do
    for s in "NpCppWebApi SessionManager V2 on (10 exports registered)" KYTY_BC5_SWITCH_DEFAULTS KYTY_BC5_AMM_SETBUFFER_GUARD KYTY_BC5_AMM_SETBUFFER_MAP KYTY_BC5_EVENT_COALESCE_SAME KYTY_BC5_SEMA_TARGETED_WAKE KYTY_BC5_EVENT_PENDING_CAP KYTY_BC5_RANGES_FAST KYTY_BC5_PHYSMAP_SORTED KYTY_BC5_FW_NET KYTY_BC5_APR_POSIX KYTY_BC5_ANON_SYNC BC5_DIRECT_HEAP_GUARDS BC5_GUARD_K1R BC5_GUARD_K1_FILTER BC5_FAULT_RECORD BC5_R3_EOP_STAT KYTY_BC5_TITLE_DEFAULTS KYTY_BC5_SAVEDATA_TRANSFER_FIX BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG BC5_GUARD_LEARN_LOG KYTY_BC5_MAP_RECORDS; do
        grep -aqF -- "$s" "$b" || restore "$b lacks [$s]"
    done
done
[ "$(tdiff)" = "$S_NEW" ] || restore "the tree's diff changed during the build"
same="DIFFERENT from the private builds (normal $S_PRIV_N, lean $S_PRIV_L)"
[ "$NM" = "$S_PRIV_N" ] && [ "$LM" = "$S_PRIV_L" ] && same="byte-identical to the private builds"
echo "$(date '+%F %T') after: normal $NM, lean $LM, archive $(m8 "$ARCH"), tree diff $S_NEW; $same" | tee "$I/after-0419.txt"
echo "undo: the archive from $ARCH.before-0419 and the two backend files from $I/direct.*.before-0419, both binaries from $I/*.before-0419, the tree by reversing 0001-new17 and applying 0001-new14 (then rebuild the backend and both emulators); this script touches no launcher"
release
