#!/usr/bin/env bash
# BC5 exp 0425: the smoke after the shared C1 swap (int0425.sh), lean only, as the top session asked:
#   s425a  ASTRO BOT 45 s on the shared lean build (exp 0413's start0413g.sh, a private _SaveData that starts empty)
#   s425t  the second title 300 s on the shared lean build, the route by time (a cross at 90, 100, 108 s, then a walk
#          from 170 s), as exp 0422's w2lb; RT on; the save copy reset from exp 0412's named snapshot (R45, never the
#          live saves)
# Exposure on lean (which prints nothing): at 150 s of each run, the emulator's threads' se.slice from /proc/<tid>/sched;
# C1 shows as threads with a 200000 ns slice.
# One BOX-LOCK line; ulimit -c 0. Stops before s425t on a kernel line, a pad key or a failed s425a.
# usage (on the box, detached, in ~/bc5-work/exp0413/n): LEAN_WANT=<md5> bash ~/bc5-work/exp0425/smoke0425.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0413/n; R=$N/raw
LB=$W/kytyplus-build-lean/src/kyty_emulator
ML=$(md5sum < "$LB" | cut -d' ' -f1)
cd "$N" || exit 1
[ "$ML" = "${LEAN_WANT:?the swapped lean md5}" ] || { echo "smoke0425 ended $(date +%T): NOT STARTED, lean is ${ML:0:8}"; exit 1; }
for t in s425a s425t; do { [ -e "$R/$t-end.txt" ] || [ -e "$R/$t-start.txt" ]; } && { echo "smoke0425 ended $(date +%T): NOT STARTED, tag $t used"; exit 1; }; done
pgrep '^kyty_emulator' > /dev/null && { echo "smoke0425 ended $(date +%T): NOT STARTED, an emulator runs"; exit 1; }
. "$N/chainlock0417.inc"
chain_claim "exp 0425: smoke of the shared C1 swap on lean: ASTRO BOT 45 s + the second title 300 s by time" 15 || { echo "smoke0425 ended $(date +%T): NOT STARTED"; exit 1; }
PADS=(); PADN=0; SAMP=""
padon() { : > "$R/$1-pad.txt"; local d; for d in /dev/input/by-id/*-event-joystick; do [ -e "$d" ] || continue; stdbuf -oL evtest "$d" 2> /dev/null | grep --line-buffered 'EV_KEY.*value 1' >> "$R/$1-pad.txt" & PADS+=($!); done; }
padoff() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); pkill -u "$USER" -x evtest 2> /dev/null; PADN=$(wc -l < "$R/$1-pad.txt"); }
slices() {  # at 150 s: the slice of every thread of the emulator
    ( sleep 150; p=$(pgrep -n '^kyty_emulator'); [ -n "$p" ] || { echo "no emulator at 150 s" > "$R/$1-slices.txt"; exit 0; }
      for s in /proc/"$p"/task/*/sched; do awk '/se.slice/ {print $3}' "$s" 2> /dev/null; done | sort | uniq -c | sort -rn > "$R/$1-slices.txt" ) &
    SAMP=$!
}
fin() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; chain_release; }
trap fin EXIT
OK=1
echo "binary: lean ${ML:0:8}; kernel $(uname -r)"
padon s425a; slices s425a
line=$(P_BIN=$LB P_WANT=$ML bash ./start0413g.sh s425a astro 45 2>&1 | tail -1)
padoff s425a; kill "$SAMP" 2> /dev/null
echo "s425a: $line; real pad keys $PADN"
case "$line" in *PASS*"kernel lines 0"*) ;; *) OK=0 ;; esac
[ "$PADN" = 0 ] || OK=0
if [ "$OK" = 1 ]; then
    sleep 5; CMD=$N/cmd-s425t.txt
    { printf 'wait 90000\npress cross\nwait 10000\npress cross\nwait 8000\npress cross\nwait 62000\n'
      c=0; while [ $c -lt 8 ]; do s=255; [ $(((c / 4) % 2)) = 1 ] && s=0; printf 'stick l 128 0 15000\nstick r %d 128 1200\nwait 300\n' "$s"; c=$((c + 1)); done
      printf 'stick l 128 128\nstick r 128 128\n'; } > "$CMD"
    padon s425t; slices s425t
    line=$(P_BIN=$LB P_WANT=$ML P_WORDS=$N/words0413nz.txt bash ./start0413l.sh s425t lean 300 KYTY_BC5_INPUT_CMD="$CMD" | grep "^s425t ")
    padoff s425t; wait "$SAMP" 2> /dev/null
    echo "${line:-s425t: no result line}; real pad keys $PADN; key lines done $(cat "$CMD.done" 2> /dev/null || echo '?') of $(wc -l < "$CMD")"
    case "$line" in *"PASS: ran 300 s"*"kernel lines 0, crash lines 0"*) ;; *) OK=0 ;; esac
else echo "s425t: not run"; fi
for t in s425a s425t; do [ -s "$R/$t-slices.txt" ] && echo "$t slices at 150 s (threads, ns): $(tr -s ' \n' ' ' < "$R/$t-slices.txt")"; done
echo "smoke0425: $([ "$OK" = 1 ] && echo "ALL PASS" || echo "NOT ALL PASS")"
echo "smoke0425 ended $(date +%T)"
