#!/usr/bin/env bash
# BC5 exp 0436: the smoke after the shared swap of the submit unlock built in (swap0436.sh); exp 0434's smoke0434.sh with
# its tags and lock text changed and each run's binary read from /proc/<pid>/exe with its md5 (LESSONS R66):
#   s436sc  the first title 200 s on the shared lean build (exp 0413's start0413g.sh, a private _SaveData that starts empty)
#   s436su  the second title 300 s on the shared lean build, the route by time (a cross at 90, 100, 108 s, then a walk
#           from 170 s); RT on; the save copy reset from exp 0412's named snapshot (R45, never the live saves)
#   s436sn  the first title 200 s on the shared NORMAL build (su436's count line shows there)
# At 150 s of each run, the drm-engine-* lines of the emulator's render fds, GTT in use and MemAvailable (exp 0434's
# check of the second title's memory wall; the lean build has no journal, so its import count is not in its log) (way 2 shows as compute time on the second
# title). One BOX-LOCK line; ulimit -c 0. Stops at the first failed run, kernel line or pad key.
# usage (on the box, detached under the user manager, in ~/bc5-work/exp0413/n):
#   LEAN_WANT=<md5> NORMAL_WANT=<md5> bash ~/bc5-work/exp0436/bake/smoke0436s.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0413/n; R=$N/raw
LB=$W/kytyplus-build-lean/src/kyty_emulator; NB=$W/kytyplus-build/src/kyty_emulator
ML=$(md5sum < "$LB" | cut -d' ' -f1); MN=$(md5sum < "$NB" | cut -d' ' -f1)
cd "$N" || exit 1
[ "$ML" = "${LEAN_WANT:?the swapped lean md5}" ] || { echo "smoke0436 ended $(date +%T): NOT STARTED, lean is ${ML:0:8}"; exit 1; }
[ "$MN" = "${NORMAL_WANT:?the swapped normal md5}" ] || { echo "smoke0436 ended $(date +%T): NOT STARTED, normal is ${MN:0:8}"; exit 1; }
for t in s436sc s436su s436sn; do { [ -e "$R/$t-end.txt" ] || [ -e "$R/$t-start.txt" ]; } && { echo "smoke0436 ended $(date +%T): NOT STARTED, tag $t used"; exit 1; }; done
pgrep '^kyty_emulator' > /dev/null && { echo "smoke0436 ended $(date +%T): NOT STARTED, an emulator runs"; exit 1; }
. "$N/chainlock0417.inc"
chain_claim "exp 0436: smoke of the submit-unlock swap: the first title lean 200 s + the second title lean 300 s + the first title normal 200 s" 20 || { echo "smoke0436 ended $(date +%T): NOT STARTED"; exit 1; }
PADS=(); PADN=0; SAMP=""
padon() { : > "$R/$1-pad.txt"; local d; for d in /dev/input/by-id/*-event-joystick; do [ -e "$d" ] || continue; stdbuf -oL evtest "$d" 2> /dev/null | grep --line-buffered 'EV_KEY.*value 1' >> "$R/$1-pad.txt" & PADS+=($!); done; }
padoff() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); pkill -u "$USER" -x evtest 2> /dev/null; PADN=$(wc -l < "$R/$1-pad.txt"); }
engines() {
    ( sleep 150; p=$(pgrep -n '^kyty_emulator'); [ -n "$p" ] || { echo "no emulator at 150 s" > "$R/$1-engines.txt"; exit 0; }
      grep -h '^drm-engine-' /proc/"$p"/fdinfo/* 2> /dev/null | sort | uniq > "$R/$1-engines.txt"
      echo "gtt-used-MiB $(( $(cat /sys/class/drm/card1/device/mem_info_gtt_used) / 1048576 )) of $(( $(cat /sys/class/drm/card1/device/mem_info_gtt_total) / 1048576 )); MemAvailable-MiB $(( $(awk '/^MemAvailable/{print $2}' /proc/meminfo) / 1024 ))" >> "$R/$1-engines.txt" ) &
    SAMP=$!
}
exe() { ( for _ in $(seq 1 240); do p=$(pgrep -n '^kyty_emulator') && break; sleep 1; done
          if [ -n "${p:-}" ]; then x=$(readlink "/proc/$p/exe"); echo "pid $p exe $x md5 $(md5sum < "$x" | cut -d' ' -f1)"; else echo "no emulator within 240 s"; fi ) > "$R/$1-exe.txt" 2>&1 & XP=$!; }
exechk() { wait "$XP" 2> /dev/null; echo "$1: exe [$(cat "$R/$1-exe.txt")]"; grep -q " md5 $2\$" "$R/$1-exe.txt" || { echo "$1: ANOTHER BINARY RAN"; OK=0; }; }
fin() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; chain_release; }
trap fin EXIT
OK=1
echo "binaries: lean ${ML:0:8}, normal ${MN:0:8}; kernel $(uname -r); boot $(cut -c1-8 /proc/sys/kernel/random/boot_id)"
padon s436sc; engines s436sc; exe s436sc
line=$(P_BIN=$LB P_WANT=$ML bash ./start0413g.sh s436sc t1 200 2>&1 | tail -1)
padoff s436sc; kill "$SAMP" 2> /dev/null
echo "s436sc: $line; real pad keys $PADN"
exechk s436sc "$ML"
case "$line" in *PASS*"kernel lines 0"*) ;; *) OK=0 ;; esac
[ "$PADN" = 0 ] || OK=0
if [ "$OK" = 1 ]; then
    sleep 5; CMD=$N/cmd-s436su.txt
    { printf 'wait 90000\npress cross\nwait 10000\npress cross\nwait 8000\npress cross\nwait 62000\n'
      c=0; while [ $c -lt 8 ]; do s=255; [ $(((c / 4) % 2)) = 1 ] && s=0; printf 'stick l 128 0 15000\nstick r %d 128 1200\nwait 300\n' "$s"; c=$((c + 1)); done
      printf 'stick l 128 128\nstick r 128 128\n'; } > "$CMD"
    padon s436su; engines s436su; exe s436su
    line=$(P_BIN=$LB P_WANT=$ML P_WORDS=$N/words0413nz.txt bash $W/exp0428/start0428l.sh s436su lean 300 KYTY_BC5_INPUT_CMD="$CMD" | grep "^s436su ")
    padoff s436su; wait "$SAMP" 2> /dev/null
    echo "${line:-s436su: no result line}; real pad keys $PADN; key lines done $(cat "$CMD.done" 2> /dev/null || echo '?') of $(wc -l < "$CMD")"
    case "$line" in *"PASS: ran 300 s"*"kernel lines 0, crash lines 0"*) ;; *) OK=0 ;; esac
    [ "$PADN" = 0 ] || OK=0
    exechk s436su "$ML"
else echo "s436su: not run"; fi
if [ "$OK" = 1 ]; then
    sleep 5
    padon s436sn; engines s436sn; exe s436sn
    line=$(P_BIN=$NB P_WANT=$MN bash ./start0413g.sh s436sn t1 200 2>&1 | tail -1)
    padoff s436sn; kill "$SAMP" 2> /dev/null
    echo "s436sn: $line; real pad keys $PADN"
    exechk s436sn "$MN"
    case "$line" in *PASS*"kernel lines 0"*) ;; *) OK=0 ;; esac
    [ "$PADN" = 0 ] || OK=0
    echo "s436sn: su436 lines $(grep -ah 'tag su436' "$R"/s436sn-play.log 2> /dev/null | wc -l); last: $(grep -ah 'tag su436' "$R"/s436sn-play.log 2> /dev/null | tail -1 | cut -c1-160)"
else echo "s436sn: not run"; fi
for t in s436sc s436su s436sn; do [ -s "$R/$t-engines.txt" ] && echo "$t engines at 150 s: $(tr -s ' \n' ' ' < "$R/$t-engines.txt")"; done
echo "smoke0436: $([ "$OK" = 1 ] && echo "ALL PASS" || echo "NOT ALL PASS")"
echo "smoke0436 ended $(date +%T)"
