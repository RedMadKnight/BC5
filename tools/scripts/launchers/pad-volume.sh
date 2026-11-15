#!/usr/bin/env bash
# BC5 (F69/F79/F94): the DualSense is a 4-channel USB audio device; its haptics and speaker
# streams are unfelt and inaudible unless both its PipeWire sink and its ALSA PCM control are at
# full volume. The desktop had the sink at 40 %, and the ALSA control comes back at 76 % (-24 dB)
# every time the pad is plugged in. wpctl, amixer and aplay exist only on the host, so inside the
# distrobox container (where the launchers run) the script re-runs itself on the host; before
# F94 it silently did nothing there.
#   pad-volume.sh            set both once
#   pad-volume.sh --watch P  set both every 3 s while process P lives (a replugged pad included)
if ! command -v wpctl >/dev/null 2>&1 && command -v distrobox-host-exec >/dev/null 2>&1; then
  exec distrobox-host-exec "$0" "$@"
fi
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
