#!/usr/bin/env bash
# BC5 (experiment 0191): screenshots of the run at fixed seconds after the emulator starts (spectacle, KDE Wayland session).
# usage: shots.sh <out dir> <t1> [t2 ...]
OUT=$1; shift; mkdir -p "$OUT"
for _ in $(seq 1 90); do pgrep -x kyty_emulator >/dev/null && break; sleep 1; done
T0=$(date +%s)
for t in "$@"; do
  while [ $(( $(date +%s) - T0 )) -lt "$t" ]; do pgrep -x kyty_emulator >/dev/null || exit 0; sleep 1; done
  XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 spectacle -b -n -f -o "$OUT/t$(printf %03d "$t").png" >/dev/null 2>&1 || true
done
