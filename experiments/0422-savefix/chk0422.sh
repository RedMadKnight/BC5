#!/usr/bin/env bash
# BC5 exp 0422: the checks of the save fix made fixed, on the SHARED binaries after int0422.sh (no switch set anywhere).
#   a1n, a1l   the first title 30 s on the kept bad save (exp 0417's _SaveData.sm0, F833's file): must PASS, normal and lean
#   a2n, a2l   the first title 120 s from an EMPTY save directory, a cross at 30, 45, 60, 75 and 90 s (F833's way to the
#              large first save), then a second start of 30 s on what it wrote (a2nn, a2ln): must not end at 5 s
#   w1n        the second title's walk to G+240 on normal (run0413p.sh, the journal-gated route, words0413nz.txt)
#   w2l        the second title on lean, 420 s: lean writes no journal, so the route is by time (a cross at 90, 100
#              and 108 s, then exp 0379's walk from 170 s for 240 s); pass = still running at the end, no kernel line,
#              no crash text. It shows no regression of the start, the menus and the load, not frame numbers.
# All RT on (the private input.cfg copies of the start scripts), ulimit -c 0, private save directories only.
# Corrected after the run (Codex 15:40 UTC, LESSONS R45): the version that ran also copied the maintainer's live saves
# and compared their sums before and after; that is removed. The first title's saves are the private wda copies; the second
# title's runs reset their private copy from exp 0412's named snapshot.
# A real pad key (evtest) marks a run VOID: the maintainer is at the box; the chain stops there.
# usage (on the box, detached, in ~/bc5-work/exp0422): bash chk0422.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0413/n; R=$N/raw; WD=$N/wda; HERE=$(cd "$(dirname "$0")" && pwd); F=_SaveData/TITLE1B/sce_sdmemory/memory.dat
NB=$W/kytyplus-build/src/kyty_emulator; LB=$W/kytyplus-build-lean/src/kyty_emulator
MN=$(md5sum < "$NB" | cut -d' ' -f1); ML=$(md5sum < "$LB" | cut -d' ' -f1)
cd "$N" || exit 1
. "$N/chainlock0417.inc"
if [ -n "${CHAIN_LOCKLINE:-}" ]; then
    [ "$(cat "$W/BOX-LOCK")" = "$CHAIN_LOCKLINE" ] || { echo "chk0422 ended $(date +%T): NOT STARTED, the chain's line is not in BOX-LOCK"; exit 1; }
    trap - EXIT; OWN=0
else
    chain_claim "exp 0422 checks of the save fix on the shared builds: the first title x6 (normal+lean), the second title walk normal + lean timed" 45 || { echo "chk0422 ended $(date +%T): NOT STARTED"; exit 1; }
    OWN=1
fi
for t in a1n a1l a2n a2nn a2l a2ln w1n w2l; do [ -e "$R/$t-end.txt" ] || [ -e "$R/$t-start.txt" ] && { echo "chk0422 ended $(date +%T): NOT STARTED, tag $t used"; exit 1; }; done
echo "binaries: shared normal $MN, shared lean $ML"
[ -d "$WD/_SaveData.sm0" ] || { echo "chk0422 ended $(date +%T): NOT STARTED, no kept bad save $WD/_SaveData.sm0"; exit 1; }
PADS=(); PADN=0
padon() { : > "$R/$1-pad.txt"; local d; for d in /dev/input/by-id/*-event-joystick; do [ -e "$d" ] || continue; stdbuf -oL evtest "$d" 2> /dev/null | grep --line-buffered 'EV_KEY.*value 1' >> "$R/$1-pad.txt" & PADS+=($!); done; }
padoff() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); pkill -u "$USER" -x evtest 2> /dev/null; PADN=$(wc -l < "$R/$1-pad.txt"); }
KEEP=$WD/_SaveData.before-chk0422-$$
mv "$WD/_SaveData" "$KEEP" && mkdir "$WD/_SaveData" || exit 1
fin() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; rm -rf "$WD/_SaveData"; mv "$KEEP" "$WD/_SaveData"; [ "$OWN" = 1 ] && chain_release; }
trap fin EXIT
OK=1; STOP=""
st() { if [ -f "$WD/$F" ]; then echo "memory.dat $(md5sum < "$WD/$F" | cut -c1-8), $(tr -d '\000' < "$WD/$F" | wc -c) non-zero bytes"; else echo "no memory.dat"; fi; }
t1() {  # tag binary md5 seconds want-pass words...
    local tag=$1 bin=$2 want=$3 secs=$4; shift 4
    padon "$tag"
    line=$(P_BIN=$bin P_WANT=$want bash ./start0413g.sh "$tag" t1 "$secs" "$@" 2>&1 | tail -1)
    padoff "$tag"
    echo "$line"
    echo "$tag: sdt417 lines $(grep -a -c 'sdt417:' "$R/$tag-play.log" 2> /dev/null): $(grep -a 'sdt417:' "$R/$tag-play.log" 2> /dev/null | sort | uniq -c | cut -c1-140 | tr '\n' ';'); $(st); real pad keys $PADN"
    [ "$PADN" = 0 ] || { STOP="a real pad key in $tag (the maintainer is at the box)"; OK=0; return; }
    case "$line" in *"kernel lines 0"*) ;; *) STOP="a kernel line in $tag"; OK=0; return ;; esac
    case "$line" in *"PASS: ran $secs s"*"crash lines 0"*) echo "$tag: PASS" ;; *) echo "$tag: NOT A PASS"; OK=0 ;; esac
}
fresh() {  # tag binary md5: 120 s from empty with five crosses, then the second start
    local tag=$1 bin=$2 want=$3 CMD=$N/cmd-$1.txt KP
    rm -rf "$WD/_SaveData"; mkdir "$WD/_SaveData" || return
    : > "$CMD"; (for t in 30 15 15 15 15; do sleep "$t"; printf 'press cross\n' >> "$CMD"; done) & KP=$!
    t1 "$tag" "$bin" "$want" 120 KYTY_BC5_INPUT_CMD="$CMD"
    kill "$KP" 2> /dev/null; echo "$tag: $(wc -l < "$CMD") cross presses sent"
    rm -rf "$WD/_SaveData.$tag"; cp -a "$WD/_SaveData" "$WD/_SaveData.$tag"
    [ -z "$STOP" ] || return
    sleep 5
    t1 "${tag}n" "$bin" "$want" 30
}
# 1. the kept bad save
for v in n l; do
    [ -z "$STOP" ] || break
    rm -rf "$WD/_SaveData"; cp -a "$WD/_SaveData.sm0" "$WD/_SaveData" || exit 1
    if [ $v = n ]; then t1 a1n "$NB" "$MN" 30; else t1 a1l "$LB" "$ML" 30; fi
    sleep 5
done
# 2. fresh, with crosses, then the second start (F833's case)
[ -z "$STOP" ] && fresh a2l "$LB" "$ML"
[ -z "$STOP" ] && { sleep 5; fresh a2n "$NB" "$MN"; }
# 3. the second title, normal walk
if [ -z "$STOP" ]; then
    sleep 5; padon w1n
    line=$(P_BIN=$NB P_WANT=$MN P_WORDS=$N/words0413nz.txt bash ./run0413p.sh w1n nozeroskip 240 | grep "^w1n ")
    padoff w1n; echo "$line; real pad keys $PADN"
    echo "w1n route: $(grep -h 'route:' "$R/w1n-start.txt" 2> /dev/null | tr '\n' ';' | cut -c1-300)"
    [ "$PADN" = 0 ] || { STOP="a real pad key in w1n"; OK=0; }
    case "$line" in *"kernel lines 0"*) ;; *) STOP="${STOP:-a kernel line in w1n}"; OK=0 ;; esac
    case "$line" in *"ended at G+240"*"kernel lines 0, crash lines 0"*) echo "w1n: clean to G+240" ;; *) echo "w1n: NOT clean"; OK=0 ;; esac
fi
# 4. the second title, lean, by time
if [ -z "$STOP" ]; then
    sleep 5; CMD=$N/cmd-w2l.txt
    { printf 'wait 90000\npress cross\nwait 10000\npress cross\nwait 8000\npress cross\nwait 62000\n'
      c=0; while [ $c -lt 14 ]; do s=255; [ $(((c / 4) % 2)) = 1 ] && s=0; printf 'stick l 128 0 15000\nstick r %d 128 1200\nwait 300\n' "$s"; c=$((c + 1)); done
      printf 'stick l 128 128\nstick r 128 128\n'; } > "$CMD"
    padon w2l
    line=$(P_BIN=$LB P_WANT=$ML P_WORDS=$N/words0413nz.txt bash ./start0413l.sh w2l lean 420 KYTY_BC5_INPUT_CMD="$CMD" | grep "^w2l ")
    padoff w2l; echo "$line; real pad keys $PADN; key lines done $(cat "$CMD.done" 2> /dev/null || echo '?') of $(wc -l < "$CMD")"
    [ "$PADN" = 0 ] || OK=0
    case "$line" in *"PASS: ran 420 s"*"kernel lines 0, crash lines 0"*) echo "w2l: PASS (ran 420 s, the timed route and the walk)" ;; *) echo "w2l: NOT A PASS"; OK=0 ;; esac
fi
echo "chk0422: $([ "$OK" = 1 ] && echo "ALL PASS" || echo "NOT ALL PASS${STOP:+ (stopped: $STOP)}")"
echo "chk0422 ended $(date +%T)"
