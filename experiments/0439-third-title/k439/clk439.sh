#!/usr/bin/env bash
# BC5 exp 0439 (tag clk439): a 20-Hz sampler for the early-hang run (the top session's step 3 of 11-22 ~06:55): from the
# emulator's start for 35 s, the GPU clock (hwmon freq1_input, sclk), temperature, power (average and input) and the
# emulator's CPU time (utime + stime, clock ticks). Read-only sysfs and /proc; writes one line per sample to $1.
#   clk439.sh <out file>
OUT=${1:?out}
H=$(ls -d /sys/class/drm/card1/device/hwmon/hwmon* | head -1)
TCK=$(getconf CLK_TCK)
for i in $(seq 1 1200); do P=$(pgrep "^kyty_emulator" | head -1); [ -n "$P" ] && break; sleep 0.25; done
[ -n "$P" ] || { echo "no emulator in 300 s" > "$OUT"; exit 1; }
t0=$(date +%s.%N)
echo "# pid $P, hwmon $H, CLK_TCK $TCK; t_s sclk_MHz temp_C power_avg_W power_in_W cpu_ticks" > "$OUT"
while :; do
  t=$(date +%s.%N)
  e=$(echo "$t - $t0" | bc)
  [ "$(echo "$e > 35" | bc)" = 1 ] && break
  [ -d /proc/$P ] || { echo "# emulator gone at $e s" >> "$OUT"; break; }
  c=$(awk '{print $14 + $15}' /proc/$P/stat 2> /dev/null)
  echo "$e $(( $(cat $H/freq1_input) / 1000000 )) $(( $(cat $H/temp1_input) / 1000 )) $(( $(cat $H/power1_average) / 1000000 )) $(( $(cat $H/power1_input) / 1000000 )) $c" >> "$OUT"
  sleep 0.05
done
