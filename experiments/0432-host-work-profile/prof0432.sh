#!/usr/bin/env bash
# BC5 exp 0432: the profiler beside one run, started by run0432f.sh at G (N_SIDE). Read-only towards the emulator:
# /proc reads and perf_event_open (cpu-clock, user space; kernel.perf_event_paranoid stays as it is). No ptrace, no
# signal to the emulator, no thread is stopped. A run with this beside it is NOT a speed measurement.
#   <prefix>-threads.txt  every 5 s: "T <mono s>" then per thread "tid comm utime stime run_ns wait_ns slices"
#   <prefix>-gpu.txt      every 5 s: "T <mono s>" then the drm-engine-* / drm-memory lines of the emulator's DRM fds
#   <prefix>-perf.data    perf record -e cpu-clock:u -F 199 -p <pid> (all threads), if perf is in the ubuntu container
#   <prefix>-perf-*.txt   perf report: by thread; by thread+dso+symbol; by dso+symbol
# usage: prof0432.sh <emulator pid> <out prefix> <seconds>
set -u
export LC_ALL=C
EP=${1:?pid}; OUT=${2:?prefix}; SECS=${3:?seconds}
case "$EP$SECS" in *[!0-9]*) echo "pid and seconds are numbers"; exit 1 ;; esac
[ -d "/proc/$EP" ] && [ "$(cat "/proc/$EP/comm" 2> /dev/null)" = kyty_emulator ] || { echo "pid $EP is not a kyty_emulator"; exit 1; }
[ -n "$OUT" ] && [ -d "$(dirname "$OUT")" ] || { echo "no directory for $OUT"; exit 1; }
PP=""
trap '[ -n "$PP" ] && kill "$PP" 2> /dev/null; exit 0' TERM INT HUP
mono() { cut -d' ' -f1 /proc/uptime; }
if [ "${PROF_PERF:-1}" = 1 ]; then
  # stdin from /dev/null: distrobox would eat the caller's (LESSONS R07)
  distrobox enter ubuntu -- /usr/bin/bash -c 'command -v perf > /dev/null || { echo "no perf in the container"; exit 3; }
    perf record -q -k CLOCK_MONOTONIC -e cpu-clock:u -F 199 -p "$1" -o "$2-perf.data" -- sleep "$3" 2>&1
    perf report -i "$2-perf.data" --stdio --no-children --sort comm 2> /dev/null | grep -v "^$" | head -80 > "$2-perf-thread.txt"
    perf report -i "$2-perf.data" --stdio --no-children --sort comm,dso,symbol 2> /dev/null | grep -v "^$" | head -400 > "$2-perf-thread-sym.txt"
    perf report -i "$2-perf.data" --stdio --no-children --sort dso,symbol 2> /dev/null | grep -v "^$" | head -300 > "$2-perf-sym.txt"
    echo "perf done"' _ "$EP" "$OUT" "$SECS" > "$OUT-perf.log" 2>&1 < /dev/null &
  PP=$!
fi
FDS=""
for f in /proc/"$EP"/fdinfo/*; do grep -q '^drm-driver:' "$f" 2> /dev/null && FDS="$FDS $f"; done
END=$(($(date +%s) + SECS))
while [ "$(date +%s)" -lt "$END" ] && [ -d "/proc/$EP" ]; do
  {
    echo "T $(mono)"
    for t in /proc/"$EP"/task/*; do
      c=$(cat "$t/comm" 2> /dev/null) || continue
      st=$(cat "$t/stat" 2> /dev/null) || continue
      ss=$(cat "$t/schedstat" 2> /dev/null) || continue
      st=${st##*) }                       # after the comm: field 3 (state) is now $1, utime $12, stime $13
      # shellcheck disable=SC2086
      set -- $st
      echo "${t##*/} ${c// /_} ${12} ${13} $ss"
    done
  } >> "$OUT-threads.txt"
  {
    echo "T $(mono)"
    for f in $FDS; do grep -E '^drm-(client-id|engine-|memory-|total-|resident-)' "$f" 2> /dev/null | tr '\n' ';'; echo; done
  } >> "$OUT-gpu.txt"
  sleep 5
done
[ -n "$PP" ] && wait "$PP" 2> /dev/null
echo "prof0432 done $(date '+%F %T')"
