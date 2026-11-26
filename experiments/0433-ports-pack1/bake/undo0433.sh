#!/usr/bin/env bash
# BC5 exp 0433: puts everything int0433.sh changed back as it was before it (patch d1388db0): the 17 units the pack
# changes, its new header gone (file and index entry), the shared backend's policy.cpp, the archive and both binaries,
# each checked by md5 against the copies and the pins file (int0433.sh's format: PIN_OLD, NORMAL, LEAN, ARCH, POL).
# No emulator may run. Run alone it takes its own BOX-LOCK slot; from int0433.sh (UNDO_IN_INT=1) it runs in int's slot.
# One step further back is exp 0430's own undo (bash ~/bc5-work/exp0430/kitb/undo0430b.sh), run after this one, never
# before. There is no rollback by a word: the pack has no switch.
# usage (on the box): bash undo0433.sh   (X=<dir> UNDO_W=<dir> UNDO_K=<dir> for a stand-in test)
set -u
export LC_ALL=C
W=${UNDO_W:-$HOME/bc5-work}; K=${UNDO_K:-$HOME/src/KytyPlus}; X=${X:-$W/exp0433/swap}
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH_PATH=$W/backend-ubuntu/libbc5_backend.a
POL_PATH=$W/d19/export/backend/src/policy.cpp; NEWF=src/bc5/ports_pack1.hpp
m8() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "undo0433: an emulator runs: NOT DONE"; exit 1; }
[ -s "$X/pins.before-0433" ] && [ -s "$X/units.md5" ] || { echo "undo0433: no copies in $X"; exit 1; }
if [ "${UNDO_IN_INT:-0}" != 1 ]; then
  . "$W/exp0413/n/chainlock0417.inc"
  chain_claim "exp 0433: undo of ports pack 1 built in (back to patch d1388db0; copies only, no emulator)" 5 || { echo "undo0433: no lock: NOT DONE"; exit 1; }
  trap chain_release EXIT
fi
PIN_OLD=; NORMAL=; LEAN=; ARCH=; POL=
. "$X/pins.before-0433"
[ -n "$PIN_OLD" ] && [ -n "$NORMAL" ] && [ -n "$LEAN" ] && [ -n "$ARCH" ] && [ -n "$POL" ] || { echo "undo0433: the pins file is incomplete: NOT DONE"; exit 1; }
(cd "$X/units" && md5sum -c --quiet "$X/units.md5") || { echo "undo0433: the unit copies do not match units.md5: NOT DONE"; exit 1; }
ok=1
while read -r _ u; do
    u=${u#\*}
    cp "$X/units/$u" "$K/$u" && touch "$K/$u" || { echo "undo0433: cannot restore $u"; ok=0; }
done < "$X/units.md5"
git -C "$K" rm -q --cached --ignore-unmatch -- "$NEWF" > /dev/null 2>&1
rm -f "$K/$NEWF"
cp "$X/policy.cpp.before-0433" "$POL_PATH" && touch "$POL_PATH" \
  && cp -p "$X/libbc5_backend.a.before-0433" "$ARCH_PATH" \
  && cp -p "$X/kyty_emulator.normal.before-0433" "$NB" && cp -p "$X/kyty_emulator.lean.before-0433" "$LB" || { echo "undo0433: a copy failed"; ok=0; }
d=$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)
[ "$d" = "$PIN_OLD" ] || { echo "undo0433: the tree's diff is $d, not $PIN_OLD"; ok=0; }
[ ! -e "$K/$NEWF" ] || { echo "undo0433: $NEWF is still there"; ok=0; }
(cd "$K" && md5sum -c --quiet "$X/units.md5") || { echo "undo0433: the units do not read back"; ok=0; }
[ "$(m8 "$POL_PATH")" = "$POL" ] || { echo "undo0433: policy.cpp is $(m8 "$POL_PATH"), not $POL"; ok=0; }
[ "$(m8 "$ARCH_PATH")" = "$ARCH" ] || { echo "undo0433: the archive is $(m8 "$ARCH_PATH"), not $ARCH"; ok=0; }
[ "$(m8 "$NB")" = "$NORMAL" ] || { echo "undo0433: normal is $(m8 "$NB"), not $NORMAL"; ok=0; }
[ "$(m8 "$LB")" = "$LEAN" ] || { echo "undo0433: lean is $(m8 "$LB"), not $LEAN"; ok=0; }
[ $ok = 1 ] && echo "undo0433: back: patch $PIN_OLD, policy.cpp $POL, archive $ARCH, normal $NORMAL, lean $LEAN (the units are touched, so the next ninja recompiles them); further back: bash $W/exp0430/kitb/undo0430b.sh"
[ $ok = 1 ]
