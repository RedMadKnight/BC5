#!/usr/bin/env bash
# BC5 exp 0401 runner, the exp 0409 arms (laptop): night0401.sh one arm at a time, stopping the series at a crash, a failed
# or unrecovered GPU reset, a reboot, a SETUP/ROUTE failure, or the file raw/night/STOP-0409 (he wants to play). A recovered
# ring reset does not stop it. usage: bash series0409.sh <named snapshot sum> <arms file>
set -u
SUM=${1:?the named snapshot sum}; ARMS=${2:?an arms file}
HERE=$(cd "$(dirname "$0")" && pwd); OUT=$HERE/raw/night; mkdir -p "$OUT"
while read -r line; do
  case "$line" in "" | \#*) continue ;; esac
  TAG=$(echo "$line" | cut -d' ' -f2)
  [ ! -e "$OUT/STOP-0409" ] || { echo "== $(date '+%F %T') STOP-0409 found: series stopped before $TAG" | tee -a "$OUT/night.txt"; exit 0; }
  printf '%s\n' "$line" > "$OUT/arm-$TAG.txt"
  bash "$HERE/night0401.sh" "$SUM" "$OUT/arm-$TAG.txt"
  END=$(cat "$OUT/$TAG-end.txt" 2> /dev/null); SUMM=$(cat "$OUT/$TAG-summary.txt" 2> /dev/null)
  why=""
  case "$END" in "") why="no end record" ;; *"ended by itself"* ) why="the emulator ended by itself (crash)" ;; *"reset failed"* | *"no reset line"* ) why="GPU hang without a recovered reset" ;; *"SETUP:"* | *"ROUTE:"* ) why="setup/route failure" ;; esac
  echo "$SUMM" | grep -q "crash lines [1-9]" && why="${why:+$why; }crash lines in the log"
  tail -5 "$OUT/night.txt" | grep -q "does not answer after the arm" && why="${why:+$why; }the box rebooted"
  if [ -n "$why" ]; then echo "== $(date '+%F %T') series stopped at $TAG: $why" | tee -a "$OUT/night.txt"; exit 0; fi
done < "$ARMS"
echo "== $(date '+%F %T') series 0409 done" | tee -a "$OUT/night.txt"
