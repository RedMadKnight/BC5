#!/usr/bin/env bash
# BC5 experiment 0194 (the night lake's patchwork water): the maintainer's play session on the diagnostic binary
# ~/bc5-work/exp0194/kyty_emulator (the shared build + edit0194.py: the draw journal also writes indirect-draw
# arguments). Normal settings otherwise (play-any.sh -> play-pkg.sh; skips and TF ring as the launcher sets them).
# While it runs: draw-journal windows of 40 graphics buffers every 4 s from t 60 s, the HDR scene target
# 0x116da40000 dumped every 20 s, and a screenshot every 5 s into ~/bc5-work/exp0194/m-<HHMM>/shots.
# Diagnostic only (reads, journals); nothing new runs on the GPU. Shortcut: "BC5 emulator (woda 0194)".
D=$HOME/bc5-work/exp0194/m-$(date +%H%M); mkdir -p "$D/shots"; ME=$$
( while kill -0 "$ME" 2>/dev/null; do
    if pgrep -x kyty_emulator >/dev/null; then
      XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=wayland-0 spectacle -b -n -f -o "$D/shots/$(date +%H%M%S).png" >/dev/null 2>&1
    fi
    sleep 5
  done ) < /dev/null > /dev/null 2>&1 &
echo "$(date "+%F %T") start" > "$D/session.txt"
/usr/bin/distrobox enter ubuntu -- /usr/bin/env BC5_EMU=$HOME/bc5-work/exp0194/kyty_emulator \
  BC5_DIRECT_DRAW_JOURNAL=60:40 BC5_DIRECT_DRAW_JOURNAL_EVERY=4 \
  "BC5_DIRECT_RT_DUMP=60;116da40000:3840:2160:r11g11b10" BC5_DIRECT_RT_DUMP_EVERY=20 \
  $HOME/bc5-work/play-any.sh "$@"
echo "$(date "+%F %T") end; journal $(ls -td $HOME/bc5-data/captures/play-*/gc | head -1)" >> "$D/session.txt"
