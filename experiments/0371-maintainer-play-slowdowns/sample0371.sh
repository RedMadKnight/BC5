#!/usr/bin/env bash
# BC5 exp 0371 (sample0359.sh plus I/O): once a minute while the emulator runs, one line from the box to
# raw/samples.txt: MemAvailable, swap used, GTT used, the emulator's and bc5-mount's RSS, the mount's disk reads in the
# last minute, PSI memory and I/O (full, avg60), the load, GPU edge and CPU Tctl temperatures. Only reads /proc and sysfs.
# Returns when the emulator has been gone for 10 minutes after it was seen, or after 4 hours.
# usage: sample0371.sh   (in the background)
out=/c/Users/kjani/Downloads/bc5/bc5/experiments/0371-maintainer-play-slowdowns/raw
mkdir -p "$out"
# shellcheck disable=SC2016
ssh -o ServerAliveInterval=10 -o ServerAliveCountMax=6 bc250 'bash -s' >> "$out/samples.txt" 2>&1 <<'EOF'
seen=0; gone=0; end=$(( $(date +%s) + 14400 )); lastrb=; lastpm=
while [ "$(date +%s)" -lt $end ]; do
  pe=$(pgrep -x kyty_emulator | head -1); pm=$(pgrep -f "bc5-mount mount" | head -1)
  if [ -n "$pe" ]; then seen=1; gone=0; elif [ $seen = 1 ]; then gone=$((gone + 1)); fi
  if [ $seen = 1 ]; then
    ma=$(awk '/^MemAvailable/{print int($2/1024)}' /proc/meminfo)
    su=$(awk '/^SwapTotal/{t=$2}/^SwapFree/{f=$2}END{print int((t-f)/1024)}' /proc/meminfo)
    gtt=$(cat /sys/class/drm/card*/device/mem_info_gtt_used 2>/dev/null | sort -n | tail -1)
    re=-; [ -n "$pe" ] && re=$(ps -o rss= -p "$pe" | awk '{print int($1/1024)}')
    rm=-; rd=-; if [ -n "$pm" ]; then rm=$(ps -o rss= -p "$pm" | awk '{print int($1/1024)}')
      rb=$(awk '/^read_bytes/{print $2}' /proc/"$pm"/io 2>/dev/null)
      [ -n "$rb" ] && [ "$pm" = "$lastpm" ] && [ -n "$lastrb" ] && rd=$(( (rb - lastrb) / 1048576 )); lastrb=$rb; lastpm=$pm; fi
    pmem=$(awk '/^full/{split($3,a,"=");print a[2]}' /proc/pressure/memory); pio=$(awk '/^full/{split($3,a,"=");print a[2]}' /proc/pressure/io)
    te=$(sensors 2>/dev/null | awk '/^edge:/{print $2}'); tc=$(sensors 2>/dev/null | awk '/^Tctl:/{print $2}')
    echo "$(date +%T) emu=${pe:-none} memavail=${ma}M swapused=${su}M gtt=$(( ${gtt:-0} / 1048576 ))M emu_rss=${re}M mount_rss=${rm}M mount_read_1min=${rd}M psi_mem_full60=${pmem} psi_io_full60=${pio} load=$(cut -d' ' -f1 /proc/loadavg) gpu_edge=${te:--} cpu_tctl=${tc:--}"
  fi
  [ $gone -ge 10 ] && { echo "$(date +%T) the emulator gone 10 minutes: end"; exit 0; }
  sleep 60
done
echo "$(date +%T) 4 hours: end"
EOF
