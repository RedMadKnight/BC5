#!/usr/bin/env bash
# BC5 exp 0431: puts the shared tree's bc5LleAgc.cpp and switch_defaults.hpp and both shared binaries back as they were
# before int0431.sh (patch a7c1653d, exp 0430: normal bf3f5f00, lean 0fb7bed5; way 2 for the second title only), and checks all
# four by md5 (exp 0428's undo0428b.sh, adapted; source paths are *_PATH, the pins file sets U1=/U2= to md5s, LESSONS R10
# 0425/undo). No emulator may run. Run alone it takes its own BOX-LOCK slot; from int0431.sh (UNDO_IN_INT=1) it runs in
# int's slot. One step further back is exp 0430's own undo (bash ~/bc5-work/exp0430/undo0430.sh), run after this one,
# never before. A quicker rollback without a build: BC5_DIRECT_ACB_RINGS=0 in the environment (way 2 off for a run).
# usage (on the box): bash ~/bc5-work/exp0431/undo0431.sh   (X=<dir> for a stand-in test)
set -u
export LC_ALL=C
W=${UNDO_W:-$HOME/bc5-work}; K=${UNDO_K:-$HOME/src/KytyPlus}; X=${X:-$W/exp0431/swap}
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator
U1_PATH=$K/src/libs/bc5LleAgc.cpp; U2_PATH=$K/src/bc5/switch_defaults.hpp
m8() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "undo0431: an emulator runs: NOT DONE"; exit 1; }
[ -s "$X/pins.before-0431" ] || { echo "undo0431: no copies in $X"; exit 1; }
if [ "${UNDO_IN_INT:-0}" != 1 ]; then
  . "$W/exp0413/n/chainlock0417.inc"
  chain_claim "exp 0431: undo of way 2 for every title (back to patch a7c1653d; copies only, no emulator)" 5 || { echo "undo0431: no lock: NOT DONE"; exit 1; }
  trap chain_release EXIT
fi
PIN_OLD=; NORMAL=; LEAN=; U1=; U2=
. "$X/pins.before-0431"
[ -n "$PIN_OLD" ] && [ -n "$NORMAL" ] && [ -n "$LEAN" ] && [ -n "$U1" ] && [ -n "$U2" ] || { echo "undo0431: the pins file is incomplete: NOT DONE"; exit 1; }
cp "$X/bc5LleAgc.cpp.before-0431" "$U1_PATH" && touch "$U1_PATH" && cp "$X/switch_defaults.hpp.before-0431" "$U2_PATH" && touch "$U2_PATH" \
  && cp -p "$X/kyty_emulator.normal.before-0431" "$NB" && cp -p "$X/kyty_emulator.lean.before-0431" "$LB" || { echo "undo0431: a copy failed"; exit 1; }
d=$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)
ok=1
[ "$d" = "$PIN_OLD" ] || { echo "undo0431: the tree's diff is $d, not $PIN_OLD"; ok=0; }
[ "$(m8 "$U1_PATH")" = "$U1" ] || { echo "undo0431: bc5LleAgc.cpp is $(m8 "$U1_PATH"), not $U1"; ok=0; }
[ "$(m8 "$U2_PATH")" = "$U2" ] || { echo "undo0431: switch_defaults.hpp is $(m8 "$U2_PATH"), not $U2"; ok=0; }
[ "$(m8 "$NB")" = "$NORMAL" ] || { echo "undo0431: normal is $(m8 "$NB"), not $NORMAL"; ok=0; }
[ "$(m8 "$LB")" = "$LEAN" ] || { echo "undo0431: lean is $(m8 "$LB"), not $LEAN"; ok=0; }
[ $ok = 1 ] && echo "undo0431: back: patch $PIN_OLD, bc5LleAgc.cpp $U1, switch_defaults.hpp $U2, normal $NORMAL, lean $LEAN (the units are touched, so the next ninja recompiles them); further back: bash $W/exp0430/undo0430.sh"
[ $ok = 1 ]
