#!/usr/bin/env bash
# BC5 exp 0430, 2026-11-17 (the top session after the maintainer's slow play on build 8, 24.3 flips/s against 39.8 on build
# 3b): does the fix itself cost in HIS scene? His newest save (slot 4, written 09:44-09:46), copied once read-only into
# $SNAP (never his live saves), the save-slot route (cross, down x3, cross, cross) and NO input after the load (N_NOWALK=1),
# PLAY s of gameplay per run. Arms, one run each in the order of $ORDER (default "S N B"):
#   S  the shared normal build as it is (the fix F3 + F4 + F2 fallback on by its defaults, no catcher)
#   N  the same binary with the fix off by words (BC5_DIRECT_XQ_ACQUIRE=0 BC5_DIRECT_XQ_FENCE=0 BC5_DIRECT_XQ_PENDING=0)
#   B  build 8 (75f87980: the fix + every catcher, G dump at 300 s), the words of the D runs
#   P  the F5 build (PBIN: the shared normal build plus F5, the precise form, mkf5.py), its defaults
# The top session (10:00): a fault or hang in one arm is data and does not stop the others.
# RT on, way 2 words as the chain's, no fuse, no watchdog, ulimit -c 0. Tags h430<arm><k> from K0+1. Stops only at
# ~/bc5-work/exp0430/STOP or at an emulator that is not ours. One run at a time; each run takes and frees its own BOX-LOCK line.
# usage (on the box, detached, in ~/bc5-work/exp0430): SNAP=<dir holding TITLE2> K0=0 bash scene0430.sh
set -u
ulimit -c 0
W=$HOME/bc5-work; E=$W/exp0430; N=$E/n; HERE=$(cd "$(dirname "$0")" && pwd)
SNAP=${SNAP:?the read-only snapshot dir}; [ -d "$SNAP/TITLE2" ] && [ ! -L "$SNAP" ] || { echo "scene0430: no $SNAP/TITLE2"; exit 1; }
PLAY=${PLAY:-600}; k=${K0:?the last run number}
WORDS=$W/exp0413/n/words0413nz.txt
WAY2="BC5_DIRECT_ACB_RINGS=4 BC5_DIRECT_ACB_QUEUE_STATE=1 BC5_DIRECT_ACB_MEC_INDIRECT=1 BC5_DIRECT_ACB_STATE_NO_WALK=1 BC5_DIRECT_ACB_SPLIT_LATE=3"
SB=$W/kytyplus-build/src/kyty_emulator; B8=$E/kyty_emulator.75f87980
CAT="BC5_0430_DJ=1 BC5_0430_ARGS=1 BC5_0430_WAVES_MS=900 BC5_0430_SNAP=1 BC5_0430_F3=1 BC5_0430_F2=1 BC5_0430_F4=1 BC5_0430_G=1 BC5_0430_G_AT=300 BC5_0430_TABLES=1 BC5_0430_TABLE_PGMS=909973900,909973b00,909973d00,909973f00,909974400,909977100,90997a500"
echo "scene0430 $(date +%T): snapshot $SNAP ($(cd "$SNAP" && find TITLE2 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16)), play $PLAY s, order ${ORDER:-S N B}"
k=$((k + 1))
for arm in ${ORDER:-S N B}; do
  [ -e "$E/STOP" ] && { echo "scene0430 $(date +%T): STOP file"; break; }
  pgrep '^kyty_emulator' > /dev/null && { echo "scene0430 $(date +%T): an emulator runs (not ours): stop"; break; }
  case "$arm" in
    S) bin=$SB; aw="$WAY2 BC5_DIRECT_TIMEOUT_PROBE=1" ;;
    N) bin=$SB; aw="$WAY2 BC5_DIRECT_TIMEOUT_PROBE=1 BC5_DIRECT_XQ_ACQUIRE=0 BC5_DIRECT_XQ_FENCE=0 BC5_DIRECT_XQ_PENDING=0" ;;
    B) bin=$B8; aw="$WAY2 BC5_DIRECT_TIMEOUT_PROBE=1 $CAT" ;;
    P) bin=${PBIN:?the F5 binary}; aw="$WAY2 BC5_DIRECT_TIMEOUT_PROBE=1" ;;
    *) echo "scene0430: arm $arm?"; break ;;
  esac
  t=h430$arm$k; while [ -e "$N/raw/$t-start.txt" ]; do t=${t}b; done
  want=$(md5sum < "$bin" | cut -d' ' -f1)
  echo "scene0430 $(date +%T): arm $arm, $t, ${want:0:8}"
  # shellcheck disable=SC2086
  line=$(N_SAVES=$SNAP N_SLOT=4 N_NOWALK=1 N_ARENA=off N_FUSE=0 N_NOWD=1 P_BIN=$bin P_WANT=$want P_WORDS=$WORDS bash "$HERE/run0430f.sh" "$t" h "$PLAY" $aw | grep "^$t ")
  echo "${line:-$t: no result line}" | cut -c1-600
  case "$line" in *"; CLASS NO_CRASH;"*) ;; *) echo "scene0430 $(date +%T): $t not NO_CRASH (data; the next arm follows)" ;; esac
  sleep 20
done
echo "scene0430 $(date +%T): done"
