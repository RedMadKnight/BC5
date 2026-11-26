#!/usr/bin/env bash
# BC5 exp 0428: puts the shared tree's bc5LleAgc.cpp and switch_defaults.hpp and both shared binaries back as they were
# before int0428b.sh (patch 2c82a979: normal 3f22e0e1, lean 35a3753d), and checks all four by md5 (exp 0425's undo0425.sh,
# adapted; source paths are *_PATH, the pins file sets U1=/U2= to md5s, LESSONS R10). No emulator may run. Run alone it
# takes its own BOX-LOCK slot; from int0428.sh (UNDO_IN_INT=1) it runs in int's slot. One step further back is exp 0425's
# own undo (bash ~/bc5-work/exp0425/undo0425.sh), run after this one, never before. A quicker rollback without a build:
# BC5_DIRECT_ACB_RINGS=0 in the environment.
# usage (on the box): bash ~/bc5-work/exp0428/undo0428.sh   (X=<dir> for a stand-in test)
set -u
export LC_ALL=C
W=${UNDO_W:-$HOME/bc5-work}; K=${UNDO_K:-$HOME/src/KytyPlus}; X=${X:-$W/exp0428/swap2}
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator
U1_PATH=$K/src/libs/bc5LleAgc.cpp; U2_PATH=$K/src/bc5/switch_defaults.hpp
m8() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "undo0428b: an emulator runs: NOT DONE"; exit 1; }
[ -s "$X/pins.before-0428b" ] || { echo "undo0428b: no copies in $X"; exit 1; }
if [ "${UNDO_IN_INT:-0}" != 1 ]; then
  . "$W/exp0413/n/chainlock0417.inc"
  chain_claim "exp 0428: undo of the second swap (back to patch 2c82a979; copies only, no emulator)" 5 || { echo "undo0428b: no lock: NOT DONE"; exit 1; }
  trap chain_release EXIT
fi
PIN_OLD=; NORMAL=; LEAN=; U1=; U2=
. "$X/pins.before-0428b"
[ -n "$PIN_OLD" ] && [ -n "$NORMAL" ] && [ -n "$LEAN" ] && [ -n "$U1" ] && [ -n "$U2" ] || { echo "undo0428b: the pins file is incomplete: NOT DONE"; exit 1; }
cp "$X/bc5LleAgc.cpp.before-0428b" "$U1_PATH" && touch "$U1_PATH" && cp "$X/switch_defaults.hpp.before-0428b" "$U2_PATH" && touch "$U2_PATH" \
  && cp -p "$X/kyty_emulator.normal.before-0428b" "$NB" && cp -p "$X/kyty_emulator.lean.before-0428b" "$LB" || { echo "undo0428b: a copy failed"; exit 1; }
d=$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)
ok=1
[ "$d" = "$PIN_OLD" ] || { echo "undo0428b: the tree's diff is $d, not $PIN_OLD"; ok=0; }
[ "$(m8 "$U1_PATH")" = "$U1" ] || { echo "undo0428b: bc5LleAgc.cpp is $(m8 "$U1_PATH"), not $U1"; ok=0; }
[ "$(m8 "$U2_PATH")" = "$U2" ] || { echo "undo0428b: switch_defaults.hpp is $(m8 "$U2_PATH"), not $U2"; ok=0; }
[ "$(m8 "$NB")" = "$NORMAL" ] || { echo "undo0428b: normal is $(m8 "$NB"), not $NORMAL"; ok=0; }
[ "$(m8 "$LB")" = "$LEAN" ] || { echo "undo0428b: lean is $(m8 "$LB"), not $LEAN"; ok=0; }
[ $ok = 1 ] && echo "undo0428b: back: patch $PIN_OLD, bc5LleAgc.cpp $U1, switch_defaults.hpp $U2, normal $NORMAL, lean $LEAN (the units are touched, so the next ninja recompiles them); further back: bash $W/exp0428/undo0428.sh"
[ $ok = 1 ]
