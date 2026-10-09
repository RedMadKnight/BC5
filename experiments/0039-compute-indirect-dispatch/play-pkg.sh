#!/usr/bin/env bash
# BC5 track B: play the maintainer's own second title from its PS5 package on the direct GPU path,
# with the latest build of the emulator and the settings in ~/bc5-work/bc5-run.env plus what this
# title needs (experiment 0036): the system module pack without the title's own libSceAmpr, its
# GPU heaps imported in full, its own learned-fault file. Run inside the ubuntu distrobox (the
# desktop shortcut does: distrobox enter ubuntu -- ~/bc5-work/play-pkg.sh). No time limit, no
# journal, no captures; the emulator's output goes to ~/bc5-work/play-pkg-last.log.
set -u
PKG=${BC5_PKG:-$HOME/bc5-data/pkg/game.pkg}
M=~/bc5-data/mnt/pkg-play
EMU=~/bc5-work/kytyplus-build/src/kyty_emulator
ENVF=${BC5_RUN_ENV:-$HOME/bc5-work/bc5-run.env}
LOG=~/bc5-work/play-pkg-last.log
BM=~/bc5-work/bc5-tools-ubuntu/release/bc5-mount

say() { echo "$*"; command -v notify-send >/dev/null 2>&1 && notify-send "BC5" "$*" 2>/dev/null; }

if pgrep -x kyty_emulator >/dev/null; then say "The emulator is already running."; exit 1; fi
[ -x "$EMU" ] || { say "No emulator build at $EMU"; exit 1; }
[ -r "$ENVF" ] || { say "No settings file at $ENVF"; exit 1; }
[ -r "$PKG" ] || { say "No package at $PKG"; exit 1; }

PLAY_ARGS=""
while IFS= read -r line; do
  case "$line" in ''|'#'*) continue ;; esac
  key=${line%%=*}; val=${line#*=}
  if [ "$key" = PLAY_ARGS ]; then PLAY_ARGS=$val; else export "$key=$val"; fi
done < "$ENVF"
unset BC5_GC_DUMP_DIR
# This title's settings (experiment 0036); the file below may override them.
export SHADPS4_SYSMODULES_PACK_DIR=$HOME/bc5-data/sysmodules-pack-hle-ampr
export BC5_DIRECT_EAGER_NAMES=RenderGpuWcLarge,RenderGpuWcSmall,RenderGpuRwLarge,RenderGpuRwSmall,CommitIABufferAllocator,AMM
export BC5_DIRECT_LEARNED=$HOME/bc5-work/direct-learned-pkg.txt
export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play
# Experiment 0039: the compute IBs indirect dispatches run (rewritten for the GFX ring), except the
# one program that hangs the single ring.
export BC5_DIRECT_MEC_INDIRECT=1 BC5_DIRECT_MEC_SKIP_PGM=909939900
PKG_ENV=~/bc5-work/bc5-pkg.env
if [ -r "$PKG_ENV" ]; then
  while IFS= read -r line; do
    case "$line" in ''|'#'*) continue ;; esac
    export "${line%%=*}=${line#*=}"
  done < "$PKG_ENV"
fi
~/bc5-work/pad-volume.sh >/dev/null 2>&1 || true
export XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0} DISPLAY=${DISPLAY:-:0}

mkdir -p "$M" "$KYTY_BC5_SAVEDATA_DIR"
MP=""
if ! mountpoint -q "$M"; then
  "$BM" mount "$PKG" "$M" > ~/bc5-work/play-pkg-mount.log 2>&1 &
  MP=$!
  for _ in $(seq 1 300); do mountpoint -q "$M" && break; sleep 0.2; done
fi
mountpoint -q "$M" || { say "Mounting the package failed (see ~/bc5-work/play-pkg-mount.log)."; exit 1; }
cleanup() { [ -n "$MP" ] && { fusermount3 -u "$M" 2>/dev/null; wait "$MP" 2>/dev/null; }; }
trap cleanup EXIT

{
  echo "== $(date '+%F %T') emulator $(stat -c '%y' "$EMU" | cut -c1-19)"
  grep -v '^#' "$ENVF" | grep -v '^$'
  [ -r "$PKG_ENV" ] && grep -v '^#' "$PKG_ENV" | grep -v '^$'
} > "$LOG"
cd ~/bc5-work
# shellcheck disable=SC2086
"$EMU" --game "$M" --printf-direction Silent --shader-log-direction Silent --command-buffer-dump false $PLAY_ARGS >> "$LOG" 2>&1
RC=$?
echo "== $(date '+%F %T') exit $RC" >> "$LOG"
exit $RC
