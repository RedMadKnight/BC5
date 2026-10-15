#!/usr/bin/env bash
# Runs FIRST..LAST: ASTRO BOT start (run426.sh settings = play settings, pieces as one job since
# experiment 0119, 70 s, no input) with the games' bc5-mount swapped for experiment 0116's build
# (per-block in-flight PFSC slots + 256 MiB cache), to retest it without 0117's wrong verdict.
# The previous binary is put back at the end, also on interruption. Stops at the first GPU fault.
cd ~/bc5-work || exit 1
first=$1; last=$2
BIN=~/bc5-work/bc5-tools-ubuntu/release/bc5-mount
OLD=~/bc5-work/bc5-mount.before-0116
NEW=~/bc5-work/bc5-mount.0116
restore() { cp --remove-destination "$OLD" "$BIN"; echo "restored: $(md5sum < "$BIN" | cut -c1-8)"; }
trap restore EXIT
cp --remove-destination "$NEW" "$BIN"
echo "swapped in 0116: $(md5sum < "$BIN" | cut -c1-8)"
for r in $(seq "$first" "$last"); do
  sed -e "s/run 426 (ASTRO BOT start, baseline for experiment 0114; maintainer available)/run $r (ASTRO BOT start, bc5-mount of experiment 0116, pieces as one job; maintainer present)/" \
      -e "s/RUN_SECONDS=60/RUN_SECONDS=70/" run426.sh > run$r.sh
  chmod +x run$r.sh
  sleep $((61 - $(date +%S | sed "s/^0//")))
  pkill -9 -x steam 2>/dev/null
  echo "run $r start $(date +%T) nproc $(nproc)"
  t0=$(date "+%Y-%m-%d %H:%M:%S")
  distrobox enter ubuntu -- /home/kjaniszewski/bc5-work/run$r.sh > run$r.out 2>&1
  sync
  c=$(ls -td ~/bc5-data/captures/kytyplus-* | head -1); d=$c/gc/direct.log
  faults=$(journalctl _TRANSPORT=kernel --since "$t0" --no-pager | grep -c "in page starting")
  echo "run $r $c faults=$faults timeouts=$(grep -c TIMEOUT "$d") pieces=$(grep -c "^piece: " "$d") $(python3 frameprof.py "$d" 40 65 2>/dev/null | head -1)"
  grep stats "$c/bc5-mount.log" | tail -1 | cut -c1-200
  journalctl _TRANSPORT=kernel --since "$t0" --no-pager | grep "in page starting" | sed -E "s/.*address (0x[0-9a-f]+).*/\1/" | sort | uniq -c | head -5
  [ "$faults" -gt 0 ] && { echo "fault: series stopped"; exit 0; }
done
echo "series done"
