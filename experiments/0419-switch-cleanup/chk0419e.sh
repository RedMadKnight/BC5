#!/usr/bin/env bash
# BC5 exp 0419: candidate E on the PRIVATE builds (exp0413/p; build it first with p0419e.sh). One chain, one lock line;
# every second-title run records pad keys (a foreign key voids the run). Private test directories only.
#   k0a     ASTRO BOT 120 s, a fresh private save directory. The title table must NOT speak (no "exp 0419: title" line).
#   k0x     ASTRO BOT 30 s on the kept bad save (wda/_SaveData.sm0), the fix off: the fault of exp 0417 section 15 is expected
#   k0f     the same with KYTY_BC5_SAVEDATA_TRANSFER_FIX=1: the start must pass and name the transfer as NOT_FOUND
#   k1      the second title's walk to G+240 with E's defaults (K1R on since the maintainer's play of 2026-11-13)
#   k1off   the same with BC5_GUARD_K1R=0 BC5_GUARD_K1_FILTER=0 (the comparison with B itself is B's own run: exp 0417's g1ctl / sw1)
#   k2cut   the cutscene arm (exp 0412's snapshot of 2026-11-13, slot 4, no input, 320 s: to its end, exp 0412's FAULTS row 1), E's defaults
#   k3l     lean 120 s
#   k4wall  the walk to G+560 with exp 0412's log-only zero scan of the launcher's eager heaps (BC5_DIRECT_ZEROSCAN_AT,
#           BC5_DIRECT_ZERO_NAMES), snap0412.sh and the emulator's fdinfo near G+500; its frame numbers are not comparable
# Each second-title run prints the title table's line (rows, taken, already set).
# usage (on the box, detached): chk0419e.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; E=$W/exp0413; N=$E/n; P=$E/p; R=$N/raw; FR=$HOME/bc5-data/captures/faults
cd "$N" || exit 1
. "$N/chainlock0417.inc"
PADS=()
padstop() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); }
fin() { padstop; chain_release; }
chain_claim "exp 0419 candidate E, private: ASTRO BOT (3 starts), the second title walk twice + cutscene arm to its end, lean, the wall walk to G+560" 65 || { echo "chk0419e ended $(date +%T): NOT STARTED"; exit 1; }
trap fin EXIT
recs() { find "$FR" -mindepth 1 -maxdepth 1 -type d -newermt "@$1" 2> /dev/null | wc -l; }
BN=$P/build-normal/src/kyty_emulator; BL=$P/build-lean/src/kyty_emulator; SN=$W/kytyplus-build/src/kyty_emulator
MN=$(md5sum < "$BN" | cut -d' ' -f1); ML=$(md5sum < "$BL" | cut -d' ' -f1); MS=$(md5sum < "$SN" | cut -d' ' -f1)
echo "binaries: B normal $MN, B lean $ML, shared normal $MS"
KERN=0; OK=1
second() {  # tag, binary, its md5, then words and N_* settings; sets OK=0 when not clean, KERN=1 on a kernel line
    local tag=$1 bin=$2 want=$3 t0 d n=0; t0=$(date +%s); shift 3
    local envs=() words=() w
    for w in "$@"; do case "$w" in N_*) envs+=("$w") ;; *) words+=("$w") ;; esac; done
    : > "$R/$tag-pad.txt"
    for d in /dev/input/by-id/*-event-joystick; do
        [ -e "$d" ] || continue
        n=$((n + 1))
        stdbuf -oL evtest "$d" 2> /dev/null | grep --line-buffered 'EV_KEY.*value 1' >> "$R/$tag-pad.txt" &
        PADS+=($!)
    done
    local line; line=$(env "${envs[@]}" P_BIN="$bin" P_WANT="$want" P_WORDS=$N/words0413nz.txt bash ./run0413p.sh "$tag" nozeroskip "${PLAYS:-240}" KYTY_BC5_LOAD_STAT="$R/$tag-loadstat.txt" "${words[@]}" | grep "^$tag ")
    padstop; pkill -u "$USER" -x evtest 2> /dev/null
    local J; J=$(sed -n 's/^journal \([^ ]*\) .*$/\1/p' "$R/$tag-journal.txt" 2> /dev/null)
    echo "$tag journal: would-learn $(grep -a -c '^would learn' "$J" 2> /dev/null), timeout-fault $(grep -a -c '^timeout: fault' "$J" 2> /dev/null), fault record lines $(grep -a -c 'fault record (exp 0412' "$J" 2> /dev/null)"
    grep -a '^lazy release (exp 0401 e7): t ' "$J" 2> /dev/null | sed -n '2,3p' | sed "s/^lazy release (exp 0401 e7)/$tag import/" | cut -c1-230
    echo "$tag route: $(grep -h 'route:' "$R/$tag-start.txt" 2> /dev/null | tr '\n' ';' | cut -c1-300); watchdog: $(tail -1 "$R/$tag-watchdog.txt" 2> /dev/null | cut -c21-140)"
    echo "$tag at ~104 s: $(awk -F'|' '$1+0 >= 100 {print "avail,swap,io" $2 "| psi" $3 "| gtt" $5; exit}' "$R/$tag-sampler.txt" 2> /dev/null | cut -c1-150)"
    echo "$tag at ~60 s: $(awk -F'|' '$1+0 >= 60 {print "avail,swap,io" $2 "| psi" $3 "| gtt" $5; exit}' "$R/$tag-sampler.txt" 2> /dev/null | cut -c1-150)"
    LOWF=$(awk '$1 >= 50 && $1 <= 84 { if (m == "" || $2 < m) { m = $2; t = $1 } } END { print (m == "" ? "none" : m " at " t " s") }' "$R/$tag-fps.txt" 2> /dev/null)
    PADN=$(wc -l < "$R/$tag-pad.txt")
    echo "$tag input: $n joystick(s) watched, pad key presses $PADN$( [ "$PADN" = 0 ] || awk -v t0="$t0" '{ sub(",", "", $3); printf " (first %.0f s after the run began: %s)", $3 - t0, $0; exit }' "$R/$tag-pad.txt" | cut -c1-200); lowest flips/s in 50..84 s: $LOWF"
    echo "$line"
    case "$line" in *"kernel lines 0"*) ;; *) KERN=1 ;; esac
    [ "$(recs "$t0")" = 0 ] || { echo "$tag: a NEW FAULT RECORD since it began: a finding, read record.txt under $FR"; OK=0; KERN=1; return; }
    case "$line" in *"ended at G+${PLAYS:-240}"*"kernel lines 0, crash lines 0"*) ;; *) OK=0; echo "$tag: NOT a clean run" ;; esac
    sleep 5
}
grep -aqF KYTY_BC5_TITLE_DEFAULTS "$BN" && grep -aqF KYTY_BC5_SAVEDATA_TRANSFER_FIX "$BN" || { echo "chk0419e ended $(date +%T): NOT STARTED, the private build is not candidate E"; exit 1; }
WD=$N/wda; KEEP=$WD/_SaveData.before-chk0419e-$$; mv "$WD/_SaveData" "$KEEP" && mkdir "$WD/_SaveData" || exit 1
back() { rm -rf "$WD/_SaveData"; mv "$KEEP" "$WD/_SaveData"; }
astro() {  # tag, seconds, words...
    local tag=$1 secs=$2; shift 2
    line=$(P_BIN=$BN P_WANT=$MN bash ./start0413g.sh "$tag" astro "$secs" "$@" 2>&1 | tail -1); echo "$line"
    echo "$tag stderr: title line $(grep -a -c 'exp 0419: title' "$R/$tag-play.log" 2> /dev/null), sdt417 $(grep -a 'sdt417:' "$R/$tag-play.log" 2> /dev/null | head -1 | cut -c1-120)"
    case "$line" in *"kernel lines 0"*) ;; *) KERN=1 ;; esac
}
astro k0a 120
case "$line" in *"PASS: ran 120 s"*"crash lines 0"*) ;; *) OK=0 ;; esac
rm -rf "$WD/_SaveData"; cp -a "$WD/_SaveData.sm0" "$WD/_SaveData"
astro k0x 30
case "$line" in *"ENDED BY ITSELF"*) echo "k0x: the fault is there without the fix, as expected" ;; *) echo "k0x: UNEXPECTED, the bad save did not fault without the fix" ;; esac
rm -rf "$WD/_SaveData"; cp -a "$WD/_SaveData.sm0" "$WD/_SaveData"
astro k0f 30 KYTY_BC5_SAVEDATA_TRANSFER_FIX=1
case "$line" in *"PASS: ran 30 s"*"crash lines 0"*) echo "k0f: the start PASSES with the fix" ;; *) echo "k0f: the fix does NOT cure the start"; OK=0 ;; esac
back
[ "$KERN" = 0 ] || { echo "chk0419e ended $(date +%T): STOPPED (a kernel line in an ASTRO BOT start)"; exit 1; }
title() { echo "$1 title table: $(grep -a 'exp 0419: title' "$R/$1-play.log" 2> /dev/null | head -1 | cut -c1-160)"; }
second k1 "$BN" "$MN"; title k1
[ "$PADN" = 0 ] || echo "k1: VOID as a measurement, a foreign pad key"
if [ "$KERN" = 0 ]; then second k1off "$BN" "$MN" BC5_GUARD_K1R=0 BC5_GUARD_K1_FILTER=0; title k1off; fi
if [ "$KERN" = 0 ]; then PLAYS=320 second k2cut "$BN" "$MN" N_SAVES=$HOME/bc5-data/saves/PPSA03671-20261113-0914-cutscene N_SLOT=4 N_NOWALK=1; title k2cut; fi
if [ "$KERN" = 0 ]; then
    line=$(P_BIN=$BL P_WANT=$ML P_WORDS=$N/words0413nz.txt bash ./start0413l.sh k3l lean 120 | grep "^k3l ")
    echo "$line"
    case "$line" in *"PASS: ran 120 s"*"kernel lines 0, crash lines 0"*) ;; *) OK=0; echo "k3l: the lean start was not clean" ;; esac
fi
# exp 0412's first measurement of the memory wall, log only (the top session: inside E's walk arm): the zero scan of the
# launcher's eager heaps at five moments, the whole-box table and the emulator's fdinfo near G+500. The scan preads the
# heaps on a nice-19 thread: this arm's frame numbers are NOT comparable with the others.
if [ "$KERN" = 0 ]; then
    ZN=$(sed -n 's/^export BC5_DIRECT_EAGER_NAMES="\(.*\)"$/\1/p' "$W/play-pkg.sh")
    [ -n "$ZN" ] || echo "k4wall: no BC5_DIRECT_EAGER_NAMES line in the launcher; the scan runs on its two default heaps"
    (
        until EP=$(pgrep -n '^kyty_emulator'); do sleep 2; done
        bash "$W/exp0412/snap0412.sh" "$R/k4wall-snap.txt" 615 > /dev/null 2>&1 &
        while [ -d "/proc/$EP" ] && [ $(($(date +%s) - $(stat -c %Y "/proc/$EP"))) -lt 615 ]; do sleep 5; done
        cat /proc/"$EP"/fdinfo/* 2> /dev/null | grep -a "drm-\|^pos" > "$R/k4wall-fdinfo.txt"
    ) &
    HP=$!
    PLAYS=560 second k4wall "$BN" "$MN" BC5_DIRECT_ZEROSCAN_AT=175,295,415,535,655 ${ZN:+"BC5_DIRECT_ZERO_NAMES=$ZN"}
    kill "$HP" 2> /dev/null
    J=$(sed -n 's/^journal \([^ ]*\) .*$/\1/p' "$R/k4wall-journal.txt" 2> /dev/null)
    echo "k4wall (frame numbers not comparable): zero scan lines $(grep -a -c '^zero scan' "$J" 2> /dev/null) in $J; snap $(wc -c < "$R/k4wall-snap.txt" 2> /dev/null) bytes, fdinfo $(wc -l < "$R/k4wall-fdinfo.txt" 2> /dev/null) lines"
    grep -a '^zero scan' "$J" 2> /dev/null | tail -4 | cut -c1-200
fi
echo "candidate E, private: $([ "$OK" = 1 ] && [ "$KERN" = 0 ] && echo "all as expected" || echo "NOT all as expected (OK $OK, kernel $KERN)")"
echo "chk0419e ended $(date +%T)"
