#!/usr/bin/env bash
# BC5 exp 0433: the smoke after the shared swap of ports pack 1 built in (int0433.sh); exp 0430's smoke0430.sh with its
# tags and lock text changed and a third run on the normal build:
#   s433sc  ASTRO BOT 200 s on the shared lean build (exp 0413's start0413g.sh, a private _SaveData that starts empty)
#   s433su  the second title 300 s on the shared lean build, the route by time (a cross at 90, 100, 108 s, then a walk
#           from 170 s); RT on; the save copy reset from exp 0412's named snapshot (R45, never the live saves)
#   s433sn  ASTRO BOT 200 s on the shared NORMAL build (the pack's hit-count lines show there)
# At 150 s of each run, the drm-engine-* lines of the emulator's render fds (way 2 shows as compute time on the second
# title). One BOX-LOCK line; ulimit -c 0. Stops at the first failed run, kernel line or pad key.
# usage (on the box, detached under the user manager, in ~/bc5-work/exp0413/n):
#   LEAN_WANT=<md5> NORMAL_WANT=<md5> bash ~/bc5-work/exp0433/bake/smoke0433.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0413/n; R=$N/raw
LB=$W/kytyplus-build-lean/src/kyty_emulator; NB=$W/kytyplus-build/src/kyty_emulator
ML=$(md5sum < "$LB" | cut -d' ' -f1); MN=$(md5sum < "$NB" | cut -d' ' -f1)
cd "$N" || exit 1
[ "$ML" = "${LEAN_WANT:?the swapped lean md5}" ] || { echo "smoke0433 ended $(date +%T): NOT STARTED, lean is ${ML:0:8}"; exit 1; }
[ "$MN" = "${NORMAL_WANT:?the swapped normal md5}" ] || { echo "smoke0433 ended $(date +%T): NOT STARTED, normal is ${MN:0:8}"; exit 1; }
for t in s433sc s433su s433sn; do { [ -e "$R/$t-end.txt" ] || [ -e "$R/$t-start.txt" ]; } && { echo "smoke0433 ended $(date +%T): NOT STARTED, tag $t used"; exit 1; }; done
pgrep '^kyty_emulator' > /dev/null && { echo "smoke0433 ended $(date +%T): NOT STARTED, an emulator runs"; exit 1; }
. "$N/chainlock0417.inc"
chain_claim "exp 0433: smoke of the ports-pack-1 swap: ASTRO BOT lean 200 s + the second title lean 300 s + ASTRO BOT normal 200 s" 20 || { echo "smoke0433 ended $(date +%T): NOT STARTED"; exit 1; }
PADS=(); PADN=0; SAMP=""
padon() { : > "$R/$1-pad.txt"; local d; for d in /dev/input/by-id/*-event-joystick; do [ -e "$d" ] || continue; stdbuf -oL evtest "$d" 2> /dev/null | grep --line-buffered 'EV_KEY.*value 1' >> "$R/$1-pad.txt" & PADS+=($!); done; }
padoff() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); pkill -u "$USER" -x evtest 2> /dev/null; PADN=$(wc -l < "$R/$1-pad.txt"); }
engines() {
    ( sleep 150; p=$(pgrep -n '^kyty_emulator'); [ -n "$p" ] || { echo "no emulator at 150 s" > "$R/$1-engines.txt"; exit 0; }
      grep -h '^drm-engine-' /proc/"$p"/fdinfo/* 2> /dev/null | sort | uniq > "$R/$1-engines.txt" ) &
    SAMP=$!
}
fin() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; chain_release; }
trap fin EXIT
OK=1
echo "binaries: lean ${ML:0:8}, normal ${MN:0:8}; kernel $(uname -r); boot $(cut -c1-8 /proc/sys/kernel/random/boot_id)"
padon s433sc; engines s433sc
line=$(P_BIN=$LB P_WANT=$ML bash ./start0413g.sh s433sc astro 200 2>&1 | tail -1)
padoff s433sc; kill "$SAMP" 2> /dev/null
echo "s433sc: $line; real pad keys $PADN"
case "$line" in *PASS*"kernel lines 0"*) ;; *) OK=0 ;; esac
[ "$PADN" = 0 ] || OK=0
if [ "$OK" = 1 ]; then
    sleep 5; CMD=$N/cmd-s433su.txt
    { printf 'wait 90000\npress cross\nwait 10000\npress cross\nwait 8000\npress cross\nwait 62000\n'
      c=0; while [ $c -lt 8 ]; do s=255; [ $(((c / 4) % 2)) = 1 ] && s=0; printf 'stick l 128 0 15000\nstick r %d 128 1200\nwait 300\n' "$s"; c=$((c + 1)); done
      printf 'stick l 128 128\nstick r 128 128\n'; } > "$CMD"
    padon s433su; engines s433su
    line=$(P_BIN=$LB P_WANT=$ML P_WORDS=$N/words0413nz.txt bash $W/exp0428/start0428l.sh s433su lean 300 KYTY_BC5_INPUT_CMD="$CMD" | grep "^s433su ")
    padoff s433su; wait "$SAMP" 2> /dev/null
    echo "${line:-s433su: no result line}; real pad keys $PADN; key lines done $(cat "$CMD.done" 2> /dev/null || echo '?') of $(wc -l < "$CMD")"
    case "$line" in *"PASS: ran 300 s"*"kernel lines 0, crash lines 0"*) ;; *) OK=0 ;; esac
    [ "$PADN" = 0 ] || OK=0
else echo "s433su: not run"; fi
if [ "$OK" = 1 ]; then
    sleep 5
    padon s433sn; engines s433sn
    line=$(P_BIN=$NB P_WANT=$MN bash ./start0413g.sh s433sn astro 200 2>&1 | tail -1)
    padoff s433sn; kill "$SAMP" 2> /dev/null
    echo "s433sn: $line; real pad keys $PADN"
    case "$line" in *PASS*"kernel lines 0"*) ;; *) OK=0 ;; esac
    [ "$PADN" = 0 ] || OK=0
    h=$(grep -h 'ports pack 1 hits' "$R"/s433sn* 2> /dev/null | sed 's/.*hits: \([A-Z_]*\) .*/\1/' | sort -u | tr '\n' ' ')
    echo "s433sn: fixes with hit lines: ${h:-none found}; switch lines: $(grep -hc 'ports pack 1: .*=on' "$R"/s433sn* 2> /dev/null | paste -sd+ | bc 2> /dev/null || echo 0)"
else echo "s433sn: not run"; fi
for t in s433sc s433su s433sn; do [ -s "$R/$t-engines.txt" ] && echo "$t engines at 150 s: $(tr -s ' \n' ' ' < "$R/$t-engines.txt")"; done
echo "smoke0433: $([ "$OK" = 1 ] && echo "ALL PASS" || echo "NOT ALL PASS")"
echo "smoke0433 ended $(date +%T)"
