#!/usr/bin/env bash
# BC5 exp 0424 addendum: the corrected catcher aq424q (the top session's GO after the re-check). One chain, one BOX-LOCK
# line: mk0424b.py on the private tree of b0424.sh (~/bc5-work/exp0424/tree, unit 11e0de65 -> aadd0b36), the private
# NORMAL build rebuilt in place (ninja, nice 19; the lean is not rebuilt), then ONE walk of the second title to G+240
# with the fix OFF (BC5_DIRECT_ACB_QUEUE_STATE=0), RT on, the private save copy reset from exp 0412's named snapshot by
# run0413p.sh (R45), ulimit -c 0. Stops at a kernel or crash line (R55) and reports a real pad key (R51).
# ~/src/KytyPlus, the shared builds, the backend source and archive are only read.
# usage (on the box, detached, in ~/bc5-work/exp0424): bash t0424b.sh
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; N=$W/exp0413/n; R=$N/raw; E=$W/exp0424; HERE=$(cd "$(dirname "$0")" && pwd)
U=$E/tree/src/libs/bc5LleAgc.cpp; D=$E/build-normal; NB=$D/src/kyty_emulator; ARCH=$W/backend-ubuntu/libbc5_backend.a
m8() { md5sum < "$1" | cut -c1-8; }
out() { echo "t0424b ended $(date +%T): $*"; exit 1; }
T=a424q1
{ [ -e "$R/$T-start.txt" ] || [ -e "$R/$T-end.txt" ]; } && out "NOT STARTED, tag $T used"
[ -e "$W/BOX-LOCK.nas" ] && out "NOT STARTED, BOX-LOCK.nas exists"
pgrep '^kyty_emulator' > /dev/null && out "NOT STARTED, an emulator runs"
[ "$(m8 "$ARCH")" = 9aab722c ] || out "NOT STARTED, the archive is not 9aab722c"
cd "$N" || exit 1
. "$N/chainlock0417.inc"
chain_claim "exp 0424: corrected catcher, private normal rebuilt under exp0424, then 1 walk of the second title to G+240 (fix off)" 30 || out "NOT STARTED, no lock"
PADS=()
fin() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; pkill -u "$USER" -x evtest 2> /dev/null; chain_release; }
trap fin EXIT
case "$(m8 "$U")" in
    11e0de65) python3 "$HERE/mk0424b.py" "$E/tree" || out "mk0424b.py refused" ;;
    aadd0b36) echo "the tree already holds aadd0b36" ;;
    *) out "the private unit is $(m8 "$U"), neither 11e0de65 nor aadd0b36" ;;
esac
[ "$(m8 "$U")" = aadd0b36 ] || out "the new unit is $(m8 "$U"), not the laptop's aadd0b36"
echo "== $(date +%T) build normal"
distrobox enter ubuntu -- sh -c "cd '$D' && nice -n 19 ninja kyty_emulator" < /dev/null > "$D.build-q.log" 2>&1 || { grep -m12 -E "error:" "$D.build-q.log" | cut -c1-260; out "build"; }
echo "normal: $(m8 "$NB"), warnings $(grep -c 'warning:' "$D.build-q.log"), in bc5LleAgc: $(grep 'warning:' "$D.build-q.log" | grep -c bc5LleAgc); catcher text $(strings "$NB" | grep -c 'tag aq424q'), old catcher text $(strings "$NB" | grep -c 'tag aq424c')"
grep -aqF 'tag aq424q' "$NB" || out "the build lacks aq424q"
[ "$(m8 "$ARCH")" = 9aab722c ] || out "the archive changed"
pgrep '^kyty_emulator' > /dev/null && out "an emulator started; no walk"
MN=$(md5sum < "$NB" | cut -d' ' -f1)
t0=$(date +%s); : > "$R/$T-pad.txt"
for d in /dev/input/by-id/*-event-joystick; do [ -e "$d" ] || continue; stdbuf -oL evtest "$d" 2> /dev/null | grep --line-buffered 'EV_KEY.*value 1' >> "$R/$T-pad.txt" & PADS+=($!); done
line=$(P_BIN=$NB P_WANT=$MN P_WORDS=$N/words0413nz.txt bash ./run0413p.sh "$T" nozeroskip 240 BC5_DIRECT_ACB_QUEUE_STATE=0 | grep "^$T ")
[ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); pkill -u "$USER" -x evtest 2> /dev/null
recs=$(find "$HOME/bc5-data/captures/faults" -mindepth 1 -maxdepth 1 -type d -newermt "@$t0" 2> /dev/null | wc -l)
echo "$T (fix off): ${line:-no result line}; real pad keys $(wc -l < "$R/$T-pad.txt"); new fault records $recs"
echo "$T switch line: $(grep -a 'tag aq424)' "$R/$T-play.log" 2> /dev/null | head -1 | cut -c1-120)"
echo "$T catcher lines: $(grep -a -c 'tag aq424q' "$R/$T-play.log" 2> /dev/null)"
grep -a 'tag aq424q' "$R/$T-play.log" 2> /dev/null > "$E/$T-catcher.txt"
echo "$T catcher, last: $(tail -1 "$E/$T-catcher.txt" | cut -c1-900)"
echo "$T route: $(grep -h 'route:' "$R/$T-start.txt" 2> /dev/null | tr '\n' ';' | cut -c1-300)"
echo "t0424b ended $(date +%T)"
