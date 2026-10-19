#!/usr/bin/env bash
# BC5 track B: play the maintainer's own second title from its PS5 package on the direct GPU path,
# with the latest build of the emulator and the settings in ~/bc5-work/bc5-run.env plus what this
# title needs (experiment 0036): the system module pack without the title's own libSceAmpr, its
# GPU heaps imported in full, its own learned-fault file. Run inside the ubuntu distrobox (the
# desktop shortcut does: distrobox enter ubuntu -- ~/bc5-work/play-pkg.sh). No time limit, no
# buffer captures (the journal: see experiment 0129 below); the emulator's output goes to ~/bc5-work/play-pkg-last.log.
set -u
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
[ -n "${BC5_EMU:-}" ] && EMU=$BC5_EMU  # exp 0177: another binary (A/B against an older build)
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
PLAY_ARGS="$PLAY_ARGS --fullscreen"  # the maintainer: this title fullscreen, at the display's resolution (Full HD here)
unset BC5_GC_DUMP_DIR
[ "${BC5_LEAN:-0}" = 1 ] && unset KYTY_BC5_INPUT_RECORD PLAY_CAPTURE  # exp 0177: no input recorder
# This title's settings (experiment 0036); the file below may override them.
export SHADPS4_SYSMODULES_PACK_DIR=$HOME/bc5-data/sysmodules-pack-hle-ampr
# Experiment 0042: also the heaps the GPU reads or writes before the CPU touches them
export BC5_DIRECT_EAGER_NAMES="RenderGpuWcLarge,RenderGpuWcSmall,RenderGpuRwLarge,RenderGpuRwSmall,CommitIABufferAllocator,AMM,RenderAlloc,Physics,Decal Job Scheduler,VisualEffectInstanceHeap,DynamicHeap,DynamicHeap Small,ComponentHeap,ComponentHeap Small,MaterialHeap,DDLHeap,Physics query allocator"
export BC5_DIRECT_LEARNED=$HOME/bc5-work/direct-learned-pkg.txt
export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play
# Experiment 0039: the compute IBs indirect dispatches run (rewritten for the GFX ring).
# Experiment 0053: their arguments checked by the CP when it runs them, a CP DMA wait before a
# dispatch after an unsynced copy; with both the tree refit runs too (before: skipped,
# BC5_DIRECT_MEC_SKIP_PGM=909939900, which bc5-pkg.env can set again with GPU_CHECK unset).
export BC5_DIRECT_MEC_INDIRECT=1 BC5_DIRECT_GPU_CHECK=1 BC5_DIRECT_DMA_SYNC=1
# Experiment 0055: cross-queue waits a job already on the ring will satisfy are left to the GPU.
export BC5_DIRECT_RING_ORDER_WAITS=1
# 2026-10-14 (experiments 0080-0081): the title's menus need the multi-draw packets and the code
# aliases, and undeferred flips (deferred ones lose glyphs).
[ "${BC5_KEEP_FLIP_DEFER:-0}" = 1 ] || unset BC5_DIRECT_FLIP_DEFER  # exp 0171: BC5_KEEP_FLIP_DEFER=1 keeps the deferral of bc5-run.env
# Experiment 0103 (maintainer said yes, 2026-10-15): the post-flip sync walk skipped for pages
# known to stay unmapped. (0105 PACE_FIX removed 2026-10-15: the 1.7 came from ASTRO s timestamp scale, now per title.)
export BC5_DIRECT_REMEMBER_UNMAPPED=1
# Experiments 0112 and 0113 (maintainer said yes, 2026-10-15): APR reads of one buffer in parallel, and
# decoded package blocks kept on disk between starts (bc5-mount, at most 8 GiB).
export KYTY_BC5_APR_PARALLEL=8 BC5_MOUNT_DISK_CACHE=$HOME/bc5-data/cache/bc5-mount
# Experiment 0122 (maintainer said yes, 2026-10-15): the sources of graphics buffers DMA copies
# taken at submission (backend snapshot ring): no other uploads pictures in the menu text.
export BC5_DIRECT_DMA_SNAPSHOT=4096
# Experiment 0123 (maintainer said yes, 2026-10-15): New Game hung in the ray-traced-reflection
# traversal (F113-F116); with it skipped New Game reaches the start screen (no RT reflections).
# Pressing cross there (the game itself) works (maintainer, 2026-10-15, runs 527-528).
# Experiment 0159 (F207): program 0x909974400 (the engine's BVH neighbour-link compaction, a GFX-ring
# DISPATCH_INDIRECT of the night scene) writes what the geometry engine then fetches from address 0;
# skipped like the traversal until the BVH inputs are right (F116, F173). The opening then plays to
# gameplay (run 735). A run script may set BC5_DIRECT_SKIP_PGM itself.
export BC5_DIRECT_SKIP_PGM=${BC5_DIRECT_SKIP_PGM:-11d049aa00,11d04a6000,909974400}
# exp 0160 (F208): at a fence timeout, dump the buffer the GPU ran and journal its draws/dispatches with the bases in force (cheap, only on a timeout).
[ "${BC5_NO_TIMEOUT_PROBE:-0}" = 1 ] || [ "${BC5_LEAN:-0}" = 1 ] || export BC5_DIRECT_TIMEOUT_PROBE=1  # exp 0175: BC5_NO_TIMEOUT_PROBE=1 for A/B
# exp 0160 (F208): one journal line per fast-launch point draw (arguments, GS user data) to compare with the one that hangs.
export BC5_DIRECT_INDIRECT_DRAWS=multi BC5_DIRECT_ALIASES=1
# Experiment 0129 (maintainer said yes, 2026-10-16): the compute buffers on kernel compute ring 0,
# the GFX ring waiting on the GPU for the labels they write (start screen 32-34 -> 41-42 fps).
export BC5_DIRECT_COMPUTE_RING=0 BC5_DIRECT_CROSS_RING_WAITS=all
# Experiment 0134 (2026-10-16): no ring dependencies; the black blocks of experiment 0132 were the
# compute heads dropping their waits on graphics (fixed in the host), not the order itself.
# Experiment 0133 (2026-10-16): the two-ring limit at 4 ms (ASTRO BOT geyser 32-34 fps against 30-31 at 8 ms).
export BC5_DIRECT_TWO_RING_WAIT_MS=4
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
PKG_ENV=~/bc5-work/bc5-pkg.env
if [ -r "$PKG_ENV" ]; then
  while IFS= read -r line; do
    case "$line" in ''|'#'*) continue ;; esac
    export "${line%%=*}=${line#*=}"
  done < "$PKG_ENV"
fi
~/bc5-work/pad-volume.sh >> "$LOG" 2>&1 || true; ~/bc5-work/pad-volume.sh --watch $$ >> "$LOG" 2>&1 &  # F94: the pad ALSA volume resets on every replug
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
