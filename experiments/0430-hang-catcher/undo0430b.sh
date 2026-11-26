#!/usr/bin/env bash
# BC5 exp 0430: puts the shared tree's bc5LleAgc.cpp and both shared binaries back as they were before int0430b.sh (patch
# ef2ff54f: normal a9b4f00b, lean abf5fb17, unit f574f460) and checks them and the archive by md5 (undo0430.sh adapted; the
# pins file sets the md5s, LESSONS R10). No emulator may run. Run alone it takes its own BOX-LOCK slot; from int0430b.sh
# (UNDO_IN_INT=1) it runs in int's slot. One step further back is exp 0429's own undo (bash ~/bc5-work/exp0429/undo0429r.sh),
# run after this one, never before. There is no rollback by a word: the fix has no switch.
# usage (on the box): bash undo0430b.sh   (X=<dir> UNDO_W=<dir> UNDO_K=<dir> for a stand-in test)
set -u
export LC_ALL=C
W=${UNDO_W:-$HOME/bc5-work}; K=${UNDO_K:-$HOME/src/KytyPlus}; X=${X:-$W/exp0430/swapb}
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH_PATH=$W/backend-ubuntu/libbc5_backend.a
U1_PATH=$K/src/libs/bc5LleAgc.cpp
m8() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "undo0430b: an emulator runs: NOT DONE"; exit 1; }
[ -s "$X/pins.before-0430b" ] || { echo "undo0430b: no copies in $X"; exit 1; }
if [ "${UNDO_IN_INT:-0}" != 1 ]; then
  . "$W/exp0413/n/chainlock0417.inc"
  chain_claim "exp 0430: undo of the built-in hang fix (back to patch ef2ff54f; copies only, no emulator)" 5 || { echo "undo0430b: no lock: NOT DONE"; exit 1; }
  trap chain_release EXIT
fi
PIN_OLD=; NORMAL=; LEAN=; U1=; ARCH=
. "$X/pins.before-0430b"
[ -n "$PIN_OLD" ] && [ -n "$NORMAL" ] && [ -n "$LEAN" ] && [ -n "$U1" ] && [ -n "$ARCH" ] || { echo "undo0430b: the pins file is incomplete: NOT DONE"; exit 1; }
cp "$X/bc5LleAgc.cpp.before-0430b" "$U1_PATH" && touch "$U1_PATH" \
  && cp -p "$X/kyty_emulator.normal.before-0430b" "$NB" && cp -p "$X/kyty_emulator.lean.before-0430b" "$LB" || { echo "undo0430b: a copy failed"; exit 1; }
d=$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)
ok=1
[ "$d" = "$PIN_OLD" ] || { echo "undo0430b: the tree's diff is $d, not $PIN_OLD"; ok=0; }
[ "$(m8 "$U1_PATH")" = "$U1" ] || { echo "undo0430b: bc5LleAgc.cpp is $(m8 "$U1_PATH"), not $U1"; ok=0; }
[ "$(m8 "$NB")" = "$NORMAL" ] || { echo "undo0430b: normal is $(m8 "$NB"), not $NORMAL"; ok=0; }
[ "$(m8 "$LB")" = "$LEAN" ] || { echo "undo0430b: lean is $(m8 "$LB"), not $LEAN"; ok=0; }
[ "$(m8 "$ARCH_PATH")" = "$ARCH" ] || { echo "undo0430b: the archive is $(m8 "$ARCH_PATH"), not $ARCH (int0430b.sh never writes it)"; ok=0; }
[ $ok = 1 ] && echo "undo0430b: back: patch $PIN_OLD, bc5LleAgc.cpp $U1, normal $NORMAL, lean $LEAN (the unit is touched, so the next ninja recompiles it); further back: bash $W/exp0429/undo0429r.sh"
[ $ok = 1 ]
