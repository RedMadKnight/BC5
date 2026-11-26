#!/usr/bin/env bash
# BC5 experiment 0342 (the maintainer's play on the integrated shared build) (exp 0341's sampleplay0341.sh): run on the laptop while the maintainer plays on the shared shortcuts. Once a minute while the
# emulator runs, one line from the box to raw/samples.txt: MemAvailable, swap used, GTT used, the emulator's and
# bc5-mount's RSS, whether the mount runs with MALLOC_ARENA_MAX=2 (F353), the load, the GPU edge and CPU Tctl temperatures. Only reads /proc and sysfs.
# Returns when the emulator has been gone for 10 minutes after it was seen (the end of the session), or after 4 hours.
# usage: sampleplay0342.sh   (in the background)
out="$(cd "$(dirname "$0")" && pwd)/raw/maintainer-test"
mkdir -p "$out"
# shellcheck disable=SC2016
ssh -o ServerAliveInterval=10 -o ServerAliveCountMax=6 bc250 'bash -s' >> "$out/samples.txt" 2>&1 <<'EOF'
seen=0; gone=0; end=$(( $(date +%s) + 14400 ))
while [ "$(date +%s)" -lt $end ]; do
  pe=$(pgrep -x kyty_emulator | head -1); pm=$(pgrep -f "bc5-mount mount" | head -1)
  if [ -n "$pe" ]; then seen=1; gone=0; elif [ $seen = 1 ]; then gone=$((gone + 1)); fi
  if [ $seen = 1 ]; then
    ma=$(awk '/^MemAvailable/{print int($2/1024)}' /proc/meminfo)
    su=$(awk '/^SwapTotal/{t=$2}/^SwapFree/{f=$2}END{print int((t-f)/1024)}' /proc/meminfo)
    gtt=$(cat /sys/class/drm/card*/device/mem_info_gtt_used 2>/dev/null | sort -n | tail -1)
    re=-; [ -n "$pe" ] && re=$(ps -o rss= -p "$pe" | awk '{print int($1/1024)}')
    rm=-; ar=-; [ -n "$pm" ] && { rm=$(ps -o rss= -p "$pm" | awk '{print int($1/1024)}'); ar=$(tr '\0' '\n' < /proc/"$pm"/environ | grep -c '^MALLOC_ARENA_MAX=2$'); }
    te=$(sensors 2>/dev/null | awk '/^edge:/{print $2}'); tc=$(sensors 2>/dev/null | awk '/^Tctl:/{print $2}')   # exp 0341: the maintainer saw lower temperatures
    echo "$(date +%T) emu=${pe:-none} memavail=${ma}M swapused=${su}M gtt=$(( ${gtt:-0} / 1048576 ))M emu_rss=${re}M mount_rss=${rm}M mount_arena2=${ar} load=$(cut -d' ' -f1 /proc/loadavg) gpu_edge=${te:--} cpu_tctl=${tc:--}"
  fi
  [ $gone -ge 10 ] && { echo "$(date +%T) the emulator gone 10 minutes: end"; exit 0; }
  sleep 60
done
echo "$(date +%T) 4 hours: end"
EOF
