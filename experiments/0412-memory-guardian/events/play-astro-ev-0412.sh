#!/usr/bin/env bash
# BC5 exp 0412 (tag ev412): one play of ASTRO BOT on the private build with the bound on an event's pending queue
# (README sections 10 and 11; the maintainer's "Tak, buduj" of 2026-11-11). On the host, as
# ~/bc5-work/exp0412/play-astro-ev-0412.sh. play-astro-guard-0412.sh's pattern: the private launcher copy
# ev/play-astro-ev0412.sh (play-astro-0412.sh with EMU and LOG changed; ulimit -c 0) in the ubuntu distrobox, capture
# off, the sampler sampler0412b.sh and the fuse (memory.max 12,400 MiB, memory.swap.max 2,048 MiB) beside it.
# Arms:
#   log   KYTY_BC5_EVENT_PENDING_LOG=1: the queue as before, the growing event named in the play log (the control)
#   cap   KYTY_BC5_EVENT_PENDING_CAP=64 and the log: at most 64 pending entries per event, later triggers coalesced
#   plain no switch: the private build as the shared one
# A second word "dry" checks the pins and prints what would run; it starts nothing.
# usage: play-astro-ev-0412.sh log|cap|plain [dry]
set -u
E=$HOME/bc5-work/exp0412; V=$E/ev
L=$V/play-astro-ev0412.sh; EMU=$V/bin/kyty_emulator
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
say() { echo "$*"; command -v notify-send > /dev/null 2>&1 && notify-send "BC5" "$*" 2> /dev/null; }
pinned() { [ -s "$3" ] && grep -qxF "$(m "$1/$2")  $2" "$3"; }
pinned "$V" bin/kyty_emulator "$V/built.md5" || { say "0412 astro ev: $EMU is not the build in ev/built.md5; not started"; exit 1; }
pinned "$V" play-astro-ev0412.sh "$V/built.md5" || { say "0412 astro ev: $L is not the launcher in ev/built.md5; not started"; exit 1; }
grep -q '^ulimit -c 0' "$L" && grep -qxF "EMU=$EMU  # exp 0412 (ev412): the private build" "$L" || { say "0412 astro ev: $L does not set ulimit -c 0 or the private build; not started"; exit 1; }
grep -aqF KYTY_BC5_EVENT_PENDING_CAP "$EMU" || { say "0412 astro ev: $EMU has no events cap; not started"; exit 1; }
case "${1:-}" in
  log)   WORDS=(KYTY_BC5_EVENT_PENDING_LOG=1) ;;
  cap)   WORDS=(KYTY_BC5_EVENT_PENDING_CAP=64 KYTY_BC5_EVENT_PENDING_LOG=1) ;;
  plain) WORDS=() ;;
  *) say "0412 astro ev: usage: play-astro-ev-0412.sh log|cap|plain [dry]; not started"; exit 1 ;;
esac
ARM=$1; DRY=${2:-}
[ -z "$DRY" ] || [ "$DRY" = dry ] || { say "0412 astro ev: unknown second word $DRY; not started"; exit 1; }
FUSE="12400 2048"
case "${BC5_0412_FUSE-unset}" in unset) ;; 0 | "") FUSE="" ;; *) FUSE=$BC5_0412_FUSE ;; esac
S=$E/sampler0412b.sh; F=$E/fuse0412.sh; STAMP=$(date +%Y%m%d-%H%M%S); SOUT=$E/sampler/astro-$STAMP-capture-ev$ARM.txt; FLOG=$E/fuse.log
SOK=0; pinned "$E" sampler0412b.sh "$E/tools.md5" && SOK=1
FOK=0; pinned "$E" fuse0412.sh "$E/tools.md5" && FOK=1
if [ -n "$DRY" ]; then
  echo "dry: astro ev, arm $ARM, words: ${WORDS[*]:-none}; capture off; build $(m "$EMU")"
  echo "dry: sampler $([ "$SOK" = 1 ] && echo "pinned, would write $SOUT" || echo "NOT the installed copy: the play would run without it")"
  echo "dry: fuse $([ -z "$FUSE" ] && echo "none" || { [ "$FOK" = 1 ] && echo "pinned, would set memory.max and memory.swap.max to $FUSE MiB" || echo "NOT the installed copy: the play would run without it"; })"
  echo "dry: would run: /usr/bin/distrobox enter ubuntu -- /usr/bin/env BC5_0412_CAPTURE=0 ${WORDS[*]:-} $L"
  echo "dry: nothing started"
  exit 0
fi
pgrep '^kyty_emulator' > /dev/null && { say "0412 astro ev: an emulator runs already; not started"; exit 1; }
[ "$FOK" = 1 ] && /usr/bin/bash "$F" restore "$FLOG"
if [ "$SOK" = 1 ]; then
  mkdir -p "$E/sampler"
  nohup /usr/bin/bash "$S" "$SOUT" 300 14400 > /dev/null 2>&1 < /dev/null &
else
  say "0412 astro ev: the sampler $S is not the installed one; playing without it"
fi
if [ -n "$FUSE" ]; then
  if [ "$FOK" = 1 ]; then
    # shellcheck disable=SC2086
    nohup /usr/bin/bash "$F" set $FUSE "$FLOG" > /dev/null 2>&1 < /dev/null &
  else
    say "0412 astro ev: the fuse $F is not the installed one; playing without it"
  fi
fi
/usr/bin/distrobox enter ubuntu -- /usr/bin/env BC5_0412_CAPTURE=0 "${WORDS[@]}" "$L"
