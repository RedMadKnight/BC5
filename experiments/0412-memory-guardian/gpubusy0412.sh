#!/usr/bin/env bash
# BC5 exp 0412: the GPU's busy share beside a run (README section 19: is a phase bound by the CPU or by the GPU?).
# Read-only, on the host: every second one line "<s since the emulator's start> <gpu_busy_percent> <sclk line>".
# usage: gpubusy0412.sh <out file> <to s>
set -u
export LC_ALL=C
OUT=${1:?out}; TO=${2:?to}
D=/sys/class/drm/card1/device
EP=""
for _ in $(seq 1 90); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 2; done
[ -n "$EP" ] || { echo "# no emulator in 180 s" >> "$OUT"; exit 0; }
T0=$(stat -c %Y "/proc/$EP")
while [ -d "/proc/$EP" ]; do
  now=$(($(date +%s) - T0))
  [ "$now" -ge "$TO" ] && break
  echo "$now $(cat "$D/gpu_busy_percent" 2> /dev/null) $(grep -m1 '\*' "$D/pp_dpm_sclk" 2> /dev/null | tr -d '\n')" >> "$OUT"
  sleep 1
done
echo "# end $(date '+%F %T')" >> "$OUT"
