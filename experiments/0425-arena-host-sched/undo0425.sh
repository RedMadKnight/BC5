#!/usr/bin/env bash
# BC5 exp 0425: puts the shared tree's pthread.cpp and switch_defaults.hpp and both shared binaries back as they were
# before int0425.sh (patch 4945ef1b, exp 0422's state: normal 9da2a9d5, lean f942676c), and checks all four by md5. No
# emulator may run. One step further back is exp 0422's own undo (bash ~/bc5-work/exp0422/undo0422.sh, to e3fd8b55),
# run after this one, never before. A quicker rollback without a build: KYTY_BC5_0425_WAKE_SLICE_US=0 in the environment.
# Fixed 2026-11-16 (Codex 10:07 UTC, confirmed): the first version named the source paths U1/U2, and the pins file it
# sources sets U1=/U2= to md5s, so the copies went to files named by those sums. Paths are now *_PATH; the pins are
# checked complete; run alone it takes its own BOX-LOCK slot, from int0425.sh (UNDO_IN_INT=1) it runs in int's slot.
# usage (on the box): bash ~/bc5-work/exp0425/undo0425.sh
set -u
export LC_ALL=C
W=$HOME/bc5-work; K=$HOME/src/KytyPlus; X=$W/exp0425/swap
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator
U1_PATH=$K/src/kernel/pthread.cpp; U2_PATH=$K/src/bc5/switch_defaults.hpp
m8() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "undo0425: an emulator runs: NOT DONE"; exit 1; }
[ -s "$X/pins.before-0425" ] || { echo "undo0425: no copies in $X"; exit 1; }
if [ "${UNDO_IN_INT:-0}" != 1 ]; then
  . "$W/exp0413/n/chainlock0417.inc"
  chain_claim "exp 0425: undo of the shared C1 swap (back to patch 4945ef1b; copies only, no emulator)" 5 || { echo "undo0425: no lock: NOT DONE"; exit 1; }
  trap chain_release EXIT
fi
PIN_OLD=; NORMAL=; LEAN=; U1=; U2=
. "$X/pins.before-0425"
[ -n "$PIN_OLD" ] && [ -n "$NORMAL" ] && [ -n "$LEAN" ] && [ -n "$U1" ] && [ -n "$U2" ] || { echo "undo0425: the pins file is incomplete: NOT DONE"; exit 1; }
cp "$X/pthread.cpp.before-0425" "$U1_PATH" && touch "$U1_PATH" && cp "$X/switch_defaults.hpp.before-0425" "$U2_PATH" && touch "$U2_PATH" \
  && cp -p "$X/kyty_emulator.normal.before-0425" "$NB" && cp -p "$X/kyty_emulator.lean.before-0425" "$LB" || { echo "undo0425: a copy failed"; exit 1; }
d=$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)
ok=1
[ "$d" = "$PIN_OLD" ] || { echo "undo0425: the tree's diff is $d, not $PIN_OLD"; ok=0; }
[ "$(m8 "$U1_PATH")" = "$U1" ] || { echo "undo0425: pthread.cpp is $(m8 "$U1_PATH"), not $U1"; ok=0; }
[ "$(m8 "$U2_PATH")" = "$U2" ] || { echo "undo0425: switch_defaults.hpp is $(m8 "$U2_PATH"), not $U2"; ok=0; }
[ "$(m8 "$NB")" = "$NORMAL" ] || { echo "undo0425: normal is $(m8 "$NB"), not $NORMAL"; ok=0; }
[ "$(m8 "$LB")" = "$LEAN" ] || { echo "undo0425: lean is $(m8 "$LB"), not $LEAN"; ok=0; }
[ $ok = 1 ] && echo "undo0425: back: patch $PIN_OLD, pthread.cpp $U1, switch_defaults.hpp $U2, normal $NORMAL, lean $LEAN (the units are touched, so the next ninja recompiles them from the old text); further back: bash $W/exp0422/undo0422.sh"
[ $ok = 1 ]
