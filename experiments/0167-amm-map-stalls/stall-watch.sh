#!/usr/bin/env bash
# BC5 (experiment 0167): when the direct journal of the running emulator stops growing for HOLD ms,
# dump every thread's stack (eu-stack -m) into OUTDIR/<time>.txt, at most MAX times, then every
# 2 s while the stall lasts. usage: stall-watch.sh <outdir> [hold_ms=400] [max=12]
set -u
OUT=$1; HOLD=${2:-400}; MAX=${3:-12}; mkdir -p "$OUT"
for _ in $(seq 1 300); do PID=$(pgrep -x kyty_emulator | head -1); [ -n "$PID" ] && break; sleep 1; done
[ -z "${PID:-}" ] && { echo "no emulator" > "$OUT/none.txt"; exit 1; }
sleep 30
L=""; for _ in $(seq 1 60); do L=$(ls -t ~/bc5-data/captures/play-*/gc/direct.log 2>/dev/null | head -1); [ -s "$L" ] && break; sleep 1; done
echo "watching $L of pid $PID" > "$OUT/watch.log"
last=-1; same_ms=0; n=0; lastdump=0
while kill -0 "$PID" 2>/dev/null && [ $n -lt $MAX ]; do
  s=$(stat -c %s "$L" 2>/dev/null || echo 0)
  if [ "$s" = "$last" ]; then same_ms=$((same_ms+100)); else same_ms=0; last=$s; fi
  now=$(date +%s%N); now=$((now/1000000))
  if [ $same_ms -ge $HOLD ] && [ $((now-lastdump)) -ge 2000 ]; then
    f="$OUT/$(date +%H%M%S.%N | cut -c1-10)-stall${same_ms}ms.txt"
    { echo "== stall ${same_ms} ms at $(date +%T.%N | cut -c1-12), journal $s bytes"; for t in /proc/$PID/task/*; do echo "thread $(basename $t) $(cat $t/comm 2>/dev/null) $(cut -d" " -f3 $t/stat 2>/dev/null)"; done; eu-stack -m -p "$PID" 2>&1; } > "$f"
    n=$((n+1)); lastdump=$now; echo "dump $n: $f" >> "$OUT/watch.log"
  fi
  sleep 0.1
done
echo "done $n dumps" >> "$OUT/watch.log"
