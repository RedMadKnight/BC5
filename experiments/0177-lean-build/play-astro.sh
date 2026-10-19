#!/usr/bin/env bash
# BC5 track B: play the maintainer's own ASTRO BOT on the direct GPU path, with the latest build
# of the emulator and the settings in ~/bc5-work/bc5-run.env. Run inside the ubuntu distrobox
# (the desktop shortcut does: distrobox enter ubuntu -- ~/bc5-work/play-astro.sh).
# No time limit, no journal, no captures; the emulator's own output goes to
# ~/bc5-work/play-last.log. Close the window to stop.
set -u
# ADR 0011: play-any.sh names another image and its mountpoint with these two.
C=${BC5_FFPFSC:-$HOME/bc5-data/games/"PPSA21567 - ASTRO BOT_4xx.ffpfsc"}
M=${BC5_FFPFSC_MOUNT:-$HOME/bc5-data/mnt/PPSA21567}
EMU=~/bc5-work/kytyplus-build/src/kyty_emulator
ENVF=${BC5_RUN_ENV:-$HOME/bc5-work/bc5-run.env}
LOG=~/bc5-work/play-last.log
# Experiment 0177: BC5_LEAN=1 (the "BC5 emulator (lean)" shortcut) runs the emulator built with
# KYTY_BC5_LEAN in ~/bc5-work/kytyplus-build-lean: no tracing, journal, counters, recorder or
# samplers, inside or outside; its own log file. The title scripts take the same switch.
if [ "${BC5_LEAN:-0}" = 1 ]; then
  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=~/bc5-work/play-lean-last.log
fi
BM=~/bc5-work/bc5-tools-ubuntu/release/bc5-mount

say() { echo "$*"; command -v notify-send >/dev/null 2>&1 && notify-send "BC5" "$*" 2>/dev/null; }

if pgrep -x kyty_emulator >/dev/null; then say "The emulator is already running."; exit 1; fi
[ -x "$EMU" ] || { say "No emulator build at $EMU"; exit 1; }
[ -r "$ENVF" ] || { say "No settings file at $ENVF"; exit 1; }

PLAY_ARGS=""
while IFS= read -r line; do
  case "$line" in ''|'#'*) continue ;; esac
  key=${line%%=*}; val=${line#*=}
  if [ "$key" = PLAY_ARGS ]; then PLAY_ARGS=$val; else export "$key=$val"; fi
done < "$ENVF"
# ADR 0011: another image's own system-module pack (play-any.sh), over the settings file's.
[ -n "${BC5_SYSMODULES_PACK_DIR:-}" ] && export SHADPS4_SYSMODULES_PACK_DIR=$BC5_SYSMODULES_PACK_DIR
unset BC5_GC_DUMP_DIR
[ "${BC5_LEAN:-0}" = 1 ] && unset KYTY_BC5_INPUT_RECORD PLAY_CAPTURE  # exp 0177: no input recorder, no journal
# 2026-10-13: PLAY_CAPTURE=1 in the settings file keeps the direct path journal with the frame
# profile (the timed lines) under ~/bc5-data/captures/play-<date>/gc, to measure a session played
# by hand; the frame rate is unchanged by it (runs 280-299 had it on).
if [ "${PLAY_CAPTURE:-}" = 1 ]; then
  CAPD=~/bc5-data/captures/play-$(date +%Y%m%d-%H%M)
  mkdir -p "$CAPD/gc" && export BC5_GC_DUMP_DIR="$CAPD/gc" BC5_DIRECT_FRAME_PROFILE=1 BC5_DIRECT_TIMING=1
  echo "$CAPD" > ~/bc5-work/last-play-capture
fi
~/bc5-work/pad-volume.sh >> "$LOG" 2>&1 || true; ~/bc5-work/pad-volume.sh --watch $$ >> "$LOG" 2>&1 &  # F94: the pad ALSA volume resets on every replug
export XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0} DISPLAY=${DISPLAY:-:0}

mkdir -p "$M"
MP=""
if ! mountpoint -q "$M"; then
  "$BM" mount "$C" "$M" > ~/bc5-work/play-mount.log 2>&1 &
  MP=$!
  for _ in $(seq 1 100); do mountpoint -q "$M" && break; sleep 0.2; done
fi
mountpoint -q "$M" || { say "Mounting the game failed (see ~/bc5-work/play-mount.log)."; exit 1; }
cleanup() { [ -n "$MP" ] && { fusermount3 -u "$M" 2>/dev/null; wait "$MP" 2>/dev/null; }; }
trap cleanup EXIT

{
  echo "== $(date '+%F %T') emulator $(stat -c '%y' "$EMU" | cut -c1-19)"
  grep -v '^#' "$ENVF" | grep -v '^$'
} > "$LOG"
cd ~/bc5-work
# Experiment 0047: exit code 75 is the F2 menu's "Restart game": start the emulator again, with
# the mount and the settings kept.
while :; do
  # shellcheck disable=SC2086
  "$EMU" --game "$M" --printf-direction Silent --shader-log-direction Silent --command-buffer-dump false $PLAY_ARGS >> "$LOG" 2>&1
  RC=$?
  [ "$RC" = 75 ] || break
  echo "== $(date '+%F %T') restart requested from the F2 menu" >> "$LOG"
done
echo "== $(date '+%F %T') exit $RC" >> "$LOG"
exit $RC
