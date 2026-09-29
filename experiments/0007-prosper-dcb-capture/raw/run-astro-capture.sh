#!/usr/bin/env bash
# BC5: mount the maintainer's own ASTRO BOT container with bc5-mount and run it headless in the
# locally built Prosper (HANDOFF D10), capturing raw DCBs (local patch) and compute shaders.
# Everything is written under ~/bc5-data/captures (never committed). Run inside the ubuntu distrobox.
set -u
C=~/bc5-data/games/"PPSA21567 - ASTRO BOT_4xx.ffpfsc"
M=~/bc5-data/mnt/PPSA21567
CAP=~/bc5-data/captures/astro-$(date +%Y%m%d-%H%M)
mkdir -p "$M" "$CAP/dcb" "$CAP/shaders" "$CAP/shots" ~/bc5-work/prosper-savedata
BM=~/bc5-work/bc5-tools-ubuntu/release/bc5-mount
"$BM" inspect "$C" > "$CAP/inspect.txt" 2>&1
"$BM" mount "$C" "$M" > "$CAP/bc5-mount.log" 2>&1 &
MP=$!
trap 'fusermount3 -u "$M" 2>/dev/null; wait $MP 2>/dev/null' EXIT
for _ in $(seq 1 100); do mountpoint -q "$M" && break; sleep 0.2; done
mountpoint -q "$M" || { echo "mount failed"; cat "$CAP/bc5-mount.log"; exit 1; }
echo "mounted: $(ls "$M" | tr "\n" " ")"
S=$(date +%s)
cd ~/src/prosper/prosper
BC5_AGC_DUMP_DIR="$CAP/dcb" BC5_AGC_DUMP_LIMIT=3000 PROSPER_SHADER_DUMP="$CAP/shaders" \
PROSPER_GUEST_ARGS=-force-gfx-direct PROSPER_AVP_SYNTH_FRAMES=120 PROSPER_RENDER_SCALE=4 \
PROSPER_SAVEDATA_DIR=~/bc5-work/prosper-savedata \
timeout 900 ~/bc5-work/prosper-build/screenshot "$M" --out "$CAP/shots" --count 3 --seconds 10 \
    --warmup-seconds 60 --timeout 840 > "$CAP/prosper.log" 2>&1
echo "prosper exit $? after $(( $(date +%s) - S )) s"
echo "dcb files: $(ls "$CAP/dcb" | wc -l) ($(du -sh "$CAP/dcb" | cut -f1)); shaders: $(ls "$CAP/shaders" | wc -l); shots: $(ls "$CAP/shots" | tr "\n" " ")"
echo "$CAP" > ~/bc5-work/last-capture
