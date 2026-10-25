#!/usr/bin/env bash
# BC5 experiment (L3/R3 on the DualSense), T1: does SDL see the DualSense's stick clicks at all? Exp 0193's padprobe
# (built on the emulator's own SDL 2.33.0, ~/bc5-work/exp0193/padprobe) listens for SECS seconds with the launch
# environment (SDL_JOYSTICK_DISABLE_UDEV=1) and prints every controller button event. No game, no GPU. Attended: the
# maintainer presses L3 three times, R3 three times, then Cross once and the touchpad once (the references).
# The experiment directory is this script's own directory (~/bc5-work/expNNNN); output goes to its raw/.
# usage: probe.sh [secs]   (on the box)
set -u
SECS=${1:-45}
E=$(cd "$(dirname "$0")" && pwd); R=$E/raw; W=$HOME/bc5-work; LOCK=$W/BOX-LOCK
N=$(basename "$E" | sed -n 's/^exp\([0-9][0-9][0-9][0-9]\)$/\1/p')
[ -n "$N" ] || { echo "run this from ~/bc5-work/expNNNN/: not started"; exit 1; }
PROBE=$W/exp0193/padprobe
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: not started"; exit 1; }
[ -s "$LOCK" ] && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
[ -x "$PROBE" ] || { echo "no $PROBE: not started"; exit 1; }
[ "$SECS" -ge 10 ] && [ "$SECS" -le 120 ] || { echo "10 to 120 s: not started"; exit 1; }
mkdir -p "$R"
OUT=$R/t1-probe-$(date +%H%M%S).txt
echo "exp $N | pad probe: exp 0193's padprobe for $SECS s, no game, no GPU, the maintainer pressing L3/R3 | start $(date +%H:%M:%S)" > "$LOCK"
trap 'grep -q "^exp $N | pad probe" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
{
  echo "# $(date '+%F %T') exp $N T1, $PROBE (md5 $(md5sum < "$PROBE" | cut -c1-8)), $SECS s"
  echo "# press: L3 x3, R3 x3, then Cross x1 and the touchpad x1"
  echo "# DualSense in /proc/bus/input/devices: $(grep -c 'DualSense Wireless Controller"' /proc/bus/input/devices) pad device(s)"
} > "$OUT"
distrobox enter ubuntu -- env SDL_JOYSTICK_DISABLE_UDEV=1 "$PROBE" "$SECS" >> "$OUT" 2>&1
echo "# exit $? at $(date '+%T')" >> "$OUT"
echo "== $OUT"
cat "$OUT"
echo "== counts: leftstick down $(grep -c 'button leftstick .* down' "$OUT"), rightstick down $(grep -c 'button rightstick .* down' "$OUT"), a (Cross) down $(grep -c 'button a .* down' "$OUT"), touchpad down $(grep -c 'button touchpad .* down' "$OUT")"
