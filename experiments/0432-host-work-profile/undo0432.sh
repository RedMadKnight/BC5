#!/usr/bin/env bash
# BC5 exp 0432: puts the shared tree's four host units, the shared backend's direct.cpp, the backend archive and both
# shared binaries back as they were before int0432.sh (patch bc39a035: normal 0de9349b, lean 63fda02d, archive
# 1423af83), and checks all of them by md5 (exp 0430's undo0430.sh, adapted). No emulator may run. Run alone it takes
# its own BOX-LOCK slot; from int0432.sh (UNDO_IN_INT=1) it runs in int's slot. One step further back is exp 0429's own
# undo (bash ~/bc5-work/exp0429/undo0429.sh), run after this one, never before.
# usage (on the box): bash ~/bc5-work/exp0432/undo0432.sh   (X=<dir>, UNDO_W, UNDO_K, UNDO_BES, UNDO_REV for a stand-in test)
set -u
export LC_ALL=C
W=${UNDO_W:-$HOME/bc5-work}; K=${UNDO_K:-$HOME/src/KytyPlus}; X=${X:-$W/exp0432/swap}; REV=${UNDO_REV:-f266548}
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator
BES=${UNDO_BES:-$W/d19/export/backend}; U5_PATH=$BES/src/direct.cpp; ARCH_PATH=$W/backend-ubuntu/libbc5_backend.a
UN=(src/libs/bc5LleAgc.cpp src/common/platform/sysLinuxVirtual.cpp src/libs/libAmpr.cpp src/bc5/anon_sync.hpp)
m8() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "undo0432: an emulator runs: NOT DONE"; exit 1; }
[ -s "$X/pins.before-0432" ] || { echo "undo0432: no copies in $X"; exit 1; }
if [ "${UNDO_IN_INT:-0}" != 1 ]; then
  . "$W/exp0413/n/chainlock0417.inc"
  chain_claim "exp 0432: undo of the host-work swap (back to patch bc39a035; copies only, no emulator)" 5 || { echo "undo0432: no lock: NOT DONE"; exit 1; }
  trap chain_release EXIT
fi
PIN_OLD=; NORMAL=; LEAN=; ARCH=; U1=; U2=; U3=; U4=; U5=
. "$X/pins.before-0432"
[ -n "$PIN_OLD" ] && [ -n "$NORMAL" ] && [ -n "$LEAN" ] && [ -n "$ARCH" ] && [ -n "$U1" ] && [ -n "$U2" ] && [ -n "$U3" ] && [ -n "$U4" ] && [ -n "$U5" ] \
  || { echo "undo0432: the pins file is incomplete: NOT DONE"; exit 1; }
UP=("$U1" "$U2" "$U3" "$U4")
for f in kyty_emulator.normal kyty_emulator.lean direct.cpp libbc5_backend.a bc5LleAgc.cpp sysLinuxVirtual.cpp libAmpr.cpp anon_sync.hpp; do
    [ -s "$X/$f.before-0432" ] || { echo "undo0432: $X/$f.before-0432 is missing: NOT DONE"; exit 1; }
done
for i in 0 1 2 3; do cp "$X/$(basename "${UN[$i]}").before-0432" "$K/${UN[$i]}" && touch "$K/${UN[$i]}" || { echo "undo0432: a copy failed (${UN[$i]})"; exit 1; }; done
cp -p "$X/kyty_emulator.normal.before-0432" "$NB" && cp -p "$X/kyty_emulator.lean.before-0432" "$LB" \
  && cp "$X/direct.cpp.before-0432" "$U5_PATH" && touch "$U5_PATH" && cp -p "$X/libbc5_backend.a.before-0432" "$ARCH_PATH" || { echo "undo0432: a copy failed"; exit 1; }
d=$(git -C "$K" diff --no-color "$REV" | md5sum | cut -c1-8)
ok=1
[ "$d" = "$PIN_OLD" ] || { echo "undo0432: the tree's diff is $d, not $PIN_OLD"; ok=0; }
for i in 0 1 2 3; do [ "$(m8 "$K/${UN[$i]}")" = "${UP[$i]}" ] || { echo "undo0432: ${UN[$i]} is $(m8 "$K/${UN[$i]}"), not ${UP[$i]}"; ok=0; }; done
[ "$(m8 "$NB")" = "$NORMAL" ] || { echo "undo0432: normal is $(m8 "$NB"), not $NORMAL"; ok=0; }
[ "$(m8 "$LB")" = "$LEAN" ] || { echo "undo0432: lean is $(m8 "$LB"), not $LEAN"; ok=0; }
[ "$(m8 "$U5_PATH")" = "$U5" ] || { echo "undo0432: direct.cpp is $(m8 "$U5_PATH"), not $U5"; ok=0; }
[ "$(m8 "$ARCH_PATH")" = "$ARCH" ] || { echo "undo0432: the archive is $(m8 "$ARCH_PATH"), not $ARCH"; ok=0; }
[ $ok = 1 ] && echo "undo0432: back: patch $PIN_OLD, normal $NORMAL, lean $LEAN, archive $ARCH, direct.cpp $U5, the four host units (the sources are touched, so the next ninja recompiles them); further back: bash $W/exp0429/undo0429.sh"
[ $ok = 1 ]
