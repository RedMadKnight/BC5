#!/usr/bin/env bash
# BC5 exp 0421: puts the shared tree's main unit and both shared binaries back as they were before int0421.sh, and
# checks them by md5. No emulator may run. usage (on the box): bash ~/bc5-work/exp0421/undo0421.sh
set -u
export LC_ALL=C
W=$HOME/bc5-work; K=$HOME/src/KytyPlus; X=$W/exp0421/swap
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; UNIT=$K/src/libs/bc5LleAgc.cpp
m8() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "undo0421: an emulator runs: NOT DONE"; exit 1; }
[ -s "$X/pins.before-0421" ] || { echo "undo0421: no copies in $X"; exit 1; }
. "$X/pins.before-0421"
cp "$X/bc5LleAgc.cpp.before-0421" "$UNIT" && touch "$UNIT" && cp -p "$X/kyty_emulator.normal.before-0421" "$NB" && cp -p "$X/kyty_emulator.lean.before-0421" "$LB" || { echo "undo0421: a copy failed"; exit 1; }
d=$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)
ok=1
[ "$d" = "$PIN_OLD" ] || { echo "undo0421: the tree's diff is $d, not $PIN_OLD"; ok=0; }
[ "$(m8 "$NB")" = "$NORMAL" ] || { echo "undo0421: normal is $(m8 "$NB"), not $NORMAL"; ok=0; }
[ "$(m8 "$LB")" = "$LEAN" ] || { echo "undo0421: lean is $(m8 "$LB"), not $LEAN"; ok=0; }
[ $ok = 1 ] && echo "undo0421: back: patch $PIN_OLD, normal $NORMAL, lean $LEAN (the unit is touched, so the next ninja recompiles it from the old text)"
[ $ok = 1 ]
