#!/usr/bin/env bash
# Runs FIRST..LAST: ASTRO BOT start (run426.sh settings, 70 s, no input) WITH BC5_DIRECT_PIECES_FULL=1
# and pieces sent as one job with their prefix (experiment 0118's fix). Maintainer present.
# Stops the series at the first GPU page fault.
cd ~/bc5-work || exit 1
first=$1; last=$2
for r in $(seq "$first" "$last"); do
  sed -e "s/run 426 (ASTRO BOT start, baseline for experiment 0114; maintainer available)/run $r (ASTRO BOT start, graphics pieces as one job with their prefix, experiment 0118; maintainer present)/" \
      -e "s/BC5_MOUNT_STATS=1/BC5_MOUNT_STATS=1 BC5_DIRECT_PIECES_FULL=1/" \
      -e "s/RUN_SECONDS=60/RUN_SECONDS=70/" run426.sh > run$r.sh
  chmod +x run$r.sh
  grep -q "PIECES_FULL=1" run$r.sh || { echo "run $r: sed failed"; exit 1; }
  sleep $((61 - $(date +%S | sed "s/^0//")))
  pkill -9 -x steam 2>/dev/null
  echo "run $r start $(date +%T) nproc $(nproc)"
  t0=$(date "+%Y-%m-%d %H:%M:%S")
  distrobox enter ubuntu -- /home/kjaniszewski/bc5-work/run$r.sh > run$r.out 2>&1
  sync
  c=$(ls -td ~/bc5-data/captures/kytyplus-* | head -1); d=$c/gc/direct.log
  faults=$(journalctl _TRANSPORT=kernel --since "$t0" --no-pager | grep -c "in page starting")
  echo "run $r $c faults=$faults timeouts=$(grep -c TIMEOUT "$d") pieces=$(grep -c "^piece: " "$d") $(grep -h "pieces full:" "$d" | grep -o "[0-9]* splits made" | awk '{s+=$1} END{print "splits=" s+0}') $(python3 frameprof.py "$d" 40 65 2>/dev/null | head -1)"
  journalctl _TRANSPORT=kernel --since "$t0" --no-pager | grep "in page starting" | sed -E "s/.*address (0x[0-9a-f]+).*/\1/" | sort | uniq -c | head -5
  [ "$faults" -gt 0 ] && { echo "fault: series stopped"; exit 0; }
done
echo "series done"
