#!/usr/bin/env bash
# BC5 experiment 0220: the box's memory state every 15 s while the emulator <pid> runs (exp 0216's S1 ran in a swap-in
# storm whose cause was not found): /proc/meminfo fields (kB), the GPU's GTT and VRAM use (bytes; GTT is system memory),
# PSI memory/io avg10, and the six largest processes by RSS. Read-only. usage: mem0220.sh <out> <pid>
OUT=$1 P=$2
G=/sys/class/drm/card1/device
{
  echo "# mem0220 pid $P start $(date '+%F %T')"
  while [ -d "/proc/$P" ]; do
    now=$(cut -d' ' -f1 /proc/uptime)
    echo "k $now $(awk '/^(MemFree|MemAvailable|Cached|Shmem|AnonPages|SwapCached|SwapTotal|SwapFree):/ {printf "%s %s ", $1, $2}' /proc/meminfo)gtt $(cat $G/mem_info_gtt_used 2> /dev/null) vram $(cat $G/mem_info_vram_used 2> /dev/null)"
    echo "p $now mem $(head -2 /proc/pressure/memory | awk '{printf "%s ", $2}')io $(head -2 /proc/pressure/io | awk '{printf "%s ", $2}')"
    ps -eo rss=,pid=,comm= --sort=-rss | head -6 | awk -v t="$now" '{printf "r %s %s %s %s\n", t, $1, $2, $3}'
    sleep 15
  done
  echo "# mem0220 end $(date '+%F %T')"
} >> "$OUT"
