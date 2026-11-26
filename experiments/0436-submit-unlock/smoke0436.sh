#!/usr/bin/env bash
# BC5 experiment 0436: a short first-title smoke of the candidate's test builds (exp 0434's smoke0434.sh, cut to the first title):
#   u436an  the first title 200 s on the candidate's NORMAL test build (exp 0413's start0413g.sh, a private _SaveData that
#           starts empty)
#   u436al  the first title 200 s on the candidate's LEAN test build
# Per run: the emulator's /proc/<pid>/exe and md5 (LESSONS R66) and the pad's key events (R51). One BOX-LOCK line for both
# (exp 0417's chainlock0417.inc); ulimit -c 0. Stops at the first failed run, kernel line, pad key or wrong binary.
# usage (on the box, detached under the user manager): bash ~/bc5-work/exp0436/kit/smoke0436.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; E=$W/exp0436; N=$W/exp0413/n; R=$N/raw
NB=$E/normal/kyty_emulator; LB=$E/lean/kyty_emulator
MN=$(md5sum < "$NB" | cut -d' ' -f1); ML=$(md5sum < "$LB" | cut -d' ' -f1)
cd "$N" || exit 1
[ "$MN" = "$(cat "$E/normal/binary.md5")" ] && [ "$ML" = "$(cat "$E/lean/binary.md5")" ] || { echo "smoke0436 ended $(date +%T): NOT STARTED, the test builds are not the built ones"; exit 1; }
for t in u436an u436al; do { [ -e "$R/$t-end.txt" ] || [ -e "$R/$t-start.txt" ]; } && { echo "smoke0436 ended $(date +%T): NOT STARTED, tag $t used"; exit 1; }; done
pgrep '^kyty_emulator' > /dev/null && { echo "smoke0436 ended $(date +%T): NOT STARTED, an emulator runs"; exit 1; }
. "$N/chainlock0417.inc"
chain_claim "exp 0436: the first title smoke of the su436 test builds, normal 200 s + lean 200 s" 12 || { echo "smoke0436 ended $(date +%T): NOT STARTED"; exit 1; }
PADS=(); PADN=0
padon() { : > "$E/raw/$1-pad.txt"; local d; for d in /dev/input/by-id/*-event-joystick; do [ -e "$d" ] || continue; stdbuf -oL evtest "$d" 2> /dev/null | grep --line-buffered 'EV_KEY.*value 1' >> "$E/raw/$1-pad.txt" & PADS+=($!); done; }
padoff() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); PADN=$(grep -c . "$E/raw/$1-pad.txt"); }
exe() { ( for _ in $(seq 1 120); do p=$(pgrep -n '^kyty_emulator') && break; sleep 1; done
          if [ -n "${p:-}" ]; then x=$(readlink "/proc/$p/exe"); echo "pid $p exe $x md5 $(md5sum < "$x" | cut -d' ' -f1)"; else echo "no emulator within 120 s"; fi ) > "$E/raw/$1-exe.txt" 2>&1 & XP=$!; }
fin() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; chain_release; }
trap fin EXIT
mkdir -p "$E/raw"
OK=1
echo "binaries: normal ${MN:0:8}, lean ${ML:0:8}; kernel $(uname -r); boot $(cut -c1-8 /proc/sys/kernel/random/boot_id)"
for t in u436an u436al; do
    [ "$OK" = 1 ] || { echo "$t: not run"; continue; }
    if [ "$t" = u436an ]; then b=$NB; w=$MN; else b=$LB; w=$ML; fi
    padon "$t"; exe "$t"
    line=$(P_BIN=$b P_WANT=$w bash ./start0413g.sh "$t" t1 200 2>&1 | tail -1)
    padoff "$t"; wait "$XP" 2> /dev/null
    echo "$t: $line; real pad keys $PADN; exe [$(cat "$E/raw/$t-exe.txt")]"
    case "$line" in *PASS*"kernel lines 0"*) ;; *) OK=0 ;; esac
    [ "$PADN" = 0 ] || OK=0
    grep -q " md5 $w\$" "$E/raw/$t-exe.txt" || { echo "$t: ANOTHER BINARY RAN"; OK=0; }
    sleep 5
done
echo "smoke0436: $([ "$OK" = 1 ] && echo "ALL PASS" || echo "NOT ALL PASS")"
echo "smoke0436 ended $(date +%T)"
