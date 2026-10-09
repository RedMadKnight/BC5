#!/usr/bin/env bash
# BC5: run a game from a PS5 package (.pkg) mounted by bc5-mount, unattended, with the settings
# of ~/bc5-work/bc5-run.env (the system module pack taken from ~/bc5-data/sysmodules-pack), a
# capture directory and screenshots, like run-astro-kytyplus.sh. Run inside the ubuntu distrobox.
# usage: run-pkg.sh <package> <seconds> [emulator args...]   (env: AUTOPRESS, SAVE_DIR, PACK_DIR, EAGER_NAMES, LEARNED, EMU_WRAP, PRINTF_DIR=Silent)
set -u
PKG=$1; RUN=${2:-180}; shift 2
M=~/bc5-data/mnt/pkg-game
CAP=~/bc5-data/captures/pkg-$(date +%Y%m%d-%H%M)
BM=~/bc5-work/bc5-tools-ubuntu/release/bc5-mount
EMU=~/bc5-work/kytyplus-build/src/kyty_emulator
mkdir -p "$M" "$CAP/cb" "$CAP/shaders" "$CAP/shots" "$CAP/gc"
while IFS= read -r line; do
  case "$line" in ''|'#'*|PLAY_ARGS=*) continue ;; esac
  export "${line%%=*}=${line#*=}"
done < ~/bc5-work/bc5-run.env
export SHADPS4_SYSMODULES_PACK_DIR=${PACK_DIR:-$HOME/bc5-data/sysmodules-pack}
export KYTY_BC5_SAVEDATA_DIR=${SAVE_DIR:-$HOME/bc5-work/_SaveData-pkg}
export BC5_GC_DUMP_DIR="$CAP/gc" BC5_DIRECT_TIMING=1 BC5_DIRECT_FRAME_PROFILE=1
[ -n "${AUTOPRESS:-}" ] && export KYTY_BC5_AUTOPRESS="$AUTOPRESS"
# The title's GPU heaps (experiment 0036): imported in full from the start instead of learned
# from GPU faults one 96 MiB window per 14 s freeze; and its own learned-fault file, apart from
# ASTRO BOT's.
[ -n "${EAGER_NAMES:-}" ] && export BC5_DIRECT_EAGER_NAMES="$EAGER_NAMES"
export BC5_DIRECT_LEARNED=${LEARNED:-$HOME/bc5-work/direct-learned-pkg.txt}
export XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=wayland-0 DISPLAY=:0
mountpoint -q "$M" || { "$BM" mount "$PKG" "$M" > "$CAP/bc5-mount.log" 2>&1 & MP=$!; trap "fusermount3 -u \"$M\" 2>/dev/null; wait $MP 2>/dev/null" EXIT; }
for _ in $(seq 1 300); do mountpoint -q "$M" && break; sleep 0.2; done
mountpoint -q "$M" || { echo "mount failed"; cat "$CAP/bc5-mount.log"; exit 1; }
echo "mounted: $(ls "$M" | wc -l) entries at the root"
~/bc5-work/pad-volume.sh >/dev/null 2>&1 || true
S=$(date +%s)
cd "$CAP"
timeout --signal=INT --kill-after=15 "$RUN" ${EMU_WRAP:-} "$EMU" --game "$M" \
  --printf-direction ${PRINTF_DIR:-File} --printf-output-file "$CAP/guest-printf.txt" \
  --command-buffer-dump false --command-buffer-dump-folder "$CAP/cb" \
  --shader-log-direction File --shader-log-folder "$CAP/shaders" \
  "$@" > "$CAP/kyty.log" 2>&1 &
EP=$!
for t in 20 45 75 120 180 240 300 360 420 480 540 600; do
  [ "$t" -ge "$RUN" ] && break
  sleep $(( t - ( $(date +%s) - S ) )) 2>/dev/null
  kill -0 $EP 2>/dev/null || break
  distrobox-host-exec spectacle -b -n -f -o "$CAP/shots/t${t}.png" >/dev/null 2>&1 || true
done
wait $EP; RC=$?
echo "kyty exit $RC after $(( $(date +%s) - S )) s (timeout=$RUN)"
echo "log lines: $(wc -l < "$CAP/kyty.log"); printf lines: $(wc -l < "$CAP/guest-printf.txt" 2>/dev/null); shots: $(ls "$CAP/shots" | tr "\n" " ")"
echo "$CAP" > ~/bc5-work/last-pkg
