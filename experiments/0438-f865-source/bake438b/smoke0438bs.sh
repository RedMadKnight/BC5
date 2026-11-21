#!/usr/bin/env bash
# BC5 exp 0438 (tag bake438b): the smoke after the shared swap of bake438b (swap0438b.sh); smoke0438os.sh with its tags and
# its log lines moved to this bake (each run's binary read from /proc/<pid>/exe, LESSONS R66):
#   b438sc  ASTRO BOT 200 s on the shared lean build (exp 0413's start0413g.sh, a private _SaveData)
#   b438sn  ASTRO BOT 200 s on the shared NORMAL build (ng438's 60-s line, a1c438's 60-s line and r438's count line show there)
# No switch is set: the bake's defaults (all on) run. At 150 s of each run the drm-engine-* lines, GTT in use and
# MemAvailable. One BOX-LOCK line; ulimit -c 0. Stops at the first failed run, kernel line or pad key. Before each run: no
# dead bc5 FUSE mount inside the container (a dead endpoint passes mountpoint -q and the launcher then skips its mount).
# Reported, not judged: the A1 / A1P on lines, ng438's holds and its 10-s fallback BUG lines, r438's lines; A2's compare-only
# check is not in the bake (a build option), so its MISMATCH and a2c438 lines must be 0.
# usage (on the box, detached under the user manager, in ~/bc5-work/exp0413/n):
#   LEAN_WANT=<md5> NORMAL_WANT=<md5> bash ~/bc5-work/exp0438/bake438b/smoke0438bs.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0413/n; R=$N/raw
LB=$W/kytyplus-build-lean/src/kyty_emulator; NB=$W/kytyplus-build/src/kyty_emulator
ML=$(md5sum < "$LB" | cut -d' ' -f1); MN=$(md5sum < "$NB" | cut -d' ' -f1)
cd "$N" || exit 1
[ "$ML" = "${LEAN_WANT:?the swapped lean md5}" ] || { echo "smoke0438b ended $(date +%T): NOT STARTED, lean is ${ML:0:8}"; exit 1; }
[ "$MN" = "${NORMAL_WANT:?the swapped normal md5}" ] || { echo "smoke0438b ended $(date +%T): NOT STARTED, normal is ${MN:0:8}"; exit 1; }
for t in b438sc b438sn; do { [ -e "$R/$t-end.txt" ] || [ -e "$R/$t-start.txt" ]; } && { echo "smoke0438b ended $(date +%T): NOT STARTED, tag $t used"; exit 1; }; done
pgrep '^kyty_emulator' > /dev/null && { echo "smoke0438b ended $(date +%T): NOT STARTED, an emulator runs"; exit 1; }
for v in KYTY_BC5_0438_A1 KYTY_BC5_0438_A1P BC5_DIRECT_0438_A2 BC5_0438_INFLIGHT_NG BC5_0438_OPEN_NG; do
    [ -z "${!v+x}" ] || { echo "smoke0438b ended $(date +%T): NOT STARTED, $v is set (${!v}): the smoke runs the defaults"; exit 1; }
done
if [ -n "${CHAIN_LOCKLINE:-}" ] && [ "$(cat "$W/BOX-LOCK" 2> /dev/null)" = "$CHAIN_LOCKLINE" ]; then  # run-swap0438b.sh holds the one line
    . "$N/chainlock0417.inc"; chain_release() { :; }; echo "the lock line of the caller is taken over: $CHAIN_LOCKLINE"
else
. "$N/chainlock0417.inc"
chain_claim "exp 0438: smoke of the bake438b swap: ASTRO BOT lean 200 s + ASTRO BOT normal 200 s" 12 || { echo "smoke0438b ended $(date +%T): NOT STARTED"; exit 1; }
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
. "${SMOKE_DISP_INC:-$HOME/bc5-work/exp0438/display438.inc}" || { echo "smoke: no display438.inc: NOT STARTED"; exit 1; }
display_check || { echo "smoke: $DISP: not 1920x1080 (LESSONS R72): NOT STARTED"; exit 1; }
echo "smoke: $DISP"
lines() { # lines TAG: the bake's own log lines of one run (reported)
    local f="$R/$1-play.log"
    echo "$1: A1 [$(grep -ah 'exp 0438 A1 ranges map' "$f" 2> /dev/null | tail -1)]; A1P [$(grep -ah 'exp 0438 A1P memory tables in maps' "$f" 2> /dev/null | tail -1)]; physmap [$(grep -ah 'exp 0412 physmap sorted' "$f" 2> /dev/null | tail -1)]"
    echo "$1: A2 MISMATCH lines $(grep -ac 'tag a2): MISMATCH' "$f" 2> /dev/null), a2c438 lines $(grep -ac 'tag a2c438' "$f" 2> /dev/null); ng438 lines $(grep -ac 'ng438 (exp 0438): t ' "$f" 2> /dev/null), ng438 BUG lines $(grep -ac 'ng438 (exp 0438): BUG' "$f" 2> /dev/null); last: $(grep -ah 'ng438 (exp 0438): t ' "$f" 2> /dev/null | tail -1 | cut -c1-300)"
    echo "$1: a1c438 last: $(grep -ah 'tag a1c438): t ' "$f" 2> /dev/null | tail -1 | cut -c1-300)"
    echo "$1: r438 lines $(grep -ah 'r438 (exp 0438, b438)' "$f" 2> /dev/null | wc -l), BUG lines $(grep -ah 'r438 (exp 0438, b438): BUG' "$f" 2> /dev/null | wc -l)"
}
deadmnt && { echo "smoke0438b: a dead ASTRO mount inside the container: NOT STARTED"; exit 1; }
OK=1
echo "binaries: lean ${ML:0:8}, normal ${MN:0:8}, archive $(md5sum < "$W/backend-ubuntu/libbc5_backend.a" | cut -c1-8); kernel $(uname -r); boot $(cut -c1-8 /proc/sys/kernel/random/boot_id)"
padon b438sc; engines b438sc; exe b438sc
line=$(P_BIN=$LB P_WANT=$ML bash ./start0413g.sh b438sc astro 200 2>&1 | tail -1)
padoff b438sc; kill "$SAMP" 2> /dev/null
echo "b438sc: $line; real pad keys $PADN"
exechk b438sc "$ML"
case "$line" in *PASS*"kernel lines 0"*) ;; *) OK=0 ;; esac
[ "$PADN" = 0 ] || OK=0
lines b438sc
if [ "$OK" = 1 ]; then
    sleep 5
    deadmnt && { echo "b438sn: a dead ASTRO mount inside the container"; OK=0; }
fi
if [ "$OK" = 1 ]; then
    padon b438sn; engines b438sn; exe b438sn
    line=$(P_BIN=$NB P_WANT=$MN bash ./start0413g.sh b438sn astro 200 2>&1 | tail -1)
    padoff b438sn; kill "$SAMP" 2> /dev/null
    echo "b438sn: $line; real pad keys $PADN"
    exechk b438sn "$MN"
    case "$line" in *PASS*"kernel lines 0"*) ;; *) OK=0 ;; esac
    [ "$PADN" = 0 ] || OK=0
    lines b438sn
else echo "b438sn: not run"; fi
for t in b438sc b438sn; do [ -s "$R/$t-engines.txt" ] && echo "$t engines at 150 s: $(tr -s ' \n' ' ' < "$R/$t-engines.txt")"; done
echo "smoke0438b: $([ "$OK" = 1 ] && echo "ALL PASS" || echo "NOT ALL PASS")"
echo "smoke0438b ended $(date +%T)"
