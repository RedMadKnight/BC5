#!/usr/bin/env bash
# BC5 track B: play the maintainer's own second title from its PS5 package (or an unpacked copy, BC5_GAME_DIR) on the
# direct GPU path, with the latest build of the emulator and the settings in ~/bc5-work/bc5-run.env. Runs on the host
# (since 2026-11-24; the build stays in the ubuntu distrobox, tools/scripts/host-deps-check.sh checks each build for
# the host). Started over ssh it must go through the user manager (systemd-run --user) for rtkit's realtime (F860).
# No time limit, no buffer captures; the emulator's output goes to ~/bc5-work/play-pkg-last.log.
set -u
ulimit -c 0  # exp 0409/0413: no core dump of the emulator (systemd-coredump froze the desktop for minutes, 11-09)
PKG=${BC5_PKG:-$HOME/bc5-data/pkg/game.pkg}
M=~/bc5-data/mnt/pkg-play
EMU=~/bc5-work/kytyplus-build/src/kyty_emulator
ENVF=${BC5_RUN_ENV:-$HOME/bc5-work/bc5-run.env}
LOG=~/bc5-work/play-pkg-last.log
# Experiment 0177: BC5_LEAN=1 (the "BC5 emulator (lean)" shortcut) runs the emulator built with
# KYTY_BC5_LEAN in ~/bc5-work/kytyplus-build-lean: no tracing, journal, counters, recorder or
# samplers, inside or outside; its own log file. The title scripts take the same switch.
if [ "${BC5_LEAN:-0}" = 1 ]; then
  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=~/bc5-work/play-pkg-lean-last.log
fi
# 2026-10-25 (exp 0324, the maintainer): with BC5_LEAN=1 this script writes no log at all; BC5_LOGS=1 keeps
# its logs. The normal shortcut logs as before.
MLOG=~/bc5-work/play-pkg-mount.log
if [ "${BC5_LEAN:-0}" = 1 ] && [ "${BC5_LOGS:-0}" != 1 ]; then LOG=/dev/null MLOG=/dev/null; fi
[ -n "${BC5_EMU:-}" ] && EMU=$BC5_EMU  # exp 0177: another binary (A/B against an older build)
BM=~/bc5-work/bc5-tools-ubuntu/release/bc5-mount

say() { echo "$*"; command -v notify-send >/dev/null 2>&1 && notify-send "BC5" "$*" 2>/dev/null; }

if pgrep -x kyty_emulator >/dev/null; then say "The emulator is already running."; exit 1; fi
[ -x "$EMU" ] || { say "No emulator build at $EMU"; exit 1; }
[ -r "$ENVF" ] || { say "No settings file at $ENVF"; exit 1; }
[ -n "${BC5_GAME_DIR:-}" ] || [ -r "$PKG" ] || { say "No package at $PKG"; exit 1; }  # exp 0409/0413: BC5_GAME_DIR = an unpacked game, no package

PLAY_ARGS=""
while IFS= read -r line; do
  case "$line" in ''|'#'*) continue ;; esac
  key=${line%%=*}; val=${line#*=}
  if [ "$key" = PLAY_ARGS ]; then PLAY_ARGS=$val; else export "$key=$val"; fi
done < "$ENVF"
PLAY_ARGS="$PLAY_ARGS --fullscreen"  # the maintainer: this title fullscreen, at the display's resolution (Full HD here)
unset BC5_GC_DUMP_DIR
[ "${BC5_LEAN:-0}" = 1 ] && unset KYTY_BC5_INPUT_RECORD PLAY_CAPTURE  # exp 0177: no input recorder
# 2026-11-24 (the maintainer: "the switches from that shortcut are not needed"): this title's behaviour words are gone
# from the launcher. What a title needs is set by the build for every title (src/bc5/switch_defaults.hpp), never here;
# a word found missing goes there. Left here: this title's paths and the normal build's diagnostics, and the three
# words below.
# TO BE REPLACED BY A UNIVERSAL DEFAULT (ADR 0015, "Words kept until the build has them"): without them the title ended
# at 3.9 s on 2026-11-24 (h442nas1: a CB/DB write into the never-imported heap "AMM", exit 86). The direct path imports
# only the 2 MiB chunks the CPU has written, plus what a submission names; heaps only the GPU writes need the build to
# import them for every title (no list). Until then they stay here, and nowhere else.
# Experiment 0042 (F88, F96): the heaps the GPU reads or writes before the CPU touches them, imported whole.
export BC5_DIRECT_EAGER_NAMES="${BC5_DIRECT_EAGER_NAMES:+$BC5_DIRECT_EAGER_NAMES,}RenderGpuWcLarge,RenderGpuWcSmall,RenderGpuRwLarge,RenderGpuRwSmall,CommitIABufferAllocator,AMM,RenderAlloc,Physics,Decal Job Scheduler,VisualEffectInstanceHeap,DynamicHeap,DynamicHeap Small,ComponentHeap,ComponentHeap Small,MaterialHeap,DDLHeap,Physics query allocator"
# Experiment 0330 (F394): four CPU-only heaps lazy, 242 MiB less pinned (FileSystem is eager anyway since exp 0421).
export BC5_DIRECT_LAZY_NAMES="${BC5_DIRECT_LAZY_NAMES:+$BC5_DIRECT_LAZY_NAMES,}Wwise,SoundAlloc,FileSystem,UIStringAlloc"
# Experiments 0080-0081, 0171: deferred flips lose this title's menu glyphs; bc5-run.env defers for every title.
unset BC5_DIRECT_FLIP_DEFER
# BC5's own libSceAgc, libSceAgcDriver and libScePsml are the default: no module pack (bc5-run.env's is the first title's).
unset SHADPS4_SYSMODULES_PACK_DIR
export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play
export BC5_MOUNT_DISK_CACHE=$HOME/bc5-data/cache/bc5-mount  # exp 0113: decoded package blocks kept between starts (at most 8 GiB)
# exp 0160 (F208): at a fence timeout, dump the buffer the GPU ran and journal its draws (normal build, only on a timeout).
[ "${BC5_NO_TIMEOUT_PROBE:-0}" = 1 ] || [ "${BC5_LEAN:-0}" = 1 ] || export BC5_DIRECT_TIMEOUT_PROBE=1
# 2026-10-16, for measuring play sessions: the direct path journal (frame profile, no buffer dumps)
# in ~/bc5-data/captures/play-<date>/gc/direct.log.
if [ "${BC5_LEAN:-0}" != 1 ]; then  # exp 0177: no journal with BC5_LEAN=1
  export BC5_GC_DUMP_DIR=$HOME/bc5-data/captures/play-$(date +%Y%m%d-%H%M)/gc BC5_DIRECT_TIMING=1 BC5_DIRECT_FRAME_PROFILE=1
  mkdir -p "$BC5_GC_DUMP_DIR"
fi
# Experiment 0174: measurements that stay on with the logging switch off (one line a second each):
# the frame-time counter, the audio push rate, and a per-thread CPU sampler (cpu-last.txt).
[ "${BC5_LEAN:-0}" = 1 ] || export KYTY_BC5_FPS_COUNTER=1 KYTY_BC5_AUDIO_TRACE=1 KYTY_BC5_MEASURE=1  # exp 0177: none with BC5_LEAN=1
# Experiment 0177: the per-thread CPU sampler is opt-in (BC5_CPU_SAMPLER=1). It was suspected of the
# halved frame rate (start screen 41-50 -> 25 flips/s, runs 828 -> 830); an A/B with and without it
# showed no difference: the GPU clock had fallen to ~1050 MHz after the ring resets (F235).
[ "${BC5_CPU_SAMPLER:-0}" = 1 ] && [ "${BC5_LEAN:-0}" != 1 ] && ( ~/bc5-work/cpu-sampler.sh 0 7200 ~/bc5-work/cpu-last.txt < /dev/null > /dev/null 2>&1 & )
~/bc5-work/pad-volume.sh >> "$LOG" 2>&1 || true; ~/bc5-work/pad-volume.sh --watch $$ >> "$LOG" 2>&1 &  # F94: the pad ALSA volume resets on every replug
# Experiment 0301 (the maintainer asked, 2026-10-25): MangoHud is part of the emulator: it loads hidden and
# Emulation > MangoHud shows its hardware figures and the title's frame rate (saved per title in the input
# configuration). KYTY_BC5_MANGOHUD=0 keeps MangoHud out, =1 shows it from the start; KYTY_BC5_OSD_FPS=1 the
# frame rate alone. The former BC5_MANGOHUD=1 switch and its shortcut are gone.
export XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0} DISPLAY=${DISPLAY:-:0}

mkdir -p "$M" "$KYTY_BC5_SAVEDATA_DIR"
MP=""
# exp 0439 (2026-11-21): a dead FUSE endpoint (its bc5-mount killed: exp 0438's first title starts at 12:58 and 13:00
# failed on one in the ubuntu container, "Transport endpoint is not connected") still passes `mountpoint -q`, while every
# read through it fails. A mount counts only when the game's sce_sys/param.json reads non-empty; a dead one is unmounted
# (lazily if it must be) before a new mount, and a failure says so by name. tools/scripts/launchers/test-mount-live.sh.
# --- mount (exp 0439) ---
mount_live() { mountpoint -q "$1" && [ -s "$1/sce_sys/param.json" ]; }
mount_clear_dead() { # $1 mountpoint, $2 log
  mountpoint -q "$1" || return 0
  mount_live "$1" && return 0
  echo "$(date '+%F %T') dead mount at $1 (param.json not readable): unmounted" >> "$2"
  fusermount3 -u "$1" 2>> "$2" || fusermount3 -u -z "$1" 2>> "$2"
  ! mountpoint -q "$1"
}
if [ -n "${BC5_GAME_DIR:-}" ]; then M=$BC5_GAME_DIR  # exp 0409/0413: an unpacked game dir, no bc5-mount
else
  mount_clear_dead "$M" "$MLOG" || { say "A dead mount at $M could not be removed (fusermount3 -u -z failed)."; exit 1; }
  if ! mount_live "$M"; then
    # 2026-10-25 (the maintainer's yes; exp 0288, F353): glibc's malloc arenas capped at 2 for the mount, ~100 MiB less, loads not slower.
    MALLOC_ARENA_MAX=2 "$BM" mount "$PKG" "$M" > "$MLOG" 2>&1 &
    MP=$!
    for _ in $(seq 1 300); do mount_live "$M" && break; sleep 0.2; done
  fi
fi
[ -n "${BC5_GAME_DIR:-}" ] || mount_live "$M" || { say "Mounting the package failed: $M/sce_sys/param.json is not readable (see $MLOG; with BC5_LEAN=1 run with BC5_LOGS=1 to keep it)."; exit 1; }
# --- end mount ---
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
  "$EMU" --game "$M" --printf-direction Silent --shader-log-direction Silent --command-buffer-dump false $PLAY_ARGS >> "$LOG" 2>&1
  RC=$?
  [ "$RC" = 75 ] || break
  echo "== $(date '+%F %T') restart requested from the F2 menu" >> "$LOG"
done
echo "== $(date '+%F %T') exit $RC" >> "$LOG"
exit $RC
