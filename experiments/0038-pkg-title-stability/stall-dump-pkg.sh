#!/usr/bin/env bash
# BC5: wait for kyty_emulator to stop submitting (no new journal lines for $QUIET seconds after
# $MIN seconds of run time), then dump every thread's state and backtrace. Run inside the ubuntu
# distrobox, in parallel with lle-cycle.sh. Output: ~/bc5-work/stall-dump.txt
set -u
MIN=${1:-30}; QUIET=${2:-8}; OUT=${STALL_OUT:-$HOME/bc5-work/stall-dump-pkg.txt}
: > "$OUT"
for _ in $(seq 1 120); do PID=$(pgrep -x kyty_emulator | head -1); [ -n "$PID" ] && break; sleep 1; done
[ -z "${PID:-}" ] && { echo "no emulator" >> "$OUT"; exit 1; }
START=$(date +%s)
LOG=""
while kill -0 "$PID" 2>/dev/null; do
  sleep 2
  NOW=$(date +%s)
  [ $((NOW - START)) -lt "$MIN" ] && continue
  [ -z "$LOG" ] && LOG=$(ls -t ~/bc5-data/captures/pkg-*/gc/direct.log 2>/dev/null | head -1)
  [ -z "$LOG" ] && continue
  AGE=$((NOW - $(stat -c %Y "$LOG")))
  if [ "$AGE" -ge "$QUIET" ]; then
    echo "== stall detected $((NOW - START)) s after attach start; journal quiet for $AGE s; pid $PID" >> "$OUT"
    for t in /proc/$PID/task/*; do
      printf "%s %s %s\n" "$(basename $t)" "$(cat $t/comm 2>/dev/null)" "$(awk '{print $3}' $t/stat 2>/dev/null)"
    done | sort -k3 >> "$OUT"
    echo "== backtraces" >> "$OUT"
    gdb -q -batch -p "$PID" -ex "set pagination off" -ex "thread apply all bt 18" >> "$OUT" 2>&1
    echo "== done" >> "$OUT"
    exit 0
  fi
done
echo "emulator exited before a stall" >> "$OUT"
