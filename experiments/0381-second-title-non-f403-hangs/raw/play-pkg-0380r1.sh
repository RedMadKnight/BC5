#!/usr/bin/env bash
# BC5 track B: play the maintainer's own second title from its PS5 package on the direct GPU path,
# with the latest build of the emulator and the settings in ~/bc5-work/bc5-run.env plus what this
# title needs (experiment 0036): the system module pack without the title's own libSceAmpr, its
# GPU heaps imported in full, its own learned-fault file. Run inside the ubuntu distrobox (the
# desktop shortcut does: distrobox enter ubuntu -- ~/bc5-work/play-pkg.sh). No time limit, no
# buffer captures (the journal: see experiment 0129 below); the emulator's output goes to ~/bc5-work/play-pkg-last.log.
set -u
unset BC5_LEAN BC5_LOGS  # exp 0380r1: the normal build's journal and timeout probe
Z=~/bc5-work/exp0380r1; ZSTAMP=$(date +%Y%m%d-%H%M%S)  # exp 0380r1
PKG=${BC5_PKG:-$HOME/bc5-data/pkg/game.pkg}
M=~/bc5-data/mnt/pkg-play
EMU=~/bc5-work/exp0380r1/bin/kyty_emulator  # exp 0380r1: shared objects and archive, bc5LleAgc.cpp with exp 0379's zero skip and the recorder of F608, runtimeLinker.cpp with BC5_CRASH_FRAMES (build0380r1.sh)
ENVF=${BC5_RUN_ENV:-$HOME/bc5-work/bc5-run.env}
mkdir -p ~/bc5-work/exp0380r1/play
LOG=~/bc5-work/exp0380r1/play/play-$ZSTAMP.log  # exp 0380r1: one log per start
# Experiment 0177: BC5_LEAN=1 (the "BC5 emulator (lean)" shortcut) runs the emulator built with
# KYTY_BC5_LEAN in ~/bc5-work/kytyplus-build-lean: no tracing, journal, counters, recorder or
# samplers, inside or outside; its own log file. The title scripts take the same switch.
if [ "${BC5_LEAN:-0}" = 1 ]; then
  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=~/bc5-work/play-pkg-lean-last.log
fi
# 2026-10-25 (exp 0324, the maintainer): with BC5_LEAN=1 this script writes no log at all; BC5_LOGS=1 keeps
# its logs. The normal shortcut logs as before.
MLOG=~/bc5-work/exp0380r1/play/mount-$ZSTAMP.log  # exp 0380r1: its own mount log
if [ "${BC5_LEAN:-0}" = 1 ] && [ "${BC5_LOGS:-0}" != 1 ]; then LOG=/dev/null MLOG=/dev/null; fi
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
# exp 0380r1 (the maintainer's play, F603/F604): the prefix without CONTEXT_CONTROL and CLEAR_STATE, exp 0379's zero skip
# on its fixed list, the flight recorder's part A after a fence timeout; no other exp 0379/0380 switch.
unset BC5_DIRECT_ARGS_WB BC5_DIRECT_FORCE_START_000 BC5_DIRECT_ARGS_COPY BC5_DIRECT_REBASE_DISPATCH BC5_DIRECT_GPU_CHECK_ZERO BC5_DIRECT_GPU_CHECK_YZ BC5_DIRECT_ZEROSCAN_AT BC5_DIRECT_ZEROSCAN_OUT BC5_0380_REC_SELFTEST_S BC5_NO_TIMEOUT_PROBE
export BC5_CRASH_FRAMES=1 BC5_0380_REC=1 BC5_DIRECT_PIECES_NO_CLEAR=1 BC5_DIRECT_ZERO_SKIP=$HOME/bc5-work/exp0380r1/zero-list-20261029-120000.txt
export BC5_DIRECT_LAZY_NAMES="${BC5_DIRECT_LAZY_NAMES:+$BC5_DIRECT_LAZY_NAMES,}Wwise,SoundAlloc,FileSystem,UIStringAlloc"  # exp 0330 (F394): the four CPU-only heaps lazy, 242 MiB less pinned
PLAY_ARGS="$PLAY_ARGS --fullscreen"  # the maintainer: this title fullscreen, at the display's resolution (Full HD here)
unset BC5_GC_DUMP_DIR
[ "${BC5_LEAN:-0}" = 1 ] && unset KYTY_BC5_INPUT_RECORD PLAY_CAPTURE  # exp 0177: no input recorder
# This title's settings (experiment 0036); the file below may override them.
export SHADPS4_SYSMODULES_PACK_DIR=$HOME/bc5-data/sysmodules-pack-hle-ampr-noplaygo  # 2026-10-25 (exp 0298, the maintainer's yes): no libScePlayGo.sprx, the host answers PlayGo (100 chunks)
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
# Experiment 0189 (the maintainer said yes, 2026-10-21): the title's own TF ring from /dev/gc is programmed
# (BC5_DIRECT_GC_TF_RING=1): no geometry-engine reads at address 0 (F207/F208), the night scene's
# tessellated patches draw. With it a fourth traversal variant, 0x11d04bb900, enters the F234 loop and
# is skipped too. BC5_DIRECT_GC_TF_RING=0 and the old skip list restore the previous setup.
export BC5_DIRECT_GC_TF_RING=${BC5_DIRECT_GC_TF_RING:-1}
# Experiment 0218 (the maintainer said yes, 2026-10-22: "Wygląda świetnie... w pełni grywalne"): the
# reflections are on by default. The traversal variants run with the flat-aperture fix
# (BC5_DIRECT_FLAT_APERTURE=1, F249-F251), the sparse AMM pages are backed (BC5_DIRECT_AMM_PRT=1, F257,
# F260), and only the BVH compaction 0x909974400 stays skipped (F275, F277): 37.5 flips/s in his
# 18-min play, against 18.5 with the compaction on and 39.4 with the reflections off.
# BC5_DIRECT_FLAT_APERTURE=0 BC5_DIRECT_AMM_PRT=0 and the old skip list
# (11d049aa00,11d04a6000,909974400,11d04bb900) restore the previous setup (backup play-pkg.sh.bak-0218).
# The emulator turns PRT on whenever BC5_DIRECT_AMM_PRT is set at all (patch 0001 tests presence only),
# so =0 here unsets it.
export BC5_DIRECT_FLAT_APERTURE=${BC5_DIRECT_FLAT_APERTURE:-1}
if [ "${BC5_DIRECT_AMM_PRT-1}" = 0 ]; then unset BC5_DIRECT_AMM_PRT; else export BC5_DIRECT_AMM_PRT=${BC5_DIRECT_AMM_PRT:-1}; fi
export BC5_DIRECT_SKIP_PGM=${BC5_DIRECT_SKIP_PGM:-0}  # exp 0323: the compaction 909974400 runs with RT on (exp 0306+); 0 = nothing skipped
# Top session, 2026-10-24 (exp 0278/0280, F337-F340; the maintainer approved it): the BVH build work the Emulation >
# Ray tracing switch drops when it is off. The switch itself stays on unless the menu or KYTY_BC5_RT=0 says otherwise.
# 2026-10-25 (exp 0299, F362, the maintainer's yes): RT off also drops the reflection traversal 0x11d049aa00, 0x11d04a6000 and 0x11d04bb900, which with no BVH built whitens the lab.
export KYTY_BC5_RT_BUILD_PGM=${KYTY_BC5_RT_BUILD_PGM:-909974400,909939400,909936c00,909939700,909939900,909974200,909973900,909973b00,909973d00,909973f00,11d049aa00,11d04a6000,11d04bb900}
# Experiment 0182 (the maintainer, 2026-10-20: "with chains it is much better"): the submission chains
# across ioctls (ADR 0010; F224: the gameplay route 33 -> 48 fps) by default for this title, normal and
# lean build alike. BC5_DIRECT_CHAIN=0 turns them off.
export BC5_DIRECT_CHAIN=${BC5_DIRECT_CHAIN:-2}
# Top session, 2026-10-24 (F253, F254, F256, F266; the maintainer approved it): the compute-state prefix in front of
# graphics buffers that dispatch before setting their own program. BC5_DIRECT_CS_PREFIX=0 turns it off.
export BC5_DIRECT_CS_PREFIX=${BC5_DIRECT_CS_PREFIX:-1}
# BC5 (2026-10-23, exps 0227-0229, F286/F287): APR read-ahead is on again, with the fix that leaves
# large and parallel-run loading buffers to the worker. The slow loads of 10-22/23 were the near-full
# drive (F286), not read-ahead; the fix keeps loads equal and speeds the cutscene clock-voice reads.
# KYTY_BC5_APR_READAHEAD=0 turns it off.
export KYTY_BC5_APR_READAHEAD=${KYTY_BC5_APR_READAHEAD:-4}
# Experiment 0183 (the maintainer said yes, 2026-10-20): at most 30 frames a second for this title (a flip
# every second vblank). It steps its cutscenes by 1/30 s per presented frame; at ~48 frames a second
# they ran 1.6 times too fast. KYTY_BC5_MIN_FLIP_RATE=0 lifts the cap.
# Experiment 0188: no longer needed. The speed-ups were the AudioOut2 queue level, which did not count the
# grains the title had advanced (the host now does, KYTY_BC5_AUDIO2_ADVANCED on by default): the opening and
# the night gameplay run at 1.00x without the cap. KYTY_BC5_MIN_FLIP_RATE=1 still caps at 30 fps.
export KYTY_BC5_MIN_FLIP_RATE=${KYTY_BC5_MIN_FLIP_RATE:-0}
# exp 0160 (F208): at a fence timeout, dump the buffer the GPU ran and journal its draws/dispatches with the bases in force (cheap, only on a timeout).
[ "${BC5_NO_TIMEOUT_PROBE:-0}" = 1 ] || [ "${BC5_LEAN:-0}" = 1 ] || export BC5_DIRECT_TIMEOUT_PROBE=1  # exp 0175: BC5_NO_TIMEOUT_PROBE=1 for A/B
# exp 0160 (F208): one journal line per fast-launch point draw (arguments, GS user data) to compare with the one that hangs.
export BC5_DIRECT_INDIRECT_DRAWS=multi BC5_DIRECT_ALIASES=1
# Experiment 0129 (maintainer said yes, 2026-10-16): the compute buffers on kernel compute ring 0,
# the GFX ring waiting on the GPU for the labels they write (start screen 32-34 -> 41-42 fps).
export BC5_DIRECT_COMPUTE_RING=-1 BC5_DIRECT_CROSS_RING_WAITS=all  # exp 0342 (F412, F415): one ring - every compute buffer on the GFX ring (was 0)
export BC5_DIRECT_GPU_CHECK_PRODUCT=1 BC5_DIRECT_SHADOW_LABELS=1  # exp 0342 (F414, F415): the RT-on guards - the product staircase in the CP check, host shadow labels
export BC5_DIRECT_HOST_INDIRECT=learn:1100000000 BC5_DIRECT_SOFT_WAIT_MS=8  # exp 0350 (F432): exp 0346 v3 (a GFX-form dispatch after the title zeroed base-1 resolved by the host, rewritten only to a page it read, else NOP-ed) + exp 0343 (soft-CP replay polls bounded at 8 ms); the exp 0349 cut is on by default
export BC5_DIRECT_RING_DEPS=dcb  # exp 0323 (F385): every GFX-ring job starts after the compute rings' last jobs - the BVH build's two-ring split hung 11/11 at ~2 min with RT on (exps 0320-0322); cost about the one-ring flip rate
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
# Experiment 0301 (the maintainer asked, 2026-10-25): MangoHud is part of the emulator: it loads hidden and
# Emulation > MangoHud shows its hardware figures and the title's frame rate (saved per title in the input
# configuration). KYTY_BC5_MANGOHUD=0 keeps MangoHud out, =1 shows it from the start; KYTY_BC5_OSD_FPS=1 the
# frame rate alone. The former BC5_MANGOHUD=1 switch and its shortcut are gone.
export XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0} DISPLAY=${DISPLAY:-:0}

mkdir -p "$M" "$KYTY_BC5_SAVEDATA_DIR"
MP=""
if ! mountpoint -q "$M"; then
  # 2026-10-25 (the maintainer's yes; exp 0288, F353): glibc's malloc arenas capped at 2 for the mount, ~100 MiB less, loads not slower.
  MALLOC_ARENA_MAX=2 "$BM" mount "$PKG" "$M" > "$MLOG" 2>&1 &
  MP=$!
  for _ in $(seq 1 300); do mountpoint -q "$M" && break; sleep 0.2; done
fi
mountpoint -q "$M" || { say "Mounting the package failed (see $MLOG; with BC5_LEAN=1 run with BC5_LOGS=1 to keep it)."; exit 1; }
# 2026-10-25 (the maintainer's yes): a failed unmount no longer hangs the launcher (exp 0301's T1 waited an hour):
# retry, then a lazy unmount, log the failure, and wait for bc5-mount at most 10 s.
cleanup() {
  [ -n "${ZSP:-}" ] && kill "$ZSP" 2> /dev/null  # exp 0380r1: the memory sampler
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
bash "$Z/play-sample0379t.sh" $$ "$Z/play/mem-$ZSTAMP.txt" < /dev/null > /dev/null 2>&1 & ZSP=$!  # exp 0380r1: once a minute

{
  echo "== exp 0380r1: BC5_CRASH_FRAMES=1 BC5_0380_REC=1 BC5_DIRECT_PIECES_NO_CLEAR=1 BC5_DIRECT_ZERO_SKIP=$BC5_DIRECT_ZERO_SKIP ($(md5sum < "$BC5_DIRECT_ZERO_SKIP" | cut -c1-8)); no write-back, FORCE_START, copy or rebase; binary $(md5sum < "$EMU" | cut -c1-8)"
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
