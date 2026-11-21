#!/usr/bin/env bash
# BC5 exp 0438 (tag r438o): puts everything swap0438o.sh changed back as it was before it (patch 9889b06a, normal b1b57df9,
# lean d3485ed4; the archive d6638808 is never touched): the unit the change edits and both binaries, each checked by md5
# against the copies and the pins file (swap0438o.sh's format: PIN_OLD, ARCH_OLD, NORMAL, LEAN). No emulator may run.
# Run alone it takes its own BOX-LOCK slot; from swap0438o.sh (UNDO_IN_INT=1) it runs in the swap's slot. UNDO_DRY=1
# (swap0438o.sh's dry run on copies): the unit only, no binary.
# Without a rebuild, r438 and r438o can be turned off per run: BC5_0438_EARLYREG=0 (and BC5_0438_PLWCV=0 for the 20-us poll).
# One step further back is r438's own undo (bash ~/bc5-work/exp0438/bake/undo0438.sh), run after this one, never
# before.
# usage (on the box): bash undo0438.sh
set -u
export LC_ALL=C
W=${UNDO_W:-$HOME/bc5-work}; K=${UNDO_K:-$HOME/src/KytyPlus}; X=${X:-$W/exp0438/swapo}; DRY=${UNDO_DRY:-0}
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH_PATH=$W/backend-ubuntu/libbc5_backend.a
m8() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "undo0438o: an emulator runs: NOT DONE"; exit 1; }
[ -s "$X/pins.before-0438o" ] && [ -s "$X/units.md5" ] || { echo "undo0438o: no copies in $X"; exit 1; }
if [ "${UNDO_IN_INT:-0}" != 1 ]; then
  . "$W/exp0413/n/chainlock0417.inc"
  chain_claim "exp 0438: undo of r438o (back to patch 9889b06a; copies only, no emulator)" 5 || { echo "undo0438o: no lock: NOT DONE"; exit 1; }
  trap chain_release EXIT
fi
PIN_OLD=; ARCH_OLD=; NORMAL=; LEAN=
. "$X/pins.before-0438o"
[ -n "$PIN_OLD" ] && [ -n "$ARCH_OLD" ] || { echo "undo0438o: the pins file is incomplete: NOT DONE"; exit 1; }
[ "$DRY" = 1 ] || { [ -n "$NORMAL" ] && [ -n "$LEAN" ]; } || { echo "undo0438o: the pins file is incomplete: NOT DONE"; exit 1; }
(cd "$X/units" && md5sum -c --quiet "$X/units.md5") || { echo "undo0438o: the unit copies do not match units.md5: NOT DONE"; exit 1; }
ok=1
while read -r _ u; do
    u=${u#\*}
    cp "$X/units/$u" "$K/$u" && touch "$K/$u" || { echo "undo0438o: cannot restore $u"; ok=0; }
done < "$X/units.md5"
if [ "$DRY" != 1 ]; then
    cp -p "$X/kyty_emulator.normal.before-0438o" "$NB" && cp -p "$X/kyty_emulator.lean.before-0438o" "$LB" || { echo "undo0438o: a copy failed"; ok=0; }
fi
d=$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)
[ "$d" = "$PIN_OLD" ] || { echo "undo0438o: the tree's diff is $d, not $PIN_OLD"; ok=0; }
(cd "$K" && md5sum -c --quiet "$X/units.md5") || { echo "undo0438o: the units do not read back"; ok=0; }
if [ "$DRY" != 1 ]; then
    [ "$(m8 "$ARCH_PATH")" = "$ARCH_OLD" ] || { echo "undo0438o: the archive is $(m8 "$ARCH_PATH"), not $ARCH_OLD (swap0438o never writes it)"; ok=0; }
    [ "$(m8 "$NB")" = "$NORMAL" ] || { echo "undo0438o: normal is $(m8 "$NB"), not $NORMAL"; ok=0; }
    [ "$(m8 "$LB")" = "$LEAN" ] || { echo "undo0438o: lean is $(m8 "$LB"), not $LEAN"; ok=0; }
fi
[ $ok = 1 ] && echo "undo0438o: back: patch $PIN_OLD$([ "$DRY" = 1 ] && echo " (dry run: the copies only)" || echo ", archive $ARCH_OLD, normal $NORMAL, lean $LEAN (the unit is touched, so the next ninja recompiles it); further back: bash $W/exp0438/bake/undo0438.sh")"
[ $ok = 1 ]
