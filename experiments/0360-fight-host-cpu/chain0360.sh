#!/usr/bin/env bash
# BC5 experiment 0360, laptop side: one go0360.sh run after another (each waits for a free box under the lock rules and
# streams the kernel log for its own run only). Stops after a run whose kernel stream has an amdgpu line.
# usage: chain0360.sh <run>...   where a run is tag:secs:build:route:fix
#   build: shared | meter2 | cand (~/bc5-work/exp0360/<build>/kyty_emulator); route: fight (the 14:50 slot-4 route) | s6n;
#   fix: on | off | default (KYTY_BC5_JOB_ARENA_FIX)
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
for run in "$@"; do
  IFS=: read -r TAG SECS BUILD ROUTE FIX <<< "$run"
  case "$BUILD" in shared) BIN='$W/kytyplus-build/src/kyty_emulator' ;; *) BIN='$W/exp0360/'"$BUILD"'/kyty_emulator' ;; esac
  ENVS=("REPRO_BIN=$BIN" "REPRO_WHAT=$BUILD-$ROUTE-fix-$FIX")
  if [ "$ROUTE" = fight ]; then
    ENVS+=('REPRO_SAVES=$W/exp0358/saves-live-47aefd45' 'REPRO_CMD=$W/exp0360/fight1450-menu.cmd' 'REPRO_PHASE2=$W/exp0360/fight1450-play.cmd')
  fi
  case "$FIX" in on) ENVS+=("BC5_0360_SWITCHES=KYTY_BC5_JOB_ARENA_FIX=1") ;; off) ENVS+=("BC5_0360_SWITCHES=KYTY_BC5_JOB_ARENA_FIX=0") ;; esac
  echo "===== $(date +%T) $TAG: $SECS s, $BUILD, $ROUTE, fix $FIX"
  bash "$HERE/go0360.sh" "$TAG" "$SECS" "$HERE/raw/$TAG-kernel-stream.txt" - -- "${ENVS[@]}" 2>&1 | grep -v "^swappiness\|^zram\|^kernel 7\|^learned file\|^launcher /"
  if grep -qi "amdgpu" "$HERE/raw/$TAG-kernel-stream.txt"; then echo "===== $TAG: an amdgpu line in the kernel stream: the chain stops"; exit 1; fi
done
echo "===== $(date +%T) chain done"
