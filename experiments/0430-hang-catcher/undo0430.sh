#!/usr/bin/env bash
# BC5 exp 0430: puts the shared tree's bc5LleAgc.cpp and switch_defaults.hpp and both shared binaries back as they were
# before int0430.sh (patch a8717e53: normal dae7bf0b, lean 819f3b05), and checks all four by md5 (exp 0425's undo0425.sh,
# adapted; source paths are *_PATH, the pins file sets U1=/U2= to md5s, LESSONS R10). No emulator may run. Run alone it
# takes its own BOX-LOCK slot; from int0430.sh (UNDO_IN_INT=1) it runs in int's slot. One step further back is exp 0428's
# own undo (bash ~/bc5-work/exp0428/undo0428b.sh), run after this one, never before. A quicker rollback without a build:
# BC5_DIRECT_XQ_ACQUIRE=0 BC5_DIRECT_XQ_PENDING=0 in the environment.
# usage (on the box): bash ~/bc5-work/exp0430/undo0430.sh   (X=<dir> for a stand-in test)
set -u
export LC_ALL=C
W=${UNDO_W:-$HOME/bc5-work}; K=${UNDO_K:-$HOME/src/KytyPlus}; X=${X:-$W/exp0430/swap}
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator
U1_PATH=$K/src/libs/bc5LleAgc.cpp; U2_PATH=$K/src/bc5/switch_defaults.hpp
BES=${UNDO_BES:-$W/d19/export/backend}; U3_PATH=$BES/src/direct.cpp; U4_PATH=$BES/include/bc5/direct.hpp; ARCH_PATH=$W/backend-ubuntu/libbc5_backend.a
m8() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "undo0430: an emulator runs: NOT DONE"; exit 1; }
[ -s "$X/pins.before-0430" ] || { echo "undo0430: no copies in $X"; exit 1; }
if [ "${UNDO_IN_INT:-0}" != 1 ]; then
  . "$W/exp0413/n/chainlock0417.inc"
  chain_claim "exp 0430: undo of the hang-fix swap (back to patch a8717e53; copies only, no emulator)" 5 || { echo "undo0430: no lock: NOT DONE"; exit 1; }
  trap chain_release EXIT
fi
PIN_OLD=; NORMAL=; LEAN=; U1=; U2=; U3=; U4=; ARCH=
. "$X/pins.before-0430"
[ -n "$PIN_OLD" ] && [ -n "$NORMAL" ] && [ -n "$LEAN" ] && [ -n "$U1" ] && [ -n "$U2" ] && [ -n "$U3" ] && [ -n "$U4" ] && [ -n "$ARCH" ] || { echo "undo0430: the pins file is incomplete: NOT DONE"; exit 1; }
cp "$X/bc5LleAgc.cpp.before-0430" "$U1_PATH" && touch "$U1_PATH" && cp "$X/switch_defaults.hpp.before-0430" "$U2_PATH" && touch "$U2_PATH" \
  && cp -p "$X/kyty_emulator.normal.before-0430" "$NB" && cp -p "$X/kyty_emulator.lean.before-0430" "$LB" \
  && cp "$X/direct.cpp.before-0430" "$U3_PATH" && touch "$U3_PATH" && cp "$X/direct.hpp.before-0430" "$U4_PATH" && touch "$U4_PATH" \
  && cp -p "$X/libbc5_backend.a.before-0430" "$ARCH_PATH" || { echo "undo0430: a copy failed"; exit 1; }
d=$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)
ok=1
[ "$d" = "$PIN_OLD" ] || { echo "undo0430: the tree's diff is $d, not $PIN_OLD"; ok=0; }
[ "$(m8 "$U1_PATH")" = "$U1" ] || { echo "undo0430: bc5LleAgc.cpp is $(m8 "$U1_PATH"), not $U1"; ok=0; }
[ "$(m8 "$U2_PATH")" = "$U2" ] || { echo "undo0430: switch_defaults.hpp is $(m8 "$U2_PATH"), not $U2"; ok=0; }
[ "$(m8 "$NB")" = "$NORMAL" ] || { echo "undo0430: normal is $(m8 "$NB"), not $NORMAL"; ok=0; }
[ "$(m8 "$LB")" = "$LEAN" ] || { echo "undo0430: lean is $(m8 "$LB"), not $LEAN"; ok=0; }
[ "$(m8 "$U3_PATH")" = "$U3" ] || { echo "undo0430: direct.cpp is $(m8 "$U3_PATH"), not $U3"; ok=0; }
[ "$(m8 "$U4_PATH")" = "$U4" ] || { echo "undo0430: direct.hpp is $(m8 "$U4_PATH"), not $U4"; ok=0; }
[ "$(m8 "$ARCH_PATH")" = "$ARCH" ] || { echo "undo0430: the archive is $(m8 "$ARCH_PATH"), not $ARCH"; ok=0; }
[ $ok = 1 ] && echo "undo0430: back: patch $PIN_OLD, bc5LleAgc.cpp $U1, switch_defaults.hpp $U2, normal $NORMAL, lean $LEAN (the units are touched, so the next ninja recompiles them); further back: bash $W/exp0428/undo0428b.sh"
[ $ok = 1 ]
