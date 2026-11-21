#!/usr/bin/env bash
# BC5 exp 0438 (tag r438o): the smoke after the shared swap of r438o (swap0438o.sh); smoke0438s.sh without the second
# title's run (the second title is uninstalled, 2026-11-21); each run's binary read from /proc/<pid>/exe (LESSONS R66):
#   o438sc  ASTRO BOT 200 s on the shared lean build (exp 0413's start0413g.sh, a private _SaveData)
#   o438sn  ASTRO BOT 200 s on the shared NORMAL build (r438's 60-s count line with r438o's counters shows there)
# At 150 s of each run the drm-engine-* lines, GTT in use and MemAvailable. One BOX-LOCK line; ulimit -c 0. Stops at the
# first failed run, kernel line or pad key. Before each run: no bc5 FUSE mount inside the container (LESSONS: a dead
# endpoint passes mountpoint -q and the launcher then skips its mount).
# usage (on the box, detached under the user manager, in ~/bc5-work/exp0413/n):
#   LEAN_WANT=<md5> NORMAL_WANT=<md5> bash ~/bc5-work/exp0438/r438okit/bake/smoke0438os.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0413/n; R=$N/raw
LB=$W/kytyplus-build-lean/src/kyty_emulator; NB=$W/kytyplus-build/src/kyty_emulator
ML=$(md5sum < "$LB" | cut -d' ' -f1); MN=$(md5sum < "$NB" | cut -d' ' -f1)
cd "$N" || exit 1
[ "$ML" = "${LEAN_WANT:?the swapped lean md5}" ] || { echo "smoke0438o ended $(date +%T): NOT STARTED, lean is ${ML:0:8}"; exit 1; }
[ "$MN" = "${NORMAL_WANT:?the swapped normal md5}" ] || { echo "smoke0438o ended $(date +%T): NOT STARTED, normal is ${MN:0:8}"; exit 1; }
for t in o438sc o438sn; do { [ -e "$R/$t-end.txt" ] || [ -e "$R/$t-start.txt" ]; } && { echo "smoke0438o ended $(date +%T): NOT STARTED, tag $t used"; exit 1; }; done
pgrep '^kyty_emulator' > /dev/null && { echo "smoke0438o ended $(date +%T): NOT STARTED, an emulator runs"; exit 1; }
if [ -n "${CHAIN_LOCKLINE:-}" ] && [ "$(cat "$W/BOX-LOCK" 2> /dev/null)" = "$CHAIN_LOCKLINE" ]; then  # run-swap0438o.sh holds the one line
    . "$N/chainlock0417.inc"; chain_release() { :; }; echo "the lock line of the caller is taken over: $CHAIN_LOCKLINE"
else
. "$N/chainlock0417.inc"
chain_claim "exp 0438: smoke of the r438o swap: ASTRO BOT lean 200 s + ASTRO BOT normal 200 s" 12 || { echo "smoke0438o ended $(date +%T): NOT STARTED"; exit 1; }
fi
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
deadmnt() { distrobox enter ubuntu -- sh -c 'M=$HOME/bc5-data/mnt/PPSA21567; if mountpoint -q "$M" && ! head -c1 "$M/sce_sys/param.json" > /dev/null 2>&1; then echo dead; fi' 2> /dev/null < /dev/null | grep -q dead; }
deadmnt && { echo "smoke0438o: a dead ASTRO mount inside the container: NOT STARTED"; exit 1; }
OK=1
echo "binaries: lean ${ML:0:8}, normal ${MN:0:8}; kernel $(uname -r); boot $(cut -c1-8 /proc/sys/kernel/random/boot_id)"
padon o438sc; engines o438sc; exe o438sc
line=$(P_BIN=$LB P_WANT=$ML bash ./start0413g.sh o438sc astro 200 2>&1 | tail -1)
padoff o438sc; kill "$SAMP" 2> /dev/null
echo "o438sc: $line; real pad keys $PADN"
exechk o438sc "$ML"
case "$line" in *PASS*"kernel lines 0"*) ;; *) OK=0 ;; esac
[ "$PADN" = 0 ] || OK=0
if [ "$OK" = 1 ]; then
    sleep 5
    deadmnt && { echo "o438sn: a dead ASTRO mount inside the container"; OK=0; }
fi
if [ "$OK" = 1 ]; then
    padon o438sn; engines o438sn; exe o438sn
    line=$(P_BIN=$NB P_WANT=$MN bash ./start0413g.sh o438sn astro 200 2>&1 | tail -1)
    padoff o438sn; kill "$SAMP" 2> /dev/null
    echo "o438sn: $line; real pad keys $PADN"
    exechk o438sn "$MN"
    case "$line" in *PASS*"kernel lines 0"*) ;; *) OK=0 ;; esac
    [ "$PADN" = 0 ] || OK=0
    echo "o438sn: r438 lines $(grep -ah 'r438 (exp 0438, b438)' "$R"/o438sn-play.log 2> /dev/null | wc -l), BUG lines $(grep -ah 'r438 (exp 0438, b438): BUG' "$R"/o438sn-play.log 2> /dev/null | wc -l); last: $(grep -ah 'r438 (exp 0438, b438): t ' "$R"/o438sn-play.log 2> /dev/null | tail -1 | cut -c1-200)"
else echo "o438sn: not run"; fi
for t in o438sc o438sn; do [ -s "$R/$t-engines.txt" ] && echo "$t engines at 150 s: $(tr -s ' \n' ' ' < "$R/$t-engines.txt")"; done
echo "smoke0438o: $([ "$OK" = 1 ] && echo "ALL PASS" || echo "NOT ALL PASS")"
echo "smoke0438o ended $(date +%T)"
