#!/usr/bin/env bash
# BC5 experiment 0009: run the maintainer's own ASTRO BOT (bc5-mount) in KytyPlus (GPL-2.0) and record how far it gets.
# Run inside the ubuntu distrobox. Output under ~/bc5-data/captures (never committed).
set -u
C=~/bc5-data/games/"PPSA21567 - ASTRO BOT_4xx.ffpfsc"
M=~/bc5-data/mnt/PPSA21567
CAP=~/bc5-data/captures/kytyplus-$(date +%Y%m%d-%H%M)
RUN=${RUN_SECONDS:-180}
mkdir -p "$M" "$CAP/cb" "$CAP/shaders" "$CAP/shots"
BM=~/bc5-work/bc5-tools-ubuntu/release/bc5-mount
mountpoint -q "$M" || { "$BM" mount "$C" "$M" > "$CAP/bc5-mount.log" 2>&1 & MP=$!; trap "fusermount3 -u \"$M\" 2>/dev/null; wait $MP 2>/dev/null" EXIT; }
for _ in $(seq 1 100); do mountpoint -q "$M" && break; sleep 0.2; done
mountpoint -q "$M" || { echo "mount failed"; cat "$CAP/bc5-mount.log"; exit 1; }
echo "mounted: $(ls "$M" | tr "\n" " ")"
export XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=wayland-0 DISPLAY=:0
S=$(date +%s)
cd "$CAP"
timeout --signal=INT --kill-after=15 "$RUN" ~/bc5-work/kytyplus-build/src/kyty_emulator --game "$M" \
  --printf-direction File --printf-output-file "$CAP/guest-printf.txt" \
  --command-buffer-dump true --command-buffer-dump-folder "$CAP/cb" \
  --shader-log-direction File --shader-log-folder "$CAP/shaders" \
  "$@" > "$CAP/kyty.log" 2>&1 &
EP=$!
for t in 30 90 150; do
  sleep $(( t - ( $(date +%s) - S ) )) 2>/dev/null
  kill -0 $EP 2>/dev/null || break
  distrobox-host-exec spectacle -b -n -f -o "$CAP/shots/t${t}.png" >/dev/null 2>&1 || true
done
wait $EP; RC=$?
echo "kyty exit $RC after $(( $(date +%s) - S )) s (timeout=$RUN)"
echo "log lines: $(wc -l < "$CAP/kyty.log"); cb files: $(ls "$CAP/cb" | wc -l); shader files: $(ls "$CAP/shaders" | wc -l); shots: $(ls "$CAP/shots" | tr "\n" " ")"
echo "$CAP" > ~/bc5-work/last-kytyplus
