#!/usr/bin/env bash
# BC5 exp 0428: way 2 on the second title (F464's fight route, automated, no person at the pad), RT on, JobArenaFix as the
# shared input.cfg has it, the private normal binary of exp 0428 (one binary for both arms; only the switches differ).
# One set per start, one BOX-LOCK line (exp 0413's chain lock):
#   CHAIN_SET=smoke:  w428Q1 (way 2 once, first: a compute-ring hang without a successful reset ends the track for the day)
#   CHAIN_SET=series: w428C1 w428Q2 w428Q3 w428C2 w428C3 w428Q4 w428Q5 w428C4 (interleaved C Q Q C C Q Q C)
#   CHAIN_SET=smoke2: w428Q6 (iteration 2, the build with the busy-queue map, BC5_DIRECT_ACB_MEC_INDIRECT, BC5_DIRECT_ACB_STATE_NO_WALK)
#   arms: C every exp 0428 switch off; Q BC5_DIRECT_ACB_RINGS=4 BC5_DIRECT_ACB_QUEUE_STATE=1 BC5_DIRECT_ACB_MEC_INDIRECT=1 BC5_DIRECT_ACB_STATE_NO_WALK=1
# Each run: run0428f.sh, slot 4, the 14:50 record's gameplay at G, G+120 s. The rule is check0428.py's, fixed before the
# runs. Stops (R55): a kernel GPU line, a real pad key (R51), any class but NO_CRASH/NOT_ROUTED, a second NOT_ROUTED, a
# STOP file ($HERE/STOP, read before each run).
# usage (on the box, detached, in ~/bc5-work/exp0428): CHAIN_SET=smoke|series bash chain0428.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0428/n; R=$N/raw; HERE=$(cd "$(dirname "$0")" && pwd)
BIN=$W/exp0428/kyty_emulator; WORDS=$W/exp0413/n/words0413nz.txt; LOCKINC=$W/exp0413/n/chainlock0417.inc
SET=${CHAIN_SET:-}; OUT=$N/chain-rows-$SET.txt
say() { echo "chain0428 $(date +%T): $*"; }
[ -x "$BIN" ] && [ -s "$W/exp0428/binary.md5" ] || { say "NOT STARTED, no private binary or binary.md5"; exit 1; }
WANT=$(cat "$W/exp0428/binary.md5"); MB=$(md5sum < "$BIN" | cut -d' ' -f1)
[ "$MB" = "$WANT" ] || { say "NOT STARTED, the binary is ${MB:0:8}, not ${WANT:0:8}"; exit 1; }
[ -s "$WORDS" ] && [ -f "$LOCKINC" ] || { say "NOT STARTED, no $WORDS or $LOCKINC"; exit 1; }
[ -d "$W/exp0425/saves-named/PPSA03671" ] || { say "NOT STARTED, no named snapshot in exp0425"; exit 1; }
[ -s "$W/exp0425/inputs/fight1450-play.cmd" ] || { say "NOT STARTED, no exp0425/inputs/fight1450-play.cmd"; exit 1; }
case "$SET" in
  smoke) TAGS="w428Q1" ;;
  smoke2) TAGS="w428Q6" ;;  # iteration 2: busy-queue map, MEC indirect allowed, no inherit walk
  long) TAGS="w428L4 w428L5 w428L6" ;;
  longab) TAGS="w428C5 w428L7 w428L8 w428C6 w428C7 w428L9" ;;  # iteration 5: one ring (C) against way 2 (L), fight + walk to G+1500, interleaved  # (w428L1 ran iteration 3: the arena crash at 228 s, JobArenaFix off; kept-without-split 0)  # iteration 3 (after the 15:09 hang): + BC5_DIRECT_ACB_SPLIT_LATE, fight then walk, G+1500
  series) TAGS="w428C1 w428Q2 w428Q3 w428C2 w428C3 w428Q4 w428Q5 w428C4" ;;
  *) say "NOT STARTED, CHAIN_SET is smoke, smoke2, series, long or longab"; exit 1 ;;
esac
mkdir -p "$R" || exit 1
for t in $TAGS; do { [ -e "$R/$t-start.txt" ] || [ -e "$R/$t-end.txt" ] || [ -e "$R/${t}R-start.txt" ]; } && { say "NOT STARTED, tag $t used"; exit 1; }; done
[ -e "$W/BOX-LOCK.nas" ] && { say "NOT STARTED, BOX-LOCK.nas exists"; exit 1; }
[ -e "$HERE/STOP" ] && { say "NOT STARTED, $HERE/STOP exists"; exit 1; }
armwords() {
  case "$1" in
    w428C*) echo "BC5_DIRECT_ACB_RINGS=0 BC5_DIRECT_ACB_QUEUE_STATE=0" ;;
    w428Q*) echo "BC5_DIRECT_ACB_RINGS=4 BC5_DIRECT_ACB_QUEUE_STATE=1 BC5_DIRECT_ACB_MEC_INDIRECT=1 BC5_DIRECT_ACB_STATE_NO_WALK=1" ;;
    w428L*) echo "BC5_DIRECT_ACB_RINGS=4 BC5_DIRECT_ACB_QUEUE_STATE=1 BC5_DIRECT_ACB_MEC_INDIRECT=1 BC5_DIRECT_ACB_STATE_NO_WALK=1 BC5_DIRECT_ACB_SPLIT_LATE=2" ;;
    *) return 1 ;;
  esac
}
cd "$N" 2> /dev/null || { mkdir -p "$N" && cd "$N"; } || exit 1
. "$LOCKINC"
chain_claim "exp 0428 set $SET: way 2 (compute rings + per-queue state) on the second title's fight route, private normal ${WANT:0:8}" 60 || { say "NOT STARTED"; exit 1; }
PADS=(); PADN=0
padon() { : > "$R/$1-pad.txt"; local d; for d in /dev/input/by-id/*-event-joystick; do [ -e "$d" ] || continue; stdbuf -oL evtest "$d" 2> /dev/null | grep --line-buffered 'EV_KEY.*value 1' >> "$R/$1-pad.txt" & PADS+=($!); done; }
padoff() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); PADN=$(wc -l < "$R/$1-pad.txt"); }
fin() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; chain_release; }
trap fin EXIT
say "binary ${WANT:0:8}; kernel $(uname -r); boot $(cut -c1-8 /proc/sys/kernel/random/boot_id)"
: > "$OUT"
SPARE=1
one() {  # tag. Sets CLASS; returns 1 when the chain must stop
  local t=$1 aw line fps gaps
  aw=$(armwords "$t") || { say "STOP: no arm for $t"; return 1; }
  [ -e "$HERE/STOP" ] && { say "STOP: $HERE/STOP before $t"; return 1; }
  padon "$t"
  # shellcheck disable=SC2086
  local play=120 walk=0 arena=""; case "$SET" in long | longab) play=1500; walk=1; arena=on ;; esac  # long: JobArenaFix on in the private copy (the GPU hang is the target)
  line=$(N_ARENA=$arena N_WALK_AFTER=$walk N_SLOT=4 P_BIN=$BIN P_WANT=$WANT P_WORDS=$WORDS bash "$HERE/run0428f.sh" "$t" "${t:4:1}" "$play" $aw | grep "^$t ")
  padoff "$t"
  CLASS=$(printf '%s\n' "$line" | sed -n 's/.*; CLASS \([A-Z_]*\);.*/\1/p')
  fps=$(printf '%s\n' "$line" | sed -n 's/.*; \([0-9.]*\) flips\/s over .*/\1/p'); gaps=$(printf '%s\n' "$line" | sed -n 's/.*s, \([0-9]*\) s with a gap over 100 ms.*/\1/p')
  echo "$t ${CLASS:-NONE} pad $PADN fps ${fps:--} gaps ${gaps:--} $(printf '%s\n' "$line" | sed -n 's/.*; exposure \(.*\)$/\1/p')" >> "$OUT"
  say "$t: ${line:-no result line}; real pad keys $PADN"
  [ "$PADN" = 0 ] || { say "STOP: a real pad key in $t (the maintainer is at the box)"; return 1; }
  case "${CLASS:-NONE}" in
    NO_CRASH | NOT_ROUTED) return 0 ;;
    KERNEL) [ "$SET" = longab ] && return 0; say "STOP: $t is KERNEL"; return 1 ;;  # longab counts hangs per arm; a failed reset ends the chain by itself
    *) say "STOP: $t is ${CLASS:-NONE}"; return 1 ;;
  esac
}
for t in $TAGS; do
  one "$t" || break
  if [ "$CLASS" = NOT_ROUTED ]; then
    if [ "$SPARE" = 1 ]; then SPARE=0; sed -i "/^$t /d" "$OUT"; one "${t}R" || break; [ "$CLASS" != NOT_ROUTED ] || { say "STOP: $t not routed twice"; break; }
    else say "STOP: $t not routed, no replacement left"; break; fi
  fi
  sleep 10
done
python3 "$HERE/check0428.py" rule "$OUT" "$SET"
say "ended"
