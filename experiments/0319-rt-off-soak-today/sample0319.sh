#!/usr/bin/env bash
# BC5 experiment 0319: run on the laptop with the chain (exp 0315's sample0315.sh). Once a minute while the chain's
# "exp 0319 | s6n run" BOX-LOCK line is there, one line from the box to raw/samples.txt: MemAvailable, swap used, GTT
# used, the emulator's and bc5-mount's RSS, whether the mount runs with MALLOC_ARENA_MAX=2 (F353), the load. Only reads
# /proc, sysfs and the lock file. Returns when the lock line has gone after it was seen, or after 80 minutes.
# usage: sample0319.sh   (in the background)
out="$(cd "$(dirname "$0")" && pwd)/raw"
mkdir -p "$out"
# shellcheck disable=SC2016
ssh -o ServerAliveInterval=10 -o ServerAliveCountMax=6 bc250 'bash -s' >> "$out/samples.txt" 2>&1 <<'EOF'
seen=0; end=$(( $(date +%s) + 4800 ))
while [ "$(date +%s)" -lt $end ]; do
  if grep -q "^exp 0319 | s6n run" ~/bc5-work/BOX-LOCK 2> /dev/null; then seen=1; elif [ $seen = 1 ]; then echo "$(date +%T) the chain's lock is gone: end"; exit 0; fi
  if [ $seen = 1 ]; then
    pe=$(pgrep -x kyty_emulator | head -1); pm=$(pgrep -f "bc5-mount mount" | head -1)
    ma=$(awk '/^MemAvailable/{print int($2/1024)}' /proc/meminfo)
    su=$(awk '/^SwapTotal/{t=$2}/^SwapFree/{f=$2}END{print int((t-f)/1024)}' /proc/meminfo)
    gtt=$(cat /sys/class/drm/card*/device/mem_info_gtt_used 2> /dev/null | sort -n | tail -1)
    re=-; [ -n "$pe" ] && re=$(ps -o rss= -p "$pe" | awk '{print int($1/1024)}')
    rm=-; ar=-; [ -n "$pm" ] && { rm=$(ps -o rss= -p "$pm" | awk '{print int($1/1024)}'); ar=$(tr '\0' '\n' < /proc/"$pm"/environ | grep -c '^MALLOC_ARENA_MAX=2$'); }
    echo "$(date +%T) emu=${pe:-none} memavail=${ma}M swapused=${su}M gtt=$(( ${gtt:-0} / 1048576 ))M emu_rss=${re}M mount_rss=${rm}M mount_arena2=${ar} load=$(cut -d' ' -f1 /proc/loadavg)"
  fi
  sleep 60
done
echo "$(date +%T) 80 minutes: end"
EOF
