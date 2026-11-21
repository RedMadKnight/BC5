#!/usr/bin/env bash
# BC5 exp 0438 (tags m438 / f438 runs): perf on the title's Render Thread beside one run, started by run0438l.sh at G
# (N_SIDE). After exp 0432's prof0432.sh: read-only towards the emulator, /proc reads and perf_event_open in user
# space (kernel.perf_event_paranoid stays as it is); no ptrace, no signal, no thread stopped. A run with this beside it is
# NOT a speed measurement (diagnosis).
#   PROF_MODE=cpu     perf record -k CLOCK_MONOTONIC -e cpu-clock:u -F 999 -t <Render Thread>   (the lean P runs)
#   PROF_MODE=faults  perf record -k CLOCK_MONOTONIC -e page-faults:u -c 1 -d -t <Render Thread> (the normal F runs:
#                     every user-space fault of the thread, with its data address)
#   PROF_MODE=all     perf record -k CLOCK_MONOTONIC -e cpu-clock:u -F 199 -p <pid> (every thread; perf script with the
#                     thread's comm), and every second each thread's schedstat and state (the run of the top session's
#                     2026-11-21 order: which threads run and which wait while the Render Thread spins)
#   <prefix>-perf.data, <prefix>-perf.txt.gz  perf script (--ns): time, ip, symbol, dso (+ addr for faults)
#   <prefix>-threads.txt  (all mode) every second: "T <uptime s>" then per thread "tid comm state run_ns wait_ns slices"
#   <prefix>-maps-<n>.txt  /proc/<pid>/maps every 10 s ("T <uptime s>" first)
#   <prefix>-tid.txt   the Render Thread's tid and when it was found
# usage: prof0438.sh <emulator pid> <out prefix> <seconds>
set -u
export LC_ALL=C
EP=${1:?pid}; OUT=${2:?prefix}; SECS=${3:?seconds}; MODE=${PROF_MODE:-cpu}
case "$EP$SECS" in *[!0-9]*) echo "pid and seconds are numbers"; exit 1 ;; esac
case "$MODE" in cpu | faults | all) ;; *) echo "PROF_MODE is cpu, faults or all"; exit 1 ;; esac
[ -d "/proc/$EP" ] && [ "$(cat "/proc/$EP/comm" 2> /dev/null)" = kyty_emulator ] || { echo "pid $EP is not a kyty_emulator"; exit 1; }
[ -n "$OUT" ] && [ -d "$(dirname "$OUT")" ] || { echo "no directory for $OUT"; exit 1; }
TID=""
for _ in $(seq 1 30); do
  for t in /proc/"$EP"/task/*; do [ "$(cat "$t/comm" 2> /dev/null)" = "Render Thread" ] && { TID=${t##*/}; break; }; done
  [ -n "$TID" ] && break
  sleep 1
done
[ -n "$TID" ] || { echo "no Render Thread in pid $EP"; exit 1; }
echo "tid $TID found at uptime $(cut -d' ' -f1 /proc/uptime)" > "$OUT-tid.txt"
PP=""
trap '[ -n "$PP" ] && kill "$PP" 2> /dev/null; exit 0' TERM INT HUP
TGT="-t $TID"
case "$MODE" in
  cpu) EV="-e cpu-clock:u -F 999"; FIELDS="tid,time,ip,sym,dso" ;;
  faults) EV="-e page-faults:u -c 1 -d"; FIELDS="tid,time,ip,sym,dso,addr" ;;
  all) EV="-e cpu-clock:u -F 199"; FIELDS="comm,tid,time,ip,sym,dso"; TGT="-p $EP" ;;
esac
# stdin from /dev/null: distrobox would eat the caller's (LESSONS R07)
distrobox enter ubuntu -- /usr/bin/bash -c 'command -v perf > /dev/null || { echo "no perf in the container"; exit 3; }
  # shellcheck disable=SC2086
  perf record -q -k CLOCK_MONOTONIC $4 $1 -o "$2-perf.data" -- sleep "$3" 2>&1
  perf script -i "$2-perf.data" --ns -F "$5" 2> "$2-perf-script.err" | gzip -1 > "$2-perf.txt.gz"
  echo "perf done: $(zcat "$2-perf.txt.gz" | wc -l) lines"' _ "$TGT" "$OUT" "$SECS" "$EV" "$FIELDS" > "$OUT-perf.log" 2>&1 < /dev/null &
PP=$!
END=$(($(date +%s) + SECS)); n=0
LAST=0
while [ "$(date +%s)" -lt "$END" ] && [ -d "/proc/$EP" ]; do
  NOW=$(date +%s)
  if [ $((NOW - LAST)) -ge 10 ]; then
    { echo "T $(cut -d' ' -f1 /proc/uptime)"; cat "/proc/$EP/maps" 2> /dev/null; } > "$OUT-maps-$n.txt"
    n=$((n + 1)); LAST=$NOW
  fi
  if [ "$MODE" = all ]; then
    {
      echo "T $(cut -d' ' -f1 /proc/uptime)"
      for t in /proc/"$EP"/task/*; do
        c=$(cat "$t/comm" 2> /dev/null) || continue
        st=$(cat "$t/stat" 2> /dev/null) || continue
        ss=$(cat "$t/schedstat" 2> /dev/null) || continue
        st=${st##*) }
        echo "${t##*/} ${c// /_} ${st%% *} $ss"
      done
    } >> "$OUT-threads.txt"
    sleep 1
  else
    sleep 10
  fi
done
wait "$PP" 2> /dev/null
echo "prof0438 done $(date '+%F %T'), mode $MODE, tid $TID"
