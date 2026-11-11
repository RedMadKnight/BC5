#!/usr/bin/env bash
# BC5 exp 0412 (README section 25): three perf sessions on the title's Render Thread and main thread, for the question
# "why is the title's own code slow here" (the top session's order, 2026-11-11). perf_event_open only: no ptrace, no
# thread stopped, never a bc5-* thread; user-space counters (kernel.perf_event_paranoid is 2).
#   <prefix>-clock.txt.gz   cpu-clock at 1 kHz, user space: tid time ip sym dso         (CPU time per frame, by function)
#   <prefix>-faults.txt.gz  every page fault of the two threads: tid time addr ip sym dso (who faults, on which memory)
#   <prefix>-stat.txt       perf stat per thread every 100 ms: cycles, instructions, dTLB/iTLB load misses, cache
#                           misses (user space), page faults, context switches, migrations; its time column counts
#                           from the "stat starts at monotonic" line of <prefix>.log
#   <prefix>-maps.txt.gz    /proc/<pid>/maps at <maps at s> after the emulator's start (the fault addresses' classes)
# Run INSIDE the ubuntu container. usage: perfall0412.sh <out prefix> <seconds> <maps at s> <thread name> [<thread name> ...]
set -u
export LC_ALL=C
OUT=${1:?out prefix}; SECS=${2:?seconds}; MAPS_AT=${3:?maps at}; shift 3
[ "$#" -ge 1 ] || { echo "thread names, please"; exit 1; }
for n in "$@"; do case "$n" in bc5-*) echo "not a bc5-* thread: $n"; exit 1 ;; esac; done
EP=""
for _ in $(seq 1 90); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 2; done
[ -n "$EP" ] || { echo "# no emulator in 180 s" > "$OUT.log"; exit 0; }
tid_of() { local t c; for t in /proc/"$EP"/task/*; do c=$(cat "$t/comm" 2> /dev/null); [ "$c" = "$1" ] && { basename "$t"; return; }; done; }
TIDS=""
for _ in $(seq 1 60); do
  TIDS=""; ok=1
  for n in "$@"; do t=$(tid_of "$n"); if [ -n "$t" ]; then TIDS="$TIDS${TIDS:+,}$t"; else ok=0; fi; done
  [ "$ok" = 1 ] && break
  sleep 1
done
[ -n "$TIDS" ] || { echo "# none of the threads found" > "$OUT.log"; exit 0; }
T0=$(stat -c %Y "/proc/$EP")
echo "# $(date '+%F %T') emulator $EP, threads $* = $TIDS, from $(($(date +%s) - T0)) s after its start for $SECS s" > "$OUT.log"
perf record -q -k CLOCK_MONOTONIC -e cpu-clock:u -F 1000 -t "$TIDS" -o "$OUT-clock.data" -- sleep "$SECS" >> "$OUT.log" 2>&1 &
P1=$!
perf record -q -k CLOCK_MONOTONIC -e page-faults -c 1 -d -t "$TIDS" -o "$OUT-faults.data" -- sleep "$SECS" >> "$OUT.log" 2>&1 &
P2=$!
echo "# stat starts at monotonic $(cut -d' ' -f1 /proc/uptime) s" >> "$OUT.log"
perf stat -x, -I 100 --per-thread -t "$TIDS" -e cycles:u,instructions:u,dTLB-load-misses:u,iTLB-load-misses:u,cache-misses:u,page-faults,context-switches,cpu-migrations \
    -o "$OUT-stat.txt" -- sleep "$SECS" >> "$OUT.log" 2>&1 &
P3=$!
( while [ -d "/proc/$EP" ] && [ $(($(date +%s) - T0)) -lt "$MAPS_AT" ]; do sleep 1; done
  [ -d "/proc/$EP" ] && gzip -c "/proc/$EP/maps" > "$OUT-maps.txt.gz" 2> /dev/null
  echo "# $(date '+%F %T') maps written at $(($(date +%s) - T0)) s" >> "$OUT.log" ) &
wait "$P1" "$P2" "$P3"
echo "# $(date '+%F %T') recordings ended; clock $(stat -c %s "$OUT-clock.data" 2> /dev/null) bytes, faults $(stat -c %s "$OUT-faults.data" 2> /dev/null) bytes" >> "$OUT.log"
perf script -i "$OUT-clock.data" --ns -F tid,time,ip,sym,dso 2>> "$OUT.log" | gzip -c > "$OUT-clock.txt.gz"
perf script -i "$OUT-faults.data" --ns -F tid,time,addr,ip,sym,dso 2>> "$OUT.log" | gzip -c > "$OUT-faults.txt.gz"
wait
echo "# $(date '+%F %T') scripts written" >> "$OUT.log"
