#!/usr/bin/env bash
# BC5 exp 0429: puts the shared tree's three units and both shared binaries back as they were before int0429r.sh (R on
# by default, the wake slice removed): patch 940e8f36, normal 4e0c00a2, lean 272685ee (archive 6eac453e, which the swap
# does not touch), and checks each by md5 (undo0429.sh's pattern). No emulator may run. Run alone it takes its own
# BOX-LOCK slot; from int0429r.sh (UNDO_IN_INT=1) it runs in int's slot. One step further back is exp 0432's own undo.
# usage (on the box): bash ~/bc5-work/exp0429/undo0429r.sh   (X=<dir> for a stand-in test)
set -u
export LC_ALL=C
W=${UNDO_W:-$HOME/bc5-work}; K=${UNDO_K:-$HOME/src/KytyPlus}; X=${X:-$W/exp0429/swapR}
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
m8() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "undo0429r: an emulator runs: NOT DONE"; exit 1; }
[ -s "$X/pins.before-0429r" ] || { echo "undo0429r: no copies in $X"; exit 1; }
if [ "${UNDO_IN_INT:-0}" != 1 ]; then
  . "$W/exp0413/n/chainlock0417.inc"
  chain_claim "exp 0429: undo of R on by default (back to patch 940e8f36; copies only, no emulator)" 5 || { echo "undo0429r: no lock: NOT DONE"; exit 1; }
  trap chain_release EXIT
fi
PIN_OLD=; NORMAL=; LEAN=; ARCH_PIN=
eval "$(grep -E '^(PIN_OLD|NORMAL|LEAN)=[0-9a-f]*$' "$X/pins.before-0429r")"
ARCH_PIN=$(grep -E '^ARCH=[0-9a-f]*$' "$X/pins.before-0429r" | cut -d= -f2)
nu=$(grep -c '^UNIT [0-9a-f]\{8\} src/' "$X/pins.before-0429r")
[ -n "$PIN_OLD" ] && [ -n "$NORMAL" ] && [ -n "$LEAN" ] && [ "$nu" = 3 ] || { echo "undo0429r: the pins file is incomplete: NOT DONE"; exit 1; }
# every copy must exist before anything is written
while read -r _ h u; do [ -s "$X/units/$(basename "$u").before-0429r" ] || { echo "undo0429r: no copy of $u: NOT DONE"; exit 1; }; done < <(grep '^UNIT ' "$X/pins.before-0429r")
[ -s "$X/kyty_emulator.normal.before-0429r" ] && [ -s "$X/kyty_emulator.lean.before-0429r" ] || { echo "undo0429r: no binary copies: NOT DONE"; exit 1; }
while read -r _ h u; do
  cp "$X/units/$(basename "$u").before-0429r" "$K/$u" && touch "$K/$u" || { echo "undo0429r: copy of $u failed"; exit 1; }
done < <(grep '^UNIT ' "$X/pins.before-0429r")
cp -p "$X/kyty_emulator.normal.before-0429r" "$NB" && cp -p "$X/kyty_emulator.lean.before-0429r" "$LB" || { echo "undo0429r: a binary copy failed"; exit 1; }
ok=1
d=$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)
[ "$d" = "$PIN_OLD" ] || { echo "undo0429r: the tree's diff is $d, not $PIN_OLD"; ok=0; }
while read -r _ h u; do [ "$(m8 "$K/$u")" = "$h" ] || { echo "undo0429r: $u is $(m8 "$K/$u"), not $h"; ok=0; }; done < <(grep '^UNIT ' "$X/pins.before-0429r")
[ "$(m8 "$NB")" = "$NORMAL" ] || { echo "undo0429r: normal is $(m8 "$NB"), not $NORMAL"; ok=0; }
[ "$(m8 "$LB")" = "$LEAN" ] || { echo "undo0429r: lean is $(m8 "$LB"), not $LEAN"; ok=0; }
[ -z "$ARCH_PIN" ] || [ "$(m8 "$ARCH")" = "$ARCH_PIN" ] || { echo "undo0429r: the archive is $(m8 "$ARCH"), not $ARCH_PIN"; ok=0; }
[ $ok = 1 ] && echo "undo0429r: back: patch $PIN_OLD, $nu units, normal $NORMAL, lean $LEAN, archive ${ARCH_PIN:-?} (the units are touched, so the next ninja recompiles them)"
[ $ok = 1 ]
