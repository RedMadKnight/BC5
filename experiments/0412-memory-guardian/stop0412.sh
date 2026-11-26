#!/usr/bin/env bash
# BC5 exp 0412: the hard stop of a play from a shortcut (the top session's decision, 2026-11-11, after the
# maintainer's play of 19:40 ran into the memory wall: frames of 1-15 s, then a standing emulator; README section 29).
# One process on the host, started by play-guard-0412.sh beside the emulator. Every 2 s it reads /proc/meminfo and
# /proc/pressure/memory with the shell's own read (no fork, so it keeps running when the box can hardly start a
# process). When, five samples in a row (10 s), MemAvailable is under <min MiB> AND the memory pressure "full" avg10
# is at or over <psi %>, or when the pressure alone is at or over <psi2 %> five samples in a row, it ends the
# emulator: SIGTERM, and SIGKILL if it is still there 3 s later. Then one line in <out file> and a window on the
# desktop: "BC5: zatrzymano, brak pamięci (N MiB)". It ends by itself when the emulator's process is gone.
# The numbers: his play of 19:40 had 267-275 MiB and 23-26 % at 124-129 s, where the frames were already 2 s long;
# the scripted runs that live dip under 300 MiB with 3-20 % and recover.
# usage (host): stop0412.sh <out file> [min MiB, default 300] [psi %, default 20] [psi2 %, default 35]
#   STOP0412_PID=<pid> watches that process instead of waiting for kyty_emulator (the stand-in test).
set -u
OUT=${1:?the out file}; MIN=${2:-300}; PSI=${3:-20}; PSI2=${4:-35}
case "$MIN$PSI$PSI2" in *[!0-9]*) echo "numbers, please"; exit 1 ;; esac
EP=${STOP0412_PID:-}
if [ -z "$EP" ]; then
  for _ in $(seq 1 150); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 2; done
fi
[ -n "$EP" ] || { echo "$(date '+%F %T') hard stop: no emulator in 300 s" >> "$OUT"; exit 0; }
F=$(mktemp -u "${OUT}.fifo.XXXXXX") && mkfifo "$F" || exit 1
exec 3<> "$F"; rm -f "$F"
printf '%s hard stop: watching %s; ends it under %s MiB available with %s %% PSI full, or at %s %% PSI full, five samples of 2 s in a row\n' "$(printf '%(%F %T)T' -1)" "$EP" "$MIN" "$PSI" "$PSI2" >> "$OUT"
low=0; hi=0; a=0; f=0
while [ -d "/proc/$EP" ]; do
  a=0; f=0
  while read -r k v _; do [ "$k" = MemAvailable: ] && { a=$((v / 1024)); break; }; done < /proc/meminfo
  while read -r k v _; do [ "$k" = full ] && { v=${v#avg10=}; f=${v%%.*}; break; }; done < /proc/pressure/memory
  case "$a$f" in *[!0-9]* | "") a=999999; f=0 ;; esac # an unreadable sample never counts toward a stop
  if [ "$a" -lt "$MIN" ] && [ "$f" -ge "$PSI" ]; then low=$((low + 1)); else low=0; fi
  if [ "$f" -ge "$PSI2" ]; then hi=$((hi + 1)); else hi=0; fi
  if [ "$low" -ge 5 ] || [ "$hi" -ge 5 ]; then
    kill -TERM "$EP" 2> /dev/null
    for _ in 1 2 3; do read -r -t 1 _ <&3; [ -d "/proc/$EP" ] || break; done
    [ -d "/proc/$EP" ] && kill -KILL "$EP" 2> /dev/null
    printf '%s hard stop: ENDED %s: available %s MiB, PSI full %s %% (%s and %s samples in a row)\n' "$(printf '%(%F %T)T' -1)" "$EP" "$a" "$f" "$low" "$hi" >> "$OUT"
    if [ -z "${STOP0412_QUIET:-}" ] && command -v kdialog > /dev/null 2>&1; then
      (kdialog --title "BC5" --msgbox "BC5: zatrzymano, brak pamięci ($a MiB)" > /dev/null 2>&1 &)
    fi
    exit 0
  fi
  read -r -t 2 _ <&3
done
printf '%s hard stop: %s ended by itself; last sample %s MiB available, PSI full %s %%\n' "$(printf '%(%F %T)T' -1)" "$EP" "$a" "$f" >> "$OUT"
