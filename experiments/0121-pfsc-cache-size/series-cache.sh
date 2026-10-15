#!/usr/bin/env bash
# ASTRO BOT start (play settings, 70 s, no input) with the games' bc5-mount (0116's reader, main
# 38e0717) and BC5_MOUNT_CACHE_MIB set per run: "run:MiB" pairs. Logs the mount's last stats line
# and the lowest MemAvailable sampled every second. Stops at the first GPU page fault.
cd ~/bc5-work || exit 1
for pair in "$@"; do
  r=${pair%%:*}; mib=${pair#*:}
  sed -e "s/run 426 (ASTRO BOT start, baseline for experiment 0114; maintainer available)/run $r (ASTRO BOT start, PFSC cache $mib MiB, experiment 0121; maintainer present)/" \
      -e "s/BC5_MOUNT_STATS=1/BC5_MOUNT_STATS=1 BC5_MOUNT_CACHE_MIB=$mib/" \
      -e "s/RUN_SECONDS=60/RUN_SECONDS=70/" run426.sh > run$r.sh
  chmod +x run$r.sh
  sleep $((61 - $(date +%S | sed "s/^0//")))
  pkill -9 -x steam 2>/dev/null
  # a fresh mount per run, so that the cache size applies (a mount left mounted is reused)
  M=~/bc5-data/mnt/PPSA21567
  distrobox enter ubuntu -- fusermount3 -uz "$M" 2>/dev/null
  sleep 1; ls "$M" >/dev/null 2>&1 || { echo "run $r: mountpoint still broken"; exit 1; }
  t0=$(date "+%Y-%m-%d %H:%M:%S")
  ( m=999999; for _ in $(seq 1 85); do a=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo); [ "$a" -lt "$m" ] && m=$a; echo "$m" > /tmp/bc5-memmin.$r; sleep 1; done ) &
  SAMPLER=$!
  distrobox enter ubuntu -- /home/kjaniszewski/bc5-work/run$r.sh > run$r.out 2>&1
  sync; wait $SAMPLER
  c=$(ls -td ~/bc5-data/captures/kytyplus-* | head -1); d=$c/gc/direct.log
  faults=$(journalctl _TRANSPORT=kernel --since "$t0" --no-pager | grep -c "in page starting")
  echo "run $r cache ${mib} MiB $c faults=$faults timeouts=$(grep -c TIMEOUT "$d") $(python3 frameprof.py "$d" 40 65 2>/dev/null | head -1) min MemAvailable $(cat /tmp/bc5-memmin.$r) MiB"
  awk '/bc5-mount stats/{t=$3; s=$6; if (!a && s+0>=2000) {a=t} if (!b && s+0>=4000) {b=t}} END{print "  2000 MiB at " a " s, 4000 MiB at " b " s"}' "$c/bc5-mount.log"
  grep stats "$c/bc5-mount.log" | tail -1 | cut -c1-200
  [ "$faults" -gt 0 ] && { echo "fault: series stopped"; exit 0; }
done
echo "series done"
