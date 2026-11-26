#!/usr/bin/env bash
# BC5 (F69/F79/F94): the DualSense is a 4-channel USB audio device; its haptics and speaker
# streams are unfelt and inaudible unless both its PipeWire sink and its ALSA PCM control are at
# full volume. The desktop had the sink at 40 %, and the ALSA control comes back at 76 % (-24 dB)
# every time the pad is plugged in. wpctl, amixer and aplay are the host's; the launchers run on the
# host since 2026-11-24 (before, in the distrobox, this script re-ran itself on the host, F94).
#   pad-volume.sh            set both once
#   pad-volume.sh --watch P  set both every 3 s while process P lives (a replugged pad included)
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}

set_once() {
  local quiet=${1:-}
  for id in $(wpctl status 2>/dev/null | grep -i "DualSense\|Wireless Controller" | grep -iv "source\|input" | sed -E "s/^[^0-9]*([0-9]+)\. .*/\1/"); do
    wpctl set-volume "$id" 1.0 2>/dev/null && [ -z "$quiet" ] && echo "pad sink $id volume 1.0"
  done
  local card
  card=$(aplay -l 2>/dev/null | grep -i "Wireless Controller\|DualSense" | head -1 | sed -E "s/^card ([0-9]+).*/\1/")
  if [ -n "$card" ]; then
    if ! amixer -c "$card" sget PCM 2>/dev/null | grep -q "\[100%\]"; then
      amixer -c "$card" sset PCM 100% >/dev/null 2>&1 && echo "pad card $card PCM 100% ($(date +%T))"
    elif [ -z "$quiet" ]; then
      echo "pad card $card PCM 100%"
    fi
  fi
}

if [ "${1:-}" = "--watch" ]; then
  PID=${2:?process id}
  while kill -0 "$PID" 2>/dev/null; do
    set_once quiet
    sleep 3
  done
else
  set_once
fi
