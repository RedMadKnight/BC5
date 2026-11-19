#!/usr/bin/env bash
# BC5 exp 0434, the shared swap of ud434 (exp 0434) and the per-title settings (exp 0435) BUILT IN, with no switch: no
# BC5_DIRECT_UD_TARGETS, no KYTY_BC5_TITLE_SETTINGS (the maintainer, 2026-11-19, after his test of the combined build on
# Bathhouse Battle: "Wszystko ok, możesz wdrożyć i wypchnic i merge"; his standing word "usuń przełączniki i wybuduj w
# kod"). The form of exp 0433's int0433.sh without its backend step (no backend file changes; the archive stays).
#   1. checks: no emulator; the kit (md5 below); the shared tree's diff is 59f00d27 and has no title_settings.hpp;
#      normal efc28a30, lean d8b75137, archive 51db2c91; the patch applies (git apply --check)
#   2. the lock (chain_claim, one line); copies under $X (*.before-0434: both binaries, the 5 units the change edits,
#      the old patch), read back; pins file
#   3. 0002-bc5-0434-0435-baked.patch applied to the tree (git apply), its new file marked with git add -N (so
#      `git diff f266548` shows it); the new patch = git diff f266548 must be PATCH_NEW; exp 0372 = 5, the
#      pad_audio_route header in, the old file list kept plus one file, the guard / learned / JOB_ARENA line counts as
#      before, no BC5_DIRECT_UD_TARGETS / KYTY_BC5_TITLE_SETTINGS text
#      DRY=1 (the dry run on a COPY of the tree, INT_K=<copy>): stops here, prints the new patch's md5, undoes the copy
#   4. normal and lean rebuilt in place (ninja kyty_emulator, nice 19)
#   5. strings: neither binary gains or loses a (KYTY_)BC5_ word; neither holds BC5_DIRECT_UD_TARGETS or
#      KYTY_BC5_TITLE_SETTINGS; normal holds ud434's journal line ("tag ud434"), lean does not (journal compiled out);
#      both hold 0435's store name ("titles")
# Any failure after step 2 runs undo0434.sh (everything back, checked by md5).
# usage (on the box, in the kit directory): PATCH_NEW=<md5 from the dry run> bash int0434.sh
#                                           DRY=1 INT_K=<copy of ~/src/KytyPlus> X=<scratch> bash int0434.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=${INT_W:-$HOME/bc5-work}; N=$W/exp0413/n; K=${INT_K:-$HOME/src/KytyPlus}; HERE=$(cd "$(dirname "$0")" && pwd); X=${X:-$W/exp0434/swap}
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
PIN_OLD=59f00d27; NORMAL_OLD=efc28a30; LEAN_OLD=d8b75137; ARCH_OLD=51db2c91
KIT_PATCH=eeae31c8; DRY=${DRY:-0}
PATCH_NEW=${PATCH_NEW:-}
NEWF=src/bc5/title_settings.hpp
UNITS="src/graphics/presentation/window/hostInput.cpp src/graphics/presentation/window/hostInput.h src/graphics/presentation/window.h src/graphics/presentation/window/window.cpp src/libs/bc5LleAgc.cpp"
m8() { md5sum < "$1" | cut -c1-8; }
tdiff() { git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8; }
stop() { echo "int0434 STOP: $*"; exit 1; }
undo() { echo "int0434: FAILED: $*; undoing"; UNDO_IN_INT=1 X=$X UNDO_W=$W UNDO_K=$K UNDO_DRY=$DRY bash "$HERE/undo0434.sh"; exit 1; }
words() { nice -n 19 strings "$1" | grep -x '\(KYTY_\)\?BC5_[A-Z0-9_]*' | sort -u; }
# 1
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
for f in 0002-bc5-0434-0435-baked.patch undo0434.sh; do [ -s "$HERE/$f" ] || stop "kit: $f missing"; done
[ "$(m8 "$HERE/0002-bc5-0434-0435-baked.patch")" = "$KIT_PATCH" ] || stop "kit: the patch is $(m8 "$HERE/0002-bc5-0434-0435-baked.patch"), not $KIT_PATCH"
[ "$DRY" = 1 ] || [ -n "$PATCH_NEW" ] || stop "PATCH_NEW is not given (take it from the dry run)"
[ "$DRY" = 1 ] && [ "$K" = "$HOME/src/KytyPlus" ] && stop "DRY=1 runs on a copy of the tree only (INT_K)"
[ "$(tdiff)" = "$PIN_OLD" ] || stop "the tree's diff is $(tdiff), not $PIN_OLD"
[ -e "$K/$NEWF" ] && stop "$K/$NEWF exists already"
if [ "$DRY" != 1 ]; then
    [ "$(m8 "$NB")" = "$NORMAL_OLD" ] || stop "normal is $(m8 "$NB"), not $NORMAL_OLD"
    [ "$(m8 "$LB")" = "$LEAN_OLD" ] || stop "lean is $(m8 "$LB"), not $LEAN_OLD"
    [ "$(m8 "$ARCH")" = "$ARCH_OLD" ] || stop "the archive is $(m8 "$ARCH"), not $ARCH_OLD"
fi
(cd "$K" && git apply --check "$HERE/0002-bc5-0434-0435-baked.patch") || stop "the patch does not apply to the tree"
# 2
if [ "$DRY" != 1 ]; then
    . "$N/chainlock0417.inc"
    chain_claim "exp 0434: shared swap, ud434 + exp 0435 built in (no switch), patch $PIN_OLD -> $PATCH_NEW; normal and lean rebuilt (CPU only, no emulator)" 40 || stop "no lock"
    trap chain_release EXIT
fi
[ -e "$X/pins.before-0434" ] && stop "$X already holds a swap's copies: undo or move them first"
mkdir -p "$X/units" || stop "cannot make $X"
if [ "$DRY" != 1 ]; then
    cp -p "$NB" "$X/kyty_emulator.normal.before-0434" && cp -p "$LB" "$X/kyty_emulator.lean.before-0434" || stop "cannot copy the binaries"
fi
for u in $UNITS; do mkdir -p "$X/units/$(dirname "$u")" && cp -p "$K/$u" "$X/units/$u" || stop "cannot copy $u"; done
git -C "$K" diff --no-color f266548 > "$X/0001.before-0434.patch" || stop "cannot save the patch"
(cd "$K" && md5sum $UNITS) > "$X/units.md5" || stop "cannot sum the units"
{ echo "PIN_OLD=$PIN_OLD"; if [ "$DRY" != 1 ]; then echo "NORMAL=$(m8 "$NB")"; echo "LEAN=$(m8 "$LB")"; echo "ARCH=$(m8 "$ARCH")"; fi; } > "$X/pins.before-0434"
[ "$(m8 "$X/0001.before-0434.patch")" = "$PIN_OLD" ] && (cd "$X/units" && md5sum -c --quiet "$X/units.md5") || stop "the copies do not read back"
if [ "$DRY" != 1 ]; then
    [ "$(m8 "$X/kyty_emulator.normal.before-0434")" = "$NORMAL_OLD" ] && [ "$(m8 "$X/kyty_emulator.lean.before-0434")" = "$LEAN_OLD" ] || stop "the binary copies do not read back"
    for v in normal lean; do words "$X/kyty_emulator.$v.before-0434" > "$X/words-$v.before"; done
fi
echo "before: $(tr '\n' ' ' < "$X/pins.before-0434")"
# 3
(cd "$K" && git apply "$HERE/0002-bc5-0434-0435-baked.patch") || undo "git apply failed"
git -C "$K" add -N "$NEWF" || undo "git add -N $NEWF failed"
P=$X/0001-new0434.patch; O=$X/0001.before-0434.patch
git -C "$K" diff --no-color f266548 > "$P" || undo "cannot write the new patch"
[ "$(grep -c 'exp 0372' "$P")" = 5 ] || undo "exp 0372 lines: $(grep -c 'exp 0372' "$P"), not 5"
grep -q '^diff --git a/src/bc5/pad_audio_route.hpp ' "$P" || undo "the pad_audio_route header is not in the patch"
files() { grep '^diff --git ' "$1" | sort; }
[ -z "$(comm -23 <(files "$O") <(files "$P"))" ] || undo "a file left the patch: $(comm -23 <(files "$O") <(files "$P") | tr '\n' ' ')"
[ "$(comm -13 <(files "$O") <(files "$P"))" = "diff --git a/$NEWF b/$NEWF" ] || undo "files new to the patch: $(comm -13 <(files "$O") <(files "$P") | tr '\n' ' '), not only $NEWF"
for w in BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG learned JOB_ARENA; do
    [ "$(grep -c "$w" "$O")" = "$(grep -c "$w" "$P")" ] || undo "lines with $w: $(grep -c "$w" "$O") -> $(grep -c "$w" "$P")"
done
grep -q 'BC5_DIRECT_UD_TARGETS\|KYTY_BC5_TITLE_SETTINGS' "$P" && undo "a switch word of 0434/0435 is in the patch"
grep -c 'tag ud434' "$P" > /dev/null || undo "ud434 is not in the patch"
echo "the patch: $(m8 "$O") -> $(m8 "$P"), files $(files "$O" | wc -l) -> $(files "$P" | wc -l), exp 0372 lines 5, pad_audio_route header in"
if [ "$DRY" = 1 ]; then
    echo "int0434 DRY: PATCH_NEW=$(m8 "$P"); undoing the copy"
    UNDO_IN_INT=1 X=$X UNDO_W=$W UNDO_K=$K UNDO_DRY=1 bash "$HERE/undo0434.sh"; exit $?
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
for v in normal lean; do
    b=$NB; [ $v = lean ] && b=$LB
    [ "$(m8 "$b")" != "$(m8 "$X/kyty_emulator.$v.before-0434")" ] || undo "$v did not change"
    words "$b" > "$X/words-$v.after"
    gained=$(comm -13 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ' | sed 's/ $//'); lost=$(comm -23 "$X/words-$v.before" "$X/words-$v.after" | tr '\n' ' ' | sed 's/ $//')
    echo "$v words: +[$gained] -[$lost]"
    [ -z "$gained" ] && [ -z "$lost" ] || undo "$v: the words changed"
    nice -n 19 strings "$b" | grep -q 'BC5_DIRECT_UD_TARGETS\|KYTY_BC5_TITLE_SETTINGS' && undo "$v: a switch word of 0434/0435 is in the binary"
    nice -n 19 strings "$b" | grep -qF "titles" || undo "$v: 0435's store name is not in the binary"
done
nice -n 19 strings "$NB" | grep -qF "tag ud434" || undo "normal: ud434's journal line is not in the binary"
nice -n 19 strings "$LB" | grep -qF "tag ud434" && undo "lean: ud434's journal line is in the binary"
echo "int0434 done $(date +%T): patch $(m8 "$P"), archive $(m8 "$ARCH") (unchanged), normal $(m8 "$NB"), lean $(m8 "$LB"); undo: bash $HERE/undo0434.sh (to $PIN_OLD; further back: exp 0433's undo0433.sh)"
