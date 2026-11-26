#!/usr/bin/env bash
# BC5 exp 0439 (tag vz439h, 11-24 night): drive a running mw439 start by hand from the laptop: the keys go to the run's
# KYTY_BC5_INPUT_CMD file (one "press <key>" line each, 1.2 s apart), then one shot (private) after 1.5 s.
#   live439.sh <tag> <shot name> [key ...]
set -u
E=$HOME/bc5-work/exp0439; T=$1; N=$2; shift 2
C=$E/in-$T.cmd; SH=$HOME/bc5-data/priv/t3-screens/$T
[ -f "$C" ] || { echo "no $C"; exit 1; }
pgrep "^kyty_emulator" > /dev/null || { echo "no emulator"; exit 1; }
for k in "$@"; do printf 'press %s\n' "$k" >> "$C"; sleep 1.2; done
sleep 1.5
wl=$(ls -1 /run/user/$(id -u)/ | grep -m1 -E '^wayland-[0-9]+$')
flock "$SH/.shot.lock" env XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=$wl DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus timeout 10 spectacle -b -n -f -o "$SH/live-$N.png" > /dev/null 2>&1
echo "$(date +%T) $N: $* -> $SH/live-$N.png"
