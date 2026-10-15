#!/usr/bin/env bash
# BC5 (experiment 0107): every GAP s from START s after the emulator appears, COUNT times, the first
# frames of every thread (gdb "thread apply all bt"), for a CPU profile of the title. Ubuntu distrobox.
# usage: pc-sampler-bt.sh START COUNT GAP OUT
set -u
START=$1; COUNT=$2; GAP=$3; OUT=$4
: > "$OUT"
for _ in $(seq 1 300); do PID=$(pgrep -x kyty_emulator | head -1); [ -n "$PID" ] && break; sleep 1; done
[ -z "${PID:-}" ] && { echo "no emulator" >> "$OUT"; exit 1; }
sleep "$START"
for i in $(seq 1 "$COUNT"); do
  kill -0 "$PID" 2>/dev/null || break
  echo "== sample $i $(date +%T.%N) up $(cut -d" " -f1 /proc/uptime)" >> "$OUT"
  gdb -q -batch -p "$PID" -ex "set pagination off" -ex "set debuginfod enabled off" -ex "thread apply all bt 14" 2>/dev/null | grep -E "^Thread |^#[0-9]+ " >> "$OUT"
  sleep "$GAP"
done
