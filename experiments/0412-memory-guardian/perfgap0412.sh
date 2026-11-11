#!/usr/bin/env bash
# BC5 exp 0412 (README section 24): where the Render Thread and game-main are ON THE CPU, by function, on the
# monotonic clock, to be joined with the gap classifier's lines (gapstack0412.py). perf's cpu-clock event at 1 kHz on
# those two threads only (perf_event_open; no ptrace, no thread is stopped; never a bc5-* thread). User space only
# (kernel.perf_event_paranoid is 2). Leaf addresses, no call chains: the guest's code has no frame pointers or
# unwind tables. Run INSIDE the ubuntu container (perf is there since 2026-11-11: apt package linux-perf).
# usage: perfgap0412.sh <out prefix> <seconds> <thread name> [<thread name> ...]
#   writes <out prefix>.data (perf's file) and, when the recording ends, <out prefix>.txt.gz: perf script's
#   "tid time ip sym dso" lines.
set -u
export LC_ALL=C
OUT=${1:?out prefix}; SECS=${2:?seconds}; shift 2
[ "$#" -ge 1 ] || { echo "thread names, please"; exit 1; }
for n in "$@"; do case "$n" in bc5-*) echo "not a bc5-* thread: $n"; exit 1 ;; esac; done
EP=""
for _ in $(seq 1 90); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 2; done
[ -n "$EP" ] || { echo "# no emulator in 180 s" > "$OUT.log"; exit 0; }
tid_of() { local t c; for t in /proc/"$EP"/task/*; do c=$(cat "$t/comm" 2> /dev/null); [ "$c" = "$1" ] && { basename "$t"; return; }; done; }
TIDS=""
for _ in $(seq 1 60); do # the title's threads appear some seconds after the emulator
  TIDS=""; ok=1
  for n in "$@"; do t=$(tid_of "$n"); if [ -n "$t" ]; then TIDS="$TIDS${TIDS:+,}$t"; else ok=0; fi; done
  [ "$ok" = 1 ] && break
  sleep 1
done
[ -n "$TIDS" ] || { echo "# none of the threads found" > "$OUT.log"; exit 0; }
T0=$(stat -c %Y "/proc/$EP")
echo "# $(date '+%F %T') emulator $EP, threads $* = $TIDS, recording from $(($(date +%s) - T0)) s after its start for $SECS s; uptime $(cut -d' ' -f1 /proc/uptime)" > "$OUT.log"
perf record -q -k CLOCK_MONOTONIC -e cpu-clock:u -F 1000 -t "$TIDS" -o "$OUT.data" -- sleep "$SECS" >> "$OUT.log" 2>&1
echo "# $(date '+%F %T') recording ended (rc $?), $(stat -c %s "$OUT.data" 2> /dev/null) bytes" >> "$OUT.log"
perf script -i "$OUT.data" --ns -F tid,time,ip,sym,dso 2>> "$OUT.log" | gzip -c > "$OUT.txt.gz"
echo "# $(date '+%F %T') script written, $(stat -c %s "$OUT.txt.gz" 2> /dev/null) bytes" >> "$OUT.log"
