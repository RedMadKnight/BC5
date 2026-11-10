#!/usr/bin/env bash
# BC5 exp 0412 (g412b): one play of ASTRO BOT for the leak question of 2026-11-10 (the shared build 4d2b1b1d was killed
# by the kernel after 36 min with 7.3 GiB of anonymous memory; the play had PLAY_CAPTURE=1 from bc5-run.env).
# On the host, as ~/bc5-work/exp0412/play-astro-guard-0412.sh. It runs exp 0412's private copy of the shared launcher,
# play-astro-0412.sh (made by install0412b.sh: play-astro.sh with ulimit -c 0, its own log and the capture word), in the
# ubuntu distrobox. The shared build, play-astro.sh and bc5-run.env are only read.
# Arms:
#   off   BC5_0412_CAPTURE=0: PLAY_CAPTURE unset, so no journal, no BC5_DIRECT_TIMING, no BC5_DIRECT_FRAME_PROFILE
#   on    BC5_0412_CAPTURE=1: PLAY_CAPTURE=1, as the play that was killed
# Beside it, on the host: the sampler sampler0412b.sh (every 5 s the emulator's and bc5-mount's anonymous, shmem and
# swapped MiB, and the cgroup's) into ~/bc5-work/exp0412/sampler/astro-<time>-<arm>.txt, and the fuse (fuse0412.sh:
# memory.max 12,300 MiB, memory.swap.max 2,048 MiB on the container's cgroup while the emulator runs), so a leak ends
# in a kill of the emulator, not in a full swap. BC5_0412_FUSE=0 leaves the fuse out.
# A second word "dry" checks the pins and prints what would run; it starts nothing.
# usage: play-astro-guard-0412.sh off|on [dry]
set -u
E=$HOME/bc5-work/exp0412
L=$E/play-astro-0412.sh; EMU=$HOME/bc5-work/kytyplus-build/src/kyty_emulator
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
say() { echo "$*"; command -v notify-send > /dev/null 2>&1 && notify-send "BC5" "$*" 2> /dev/null; }
pinned() { [ -s "$2" ] && grep -qxF "$(m "$E/$1")  $1" "$2"; }
pinned play-astro-0412.sh "$E/tools.md5" || { say "0412 astro: $L is not the installed launcher; not started"; exit 1; }
grep -q '^ulimit -c 0' "$L" || { say "0412 astro: $L does not set ulimit -c 0; not started"; exit 1; }
[ "$(m "$EMU")" = 4d2b1b1dd52eaea6e3195500f604e73e ] || { say "0412 astro: the shared build is not 4d2b1b1d (the build of the killed play); not started"; exit 1; }
case "${1:-}" in
  off) CAPTURE=0 ;;
  on)  CAPTURE=1 ;;
  *) say "0412 astro: usage: play-astro-guard-0412.sh off|on [dry]; not started"; exit 1 ;;
esac
ARM=$1; DRY=${2:-}
[ -z "$DRY" ] || [ "$DRY" = dry ] || { say "0412 astro: unknown second word $DRY; not started"; exit 1; }
FUSE="12300 2048"
case "${BC5_0412_FUSE-unset}" in unset) ;; 0 | "") FUSE="" ;; *) FUSE=$BC5_0412_FUSE ;; esac
S=$E/sampler0412b.sh; F=$E/fuse0412.sh; STAMP=$(date +%Y%m%d-%H%M%S); SOUT=$E/sampler/astro-$STAMP-capture-$ARM.txt; FLOG=$E/fuse.log
SOK=0; pinned sampler0412b.sh "$E/tools.md5" && SOK=1
FOK=0; pinned fuse0412.sh "$E/tools.md5" && FOK=1
if [ -n "$DRY" ]; then
  echo "dry: astro, capture $ARM (BC5_0412_CAPTURE=$CAPTURE); build $(m "$EMU")"
  echo "dry: sampler $([ "$SOK" = 1 ] && echo "pinned, would write $SOUT" || echo "NOT the installed copy: the play would run without it")"
  echo "dry: fuse $([ -z "$FUSE" ] && echo "none" || { [ "$FOK" = 1 ] && echo "pinned, would set memory.max and memory.swap.max to $FUSE MiB" || echo "NOT the installed copy: the play would run without it"; })"
  echo "dry: would run: /usr/bin/distrobox enter ubuntu -- /usr/bin/env BC5_0412_CAPTURE=$CAPTURE $L"
  echo "dry: nothing started"
  exit 0
fi
pgrep '^kyty_emulator' > /dev/null && { say "0412 astro: an emulator runs already; not started"; exit 1; }
[ "$FOK" = 1 ] && /usr/bin/bash "$F" restore "$FLOG"
if [ "$SOK" = 1 ]; then
  mkdir -p "$E/sampler"
  nohup /usr/bin/bash "$S" "$SOUT" 300 14400 > /dev/null 2>&1 < /dev/null &
else
  say "0412 astro: the sampler $S is not the installed one; playing without it"
fi
if [ -n "$FUSE" ]; then
  if [ "$FOK" = 1 ]; then
    # shellcheck disable=SC2086
    nohup /usr/bin/bash "$F" set $FUSE "$FLOG" > /dev/null 2>&1 < /dev/null &
  else
    say "0412 astro: the fuse $F is not the installed one; playing without it"
  fi
fi
/usr/bin/distrobox enter ubuntu -- /usr/bin/env "BC5_0412_CAPTURE=$CAPTURE" "$L"
