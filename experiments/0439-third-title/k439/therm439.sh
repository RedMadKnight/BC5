#!/usr/bin/env bash
# BC5 exp 0439 (tag vz439k, step 4): GPU and CPU temperature, GPU clock and power, GPU busy, mean CPU clock every 2 s
# while the given user unit is active.   therm439.sh <unit> > out
U=${1:?unit}
G=$(ls -d /sys/class/drm/card*/device | head -1); H=$(ls -d "$G"/hwmon/hwmon* | head -1)
C=$(for h in /sys/class/hwmon/hwmon*; do [ "$(cat "$h/name")" = k10temp ] && echo "$h"; done | head -1)
while systemctl --user is-active -q "$U"; do
    mhz=$(awk -F: '/cpu MHz/ {s += $2; n++} END {printf "%d", s / n}' /proc/cpuinfo)
    echo "$(date +%T) gpuT $(( $(cat "$H/temp1_input") / 1000 )) sclkMHz $(( $(cat "$H/freq1_input" 2> /dev/null || echo 0) / 1000000 )) pwrW $(( $(cat "$H/power1_average" 2> /dev/null || echo 0) / 1000000 )) busy $(cat "$G/gpu_busy_percent") cpuT $(( $(cat "$C/temp1_input") / 1000 )) cpuMHz $mhz"
    sleep 2
done
