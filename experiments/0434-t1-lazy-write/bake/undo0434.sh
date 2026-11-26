#!/usr/bin/env bash
# BC5 exp 0434: puts everything int0434.sh changed back as it was before it (patch 59f00d27): the 5 units the change
# edits, its new header gone (file and index entry), both binaries, each checked by md5 against the copies and the pins
# file (int0434.sh's format: PIN_OLD, NORMAL, LEAN, ARCH). The backend archive is not touched by the swap; it is checked.
# No emulator may run. Run alone it takes its own BOX-LOCK slot; from int0434.sh (UNDO_IN_INT=1) it runs in int's slot.
# UNDO_DRY=1 (from int0434.sh's dry run on a copy of the tree): the units and the header only, no binary.
# One step further back is exp 0433's own undo (bash ~/bc5-work/exp0433/bake/undo0433.sh), run after this one, never
# before. There is no rollback by a word: the change has no switch.
# usage (on the box): bash undo0434.sh
set -u
export LC_ALL=C
W=${UNDO_W:-$HOME/bc5-work}; K=${UNDO_K:-$HOME/src/KytyPlus}; X=${X:-$W/exp0434/swap}; DRY=${UNDO_DRY:-0}
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH_PATH=$W/backend-ubuntu/libbc5_backend.a
NEWF=src/bc5/title_settings.hpp
m8() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "undo0434: an emulator runs: NOT DONE"; exit 1; }
[ -s "$X/pins.before-0434" ] && [ -s "$X/units.md5" ] || { echo "undo0434: no copies in $X"; exit 1; }
if [ "${UNDO_IN_INT:-0}" != 1 ]; then
  . "$W/exp0413/n/chainlock0417.inc"
  chain_claim "exp 0434: undo of ud434 + exp 0435 built in (back to patch 59f00d27; copies only, no emulator)" 5 || { echo "undo0434: no lock: NOT DONE"; exit 1; }
  trap chain_release EXIT
fi
PIN_OLD=; NORMAL=; LEAN=; ARCH=
. "$X/pins.before-0434"
[ -n "$PIN_OLD" ] || { echo "undo0434: the pins file is incomplete: NOT DONE"; exit 1; }
[ "$DRY" = 1 ] || { [ -n "$NORMAL" ] && [ -n "$LEAN" ] && [ -n "$ARCH" ]; } || { echo "undo0434: the pins file is incomplete: NOT DONE"; exit 1; }
(cd "$X/units" && md5sum -c --quiet "$X/units.md5") || { echo "undo0434: the unit copies do not match units.md5: NOT DONE"; exit 1; }
ok=1
while read -r _ u; do
    u=${u#\*}
    cp "$X/units/$u" "$K/$u" && touch "$K/$u" || { echo "undo0434: cannot restore $u"; ok=0; }
done < "$X/units.md5"
git -C "$K" rm -q --cached --ignore-unmatch -- "$NEWF" > /dev/null 2>&1
rm -f "$K/$NEWF"
if [ "$DRY" != 1 ]; then
    cp -p "$X/kyty_emulator.normal.before-0434" "$NB" && cp -p "$X/kyty_emulator.lean.before-0434" "$LB" || { echo "undo0434: a copy failed"; ok=0; }
fi
d=$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)
[ "$d" = "$PIN_OLD" ] || { echo "undo0434: the tree's diff is $d, not $PIN_OLD"; ok=0; }
[ ! -e "$K/$NEWF" ] || { echo "undo0434: $NEWF is still there"; ok=0; }
(cd "$K" && md5sum -c --quiet "$X/units.md5") || { echo "undo0434: the units do not read back"; ok=0; }
if [ "$DRY" != 1 ]; then
    [ "$(m8 "$ARCH_PATH")" = "$ARCH" ] || { echo "undo0434: the archive is $(m8 "$ARCH_PATH"), not $ARCH"; ok=0; }
    [ "$(m8 "$NB")" = "$NORMAL" ] || { echo "undo0434: normal is $(m8 "$NB"), not $NORMAL"; ok=0; }
    [ "$(m8 "$LB")" = "$LEAN" ] || { echo "undo0434: lean is $(m8 "$LB"), not $LEAN"; ok=0; }
fi
[ $ok = 1 ] && echo "undo0434: back: patch $PIN_OLD$([ "$DRY" = 1 ] && echo " (dry run: the copy's tree only)" || echo ", archive $ARCH, normal $NORMAL, lean $LEAN (the units are touched, so the next ninja recompiles them); further back: bash $W/exp0433/bake/undo0433.sh")"
[ $ok = 1 ]
