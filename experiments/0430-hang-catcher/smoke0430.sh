#!/usr/bin/env bash
# BC5 exp 0430: the smoke after the hang-fix swap (int0430.sh), lean only; exp 0428's smoke0428b.sh with its tags, its lock
# text and the second title's starter changed (start0428l.sh: JobArenaFix as the shared input.cfg has it, not forced on):
#   s430c  the first title 45 s on the shared lean build (exp 0413's start0413g.sh, a private _SaveData that starts empty);
#          way 2 has no first-title row, so it should show no compute engine time
#   s430u  the second title 300 s on the shared lean build, the route by time (a cross at 90, 100, 108 s, then a walk
#          from 170 s); RT on; the save copy reset from exp 0412's named snapshot (R45, never the live saves)
# Exposure on lean (which prints nothing): at 150 s of each run, the drm-engine-* lines of the emulator's render fds
# (/proc/<pid>/fdinfo; F412 read them the same way): way 2 shows as drm-engine-compute time on the second title.
# One BOX-LOCK line; ulimit -c 0. Stops before s430u on a kernel line, a pad key or a failed s430c.
# usage (on the box, detached, in ~/bc5-work/exp0413/n): LEAN_WANT=<md5> bash ~/bc5-work/exp0430/smoke0430.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0413/n; R=$N/raw
LB=$W/kytyplus-build-lean/src/kyty_emulator
ML=$(md5sum < "$LB" | cut -d' ' -f1)
cd "$N" || exit 1
[ "$ML" = "${LEAN_WANT:?the swapped lean md5}" ] || { echo "smoke0430 ended $(date +%T): NOT STARTED, lean is ${ML:0:8}"; exit 1; }
for t in s430c s430u; do { [ -e "$R/$t-end.txt" ] || [ -e "$R/$t-start.txt" ]; } && { echo "smoke0430 ended $(date +%T): NOT STARTED, tag $t used"; exit 1; }; done
pgrep '^kyty_emulator' > /dev/null && { echo "smoke0430 ended $(date +%T): NOT STARTED, an emulator runs"; exit 1; }
. "$N/chainlock0417.inc"
chain_claim "exp 0430: smoke of the hang-fix swap on lean: the first title 45 s + the second title 300 s by time" 15 || { echo "smoke0430 ended $(date +%T): NOT STARTED"; exit 1; }
PADS=(); PADN=0; SAMP=""
padon() { : > "$R/$1-pad.txt"; local d; for d in /dev/input/by-id/*-event-joystick; do [ -e "$d" ] || continue; stdbuf -oL evtest "$d" 2> /dev/null | grep --line-buffered 'EV_KEY.*value 1' >> "$R/$1-pad.txt" & PADS+=($!); done; }
padoff() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); pkill -u "$USER" -x evtest 2> /dev/null; PADN=$(wc -l < "$R/$1-pad.txt"); }
engines() {  # at 150 s: the drm-engine lines of the emulator's render fds
    ( sleep 150; p=$(pgrep -n '^kyty_emulator'); [ -n "$p" ] || { echo "no emulator at 150 s" > "$R/$1-engines.txt"; exit 0; }
      grep -h '^drm-engine-' /proc/"$p"/fdinfo/* 2> /dev/null | sort | uniq > "$R/$1-engines.txt" ) &
    SAMP=$!
}
fin() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; chain_release; }
trap fin EXIT
OK=1
echo "binary: lean ${ML:0:8}; kernel $(uname -r)"
padon s430c; engines s430c
line=$(P_BIN=$LB P_WANT=$ML bash ./start0413g.sh s430c t1 45 2>&1 | tail -1)
padoff s430c; kill "$SAMP" 2> /dev/null
echo "s430c: $line; real pad keys $PADN"
case "$line" in *PASS*"kernel lines 0"*) ;; *) OK=0 ;; esac
[ "$PADN" = 0 ] || OK=0
if [ "$OK" = 1 ]; then
    sleep 5; CMD=$N/cmd-s430u.txt
    { printf 'wait 90000\npress cross\nwait 10000\npress cross\nwait 8000\npress cross\nwait 62000\n'
      c=0; while [ $c -lt 8 ]; do s=255; [ $(((c / 4) % 2)) = 1 ] && s=0; printf 'stick l 128 0 15000\nstick r %d 128 1200\nwait 300\n' "$s"; c=$((c + 1)); done
      printf 'stick l 128 128\nstick r 128 128\n'; } > "$CMD"
    padon s430u; engines s430u
    line=$(P_BIN=$LB P_WANT=$ML P_WORDS=$N/words0413nz.txt bash $W/exp0428/start0428l.sh s430u lean 300 KYTY_BC5_INPUT_CMD="$CMD" | grep "^s430u ")
    padoff s430u; wait "$SAMP" 2> /dev/null
    echo "${line:-s430u: no result line}; real pad keys $PADN; key lines done $(cat "$CMD.done" 2> /dev/null || echo '?') of $(wc -l < "$CMD")"
    case "$line" in *"PASS: ran 300 s"*"kernel lines 0, crash lines 0"*) ;; *) OK=0 ;; esac
else echo "s430u: not run"; fi
for t in s430c s430u; do [ -s "$R/$t-engines.txt" ] && echo "$t engines at 150 s: $(tr -s ' 
' ' ' < "$R/$t-engines.txt")"; done
echo "smoke0430: $([ "$OK" = 1 ] && echo "ALL PASS" || echo "NOT ALL PASS")"
echo "smoke0430 ended $(date +%T)"
