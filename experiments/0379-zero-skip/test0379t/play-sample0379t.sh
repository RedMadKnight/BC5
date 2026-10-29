#!/usr/bin/env bash
# BC5 experiment 0379, test shortcut (exp 0371's sample0371.sh on the box): once a minute while the test launcher runs,
# one line to <out>: MemAvailable, swap used, GTT used, the emulator's and bc5-mount's RSS, the mount's disk reads in the
# last minute (/proc/<pid>/io read_bytes), PSI memory and io "full" avg60, the load. Read-only (/proc, /sys). Started by
# play-pkg-0379t.sh after the mount; ends when the launcher <pid> is gone (its EXIT trap also kills it) or after 6 hours.
# usage: play-sample0379t.sh <launcher pid> <out>
set -u
LP=$1; OUT=$2; end=$(( $(date +%s) + 21600 )); lastrb=; lastpm=
echo "# exp 0379t memory once a minute, launcher $LP; MiB" >> "$OUT"
while [ -d "/proc/$LP" ] && [ "$(date +%s)" -lt $end ]; do
  pe=$(pgrep -o '^kyty_emulator'); pm=$(pgrep -o -x bc5-mount)
  ma=$(awk '/^MemAvailable/{print int($2/1024)}' /proc/meminfo)
  su=$(awk '/^SwapTotal/{t=$2}/^SwapFree/{f=$2}END{print int((t-f)/1024)}' /proc/meminfo)
  gtt=$(cat /sys/class/drm/card*/device/mem_info_gtt_used 2> /dev/null | sort -n | tail -1)
  re=-; [ -n "$pe" ] && re=$(ps -o rss= -p "$pe" | awk '{print int($1/1024)}')
  rm=-; rd=-
  if [ -n "$pm" ]; then
    rm=$(ps -o rss= -p "$pm" | awk '{print int($1/1024)}')
    rb=$(awk '/^read_bytes/{print $2}' /proc/"$pm"/io 2> /dev/null)
    [ -n "$rb" ] && [ "$pm" = "$lastpm" ] && [ -n "$lastrb" ] && rd=$(( (rb - lastrb) / 1048576 ))
    lastrb=$rb; lastpm=$pm
  fi
  pmem=$(awk '/^full/{split($3,a,"=");print a[2]}' /proc/pressure/memory); pio=$(awk '/^full/{split($3,a,"=");print a[2]}' /proc/pressure/io)
  echo "$(date +%T) emu=${pe:-none} memavail=${ma}M swapused=${su}M gtt=$(( ${gtt:-0} / 1048576 ))M emu_rss=${re}M mount_rss=${rm}M mount_read_1min=${rd}M psi_mem_full60=${pmem} psi_io_full60=${pio} load=$(cut -d' ' -f1 /proc/loadavg)" >> "$OUT"
  sleep 60
done
echo "# end $(date '+%F %T')" >> "$OUT"
