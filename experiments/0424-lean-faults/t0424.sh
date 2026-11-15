#!/usr/bin/env bash
# BC5 exp 0424: the private test build's test (the top session's GO, 2026-11-15 21:06). The second title, RT on, the
# private save copy reset from exp 0412's named snapshot by the start scripts (R45; live saves not read), ulimit -c 0.
#   a424f1, a424n1, a424f2, a424n2: walks to G+240 on the private NORMAL build (run0413p.sh), the fix
#     BC5_DIRECT_ACB_QUEUE_STATE off / ON / off / ON; the catcher's last aq424c line per walk
#   a424l: the private LEAN build with the fix ON, 420 s, the route by time (a cross at 90, 100, 108 s, the walk from
#     170 s); the switch is read back from the emulator's /proc/<pid>/environ at about 30 s
# The chain stops at the first kernel or crash line and at a real pad key (R55, R51). One BOX-LOCK line.
# usage (on the box, detached, in ~/bc5-work/exp0424): bash t0424.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0413/n; R=$N/raw; E=$W/exp0424
NB=$E/build-normal/src/kyty_emulator; LB=$E/build-lean/src/kyty_emulator
MN=$(md5sum < "$NB" | cut -d' ' -f1); ML=$(md5sum < "$LB" | cut -d' ' -f1)
TAGS="a424f1 a424n1 a424f2 a424n2 a424l"
for t in $TAGS; do { [ -e "$R/$t-start.txt" ] || [ -e "$R/$t-end.txt" ]; } && { echo "t0424 ended $(date +%T): NOT STARTED, tag $t used"; exit 1; }; done
grep -aqF 'tag aq424c' "$NB" || { echo "t0424 ended $(date +%T): NOT STARTED, $NB is not the test build"; exit 1; }
[ -e "$W/BOX-LOCK.nas" ] && { echo "t0424 ended $(date +%T): NOT STARTED, BOX-LOCK.nas exists"; exit 1; }
cd "$N" || exit 1
. "$N/chainlock0417.inc"
chain_claim "exp 0424: private test build, the second title: 4 walks to G+240 (fix off/ON/off/ON) + lean ON 420 s" 45 || { echo "t0424 ended $(date +%T): NOT STARTED"; exit 1; }
PADS=(); PADN=0
padon() { : > "$R/$1-pad.txt"; local d; for d in /dev/input/by-id/*-event-joystick; do [ -e "$d" ] || continue; stdbuf -oL evtest "$d" 2> /dev/null | grep --line-buffered 'EV_KEY.*value 1' >> "$R/$1-pad.txt" & PADS+=($!); done; }
padoff() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); pkill -u "$USER" -x evtest 2> /dev/null; PADN=$(wc -l < "$R/$1-pad.txt"); }
fin() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; chain_release; }
trap fin EXIT
echo "binaries: private normal ${MN:0:8}, private lean ${ML:0:8}"
recs() { find "$HOME/bc5-data/captures/faults" -mindepth 1 -maxdepth 1 -type d -newermt "@$1" 2> /dev/null | wc -l; }
STOP=""
for t in a424f1 a424n1 a424f2 a424n2; do
    case "$t" in *n*) sw=1 ;; *) sw=0 ;; esac
    t0=$(date +%s); padon "$t"
    line=$(P_BIN=$NB P_WANT=$MN P_WORDS=$N/words0413nz.txt bash ./run0413p.sh "$t" nozeroskip 240 BC5_DIRECT_ACB_QUEUE_STATE=$sw | grep "^$t ")
    padoff "$t"
    echo "$t (fix $([ $sw = 1 ] && echo ON || echo off)): ${line:-no result line}; real pad keys $PADN; new fault records $(recs "$t0")"
    echo "$t switch line: $(grep -a 'tag aq424)' "$R/$t-play.log" 2> /dev/null | head -1 | cut -c1-120)"
    echo "$t catcher, last: $(grep -a 'tag aq424c' "$R/$t-play.log" 2> /dev/null | tail -1 | cut -c1-400)"
    echo "$t catcher lines: $(grep -a -c 'tag aq424c' "$R/$t-play.log" 2> /dev/null)"
    echo "$t route: $(grep -h 'route:' "$R/$t-start.txt" 2> /dev/null | tr '\n' ';' | cut -c1-300)"
    [ "$PADN" = 0 ] || { STOP="a real pad key in $t"; break; }
    case "$line" in *"kernel lines 0, crash lines 0"*) ;; *) STOP="a kernel or crash line (or no result) in $t"; break ;; esac
    sleep 10
done
if [ -z "$STOP" ]; then
    CMD=$N/cmd-a424l.txt
    { printf 'wait 90000\npress cross\nwait 10000\npress cross\nwait 8000\npress cross\nwait 62000\n'
      c=0; while [ $c -lt 14 ]; do s=255; [ $(((c / 4) % 2)) = 1 ] && s=0; printf 'stick l 128 0 15000\nstick r %d 128 1200\nwait 300\n' "$s"; c=$((c + 1)); done
      printf 'stick l 128 128\nstick r 128 128\n'; } > "$CMD"
    ( for _ in $(seq 1 90); do p=$(pgrep -o '^kyty_emulator') && [ -r "/proc/$p/environ" ] && [ "$(($(date +%s) - $(stat -c %Y "/proc/$p")))" -ge 30 ] && { tr '\0' '\n' < "/proc/$p/environ" | grep -c '^BC5_DIRECT_ACB_QUEUE_STATE=1$' > "$R/a424l-switch.txt"; exit 0; }; sleep 2; done ) &
    padon a424l
    line=$(P_BIN=$LB P_WANT=$ML P_WORDS=$N/words0413nz.txt bash ./start0413l.sh a424l lean 420 KYTY_BC5_INPUT_CMD="$CMD" BC5_DIRECT_ACB_QUEUE_STATE=1 | grep "^a424l ")
    padoff a424l; wait
    echo "a424l (lean, fix ON): ${line:-no result line}; real pad keys $PADN; key lines done $(cat "$CMD.done" 2> /dev/null || echo '?') of $(wc -l < "$CMD"); BC5_DIRECT_ACB_QUEUE_STATE=1 in its environment: $(cat "$R/a424l-switch.txt" 2> /dev/null || echo 'not read')"
fi
echo "t0424: ${STOP:-all runs done}"
echo "t0424 ended $(date +%T)"
