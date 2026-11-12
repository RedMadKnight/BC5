#!/usr/bin/env bash
# BC5 exp 0415: perf's cpu-clock at 1 kHz on the title's own threads for a whole load run, on CLOCK_MONOTONIC, leaf
# address with symbol and DSO (exp 0412's perfall0412.sh pattern: perf_event_open only, no ptrace, no thread stopped,
# user space, kernel.perf_event_paranoid 2). Never a bc5-* thread: threads are taken by name and every name that starts
# with "bc5-" or "kyty-" is left out. Threads that start later than 25 s after the emulator are not sampled.
#   <prefix>-clock.txt.gz   tid time ip sym dso
#   <prefix>-tids.txt       tid and name of the sampled threads
# Run INSIDE the ubuntu container. usage: perf0415.sh <out prefix> <seconds>
set -u
export LC_ALL=C
OUT=${1:?out prefix}; SECS=${2:?seconds}
EP=""
for _ in $(seq 1 60); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 1; done
[ -n "$EP" ] || { echo "# no emulator in 60 s" > "$OUT.log"; exit 0; }
pick() {
  local t c
  for t in /proc/"$EP"/task/*; do
    c=$(cat "$t/comm" 2> /dev/null) || continue
    case "$c" in bc5-* | kyty-* | "") continue ;; esac
    echo "$(basename "$t") $c"
  done
}
# The title's threads appear over the first seconds: sample from 4 s (the early ones) and again from 25 s (all).
sleep 4
pick > "$OUT-tids.txt"
TIDS=$(cut -d' ' -f1 "$OUT-tids.txt" | paste -sd, -)
[ -n "$TIDS" ] || { echo "# none of the threads found" > "$OUT.log"; exit 0; }
T0=$(stat -c %Y "/proc/$EP")
echo "# $(date '+%F %T') emulator $EP, $(wc -l < "$OUT-tids.txt") threads from $(($(date +%s) - T0)) s after its start" > "$OUT.log"
perf record -q -k CLOCK_MONOTONIC -e cpu-clock:u -F 1000 -t "$TIDS" -o "$OUT-clock-a.data" -- sleep 21 >> "$OUT.log" 2>&1
[ -d "/proc/$EP" ] || { echo "# the emulator ended in the first 25 s" >> "$OUT.log"; }
pick > "$OUT-tids.txt"
TIDS=$(cut -d' ' -f1 "$OUT-tids.txt" | paste -sd, -)
echo "# $(date '+%F %T') second recording: $(wc -l < "$OUT-tids.txt") threads from $(($(date +%s) - T0)) s" >> "$OUT.log"
if [ -n "$TIDS" ] && [ -d "/proc/$EP" ]; then
  perf record -q -k CLOCK_MONOTONIC -e cpu-clock:u -F 1000 -t "$TIDS" -o "$OUT-clock-b.data" -- sleep "$SECS" >> "$OUT.log" 2>&1 &
  P1=$!
  while [ -d "/proc/$EP" ] && kill -0 "$P1" 2> /dev/null; do sleep 1; done
  # perf's "sleep" child is ours: end the recording when the emulator has ended (perf writes its file on SIGINT).
  kill -INT "$P1" 2> /dev/null
  wait "$P1" 2> /dev/null
fi
echo "# $(date '+%F %T') recordings ended" >> "$OUT.log"
{ for f in "$OUT-clock-a.data" "$OUT-clock-b.data"; do [ -s "$f" ] && perf script -i "$f" --ns -F tid,time,ip,sym,dso 2>> "$OUT.log"; done; } | gzip -c > "$OUT-clock.txt.gz"
rm -f "$OUT-clock-a.data" "$OUT-clock-b.data"
echo "# $(date '+%F %T') scripts written" >> "$OUT.log"
