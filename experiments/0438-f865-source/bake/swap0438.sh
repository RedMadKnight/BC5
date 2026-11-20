#!/usr/bin/env bash
# BC5 exp 0438, the shared swap of r438 (F865's source fix) with PLWCV, its two switches KEPT for a per-run opt-out
# (BC5_0438_EARLYREG, BC5_0438_PLWCV: both on unless "0"; the top session's proposal of 2026-11-20, result 13). No p438.
# exp 0436's swap0436.sh without its backend step: r438 lives in the host unit only, so the archive stays d6638808.
#   1. checks: no emulator; the kit (md5s below); the shared tree's diff is bb04219b and its unit a62e8bf6; normal
#      f345db74, lean 6a735b81, archive d6638808; the patch applies (git apply --check)
#   2. the lock (chain_claim, one line); copies under $X (*.before-0438: both binaries, the unit, the old patch), read
#      back; pins file
#   3. 0002-bc5-0438-baked.patch applied to the tree; the unit must be the kit's (ff9e8fe2); the new patch = git diff
#      f266548 must be PATCH_NEW; exp 0372 = 5, the pad_audio_route header in, the same file list, the guard / learned /
#      JOB_ARENA line counts as before, no PROLMERGE / p438 text, r438's count line in
#      DRY=1 (on COPIES: INT_K=<copy of ~/src/KytyPlus>, X=<scratch>): stops here, prints the new patch's md5, undoes
#   4. normal and lean rebuilt in place (ninja kyty_emulator, nice 19)
#   5. strings: each binary gains exactly BC5_0438_EARLYREG and BC5_0438_PLWCV and loses no (KYTY_)BC5_ word; no
#      PROLMERGE or p438 text; normal holds r438's count line, lean does not; the archive is unchanged
# Any failure after step 2 runs undo0438.sh (everything back, checked by md5).
# usage (on the box, in the kit directory): PATCH_NEW=<md5 from the dry run> bash swap0438.sh
#                                           DRY=1 INT_K=<copy> X=<scratch> bash swap0438.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=${INT_W:-$HOME/bc5-work}; N=$W/exp0413/n; K=${INT_K:-$HOME/src/KytyPlus}; HERE=$(cd "$(dirname "$0")" && pwd); X=${X:-$W/exp0438/swap}
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
PIN_OLD=bb04219b; NORMAL_OLD=f345db74; LEAN_OLD=6a735b81; ARCH_OLD=d6638808; UNIT_OLD=a62e8bf6; UNIT_NEW=ff9e8fe2
KIT_PATCH=eb431795; DRY=${DRY:-0}
PATCH_NEW=${PATCH_NEW:-}
UNITS="src/libs/bc5LleAgc.cpp"
m8() { md5sum < "$1" | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8; }
stop() { echo "swap0438 STOP: $*"; exit 1; }
undo() { echo "swap0438: FAILED: $*; undoing"; UNDO_IN_INT=1 X=$X UNDO_W=$W UNDO_K=$K UNDO_DRY=$DRY bash "$HERE/undo0438.sh"; exit 1; }
words() { nice -n 19 strings "$1" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u; }
# 1
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
for f in 0002-bc5-0438-baked.patch undo0438.sh; do [ -s "$HERE/$f" ] || stop "kit: $f missing"; done
[ "$(m8 "$HERE/0002-bc5-0438-baked.patch")" = "$KIT_PATCH" ] || stop "kit: the patch is $(m8 "$HERE/0002-bc5-0438-baked.patch"), not $KIT_PATCH"
[ "$DRY" = 1 ] || [ -n "$PATCH_NEW" ] || stop "PATCH_NEW is not given (take it from the dry run)"
if [ "$DRY" = 1 ]; then
    [ "$K" = "$HOME/src/KytyPlus" ] && stop "DRY=1 runs on a copy of the tree only (INT_K)"
    [ "$X" = "$W/exp0438/swap" ] && stop "DRY=1 keeps its copies apart (X)"
fi
[ "$(tdiff)" = "$PIN_OLD" ] || stop "the tree's diff is $(tdiff), not $PIN_OLD"
[ "$(m8 "$K/src/libs/bc5LleAgc.cpp")" = "$UNIT_OLD" ] || stop "the tree's unit is $(m8 "$K/src/libs/bc5LleAgc.cpp"), not $UNIT_OLD"
[ "$(m8 "$NB")" = "$NORMAL_OLD" ] || stop "normal is $(m8 "$NB"), not $NORMAL_OLD"
[ "$(m8 "$LB")" = "$LEAN_OLD" ] || stop "lean is $(m8 "$LB"), not $LEAN_OLD"
[ "$(m8 "$ARCH")" = "$ARCH_OLD" ] || stop "the archive is $(m8 "$ARCH"), not $ARCH_OLD"
(cd "$K" && git apply --check "$HERE/0002-bc5-0438-baked.patch") || stop "the patch does not apply to the tree"
# 2
if [ "$DRY" != 1 ]; then
    . "$N/chainlock0417.inc"
    chain_claim "exp 0438: shared swap, r438 with PLWCV (switches kept), patch $PIN_OLD -> $PATCH_NEW; normal and lean rebuilt (CPU only, no emulator)" 45 || stop "no lock"
    trap chain_release EXIT
fi
[ -e "$X/pins.before-0438" ] && stop "$X already holds a swap's copies: undo or move them first"
mkdir -p "$X/units" || stop "cannot make $X"
if [ "$DRY" != 1 ]; then
    cp -p "$NB" "$X/kyty_emulator.normal.before-0438" && cp -p "$LB" "$X/kyty_emulator.lean.before-0438" || stop "cannot copy the binaries"
fi
for u in $UNITS; do mkdir -p "$X/units/$(dirname "$u")" && cp -p "$K/$u" "$X/units/$u" || stop "cannot copy $u"; done
git -C "$K" diff --no-color f266548 > "$X/0001.before-0438.patch" || stop "cannot save the patch"
# shellcheck disable=SC2086
(cd "$K" && md5sum $UNITS) > "$X/units.md5" || stop "cannot sum the units"
{ echo "PIN_OLD=$PIN_OLD"; echo "ARCH_OLD=$ARCH_OLD"
  if [ "$DRY" != 1 ]; then echo "NORMAL=$(m8 "$NB")"; echo "LEAN=$(m8 "$LB")"; fi; } > "$X/pins.before-0438"
[ "$(m8 "$X/0001.before-0438.patch")" = "$PIN_OLD" ] && (cd "$X/units" && md5sum -c --quiet "$X/units.md5") || stop "the copies do not read back"
if [ "$DRY" != 1 ]; then
    [ "$(m8 "$X/kyty_emulator.normal.before-0438")" = "$NORMAL_OLD" ] && [ "$(m8 "$X/kyty_emulator.lean.before-0438")" = "$LEAN_OLD" ] || stop "the binary copies do not read back"
    for v in normal lean; do words "$X/kyty_emulator.$v.before-0438" > "$X/words-$v.before"; done
fi
echo "before: $(tr '\n' ' ' < "$X/pins.before-0438")"
# 3
(cd "$K" && git apply "$HERE/0002-bc5-0438-baked.patch") || undo "git apply failed"
[ "$(m8 "$K/src/libs/bc5LleAgc.cpp")" = "$UNIT_NEW" ] || undo "the unit is $(m8 "$K/src/libs/bc5LleAgc.cpp") after the patch, not $UNIT_NEW"
P=$X/0001-new0438.patch; O=$X/0001.before-0438.patch
git -C "$K" diff --no-color f266548 > "$P" || undo "cannot write the new patch"
[ "$(grep -c 'exp 0372' "$P")" = 5 ] || undo "exp 0372 lines: $(grep -c 'exp 0372' "$P"), not 5"
grep -q '^diff --git a/src/bc5/pad_audio_route.hpp ' "$P" || undo "the pad_audio_route header is not in the patch"
files() { grep '^diff --git ' "$1" | sort; }
[ "$(files "$O")" = "$(files "$P")" ] || undo "the patch's file list changed"
for w in BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG learned JOB_ARENA; do
    [ "$(grep -c "$w" "$O")" = "$(grep -c "$w" "$P")" ] || undo "lines with $w: $(grep -c "$w" "$O") -> $(grep -c "$w" "$P")"
done
grep -q 'PROLMERGE\|p438' "$P" && undo "p438 text is in the patch"
grep -q 'r438 (exp 0438, b438): t ' "$P" || undo "r438's count line is not in the patch"
echo "the patch: $(m8 "$O") -> $(m8 "$P"), files $(files "$O" | wc -l) -> $(files "$P" | wc -l), exp 0372 lines 5, pad_audio_route header in; unit $UNIT_OLD -> $UNIT_NEW"
if [ "$DRY" = 1 ]; then
    echo "swap0438 DRY: PATCH_NEW=$(m8 "$P"); undoing the copies"
    UNDO_IN_INT=1 X=$X UNDO_W=$W UNDO_K=$K UNDO_DRY=1 bash "$HERE/undo0438.sh"; exit $?
fi
[ "$(m8 "$P")" = "$PATCH_NEW" ] || undo "the new patch is $(m8 "$P"), not $PATCH_NEW"
# 4
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
[ "$(m8 "$ARCH")" = "$ARCH_OLD" ] || undo "the archive changed: $(m8 "$ARCH")"
for v in normal lean; do
    b=$NB; [ $v = lean ] && b=$LB
    [ "$(m8 "$b")" != "$(m8 "$X/kyty_emulator.$v.before-0438")" ] || undo "$v did not change"
    words "$b" > "$X/words-$v.after"
    gained=$(comm -13 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ' | sed 's/ $//'); lost=$(comm -23 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ' | sed 's/ $//')
    echo "$v words: +[$gained] -[$lost]"
    [ "$gained" = "BC5_0438_EARLYREG BC5_0438_PLWCV" ] && [ -z "$lost" ] || undo "$v: the words are not +EARLYREG +PLWCV only"
    nice -n 19 strings "$b" | grep -q 'PROLMERGE\|p438 (exp 0438)\|b438, lean' && undo "$v: p438 or lean's counter is in the binary"
done
nice -n 19 strings "$NB" | grep -qF "r438 (exp 0438, b438): t " || undo "normal: r438's count line is not in the binary"
nice -n 19 strings "$LB" | grep -qF "r438 (exp 0438, b438)" && undo "lean: r438's lines are in the binary"
echo "swap0438 done $(date +%T): patch $(m8 "$P"), archive $(m8 "$ARCH") (unchanged), normal $(m8 "$NB"), lean $(m8 "$LB"); undo: bash $HERE/undo0438.sh (to $PIN_OLD; further back: exp 0436's undo0436.sh)"
