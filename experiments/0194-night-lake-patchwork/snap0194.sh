#!/usr/bin/env bash
# exp 0194: one screenshot now into a run directory of ~/bc5-work/exp0194 (spectacle). usage: snap0194.sh <run dir> [name]
O=$1; N=${2:-snap}; F="$HOME/bc5-work/exp0194/$O/shots/$(date +%H%M%S)-$N.png"
XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 spectacle -b -n -f -o "$F" >/dev/null 2>&1
echo "$F"
