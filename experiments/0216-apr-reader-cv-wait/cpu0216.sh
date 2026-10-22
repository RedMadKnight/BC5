#!/usr/bin/env bash
# BC5 experiment 0216: exp 0214's cpu0214.sh with the whole schedstat line. Every 10 s until the emulator exits, for
# each APR thread (bc5-apr-q* workers, bc5-apr-r* readers): run time (ns), run-queue wait (ns) and the number of times
# it ran on a CPU (so the wake-ups); and the process's VmRSS, RssAnon, RssFile (kB), thread count and CPU time
# (utime + stime, clock ticks). Appended to <out>. Read-only /proc reads. usage: cpu0216.sh <out> [pid]
OUT=$1
P=${2:-}
[ -n "$P" ] || for _ in $(seq 1 120); do P=$(pgrep -n -x kyty_emulator) && break; sleep 1; done
[ -n "$P" ] || exit 1
echo "# cpu0216 pid $P start $(date '+%F %T')" >> "$OUT"
while [ -d "/proc/$P" ]; do
  now=$(cut -d' ' -f1 /proc/uptime)
  for t in /proc/"$P"/task/*; do
    n=$(cat "$t/comm" 2> /dev/null)
    case $n in bc5-apr-*) echo "t $now $n $(cat "$t/schedstat" 2> /dev/null)" ;; esac
  done
  echo "m $now $(awk '/^(VmRSS|RssAnon|RssFile|Threads):/ {printf "%s %s ", $1, $2}' "/proc/$P/status" 2> /dev/null)cpu $(awk '{print $14 + $15}' "/proc/$P/stat" 2> /dev/null)"
  sleep 10
done >> "$OUT"
echo "# cpu0216 end $(date '+%F %T')" >> "$OUT"
