#!/usr/bin/env bash
# BC5 exp 0412 (tag ev412): the second title, unpacked, on the events-cap build (the maintainer, 2026-11-11: "do tej
# wersji dodaj mozliwosc uruchomienia rozpakowanej wersji drugiej gry"). On the host, as
# ~/bc5-work/exp0412/play-pkg-ev-0412.sh. It runs ev/play-pkg-ev0412.sh (exp 0412's play-pkg-0412.sh, which starts the
# unpacked game when BC5_GAME_DIR is set and sets ulimit -c 0, with EMU and LOG changed) in the ubuntu distrobox, with
# BC5_GAME_DIR=~/bc5-data/games/PPSA03671 and the arm's event words. The sampler sampler0412b.sh and the fuse
# (memory.max 12,400 MiB, memory.swap.max 2,048 MiB) run beside it.
# This build is the SHARED source of 2026-11-02 plus the events cap. It has none of the e-series' work (exp 0401-0411)
# and none of the guardian's, so the "e11 unpacked" shortcut's 70 switch words are not passed: this build does not know
# them. RT, the saves, the settings and the learned file are the launcher's, as in the other shortcuts.
# Arms:
#   cap   KYTY_BC5_EVENT_PENDING_CAP=64 and the log
#   log   KYTY_BC5_EVENT_PENDING_LOG=1 only (the queue as before, growth named in the play log)
#   plain no event word
# A second word "dry" checks the pins and prints what would run; it starts nothing.
# usage: play-pkg-ev-0412.sh cap|log|plain [dry]
set -u
E=$HOME/bc5-work/exp0412; V=$E/ev
L=$V/play-pkg-ev0412.sh; EMU=$V/bin/kyty_emulator; GAME=/home/kjaniszewski/bc5-data/games/PPSA03671
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
say() { echo "$*"; command -v notify-send > /dev/null 2>&1 && notify-send "BC5" "$*" 2> /dev/null; }
pinned() { [ -s "$3" ] && grep -qxF "$(m "$1/$2")  $2" "$3"; }
pinned "$V" bin/kyty_emulator "$V/built.md5" || { say "0412 pkg ev: $EMU is not the build in ev/built.md5; not started"; exit 1; }
pinned "$V" play-pkg-ev0412.sh "$V/built.md5" || { say "0412 pkg ev: $L is not the launcher in ev/built.md5; not started"; exit 1; }
grep -q '^ulimit -c 0' "$L" && grep -qxF "EMU=$EMU  # exp 0412 (ev412): the private build" "$L" && grep -q 'BC5_GAME_DIR' "$L" || { say "0412 pkg ev: $L does not set ulimit -c 0, the private build or the unpacked game; not started"; exit 1; }
[ -r "$GAME/eboot.bin" ] || { say "0412 pkg ev: no unpacked game at $GAME; not started"; exit 1; }
case "${1:-}" in
  cap)   WORDS=(KYTY_BC5_EVENT_PENDING_CAP=64 KYTY_BC5_EVENT_PENDING_LOG=1) ;;
  log)   WORDS=(KYTY_BC5_EVENT_PENDING_LOG=1) ;;
  plain) WORDS=() ;;
  *) say "0412 pkg ev: usage: play-pkg-ev-0412.sh cap|log|plain [dry]; not started"; exit 1 ;;
esac
ARM=$1; DRY=${2:-}
[ -z "$DRY" ] || [ "$DRY" = dry ] || { say "0412 pkg ev: unknown second word $DRY; not started"; exit 1; }
WORDS=("BC5_GAME_DIR=$GAME" "${WORDS[@]}")
FUSE="12400 2048"
case "${BC5_0412_FUSE-unset}" in unset) ;; 0 | "") FUSE="" ;; *) FUSE=$BC5_0412_FUSE ;; esac
S=$E/sampler0412b.sh; F=$E/fuse0412.sh; STAMP=$(date +%Y%m%d-%H%M%S); SOUT=$E/sampler/play-$STAMP-ev$ARM.txt; FLOG=$E/fuse.log
SOK=0; pinned "$E" sampler0412b.sh "$E/tools.md5" && SOK=1
FOK=0; pinned "$E" fuse0412.sh "$E/tools.md5" && FOK=1
if [ -n "$DRY" ]; then
  echo "dry: the second title unpacked on ev412, arm $ARM, words: ${WORDS[*]}; build $(m "$EMU")"
  echo "dry: sampler $([ "$SOK" = 1 ] && echo "pinned, would write $SOUT" || echo "NOT the installed copy: the play would run without it")"
  echo "dry: fuse $([ -z "$FUSE" ] && echo "none" || { [ "$FOK" = 1 ] && echo "pinned, would set memory.max and memory.swap.max to $FUSE MiB" || echo "NOT the installed copy: the play would run without it"; })"
  echo "dry: would run: /usr/bin/distrobox enter ubuntu -- /usr/bin/env ${WORDS[*]} ${BC5_0412_LAUNCHER:-$L}"
  echo "dry: nothing started"
  exit 0
fi
pgrep '^kyty_emulator' > /dev/null && { say "0412 pkg ev: an emulator runs already; not started"; exit 1; }
[ "$FOK" = 1 ] && /usr/bin/bash "$F" restore "$FLOG"
if [ "$SOK" = 1 ]; then
  mkdir -p "$E/sampler"
  nohup /usr/bin/bash "$S" "$SOUT" 300 14400 > /dev/null 2>&1 < /dev/null &
else
  say "0412 pkg ev: the sampler $S is not the installed one; playing without it"
fi
if [ -n "$FUSE" ]; then
  if [ "$FOK" = 1 ]; then
    # shellcheck disable=SC2086
    nohup /usr/bin/bash "$F" set $FUSE "$FLOG" > /dev/null 2>&1 < /dev/null &
  else
    say "0412 pkg ev: the fuse $F is not the installed one; playing without it"
  fi
fi
# BC5_0412_LAUNCHER: another launcher for the start check only (startev0412.sh's copy with a private working directory).
/usr/bin/distrobox enter ubuntu -- /usr/bin/env "${WORDS[@]}" "${BC5_0412_LAUNCHER:-$L}"
