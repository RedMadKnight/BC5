#!/usr/bin/env bash
# BC5 experiment 0214: every 10 s until the emulator exits, the CPU time of its APR threads (bc5-apr-q* workers,
# bc5-apr-r* readers; schedstat run time in ns) and the process's VmRSS, RssAnon, RssFile (kB), thread count and
# CPU time (utime + stime, clock ticks), appended to <out>. Read-only /proc reads. usage: cpu0214.sh <out>
OUT=$1
P=""
for _ in $(seq 1 120); do P=$(pgrep -n -x kyty_emulator) && break; sleep 1; done
[ -n "$P" ] || exit 1
echo "# cpu0214 pid $P start $(date '+%F %T')" >> "$OUT"
while [ -d "/proc/$P" ]; do
  now=$(cut -d' ' -f1 /proc/uptime)
  for t in /proc/"$P"/task/*; do
    n=$(cat "$t/comm" 2> /dev/null)
    case $n in bc5-apr-*) echo "t $now $n $(cut -d' ' -f1 "$t/schedstat" 2> /dev/null)" ;; esac
  done
  echo "m $now $(awk '/^(VmRSS|RssAnon|RssFile|Threads):/ {printf "%s %s ", $1, $2}' "/proc/$P/status" 2> /dev/null)cpu $(awk '{print $14 + $15}' "/proc/$P/stat" 2> /dev/null)"
  sleep 10
done >> "$OUT"
echo "# cpu0214 end $(date '+%F %T')" >> "$OUT"
