#!/usr/bin/env bash
# BC5 experiment 0043: the GPU's shader clock (hwmon freq1_input, Hz) every 100 ms while the
# emulator runs, with the monotonic clock (the direct path's journal prints its zero on it,
# "bc5 clock"). Read-only. Usage: clock-sampler.sh OUT
set -u
OUT=$1
F=$(ls /sys/class/drm/card*/device/hwmon/hwmon*/freq1_input 2>/dev/null | head -1)
[ -z "$F" ] && { echo "no freq1_input" >&2; exit 1; }
for _ in $(seq 1 600); do pgrep -x kyty_emulator >/dev/null && break; sleep 0.5; done
: > "$OUT"
while pgrep -x kyty_emulator >/dev/null; do
  printf '%s %s\n' "$(cut -d' ' -f1 /proc/uptime)" "$(cat "$F")" >> "$OUT"
  sleep 0.1
done
