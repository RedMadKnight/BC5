#!/usr/bin/env bash
# BC5 exp 0433, step 3b (top, 2026-11-19 06:4x), all on the box in one unit so the box never waits on the laptop:
#   1. the private build again with 0002's hit counters (claim, build, release; the previous binaries are kept beside
#      the new ones as kyty_emulator.<md5 8>);
#   2. one short fight run each, pack (P, every word on) then control (C, every word =0), G+300, run0430f.sh as
#      chain0433.sh calls it, each with probe0433.sh beside it.
# Writes $E/step3b.done with the exit code at the end (also on a stop). Stops at a foreign emulator, a STOP file, or a
# run that is not NO_CRASH.
# usage (on the box, under the user manager, in ~/bc5-work/exp0433/kit): bash step3b0433.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; E=$W/exp0433; R=$W/exp0430/n/raw; HERE=$(cd "$(dirname "$0")" && pwd)
say() { echo "step3b $(date +%T): $*"; }
fin() { echo "$1" > "$E/step3b.done"; say "end, code $1"; exit "$1"; }
pgrep '^kyty_emulator' > /dev/null && { say "an emulator runs: not started"; fin 1; }
mkdir -p "$E/probe" || fin 1
bash "$HERE/box0433.sh" claim "0433 build with hit counters" 30 || fin 1
tok=$(sed -n 's/.*token \([0-9]*\).*/\1/p' "$E/lock.line")
echo "exp 0433 | claimed: private build with hit counters (CPU only, no emulator), token $tok | $(date '+%F %T')" >> "$W/BOX-QUEUE"
bash "$HERE/box0433.sh" build; rc=$?
bash "$HERE/box0433.sh" release && echo "exp 0433 | released: private build with hit counters, token $tok | $(date '+%F %T')" >> "$W/BOX-QUEUE"
[ "$rc" = 0 ] || { say "build failed"; fin 1; }
strings "$E/normal/kyty_emulator" | grep -qF "ports pack 1 hits:" || { say "no hit counter in the normal binary"; fin 1; }
BIN=$E/normal/kyty_emulator; WANT=$(cat "$E/normal/binary.md5"); WORDS=$W/exp0413/n/words0413nz.txt
WAY2="BC5_DIRECT_ACB_RINGS=4 BC5_DIRECT_ACB_QUEUE_STATE=1 BC5_DIRECT_ACB_MEC_INDIRECT=1 BC5_DIRECT_ACB_STATE_NO_WALK=1 BC5_DIRECT_ACB_SPLIT_LATE=3"
OFF=$(cat "$E/off-words.txt")
for arm in ${ORDER:-P C}; do
  case "$arm" in P) t=${TAGP:-s433}p1; AW="$WAY2 BC5_DIRECT_TIMEOUT_PROBE=1" ;;
                 C) t=${TAGP:-s433}q1; AW="$WAY2 BC5_DIRECT_TIMEOUT_PROBE=1 $OFF" ;; esac
  while [ -e "$R/$t-start.txt" ]; do t=${t}b; done
  [ -e "$HERE/STOP" ] && { say "STOP file before $t"; fin 1; }
  pgrep '^kyty_emulator' > /dev/null && { say "an emulator runs before $t (not ours): stop"; fin 1; }
  say "run $t, arm $arm, binary ${WANT:0:8}"
  bash "$HERE/probe0433.sh" "$E/probe/$t" > /dev/null 2>&1 &
  PR=$!
  # shellcheck disable=SC2086
  line=$(N_ARENA=off N_WALK_AFTER=1 N_SLOT=4 N_FUSE=0 N_NOWD=1 P_BIN=$BIN P_WANT=$WANT P_WORDS=$WORDS \
         bash "$W/exp0430/run0430f.sh" "$t" h 300 $AW | grep "^$t ")
  wait "$PR"
  CLASS=$(printf '%s\n' "$line" | sed -n 's/.*; CLASS \([A-Z_]*\);.*/\1/p')
  echo "$t $arm ${CLASS:-NONE} $(printf '%s\n' "$line" | cut -c1-400)" >> "$E/step3b-rows.txt"
  say "$t: ${CLASS:-NONE}"
  [ "${CLASS:-NONE}" = NO_CRASH ] || { say "not NO_CRASH: stop"; fin 1; }
done
fin 0
