#!/usr/bin/env bash
# BC5 exp 0438 (tag bake438b), the shared swap of A1 + A1b + A1P, A2 and the acb gate (BC5_0438_INFLIGHT_NG, BC5_0438_OPEN_NG;
# no Q438, no labelmap): every switch kept, on unless "0". swap0438o.sh's shape with two more host files and the backend:
#   host (the KytyPlus tree, patch 0fede35d): 0004-bc5-0438-bake438b.patch on src/libs/bc5LleAgc.cpp (2e6168de) and
#        src/kernel/memory.cpp (aa7d7f5b); src/bc5/switch_defaults.hpp stays 48ae1cd6 (checked); the patch's file list
#        is unchanged (both files are in patch 0001 already)
#   backend (the shared source $B = ~/bc5-work/d19/export/backend, built in ~/bc5-work/backend-ubuntu): 0004-backend-0438-
#        bake438b.patch on src/direct.cpp (eacf8d2a), include/bc5/direct.hpp (9256f3b9) and a new include/bc5/mapping_index.hpp
#        (A2's compare-only check is under #if defined(BC5_0438_A2_CHECK_BUILD), not defined here: not in the archive);
#        the archive d6638808 is rebuilt by ninja in backend-ubuntu, then both emulators (they include $B/include and
#        link the archive by its path)
#   1. checks: no emulator; the kit (pins438b.inc from mkbake438b.py); the tree's diff is 0fede35d, its three files the
#      pinned ones; the backend source's two files the pinned ones and no mapping_index.hpp; both CMake caches point at
#      $B and backend-ubuntu; normal 199a0f39, lean 3a20b974, archive d6638808; both patches apply (git apply --check)
#   2. the lock (chain_claim, one line); copies under $X (*.before-0438b: both binaries, the archive, the host files, the
#      backend files, the old patch); pins
#   3. the host patch applied, its files must be the kit's; the new patch = git diff f266548 must be PATCH_NEW; exp 0372 = 5,
#      the pad_audio_route header in, the same file list, the guard / learned / JOB_ARENA line counts as before, no Q438 or
#      labelmap text, the gate's, A1's and A1P's text in; the backend patch applied, its files the
#      kit's. DRY=1 (on COPIES: INT_K=<copy of ~/src/KytyPlus>, INT_B=<copy of the backend source>, X=<scratch>): stops
#      here, prints the new patch's md5, undoes
#   4. the archive rebuilt (ninja bc5_backend in backend-ubuntu), then normal and lean (ninja kyty_emulator), nice 19
#   5. the archive changed and holds BC5_DIRECT_0438_A2; the archive and both binaries hold no BC5_DIRECT_0438_A2_CHECK
#      and no "tag a2c438" line; strings: exactly the new words gained, none lost (listed below); normal holds the ng438,
#      wd438 and a1c438 lines, lean holds none of them and no KYTY_BC5_0438_A1J (the normal-only diagnostics compiled out)
# Any failure after step 2 runs undo0438b.sh (everything back to 0fede35d / 199a0f39 / 3a20b974 / d6638808, by md5).
# usage (on the box, in the kit directory): PATCH_NEW=<md5 from the dry run> bash swap0438b.sh
#                                           DRY=1 INT_K=<copy> INT_B=<copy> X=<scratch> bash swap0438b.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=${INT_W:-$HOME/bc5-work}; N=$W/exp0413/n; K=${INT_K:-$HOME/src/KytyPlus}; B=${INT_B:-$W/d19/export/backend}; BB=$W/backend-ubuntu
HERE=$(cd "$(dirname "$0")" && pwd); X=${X:-$W/exp0438/swapb}
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$BB/libbc5_backend.a
PIN_OLD=0fede35d; NORMAL_OLD=199a0f39; LEAN_OLD=3a20b974; ARCH_OLD=d6638808
DRY=${DRY:-0}; PATCH_NEW=${PATCH_NEW:-}
KP=0004-bc5-0438-bake438b.patch; BP=0004-backend-0438-bake438b.patch
UNITS="src/libs/bc5LleAgc.cpp src/kernel/memory.cpp"; BEFILES="src/direct.cpp include/bc5/direct.hpp"; BENEW=include/bc5/mapping_index.hpp
# the switch words the swap adds (strings of each binary; the archive's BC5_DIRECT_0438_A2 is in both, A1J is normal-only)
WORDS_NORMAL="BC5_0438_INFLIGHT_NG BC5_0438_OPEN_NG BC5_DIRECT_0438_A2 KYTY_BC5_0438_A1 KYTY_BC5_0438_A1J KYTY_BC5_0438_A1P"
WORDS_LEAN="BC5_0438_INFLIGHT_NG BC5_0438_OPEN_NG BC5_DIRECT_0438_A2 KYTY_BC5_0438_A1 KYTY_BC5_0438_A1P"
m8() { md5sum < "$1" | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8; }
stop() { echo "swap0438b STOP: $*"; exit 1; }
undo() { echo "swap0438b: FAILED: $*; undoing"; UNDO_IN_INT=1 X=$X UNDO_W=$W UNDO_K=$K UNDO_B=$B UNDO_DRY=$DRY bash "$HERE/undo0438b.sh"; exit 1; }
words() { nice -n 19 strings "$1" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u; }
bapply() { (cd "$B" && GIT_CEILING_DIRECTORIES=$(dirname "$B") git apply "$@" "$HERE/$BP"); } # outside any repository: paths from $B
# 1
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
for f in $KP $BP pins438b.inc undo0438b.sh; do [ -s "$HERE/$f" ] || stop "kit: $f missing"; done
KIT_PATCH=; KIT_BE_PATCH=; UNIT_OLD=; UNIT_NEW=; MEM_OLD=; MEM_NEW=; SWD=; BE_CPP_OLD=; BE_CPP_NEW=; BE_HPP_OLD=; BE_HPP_NEW=; BE_MI_NEW=
. "$HERE/pins438b.inc"
[ -n "$KIT_PATCH" ] && [ -n "$KIT_BE_PATCH" ] && [ -n "$UNIT_NEW" ] && [ -n "$MEM_NEW" ] && [ "$SWD" = 48ae1cd6 ] && [ -n "$BE_CPP_NEW" ] && [ -n "$BE_HPP_NEW" ] && [ -n "$BE_MI_NEW" ] || stop "kit: pins438b.inc is incomplete"
[ "$UNIT_OLD" = 2e6168de ] && [ "$MEM_OLD" = aa7d7f5b ] && [ "$BE_CPP_OLD" = eacf8d2a ] && [ "$BE_HPP_OLD" = 9256f3b9 ] || stop "kit: pins438b.inc has other old pins"
[ "$(m8 "$HERE/$KP")" = "$KIT_PATCH" ] || stop "kit: $KP is $(m8 "$HERE/$KP"), not $KIT_PATCH"
[ "$(m8 "$HERE/$BP")" = "$KIT_BE_PATCH" ] || stop "kit: $BP is $(m8 "$HERE/$BP"), not $KIT_BE_PATCH"
[ "$DRY" = 1 ] || [ -n "$PATCH_NEW" ] || stop "PATCH_NEW is not given (take it from the dry run)"
if [ "$DRY" = 1 ]; then
    [ "$K" = "$HOME/src/KytyPlus" ] && stop "DRY=1 runs on a copy of the tree only (INT_K)"
    [ "$B" = "$W/d19/export/backend" ] && stop "DRY=1 runs on a copy of the backend source only (INT_B)"
    [ "$X" = "$W/exp0438/swapb" ] && stop "DRY=1 keeps its copies apart (X)"
fi
[ -e "$B/.git" ] && stop "$B is a git checkout: the backend patch is applied outside a repository only"
[ "$(tdiff)" = "$PIN_OLD" ] || stop "the tree's diff is $(tdiff), not $PIN_OLD"
for p in "src/libs/bc5LleAgc.cpp:$UNIT_OLD" "src/kernel/memory.cpp:$MEM_OLD" "src/bc5/switch_defaults.hpp:$SWD"; do
    [ "$(m8 "$K/${p%%:*}")" = "${p##*:}" ] || stop "the tree's ${p%%:*} is $(m8 "$K/${p%%:*}"), not ${p##*:}"
done
[ "$(m8 "$B/src/direct.cpp")" = "$BE_CPP_OLD" ] && [ "$(m8 "$B/include/bc5/direct.hpp")" = "$BE_HPP_OLD" ] || stop "the backend source is not eacf8d2a / 9256f3b9"
[ -e "$B/$BENEW" ] && stop "the backend source already has $BENEW"
cache() { sed -n "s/^$2:[A-Z]*=//p" "$1/CMakeCache.txt" | head -1; }
same() { [ -n "$1" ] && [ "$(realpath -m "$1")" = "$(realpath -m "$2")" ]; }  # /home vs /var/home on Bazzite
same "$(cache "$BB" CMAKE_HOME_DIRECTORY)" "$W/d19/export/backend" || stop "backend-ubuntu is not built from $W/d19/export/backend ($(cache "$BB" CMAKE_HOME_DIRECTORY))"
for d in kytyplus-build kytyplus-build-lean; do
    same "$(cache "$W/$d" KYTY_BC5_BACKEND_SRC)" "$W/d19/export/backend" && same "$(cache "$W/$d" KYTY_BC5_BACKEND_BUILD)" "$BB" \
        || stop "$d does not read the backend from $W/d19/export/backend and $BB ($(cache "$W/$d" KYTY_BC5_BACKEND_SRC), $(cache "$W/$d" KYTY_BC5_BACKEND_BUILD))"
done
[ "$(m8 "$NB")" = "$NORMAL_OLD" ] || stop "normal is $(m8 "$NB"), not $NORMAL_OLD"
[ "$(m8 "$LB")" = "$LEAN_OLD" ] || stop "lean is $(m8 "$LB"), not $LEAN_OLD"
[ "$(m8 "$ARCH")" = "$ARCH_OLD" ] || stop "the archive is $(m8 "$ARCH"), not $ARCH_OLD"
(cd "$K" && git apply --check "$HERE/$KP") || stop "the host patch does not apply to the tree"
bapply --check || stop "the backend patch does not apply to $B"
# 2
if [ "$DRY" != 1 ]; then
    if [ -n "${CHAIN_LOCKLINE:-}" ] && [ "$(cat "$W/BOX-LOCK" 2> /dev/null)" = "$CHAIN_LOCKLINE" ]; then  # run-swap0438b.sh holds the one line
        . "$N/chainlock0417.inc"; chain_release() { :; }; echo "the lock line of the caller is taken over: $CHAIN_LOCKLINE"
    else
        . "$N/chainlock0417.inc"
        chain_claim "exp 0438: shared swap, bake438b (A1+A1P, A2, the acb gate), patch $PIN_OLD -> $PATCH_NEW; archive, normal and lean rebuilt (CPU only, no emulator)" 60 || stop "no lock"
        trap chain_release EXIT
    fi
fi
[ -e "$X/pins.before-0438b" ] && stop "$X already holds a swap's copies: undo or move them first"
mkdir -p "$X/units" "$X/be" || stop "cannot make $X"
if [ "$DRY" != 1 ]; then
    cp -p "$NB" "$X/kyty_emulator.normal.before-0438b" && cp -p "$LB" "$X/kyty_emulator.lean.before-0438b" && cp -p "$ARCH" "$X/libbc5_backend.a.before-0438b" \
        || stop "cannot copy the binaries or the archive"
fi
for u in $UNITS; do mkdir -p "$X/units/$(dirname "$u")" && cp -p "$K/$u" "$X/units/$u" || stop "cannot copy $u"; done
for u in $BEFILES; do mkdir -p "$X/be/$(dirname "$u")" && cp -p "$B/$u" "$X/be/$u" || stop "cannot copy $u"; done
git -C "$K" diff --no-color f266548 > "$X/0001.before-0438b.patch" || stop "cannot save the patch"
# shellcheck disable=SC2086
(cd "$K" && md5sum $UNITS) > "$X/units.md5" && (cd "$B" && md5sum $BEFILES) > "$X/be.md5" || stop "cannot sum the copies"
{ echo "PIN_OLD=$PIN_OLD"; echo "ARCH_OLD=$ARCH_OLD"; echo "BENEW=$BENEW"
  if [ "$DRY" != 1 ]; then echo "NORMAL=$(m8 "$NB")"; echo "LEAN=$(m8 "$LB")"; echo "ARCH=$(m8 "$ARCH")"; fi; } > "$X/pins.before-0438b"
[ "$(m8 "$X/0001.before-0438b.patch")" = "$PIN_OLD" ] && (cd "$X/units" && md5sum -c --quiet "$X/units.md5") && (cd "$X/be" && md5sum -c --quiet "$X/be.md5") \
    || stop "the copies do not read back"
if [ "$DRY" != 1 ]; then
    [ "$(m8 "$X/kyty_emulator.normal.before-0438b")" = "$NORMAL_OLD" ] && [ "$(m8 "$X/kyty_emulator.lean.before-0438b")" = "$LEAN_OLD" ] \
        && [ "$(m8 "$X/libbc5_backend.a.before-0438b")" = "$ARCH_OLD" ] || stop "the binary copies do not read back"
    for v in normal lean; do words "$X/kyty_emulator.$v.before-0438b" > "$X/words-$v.before"; done
fi
echo "before: $(tr '\n' ' ' < "$X/pins.before-0438b")"
# 3
(cd "$K" && git apply "$HERE/$KP") || undo "git apply (host) failed"
for p in "src/libs/bc5LleAgc.cpp:$UNIT_NEW" "src/kernel/memory.cpp:$MEM_NEW" "src/bc5/switch_defaults.hpp:$SWD"; do
    [ "$(m8 "$K/${p%%:*}")" = "${p##*:}" ] || undo "${p%%:*} is $(m8 "$K/${p%%:*}") after the patch, not ${p##*:}"
done
P=$X/0001-new0438b.patch; O=$X/0001.before-0438b.patch
git -C "$K" diff --no-color f266548 > "$P" || undo "cannot write the new patch"
[ "$(grep -c 'exp 0372' "$P")" = 5 ] || undo "exp 0372 lines: $(grep -c 'exp 0372' "$P"), not 5"
grep -q '^diff --git a/src/bc5/pad_audio_route.hpp ' "$P" || undo "the pad_audio_route header is not in the patch"
files() { grep '^diff --git ' "$1" | sort; }
[ "$(files "$O")" = "$(files "$P")" ] || undo "the patch's file list changed"
for w in BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG learned JOB_ARENA; do
    [ "$(grep -c "$w" "$O")" = "$(grep -c "$w" "$P")" ] || undo "lines with $w: $(grep -c "$w" "$O") -> $(grep -c "$w" "$P")"
done
grep -q 'BC5_DIRECT_0438_A2_CHECK' "$P" && undo "the host patch names BC5_DIRECT_0438_A2_CHECK"
grep -q 'BC5_0438_SUBMITQ\|q438_on()\|q438_writer_queued\|BC5_0438_R438_LWM\|lw_packet_mapped\|PROLMERGE' "$P" && undo "Q438, labelmap or p438 text is in the patch"
for t in 'static bool acb_wait_unready(' 'std::getenv("BC5_0438_INFLIGHT_NG")' 'std::getenv("BC5_0438_OPEN_NG")' 'static std::atomic<int64_t> g_ng_live' \
         'std::getenv("KYTY_BC5_0438_A1")' 'std::getenv("KYTY_BC5_0438_A1P")' 'r438o: early entries renumbered'; do
    grep -qF "$t" "$P" || undo "not in the new patch: $t"
done
echo "the patch: $(m8 "$O") -> $(m8 "$P"), files $(files "$O" | wc -l) -> $(files "$P" | wc -l), exp 0372 lines 5, pad_audio_route header in; unit $UNIT_OLD -> $UNIT_NEW, memory.cpp $MEM_OLD -> $MEM_NEW, switch_defaults.hpp $SWD (unchanged)"
bapply || undo "git apply (backend) failed"
[ "$(m8 "$B/src/direct.cpp")" = "$BE_CPP_NEW" ] && [ "$(m8 "$B/include/bc5/direct.hpp")" = "$BE_HPP_NEW" ] && [ "$(m8 "$B/$BENEW")" = "$BE_MI_NEW" ] \
    || undo "the backend source after the patch: direct.cpp $(m8 "$B/src/direct.cpp"), direct.hpp $(m8 "$B/include/bc5/direct.hpp"), mapping_index.hpp $(m8 "$B/$BENEW" 2> /dev/null)"
echo "the backend source: direct.cpp $BE_CPP_OLD -> $BE_CPP_NEW, direct.hpp $BE_HPP_OLD -> $BE_HPP_NEW, $BENEW new ($BE_MI_NEW)"
if [ "$DRY" = 1 ]; then
    echo "swap0438b DRY: PATCH_NEW=$(m8 "$P"); undoing the copies"
    UNDO_IN_INT=1 X=$X UNDO_W=$W UNDO_K=$K UNDO_B=$B UNDO_DRY=1 bash "$HERE/undo0438b.sh"; exit $?
fi
[ "$(m8 "$P")" = "$PATCH_NEW" ] || undo "the new patch is $(m8 "$P"), not $PATCH_NEW"
# 4
echo "== $(date +%T) build the archive"
if ! distrobox enter ubuntu -- sh -c "cd '$BB' && nice -n 19 ninja bc5_backend" < /dev/null > "$X/build-backend.log" 2>&1; then
    grep -m12 -E "error:" "$X/build-backend.log" | cut -c1-260
    undo "the archive build failed"
fi
echo "archive: $(m8 "$ARCH"), warnings $(grep -c 'warning:' "$X/build-backend.log"); steps $(grep -c '^\[' "$X/build-backend.log")"
for v in normal lean; do
    d=$W/kytyplus-build$([ $v = lean ] && echo -lean)
    echo "== $(date +%T) build $v"
    if ! distrobox enter ubuntu -- sh -c "cd '$d' && nice -n 19 ninja kyty_emulator" < /dev/null > "$X/build-$v.log" 2>&1; then
        grep -m12 -E "error:" "$X/build-$v.log" | cut -c1-260
        undo "build $v failed"
    fi
    echo "$v: $(m8 "$d/src/kyty_emulator"), warnings $(grep -c 'warning:' "$X/build-$v.log"); steps $(grep -c '^\[' "$X/build-$v.log")"
done
# 5
[ "$(m8 "$ARCH")" != "$ARCH_OLD" ] || undo "the archive did not change"
nice -n 19 strings "$ARCH" | grep -qx 'BC5_DIRECT_0438_A2' || undo "the archive has no BC5_DIRECT_0438_A2"
for f in "$ARCH" "$NB" "$LB"; do  # A2's compare-only check is a build option, off in the bake: neither its word nor its line
    nice -n 19 strings "$f" | grep -q 'BC5_DIRECT_0438_A2_CHECK\|tag a2c438\|tag a2): MISMATCH' && undo "$f holds A2's compare-only check"
done
for v in normal lean; do
    b=$NB; want=$WORDS_NORMAL; [ $v = lean ] && { b=$LB; want=$WORDS_LEAN; }
    [ "$(m8 "$b")" != "$(m8 "$X/kyty_emulator.$v.before-0438b")" ] || undo "$v did not change"
    words "$b" > "$X/words-$v.after"
    gained=$(comm -13 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ' | sed 's/ $//'); lost=$(comm -23 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ' | sed 's/ $//')
    echo "$v words: +[$gained] -[$lost]"
    [ "$gained" = "$want" ] && [ -z "$lost" ] || undo "$v: switch words: gained [$gained], want [$want]; lost [$lost]"
    nice -n 19 strings "$b" | grep -q 'PROLMERGE\|p438 (exp 0438)\|BC5_0438_SUBMITQ\|BC5_0438_R438_LWM' && undo "$v: p438, Q438 or labelmap text is in the binary"
done
for t in "ng438 (exp 0438): t " "wd438 (exp 0438)" "tag a1c438" "r438o: early entries renumbered"; do
    nice -n 19 strings "$NB" | grep -qF "$t" || undo "normal: not in the binary: $t"
done
for t in "ng438 (exp 0438)" "wd438" "tag a1c438" "KYTY_BC5_0438_A1J" "r438 (exp 0438, b438)"; do
    nice -n 19 strings "$LB" | grep -qF "$t" && undo "lean: a normal-build line is in the binary: $t"
done
echo "swap0438b done $(date +%T): patch $(m8 "$P"), archive $(m8 "$ARCH"), normal $(m8 "$NB"), lean $(m8 "$LB"); undo: bash $HERE/undo0438b.sh (to $PIN_OLD; further back: the r438o kit's bake/undo0438o.sh)"
