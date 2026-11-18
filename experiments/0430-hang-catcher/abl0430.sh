#!/usr/bin/env bash
# BC5 exp 0430 (2026-11-18 evening, the bake's lean checks; the top session's order): lean runs through run0430l.sh, one at
# a time, each with its own BOX-LOCK line: the route by time (N_TIMED; lean writes no journal), MangoHud's frame log as the
# counter for every arm (N_MH), the Plasma shell stopped for the run through lean-session.sh as the lean shortcuts do
# (N_LEANSESS), slot 4, the 14:50 record's gameplay and exp 0379's walk, RT on, way 2 (the title rows), ulimit -c 0 (the
# launcher), no JobArenaFix word. Arms: S = the shared lean (as it is), B = the baked lean (exp0430/lean, pinned), H = the
# baked lean on the Bazzite host (P_HOST=1, no distrobox). Stops at the first run that is not NO_CRASH or at a STOP file.
# usage (on the box, detached, in ~/bc5-work/exp0430): ORDER="S B H" PLAY=900 TAGP=hl430 bash abl0430.sh
set -u
W=$HOME/bc5-work; E=$W/exp0430; HERE=$(cd "$(dirname "$0")" && pwd)
WORDS=$W/exp0413/n/words0413nz.txt; PLAY=${PLAY:-900}
WAY2="BC5_DIRECT_ACB_RINGS=4 BC5_DIRECT_ACB_QUEUE_STATE=1 BC5_DIRECT_ACB_MEC_INDIRECT=1 BC5_DIRECT_ACB_STATE_NO_WALK=1 BC5_DIRECT_ACB_SPLIT_LATE=3"
SB=$W/kytyplus-build-lean/src/kyty_emulator; BB=$E/lean/kyty_emulator; BW=85befb72
[ "$(md5sum < "$BB" | cut -c1-8)" = "$BW" ] || { echo "abl0430: $BB is not $BW"; exit 1; }
k=0
for arm in ${ORDER:-S B H}; do
  k=$((k + 1)); t=${TAGP:?TAGP}$arm$k
  [ -e "$E/STOP" ] && { echo "abl0430 $(date +%T): STOP file"; break; }
  pgrep '^kyty_emulator' > /dev/null && { echo "abl0430 $(date +%T): an emulator runs before $t (not ours): stop"; break; }
  host=0; bin=$SB; [ "$arm" = S ] || bin=$BB; [ "$arm" = H ] && host=1
  echo "abl0430 $(date +%T): run $t, arm $arm, $(md5sum < "$bin" | cut -c1-8), host $host"
  # shellcheck disable=SC2086
  line=$(P_HOST=$host N_TIMED=1 N_T0=90 N_T1=10 N_T2=8 N_T3=25 N_MH=1 N_MHD=$((133 + PLAY - 15)) N_LEANSESS=1 N_ARENA=off N_WALK_AFTER=1 N_SLOT=4 N_FUSE=0 N_NOWD=1 \
    P_BIN=$bin P_WANT=$(md5sum < "$bin" | cut -d' ' -f1) P_WORDS=$WORDS bash "$HERE/run0430l.sh" "$t" h "$PLAY" $WAY2 | grep "^$t ")
  echo "$line" | cut -c1-600
  printf '%s\n' "$line" | grep -q "; CLASS NO_CRASH;" || { echo "abl0430 $(date +%T): not NO_CRASH, stop"; break; }
done
echo "abl0430 $(date +%T): done"
