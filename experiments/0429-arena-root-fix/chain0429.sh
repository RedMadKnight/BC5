#!/usr/bin/env bash
# BC5 exp 0429 (derived by mkrun0429.py from exp 0428's chain0428.sh): the job-arena crash with the workaround gone from
# the code, on the long route: the 14:50 record's gameplay at G, then exp 0379's walk, to G+600 s; RT on; slot 4; the
# named snapshot; the private normal build of exp 0429 (one binary; only the switches differ). One BOX-LOCK line.
#   arms (every run also KYTY_BC5_0429_TRACE=1):
#     C  none of the candidates (exp 0425 C1 and exp 0428's way 2 as the shared defaults have them)
#     P  KYTY_BC5_0429_PRIO_ORDER=1 (not in screen2: it adds to M as Y)
#     M  KYTY_BC5_0429_CPU13=1 (the title's 13-CPU model, its masks applied)
#     Y  M + P
#     X  M + P + KYTY_BC5_0425_HANDOFF_US=300 (exp 0425 C2)
#   (the first build's arms A and H and its smoke h429X1, with AFFINITY=1, are gone with that build)
#   CHAIN_SET=smoke2:  h429M1 (once: the 13-CPU model runs, the trace shows the map and the masks applied)
#   CHAIN_SET=screen2: h429C1 h429M2 h429Y1 h429X2 h429C2 h429M3 h429Y2 h429X3
#   CHAIN_SET=rep<k>: set by REP_TAGS (the arms that survived, with controls between)
# TARGET (the crash at the site) and KERNEL do not stop the chain. Stops: a real pad key (R51), the STOP file
# ($HERE/STOP or ~/bc5-work/exp0429/STOP, read before each run), any other class, a second NOT_ROUTED.
# usage (on the box, detached, in ~/bc5-work/exp0429): CHAIN_SET=smoke|screen|rep1.. bash chain0429.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0429/n; R=$N/raw; HERE=$(cd "$(dirname "$0")" && pwd)
BIN=$W/exp0429/normal/kyty_emulator; WORDS=$W/exp0413/n/words0413nz.txt; LOCKINC=$W/exp0413/n/chainlock0417.inc
SET=${CHAIN_SET:-}; OUT=$N/chain-rows-$SET.txt
say() { echo "chain0429 $(date +%T): $*"; }
[ -x "$BIN" ] && [ -s "$W/exp0429/normal/binary.md5" ] || { say "NOT STARTED, no private binary or binary.md5"; exit 1; }
WANT=$(cat "$W/exp0429/normal/binary.md5"); MB=$(md5sum < "$BIN" | cut -d' ' -f1)
[ "$MB" = "$WANT" ] || { say "NOT STARTED, the binary is ${MB:0:8}, not ${WANT:0:8}"; exit 1; }
[ -s "$WORDS" ] && [ -f "$LOCKINC" ] || { say "NOT STARTED, no $WORDS or $LOCKINC"; exit 1; }
[ -d "$W/exp0425/saves-named/PPSA03671" ] || { say "NOT STARTED, no named snapshot in exp0425"; exit 1; }
[ -s "$W/exp0425/inputs/fight1450-play.cmd" ] || { say "NOT STARTED, no exp0425/inputs/fight1450-play.cmd"; exit 1; }
case "$SET" in
  smoke2) TAGS="h429M1" ;;
  screen2) TAGS="h429C1 h429M2 h429Y1 h429X2 h429C2 h429M3 h429Y2 h429X3" ;;
  rep[0-9]*) TAGS=${REP_TAGS:?REP_TAGS for a rep set} ;;
  *) say "NOT STARTED, CHAIN_SET is smoke2, screen2 or rep<k>"; exit 1 ;;
esac
mkdir -p "$R" || exit 1
for t in $TAGS; do { [ -e "$R/$t-start.txt" ] || [ -e "$R/$t-end.txt" ] || [ -e "$R/${t}R-start.txt" ]; } && { say "NOT STARTED, tag $t used"; exit 1; }; done
[ -e "$W/BOX-LOCK.nas" ] && { say "NOT STARTED, BOX-LOCK.nas exists"; exit 1; }
{ [ -e "$HERE/STOP" ] || [ -e "$W/exp0429/STOP" ]; } && { say "NOT STARTED, a STOP file exists"; exit 1; }
armwords() {
  case "$1" in
    h429C*) echo "KYTY_BC5_0429_TRACE=1" ;;
    h429M*) echo "KYTY_BC5_0429_TRACE=1 KYTY_BC5_0429_CPU13=1" ;;
    h429Y*) echo "KYTY_BC5_0429_TRACE=1 KYTY_BC5_0429_CPU13=1 KYTY_BC5_0429_PRIO_ORDER=1" ;;
    h429X*) echo "KYTY_BC5_0429_TRACE=1 KYTY_BC5_0429_CPU13=1 KYTY_BC5_0429_PRIO_ORDER=1 KYTY_BC5_0425_HANDOFF_US=300" ;;
    *) return 1 ;;
  esac
}
cd "$N" 2> /dev/null || { mkdir -p "$N" && cd "$N"; } || exit 1
. "$LOCKINC"
chain_claim "exp 0429 set $SET: the job-arena crash on the long route (fight + walk to G+600), private normal ${WANT:0:8}" 60 || { say "NOT STARTED"; exit 1; }
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
  { [ -e "$HERE/STOP" ] || [ -e "$W/exp0429/STOP" ]; } && { say "STOP: a STOP file before $t"; return 1; }
  padon "$t"
  # shellcheck disable=SC2086
  local play=600 walk=1  # exp 0429: the long route
  line=$(N_WALK_AFTER=$walk N_SLOT=4 P_BIN=$BIN P_WANT=$WANT P_WORDS=$WORDS bash "$HERE/run0429f.sh" "$t" "${t:4:1}" "$play" $aw | grep "^$t ")
  padoff "$t"
  CLASS=$(printf '%s\n' "$line" | sed -n 's/.*; CLASS \([A-Z_]*\);.*/\1/p')
  fps=$(printf '%s\n' "$line" | sed -n 's/.*; \([0-9.]*\) flips\/s over .*/\1/p'); gaps=$(printf '%s\n' "$line" | sed -n 's/.*s, \([0-9]*\) s with a gap over 100 ms.*/\1/p')
  echo "$t ${CLASS:-NONE} pad $PADN fps ${fps:--} gaps ${gaps:--} $(printf '%s\n' "$line" | sed -n 's/.*; exposure \(.*\)$/\1/p')" >> "$OUT"
  say "$t: ${line:-no result line}; real pad keys $PADN"
  [ "$PADN" = 0 ] || { say "STOP: a real pad key in $t (the maintainer is at the box)"; return 1; }
  case "${CLASS:-NONE}" in
    NO_CRASH | NOT_ROUTED | TARGET | KERNEL) return 0 ;;  # exp 0429: every arm gets its runs; a failed reset ends the chain by itself
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
python3 "$HERE/check0429.py" "$OUT"
say "ended"
