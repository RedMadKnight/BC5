#!/usr/bin/env bash
# BC5 exp 0429: the ASTRO BOT smoke of candidate R before any swap (the top session, 2026-11-17): exp 0431's
# astro0431.sh (named save snapshot, route by time, screen shots kept on the box only, one BOX-LOCK line per call) on the
# private build 11, R off and R on, normal and lean, the build's defaults (arm D) otherwise. Four calls in turn:
#   <p>A1 normal RR=0, <p>A2 normal RR=$RRMODE, <p>A3 lean RR=0, <p>A4 lean RR=$RRMODE
# After each: the result line, the fps lines of KYTY_BC5_FPS_COUNTER=1 (astro0431 sets it) and R's lines. Stops at the
# first run that is not a PASS (astro0431's own rule) or at ~/bc5-work/exp0431/STOP or ~/bc5-work/exp0429/STOP.
# Screen shots stay on the box (~/bc5-work/exp0431/shots/), never in git.
# usage (on the box, detached): [RRMODE=1|2] [SECS=200] bash ~/bc5-work/exp0429/astro0429.sh <prefix, e.g. a429B>
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; E=$W/exp0429; R=$W/exp0413/n/raw; P=${1:?a tag prefix}; M=${RRMODE:-1}; SECS=${SECS:-200}
for v in normal lean; do
  [ "$(md5sum < "$E/$v/kyty_emulator" | cut -d' ' -f1)" = "$(cat "$E/$v/binary.md5")" ] || { echo "the $v binary is not its pin"; exit 1; }
done
n=0
for spec in "normal 0" "normal $M" "lean 0" "lean $M"; do
  read -r v rr <<< "$spec"; n=$((n + 1)); t=${P}A$n
  [ -e "$E/STOP" ] && { echo "$(date +%T) STOP file: stopped before $t"; break; }
  echo "$(date +%T) == $t: private $v, KYTY_BC5_0429_RR=$rr"
  out=$(cd "$W/exp0431" && XBIN=$E/$v/kyty_emulator XWORDS="KYTY_BC5_0429_RR=$rr" bash astro0431.sh "$SECS" "$t:x:D" 2>&1)
  printf '%s\n' "$out" | grep -v 'w428c lines' | tail -4
  grep -a -i 'fps\|flips' "$R/$t-play.log" 2> /dev/null | tail -3 | cut -c1-200
  grep -a 'exp 0429 R count\|exp 0429: R (RR' "$R/$t-play.log" 2> /dev/null | tail -3 | cut -c1-260
  printf '%s\n' "$out" | grep -q "$t: PASS" || { echo "$(date +%T) $t is not a PASS: stopped"; break; }
done
echo "$(date +%T) astro0429 ended"
