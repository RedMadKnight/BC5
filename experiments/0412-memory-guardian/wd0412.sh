#!/usr/bin/env bash
# BC5 exp 0412: the night runs' watchdog (the top session's order, 2026-11-10 23:00: "an ssh-independent watchdog on the
# box that kills the emulator if MemAvailable < ~400 MiB or PSI full > 60 % for 10 s"). One process on the host, started
# by run0412n.sh beside one emulator. Every 2 s it reads /proc/meminfo and /proc/pressure/memory with the shell's own
# read (no fork, so it keeps running when the box can hardly start a process); after five samples in a row with
# MemAvailable under <min MiB>, or five with PSI memory "full" avg10 over <psi %>, it sends SIGKILL to the emulator,
# writes one line and ends. It ends by itself when the emulator's process is gone.
# usage (host): wd0412.sh <emulator pid> <out file> [min MiB, default 400] [psi %, default 60]
set -u
EP=${1:?the pid of the emulator}; OUT=${2:?the out file}; MIN=${3:-400}; PSI=${4:-60}
case "$EP$MIN$PSI" in *[!0-9]*) echo "numbers, please"; exit 1 ;; esac
F=$(mktemp -u "${OUT}.fifo.XXXXXX") && mkfifo "$F" || exit 1
exec 3<> "$F"; rm -f "$F"
low=0; hi=0; n=0; amin=999999; fmax=0
printf '%s watchdog: emulator %s, kill under %s MiB available or over %s %% PSI full, five samples of 2 s in a row\n' "$(printf '%(%F %T)T' -1)" "$EP" "$MIN" "$PSI" >> "$OUT"
while [ -d "/proc/$EP" ]; do
  a=0; f=0
  while read -r k v _; do if [ "$k" = MemAvailable: ]; then a=$((v / 1024)); break; fi; done < /proc/meminfo
  while read -r k s _; do if [ "$k" = full ]; then s=${s#avg10=}; f=${s%.*}; fi; done < /proc/pressure/memory
  [ "$a" -lt "$amin" ] && amin=$a
  [ "$f" -gt "$fmax" ] && fmax=$f
  if [ "$a" -lt "$MIN" ]; then low=$((low + 1)); else low=0; fi
  if [ "$f" -gt "$PSI" ]; then hi=$((hi + 1)); else hi=0; fi
  n=$((n + 1))
  if [ "$low" -ge 5 ] || [ "$hi" -ge 5 ]; then
    kill -9 "$EP" 2> /dev/null
    printf '%s watchdog: KILLED emulator %s after %s samples: available %s MiB (%s low in a row), PSI full %s %% (%s high in a row)\n' "$(printf '%(%F %T)T' -1)" "$EP" "$n" "$a" "$low" "$f" "$hi" >> "$OUT"
    exit 0
  fi
  read -r -t 2 _ <&3
done
printf '%s watchdog: emulator %s ended; %s samples, lowest available %s MiB, highest PSI full %s %%\n' "$(printf '%(%F %T)T' -1)" "$EP" "$n" "$amin" "$fmax" >> "$OUT"
