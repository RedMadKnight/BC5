#!/usr/bin/env bash
# BC5 experiment 0112: per-thread CPU of the emulator and bc5-mount, about once a second from the
# emulator start. usage: topwatch.sh SECS OUT
SECS=$1; OUT=$2; : > "$OUT"
for _ in $(seq 1 600); do PID=$(pgrep -x kyty_emulator | head -1); [ -n "$PID" ] && break; sleep 0.5; done
for i in $(seq 1 "$SECS"); do
  echo "== $i up $(cut -d" " -f1 /proc/uptime)" >> "$OUT"
  top -b -H -n 1 -d 0.5 -w 200 | awk 'NR>7 && $9+0 >= 5' | head -20 >> "$OUT"
done
