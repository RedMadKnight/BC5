#!/usr/bin/env bash
# BC5 exp 0438 (tag bake438b): puts everything swap0438b.sh changed back as it was before it (patch 0fede35d, normal 199a0f39,
# lean 3a20b974, archive d6638808): the two host files (bc5LleAgc.cpp, memory.cpp), the backend source's two files (and removes the new
# include/bc5/mapping_index.hpp), the archive and both binaries, each checked by md5 against the copies and the pins file
# (swap0438b.sh's format: PIN_OLD, ARCH_OLD, BENEW, NORMAL, LEAN, ARCH). No emulator may run.
# Run alone it takes its own BOX-LOCK slot; from swap0438b.sh (UNDO_IN_INT=1) it runs in the swap's slot. UNDO_DRY=1
# (swap0438b.sh's dry run on copies): the source copies only, no binary, no archive.
# The restored sources are touched, so the next ninja in backend-ubuntu and in both host builds recompiles them (the
# restored archive and binaries are the old ones byte for byte until then).
# Without a rebuild every part can be turned off per run: KYTY_BC5_0438_A1=0, KYTY_BC5_0438_A1P=0, BC5_DIRECT_0438_A2=0,
# BC5_0438_INFLIGHT_NG=0, BC5_0438_OPEN_NG=0. One step further back is r438o's undo (bash
# ~/bc5-work/exp0438/r438okit/bake/undo0438o.sh), run after this one, never before.
# usage (on the box): bash undo0438b.sh
set -u
export LC_ALL=C
W=${UNDO_W:-$HOME/bc5-work}; K=${UNDO_K:-$HOME/src/KytyPlus}; B=${UNDO_B:-$W/d19/export/backend}; X=${X:-$W/exp0438/swapb}; DRY=${UNDO_DRY:-0}
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH_PATH=$W/backend-ubuntu/libbc5_backend.a
m8() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "undo0438b: an emulator runs: NOT DONE"; exit 1; }
[ -s "$X/pins.before-0438b" ] && [ -s "$X/units.md5" ] && [ -s "$X/be.md5" ] || { echo "undo0438b: no copies in $X"; exit 1; }
if [ "${UNDO_IN_INT:-0}" != 1 ]; then
  . "$W/exp0413/n/chainlock0417.inc"
  chain_claim "exp 0438: undo of bake438b (back to patch 0fede35d, archive d6638808; copies only, no emulator)" 5 || { echo "undo0438b: no lock: NOT DONE"; exit 1; }
  trap chain_release EXIT
fi
PIN_OLD=; ARCH_OLD=; BENEW=; NORMAL=; LEAN=; ARCH=
. "$X/pins.before-0438b"
[ -n "$PIN_OLD" ] && [ -n "$ARCH_OLD" ] && [ -n "$BENEW" ] || { echo "undo0438b: the pins file is incomplete: NOT DONE"; exit 1; }
[ "$DRY" = 1 ] || { [ -n "$NORMAL" ] && [ -n "$LEAN" ] && [ -n "$ARCH" ]; } || { echo "undo0438b: the pins file is incomplete: NOT DONE"; exit 1; }
(cd "$X/units" && md5sum -c --quiet "$X/units.md5") && (cd "$X/be" && md5sum -c --quiet "$X/be.md5") || { echo "undo0438b: the copies do not match their md5 lists: NOT DONE"; exit 1; }
if [ "$DRY" != 1 ]; then
    [ "$(m8 "$X/kyty_emulator.normal.before-0438b")" = "$NORMAL" ] && [ "$(m8 "$X/kyty_emulator.lean.before-0438b")" = "$LEAN" ] \
        && [ "$(m8 "$X/libbc5_backend.a.before-0438b")" = "$ARCH" ] || { echo "undo0438b: the binary copies do not match the pins: NOT DONE"; exit 1; }
fi
ok=1
while read -r _ u; do
    u=${u#\*}
    cp "$X/units/$u" "$K/$u" && touch "$K/$u" || { echo "undo0438b: cannot restore $u"; ok=0; }
done < "$X/units.md5"
while read -r _ u; do
    u=${u#\*}
    cp "$X/be/$u" "$B/$u" && touch "$B/$u" || { echo "undo0438b: cannot restore the backend's $u"; ok=0; }
done < "$X/be.md5"
rm -f "$B/$BENEW" || { echo "undo0438b: cannot remove $B/$BENEW"; ok=0; }
if [ "$DRY" != 1 ]; then
    cp -p "$X/libbc5_backend.a.before-0438b" "$ARCH_PATH" && cp -p "$X/kyty_emulator.normal.before-0438b" "$NB" && cp -p "$X/kyty_emulator.lean.before-0438b" "$LB" \
        || { echo "undo0438b: a copy failed"; ok=0; }
fi
d=$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)
[ "$d" = "$PIN_OLD" ] || { echo "undo0438b: the tree's diff is $d, not $PIN_OLD"; ok=0; }
(cd "$K" && md5sum -c --quiet "$X/units.md5") || { echo "undo0438b: the host files do not read back"; ok=0; }
(cd "$B" && md5sum -c --quiet "$X/be.md5") || { echo "undo0438b: the backend files do not read back"; ok=0; }
[ -e "$B/$BENEW" ] && { echo "undo0438b: $B/$BENEW is still there"; ok=0; }
if [ "$DRY" != 1 ]; then
    [ "$(m8 "$ARCH_PATH")" = "$ARCH_OLD" ] || { echo "undo0438b: the archive is $(m8 "$ARCH_PATH"), not $ARCH_OLD"; ok=0; }
    [ "$(m8 "$NB")" = "$NORMAL" ] || { echo "undo0438b: normal is $(m8 "$NB"), not $NORMAL"; ok=0; }
    [ "$(m8 "$LB")" = "$LEAN" ] || { echo "undo0438b: lean is $(m8 "$LB"), not $LEAN"; ok=0; }
fi
[ $ok = 1 ] && echo "undo0438b: back: patch $PIN_OLD$([ "$DRY" = 1 ] && echo " (dry run: the copies only)" || echo ", archive $ARCH_OLD, normal $NORMAL, lean $LEAN (the sources are touched, so the next ninja recompiles them); further back: bash $W/exp0438/r438okit/bake/undo0438o.sh")"
[ $ok = 1 ]
