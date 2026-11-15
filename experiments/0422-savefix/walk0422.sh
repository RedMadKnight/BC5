#!/usr/bin/env bash
# BC5 exp 0422: the second title's two runs of chk0422.sh, under new tags, after the top's NAS reinstall of the title
# (BOX-LOCK.nas; chk0422.sh's w1n and w2l were blocked on purpose at 16:26 by tag files, so they never started).
#   w1nb  the walk to G+240 on the shared normal build (run0413p.sh, the journal-gated route)
#   w2lb  the shared lean build, 420 s, the route by time (a cross at 90, 100, 108 s, the walk from 170 s)
# One BOX-LOCK line; refuses while BOX-LOCK.nas exists. RT on, ulimit -c 0, the private save copies of the start scripts.
# usage (on the box, detached, in ~/bc5-work/exp0422): bash walk0422.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0413/n; R=$N/raw
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator
MN=$(md5sum < "$NB" | cut -d' ' -f1); ML=$(md5sum < "$LB" | cut -d' ' -f1)
cd "$N" || exit 1
[ -e "$W/BOX-LOCK.nas" ] && { echo "walk0422 ended $(date +%T): NOT STARTED, BOX-LOCK.nas exists"; exit 1; }
for t in w1nb w2lb; do { [ -e "$R/$t-end.txt" ] || [ -e "$R/$t-start.txt" ]; } && { echo "walk0422 ended $(date +%T): NOT STARTED, tag $t used"; exit 1; }; done
case "$MN$ML" in 9da2a9d5*f942676c*) ;; *) echo "walk0422 ended $(date +%T): NOT STARTED, the shared binaries are not exp 0422's (${MN:0:8} ${ML:0:8})"; exit 1 ;; esac
. "$N/chainlock0417.inc"
chain_claim "exp 0422: the second title on the shared builds after the save fix, walk normal to G+240 + lean 420 s by time" 25 || { echo "walk0422 ended $(date +%T): NOT STARTED"; exit 1; }
livesum() { (cd "$W/_SaveData" && find . -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }
L0=$(livesum); echo "binaries: normal ${MN:0:8}, lean ${ML:0:8}; live saves $L0"
PADS=(); PADN=0
padon() { : > "$R/$1-pad.txt"; local d; for d in /dev/input/by-id/*-event-joystick; do [ -e "$d" ] || continue; stdbuf -oL evtest "$d" 2> /dev/null | grep --line-buffered 'EV_KEY.*value 1' >> "$R/$1-pad.txt" & PADS+=($!); done; }
padoff() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); pkill -u "$USER" -x evtest 2> /dev/null; PADN=$(wc -l < "$R/$1-pad.txt"); }
fin() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; chain_release; }
trap fin EXIT
OK=1
padon w1nb
line=$(P_BIN=$NB P_WANT=$MN P_WORDS=$N/words0413nz.txt bash ./run0413p.sh w1nb nozeroskip 240 | grep "^w1nb ")
padoff w1nb; echo "${line:-w1nb: no result line}; real pad keys $PADN"
echo "w1nb route: $(grep -h 'route:' "$R/w1nb-start.txt" 2> /dev/null | tr '\n' ';' | cut -c1-400)"
case "$line" in *"ended at G+240"*"kernel lines 0, crash lines 0"*) echo "w1nb: clean to G+240" ;; *) echo "w1nb: NOT clean"; OK=0 ;; esac
case "$line" in *"kernel lines 0"*) KOK=1 ;; *) KOK=0 ;; esac
if [ "$KOK" = 1 ] && [ "$PADN" = 0 ]; then
    sleep 5; CMD=$N/cmd-w2lb.txt
    { printf 'wait 90000\npress cross\nwait 10000\npress cross\nwait 8000\npress cross\nwait 62000\n'
      c=0; while [ $c -lt 14 ]; do s=255; [ $(((c / 4) % 2)) = 1 ] && s=0; printf 'stick l 128 0 15000\nstick r %d 128 1200\nwait 300\n' "$s"; c=$((c + 1)); done
      printf 'stick l 128 128\nstick r 128 128\n'; } > "$CMD"
    padon w2lb
    line=$(P_BIN=$LB P_WANT=$ML P_WORDS=$N/words0413nz.txt bash ./start0413l.sh w2lb lean 420 KYTY_BC5_INPUT_CMD="$CMD" | grep "^w2lb ")
    padoff w2lb; echo "${line:-w2lb: no result line}; real pad keys $PADN; key lines done $(cat "$CMD.done" 2> /dev/null || echo '?') of $(wc -l < "$CMD")"
    case "$line" in *"PASS: ran 420 s"*"kernel lines 0, crash lines 0"*) echo "w2lb: PASS (ran 420 s, the timed route and the walk)" ;; *) echo "w2lb: NOT A PASS"; OK=0 ;; esac
else echo "w2lb: not run (kernel line or pad key in w1nb)"; OK=0; fi
L1=$(livesum); echo "live saves after: $L1 ($([ "$L1" = "$L0" ] && echo unchanged || echo CHANGED))"
echo "walk0422: $([ "$OK" = 1 ] && echo "ALL PASS" || echo "NOT ALL PASS")"
echo "walk0422 ended $(date +%T)"
