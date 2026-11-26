#!/usr/bin/env bash
# BC5 exp 0442 (tag bake442): puts everything swap0442.sh changed back as it was before it (patch 589ef163, normal 30546370,
# lean 05fd749d, archive a548a249): the four host files, src/bc5/idraws0442.hpp removed from the tree and the index, the
# backend's seven changed files and five deleted ones, the archive and both binaries, each checked by md5 against the
# copies and the pins file. No emulator may run.
# Run alone it takes its own BOX-LOCK slot; from swap0442.sh (UNDO_IN_INT=1) it runs in the swap's slot. UNDO_DRY=1
# (swap0442.sh's dry run on copies): the source copies only, no binary, no archive.
# The restored sources are touched, so the next ninja recompiles them (the restored archive and binaries are the old
# ones byte for byte until then). Without a rebuild each moved row can be turned off per run (NAME=0, as for kSoft);
# the removed learned code cannot be turned back on: that takes this undo. One step further back is bake438b's undo (bash ~/bc5-work/exp0438/bake438bkit/undo0438b.sh), run
# after this one, never before.
# usage (on the box): bash undo0442.sh
set -u
export LC_ALL=C
W=${UNDO_W:-$HOME/bc5-work}; K=${UNDO_K:-$HOME/src/KytyPlus}; B=${UNDO_B:-$W/d19/export/backend}; X=${X:-$W/exp0442/swap}; DRY=${UNDO_DRY:-0}
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH_PATH=$W/backend-ubuntu/libbc5_backend.a
m8() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "undo0442: an emulator runs: NOT DONE"; exit 1; }
[ -s "$X/pins.before-0442" ] && [ -s "$X/host.md5" ] && [ -s "$X/be.md5" ] || { echo "undo0442: no copies in $X"; exit 1; }
if [ "${UNDO_IN_INT:-0}" != 1 ]; then
  . "$W/exp0413/n/chainlock0417.inc"
  chain_claim "exp 0442: undo of bake442 (back to patch 589ef163, archive a548a249; copies only, no emulator)" 5 || { echo "undo0442: no lock: NOT DONE"; exit 1; }
  trap chain_release EXIT
fi
PIN_OLD=; ARCH_OLD=; ADD_P=; NORMAL=; LEAN=; ARCH=
. "$X/pins.before-0442"
[ -n "$PIN_OLD" ] && [ -n "$ARCH_OLD" ] && [ -n "$ADD_P" ] || { echo "undo0442: the pins file is incomplete: NOT DONE"; exit 1; }
[ "$DRY" = 1 ] || { [ -n "$NORMAL" ] && [ -n "$LEAN" ] && [ -n "$ARCH" ]; } || { echo "undo0442: the pins file is incomplete: NOT DONE"; exit 1; }
(cd "$X/host" && md5sum -c --quiet "$X/host.md5") && (cd "$X/be" && md5sum -c --quiet "$X/be.md5") || { echo "undo0442: the copies do not match their md5 lists: NOT DONE"; exit 1; }
if [ "$DRY" != 1 ]; then
    [ "$(m8 "$X/kyty_emulator.normal.before-0442")" = "$NORMAL" ] && [ "$(m8 "$X/kyty_emulator.lean.before-0442")" = "$LEAN" ] \
        && [ "$(m8 "$X/libbc5_backend.a.before-0442")" = "$ARCH" ] || { echo "undo0442: the binary copies do not match the pins: NOT DONE"; exit 1; }
fi
ok=1
while read -r _ u; do u=${u#\*}; cp "$X/host/$u" "$K/$u" && touch "$K/$u" || { echo "undo0442: cannot restore $u"; ok=0; }; done < "$X/host.md5"
if git -C "$K" ls-files --error-unmatch -- "$ADD_P" > /dev/null 2>&1; then git -C "$K" rm -q --cached -- "$ADD_P" || { echo "undo0442: cannot unstage $ADD_P"; ok=0; }; fi
rm -f "$K/$ADD_P" || { echo "undo0442: cannot remove $ADD_P"; ok=0; }
while read -r _ u; do u=${u#\*}; mkdir -p "$B/$(dirname "$u")" && cp "$X/be/$u" "$B/$u" && touch "$B/$u" || { echo "undo0442: cannot restore the backend's $u"; ok=0; }; done < "$X/be.md5"
if [ "$DRY" != 1 ]; then
    cp -p "$X/libbc5_backend.a.before-0442" "$ARCH_PATH" && cp -p "$X/kyty_emulator.normal.before-0442" "$NB" && cp -p "$X/kyty_emulator.lean.before-0442" "$LB" \
        || { echo "undo0442: a copy failed"; ok=0; }
fi
d=$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)
[ "$d" = "$PIN_OLD" ] || { echo "undo0442: the tree's diff is $d, not $PIN_OLD"; ok=0; }
(cd "$K" && md5sum -c --quiet "$X/host.md5") || { echo "undo0442: the host files do not read back"; ok=0; }
(cd "$B" && md5sum -c --quiet "$X/be.md5") || { echo "undo0442: the backend files do not read back"; ok=0; }
[ -e "$K/$ADD_P" ] && { echo "undo0442: $ADD_P is still there"; ok=0; }
if [ "$DRY" != 1 ]; then
    [ "$(m8 "$ARCH_PATH")" = "$ARCH_OLD" ] || { echo "undo0442: the archive is $(m8 "$ARCH_PATH"), not $ARCH_OLD"; ok=0; }
    [ "$(m8 "$NB")" = "$NORMAL" ] || { echo "undo0442: normal is $(m8 "$NB"), not $NORMAL"; ok=0; }
    [ "$(m8 "$LB")" = "$LEAN" ] || { echo "undo0442: lean is $(m8 "$LB"), not $LEAN"; ok=0; }
fi
[ $ok = 1 ] && echo "undo0442: back: patch $PIN_OLD$([ "$DRY" = 1 ] && echo " (dry run: the copies only)" || echo ", archive $ARCH_OLD, normal $NORMAL, lean $LEAN (the sources are touched, so the next ninja recompiles them)")"
[ $ok = 1 ]
