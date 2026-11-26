#!/usr/bin/env bash
# BC5: from START s after the emulator appears, every second for COUNT s: CPU % of every thread of the emulator that used >5% (utime+stime deltas from /proc), the load average and free memory -> OUT
set -u
START=$1; COUNT=$2; OUT=$3
: > "$OUT"
for _ in $(seq 1 300); do PID=$(pgrep -x kyty_emulator | head -1); [ -n "$PID" ] && break; sleep 1; done
[ -z "${PID:-}" ] && { echo "no emulator" >> "$OUT"; exit 1; }
sleep "$START"
HZ=$(getconf CLK_TCK)
declare -A prev
for i in $(seq 1 "$COUNT"); do
  kill -0 "$PID" 2>/dev/null || break
  line="== $(date +%T) load $(cut -d" " -f1 /proc/loadavg) memavail $(awk "/MemAvailable/{print int(\$2/1024)}" /proc/meminfo) MiB swapused $(awk "/SwapTotal/{t=\$2} /SwapFree/{f=\$2} END{print int((t-f)/1024)}" /proc/meminfo) MiB:"
  for t in /proc/$PID/task/*; do
    tid=$(basename $t); s=$(cat $t/stat 2>/dev/null) || continue
    c=${s#*(}; c=${c%%)*}; rest=${s##*) }; set -- $rest; ticks=$(( ${12} + ${13} ))
    p=${prev[$tid]:-$ticks}; d=$(( ticks - p )); prev[$tid]=$ticks
    pct=$(( d * 100 / HZ )); [ $pct -ge 5 ] && line="$line $c=$pct%"
  done
  echo "$line" >> "$OUT"
  sleep 1
done
echo DONE >> "$OUT"
