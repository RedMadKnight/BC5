#!/usr/bin/env bash
# BC5 exp 0429: puts the shared tree's units, the deleted src/bc5/job_arena_fix.hpp, both shared binaries and
# ~/bc5-work/input.cfg back as they were before int0429.sh (patch 9e7c4514, exp 0431), and checks each by md5 (exp
# 0431's undo0431.sh, adapted to a list of units; LESSONS R10 0425/undo: the pins file names md5s, never paths of its
# own). No emulator may run. Run alone it takes its own BOX-LOCK slot; from int0429.sh (UNDO_IN_INT=1) it runs in
# int's slot. One step further back is exp 0431's own undo (bash ~/bc5-work/exp0431/undo0431.sh), run after this one,
# never before.
# usage (on the box): bash ~/bc5-work/exp0429/undo0429.sh   (X=<dir> for a stand-in test)
set -u
export LC_ALL=C
W=${UNDO_W:-$HOME/bc5-work}; K=${UNDO_K:-$HOME/src/KytyPlus}; X=${X:-$W/exp0429/swap}
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator; CFG=$W/input.cfg
m8() { md5sum < "$1" | cut -c1-8; }
pgrep '^kyty_emulator' > /dev/null && { echo "undo0429: an emulator runs: NOT DONE"; exit 1; }
[ -s "$X/pins.before-0429" ] || { echo "undo0429: no copies in $X"; exit 1; }
if [ "${UNDO_IN_INT:-0}" != 1 ]; then
  . "$W/exp0413/n/chainlock0417.inc"
  chain_claim "exp 0429: undo of the JobArenaFix removal (back to patch 9e7c4514; copies only, no emulator)" 5 || { echo "undo0429: no lock: NOT DONE"; exit 1; }
  trap chain_release EXIT
fi
PIN_OLD=; NORMAL=; LEAN=; CFG_MD5=; CFG_NEW=
eval "$(grep -E '^(PIN_OLD|NORMAL|LEAN|CFG_MD5|CFG_NEW)=[0-9a-f]*$' "$X/pins.before-0429")"
nu=$(grep -c '^UNIT [0-9a-f]\{8\} src/' "$X/pins.before-0429")
[ -n "$PIN_OLD" ] && [ -n "$NORMAL" ] && [ -n "$LEAN" ] && [ "$nu" -ge 1 ] || { echo "undo0429: the pins file is incomplete: NOT DONE"; exit 1; }
# every copy must exist before anything is written
while read -r _ h u; do [ -s "$X/units/$(basename "$u").before-0429" ] || { echo "undo0429: no copy of $u: NOT DONE"; exit 1; }; done < <(grep '^UNIT ' "$X/pins.before-0429")
[ -s "$X/kyty_emulator.normal.before-0429" ] && [ -s "$X/kyty_emulator.lean.before-0429" ] || { echo "undo0429: no binary copies: NOT DONE"; exit 1; }
while read -r _ h u; do
  cp "$X/units/$(basename "$u").before-0429" "$K/$u" && touch "$K/$u" || { echo "undo0429: copy of $u failed"; exit 1; }
done < <(grep '^UNIT ' "$X/pins.before-0429")
cp -p "$X/kyty_emulator.normal.before-0429" "$NB" && cp -p "$X/kyty_emulator.lean.before-0429" "$LB" || { echo "undo0429: a binary copy failed"; exit 1; }
# input.cfg: untouched when int0429.sh did not reach step 6 (no CFG_NEW); the copy back when it is still as int left it;
# otherwise (the menu wrote it since) only the removed JobArenaFix lines are added again, the rest is kept
CFG_STATE=untouched
if [ -n "$CFG_NEW" ] && [ -s "$X/input.cfg.before-0429" ]; then
  if [ "$(m8 "$CFG")" = "$CFG_NEW" ]; then
    cp -p "$X/input.cfg.before-0429" "$CFG" || { echo "undo0429: input.cfg copy failed"; exit 1; }; CFG_STATE=copy
  else
    grep '^JobArenaFix\.' "$X/input.cfg.before-0429" | while read -r l; do grep -qxF "$l" "$CFG" || echo "$l" >> "$CFG"; done; CFG_STATE=lines
  fi
fi
ok=1
d=$(git -C "$K" diff --no-color f266548 | md5sum | cut -c1-8)
[ "$d" = "$PIN_OLD" ] || { echo "undo0429: the tree's diff is $d, not $PIN_OLD"; ok=0; }
while read -r _ h u; do [ "$(m8 "$K/$u")" = "$h" ] || { echo "undo0429: $u is $(m8 "$K/$u"), not $h"; ok=0; }; done < <(grep '^UNIT ' "$X/pins.before-0429")
[ "$(m8 "$NB")" = "$NORMAL" ] || { echo "undo0429: normal is $(m8 "$NB"), not $NORMAL"; ok=0; }
[ "$(m8 "$LB")" = "$LEAN" ] || { echo "undo0429: lean is $(m8 "$LB"), not $LEAN"; ok=0; }
[ "$CFG_STATE" != copy ] || [ "$(m8 "$CFG")" = "$CFG_MD5" ] || { echo "undo0429: input.cfg is $(m8 "$CFG"), not $CFG_MD5"; ok=0; }
[ "$CFG_STATE" != lines ] || [ "$(grep -c "^JobArenaFix\." "$CFG")" = "$(grep -c "^JobArenaFix\." "$X/input.cfg.before-0429")" ] || { echo "undo0429: input.cfg lacks a JobArenaFix line"; ok=0; }
[ $ok = 1 ] && echo "undo0429: back: patch $PIN_OLD, $nu units, normal $NORMAL, lean $LEAN, input.cfg $CFG_STATE (the units are touched, so the next ninja recompiles them); further back: bash $W/exp0431/undo0431.sh"
[ $ok = 1 ]
