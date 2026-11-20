#!/usr/bin/env bash
# BC5 exp 0436: puts everything swap0436.sh changed back as it was before it (patch 8986853b, normal 99f2a567, lean
# 82720cca, archive 51db2c91): the unit the change edits, the shared backend source's direct.cpp and direct.hpp, the
# archive and both binaries, each checked by md5 against the copies and the pins file (swap0436.sh's format: PIN_OLD,
# CPP, HPP, NORMAL, LEAN, ARCH). No emulator may run. Run alone it takes its own BOX-LOCK slot; from swap0436.sh
# (UNDO_IN_INT=1) it runs in int's slot. UNDO_DRY=1 (from swap0436.sh's dry run on copies): the unit and the backend
# source only, no binary, no archive.
# One step further back is exp 0434's own undo (bash ~/bc5-work/exp0434/bake/undo0434.sh), run after this one, never
# before. There is no rollback by a word: the change has no switch.
# usage (on the box): bash undo0436.sh
set -u
export LC_ALL=C
W=${UNDO_W:-$HOME/bc5-work}; K=${UNDO_K:-$HOME/src/KytyPlus}; X=${X:-$W/exp0436/swap}; DRY=${UNDO_DRY:-0}
BES=${UNDO_BES:-$W/d19/export/backend}; CPP_PATH=$BES/src/direct.cpp; HPP_PATH=$BES/include/bc5/direct.hpp
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; ARCH_PATH=$W/backend-ubuntu/libbc5_backend.a
m8() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "undo0436: an emulator runs: NOT DONE"; exit 1; }
[ -s "$X/pins.before-0436" ] && [ -s "$X/units.md5" ] || { echo "undo0436: no copies in $X"; exit 1; }
if [ "${UNDO_IN_INT:-0}" != 1 ]; then
  . "$W/exp0413/n/chainlock0417.inc"
  chain_claim "exp 0436: undo of the submit unlock built in (back to patch 8986853b; copies only, no emulator)" 5 || { echo "undo0436: no lock: NOT DONE"; exit 1; }
  trap chain_release EXIT
fi
PIN_OLD=; CPP=; HPP=; NORMAL=; LEAN=; ARCH=
. "$X/pins.before-0436"
[ -n "$PIN_OLD" ] && [ -n "$CPP" ] && [ -n "$HPP" ] || { echo "undo0436: the pins file is incomplete: NOT DONE"; exit 1; }
[ "$DRY" = 1 ] || { [ -n "$NORMAL" ] && [ -n "$LEAN" ] && [ -n "$ARCH" ]; } || { echo "undo0436: the pins file is incomplete: NOT DONE"; exit 1; }
(cd "$X/units" && md5sum -c --quiet "$X/units.md5") || { echo "undo0436: the unit copies do not match units.md5: NOT DONE"; exit 1; }
[ "$(m8 "$X/direct.cpp.before-0436")" = "$CPP" ] && [ "$(m8 "$X/direct.hpp.before-0436")" = "$HPP" ] || { echo "undo0436: the backend source copies do not match: NOT DONE"; exit 1; }
ok=1
while read -r _ u; do
    u=${u#\*}
    cp "$X/units/$u" "$K/$u" && touch "$K/$u" || { echo "undo0436: cannot restore $u"; ok=0; }
done < "$X/units.md5"
cp "$X/direct.cpp.before-0436" "$CPP_PATH" && touch "$CPP_PATH" && cp "$X/direct.hpp.before-0436" "$HPP_PATH" && touch "$HPP_PATH" || { echo "undo0436: cannot restore the backend source"; ok=0; }
if [ "$DRY" != 1 ]; then
    cp -p "$X/libbc5_backend.a.before-0436" "$ARCH_PATH" && cp -p "$X/kyty_emulator.normal.before-0436" "$NB" \
      && cp -p "$X/kyty_emulator.lean.before-0436" "$LB" || { echo "undo0436: a copy failed"; ok=0; }
fi
d=$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)
[ "$d" = "$PIN_OLD" ] || { echo "undo0436: the tree's diff is $d, not $PIN_OLD"; ok=0; }
(cd "$K" && md5sum -c --quiet "$X/units.md5") || { echo "undo0436: the units do not read back"; ok=0; }
[ "$(m8 "$CPP_PATH")" = "$CPP" ] && [ "$(m8 "$HPP_PATH")" = "$HPP" ] || { echo "undo0436: the backend source is $(m8 "$CPP_PATH") / $(m8 "$HPP_PATH"), not $CPP / $HPP"; ok=0; }
if [ "$DRY" != 1 ]; then
    [ "$(m8 "$ARCH_PATH")" = "$ARCH" ] || { echo "undo0436: the archive is $(m8 "$ARCH_PATH"), not $ARCH"; ok=0; }
    [ "$(m8 "$NB")" = "$NORMAL" ] || { echo "undo0436: normal is $(m8 "$NB"), not $NORMAL"; ok=0; }
    [ "$(m8 "$LB")" = "$LEAN" ] || { echo "undo0436: lean is $(m8 "$LB"), not $LEAN"; ok=0; }
fi
[ $ok = 1 ] && echo "undo0436: back: patch $PIN_OLD, direct.cpp $CPP, direct.hpp $HPP$([ "$DRY" = 1 ] && echo " (dry run: the copies only)" || echo ", archive $ARCH, normal $NORMAL, lean $LEAN (the sources are touched, so the next ninja recompiles them); further back: bash $W/exp0434/bake/undo0434.sh")"
[ $ok = 1 ]
