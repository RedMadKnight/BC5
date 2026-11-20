#!/usr/bin/env bash
# BC5 exp 0438: puts everything swap0438.sh changed back as it was before it (patch bb04219b, normal f345db74, lean
# 6a735b81; the archive d6638808 is never touched): the unit the change edits and both binaries, each checked by md5
# against the copies and the pins file (swap0438.sh's format: PIN_OLD, ARCH_OLD, NORMAL, LEAN). No emulator may run.
# Run alone it takes its own BOX-LOCK slot; from swap0438.sh (UNDO_IN_INT=1) it runs in the swap's slot. UNDO_DRY=1
# (swap0438.sh's dry run on copies): the unit only, no binary.
# Without a rebuild, r438 can be turned off per run: BC5_0438_EARLYREG=0 (and BC5_0438_PLWCV=0 for the 20-us poll).
# One step further back is exp 0436's own undo (bash ~/bc5-work/exp0436/bake/undo0436.sh), run after this one, never
# before.
# usage (on the box): bash undo0438.sh
set -u
export LC_ALL=C
W=${UNDO_W:-$HOME/bc5-work}; K=${UNDO_K:-$HOME/src/KytyPlus}; X=${X:-$W/exp0438/swap}; DRY=${UNDO_DRY:-0}
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH_PATH=$W/backend-ubuntu/libbc5_backend.a
m8() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "undo0438: an emulator runs: NOT DONE"; exit 1; }
[ -s "$X/pins.before-0438" ] && [ -s "$X/units.md5" ] || { echo "undo0438: no copies in $X"; exit 1; }
if [ "${UNDO_IN_INT:-0}" != 1 ]; then
  . "$W/exp0413/n/chainlock0417.inc"
  chain_claim "exp 0438: undo of r438 built in (back to patch bb04219b; copies only, no emulator)" 5 || { echo "undo0438: no lock: NOT DONE"; exit 1; }
  trap chain_release EXIT
fi
PIN_OLD=; ARCH_OLD=; NORMAL=; LEAN=
. "$X/pins.before-0438"
[ -n "$PIN_OLD" ] && [ -n "$ARCH_OLD" ] || { echo "undo0438: the pins file is incomplete: NOT DONE"; exit 1; }
[ "$DRY" = 1 ] || { [ -n "$NORMAL" ] && [ -n "$LEAN" ]; } || { echo "undo0438: the pins file is incomplete: NOT DONE"; exit 1; }
(cd "$X/units" && md5sum -c --quiet "$X/units.md5") || { echo "undo0438: the unit copies do not match units.md5: NOT DONE"; exit 1; }
ok=1
while read -r _ u; do
    u=${u#\*}
    cp "$X/units/$u" "$K/$u" && touch "$K/$u" || { echo "undo0438: cannot restore $u"; ok=0; }
done < "$X/units.md5"
if [ "$DRY" != 1 ]; then
    cp -p "$X/kyty_emulator.normal.before-0438" "$NB" && cp -p "$X/kyty_emulator.lean.before-0438" "$LB" || { echo "undo0438: a copy failed"; ok=0; }
fi
d=$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)
[ "$d" = "$PIN_OLD" ] || { echo "undo0438: the tree's diff is $d, not $PIN_OLD"; ok=0; }
(cd "$K" && md5sum -c --quiet "$X/units.md5") || { echo "undo0438: the units do not read back"; ok=0; }
if [ "$DRY" != 1 ]; then
    [ "$(m8 "$ARCH_PATH")" = "$ARCH_OLD" ] || { echo "undo0438: the archive is $(m8 "$ARCH_PATH"), not $ARCH_OLD (swap0438 never writes it)"; ok=0; }
    [ "$(m8 "$NB")" = "$NORMAL" ] || { echo "undo0438: normal is $(m8 "$NB"), not $NORMAL"; ok=0; }
    [ "$(m8 "$LB")" = "$LEAN" ] || { echo "undo0438: lean is $(m8 "$LB"), not $LEAN"; ok=0; }
fi
[ $ok = 1 ] && echo "undo0438: back: patch $PIN_OLD$([ "$DRY" = 1 ] && echo " (dry run: the copies only)" || echo ", archive $ARCH_OLD, normal $NORMAL, lean $LEAN (the unit is touched, so the next ninja recompiles it); further back: bash $W/exp0436/bake/undo0436.sh")"
[ $ok = 1 ]
