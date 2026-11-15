#!/usr/bin/env bash
# BC5 exp 0425: the fight runs (F464's route, automated, no person at the pad), all with JobArenaFix OFF, RT on, the
# private normal binary of exp 0425 and the catcher on. One set per start, 15 runs, interleaved, one BOX-LOCK line (exp
# 0413's chain lock):
#   CHAIN_SET=playgo (first: the regression lead): C control x3, L P1 locus slow x4, F P2 prefetch 500 ms x4,
#                    K P3 call cost 200 us x4
#   CHAIN_SET=sched:  C control x3, S C1 wake slice 200 us x4, Y C2 handoff 300 us x4, D C3 direct wake x4
# Each run: run0425f.sh, slot 4, the 14:50 record's gameplay at G, G+120 s. The rule is check0425.py's, fixed before
# the runs (README). Stops (R55): a kernel GPU line, a real pad key (R51), any class but TARGET/NO_CRASH/NOT_ROUTED,
# a second NOT_ROUTED, a STOP file ($HERE/STOP, read before each run). A TARGET run (the known crash, no kernel line)
# continues the chain only with CHAIN_TARGET_OK=1, which the top session sets by name when it starts the chain.
# usage (on the box, detached, in ~/bc5-work/exp0425): CHAIN_SET=playgo|sched CHAIN_TARGET_OK=1 bash chain0425.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0425/n; R=$N/raw; HERE=$(cd "$(dirname "$0")" && pwd)
BIN=$W/exp0425/kyty_emulator; WORDS=$W/exp0413/n/words0413nz.txt; LOCKINC=$W/exp0413/n/chainlock0417.inc
SET=${CHAIN_SET:-}; OUT=$N/chain-rows-$SET.txt
say() { echo "chain0425 $(date +%T): $*"; }
[ -x "$BIN" ] && [ -s "$W/exp0425/binary.md5" ] || { say "NOT STARTED, no private binary or binary.md5"; exit 1; }
WANT=$(cat "$W/exp0425/binary.md5"); MB=$(md5sum < "$BIN" | cut -d' ' -f1)
[ "$MB" = "$WANT" ] || { say "NOT STARTED, the binary is ${MB:0:8}, not ${WANT:0:8}"; exit 1; }
[ -s "$WORDS" ] && [ -f "$LOCKINC" ] || { say "NOT STARTED, no $WORDS or $LOCKINC"; exit 1; }
[ -d "$W/exp0425/saves-named/PPSA03671" ] || { say "NOT STARTED, no named snapshot (MODE=name bash run0425f.sh first)"; exit 1; }
[ -s "$W/exp0425/inputs/fight1450-play.cmd" ] || { say "NOT STARTED, no exp0425/inputs/fight1450-play.cmd"; exit 1; }
case "$SET" in
  playgo) TAGS="f425C1 f425L1 f425F1 f425K1 f425L2 f425F2 f425K2 f425C2 f425L3 f425F3 f425K3 f425C3 f425L4 f425F4 f425K4" ;;
  sched) TAGS="f425C4 f425S1 f425Y1 f425D1 f425S2 f425Y2 f425D2 f425C5 f425S3 f425Y3 f425D3 f425C6 f425S4 f425Y4 f425D4" ;;
  *) say "NOT STARTED, CHAIN_SET is playgo or sched"; exit 1 ;;
esac
mkdir -p "$R" || exit 1
for t in $TAGS; do { [ -e "$R/$t-start.txt" ] || [ -e "$R/$t-end.txt" ] || [ -e "$R/${t}R-start.txt" ]; } && { say "NOT STARTED, tag $t used"; exit 1; }; done
[ -e "$W/BOX-LOCK.nas" ] && { say "NOT STARTED, BOX-LOCK.nas exists"; exit 1; }
[ -e "$HERE/STOP" ] && { say "NOT STARTED, $HERE/STOP exists"; exit 1; }
armwords() {  # the arm's words, by the tag's fifth letter
  case "$1" in
    f425C*) echo "" ;;
    f425L*) echo "KYTY_BC5_0425_PLAYGO_LOCUS=slow" ;;
    f425F*) echo "KYTY_BC5_0425_PLAYGO_PREFETCH_MS=500" ;;
    f425K*) echo "KYTY_BC5_0425_PLAYGO_CALL_US=200" ;;
    f425S*) echo "KYTY_BC5_0425_WAKE_SLICE_US=200" ;;
    f425Y*) echo "KYTY_BC5_0425_HANDOFF_US=300" ;;
    f425D*) echo "KYTY_BC5_0425_DIRECT_WAKE=1" ;;
    *) return 1 ;;
  esac
}
cd "$N" || exit 1
. "$LOCKINC"
chain_claim "exp 0425 set $SET: the second title's fight, JobArenaFix off, 15 runs on the private normal ${WANT:0:8}" 95 || { say "NOT STARTED"; exit 1; }
PADS=(); PADN=0
padon() { : > "$R/$1-pad.txt"; local d; for d in /dev/input/by-id/*-event-joystick; do [ -e "$d" ] || continue; stdbuf -oL evtest "$d" 2> /dev/null | grep --line-buffered 'EV_KEY.*value 1' >> "$R/$1-pad.txt" & PADS+=($!); done; }
padoff() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); PADN=$(wc -l < "$R/$1-pad.txt"); }
fin() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; chain_release; }
trap fin EXIT
say "binary ${WANT:0:8}; kernel $(uname -r); boot $(cut -c1-8 /proc/sys/kernel/random/boot_id)"
: > "$OUT"
SPARE=1
one() {  # tag. Sets CLASS; returns 1 when the chain must stop
  local t=$1 aw line
  aw=$(armwords "$t") || { say "STOP: no arm for $t"; return 1; }
  [ -e "$HERE/STOP" ] && { say "STOP: $HERE/STOP before $t"; return 1; }
  padon "$t"
  # shellcheck disable=SC2086
  line=$(N_SLOT=4 P_BIN=$BIN P_WANT=$WANT P_WORDS=$WORDS bash "$HERE/run0425f.sh" "$t" "${t:4:1}" 120 KYTY_BC5_JOB_ARENA_FIX=0 KYTY_BC5_0425_CATCH=1 $aw | grep "^$t ")
  padoff "$t"
  CLASS=$(printf '%s\n' "$line" | sed -n 's/.*; CLASS \([A-Z_]*\);.*/\1/p')
  echo "$t ${CLASS:-NONE} pad $PADN $(printf '%s\n' "$line" | sed -n 's/.*; exposure \(.*\)$/\1/p')" >> "$OUT"
  say "$t: ${line:-no result line}; real pad keys $PADN"
  [ "$PADN" = 0 ] || { say "STOP: a real pad key in $t (the maintainer is at the box)"; return 1; }
  case "${CLASS:-NONE}" in
    NO_CRASH | NOT_ROUTED) return 0 ;;
    TARGET) [ "${CHAIN_TARGET_OK:-0}" = 1 ] && return 0; say "STOP: $t crashed at the site and CHAIN_TARGET_OK is not 1"; return 1 ;;
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
python3 "$HERE/check0425.py" rule "$OUT"
say "ended"
