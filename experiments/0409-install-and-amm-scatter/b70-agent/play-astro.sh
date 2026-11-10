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
# 2026-10-25 (exp 0324, the maintainer): with BC5_LEAN=1 this script writes no log at all; BC5_LOGS=1 keeps
# its logs. The normal shortcut logs as before.
ALOG=~/bc5-work/play-mount.log MLOG=~/bc5-work/play-pkg-mount.log
if [ "${BC5_LEAN:-0}" = 1 ] && [ "${BC5_LOGS:-0}" != 1 ]; then LOG=/dev/null ALOG=/dev/null MLOG=/dev/null; fi
BM=~/bc5-work/bc5-tools-ubuntu/release/bc5-mount

say() { echo "$*"; command -v notify-send >/dev/null 2>&1 && notify-send "BC5" "$*" 2>/dev/null; }

if pgrep -x kyty_emulator >/dev/null; then say "The emulator is already running."; exit 1; fi
[ -x "$EMU" ] || { say "No emulator build at $EMU"; exit 1; }
[ -r "$ENVF" ] || { say "No settings file at $ENVF"; exit 1; }
# BC5_GAME_DIR: when set, the game is already installed — skip image check and mount.
if [ -z "${BC5_GAME_DIR:-}" ]; then
  [ -r "$C" ] || { say "No image at $C"; exit 1; }
fi

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
# 2026-10-22 (the maintainer asked): submission chains across the game thread's ioctls (ADR 0010 section B)
# by default, as for the second title. Measured with tools/scripts/astro-route.sh (AC0/AC1): the title's
# 60-fps cap with and without, audio clean, no hang; 8 against 2 seconds with a frame gap over 70 ms.
# BC5_DIRECT_CHAIN=0 turns them off.
export BC5_DIRECT_CHAIN=${BC5_DIRECT_CHAIN:-2}
# BC5 (2026-10-23, exps 0227-0229, F286/F287): APR read-ahead is on again, with the fix that leaves
# large and parallel-run loading buffers to the worker. The slow loads of 10-22/23 were the near-full
# drive (F286), not read-ahead; the fix keeps loads equal and speeds the cutscene clock-voice reads.
# KYTY_BC5_APR_READAHEAD=0 turns it off.
export KYTY_BC5_APR_READAHEAD=${KYTY_BC5_APR_READAHEAD:-4}
# Experiment 0301 (the maintainer asked, 2026-10-25): MangoHud is part of the emulator: it loads hidden and
# Emulation > MangoHud shows its hardware figures and the title's frame rate (saved per title in the input
# configuration). KYTY_BC5_MANGOHUD=0 keeps MangoHud out, =1 shows it from the start; KYTY_BC5_OSD_FPS=1 the
# frame rate alone. The former BC5_MANGOHUD=1 switch and its shortcut are gone.
export XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0} DISPLAY=${DISPLAY:-:0}

# BC5_GAME_DIR: when set, run from the installed directory (no mount).
if [ -n "${BC5_GAME_DIR:-}" ]; then
  GAME_ROOT="$BC5_GAME_DIR"
  MP=""
else
  GAME_ROOT="$M"
  mkdir -p "$M"
  MP=""
  if ! mountpoint -q "$M"; then
    "$BM" mount "$C" "$M" > "$ALOG" 2>&1 &
    MP=$!
    for _ in $(seq 1 100); do mountpoint -q "$M" && break; sleep 0.2; done
  fi
  mountpoint -q "$M" || { say "Mounting the game failed (see $ALOG; with BC5_LEAN=1 run with BC5_LOGS=1 to keep it)."; exit 1; }
fi
# 2026-10-25 (the maintainer's yes): a failed unmount no longer hangs the launcher (exp 0301's T1 waited an hour):
# retry, then a lazy unmount, log the failure, and wait for bc5-mount at most 10 s.
cleanup() {
  [ -n "$MP" ] || return 0
  local i
  for i in 1 2 3 4 5; do fusermount3 -u "$M" 2>> "$MLOG" && break; sleep 1; done
  if mountpoint -q "$M"; then
    echo "$(date '+%F %T') unmount of $M failed 5 times; lazy unmount" >> "$MLOG"
    fusermount3 -u -z "$M" 2>> "$MLOG"
  fi
  for i in $(seq 1 20); do kill -0 "$MP" 2> /dev/null || break; sleep 0.5; done
  if kill -0 "$MP" 2> /dev/null; then
    echo "$(date '+%F %T') bc5-mount $MP still running 10 s after the unmount; not waited for" >> "$MLOG"
  else
    wait "$MP" 2> /dev/null
  fi
}
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
  "$EMU" --game "$GAME_ROOT" --printf-direction Silent --shader-log-direction Silent --command-buffer-dump false $PLAY_ARGS >> "$LOG" 2>&1
  RC=$?
  [ "$RC" = 75 ] || break
  echo "== $(date '+%F %T') restart requested from the F2 menu" >> "$LOG"
done
echo "== $(date '+%F %T') exit $RC" >> "$LOG"
exit $RC
